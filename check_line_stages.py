import urllib.request, urllib.parse, json, base64
from collections import Counter

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path):
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

f1 = urllib.parse.quote("OrderDate ge 2026-01-01T00:00:00Z and OrderDate le 2026-01-31T23:59:59Z")
sample = _get(f"/JobLines?$filter={f1}&$top=5")
lines = sample.get("value", [])

print("=== All fields on a job line ===")
if lines:
    print(json.dumps(lines[0], indent=2))

f2 = urllib.parse.quote("OrderDate ge 2026-01-01T00:00:00Z and OrderDate le 2026-03-31T23:59:59Z")
sample2 = _get(f"/JobLines?$filter={f2}&$top=500")
lines2 = sample2.get("value", [])

stage_counts = Counter(l.get("Stage") for l in lines2)
status_counts = Counter(l.get("Status") for l in lines2)
print(f"\n=== Stage values (from {len(lines2)} lines) ===")
for k, v in stage_counts.most_common():
    print(f"  {k!r}: {v}")

print(f"\n=== Status values ===")
for k, v in status_counts.most_common():
    print(f"  {k!r}: {v}")
