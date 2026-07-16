"""Fetch fresh initiative data with corrected Sales Appointment counts."""
import urllib.request, urllib.parse, json, base64, time
from collections import defaultdict

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

Y1FROM, Y1TO = "2026-01-01", "2026-06-27"
Y2FROM, Y2TO = "2025-01-01", "2025-06-27"

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

def df(field, frm, to):
    return f"{field} ge {frm}T00:00:00Z and {field} le {to}T23:59:59Z"

EXCLUDE_STATUS   = {"status_job_line_cancelled"}
EXCLUDE_STAGE    = {"stage_job_line_unconfirmed"}
EXCLUDE_TYPE     = {"type_job_line_remake", "type_job_line_service", "type_job_line_alter"}
EXCLUDE_JOB_TYPE = {"type_job_service"}

def base_ref(r):
    """Strip trailing -N suffix to get the unique order reference."""
    import re as _re
    return _re.sub(r'-\d+$', '', str(r or ''))

def safe_disc(l):
    v = l.get("DiscountedPriceExTax")
    return v if v is not None else (l.get("StandardPriceExTax") or 0)

def safe_cost(l):
    c = l.get("DiscountedCostExTax")
    if c is None: c = l.get("StandardCostExTax") or 0
    return c + (l.get("StandardIntallCostExTax") or 0) + (l.get("StandardDeliveryCostExTax") or 0)

BUCKETS = [
    {"label": "0–10%",  "min": 0,  "max": 10,  "initiative": False},
    {"label": "10–20%", "min": 10, "max": 20,  "initiative": False},
    {"label": "20–30%", "min": 20, "max": 30,  "initiative": False},
    {"label": "30–35%", "min": 30, "max": 35,  "initiative": False},
    {"label": "35–40%", "min": 35, "max": 40,  "initiative": True},
    {"label": "40–50%", "min": 40, "max": 50,  "initiative": False},
    {"label": "50%+",   "min": 50, "max": 100, "initiative": False},
]

def get_bucket_idx(disc_pct):
    for i, b in enumerate(BUCKETS):
        if b["min"] <= disc_pct < b["max"]: return i
    return len(BUCKETS) - 1

def build_jobs(lines, job_map, user_map):
    by_job = {}
    for l in lines:
        if not l.get("JobID"): continue
        if l.get("Status") in EXCLUDE_STATUS: continue
        if l.get("Stage") in EXCLUDE_STAGE: continue
        if l.get("LineType") in EXCLUDE_TYPE: continue
        job = job_map.get(l["JobID"], {})
        if job.get("JobType") in EXCLUDE_JOB_TYPE: continue
        key = base_ref(job.get("Reference") or str(l["JobID"]))
        if key not in by_job:
            by_job[key] = {
                "jobId": l["JobID"],
                "rep": user_map.get(job.get("SalesRepID"), f"Rep {job.get('SalesRepID','?')}"),
                "repId": job.get("SalesRepID"),
                "month": (l.get("OrderDate") or "")[:7],
                "std": 0, "disc": 0, "cost": 0,
            }
        by_job[key]["std"]  += l.get("StandardPriceExTax") or 0
        by_job[key]["disc"] += safe_disc(l)
        by_job[key]["cost"] += safe_cost(l)
    jobs = []
    for key, j in by_job.items():
        revenue = j["disc"]
        gp      = revenue - j["cost"]
        disc_pct = max(0, min(100, (1 - j["disc"]/j["std"])*100)) if j["std"] > 0 else 0
        bi = get_bucket_idx(disc_pct)
        jobs.append({**j, "revenue": revenue, "gp": gp, "disc_pct": round(disc_pct, 1),
                     "bucket_idx": bi, "gp_pct": round(gp/revenue*100, 1) if revenue else 0})
    return jobs

# ── 1. Users ───────────────────────────────────────────────
print("Loading users...")
users = fetch_all("/Users", "users")
user_map = {u["ID"]: (u.get("FullName") or f"{u.get('FirstName','')} {u.get('LastName','')}".strip()) for u in users}
print(f"  {len(user_map)} users")

