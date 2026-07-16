import urllib.request, urllib.parse, json, base64, time, re
from collections import Counter, defaultdict

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

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

# ── Fetch all 2026 confirmed job lines
print("Fetching 2026 confirmed job lines...")
f = urllib.parse.quote("OrderDate ge 2026-01-01T00:00:00Z and OrderDate le 2026-06-29T23:59:59Z")
lines = fetch_all(f"/JobLines?$filter={f}", "2026 lines")
print(f"  {len(lines):,} total lines\n")

OPT_KEYS = [f"DisplayOption{i}" for i in range(1, 11)]
EXCL_STATUS = {"status_job_line_cancelled"}
EXCL_TYPE   = {"type_job_line_remake", "type_job_line_service", "type_job_line_alter"}
EXCL_STAGE  = {"stage_job_line_unconfirmed"}

active = [l for l in lines
          if l.get("Status") not in EXCL_STATUS
          and l.get("LineType") not in EXCL_TYPE
          and l.get("Stage") not in EXCL_STAGE]
print(f"Active lines (excl. cancelled/service/unconfirmed): {len(active):,}\n")

# ── 1. BRICK FITTING ANALYSIS
# Search all DisplayOption fields for "brick"
print("=" * 60)
print("BRICK FITTING ANALYSIS")
print("=" * 60)

brick_lines = []
brick_opt_vals = Counter()

for l in active:
    found = False
    for key in OPT_KEYS:
        val = l.get(key) or ""
        if "brick" in val.lower():
            brick_lines.append(l)
            brick_opt_vals[val.strip()] += 1
            found = True
            break

print(f"Lines with 'brick' in any DisplayOption: {len(brick_lines):,}")

# Count unique jobs (base refs) with brick fitting
brick_jobs = set(base_ref(l.get("JobLineNo","") or "") for l in brick_lines)
# Better: get job IDs
brick_job_ids = set(l.get("JobID") for l in brick_lines if l.get("JobID"))
print(f"Unique JobIDs with brick fitting:        {len(brick_job_ids):,}")

print(f"\nTop brick-related DisplayOption values:")
for val, cnt in brick_opt_vals.most_common(20):
    print(f"  {cnt:4d}  {val!r}")

# Also check what products are involved
brick_products = Counter(l.get("Product") for l in brick_lines)
print(f"\nProducts with brick fitting:")
for p, c in brick_products.most_common(15):
    print(f"  {c:4d}  {p}")

# ── 2. TAKEDOWN ANALYSIS
print("\n" + "=" * 60)
print("TAKEDOWN ANALYSIS")
print("=" * 60)

# Check by Product name
takedown_lines = []
for l in lines:  # include all lines including cancelled/remake
    prod = (l.get("Product") or "").lower()
    if "take" in prod and ("down" in prod or "takedown" in prod):
        takedown_lines.append(l)

# Also check by LineType
print(f"\nAll lines (incl. cancelled): {len(lines):,}")
linetype_counts = Counter(l.get("LineType") for l in lines)
print("\nAll LineType values in 2026:")
for k, v in linetype_counts.most_common():
    print(f"  {k!r}: {v:,}")

print(f"\nProduct-based takedown lines: {len(takedown_lines):,}")
td_products = Counter(l.get("Product") for l in takedown_lines)
for p, c in td_products.most_common():
    print(f"  {c:4d}  {p!r}")

# Unique jobs with takedowns (by product)
td_job_ids = set(l.get("JobID") for l in takedown_lines if l.get("JobID"))
print(f"Unique JobIDs with takedown product: {len(td_job_ids):,}")

# Also check for "alter" products (these are sometimes used for takedown/removal)
alter_lines = [l for l in lines if (l.get("Product") or "").lower().startswith("alter")]
alter_products = Counter(l.get("Product") for l in alter_lines)
print(f"\nAlter-type product lines: {len(alter_lines):,}")
for p, c in alter_products.most_common():
    print(f"  {c:4d}  {p!r}")

# ── 3. Check specifically for "Roller" takedowns
print("\n" + "=" * 60)
print("ROLLER BLIND TAKEDOWNS")
print("=" * 60)

# Take Downs that are on the same job as Roller blinds
td_job_ids_set = set(l.get("JobID") for l in takedown_lines if l.get("JobID"))
roller_td_jobs = set()
for l in lines:
    if l.get("JobID") in td_job_ids_set:
        prod = (l.get("Product") or "").lower()
        if "roller" in prod:
            roller_td_jobs.add(l.get("JobID"))
print(f"Jobs with both a takedown AND roller blind product: {len(roller_td_jobs):,}")

# Look for any DisplayOption that mentions roller + takedown
roller_takedown_opts = []
for l in lines:
    for key in OPT_KEYS:
        val = (l.get(key) or "").lower()
        if ("take" in val and "down" in val) or "takedown" in val or "take down" in val:
            roller_takedown_opts.append((l.get("Product"), l.get(key)))
            break

print(f"\nLines with takedown in DisplayOptions: {len(roller_takedown_opts):,}")
for prod, val in roller_takedown_opts[:20]:
    print(f"  Product: {prod!r}  |  Option: {val!r}")
