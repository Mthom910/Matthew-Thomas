"""Fetch Revenue Initiative metrics for PPTX presentation."""
import urllib.request, urllib.parse, json, base64, math, http.client, time
from concurrent.futures import ThreadPoolExecutor

from insyte_env import EMAIL, KEY
BASE   = "https://api.myinsyte.com.au/v2"
AUTH   = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

Y1FROM, Y1TO = "2026-01-01", "2026-06-26"
Y2FROM, Y2TO = "2025-01-01", "2025-06-26"
MIN_VAL = 5000
BASE_COMM, INIT_COMM = 0.08, 0.12

BUCKETS = [
    {"label":"0–10%",  "min":0,  "max":10},
    {"label":"10–20%", "min":10, "max":20},
    {"label":"20–30%", "min":20, "max":30},
    {"label":"30–35%", "min":30, "max":35},
    {"label":"35–40%", "min":35, "max":40, "initiative":True},
    {"label":"40–50%", "min":40, "max":50},
    {"label":"50%+",   "min":50, "max":100},
]

def _get(path, retries=5):
    url = f"{BASE}/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3 ** attempt)
            else:
                raise

def fetch_all(path, label=""):
    PAGE, rows, skip, pg = 500, [], 0, 1
    sep = "&" if "?" in path else "?"
    while True:
        print(f"  {label} p{pg}...", flush=True)
        data = _get(f"{path}{sep}$top={PAGE}&$skip={skip}")
        page = data.get("value", data if isinstance(data, list) else [])
        rows.extend(page)
        if len(page) < PAGE: break
        skip += PAGE; pg += 1
    return rows

def df(field, f, t):
    return f"{field} ge {f}T00:00:00Z and {field} le {t}T23:59:59Z"

def base_ref(r):
    import re
    return re.sub(r"-\d+$", "", str(r or ""))

def batch_jobs(ids):
    CHUNK, WAVE, MAP = 15, 5, {}
    chunks = [ids[i:i+CHUNK] for i in range(0, len(ids), CHUNK)]
    for i in range(0, len(chunks), WAVE):
        wave = chunks[i:i+WAVE]
        print(f"  Jobs {min((i+WAVE)*CHUNK,len(ids))}/{len(ids)}...", flush=True)
        def fetch_chunk(ch):
            f = urllib.parse.quote(" or ".join(f"ID eq {id_}" for id_ in ch))
            return fetch_all(f"/Jobs?$filter={f}", "J")
        with ThreadPoolExecutor(max_workers=WAVE) as ex:
            for rows in ex.map(fetch_chunk, wave):
                for j in rows: MAP[j["ID"]] = j
    return MAP

def build_agg(lines, job_map, user_map):
    by_ref = {}
    for l in lines:
        job = job_map.get(l.get("JobID"), {})
        ref = base_ref(job.get("Reference") or str(l.get("JobID", "")))
        if ref not in by_ref:
            by_ref[ref] = {
                "ref": ref, "rep": user_map.get(job.get("SalesRepID"), f"Rep {job.get('SalesRepID','?')}"),
                "month": (l.get("OrderDate") or "")[:7],
                "std": 0, "disc": 0, "revenue": 0, "cost": 0, "gp": 0, "lines": 0,
            }
        std  = l.get("StandardPriceExTax", 0) or 0
        disc = l.get("DiscountedPriceExTax", std) or std
        cost = (l.get("DiscountedCostExTax") or l.get("StandardCostExTax") or 0) + \
               (l.get("StandardIntallCostExTax") or 0) + (l.get("StandardDeliveryCostExTax") or 0)
        by_ref[ref]["std"]     += std
        by_ref[ref]["disc"]    += disc
        by_ref[ref]["revenue"] += disc
        by_ref[ref]["cost"]    += cost
        by_ref[ref]["gp"]      += disc - cost
        by_ref[ref]["lines"]   += 1
    result = []
    for j in by_ref.values():
        disc_pct = max(0, min(100, (1 - j["disc"] / j["std"]) * 100)) if j["std"] > 0 else 0
        gp_pct   = (j["gp"] / j["revenue"] * 100) if j["revenue"] > 0 else 0
        bi = next((i for i, b in enumerate(BUCKETS) if disc_pct >= b["min"] and disc_pct < b["max"]), 0)
        result.append({**j, "disc_pct": round(disc_pct, 1), "gp_pct": round(gp_pct, 1), "bucket_idx": bi})
    return result

