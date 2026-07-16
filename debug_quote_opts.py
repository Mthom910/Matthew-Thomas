import urllib.request, urllib.parse, json, base64, re
from collections import Counter, defaultdict

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path):
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

# Print ALL fields from one roller blind quote line
qlf = urllib.parse.quote("Stage eq 'stage_job_line_unconfirmed'")
ldata = _get(f"/JobLines?$filter={qlf}&$top=500")
all_q_lines = ldata.get("value", [])
roller_lines = [l for l in all_q_lines if "roller" in (l.get("Product") or "").lower()]
print(f"Roller blind unconfirmed lines: {len(roller_lines)}")

if roller_lines:
    print("\nALL fields on a roller blind quote line:")
    l = roller_lines[0]
    for k, v in sorted(l.items()):
        if v not in (None, "", 0, False):
            print(f"  {k!r}: {str(v)[:80]!r}")

# Check the Job record itself for installation fields
jf = urllib.parse.quote("JobDate ge 2026-01-01T00:00:00Z and Stage eq 'stage_job_quote'")
jdata = _get(f"/Jobs?$filter={jf}&$top=3")
jobs = jdata.get("value", [])
print("\nALL non-empty fields on a quote job:")
if jobs:
    j = jobs[0]
    for k, v in sorted(j.items()):
        if v not in (None, "", 0, False):
            print(f"  {k!r}: {str(v)[:80]!r}")

# Check if there are other endpoints like Measurements, Installations
print("\nChecking for /JobInstallations endpoint...")
try:
    d = _get("/JobInstallations?$top=1")
    print(f"  EXISTS: {d}")
except Exception as e:
    print(f"  Not found: {e}")

print("\nChecking for /JobMeasurements endpoint...")
try:
    d = _get("/JobMeasurements?$top=1")
    print(f"  EXISTS: {d}")
except Exception as e:
    print(f"  Not found: {e}")

print("\nDone.")
