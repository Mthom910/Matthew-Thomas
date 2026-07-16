import urllib.request, urllib.parse, json, base64

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path):
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

# Try fetching a contact by filter
f = urllib.parse.quote("ID eq 76959")
r = _get(f"/Contacts?$filter={f}&$top=1")
print("Filter by ID:", json.dumps(r, indent=2))
