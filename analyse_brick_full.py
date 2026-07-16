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

# Fetch all 2026 lines
print("Fetching all 2026 lines...")
f = urllib.parse.quote("OrderDate ge 2026-01-01T00:00:00Z and OrderDate le 2026-06-29T23:59:59Z")
lines = fetch_all(f"/JobLines?$filter={f}", "lines")
print(f"  Total: {len(lines):,}\n")

OPT_KEYS = [f"DisplayOption{i}" for i in range(1, 11)]
ALL_TEXT  = OPT_KEYS + ["Notes", "SupplyNotes", "InstallationNotes", "Location"]

EXCL_STATUS = {"status_job_line_cancelled"}
EXCL_TYPE   = {"type_job_line_remake", "type_job_line_service", "type_job_line_alter"}
EXCL_STAGE  = {"stage_job_line_unconfirmed"}
active = [l for l in lines
          if l.get("Status") not in EXCL_STATUS
          and l.get("LineType") not in EXCL_TYPE
          and l.get("Stage") not in EXCL_STAGE]

# ── ALL unique Fixing/Application/Bracket values across full dataset
print("=" * 60)
print("ALL FIXING / APPLICATION / BRACKET VALUES (full dataset)")
print("=" * 60)
all_fixing_vals = Counter()
for l in active:
    for key in OPT_KEYS:
        val = l.get(key) or ""
        vl  = val.lower()
        if (vl.startswith("fixing:") or vl.startswith("application:")
                or vl.startswith("bracket") or "brick" in vl
                or "masonry" in vl or "timber" in vl and "fix" in vl):
            all_fixing_vals[val.strip()] += 1

print(f"Distinct fixing/application values: {len(all_fixing_vals)}")
for val, cnt in all_fixing_vals.most_common(40):
    print(f"  {cnt:4d}  {val!r}")

# ── Search every text field for brick
print("\n" + "=" * 60)
print("BRICK SEARCH — all text fields, all lines")
print("=" * 60)
brick_hits = []
for l in active:
    for key in ALL_TEXT:
        val = (l.get(key) or "").lower()
        if "brick" in val:
            brick_hits.append((l.get("Product"), key, l.get(key), l.get("JobID")))
            break

print(f"Lines with 'brick' anywhere: {len(brick_hits):,}")
print(f"Unique jobs: {len(set(h[3] for h in brick_hits)):,}")
print("\nSample hits:")
for prod, key, val, jid in brick_hits[:20]:
    print(f"  Job {jid} | {prod!r} | {key}: {val!r}")

# ── Check all notes fields for any install-related keywords
print("\n" + "=" * 60)
print("ALL VALUES IN InstallationNotes / Notes (sample unique values)")
print("=" * 60)
install_notes = Counter()
for l in active[:3000]:
    n = l.get("InstallationNotes") or ""
    if n.strip():
        install_notes[n.strip()[:80]] += 1
print("Top InstallationNotes values:")
for v, c in install_notes.most_common(15):
    print(f"  {c:3d}  {v!r}")

# ── TAKEDOWN summary
print("\n" + "=" * 60)
print("TAKEDOWN SUMMARY")
print("=" * 60)
td_lines   = [l for l in lines if "take down" in (l.get("Product") or "").lower().replace("takedown","take down")]
td_job_ids = set(l["JobID"] for l in td_lines if l.get("JobID"))
td_roller  = set()
for l in lines:
    if l.get("JobID") in td_job_ids and "roller" in (l.get("Product") or "").lower():
        td_roller.add(l["JobID"])

print(f"Jobs with 'Take Down' product line:          {len(td_job_ids):,}")
print(f"  — of which also have a Roller Blind line:  {len(td_roller):,}")
print(f"  — Take Down only (no roller in same job):  {len(td_job_ids - td_roller):,}")

# Show all products appearing in jobs that have a takedown
print("\nAll product types in jobs that have a Take Down line:")
td_job_products = Counter()
for l in lines:
    if l.get("JobID") in td_job_ids:
        p = l.get("Product") or ""
        if p and "take down" not in p.lower():
            td_job_products[p] += 1
for p, c in td_job_products.most_common(20):
    print(f"  {c:3d}  {p!r}")
