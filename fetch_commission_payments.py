"""Find DC commission payments — search by email domain, payment type, and notes."""
import urllib.request, urllib.parse, json, base64, time
from collections import defaultdict

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()
Y1FROM, Y1TO = "2026-01-01", "2026-06-26"
Y2FROM, Y2TO = "2025-01-01", "2025-06-26"

def _get(path, retries=5):
    url = f"{BASE}/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            else: raise

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

def full_name(c):
    return f"{c.get('FirstName','') or ''} {c.get('LastName','') or ''}".strip()

df_filter = lambda f, t: f"Date ge {f}T00:00:00Z and Date le {t}T23:59:59Z"

# ── 1. Load payments ──────────────────────────────────────
print("Loading 2026 payments...")
p26 = fetch_all(f"/Payments?$filter={urllib.parse.quote(df_filter(Y1FROM,Y1TO))}", "2026")
print("Loading 2025 payments...")
p25 = fetch_all(f"/Payments?$filter={urllib.parse.quote(df_filter(Y2FROM,Y2TO))}", "2025")

print(f"\n2026: {len(p26):,} payments  total=${sum(p.get('Amount',0) or 0 for p in p26):,.2f}")
print(f"2025: {len(p25):,} payments  total=${sum(p.get('Amount',0) or 0 for p in p25):,.2f}")

# ── 2. Payment type breakdown ────────────────────────────
print("\n=== Payment Types (2026) ===")
by_type = defaultdict(lambda: {"count": 0, "total": 0.0, "neg": 0, "neg_total": 0.0})
for p in p26:
    t = p.get("Type", "?")
    amt = p.get("Amount", 0) or 0
    by_type[t]["count"] += 1
    by_type[t]["total"] += amt
    if amt < 0:
        by_type[t]["neg"] += 1
        by_type[t]["neg_total"] += amt
for t, d in sorted(by_type.items(), key=lambda x: -x[1]["total"]):
    print(f"  {t:<35}  {d['count']:>6,} payments  ${d['total']:>12,.2f}  ({d['neg']} neg  ${d['neg_total']:,.2f})")

print("\n=== Payment Status (2026) ===")
by_status = defaultdict(lambda: {"count":0,"total":0.0})
for p in p26:
    s = p.get("Status","?"); amt = p.get("Amount",0) or 0
    by_status[s]["count"] += 1; by_status[s]["total"] += amt
for s, d in sorted(by_status.items(), key=lambda x: -x[1]["total"]):
    print(f"  {s:<35}  {d['count']:>6,}  ${d['total']:>12,.2f}")

# ── 3. Sample notes/receipts to spot commission patterns ─
print("\n=== Sample payment Notes (2026, first 20 with notes) ===")
noted = [(p.get("Notes","") or "").strip() for p in p26 if (p.get("Notes") or "").strip()][:20]
for n in noted:
    print(f"  {n[:100]}")

# ── 4. Payments with 'commission' or 'dc' in notes ───────
comm_payments = [p for p in p26 + p25
                 if any(kw in (p.get("Notes") or "").lower()
                        for kw in ["commis", " dc ", "(dc)", "consult"])]
print(f"\n=== Payments with commission/DC in notes: {len(comm_payments)} ===")
for p in comm_payments[:20]:
    print(f"  {p.get('Date','')[:10]}  ${p.get('Amount',0):>10,.2f}  ContactID={p.get('ContactID')}  Notes={p.get('Notes','')[:80]}")

# ── 5. Fetch contacts, search by victoryblinds / DC emails ─
print("\nFetching contacts for all payment ContactIDs...")
all_cids = list({p["ContactID"] for p in p26 + p25 if p.get("ContactID")})
CHUNK, contact_map = 15, {}
for i in range(0, len(all_cids), CHUNK):
    chunk = all_cids[i:i + CHUNK]
    fstr = " or ".join(f"ID eq {c}" for c in chunk)
    try:
        data = _get(f"/Contacts?$filter={urllib.parse.quote(fstr)}&$top={CHUNK * 2}")
        for c in data.get("value", []):
            contact_map[c["ID"]] = c
    except Exception: pass
    if i % 1500 == 0:
        print(f"  {len(contact_map):,}/{len(all_cids):,}...", flush=True)
print(f"  Loaded {len(contact_map):,} contacts")

# Known DC consultant names from Users endpoint
KNOWN_DC_NAMES = {
    "maria rundle", "cameron walsh", "michelle kelcey", "joshua correa",
    "ken morris", "sean turner", "sahel azadi", "jim panagiotou",
}
DC_KEYWORDS = ["(dc)", " dc ", "dc mentor", "vcb dc", "victoryblinds",
               "victory blinds", "design consultant"]

