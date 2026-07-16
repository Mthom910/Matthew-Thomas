import urllib.request, json, base64, re, urllib.parse

from insyte_env import EMAIL, KEY
BASE  = 'https://api.myinsyte.com.au/v2'
AUTH  = 'Basic ' + base64.b64encode(f'{EMAIL}:{KEY}'.encode()).decode()

def get(path):
    req = urllib.request.Request(BASE+path, headers={'Authorization':AUTH,'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

data = get('/Jobs?$top=100&$select=ID,Reference,JobType')
jobs = data.get('value', [])

print(f"Fetched {len(jobs)} jobs")
print("\nSample references:")
for j in jobs[:40]:
    ref = j.get('Reference') or ''
    base1 = re.sub(r'-\d+$', '', ref)
    base2 = re.sub(r'(-\d+)+$', '', ref)
    match = '*' if base1 != ref else ''
    print(f"  {match} {ref!r:30s}  base1={base1!r:25s}  base2={base2!r}")

refs = [j.get('Reference') or '' for j in jobs]
print(f"\nTotal: {len(refs)}, Unique refs: {len(set(refs))}")
print(f"Unique base1 (-\\d+$):       {len(set(re.sub(r'-\d+$','',r) for r in refs))}")
print(f"Unique base2 ((-\\d+)+$):    {len(set(re.sub(r'(-\d+)+$','',r) for r in refs))}")