# ── 2. Job Lines ───────────────────────────────────────────
print("Loading 2026 job lines...")
lines26 = fetch_all(f"/JobLines?$filter={urllib.parse.quote(df('OrderDate',Y1FROM,Y1TO))}", "2026 lines")
print("Loading 2025 job lines...")
lines25 = fetch_all(f"/JobLines?$filter={urllib.parse.quote(df('OrderDate',Y2FROM,Y2TO))}", "2025 lines")

# ── 3. Batch-fetch Jobs ────────────────────────────────────
print("Fetching job details...")
all_job_ids = list({l["JobID"] for l in lines26 + lines25 if l.get("JobID")})
CHUNK, JOB_MAP = 15, {}
for i in range(0, len(all_job_ids), CHUNK):
    chunk = all_job_ids[i:i+CHUNK]
    fstr = urllib.parse.quote(" or ".join(f"ID eq {c}" for c in chunk))
    try:
        data = _get(f"/Jobs?$filter={fstr}&$top={CHUNK*2}")
        for j in data.get("value", []):
            JOB_MAP[j["ID"]] = j
    except Exception: pass
    if i % 1500 == 0: print(f"  jobs {min(i+CHUNK,len(all_job_ids)):,}/{len(all_job_ids):,}...", flush=True)
print(f"  {len(JOB_MAP):,} jobs loaded")

# ── 4. Build job aggregates ────────────────────────────────
jobs26 = build_jobs(lines26, JOB_MAP, user_map)
jobs25 = build_jobs(lines25, JOB_MAP, user_map)
print(f"2026: {len(jobs26):,} jobs  ${sum(j['revenue'] for j in jobs26):,.0f}")
print(f"2025: {len(jobs25):,} jobs  ${sum(j['revenue'] for j in jobs25):,.0f}")

# ── 5. Sales Appointments (ActivityType = 'Sales Appointment', not cancelled) ──
print("Loading 2026 sales appointments...")
af26 = urllib.parse.quote(df("Start",Y1FROM,Y1TO) + " and ActivityType eq 'Sales Appointment' and Cancelled eq false")
acts26 = fetch_all(f"/Activities?$filter={af26}", "2026 appts")
print("Loading 2025 sales appointments...")
af25 = urllib.parse.quote(df("Start",Y2FROM,Y2TO) + " and ActivityType eq 'Sales Appointment' and Cancelled eq false")
acts25 = fetch_all(f"/Activities?$filter={af25}", "2025 appts")
print(f"2026 appts: {len(acts26):,}  |  2025 appts: {len(acts25):,}")

# ── 6. Compute KPIs ────────────────────────────────────────
MIN = 5000
j26h = [j for j in jobs26 if j["revenue"] >= MIN]
j25h = [j for j in jobs25 if j["revenue"] >= MIN]

def total(arr, k): return sum(j[k] for j in arr)

rev26 = total(j26h, "revenue");  rev25 = total(j25h, "revenue")
gp26  = total(j26h, "gp");       gp25  = total(j25h, "gp")
all_rev26 = total(jobs26, "revenue"); all_rev25 = total(jobs25, "revenue")
all_gp26  = total(jobs26, "gp");      all_gp25  = total(jobs25, "gp")

init26 = [j for j in j26h if j["bucket_idx"] == 4]
init25 = [j for j in j25h if j["bucket_idx"] == 4]

def avg_disc(arr): return round(sum(j["disc_pct"] for j in arr)/len(arr), 1) if arr else 0
def aov(arr):      return round(total(arr,"revenue")/len(arr)) if arr else 0

a_acts26 = len(acts26); a_acts25 = len(acts25)

def conv(jobs, acts): return round(len(jobs)/acts*100, 1) if acts else 0

# Price segment AOV (all jobs)
PRICE_SEGS = [
    {"label":"<$1K",     "min":0,     "max":1000},
    {"label":"$1K-$2K",  "min":1000,  "max":2000},
    {"label":"$2K-$3K",  "min":2000,  "max":3000},
    {"label":"$3K-$5K",  "min":3000,  "max":5000},
    {"label":"$5K-$10K", "min":5000,  "max":10000},
    {"label":"$10K+",    "min":10000, "max":1e9},
]
def seg_stats(jobs, seg):
    g = [j for j in jobs if seg["min"] <= j["revenue"] < seg["max"]]
    return {"count": len(g), "total_rev": round(sum(j["revenue"] for j in g), 2),
            "aov": round(sum(j["revenue"] for j in g)/len(g)) if g else 0}

