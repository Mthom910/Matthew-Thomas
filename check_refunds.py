"""Check for refunds/credits that might explain the $370K gap."""
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
        except Exception as e:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            else: raise

def fetch_all(path, label, max_pages=999):
    PAGE, rows, skip, pg = 500, [], 0, 1
    sep = "&" if "?" in path else "?"
    while pg <= max_pages:
        print(f"  {label} p{pg} ({len(rows)})...", flush=True)
        data = _get(f"{path}{sep}$top={PAGE}&$skip={skip}")
        page = data.get("value", data if isinstance(data, list) else [])
        rows.extend(page)
        if len(page) < PAGE: break
        skip += PAGE; pg += 1
    return rows

FROM, TO = "2026-01-01", "2026-06-26"
df = lambda f, t, field="OrderDate": f"{field} ge {f}T00:00:00Z and {field} le {t}T23:59:59Z"

# ── 1. Job lines with NEGATIVE DiscountedPriceExTax (credit lines) ──
print("=== 1. Checking for negative-price job lines (no date filter) ===")
try:
    neg_filter = urllib.parse.quote("DiscountedPriceExTax lt 0")
    neg_lines = fetch_all(f"/JobLines?$filter={neg_filter}", "neg lines", max_pages=10)
    total_neg = sum(l.get("DiscountedPriceExTax", 0) for l in neg_lines)
    print(f"  Negative-price lines: {len(neg_lines):,}  total: ${total_neg:,.2f}")
    if neg_lines:
        print(f"  Sample: {neg_lines[0]}")
except Exception as e:
    print(f"  Error: {e}")

# ── 2. Payments endpoint ──────────────────────────────────────────────
print("\n=== 2. Payments endpoint (2026 YTD) ===")
try:
    pf = urllib.parse.quote(df(FROM, TO, "PaymentDate"))
    payments = fetch_all(f"/Payments?$filter={pf}", "payments", max_pages=10)
    if payments:
        print(f"  Fields: {list(payments[0].keys())}")
        total_pay = sum(p.get("Amount", p.get("amount", 0)) or 0 for p in payments)
        neg_pay   = [p for p in payments if (p.get("Amount") or 0) < 0]
        print(f"  Total payments: {len(payments):,}  total amount: ${total_pay:,.2f}")
        print(f"  Negative payments (refunds): {len(neg_pay):,}  total: ${sum(p.get('Amount',0) for p in neg_pay):,.2f}")
    else:
        print("  No payments found or endpoint not available")
except Exception as e:
    print(f"  Error (endpoint may not exist): {e}")

# ── 3. Credits endpoint ───────────────────────────────────────────────
print("\n=== 3. Credits endpoint (2026 YTD) ===")
for ep in ["/Credits", "/CreditNotes", "/CreditNote", "/Refunds"]:
    try:
        data = _get(f"{ep}?$top=5")
        rows = data.get("value", data if isinstance(data, list) else [])
        print(f"  {ep}: OK — {len(rows)} rows, fields: {list(rows[0].keys()) if rows else 'empty'}")
    except Exception as e:
        print(f"  {ep}: {type(e).__name__} — {str(e)[:60]}")

# ── 4. Invoices with negative amounts ────────────────────────────────
print("\n=== 4. Invoices with negative amounts (credit invoices) ===")
try:
    inv_filter = urllib.parse.quote(f"InvoiceDate ge {FROM}T00:00:00Z and InvoiceDate le {TO}T23:59:59Z")
    invs = fetch_all(f"/Invoices?$filter={inv_filter}", "invoices", max_pages=10)
    if invs:
        print(f"  Fields: {[k for k in invs[0] if any(w in k.lower() for w in ['amount','total','price','tax','value'])]}")
        # Find the amount field
        amt_field = next((k for k in invs[0] if 'total' in k.lower() or 'amount' in k.lower()), None)
        if amt_field:
            neg_inv = [i for i in invs if (i.get(amt_field) or 0) < 0]
            total_inv = sum(i.get(amt_field, 0) or 0 for i in invs)
            print(f"  Total invoices: {len(invs):,}  total {amt_field}: ${total_inv:,.2f}")
            print(f"  Negative/credit invoices: {len(neg_inv):,}  total: ${sum(i.get(amt_field,0) for i in neg_inv):,.2f}")
            if neg_inv: print(f"  Sample: {neg_inv[0]}")
    else:
        print("  No invoices found")
except Exception as e:
    print(f"  Error: {e}")

# ── 5. JobLines with LineType = credit/refund ─────────────────────────
print("\n=== 5. Job line types in 2026 confirmed lines ===")
try:
    f_str = urllib.parse.quote(df(FROM, TO))
    lines = fetch_all(f"/JobLines?$filter={f_str}", "lines", max_pages=50)
    from collections import Counter
    types = Counter(l.get("LineType","?") for l in lines)
    statuses = Counter(l.get("Status","?") for l in lines)
    print(f"  LineType counts: {dict(types.most_common())}")
    print(f"  Status counts:   {dict(statuses.most_common())}")

    # Revenue by LineType
    print(f"\n  Revenue by LineType:")
    by_type = {}
    for l in lines:
        lt = l.get("LineType", "?")
        v  = l.get("DiscountedPriceExTax") or 0
        by_type.setdefault(lt, {"count": 0, "rev": 0})
        by_type[lt]["count"] += 1
        by_type[lt]["rev"]   += v
    for lt, d in sorted(by_type.items(), key=lambda x: -x[1]["rev"]):
        print(f"    {lt:<40} {d['count']:>6,} lines  ${d['rev']:>12,.2f}")
except Exception as e:
    print(f"  Error: {e}")
