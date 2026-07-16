"""Explore Payments and Contacts endpoints to find DC commission data."""
import urllib.request, urllib.parse, json, base64, time

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path, retries=4):
    url = f"{BASE}/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            print(f"    HTTP {e.code}: {body}")
            raise
        except Exception as e:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            else: raise

def fetch_sample(path, label, top=5):
    try:
        sep = "&" if "?" in path else "?"
        data = _get(f"{path}{sep}$top={top}")
        rows = data.get("value", data if isinstance(data, list) else [])
        print(f"  {label}: {len(rows)} rows")
        if rows:
            print(f"    Fields: {list(rows[0].keys())}")
            print(f"    Sample: {json.dumps(rows[0], indent=6)[:600]}")
        return rows
    except Exception as e:
        print(f"  {label}: ERROR — {e}")
        return []

def fetch_all(path, label):
    PAGE, rows, skip, pg = 500, [], 0, 1
    sep = "&" if "?" in path else "?"
    while True:
        print(f"  {label} p{pg} ({len(rows)})...", flush=True)
        data = _get(f"{path}{sep}$top={PAGE}&$skip={skip}")
        page = data.get("value", data if isinstance(data, list) else [])
        rows.extend(page)
        if len(page) < PAGE: break
        skip += PAGE; pg += 1
    return rows

# ── 1. Payments endpoint — try without filter first ──────────────
print("=== 1. Payments (no filter) ===")
fetch_sample("/Payments", "payments")

# ── 2. Payments with date filter using different field names ──────
print("\n=== 2. Payments — try different date fields ===")
FROM, TO = "2026-01-01", "2026-06-26"
for field in ["Date", "PaymentDate", "CreatedOn", "TransactionDate", "PaidDate"]:
    try:
        f = urllib.parse.quote(f"{field} ge {FROM}T00:00:00Z and {field} le {TO}T23:59:59Z")
        data = _get(f"/Payments?$filter={f}&$top=3")
        rows = data.get("value", data if isinstance(data, list) else [])
        print(f"  {field}: OK — {len(rows)} rows")
        if rows: print(f"    Fields: {list(rows[0].keys())}")
        break
    except Exception as e:
        print(f"  {field}: {str(e)[:60]}")

# ── 3. Contacts endpoint ──────────────────────────────────────────
print("\n=== 3. Contacts (sample) ===")
fetch_sample("/Contacts", "contacts")

# ── 4. Find contacts with DC in name ─────────────────────────────
print("\n=== 4. Contacts with 'DC' in name ===")
try:
    # Try contains filter
    for filter_str in [
        "contains(tolower(Name), 'dc')",
        "contains(Name, 'DC')",
        "contains(tolower(FullName), 'dc')",
        "contains(tolower(FirstName), 'dc') or contains(tolower(LastName), 'dc')",
    ]:
        try:
            f = urllib.parse.quote(filter_str)
            data = _get(f"/Contacts?$filter={f}&$top=20")
            rows = data.get("value", data if isinstance(data, list) else [])
            print(f"  Filter '{filter_str}': {len(rows)} results")
            for r in rows[:5]:
                name = r.get("Name") or r.get("FullName") or f"{r.get('FirstName','')} {r.get('LastName','')}".strip()
                print(f"    ID={r.get('ID')}  Name={name}")
            break
        except Exception as e:
            print(f"  Filter '{filter_str}': {str(e)[:80]}")
except Exception as e:
    print(f"  Error: {e}")

# ── 5. All contacts — search for DC ──────────────────────────────
print("\n=== 5. All contacts — search for DC pattern ===")
try:
    contacts = fetch_all("/Contacts", "contacts")
    print(f"  Total contacts: {len(contacts):,}")
    if contacts:
        name_field = next((k for k in contacts[0] if 'name' in k.lower()), None)
        print(f"  Name field: {name_field}")
        dc_contacts = [c for c in contacts if 'dc' in str(c.get(name_field,'')).lower() or
                       'dc' in str(c.get('Name','')).lower() or
                       'dc' in str(c.get('FullName','')).lower() or
                       '(dc)' in str(c).lower()]
        print(f"  Contacts containing 'DC': {len(dc_contacts)}")
        for c in dc_contacts[:20]:
            print(f"    {c}")
except Exception as e:
    print(f"  Error: {e}")