price_segs = []
for seg in PRICE_SEGS:
    s26 = seg_stats(jobs26, seg)
    s25 = seg_stats(jobs25, seg)
    price_segs.append({**seg, "max": seg["max"] if seg["max"] < 1e9 else None,
                       "count26": s26["count"], "rev26": s26["total_rev"], "aov26": s26["aov"],
                       "count25": s25["count"], "rev25": s25["total_rev"], "aov25": s25["aov"]})

# Bucket breakdown
buckets = []
for i, b in enumerate(BUCKETS):
    g26 = [j for j in j26h if j["bucket_idx"] == i]
    g25 = [j for j in j25h if j["bucket_idx"] == i]
    buckets.append({**b,
        "count26": len(g26), "rev26": round(total(g26,"revenue"),2), "gp26": round(total(g26,"gp"),2),
        "count25": len(g25), "rev25": round(total(g25,"revenue"),2), "gp25": round(total(g25,"gp"),2),
    })

# Monthly breakdown
def monthly_stats(jobs, year):
    by_month = defaultdict(lambda: {"jobs":0,"rev":0,"init":0})
    for j in jobs:
        m = j["month"]
        if not m: continue
        by_month[m]["jobs"] += 1
        by_month[m]["rev"]  += j["revenue"]
        if j["bucket_idx"] == 4: by_month[m]["init"] += 1
    out = []
    for m in sorted(by_month):
        d = by_month[m]
        row = {"month": m, "jobs": d["jobs"], "rev": round(d["rev"], 2)}
        if year == 26: row["init"] = d["init"]
        out.append(row)
    return out

# Monthly appointments
def monthly_appts(acts):
    by_month = defaultdict(int)
    for a in acts:
        m = (a.get("Start") or "")[:7]
        if m: by_month[m] += 1
    return dict(sorted(by_month.items()))

# Top reps (by 2026 revenue on $5K+ jobs)
by_rep26 = defaultdict(lambda: {"jobs":0,"rev":0,"gp":0,"init":0})
by_rep25 = defaultdict(lambda: {"jobs":0,"rev":0,"gp":0,"init":0})
for j in j26h:
    r = j["rep"]; by_rep26[r]["jobs"]+=1; by_rep26[r]["rev"]+=j["revenue"]; by_rep26[r]["gp"]+=j["gp"]
    if j["bucket_idx"]==4: by_rep26[r]["init"]+=1
for j in j25h:
    r = j["rep"]; by_rep25[r]["jobs"]+=1; by_rep25[r]["rev"]+=j["revenue"]; by_rep25[r]["gp"]+=j["gp"]

BASE_RATE = 0.08; INIT_RATE = 0.12
def comm(rev, is_init): return rev * (INIT_RATE if is_init else BASE_RATE)

# Compute commission per rep
for j in j26h:
    r = j["rep"]
    by_rep26[r].setdefault("comm", 0)
    by_rep26[r]["comm"] += comm(j["revenue"], j["bucket_idx"]==4)
for j in j25h:
    r = j["rep"]
    by_rep25[r].setdefault("comm", 0)
    by_rep25[r]["comm"] += comm(j["revenue"], j["bucket_idx"]==4)

top_reps = []
for rep, d in sorted(by_rep26.items(), key=lambda x: -x[1]["rev"])[:8]:
    d25 = by_rep25.get(rep, {})
    row = {"rep": rep, "jobs26": d["jobs"], "rev26": round(d["rev"],2),
           "gp26": round(d["gp"],2), "comm26": round(d.get("comm",0),2), "init26": d["init"]}
    if d25: row.update({"jobs25": d25["jobs"], "rev25": round(d25["rev"],2),
                         "gp25": round(d25["gp"],2), "comm25": round(d25.get("comm",0),2)})
    top_reps.append(row)

# Total commission
total_comm26 = sum(comm(j["revenue"], j["bucket_idx"]==4) for j in j26h)
total_comm25 = sum(comm(j["revenue"], j["bucket_idx"]==4) for j in j25h)
eff_rate26 = round(total_comm26/rev26*100, 1) if rev26 else 0

