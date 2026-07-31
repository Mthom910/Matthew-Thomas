"""
Pulls Job/JobLine, Sales Appointment Activity, and Opportunity data from the
Insyte OData v4 API and writes a JSON file for insyte_revenue_initiative.html
to render: the Revenue Management Initiative dashboard analysing whether the
35-40% discount bracket (with its tiered consultant commission incentive)
increases conversion on $5,000+ jobs.

Run:  python refresh_initiative_data.py

Credentials come from environment variables — see .env.example. Copy it to
.env and fill in real values; never hardcode credentials in this file.

ARCHITECTURE: unlike refresh_category_data.py (which pre-aggregates in
Python), this script writes near-raw per-job and per-appointment records.
The dashboard's Config panel (min job value, commission rates, YTD date
ranges) recomputes every KPI/chart client-side from these raw records, so
changing a config value doesn't require re-running this script — only
"Refresh" (reloading the JSON) needs a fresh pull.

ORDER INTAKE, NOT INSTALLED REVENUE: a job is "confirmed" (won) the moment it
receives its first confirmed payment — i.e. when the customer pays a deposit
— not when Insyte's internal Stage/OrderDate fields flip (those track the
supply chain: manufacturing/dispatch, which lags the actual sale, sometimes
by weeks). We deliberately don't rely on Payment.IsDeposit (see below) —
instead the earliest confirmed, non-refund/transfer payment allocated to a
job is treated as its deposit/order-intake date.

KNOWN DATA LIMITATIONS:
  - Payment.IsDeposit is null on ~55% of Payment records tenant-wide (it
    looks like a relatively recent field that isn't consistently set), so
    filtering on it would silently drop roughly half of all real deposits.
    We use "first confirmed payment of type_payment_payment allocated to
    the job" instead — robust to the flag's incomplete population, and
    functionally the same thing (the first money received on a job that
    hasn't been fully paid yet, in practice, is the deposit).
  - Opportunities endpoint's ExpectedRevenue field is populated on only a
    handful of records tenant-wide (confirmed: ~14 of many thousands have
    ExpectedRevenue > 0, none in the current YTD windows), so the
    "Opportunity Pipeline" section will render empty. This mirrors the same
    field being effectively unused in the source system, not a bug in the
    dashboard or this script.
"""

import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()

BASE_URL = os.environ.get("INSYTE_BASE_URL", "https://api.myinsyte.com.au/v2")
EMAIL = os.environ["INSYTE_EMAIL"]
API_KEY = os.environ["INSYTE_API_KEY"]

OUTPUT_FILE = "insyte_initiative_data.json"
PAGE_SIZE = 1000
MAX_WORKERS = 6
MONTHS_BACK = 19          # covers Jan of last year through the current month

DISCOUNT_BUCKETS = [
    ("0-10%", 0, 10),
    ("10-20%", 10, 20),
    ("20-30%", 20, 30),
    ("30-35%", 30, 35),
    ("35-40%", 35, 40),
    ("40-50%", 40, 50),
    ("50%+", 50, 1000),
]


def discount_bucket(disc_pct):
    for label, lo, hi in DISCOUNT_BUCKETS:
        if lo <= disc_pct < hi:
            return label
    return DISCOUNT_BUCKETS[-1][0]


STATE_NORMALIZE = {
    "NSW": "NSW", "VIC": "VIC", "QLD": "QLD", "SA": "SA",
    "WA": "WA", "TAS": "TAS", "NT": "NT", "ACT": "ACT",
    "NEW SOUTH WALES": "NSW", "VICTORIA": "VIC", "QUEENSLAND": "QLD",
    "SOUTH AUSTRALIA": "SA", "WESTERN AUSTRALIA": "WA", "TASMANIA": "TAS",
    "NORTHERN TERRITORY": "NT", "AUSTRALIAN CAPITAL TERRITORY": "ACT",
}


def normalize_state(raw):
    s = (raw or "").strip().upper().rstrip(".")
    return STATE_NORMALIZE.get(s, "Other")


def clean_name(raw):
    return re.sub(r"\s+", " ", (raw or "")).strip() or "Unassigned"


EXCL_LINE_TYPE = {"type_job_line_remake", "type_job_line_service", "type_job_line_alter"}
EXCL_LINE_STATUS = {"status_job_line_cancelled"}
EXCL_JOB_STATUS = {"status_job_cancelled"}

WON_STAGES = {"stage_job_order", "stage_job_order_edit"}
LOST_STAGE = "stage_job_lost"
QUOTE_STAGE = "stage_job_quote"

