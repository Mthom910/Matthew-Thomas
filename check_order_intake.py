"""Quick verify: total order intake for all confirmed jobs, Jan-Jun 2026."""
import urllib.request, urllib.parse, json, base64, time

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

FROM, TO = "2026-01-01", "2026-06-26"

def _get(path, retries=5):
    url = f"{BASE}/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            else: raise

def fetch_all(path, label):
    PAGE, rows, skip, pg = 500, [], 0, 1
    sep = "&" if "?" in path else "?"
    while True:
        print(f"  {label} p{pg} ({len(rows)} rows)...", flush=True)
        data = _get(f"{path}{sep}$top={PAGE}&$skip={skip}")
        page = data.get("value", data if isinstance(data, list) else [])
        rows.extend(page)
        if len(page) < PAGE: break
        skip += PAGE; pg += 1
    return rows

# ── Fetch job lines ────────────────────────────────────────
f = urllib.parse.quote(f"OrderDate ge {FROM}T00:00:00Z and OrderDate le {TO}T23:59:59Z")
print("Fetching 2026 confirmed job lines...")
lines = fetch_all(f"/JobLines?$filter={f}", "lines")
print(f"\nTotal lines fetched: {len(lines):,}")

# ── Diagnose field values ──────────────────────────────────
has_disc     = sum(1 for l in lines if l.get("DiscountedPriceExTax") is not None)
disc_zero    = sum(1 for l in lines if l.get("DiscountedPriceExTax") == 0)
disc_null    = sum(1 for l in lines if l.get("DiscountedPriceExTax") is None)
disc_pos     = sum(1 for l in lines if (l.get("DiscountedPriceExTax") or 0) > 0)

print(f"\nDiscountedPriceExTax breakdown:")
print(f"  > 0  (normal sale): {disc_pos:,}")
print(f"  = 0  (zero/100% disc): {disc_zero:,}")
print(f"  null/missing: {disc_null:,}")
print(f"  has value: {has_disc:,}")

# ── Revenue calc — TWO methods ─────────────────────────────
# Method A: current code (|| fallback — treats 0 as missing)
rev_A = sum(
    (l.get("DiscountedPriceExTax") or l.get("StandardPriceExTax") or 0)
    for l in lines
)

# Method B: correct (null-safe — 0 stays 0)
def safe_disc(l):
    d = l.get("DiscountedPriceExTax")
    return d if d is not None else (l.get("StandardPriceExTax") or 0)

rev_B = sum(safe_disc(l) for l in lines)

print(f"\nTotal revenue comparison (line-level, before job dedup):")
print(f"  Method A (|| fallback, current): ${rev_A:,.0f}")
print(f"  Method B (null-safe, corrected):  ${rev_B:,.0f}")
print(f"  Difference: ${rev_A - rev_B:,.0f}")

# ── Job-level aggregation (method B) ──────────────────────
import re
def base_ref(r): return re.sub(r"-\d+$", "", str(r or ""))

by_job = {}
for l in lines:
    jid = l.get("JobID")
    key = str(jid) if jid else f"__nojob_{l.get('ID','?')}"
    if key not in by_job:
        by_job[key] = 0
    by_job[key] += safe_disc(l)

job_totals = list(by_job.values())
print(f"\nJob-level (by JobID, method B):")
print(f"  Unique jobs:      {len(job_totals):,}")
print(f"  Total revenue:    ${sum(job_totals):,.0f}")
print(f"  Jobs >= $5K:      {sum(1 for v in job_totals if v >= 5000):,}  rev: ${sum(v for v in job_totals if v >= 5000):,.0f}")
print(f"  Jobs < $5K:       {sum(1 for v in job_totals if v < 5000):,}  rev: ${sum(v for v in job_totals if v < 5000):,.0f}")
print(f"  Jobs = $0:        {sum(1 for v in job_totals if v == 0):,}")

# ── Breakdown by segment ───────────────────────────────────
segs = [
    ("<$1K",    0,      1000),
    ("$1K-$2K", 1000,   2000),
    ("$2K-$3K", 2000,   3000),
    ("$3K-$5K", 3000,   5000),
    ("$5K-$10K",5000,  10000),
    ("$10K+",  10000, 9e99),
]
print(f"\nSegment breakdown (by JobID, method B):")
print(f"  {'Segment':<12} {'Jobs':>6}  {'Revenue':>14}  {'AOV':>10}")
print(f"  {'-'*50}")
for lbl, mn, mx in segs:
    grp = [v for v in job_totals if mn <= v < mx]
    if grp:
        avg = sum(grp)/len(grp)
        print(f"  {lbl:<12} {len(grp):>6,}  ${sum(grp):>13,.0f}  ${avg:>9,.0f}")
total_all = sum(job_totals)
print(f"  {'TOTAL':<12} {len(job_totals):>6,}  ${total_all:>13,.0f}  ${total_all/len(job_totals) if job_totals else 0:>9,.0f}")