# Opportunities (just totals — already minimal)
print("Loading opportunity counts...")
try:
    of26 = urllib.parse.quote(df("CreatedOn",Y1FROM,Y1TO))
    opps26 = _get(f"/Opportunities?$filter={of26}&$top=1")
    opps26_total = opps26.get("@odata.count", len(opps26.get("value",[])))
    of25 = urllib.parse.quote(df("CreatedOn",Y2FROM,Y2TO))
    opps25 = _get(f"/Opportunities?$filter={of25}&$top=1")
    opps25_total = opps25.get("@odata.count", len(opps25.get("value",[])))
except:
    opps26_total = opps25_total = 0

# Monthly appointment counts
m_appts26 = monthly_appts(acts26)
m_appts25 = monthly_appts(acts25)

# ── 7. Assemble output ────────────────────────────────────
out = {
    "period": {"y1": f"{Y1FROM} to {Y1TO}", "y2": f"{Y2FROM} to {Y2TO}"},
    "kpis": {
        # $5K+ jobs
        "jobs26": len(j26h), "jobs25": len(j25h),
        "rev26": round(rev26,2), "rev25": round(rev25,2),
        "gp26":  round(gp26,2),  "gp25":  round(gp25,2),
        "gp_pct26": round(gp26/rev26*100,1) if rev26 else 0,
        "gp_pct25": round(gp25/rev25*100,1) if rev25 else 0,
        "avg_disc26": avg_disc(j26h), "avg_disc25": avg_disc(j25h),
        "init_jobs26": len(init26), "init_jobs25": len(init25),
        "init_pct26": round(len(init26)/len(j26h)*100,1) if j26h else 0,
        "init_pct25": round(len(init25)/len(j25h)*100,1) if j25h else 0,
        # All jobs AOV
        "aov_all26": aov(jobs26), "aov_all25": aov(jobs25),
        "aov_over26": aov(j26h),  "aov_over25": aov(j25h),
        "aov_under26": aov([j for j in jobs26 if j["revenue"]<MIN]),
        "aov_under25": aov([j for j in jobs25 if j["revenue"]<MIN]),
        # Sales appointments (corrected)
        "acts26": a_acts26, "acts25": a_acts25,
        # Conversion rates ($5K+ jobs / all sales appts)
        "conv_all26": conv(jobs26, a_acts26), "conv_all25": conv(jobs25, a_acts25),
        "conv_over26": conv(j26h, a_acts26),  "conv_over25": conv(j25h, a_acts25),
        "conv_under26": conv([j for j in jobs26 if j["revenue"]<MIN], a_acts26),
        "conv_under25": conv([j for j in jobs25 if j["revenue"]<MIN], a_acts25),
        # Commission
        "comm26": round(total_comm26,2), "comm25": round(total_comm25,2),
        "comm_rate26": eff_rate26,
        # All-jobs totals
        "all_jobs26": len(jobs26), "all_jobs25": len(jobs25),
        "all_rev26": round(all_rev26,2), "all_rev25": round(all_rev25,2),
        "all_gp26":  round(all_gp26,2),  "all_gp25":  round(all_gp25,2),
        # Opps
        "opps26_total": opps26_total, "opps25_total": opps25_total,
    },
    "buckets": buckets,
    "price_segs": price_segs,
    "top_reps": top_reps,
    "monthly26": monthly_stats(j26h, 26),
    "monthly25": monthly_stats(j25h, 25),
    "monthly_appts26": m_appts26,
    "monthly_appts25": m_appts25,
}

with open("initiative_data.json", "w") as f:
    json.dump(out, f, indent=2)

print("\n>> initiative_data.json saved")
print(f"   2026: {len(j26h):,} $5K+ jobs  ${rev26:,.0f}  |  appts: {a_acts26:,}  |  conv: {conv(j26h,a_acts26)}%")
print(f"   2025: {len(j25h):,} $5K+ jobs  ${rev25:,.0f}  |  appts: {a_acts25:,}  |  conv: {conv(j25h,a_acts25)}%")
print(f"   Initiative bracket: {len(init26)} jobs 2026 vs {len(init25)} jobs 2025")
print(f"   Total commission: ${total_comm26:,.0f} 2026  vs  ${total_comm25:,.0f} 2025")
