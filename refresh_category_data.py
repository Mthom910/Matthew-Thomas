"""
Pulls Job/JobLine data from the Insyte OData v4 API, categorises product lines,
dedupes revised quote/order versions, and writes a pre-aggregated JSON file
for the category_performance_dashboard.html dashboard to render.

Run:  python refresh_category_data.py

Credentials come from environment variables — see .env.example. Copy it to
.env and fill in real values; never hardcode credentials in this file.
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

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
BASE_URL = os.environ.get("INSYTE_BASE_URL", "https://api.myinsyte.com.au/v2")
EMAIL = os.environ["INSYTE_EMAIL"]
API_KEY = os.environ["INSYTE_API_KEY"]

MONTHS_BACK = 24        # how much history to pull, in whole calendar months
PAGE_SIZE = 1000        # server caps $top at 1000 regardless of requested value
MAX_WORKERS = 6         # concurrent month-fetches

OUTPUT_FILE = "insyte_category_data.json"

# ─────────────────────────────────────────────────────────────
# PRODUCT -> CATEGORY MAPPING (Insyte has no native category field,
# so we derive one from the free-text Product name). Order matters —
# first matching keyword wins.
# ─────────────────────────────────────────────────────────────
CATEGORY_RULES = [
    ("shutter", "Plantation Shutters"),
    ("venetian", "Venetian Blinds"),
    ("vertical", "Vertical Blinds"),
    ("awning", "Awnings"),
    ("roller", "Roller Blinds"),
    ("sheerview", "Roller Blinds"),
    ("curtain", "Curtains & Soft Furnishings"),
    ("roman", "Curtains & Soft Furnishings"),
    ("pelmet", "Curtains & Soft Furnishings"),
    ("pleated", "Curtains & Soft Furnishings"),
    ("rod system", "Curtains & Soft Furnishings"),
]
FALLBACK_CATEGORY = "Accessories & Other"

# ─────────────────────────────────────────────────────────────
# STATE NORMALISATION (Address.State is free text in Insyte — mixed
# case, abbreviations, full names, and occasional garbage/suburb entries)
# ─────────────────────────────────────────────────────────────
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


def categorize(product_name):
    name = (product_name or "").strip().lower()
    for keyword, category in CATEGORY_RULES:
        if keyword in name:
            return category
    return FALLBACK_CATEGORY


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


# ─────────────────────────────────────────────────────────────
# EXCLUSIONS (mirrors the logic used in the existing revenue-initiative
# dashboard, extended to cover quote/lost stages as well as won)
# ─────────────────────────────────────────────────────────────
EXCL_LINE_TYPE = {"type_job_line_remake", "type_job_line_service", "type_job_line_alter"}
EXCL_LINE_STATUS = {"status_job_line_cancelled"}
EXCL_JOB_STATUS = {"status_job_cancelled"}

WON_STAGES = {"stage_job_order", "stage_job_order_edit"}
LOST_STAGE = "stage_job_lost"
QUOTE_STAGE = "stage_job_quote"


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
        # step back one month
        prev_month_end = cur - timedelta(days=1)
        cur = prev_month_end.replace(day=1)
    starts.append(cur)  # extra boundary at the tail
    return list(reversed(starts))  # oldest -> newest


def fetch_month(session, start, end):
    f = (
        f"Job/JobDate ge {start.strftime('%Y-%m-%dT00:00:00Z')} "
        f"and Job/JobDate lt {end.strftime('%Y-%m-%dT00:00:00Z')} "
        f"and Job/JobType eq 'type_job_sales' "
        f"and Status ne 'status_job_line_cancelled'"
    )
    select = (
        "ID,JobID,Product,Qty,StandardPriceExTax,DiscountedPriceExTax,"
        "StandardCostExTax,DiscountedCostExTax,StandardIntallCostExTax,"
        "StandardDeliveryCostExTax,LineType,Status,Stage"
    )
    expand = "Job($select=Reference,Stage,Status,JobDate,SalesRepID;$expand=Address($select=State))"
    return fetch_all(session, "/JobLines", filter_str=f, select=select, expand=expand)


# ─────────────────────────────────────────────────────────────
# AGGREGATION
# ─────────────────────────────────────────────────────────────
def build_subjobs(lines):
    """Group raw job-line rows into per-JobID (sub-job) aggregates."""
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
                "state": normalize_state((job.get("Address") or {}).get("State")),
                "stdTotal": 0.0,
                "discTotal": 0.0,
                "costTotal": 0.0,
                "qty": 0.0,
                "lineCount": 0,
                "catStd": defaultdict(float),
                "prodAgg": defaultdict(lambda: {"std": 0.0, "disc": 0.0, "cost": 0.0, "qty": 0.0, "lines": 0}),
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
        qty = l.get("Qty") or 0.0
        sj["stdTotal"] += std
        sj["discTotal"] += disc
        sj["costTotal"] += cost
        sj["qty"] += qty
        sj["lineCount"] += 1

        product_name = (l.get("Product") or "").strip() or "Unspecified"
        sj["catStd"][categorize(product_name)] += std

        p = sj["prodAgg"][product_name]
        p["std"] += std
        p["disc"] += disc
        p["cost"] += cost
        p["qty"] += qty
        p["lines"] += 1

    return subjobs


def base_ref(reference):
    return re.sub(r"-\d+$", "", reference or "")


def canonicalize(subjobs):
    """Dedupe revised quote/order versions sharing the same base reference,
    keeping only the latest (by JobDate) sub-job as the current state."""
    groups = defaultdict(list)
    for sj in subjobs.values():
        groups[base_ref(sj["reference"])].append(sj)

    canonical = []
    product_rows = []
    skipped_cancelled = 0
    skipped_other_stage = 0
    for group in groups.values():
        group.sort(key=lambda x: x["jobDate"])
        latest = group[-1]
        if latest["status"] in EXCL_JOB_STATUS:
            skipped_cancelled += 1
            continue

        stage = latest["stage"]
        if stage in WON_STAGES:
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

        dominant_category = FALLBACK_CATEGORY
        if latest["catStd"]:
            dominant_category = max(latest["catStd"].items(), key=lambda kv: kv[1])[0]

        month = (latest["jobDate"] or "")[:7]

        canonical.append({
            "month": month,
            "category": dominant_category,
            "state": latest["state"],
            "stage": bucket,
            "revenue": round(disc_total, 2),
            "stdRevenue": round(std_total, 2),
            "gp": round(gp, 2),
            "gpPct": gp_pct,
            "discPct": disc_pct,
            "discBucket": discount_bucket(disc_pct),
            "qty": round(latest["qty"], 2),
        })

        for product_name, p in latest["prodAgg"].items():
            p_gp = p["disc"] - p["cost"]
            product_rows.append({
                "month": month,
                "category": categorize(product_name),
                "product": product_name,
                "stage": bucket,
                "lines": p["lines"],
                "qty": round(p["qty"], 2),
                "revenue": round(p["disc"], 2),
                "stdRevenue": round(p["std"], 2),
                "gp": round(p_gp, 2),
            })

    return canonical, product_rows, skipped_cancelled, skipped_other_stage


def aggregate(canonical_jobs, product_rows):
    """Roll canonical jobs up into compact summary tables for the dashboard."""
    monthly_category = defaultdict(lambda: {
        "jobs": 0, "qty": 0.0, "revenue": 0.0, "stdRevenue": 0.0, "gp": 0.0,
    })
    discount_band_category = defaultdict(lambda: {"jobs": 0, "revenue": 0.0})
    product_performance = defaultdict(lambda: {
        "lines": 0, "qty": 0.0, "revenue": 0.0, "stdRevenue": 0.0, "gp": 0.0,
    })

    categories_seen = set()
    months_seen = set()
    states_seen = set()
    products_seen = set()

    for j in canonical_jobs:
        categories_seen.add(j["category"])
        months_seen.add(j["month"])
        states_seen.add(j["state"])

        mk = (j["month"], j["category"], j["state"], j["stage"])
        m = monthly_category[mk]
        m["jobs"] += 1
        m["qty"] += j["qty"]
        m["revenue"] += j["revenue"]
        m["stdRevenue"] += j["stdRevenue"]
        m["gp"] += j["gp"]

        if j["stage"] in ("won", "lost"):
            bk = (j["category"], j["discBucket"], j["stage"])
            b = discount_band_category[bk]
            b["jobs"] += 1
            b["revenue"] += j["revenue"]

    for p in product_rows:
        products_seen.add(p["product"])
        pk = (p["month"], p["category"], p["product"], p["stage"])
        agg = product_performance[pk]
        agg["lines"] += p["lines"]
        agg["qty"] += p["qty"]
        agg["revenue"] += p["revenue"]
        agg["stdRevenue"] += p["stdRevenue"]
        agg["gp"] += p["gp"]

    monthly_category_rows = [
        {"month": mk[0], "category": mk[1], "state": mk[2], "stage": mk[3], **{k: round(v, 2) for k, v in v.items()}}
        for mk, v in monthly_category.items()
    ]
    discount_band_rows = [
        {"category": bk[0], "band": bk[1], "stage": bk[2], **{k: round(v, 2) for k, v in v.items()}}
        for bk, v in discount_band_category.items()
    ]
    product_performance_rows = [
        {"month": pk[0], "category": pk[1], "product": pk[2], "stage": pk[3], **{k: round(v, 2) for k, v in v.items()}}
        for pk, v in product_performance.items()
    ]

    return {
        "categories": sorted(categories_seen),
        "months": sorted(months_seen),
        "states": sorted(states_seen),
        "products": sorted(products_seen),
        "monthlyCategory": monthly_category_rows,
        "discountBandCategory": discount_band_rows,
        "productPerformance": product_performance_rows,
    }


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    session = make_session()
    boundaries = month_starts(MONTHS_BACK)  # oldest -> newest, len = MONTHS_BACK+1

    print(f"Fetching {MONTHS_BACK} months of JobLines ({boundaries[0].date()} to {boundaries[-1].date()})...")

    all_lines = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {}
        for i in range(len(boundaries) - 1):
            start, end = boundaries[i], boundaries[i + 1]
            fut = pool.submit(fetch_month, session, start, end)
            futures[fut] = start.strftime("%Y-%m")

        done = 0
        for fut in as_completed(futures):
            month_label = futures[fut]
            rows = fut.result()
            all_lines.extend(rows)
            done += 1
            print(f"  [{done}/{len(futures)}] {month_label}: {len(rows)} lines")

    print(f"Total lines fetched: {len(all_lines)}")

    subjobs = build_subjobs(all_lines)
    print(f"Distinct sub-jobs: {len(subjobs)}")

    canonical_jobs, product_rows, skipped_cancelled, skipped_other_stage = canonicalize(subjobs)
    print(f"Canonical jobs after dedup: {len(canonical_jobs)} "
          f"(skipped {skipped_cancelled} cancelled, {skipped_other_stage} other-stage)")

    aggregates = aggregate(canonical_jobs, product_rows)

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dateRange": {
            "from": boundaries[0].strftime("%Y-%m-%d"),
            "to": boundaries[-1].strftime("%Y-%m-%d"),
        },
        **aggregates,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {OUTPUT_FILE} ({len(aggregates['monthlyCategory'])} monthly-category rows, "
          f"{len(aggregates['discountBandCategory'])} discount-band rows, "
          f"{len(aggregates['productPerformance'])} product-performance rows)")


if __name__ == "__main__":
    main()
