"""Check Job-level type fields to identify service jobs."""
import urllib.request, urllib.parse, json, base64
from collections import Counter

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path):
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def fetch_all(path, label, max_pages=99):
    PAGE, rows, skip, pg = 500, [], 0, 1
    sep = "&" if "?" in path else "?"
    while pg <= max_pages:
        print(f"  {label} p{pg} ({len(rows)})...", flush=True)
        data = _get(f"{path}{sep}$top={PAGE}&$skip={skip}")
        page = data.get("value", data if isinstance(data, list) else [])
        rows.extend(page)
        if len(page) < PAGE: break
        skip += PAGE; pg += 1
    return rows

# Sample job lines with OrderDate to see what LineType values appear
print("Sampling 2026 job lines...")
f = urllib.parse.quote("OrderDate ge 2026-01-01T00:00:00Z and OrderDate le 2026-06-27T23:59:59Z")
lines = _get(f"/JobLines?$filter={f}&$top=500")
rows = lines.get("value", [])

print(f"\nJob line fields: {list(rows[0].keys()) if rows else 'none'}")

print("\n=== LineType counts (sample 500) ===")
lt = Counter(r.get("LineType","null") for r in rows)
for t,n in sorted(lt.items(), key=lambda x:-x[1]):
    print(f"  {n:>5}  {t}")

print("\n=== Status counts (sample 500) ===")
st = Counter(r.get("Status","null") for r in rows)
for t,n in sorted(st.items(), key=lambda x:-x[1]):
    print(f"  {n:>5}  {t}")

# Now fetch full set and count
print("\nFetching all 2026 job lines...")
all_lines = fetch_all(f"/JobLines?$filter={f}", "lines")
print(f"\nTotal lines: {len(all_lines):,}")

print("\n=== Full LineType breakdown ===")
lt_full = Counter(r.get("LineType","null") for r in all_lines)
for t,n in sorted(lt_full.items(), key=lambda x:-x[1]):
    amt = sum(r.get("DiscountedPriceExTax") or r.get("StandardPriceExTax") or 0
              for r in all_lines if r.get("LineType")==t)
    print(f"  {n:>6,}  ${amt:>12,.0f}  {t}")

# Check Job-level Type field
print("\nSampling Jobs to check Type field...")
job_sample = _get("/Jobs?$top=20")
jobs = job_sample.get("value", [])
if jobs:
    print(f"Job fields: {list(jobs[0].keys())}")
    print("\n=== Sample jobs ===")
    for j in jobs[:5]:
        print(f"  ID={j.get('ID')}  Type={j.get('Type')}  JobType={j.get('JobType')}  Status={j.get('Status')}  Ref={j.get('Reference')}")

# Check unique Type values on jobs
print("\nFetching job type values (sample 500)...")
all_jobs = _get("/Jobs?$top=500")
job_rows = all_jobs.get("value", [])
job_types = Counter(j.get("Type","null") for j in job_rows)
print("Job Type values:")
for t,n in sorted(job_types.items(), key=lambda x:-x[1]):
    print(f"  {n:>5}  {t}")
job_status = Counter(j.get("Status","null") for j in job_rows)
print("Job Status values:")
for s,n in sorted(job_status.items(), key=lambda x:-x[1]):
    print(f"  {n:>5}  {s}")
