import urllib.request, urllib.parse, json, base64

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path):
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

f = urllib.parse.quote("Start ge 2026-01-01T00:00:00Z and Start le 2026-01-31T23:59:59Z and ActivityType eq 'Sales Appointment' and Cancelled eq false")
sample = _get(f"/Activities?$filter={f}&$top=3")
acts = sample.get("value", [])

print("=== Activity fields ===")
if acts:
    print(json.dumps(acts[0], indent=2))

# Check what ContactID looks like and fetch a contact
for a in acts:
    cid = a.get("ContactID") or a.get("Contact") or a.get("CustomerID")
    print(f"\nContactID field: {cid}")
    break
