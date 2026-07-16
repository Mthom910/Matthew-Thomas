"""Export raw $5K+ orders for H1 2026 to CSV for manual verification."""
import urllib.request, urllib.parse, json, base64, csv, re, time
from collections import defaultdict

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

Y1FROM, Y1TO = "2026-01-01", "2026-06-30"

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

def base_ref(r):
    return re.sub(r'-\d+$', '', str(r or ''))

EXCL_LINE_STAT = {"status_job_line_cancelled"}
EXCL_LINE_TYPE = {"type_job_line_remake", "type_job_line_service", "type_job_line_alter"}
EXCL_JOB_TYPE  = {"type_job_service"}

def safe_disc(l):
    v = l.get("DiscountedPriceExTax")
    return v if v is not None else (l.get("StandardPriceExTax") or 0)

def safe_cost(l):
    c = l.get("DiscountedCostExTax")
    if c is None: c = l.get("StandardCostExTax") or 0
    return c + (l.get("StandardIntallCostExTax") or 0) + (l.get("StandardDeliveryCostExTax") or 0)

# Load users
print("Loading users...")
users = fetch_all("/Users", "users")
user_map = {u["ID"]: (u.get("FullName") or f"{u.get('FirstName','')} {u.get('LastName','')}".strip()) for u in users}

# Load 2026 job lines
print("Loading 2026 job lines...")
f26 = urllib.parse.quote(f"OrderDate ge {Y1FROM}T00:00:00Z and OrderDate le {Y1TO}T23:59:59Z")
lines26 = fetch_all(f"/JobLines?$filter={f26}", "2026 lines")
print(f"  {len(lines26):,} lines loaded")

# Batch-fetch jobs
print("Fetching job details...")
all_job_ids = list({l["JobID"] for l in lines26 if l.get("JobID")})
CHUNK, JOB_MAP = 15, {}
for i in range(0, len(all_job_ids), CHUNK):
    chunk = all_job_ids[i:i+CHUNK]
    fstr = urllib.parse.quote(" or ".join(f"ID eq {c}" for c in chunk))
    try:
        data = _get(f"/Jobs?$filter={fstr}&$top={CHUNK*2}")
        for j in data.get("value", []):
            JOB_MAP[j["ID"]] = j
    except Exception as e:
        print(f"  chunk {i} failed: {e}")
    if i % 1500 == 0:
        print(f"  jobs {min(i+CHUNK,len(all_job_ids)):,}/{len(all_job_ids):,}...", flush=True)
print(f"  {len(JOB_MAP):,} jobs loaded")

# Build order aggregates grouped by base_ref
by_ref = {}
for l in lines26:
    if l.get("Status") in EXCL_LINE_STAT: continue
    if l.get("LineType") in EXCL_LINE_TYPE: continue
    if not l.get("JobID"): continue
    job = JOB_MAP.get(l["JobID"], {})
    if job.get("JobType") in EXCL_JOB_TYPE: continue

    ref     = job.get("Reference") or str(l["JobID"])
    br      = base_ref(ref)
    sub_ids = set()
    if br not in by_ref:
        by_ref[br] = {
            "order_ref": br,
            "sub_jobs": set(),
            "rep": user_map.get(job.get("SalesRepID"), f"Rep {job.get('SalesRepID','?')}"),
            "rep_id": job.get("SalesRepID"),
            "first_order_date": l.get("OrderDate", ""),
            "last_order_date": l.get("OrderDate", ""),
            "std": 0, "disc": 0, "cost": 0,
            "line_count": 0,
            "job_type": job.get("JobType", ""),
        }
    entry = by_ref[br]
    entry["sub_jobs"].add(ref)
    disc = safe_disc(l)
    std  = l.get("StandardPriceExTax") or 0
    cost = safe_cost(l)
    entry["disc"]       += disc
    entry["std"]        += std
    entry["cost"]       += cost
    entry["line_count"] += 1
    od = l.get("OrderDate", "")
    if od:
        if not entry["first_order_date"] or od < entry["first_order_date"]:
            entry["first_order_date"] = od
        if od > entry["last_order_date"]:
            entry["last_order_date"] = od

# Compute derived fields and filter ≥ $5K
MIN = 5000
orders = []
for br, e in by_ref.items():
    revenue  = e["disc"]
    gp       = revenue - e["cost"]
    disc_pct = max(0, min(100, (1 - e["disc"]/e["std"])*100)) if e["std"] > 0 else 0
    gp_pct   = round(gp/revenue*100, 1) if revenue else 0
    orders.append({
        "order_ref":        br,
        "sub_jobs":         " | ".join(sorted(e["sub_jobs"])),
        "sub_job_count":    len(e["sub_jobs"]),
        "rep":              e["rep"],
        "first_order_date": (e["first_order_date"] or "")[:10],
        "last_order_date":  (e["last_order_date"] or "")[:10],
        "revenue":          round(revenue, 2),
        "std_price":        round(e["std"], 2),
        "cost":             round(e["cost"], 2),
        "gp":               round(gp, 2),
        "gp_pct":           gp_pct,
        "disc_pct":         round(disc_pct, 1),
        "line_count":       e["line_count"],
        "job_type":         e["job_type"],
        "qualifies_5k":     revenue >= MIN,
    })

orders.sort(key=lambda x: x["revenue"], reverse=True)

# Export ALL orders
outfile_all = "raw_orders_2026_all.csv"
fields = ["order_ref","sub_jobs","sub_job_count","rep","first_order_date","last_order_date",
          "revenue","std_price","cost","gp","gp_pct","disc_pct","line_count","job_type","qualifies_5k"]
with open(outfile_all, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(orders)

# Export $5K+ only
orders_5k = [o for o in orders if o["qualifies_5k"]]
outfile_5k = "raw_orders_2026_5k_plus.csv"
with open(outfile_5k, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(orders_5k)

print(f"\n>> Exported:")
print(f"   All orders:    {outfile_all}  ({len(orders):,} rows)")
print(f"   $5K+ orders:   {outfile_5k}  ({len(orders_5k):,} rows)")
print(f"\n   Total $5K+ revenue: ${sum(o['revenue'] for o in orders_5k):,.2f}")
print(f"   Orders with 1 sub-job:  {sum(1 for o in orders_5k if o['sub_job_count']==1)}")
print(f"   Orders with 2 sub-jobs: {sum(1 for o in orders_5k if o['sub_job_count']==2)}")
print(f"   Orders with 3+ sub-jobs:{sum(1 for o in orders_5k if o['sub_job_count']>=3)}")