ACTIVITY_TYPE = "Sales Appointment"
PAYMENT_STATUS_CONFIRMED = "status_payment_confirmed"
PAYMENT_TYPE_PAYMENT = "type_payment_payment"


# ─────────────────────────────────────────────────────────────
# API CLIENT
# ─────────────────────────────────────────────────────────────
def make_session():
    s = requests.Session()
    s.auth = (EMAIL, API_KEY)
    s.headers.update({"Accept": "application/json"})
    adapter = HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
    s.mount("https://", adapter)
    return s


def fetch_all(session, path, filter_str=None, select=None, expand=None):
    rows = []
    skip = 0
    while True:
        params = {"$top": PAGE_SIZE, "$skip": skip}
        if filter_str:
            params["$filter"] = filter_str
        if select:
            params["$select"] = select
        if expand:
            params["$expand"] = expand

        last_exc = None
        for attempt in range(5):
            try:
                r = session.get(f"{BASE_URL}{path}", params=params, timeout=90)
                r.raise_for_status()
                data = r.json()
                break
            except (requests.exceptions.RequestException, ValueError) as e:
                last_exc = e
                if attempt < 4:
                    time.sleep(2 ** attempt)
                else:
                    raise last_exc

        page = data.get("value", [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
    return rows


def month_starts(months_back):
    now = datetime.now(timezone.utc)
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    starts = []
    cur = first_of_this_month
    for _ in range(months_back):
        starts.append(cur)
        prev_month_end = cur - timedelta(days=1)
        cur = prev_month_end.replace(day=1)
    starts.append(cur)
    return list(reversed(starts))  # oldest -> newest


JOB_EXPAND = (
    "Job($select=Reference,Stage,Status,JobDate,SalesRepID,BusinessUnitID;"
    "$expand=SalesRep($select=FullName),Address($select=State))"
)
JOB_LINE_SELECT = (
    "ID,JobID,Product,Qty,StandardPriceExTax,DiscountedPriceExTax,"
    "StandardCostExTax,DiscountedCostExTax,StandardIntallCostExTax,"
    "StandardDeliveryCostExTax,LineType,Status,Stage"
)


def fetch_job_lines_month(session, start, end):
    f = (
        f"Job/JobDate ge {start.strftime('%Y-%m-%dT00:00:00Z')} "
        f"and Job/JobDate lt {end.strftime('%Y-%m-%dT00:00:00Z')} "
        f"and Job/JobType eq 'type_job_sales' "
        f"and Status ne 'status_job_line_cancelled'"
    )
    return fetch_all(session, "/JobLines", filter_str=f, select=JOB_LINE_SELECT, expand=JOB_EXPAND)


PAYMENT_EXPAND = "Payment($select=Date)"


def fetch_payments_month(session, start, end):
    f = (
        f"Payment/Date ge {start.strftime('%Y-%m-%dT00:00:00Z')} "
        f"and Payment/Date lt {end.strftime('%Y-%m-%dT00:00:00Z')} "
        f"and Payment/Status eq '{PAYMENT_STATUS_CONFIRMED}' "
        f"and Payment/Type eq '{PAYMENT_TYPE_PAYMENT}'"
    )
    select = "ID,JobID,PaymentID"
    return fetch_all(session, "/JobPaymentAllocations", filter_str=f, select=select, expand=PAYMENT_EXPAND)


def build_deposit_map(rows):
    """JobID -> earliest confirmed-payment date string (the order-intake / deposit moment)."""
    deposit_map = {}
    for r in rows:
        jid = r.get("JobID")
        date = (r.get("Payment") or {}).get("Date")
        if jid is None or not date:
            continue
        date10 = date[:10]
        if jid not in deposit_map or date10 < deposit_map[jid]:
            deposit_map[jid] = date10
    return deposit_map


REP_EXPAND = "Representative($select=FullName)"


def fetch_appointments_month(session, start, end):
    f = (
        f"ActivityType eq '{ACTIVITY_TYPE}' "
        f"and Start ge {start.strftime('%Y-%m-%dT00:00:00Z')} "
        f"and Start lt {end.strftime('%Y-%m-%dT00:00:00Z')}"
    )
    select = "ID,Start,Status,Cancelled,RepresentativeID"
    return fetch_all(session, "/Activities", filter_str=f, select=select, expand=REP_EXPAND)


def fetch_month_ranged(session, fetch_fn, boundaries, label):
    print(f"Fetching {label} ({boundaries[0].date()} to {boundaries[-1].date()})...")
    all_rows = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {}
        for i in range(len(boundaries) - 1):
            start, end = boundaries[i], boundaries[i + 1]
            fut = pool.submit(fetch_fn, session, start, end)
            futures[fut] = start.strftime("%Y-%m")
        done = 0
        for fut in as_completed(futures):
            month_label = futures[fut]
            rows = fut.result()
            all_rows.extend(rows)
            done += 1
            print(f"  [{done}/{len(futures)}] {month_label}: {len(rows)} rows")
    print(f"Total {label}: {len(all_rows)}")
    return all_rows


# ─────────────────────────────────────────────────────────────
# JOB CANONICALISATION (mirrors refresh_category_data.py's dedup logic)
# ─────────────────────────────────────────────────────────────
def build_subjobs(lines):
    subjobs = {}
    for l in lines:
        if l.get("LineType") in EXCL_LINE_TYPE:
            continue
        if l.get("Status") in EXCL_LINE_STATUS:
            continue
        job = l.get("Job") or {}
        if not job:
            continue
        jid = l["JobID"]
        sj = subjobs.get(jid)
        if sj is None:
            sj = {
                "jobId": jid,
                "reference": job.get("Reference") or str(jid),
                "stage": job.get("Stage"),
                "status": job.get("Status"),
                "jobDate": job.get("JobDate") or "",
                "rep": clean_name(((job.get("SalesRep") or {}).get("FullName"))),
                "state": normalize_state((job.get("Address") or {}).get("State")),
                "stdTotal": 0.0,
                "discTotal": 0.0,
                "costTotal": 0.0,
            }
            subjobs[jid] = sj

        std = l.get("StandardPriceExTax") or 0.0
        disc = l.get("DiscountedPriceExTax")
        disc = disc if disc is not None else std
        cost = (
            (l.get("DiscountedCostExTax") or l.get("StandardCostExTax") or 0.0)
            + (l.get("StandardIntallCostExTax") or 0.0)
            + (l.get("StandardDeliveryCostExTax") or 0.0)
        )
        sj["stdTotal"] += std
        sj["discTotal"] += disc
        sj["costTotal"] += cost

    return subjobs


def base_ref(reference):
    return re.sub(r"-\d+$", "", reference or "")


def canonicalize(subjobs, deposit_map):
    groups = defaultdict(list)
    for sj in subjobs.values():
        groups[base_ref(sj["reference"])].append(sj)

    canonical = []
    skipped_cancelled = 0
    skipped_other_stage = 0
    won_by_stage_no_payment = 0  # Stage says "order" but no confirmed payment found (data-quality signal)
    for group in groups.values():
        group.sort(key=lambda x: x["jobDate"])
        first = group[0]
        latest = group[-1]
        if latest["status"] in EXCL_JOB_STATUS:
            skipped_cancelled += 1
            continue

        # Order intake = first confirmed payment received on ANY revision of this job,
        # not Insyte's internal Stage/OrderDate (which tracks manufacturing/dispatch and
        # lags the actual sale). This is the "deposit received" moment.
        deposit_dates = [deposit_map[sj["jobId"]] for sj in group if sj["jobId"] in deposit_map]
        confirmed_date = min(deposit_dates) if deposit_dates else None

        stage = latest["stage"]
        if not confirmed_date and stage in WON_STAGES:
            won_by_stage_no_payment += 1

        if confirmed_date:
            bucket = "won"
        elif stage == LOST_STAGE:
            bucket = "lost"
        elif stage == QUOTE_STAGE:
            bucket = "quote"
        else:
            skipped_other_stage += 1
            continue

        std_total = latest["stdTotal"]
        disc_total = latest["discTotal"]
        cost_total = latest["costTotal"]
        disc_pct = round((1 - disc_total / std_total) * 100, 1) if std_total > 0 else 0.0
        disc_pct = max(0.0, min(100.0, disc_pct))
        gp = disc_total - cost_total
        gp_pct = round((gp / disc_total) * 100, 1) if disc_total > 0 else 0.0

        canonical.append({
            "ref": base_ref(latest["reference"]),
            "firstDate": (first["jobDate"] or "")[:10],
            "jobDate": (latest["jobDate"] or "")[:10],
            "confirmedDate": confirmed_date,
            "stage": bucket,
            "rep": latest["rep"],
            "state": latest["state"],
            "revenue": round(disc_total, 2),
            "stdRevenue": round(std_total, 2),
            "cost": round(cost_total, 2),
            "gp": round(gp, 2),
            "gpPct": gp_pct,
            "discPct": disc_pct,
            "discBucket": discount_bucket(disc_pct),
        })

    return canonical, skipped_cancelled, skipped_other_stage, won_by_stage_no_payment


# ─────────────────────────────────────────────────────────────
# APPOINTMENTS
# ─────────────────────────────────────────────────────────────
def build_appointments(rows):
    out = []
    excluded = 0
    for r in rows:
        if r.get("Cancelled") or r.get("Status") == "activity_status_cancelled":
            excluded += 1
            continue
        start = r.get("Start")
        if not start:
            continue
        rep = clean_name((r.get("Representative") or {}).get("FullName"))
        out.append({"date": start[:10], "rep": rep})
    return out, excluded


# ─────────────────────────────────────────────────────────────
# OPPORTUNITIES (see module docstring — expect this to be near-empty)
# ─────────────────────────────────────────────────────────────
def fetch_opportunities(session):
    select = "ID,Status,PipelineStage,ExpectedRevenue,CloseDate,LeadDate,RepresentativeID"
    expand = "Representative($select=FullName)"
    rows = fetch_all(session, "/Opportunities", filter_str="ExpectedRevenue gt 0", select=select, expand=expand)
    out = []
    for r in rows:
        out.append({
            "leadDate": (r.get("LeadDate") or "")[:10],
            "closeDate": (r.get("CloseDate") or "")[:10] if r.get("CloseDate") else None,
            "status": r.get("Status"),
            "pipelineStage": r.get("PipelineStage"),
            "expectedRevenue": r.get("ExpectedRevenue"),
            "rep": clean_name((r.get("Representative") or {}).get("FullName")),
        })
    return out


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    session = make_session()
    boundaries = month_starts(MONTHS_BACK)

    job_lines = fetch_month_ranged(session, fetch_job_lines_month, boundaries, "JobLines")
    appointment_rows = fetch_month_ranged(session, fetch_appointments_month, boundaries, "Sales Appointments")
    payment_rows = fetch_month_ranged(session, fetch_payments_month, boundaries, "confirmed Payment allocations")

    print("Fetching Opportunities with ExpectedRevenue > 0 (tenant-wide, expected to be a small set)...")
    opportunities = fetch_opportunities(session)
    print(f"  {len(opportunities)} opportunities with nonzero ExpectedRevenue")

    subjobs = build_subjobs(job_lines)
    print(f"Distinct sub-jobs: {len(subjobs)}")

    deposit_map = build_deposit_map(payment_rows)
    print(f"Jobs with a confirmed payment (deposit/order-intake) in window: {len(deposit_map)}")

    canonical_jobs, skipped_cancelled, skipped_other_stage, won_no_payment = canonicalize(subjobs, deposit_map)
    print(f"Canonical jobs after dedup: {len(canonical_jobs)} "
          f"(skipped {skipped_cancelled} cancelled, {skipped_other_stage} other-stage)")
    print(f"Jobs Insyte marks as 'order' stage but with no matching confirmed payment found: {won_no_payment} "
          f"(these are NOT counted as won under the deposit-based definition)")

    appointments, excluded_appointments = build_appointments(appointment_rows)
    print(f"Appointments kept: {len(appointments)} (excluded {excluded_appointments} cancelled)")

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dateRange": {
            "from": boundaries[0].strftime("%Y-%m-%d"),
            "to": boundaries[-1].strftime("%Y-%m-%d"),
        },
        "jobs": canonical_jobs,
        "appointments": appointments,
        "opportunities": opportunities,
        "dataQuality": {
            "skippedCancelledJobs": skipped_cancelled,
            "skippedOtherStageJobs": skipped_other_stage,
            "excludedCancelledAppointments": excluded_appointments,
            "jobsWithConfirmedPayment": len(deposit_map),
            "insyteOrderStageWithoutPayment": won_no_payment,
            "orderIntakeNote": (
                "'Won' = first confirmed payment received (order intake / deposit), not "
                "Insyte's Stage/OrderDate fields (which track manufacturing/dispatch and "
                "lag the actual sale). Payment.IsDeposit is null on ~55% of records "
                "tenant-wide so it isn't used directly; the earliest confirmed, "
                "non-refund payment allocated to a job is treated as its deposit."
            ),
            "opportunitiesWithRevenueNote": (
                "Insyte's Opportunities.ExpectedRevenue field is populated on only a "
                "handful of records tenant-wide, none falling in the current YTD "
                "windows in most refreshes — the Opportunity Pipeline chart will be "
                "empty until this field is actually used in Insyte."
            ),
        },
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {OUTPUT_FILE} ({len(canonical_jobs)} jobs, {len(appointments)} appointments, "
          f"{len(opportunities)} opportunities)")


if __name__ == "__main__":
    main()
