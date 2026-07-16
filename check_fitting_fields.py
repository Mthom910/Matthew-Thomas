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
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            else: raise

f = urllib.parse.quote("OrderDate ge 2026-01-01T00:00:00Z and OrderDate le 2026-03-31T23:59:59Z")
data = _get(f"/JobLines?$filter={f}&$top=500")
lines = data.get("value", [])
print(f"Sample: {len(lines)} lines\n")

# Check all DisplayOption fields for fitting/brick references
opt_keys = [f"DisplayOption{i}" for i in range(1, 11)]

print("=== DisplayOption value samples (non-null) ===")
for key in opt_keys:
    vals = [l[key] for l in lines if l.get(key)]
    if vals:
        sample_vals = list(set(vals))[:8]
        print(f"\n{key} ({len(vals)} non-null):")
        for v in sample_vals:
            print(f"  {v!r}")

# Search specifically for brick/fitting type values
print("\n\n=== Lines mentioning 'brick' (case-insensitive) ===")
brick_count = 0
for l in lines:
    for key in opt_keys:
        val = (l.get(key) or "").lower()
        if "brick" in val:
            brick_count += 1
            print(f"  {key}: {l.get(key)!r}  (Product: {l.get('Product')})")
            break
print(f"Total brick lines in sample: {brick_count}")

# Check product field for takedowns
print("\n\n=== Product values mentioning 'take' or 'down' ===")
takedown_products = Counter()
for l in lines:
    prod = (l.get("Product") or "").lower()
    if "take" in prod or "takedown" in prod or "take down" in prod:
        takedown_products[l.get("Product")] += 1
print(dict(takedown_products))

# Show all unique product names in sample
print("\n\n=== All unique Product values in sample ===")
all_prods = Counter(l.get("Product") for l in lines if l.get("Product"))
for p, c in all_prods.most_common(30):
    print(f"  {p}: {c}")
