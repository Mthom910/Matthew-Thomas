"""
Pulls Sales Appointment + Calendar Note activity data from the Insyte OData v4
API for Victory Curtains & Blinds, and writes a pre-aggregated JSON file for
appointment_health_dashboard.html to render (DATA[brand] shape).

Run:  python refresh_appointment_data.py

Credentials come from environment variables — see .env.example. Copy it to
.env and fill in real values; never hardcode credentials in this file.

SCOPE / KNOWN LIMITATIONS (see README.md for full detail):
  - Victory only. The credentials this script uses have no visibility into
    any Wynstan business unit — Wynstan appears to be a separate Insyte
    tenant. The dashboard keeps Wynstan on its original sample data.
  - No-show = an appointment whose Status is still "activity_status_open"
    (never closed out by staff) after its End time has passed. Insyte has
    no explicit no-show flag; this heuristic was confirmed by the business
    owner as the correct real-world signal.
  - Slot capacity comes from "Calendar Note" activities, where staff log
    free-text rosters like "2 @ 9 - 12, 2 @ 12 - 3" or "off". About 82% of
    notes in a sample window matched a parseable capacity/off-day pattern;
    the rest (area/product restriction notes, one-off comments) carry no
    capacity signal and are excluded from the fill-rate denominator rather
    than guessed at. dataQuality.capacityNoteCoverage in the output JSON
    reports the actual parse rate for whatever period was just pulled.
  - The dashboard's diary grid is a fixed 3-slots/day (morning/midday/
    afternoon) x 5-day layout, so real slot times/counts are bucketed into
    those 3 windows rather than shown at full resolution.
  - No consultant name-based filtering is applied. Every Representative
    with a real Sales Appointment booking is included as-is.
  - On-time rate has no source field in Insyte (only scheduled Start/End,
    no actual arrival time) — it is emitted as null and the dashboard
    renders "N/A" for it.
"""

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

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

OUTPUT_FILE = "insyte_appointment_data.json"
PAGE_SIZE = 1000
TREND_WEEKS = 8            # weeks of history behind the current week, for the trend chart
ACTIVITY_TYPE = "Sales Appointment"

BUSINESS_UNIT_REGION = {
    "Hunter Douglas Pty Limited trading as Victory Curtains & Blinds Victoria": ("VIC", "Australia/Melbourne"),
    "Hunter Douglas Pty Limited trading as Victory Curtains & Blinds Queensland": ("QLD", "Australia/Brisbane"),
    "Hunter Douglas Pty Limited trading as Victory Curtains & Blinds NSW": ("NSW", "Australia/Sydney"),
    "Hunter Douglas Pty Limited trading as Victory Curtains & Blinds SA": ("SA", "Australia/Adelaide"),
}
DEFAULT_TZ = "Australia/Melbourne"

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
TIMES = ["9:00am", "12:00pm", "3:00pm"]  # matches the dashboard's fixed 3-slot/day grid
BUCKET_LABELS = ["morning", "midday", "afternoon"]

REASON_RULES = [
    ("no show", "No-show (not cancelled in advance)"),
    ("rebook", "Rescheduled"),
    ("dc cancel", "Cancelled by consultant"),
    ("customer", "Cancelled by customer"),
    ("purchased elsewhere", "Lost to competitor"),
    ("not sent quote", "Lost to competitor"),
]
FALLBACK_REASON = "Other / unspecified"

OFF_KEYWORDS = re.compile(r"\b(off|na|n/a|leave|ill|sick|holiday|hol|pub\s*holl|public\s*holl)\b", re.I)
CAPACITY_PATTERN = re.compile(r"(\d+)\s*@\s*(\d{1,2})(?::\d{2}|\.\d{2})?\s*(?:am|pm)?\s*-\s*(\d{1,2})(?::\d{2}|\.\d{2})?\s*(?:am|pm)?", re.I)


def bucket_for_hour(hour):
    if hour in (8, 9, 10):
        return "morning"
    if hour in (11, 12, 13):
        return "midday"
    return "afternoon"


def categorize_reason(text):
    t = (text or "").strip().lower()
    if not t:
        return "No-show (not cancelled in advance)"
    for keyword, label in REASON_RULES:
        if keyword in t:
            return label
    return FALLBACK_REASON


