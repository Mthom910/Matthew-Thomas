import urllib.request, urllib.parse, json, base64, time
from collections import Counter

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path, retries=3):
    url = f"{BASE}/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            else: raise

# 1. Check all fields on a Job record
f = urllib.parse.quote("JobDate ge 2026-01-01T00:00:00Z and Stage eq 'stage_job_order'")
sample = _get(f"/Jobs?$filter={f}&$top=3")
jobs = sample.get("value", [])
print("=== All fields on a Job record ===")
if jobs:
    print(json.dumps(jobs[0], indent=2))

# 2. Fetch a larger sample of job lines and look at ALL text fields for brick terms
f2 = urllib.parse.quote("OrderDate ge 2026-01-01T00:00:00Z and OrderDate le 2026-06-29T23:59:59Z")
sample2 = _get(f"/JobLines?$filter={f2}&$top=500&$skip=5000")
lines = sample2.get("value", [])

SEARCH_TERMS = ["brick", "masonry", "cavity", "veneer", "fixing", "mount type", "wall type"]
ALL_TEXT_KEYS = [f"DisplayOption{i}" for i in range(1, 11)] + ["Notes", "SupplyNotes", "InstallationNotes", "Location"]

print("\n=== Searching lines (sample 500) for brick/masonry/cavity terms ===")
hits = {}
for term in SEARCH_TERMS:
    count = 0
    examples = []
    for l in lines:
        for key in ALL_TEXT_KEYS:
            val = (l.get(key) or "").lower()
            if term in val:
                count += 1
                if len(examples) < 3:
                    examples.append(f"{key}: {l.get(key)!r}")
                break
    if count > 0:
        hits[term] = (count, examples)

for term, (cnt, examples) in hits.items():
    print(f"\n'{term}': {cnt} lines")
    for ex in examples:
        print(f"  {ex}")

if not hits:
    print("No matches found for any brick/masonry/fitting terms in this sample")
    print("\nAll unique Location values (sample):")
    locs = Counter(l.get("Location") for l in lines if l.get("Location"))
    for loc, cnt in locs.most_common(10):
        print(f"  {cnt}  {loc!r}")

# 3. Check Application values across all DisplayOptions for fitting types
print("\n=== Application values found in DisplayOptions ===")
app_vals = Counter()
for l in lines:
    for key in [f"DisplayOption{i}" for i in range(1, 11)]:
        val = l.get(key) or ""
        if val.lower().startswith("application:") or "fixing" in val.lower() or "mount" in val.lower():
            app_vals[val.strip()] += 1
for v, c in app_vals.most_common(20):
    print(f"  {c:3d}  {v!r}")
