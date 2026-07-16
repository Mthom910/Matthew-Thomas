import urllib.request, urllib.parse, json, base64, time, re
from collections import Counter, defaultdict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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

OPT_KEYS = [f"DisplayOption{i}" for i in range(1, 11)]

# ── Fetch all 2026 job lines (confirmed) + all 2026 jobs for quote-stage lines
# Strategy: fetch confirmed lines via OrderDate, PLUS all jobs via JobDate then batch lines
print("Fetching all 2026 confirmed job lines...")
f_conf = urllib.parse.quote("OrderDate ge 2026-01-01T00:00:00Z and OrderDate le 2026-06-29T23:59:59Z")
conf_lines = fetch_all(f"/JobLines?$filter={f_conf}", "confirmed lines")
print(f"  {len(conf_lines):,} confirmed lines\n")

# Also fetch all 2026 jobs (all stages) to get quote-stage job IDs
print("Fetching all 2026 jobs (all stages)...")
jf = urllib.parse.quote("JobDate ge 2026-01-01T00:00:00Z and JobDate le 2026-06-29T23:59:59Z")
all_jobs_2026 = fetch_all(f"/Jobs?$filter={jf}", "all 2026 jobs")
job_map = {j["ID"]: j for j in all_jobs_2026}
print(f"  {len(all_jobs_2026):,} job records ({len(job_map):,} unique job IDs)\n")

# Batch fetch lines for ALL 2026 jobs (including quote-stage)
print("Fetching lines for all 2026 jobs (incl. quotes)...")
all_job_ids = list(job_map.keys())
CHUNK = 15
all_lines_raw = []
for i in range(0, len(all_job_ids), CHUNK):
    chunk = all_job_ids[i:i+CHUNK]
    fstr  = urllib.parse.quote(" or ".join(f"ID eq {c}" for c in chunk))
    try:
        data = _get(f"/JobLines?$filter={fstr}&$top={CHUNK*20}")
        all_lines_raw.extend(data.get("value", []))
    except Exception as e:
        print(f"  Warning chunk {i}: {e}")
    if i % 750 == 0:
        print(f"  jobs {min(i+CHUNK, len(all_job_ids)):,}/{len(all_job_ids):,}...", flush=True)

print(f"  {len(all_lines_raw):,} total lines (all stages)\n")

# Use all lines (deduplicated by line ID)
seen_ids = set()
all_lines = []
for l in all_lines_raw:
    lid = l.get("ID")
    if lid not in seen_ids:
        seen_ids.add(lid)
        all_lines.append(l)
print(f"  {len(all_lines):,} unique lines after dedup\n")

# ── Enumerate ALL unique DisplayOption key:value pairs
print("="*60)
print("ALL DISTINCT DisplayOption KEYS AND VALUES")
print("="*60)
key_vals = defaultdict(Counter)  # key_prefix -> Counter of values
for l in all_lines:
    for opt in OPT_KEYS:
        val = (l.get(opt) or "").strip()
        if not val: continue
        colon = val.find(":")
        if colon > 0:
            prefix = val[:colon].strip()
            value  = val[colon+1:].strip()
            key_vals[prefix][value] += 1
        else:
            key_vals["(no key)"][val] += 1

# Print all keys sorted by total count
print(f"\nTotal distinct DisplayOption keys found: {len(key_vals)}")
for key in sorted(key_vals, key=lambda k: -sum(key_vals[k].values())):
    total = sum(key_vals[key].values())
    vals  = key_vals[key].most_common()
    print(f"\n  [{total:,} lines] {key!r}:")
    for v, c in vals[:15]:
        print(f"    {c:5d}  {v!r}")

# ── Find the exact Fixing and Takedown fields
print("\n" + "="*60)
print("FIXING VALUES (all lines)")
print("="*60)
for v, c in key_vals.get("Fixing", Counter()).most_common():
    print(f"  {c:5d}  {v!r}")

print("\n" + "="*60)
print("KEYS CONTAINING 'TAKE' OR 'DOWN' OR 'EXISTING' OR 'REMOVAL'")
print("="*60)
for key in key_vals:
    kl = key.lower()
    if any(t in kl for t in ["take", "down", "existing", "remov", "old", "replace"]):
        total = sum(key_vals[key].values())
        print(f"\n  [{total}] {key!r}:")
        for v, c in key_vals[key].most_common():
            print(f"    {c:5d}  {v!r}")
