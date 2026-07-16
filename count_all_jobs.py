import urllib.request, urllib.parse, json, base64, time, re
from collections import Counter

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

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
        print(f"  {label} p{pg} ({len(rows)})...", flush=True)
        data = _get(f"{path}{sep}$top={PAGE}&$skip={skip}")
        page = data.get("value", data if isinstance(data, list) else [])
        rows.extend(page)
        if len(page) < PAGE: break
        skip += PAGE; pg += 1
    return rows

def base_ref(r):
    return re.sub(r'-\d+$', '', str(r or ''))

def df(field, frm, to):
    return urllib.parse.quote(f"{field} ge {frm}T00:00:00Z and {field} le {to}T23:59:59Z")

# Fetch all jobs by JobDate (creation date)
print("Fetching 2026 YTD jobs...")
jobs26 = fetch_all(f"/Jobs?$filter={df('JobDate','2026-01-01','2026-06-29')}", "2026 jobs")
print(f"  Raw job records: {len(jobs26)}")

print("Fetching 2025 equivalent jobs (Jan-Jun)...")
jobs25 = fetch_all(f"/Jobs?$filter={df('JobDate','2025-01-01','2025-06-29')}", "2025 jobs")
print(f"  Raw job records: {len(jobs25)}")

def analyse(jobs, label):
    # Each record is already a job (sub-job like J0001234-1)
    # Deduplicate by base reference
    base_refs = set()
    stage_counts = Counter()
    type_counts = Counter()
    by_base = {}

    for j in jobs:
        ref = j.get("Reference", "")
        br = base_ref(ref)
        base_refs.add(br)
        stage_counts[j.get("Stage", "unknown")] += 1
        type_counts[j.get("JobType", "unknown")] += 1
        if br not in by_base:
            by_base[br] = j.get("Stage")

    # Count unique orders by their stage (use first sub-job's stage as representative)
    order_stage_counts = Counter(by_base.values())

    print(f"\n=== {label} ===")
    print(f"Total sub-job records: {len(jobs)}")
    print(f"Unique base references (orders/quotes): {len(base_refs)}")
    print(f"\nSub-job stage breakdown:")
    for k, v in stage_counts.most_common():
        print(f"  {k}: {v}")
    print(f"\nUnique orders by stage (first sub-job):")
    for k, v in order_stage_counts.most_common():
        print(f"  {k}: {v}")
    print(f"\nJob type breakdown (sub-jobs):")
    for k, v in type_counts.most_common():
        print(f"  {k}: {v}")
    return len(base_refs), order_stage_counts

total26, stages26 = analyse(jobs26, "2026 YTD (Jan-Jun 29)")
total25, stages25 = analyse(jobs25, "2025 YTD (Jan-Jun 29)")

print(f"\n=== SUMMARY ===")
print(f"2026 YTD unique job references: {total26:,}")
print(f"2025 YTD unique job references: {total25:,}")
print(f"YoY change: {total26-total25:+,} ({(total26/total25-1)*100:+.1f}%)")
