"""Print all fields on a sample of JobLines to identify price fields."""
import urllib.request, json, base64

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

FROM, TO = "2026-01-01", "2026-06-26"
f = f"OrderDate ge {FROM}T00:00:00Z and OrderDate le {TO}T23:59:59Z"

req = urllib.request.Request(
    f"{BASE}/JobLines?$filter={urllib.parse.quote(f)}&$top=5",
    headers={"Authorization": AUTH, "Accept": "application/json"}
)
import urllib.parse
data = json.loads(urllib.request.urlopen(req, timeout=30).read())
rows = data.get("value", data if isinstance(data, list) else [])

if not rows:
    print("No rows returned")
else:
    sample = rows[0]
    # All keys
    print("=== ALL FIELDS ON A JOBLINE ===")
    for k, v in sorted(sample.items()):
        print(f"  {k:<45} = {v}")

    # Just price/cost/tax fields
    print("\n=== PRICE / COST / TAX FIELDS ===")
    keywords = ["price","cost","tax","gst","value","amount","sale","disc","std","total","margin","gp","profit"]
    for k, v in sorted(sample.items()):
        if any(kw in k.lower() for kw in keywords):
            print(f"  {k:<45} = {v}")

    # Show same fields across all 5 samples
    price_keys = [k for k in sample if any(kw in k.lower() for kw in keywords)]
    print(f"\n=== PRICE FIELDS ACROSS {len(rows)} SAMPLE LINES ===")
    print(f"  {'Field':<45}", end="")
    for i in range(len(rows)): print(f"  Line {i+1:>6}", end="")
    print()
    for k in sorted(price_keys):
        print(f"  {k:<45}", end="")
        for r in rows:
            v = r.get(k)
            print(f"  {str(v)[:8]:>8}", end="")
        print()
