"""
How many jobs had an 'Other - Disposal' job line, whether those jobs also
contained a roller blind product, and how many of those jobs also had a
'Take Down' line.

'Other - Disposal' = JobLine with Location == 'Other' (case-insens) and
Product == 'Disposal' (this is how Insyte composes the on-screen label:
"<Location> - <Product>"). All-time, no date filter (disposal/take-down
lines are rare - a few hundred total - so the full history is used).
"""
import urllib.request, urllib.parse, json, base64, time
from collections import Counter

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
        except Exception:
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

EXCL_STATUS = {"status_job_line_cancelled"}

# ── 1. All Disposal lines, all time ──────────────────────────
print("Fetching Disposal lines...")
disp_lines = fetch_all("/JobLines?$filter=" + urllib.parse.quote("contains(Product,'Dispos')"), "disposal")
other_disp_lines = [l for l in disp_lines
                     if (l.get("Location") or "").strip().lower() == "other"
                     and l.get("Status") not in EXCL_STATUS]
other_disp_job_ids = set(l["JobID"] for l in other_disp_lines if l.get("JobID"))
print(f"\n'Other - Disposal' lines (Location='Other', Product contains 'Dispos', not cancelled): {len(other_disp_lines)}")
print(f"Unique jobs with an 'Other - Disposal' line: {len(other_disp_job_ids)}")

# ── 2. Take Down lines, all time ─────────────────────────────
print("\nFetching Take Down lines...")
td_lines = fetch_all("/JobLines?$filter=" + urllib.parse.quote("contains(Product,'Take Down')"), "take down")
td_lines = [l for l in td_lines if l.get("Status") not in EXCL_STATUS]
td_job_ids = set(l["JobID"] for l in td_lines if l.get("JobID"))
print(f"Take Down lines (not cancelled): {len(td_lines)}  |  unique jobs: {len(td_job_ids)}")

jobs_with_both_disposal_and_takedown = other_disp_job_ids & td_job_ids
print(f"\nOf the 'Other - Disposal' jobs, {len(jobs_with_both_disposal_and_takedown)} also had a Take Down line")

# ── 3. Pull every JobLine for the disposal jobs, to check for roller blinds ──
print("\nFetching all JobLines for the disposal jobs (to check for roller blinds)...")
job_id_list = list(other_disp_job_ids)
CHUNK = 20
all_lines_for_disp_jobs = []
for i in range(0, len(job_id_list), CHUNK):
    chunk = job_id_list[i:i+CHUNK]
    fstr = urllib.parse.quote(" or ".join(f"JobID eq {c}" for c in chunk))
    data = _get(f"/JobLines?$filter={fstr}&$top=1000")
    all_lines_for_disp_jobs.extend(data.get("value", []))
    print(f"  {min(i+CHUNK, len(job_id_list))}/{len(job_id_list)} jobs queried...", flush=True)

by_job = {}
for l in all_lines_for_disp_jobs:
    jid = l.get("JobID")
    if jid is None: continue
    by_job.setdefault(jid, []).append(l)

roller_jobs = set()
for jid, lines in by_job.items():
    for l in lines:
        if l.get("Status") in EXCL_STATUS: continue
        if "roller" in (l.get("Product") or "").lower():
            roller_jobs.add(jid)
            break

print(f"\nOf the {len(other_disp_job_ids)} 'Other - Disposal' jobs, {len(roller_jobs)} also contained a Roller Blind product line")

roller_and_takedown = roller_jobs & jobs_with_both_disposal_and_takedown
print(f"Jobs with Other-Disposal AND Roller Blind AND Take Down: {len(roller_and_takedown)}")

# ── 4. Job completion status/date (Jobs.Status + Jobs.CloseDate) ──
# HandoverDate is unused (always null on this data). CloseDate is only set
# once Status flips to 'status_job_closed' - that's the completion date.
print("\nFetching job completion dates (Status/CloseDate)...")
job_details = {}
for i in range(0, len(job_id_list), CHUNK):
    chunk = job_id_list[i:i+CHUNK]
    fstr = urllib.parse.quote(" or ".join(f"ID eq {c}" for c in chunk))
    data = _get(f"/Jobs?$filter={fstr}&$top={CHUNK*2}")
    for j in data.get("value", []):
        job_details[j["ID"]] = j

completed = [jid for jid in other_disp_job_ids if job_details.get(jid, {}).get("Status") == "status_job_closed"]
open_jobs = [jid for jid in other_disp_job_ids if job_details.get(jid, {}).get("Status") != "status_job_closed"]
print(f"Completed (status_job_closed, has CloseDate): {len(completed)}")
print(f"Still open (no CloseDate yet):                {len(open_jobs)}")

# ── Summary ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Jobs with an 'Other - Disposal' line:                 {len(other_disp_job_ids)}")
print(f"  ...of which also had a Roller Blind product:        {len(roller_jobs)}")
print(f"  ...of which also had a Take Down line:              {len(jobs_with_both_disposal_and_takedown)}")
print(f"  ...of which had BOTH Roller Blind AND Take Down:    {len(roller_and_takedown)}")
print(f"  ...completed (job closed):                          {len(completed)}")
print(f"  ...still open:                                      {len(open_jobs)}")

rows = []
for jid in sorted(other_disp_job_ids):
    j = job_details.get(jid, {})
    rows.append({
        "job_id": jid,
        "reference": j.get("Reference"),
        "status": j.get("Status"),
        "close_date": j.get("CloseDate"),
        "job_date": j.get("JobDate"),
        "has_roller_blind": jid in roller_jobs,
        "has_take_down": jid in jobs_with_both_disposal_and_takedown,
    })

with open("disposal_takedown_analysis.json", "w") as f:
    json.dump({
        "counts": {
            "other_disposal_jobs": len(other_disp_job_ids),
            "with_roller": len(roller_jobs),
            "with_takedown": len(jobs_with_both_disposal_and_takedown),
            "with_roller_and_takedown": len(roller_and_takedown),
            "completed": len(completed),
            "still_open": len(open_jobs),
        },
        "jobs": rows,
    }, f, indent=2)
print("\n>> disposal_takedown_analysis.json saved")

import csv
with open("disposal_takedown_analysis.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(">> disposal_takedown_analysis.csv saved")