def comm_job(j):
    return j["revenue"] * (INIT_COMM if j["bucket_idx"] == 4 else BASE_COMM)

# ── FETCH ──────────────────────────────────────────────────
print("Fetching users...")
users_raw = fetch_all("/Users", "U")
users = {u["ID"]: (u.get("FullName") or f"{u.get('FirstName','')} {u.get('LastName','')}".strip() or f"Rep {u['ID']}") for u in users_raw}

print("Fetching 2026 job lines...")
l26 = fetch_all(f"/JobLines?$filter={urllib.parse.quote(df('OrderDate', Y1FROM, Y1TO))}", "2026L")
print("Fetching 2025 job lines...")
l25 = fetch_all(f"/JobLines?$filter={urllib.parse.quote(df('OrderDate', Y2FROM, Y2TO))}", "2025L")

print("Fetching jobs...")
all_ids = list({l["JobID"] for l in l26 + l25 if l.get("JobID")})
job_map = batch_jobs(all_ids)

print("Fetching 2026 opportunities...")
o26 = fetch_all(f"/Opportunities?$filter={urllib.parse.quote(df('CreatedOn', Y1FROM, Y1TO))}", "2026O")
print("Fetching 2025 opportunities...")
o25 = fetch_all(f"/Opportunities?$filter={urllib.parse.quote(df('CreatedOn', Y2FROM, Y2TO))}", "2025O")

print("Fetching 2026 activities...")
a26 = fetch_all(f"/Activities?$filter={urllib.parse.quote(df('Start', Y1FROM, Y1TO))}", "2026A")
print("Fetching 2025 activities...")
a25 = fetch_all(f"/Activities?$filter={urllib.parse.quote(df('Start', Y2FROM, Y2TO))}", "2025A")

# ── BUILD ──────────────────────────────────────────────────
print("Aggregating...")
all26 = build_agg(l26, job_map, users)
all25 = build_agg(l25, job_map, users)
j26 = [j for j in all26 if j["revenue"] >= MIN_VAL]
j25 = [j for j in all25 if j["revenue"] >= MIN_VAL]

def rev(arr): return sum(j["revenue"] for j in arr)
def gp(arr):  return sum(j["gp"]      for j in arr)
def aov(arr): return rev(arr) / len(arr) if arr else 0
def avg_disc(arr): return sum(j["disc_pct"] for j in arr) / len(arr) if arr else 0

# KPIs
r26, r25 = rev(j26), rev(j25)
g26, g25 = gp(j26),  gp(j25)
tc26 = sum(comm_job(j) for j in j26)
tc25 = sum(comm_job(j) for j in j25)
init26 = [j for j in j26 if j["bucket_idx"] == 4]
init25 = [j for j in j25 if j["bucket_idx"] == 4]

conv_rate = lambda jobs, acts: round(len(jobs)/len(acts)*100, 1) if acts else 0

# By bucket
bucket_data = []
for i, b in enumerate(BUCKETS):
    g26b = [j for j in j26 if j["bucket_idx"] == i]
    g25b = [j for j in j25 if j["bucket_idx"] == i]
    bucket_data.append({
        "label": b["label"],
        "initiative": b.get("initiative", False),
        "count26": len(g26b), "rev26": rev(g26b), "gp26": gp(g26b),
        "count25": len(g25b), "rev25": rev(g25b), "gp25": gp(g25b),
    })

# By rep (top reps)
by_rep = {}
for j in j26:
    r = j["rep"]
    if r not in by_rep: by_rep[r] = {"jobs26":0,"rev26":0,"gp26":0,"comm26":0,"init26":0}
    by_rep[r]["jobs26"] += 1
    by_rep[r]["rev26"]  += j["revenue"]
    by_rep[r]["gp26"]   += j["gp"]
    by_rep[r]["comm26"] += comm_job(j)
    if j["bucket_idx"] == 4: by_rep[r]["init26"] += 1