dc_contacts = {}
for cid, c in contact_map.items():
    name = full_name(c).lower()
    email = (c.get("Email") or "").lower()
    title = (c.get("JobTitle") or "").lower()
    notes = (c.get("Notes") or "").lower()
    if (any(kw in name for kw in DC_KEYWORDS) or
        any(kw in email for kw in ["victoryblinds", "victory blinds"]) or
        any(kw in title for kw in DC_KEYWORDS + ["consultant"]) or
        any(n in name for n in KNOWN_DC_NAMES)):
        dc_contacts[cid] = c

print(f"\nDC contacts identified: {len(dc_contacts)}")
for cid, c in sorted(dc_contacts.items(), key=lambda x: full_name(x[1])):
    print(f"  ID={cid:>6}  {full_name(c):<35}  email={c.get('Email','')}  title={c.get('JobTitle','')}")

# ── 6. If still none, show top 30 contacts by volume ─────
if not dc_contacts:
    print("\nStill no DC contacts found. Top 30 contacts by 2026 payment volume:")
    by_cid = defaultdict(float)
    for p in p26:
        cid = p.get("ContactID")
        if cid: by_cid[cid] += (p.get("Amount") or 0)
    print(f"  {'ID':>6}  {'Name':<40}  {'Email':<35}  {'JobTitle':<25}  Total")
    for cid, total in sorted(by_cid.items(), key=lambda x: -x[1])[:30]:
        c = contact_map.get(cid) or {}
        n = full_name(c) or f"Contact {cid}"
        e = (c.get("Email") or "")[:34]
        t = (c.get("JobTitle") or "")[:24]
        print(f"  {cid:>6}  {n:<40}  {e:<35}  {t:<25}  ${total:>10,.2f}")

# ── 7. DC payment analysis if contacts found ─────────────
if dc_contacts:
    dc_ids = set(dc_contacts.keys())
    for payments, yr in [(p26, "2026"), (p25, "2025")]:
        dc_pay = [p for p in payments if p.get("ContactID") in dc_ids]
        if not dc_pay:
            print(f"\n{yr}: No payments found for DC contacts")
            continue
        total = sum(p.get("Amount",0) or 0 for p in dc_pay)
        print(f"\n=== {yr} DC Commission Payments ===")
        print(f"  Count: {len(dc_pay):,}   Total: ${total:,.2f}")

        by_dc = defaultdict(lambda: {"count":0,"total":0.0,"months":set()})
        for p in dc_pay:
            cid = p.get("ContactID")
            nm = full_name(dc_contacts[cid])
            by_dc[nm]["count"] += 1
            by_dc[nm]["total"] += p.get("Amount",0) or 0
            by_dc[nm]["months"].add((p.get("Date") or "")[:7])

        print(f"  {'Consultant':<35}  {'Pmts':>5}  {'Total':>12}  {'Avg/pmt':>10}  Months active")
        for nm, d in sorted(by_dc.items(), key=lambda x: -x[1]["total"]):
            avg = d["total"] / d["count"] if d["count"] else 0
            print(f"  {nm:<35}  {d['count']:>5}  ${d['total']:>11,.2f}  ${avg:>9,.2f}  {', '.join(sorted(d['months']))}")

        monthly = defaultdict(float)
        for p in dc_pay:
            mo = (p.get("Date") or "")[:7]
            if mo: monthly[mo] += p.get("Amount",0) or 0
        print(f"  Monthly: {dict(sorted(monthly.items()))}")

# ── 8. Save ───────────────────────────────────────────────
out = {
    "payment_types_2026": {t: d for t, d in by_type.items()},
    "dc_contacts": {str(k): {"id": k, "name": full_name(v), "email": v.get("Email",""), "title": v.get("JobTitle","")} for k, v in dc_contacts.items()},
    "dc_payments_2026": [
        {"date": p["Date"][:10], "amount": p["Amount"], "contact_id": p["ContactID"],
         "status": p["Status"], "type": p["Type"], "notes": p.get("Notes",""), "receipt": p.get("ReceiptNumber","")}
        for p in p26 if p.get("ContactID") in dc_contacts
    ],
    "dc_payments_2025": [
        {"date": p["Date"][:10], "amount": p["Amount"], "contact_id": p["ContactID"],
         "status": p["Status"], "type": p["Type"], "notes": p.get("Notes",""), "receipt": p.get("ReceiptNumber","")}
        for p in p25 if p.get("ContactID") in dc_contacts
    ],
}
with open("commission_payments.json", "w") as f:
    json.dump(out, f, indent=2)
print("\nSaved commission_payments.json")
