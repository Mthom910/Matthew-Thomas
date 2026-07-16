"""Sample Activities to find the correct type for DC sales appointments."""
import urllib.request, urllib.parse, json, base64, time
from collections import Counter

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path):
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def fetch_all(path, label, max_pages=20):
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

# Fetch a broad sample of 2026 activities
print("Fetching 2026 activities (Jan-Jun)...")
f = urllib.parse.quote("Start ge 2026-01-01T00:00:00Z and Start le 2026-06-27T23:59:59Z")
acts = fetch_all(f"/Activities?$filter={f}", "acts", max_pages=40)
print(f"\nTotal 2026 activities fetched: {len(acts):,}")

# Show all unique Type values with counts
print("\n=== Activity Types ===")
type_counts = Counter(a.get("Type", "None/null") for a in acts)
for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {n:>6,}  {t}")

# Show all field names from first record
if acts:
    print(f"\n=== Fields on Activity record ===")
    print(list(acts[0].keys()))
    print(f"\n=== Sample record ===")
    print(json.dumps(acts[0], indent=2)[:800])

# Show sample of each type
print("\n=== Sample Subject/Description per Type ===")
by_type = {}
for a in acts:
    t = a.get("Type","None")
    if t not in by_type: by_type[t] = []
    if len(by_type[t]) < 3: by_type[t].append(a)

for t, samples in sorted(by_type.items()):
    print(f"\n  Type: {t}")
    for s in samples:
        subj = (s.get("Subject") or s.get("Title") or s.get("Description") or "")[:80]
        start = (s.get("Start") or "")[:16]
        print(f"    {start}  {subj}")