for j in j25:
    r = j["rep"]
    if r not in by_rep: by_rep[r] = {"jobs26":0,"rev26":0,"gp26":0,"comm26":0,"init26":0}
    if "rev25" not in by_rep[r]: by_rep[r].update({"jobs25":0,"rev25":0,"gp25":0,"comm25":0})
    by_rep[r]["jobs25"] = by_rep[r].get("jobs25",0) + 1
    by_rep[r]["rev25"]  = by_rep[r].get("rev25",0) + j["revenue"]
    by_rep[r]["gp25"]   = by_rep[r].get("gp25",0)  + j["gp"]
    by_rep[r]["comm25"] = by_rep[r].get("comm25",0) + comm_job(j)

top_reps = sorted(by_rep.items(), key=lambda x: x[1]["rev26"], reverse=True)[:8]

# Monthly trend
months26 = sorted({j["month"] for j in j26 if j["month"]})
months25 = sorted({j["month"] for j in j25 if j["month"]})
monthly26 = [{"month": m, "jobs": len([j for j in j26 if j["month"]==m]),
              "rev": rev([j for j in j26 if j["month"]==m]),
              "init": len([j for j in j26 if j["month"]==m and j["bucket_idx"]==4])} for m in months26]
monthly25 = [{"month": m, "jobs": len([j for j in j25 if j["month"]==m]),
              "rev": rev([j for j in j25 if j["month"]==m])} for m in months25]

sub26 = [j for j in all26 if j["revenue"] < MIN_VAL]
sub25 = [j for j in all25 if j["revenue"] < MIN_VAL]

out = {
    "period": {"y1": f"{Y1FROM} to {Y1TO}", "y2": f"{Y2FROM} to {Y2TO}"},
    "kpis": {
        "jobs26": len(j26), "jobs25": len(j25),
        "rev26": round(r26,0), "rev25": round(r25,0),
        "gp26": round(g26,0),  "gp25": round(g25,0),
        "gp_pct26": round(g26/r26*100,1) if r26 else 0,
        "gp_pct25": round(g25/r25*100,1) if r25 else 0,
        "avg_disc26": round(avg_disc(j26),1), "avg_disc25": round(avg_disc(j25),1),
        "init_jobs26": len(init26), "init_jobs25": len(init25),
        "init_pct26": round(len(init26)/len(j26)*100,1) if j26 else 0,
        "init_pct25": round(len(init25)/len(j25)*100,1) if j25 else 0,
        "aov_all26": round(aov(all26),0),   "aov_all25": round(aov(all25),0),
        "aov_over26": round(aov(j26),0),    "aov_over25": round(aov(j25),0),
        "aov_under26": round(aov(sub26),0), "aov_under25": round(aov(sub25),0),
        "acts26": len(a26), "acts25": len(a25),
        "conv_all26": conv_rate(all26, a26), "conv_all25": conv_rate(all25, a25),
        "conv_over26": conv_rate(j26, a26),  "conv_over25": conv_rate(j25, a25),
        "conv_under26": conv_rate(sub26, a26),"conv_under25": conv_rate(sub25, a25),
        "comm26": round(tc26,0), "comm25": round(tc25,0),
        "comm_rate26": round(tc26/r26*100,1) if r26 else 0,
        "opps26_total": len(o26), "opps26_won": len([o for o in o26 if (o.get("Status","")).lower()=="won"]),
        "opps26_lost": len([o for o in o26 if (o.get("Status","")).lower()=="lost"]),
        "opps26_open": len([o for o in o26 if (o.get("Status","")).lower()=="open"]),
        "opps25_total": len(o25), "opps25_won": len([o for o in o25 if (o.get("Status","")).lower()=="won"]),
    },
    "buckets": bucket_data,
    "top_reps": [{"rep": r, **d} for r, d in top_reps],
    "monthly26": monthly26,
    "monthly25": monthly25,
}

with open("initiative_data.json", "w") as f:
    json.dump(out, f, indent=2)
print("\nDone — initiative_data.json written")
print(json.dumps(out["kpis"], indent=2))
