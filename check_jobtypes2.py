import urllib.request, json, base64
from collections import Counter

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path):
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

rows = []
skip = 0
while len(rows) < 3000:
    data = _get(f"/Jobs?$top=500&$skip={skip}")
    page = data.get("value", [])
    rows.extend(page)
    if len(page) < 500: break
    skip += 500

print(f"Sampled {len(rows):,} jobs")
jt = Counter(j.get("JobType", "null") for j in rows)
print("JobType values:")
for t, n in sorted(jt.items(), key=lambda x: -x[1]):
    print(f"  {n:>5}  {t}")
