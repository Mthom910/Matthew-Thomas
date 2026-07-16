"""Quantify revenue impact of cancelled and non-sale line types."""
import urllib.request, urllib.parse, json, base64, time

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()
FROM, TO = "2026-01-01", "2026-06-26"

def _get(path, retries=4):
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
        rows.extend(page);
        if len(page) < PAGE: break
        skip += PAGE; pg += 1
    return rows

f = urllib.parse.quote(f"OrderDate ge {FROM}T00:00:00Z and OrderDate le {TO}T23:59:59Z")
print("Fetching 2026 confirmed lines...")
lines = fetch_all(f"/JobLines?$filter={f}", "lines")

def rev(l):
    d = l.get("DiscountedPriceExTax")
    return d if d is not None else (l.get("StandardPriceExTax") or 0)

total_all = sum(rev(l) for l in lines)

# Break down by status and line type
from collections import defaultdict
by_status = defaultdict(lambda: {"count": 0, "rev": 0.0})
by_type   = defaultdict(lambda: {"count": 0, "rev": 0.0})
for l in lines:
    s, t, r = l.get("Status","?"), l.get("LineType","?"), rev(l)
    by_status[s]["count"] += 1; by_status[s]["rev"] += r
    by_type[t]["count"]   += 1; by_type[t]["rev"]   += r

print(f"\nTotal lines: {len(lines):,}  |  Total revenue (null-safe): ${total_all:,.2f}")

print(f"\nRevenue by Status:")
for s, d in sorted(by_status.items(), key=lambda x: -x[1]["rev"]):
    print(f"  {s:<40} {d['count']:>6,} lines  ${d['rev']:>12,.2f}")

print(f"\nRevenue by LineType:")
for t, d in sorted(by_type.items(), key=lambda x: -x[1]["rev"]):
    print(f"  {t:<40} {d['count']:>6,} lines  ${d['rev']:>12,.2f}")

# What if we exclude cancelled + remake + service?
excl_status = {"status_job_line_cancelled"}
excl_type   = {"type_job_line_remake", "type_job_line_service"}

sale_lines = [l for l in lines
              if l.get("Status") not in excl_status
              and l.get("LineType") not in excl_type]

rev_sales = sum(rev(l) for l in sale_lines)
print(f"\n--- Exclusion scenarios ---")
print(f"All lines:                              ${total_all:>12,.2f}")
print(f"Excl. cancelled:                        ${sum(rev(l) for l in lines if l.get('Status') not in excl_status):>12,.2f}")
print(f"Excl. cancelled + remake + service:     ${rev_sales:>12,.2f}")
print(f"Excl. cancelled + remake only:          ${sum(rev(l) for l in lines if l.get('Status') not in excl_status and l.get('LineType') != 'type_job_line_remake'):>12,.2f}")
print(f"\nUser's known total:                     $10,690,000.00")
print(f"Closest match gap:                      ${rev_sales - 10690000:>+12,.2f}")