# ─────────────────────────────────────────────────────────────
# API CLIENT
# ─────────────────────────────────────────────────────────────
def make_session():
    s = requests.Session()
    s.auth = (EMAIL, API_KEY)
    s.headers.update({"Accept": "application/json"})
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
        r = session.get(f"{BASE_URL}{path}", params=params, timeout=90)
        r.raise_for_status()
        page = r.json().get("value", [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
    return rows


REP_EXPAND = "Representative($select=FirstName,LastName,DefaultBusinessUnitID;$expand=DefaultBusinessUnit($select=Name))"


def rep_info(row):
    rep = row.get("Representative") or {}
    name = f"{(rep.get('FirstName') or '').strip()} {(rep.get('LastName') or '').strip()}".strip()
    bu_name = ((rep.get("DefaultBusinessUnit") or {}).get("Name") or "")
    region, tz = BUSINESS_UNIT_REGION.get(bu_name, (None, None))
    return name, region, tz


def fetch_activities(session, activity_type, start, end):
    f = (
        f"ActivityType eq '{activity_type}' "
        f"and Start ge {start.strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"and Start lt {end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )
    select = "ID,Subject,Start,End,Status,Cancelled,CancelledReason,CreatedOn,RepresentativeID"
    return fetch_all(session, "/Activities", filter_str=f, select=select, expand=REP_EXPAND)


# ─────────────────────────────────────────────────────────────
# CLASSIFICATION
# ─────────────────────────────────────────────────────────────
def classify_appointment(row, now_utc):
    """held / noshow / cancelled / future (booked, not yet due)."""
    status = row.get("Status")
    if status == "activity_status_cancelled":
        return "cancelled"
    if status == "activity_status_closed":
        return "held"
    # activity_status_open
    end = parse_dt(row.get("End"))
    if end is not None and end < now_utc:
        return "noshow"
    return "future"


def parse_dt(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def local_date_and_bucket(dt_utc, tz_name):
    tz = ZoneInfo(tz_name or DEFAULT_TZ)
    local = dt_utc.astimezone(tz)
    return local.date(), bucket_for_hour(local.hour)


# ─────────────────────────────────────────────────────────────
# CAPACITY (Calendar Note) PARSING
# ─────────────────────────────────────────────────────────────
def parse_capacity_note(subject):
    """Returns dict{bucket: count} or None if the note carries no capacity signal,
    or {} for an explicit day-off (zero capacity, but known)."""
    text = (subject or "").strip()
    if not text:
        return None

    matches = CAPACITY_PATTERN.findall(text)
    if matches:
        counts = defaultdict(int)
        for count_str, start_hr, _end_hr in matches:
            counts[bucket_for_hour(int(start_hr) % 24)] += int(count_str)
        return dict(counts)

    if OFF_KEYWORDS.search(text):
        return {}

    return None  # unparseable note (area/product restriction, one-off comment, etc.)


def build_capacity_map(calendar_notes):
    """(rep_name, region, local_date) -> {morning: n, midday: n, afternoon: n} | None"""
    capacity = {}
    parsed = 0
    total = 0
    for row in calendar_notes:
        name, region, tz = rep_info(row)
        if not region:
            continue
        start = parse_dt(row.get("Start"))
        if start is None:
            continue
        local_date, _ = local_date_and_bucket(start, tz)
        total += 1
        parsed_note = parse_capacity_note(row.get("Subject"))
        if parsed_note is None:
            continue
        parsed += 1
        key = (name, region, local_date)
        existing = capacity.get(key)
        if existing is None:
            capacity[key] = {b: 0 for b in BUCKET_LABELS}
        for b, n in parsed_note.items():
            capacity[key][b] += n
    coverage = round(parsed / total, 3) if total else 0.0
    return capacity, coverage, total, parsed


# ─────────────────────────────────────────────────────────────
# WEEK / DATE HELPERS
# ─────────────────────────────────────────────────────────────
def week_bounds(any_date):
    """Return (Monday, following-Monday) as naive dates for the ISO week containing any_date."""
    monday = any_date - timedelta(days=any_date.weekday())
    return monday, monday + timedelta(days=7)


# ─────────────────────────────────────────────────────────────
# MAIN AGGREGATION
# ─────────────────────────────────────────────────────────────
def main():
    session = make_session()
    now_utc = datetime.now(timezone.utc)
    today_local = now_utc.astimezone(ZoneInfo(DEFAULT_TZ)).date()

    current_week_start, current_week_end = week_bounds(today_local)
    fetch_start_date = current_week_start - timedelta(weeks=TREND_WEEKS)
    fetch_start = datetime.combine(fetch_start_date, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=1)
    fetch_end = datetime.combine(current_week_end, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)

    print(f"Fetching Sales Appointments {fetch_start.date()} .. {fetch_end.date()} (UTC)...")
    appointments = fetch_activities(session, ACTIVITY_TYPE, fetch_start, fetch_end)
    print(f"  {len(appointments)} appointments")

    print("Fetching Calendar Note rosters over the same window...")
    calendar_notes = fetch_activities(session, "Calendar Note", fetch_start, fetch_end)
    print(f"  {len(calendar_notes)} calendar notes")

    capacity_map, coverage, cn_total, cn_parsed = build_capacity_map(calendar_notes)
    print(f"  capacity note parse coverage: {cn_parsed}/{cn_total} ({coverage:.0%})")

    # ---- classify + localize every appointment ----
    events = []
    for row in appointments:
        name, region, tz = rep_info(row)
        if not region or not name:
            continue
        start = parse_dt(row.get("Start"))
        if start is None:
            continue
        local_date, bucket = local_date_and_bucket(start, tz)
        created = parse_dt(row.get("CreatedOn"))
        wait_days = (start - created).total_seconds() / 86400.0 if created else None
        events.append({
            "name": name, "region": region,
            "local_date": local_date, "bucket": bucket,
            "status": classify_appointment(row, now_utc),
            "reason": row.get("CancelledReason"),
            "wait_days": wait_days,
        })

    # ---- per (name, region, local_date, bucket) roll-up of bookings ----
    bucket_status = {}  # (name, region, date, bucket) -> priority-resolved status
    STATUS_PRIORITY = {"noshow": 0, "cancelled": 1, "held": 2, "future": 3}
    for e in events:
        key = (e["name"], e["region"], e["local_date"], e["bucket"])
        cur = bucket_status.get(key)
        if cur is None or STATUS_PRIORITY[e["status"]] < STATUS_PRIORITY[cur]:
            bucket_status[key] = e["status"]

    def fill_metrics(name, region, start_date, end_date):
        """offered/filled/noshow/held/cancelled counts using known-capacity bucket-cells only."""
        offered = filled = noshow = held = cancelled = 0
        d = start_date
        while d < end_date:
            for b in BUCKET_LABELS:
                cap = capacity_map.get((name, region, d))
                if cap is None or cap.get(b, 0) <= 0:
                    d_has_cap = False
                else:
                    d_has_cap = True
                if not d_has_cap:
                    continue
                offered += 1
                st = bucket_status.get((name, region, d, b))
                if st in ("held", "future"):
                    filled += 1
                    held += 1
                elif st == "noshow":
                    filled += 1
                    noshow += 1
                elif st == "cancelled":
                    filled += 1
                    cancelled += 1
            d += timedelta(days=1)
        return offered, filled, held, noshow, cancelled

    def wait_avg(name, region, start_date, end_date):
        vals = [e["wait_days"] for e in events
                if e["name"] == name and e["region"] == region
                and start_date <= e["local_date"] < end_date
                and e["status"] in ("held", "noshow", "cancelled")
                and e["wait_days"] is not None]
        return sum(vals) / len(vals) if vals else None

    consultants_by_region = defaultdict(dict)  # region -> name -> stats
    for e in events:
        consultants_by_region[e["region"]].setdefault(e["name"], True)

    # ---- trailing-8-week window used for the consultant table ----
    table_start = current_week_start - timedelta(weeks=TREND_WEEKS)
    table_end = current_week_end

    region_output = defaultdict(list)
    for region, names in consultants_by_region.items():
        for name in names:
            offered, filled, held, noshow, cancelled = fill_metrics(name, region, table_start, table_end)
            if offered == 0:
                continue
            fill_pct = round(100 * filled / offered, 1)
            booked = held + noshow + cancelled
            noshow_pct = round(100 * noshow / booked, 1) if booked else 0.0
            wait = wait_avg(name, region, table_start, table_end)
            region_output[region].append({
                "name": name,
                "fill": fill_pct,
                "noShow": noshow_pct,
                "wait": round(wait, 1) if wait is not None else None,
                "offered": offered,
            })
        region_output[region].sort(key=lambda c: -c["fill"])

    # ---- diary for the current week ----
    diary = {}
    for region, names in consultants_by_region.items():
        for name in names:
            pattern = []
            for d_offset in range(5):
                d = current_week_start + timedelta(days=d_offset)
                for b in BUCKET_LABELS:
                    cap = capacity_map.get((name, region, d))
                    st = bucket_status.get((name, region, d, b))
                    if st in ("held", "future"):
                        pattern.append("filled")
                    elif st == "noshow":
                        pattern.append("noshow")
                    elif st == "cancelled":
                        pattern.append("cancelled")
                    else:
                        pattern.append("open")
            diary[name] = pattern

    # ---- 8-week trend (fill rate %, all regions combined) ----
    trend = []
    for i in range(TREND_WEEKS):
        w_start = current_week_start - timedelta(weeks=TREND_WEEKS - i)
        w_end = w_start + timedelta(days=7)
        offered_total = filled_total = 0
        for region, names in consultants_by_region.items():
            for name in names:
                o, f, _, _, _ = fill_metrics(name, region, w_start, w_end)
                offered_total += o
                filled_total += f
        trend.append(round(100 * filled_total / offered_total, 1) if offered_total else None)

    # ---- unfilled/cancellation reasons (share %) over the table window ----
    reason_counts = Counter()
    for e in events:
        if table_start <= e["local_date"] < table_end and e["status"] in ("cancelled", "noshow"):
            reason_counts[categorize_reason(e["reason"] if e["status"] == "cancelled" else None)] += 1
    reason_total = sum(reason_counts.values())
    reasons = {k: round(100 * v / reason_total, 1) for k, v in reason_counts.most_common()} if reason_total else {}

    # ---- headline KPIs: current calendar-MTD vs previous MTD (matches the dashboard's "vs last MTD" label) ----
    def mtd_bounds():
        cur_start = today_local.replace(day=1)
        cur_end = today_local + timedelta(days=1)
        elapsed = (cur_end - cur_start).days
        if cur_start.month == 1:
            prev_start = cur_start.replace(year=cur_start.year - 1, month=12)
        else:
            prev_start = cur_start.replace(month=cur_start.month - 1)
        prev_end = prev_start + timedelta(days=elapsed)
        return cur_start, cur_end, prev_start, prev_end

    cur_start, cur_end, prev_start, prev_end = mtd_bounds()

    def period_kpis(p_start, p_end):
        offered_total = filled_total = held_total = noshow_total = cancelled_total = 0
        for region, names in consultants_by_region.items():
            for name in names:
                o, f, h, ns, c = fill_metrics(name, region, p_start, p_end)
                offered_total += o
                filled_total += f
                held_total += h
                noshow_total += ns
                cancelled_total += c
        booked_total = held_total + noshow_total + cancelled_total
        fill_rate = round(100 * filled_total / offered_total, 1) if offered_total else None
        noshow_rate = round(100 * noshow_total / booked_total, 1) if booked_total else None
        waits = [e["wait_days"] for e in events
                 if p_start <= e["local_date"] < p_end
                 and e["status"] in ("held", "noshow", "cancelled") and e["wait_days"] is not None]
        avg_wait = round(sum(waits) / len(waits), 1) if waits else None
        return fill_rate, noshow_rate, avg_wait

    cur_fill, cur_noshow, cur_wait = period_kpis(cur_start, cur_end)
    prev_fill, prev_noshow, prev_wait = period_kpis(prev_start, prev_end)

    def delta(cur, prev):
        if cur is None or prev is None:
            return None
        return round(cur - prev, 1)

    kpis = {
        "fillRate": cur_fill, "fillRateDelta": delta(cur_fill, prev_fill),
        "noShow": cur_noshow, "noShowDelta": delta(cur_noshow, prev_noshow),
        "avgWait": cur_wait, "avgWaitDelta": delta(cur_wait, prev_wait),
        "onTime": None, "onTimeDelta": None,  # not available from Insyte — see module docstring
    }

    victory = {
        "kpis": kpis,
        "regions": {"All Regions": None, **{r: {"consultants": c} for r, c in region_output.items()}},
        "diary": diary,
        "trend": trend,
        "reasons": reasons,
    }

    output = {
        "generatedAt": now_utc.isoformat(),
        "currentWeekStart": current_week_start.isoformat(),
        "dataQuality": {
            "capacityNoteCoverage": coverage,
            "capacityNotesTotal": cn_total,
            "capacityNotesParsed": cn_parsed,
        },
        "victory": victory,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"Wrote {OUTPUT_FILE}")
    print(f"  regions: {list(region_output.keys())}")
    print(f"  consultants: {sum(len(v) for v in region_output.values())}")
    print(f"  KPIs: {kpis}")


if __name__ == "__main__":
    main()
