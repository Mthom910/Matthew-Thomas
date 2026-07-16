import urllib.request, urllib.parse, json, base64, time, csv
from collections import defaultdict

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

# ── 1. Fetch all 2026 sales appointments (not cancelled)
print("Fetching 2026 sales appointments...")
af = urllib.parse.quote(
    "Start ge 2026-01-01T00:00:00Z and Start le 2026-06-29T23:59:59Z "
    "and ActivityType eq 'Sales Appointment' and Cancelled eq false"
)
acts = fetch_all(f"/Activities?$filter={af}", "appointments")
print(f"  {len(acts):,} appointments found")

# ── 2. Collect unique contact IDs + appointment details
contact_appt_details = defaultdict(list)  # contactID -> [(date, rep_id)]
for a in acts:
    cid = a.get("ContactID")
    if not cid:
        continue
    date   = (a.get("Start") or "")[:10]
    rep_id = a.get("RepresentativeID")
    contact_appt_details[cid].append((date, rep_id))

contact_ids = list(contact_appt_details.keys())
print(f"  {len(contact_ids):,} unique contacts with appointments")

# ── 3. Fetch all confirmed orders (stage_job_order) for 2026 to check conversion
print("Fetching 2026 confirmed orders...")
jf = urllib.parse.quote(
    "JobDate ge 2026-01-01T00:00:00Z and JobDate le 2026-06-29T23:59:59Z "
    "and Stage eq 'stage_job_order'"
)
confirmed_jobs = fetch_all(f"/Jobs?$filter={jf}", "confirmed jobs")
print(f"  {len(confirmed_jobs):,} confirmed job records")

# Build set of ContactIDs that have at least one confirmed order
converted_contacts = set()
contact_order_info = {}  # contactID -> {'order_date': ..., 'job_ref': ...}
for j in confirmed_jobs:
    cid = j.get("ContactID")
    if not cid:
        continue
    converted_contacts.add(cid)
    # Keep the most recent order per contact
    order_date = (j.get("JobDate") or "")[:10]
    ref = j.get("Reference", "")
    if cid not in contact_order_info or order_date > contact_order_info[cid]["order_date"]:
        contact_order_info[cid] = {"order_date": order_date, "job_ref": ref}

print(f"  {len(converted_contacts):,} unique contacts with a confirmed order in 2026")

# ── 4. Batch-fetch contacts
print("Fetching contact details...")
CHUNK = 20
contacts = {}
for i in range(0, len(contact_ids), CHUNK):
    chunk = contact_ids[i:i+CHUNK]
    fstr = urllib.parse.quote(" or ".join(f"ID eq {c}" for c in chunk))
    try:
        data = _get(f"/Contacts?$filter={fstr}&$top={CHUNK*2}")
        for c in data.get("value", []):
            contacts[c["ID"]] = c
    except Exception as e:
        print(f"  Warning: chunk {i//CHUNK+1} failed: {e}")
    if i % 500 == 0:
        print(f"  contacts {min(i+CHUNK, len(contact_ids)):,}/{len(contact_ids):,}...", flush=True)
print(f"  {len(contacts):,} contact records fetched")

# ── 5. Fetch rep names
print("Fetching users...")
users_data = fetch_all("/Users", "users")
user_map = {u["ID"]: (u.get("FullName") or f"{u.get('FirstName','')} {u.get('LastName','')}".strip()) for u in users_data}

# ── 6. Write CSV — one row per appointment
out_file = "appointment_customers_2026.csv"
rows_written = 0
with open(out_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["First Name", "Last Name", "Full Name", "Mobile", "Email",
                     "Appointment Date", "Sales Rep", "Total Appointments 2026",
                     "Converted to Order", "Order Date", "Job Reference"])
    for cid, appt_list in sorted(contact_appt_details.items(), key=lambda x: x[1][0][0]):
        c = contacts.get(cid, {})
        first  = c.get("FirstName") or ""
        last   = c.get("LastName")  or ""
        name   = f"{first} {last}".strip() or f"Contact {cid}"
        mobile = c.get("Mobile") or ""
        email  = c.get("Email")  or ""
        converted = cid in converted_contacts
        order_info = contact_order_info.get(cid, {})
        order_date = order_info.get("order_date", "")
        job_ref    = order_info.get("job_ref", "")
        for date, rep_id in sorted(appt_list):
            rep = user_map.get(rep_id, "")
            writer.writerow([first, last, name, mobile, email, date, rep,
                             len(appt_list),
                             "Yes" if converted else "No",
                             order_date, job_ref])
            rows_written += 1

print(f"\n>> {out_file} saved — {rows_written:,} rows")

# ── 7. Write deduplicated version — one row per customer
out_dedup = "appointment_customers_2026_unique.csv"
with open(out_dedup, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["First Name", "Last Name", "Full Name", "Mobile", "Email",
                     "First Appt Date", "Last Appt Date", "Total Appointments 2026",
                     "Sales Rep (last appt)",
                     "Converted to Order", "Order Date", "Job Reference"])
    for cid, appt_list in sorted(contact_appt_details.items(), key=lambda x: x[1][0][0]):
        c = contacts.get(cid, {})
        first  = c.get("FirstName") or ""
        last   = c.get("LastName")  or ""
        name   = f"{first} {last}".strip() or f"Contact {cid}"
        mobile = c.get("Mobile") or ""
        email  = c.get("Email")  or ""
        sorted_appts = sorted(appt_list)
        first_date = sorted_appts[0][0]
        last_date  = sorted_appts[-1][0]
        last_rep   = user_map.get(sorted_appts[-1][1], "")
        converted  = cid in converted_contacts
        order_info = contact_order_info.get(cid, {})
        writer.writerow([first, last, name, mobile, email,
                         first_date, last_date, len(appt_list), last_rep,
                         "Yes" if converted else "No",
                         order_info.get("order_date", ""),
                         order_info.get("job_ref", "")])

converted_count = sum(1 for cid in contact_appt_details if cid in converted_contacts)
not_converted   = len(contact_appt_details) - converted_count
conv_rate       = converted_count / len(contact_appt_details) * 100 if contact_appt_details else 0

print(f">> {out_dedup} saved — {len(contact_appt_details):,} unique customers")
print(f"\n=== CONVERSION SUMMARY ===")
print(f"Total customers with appointment: {len(contact_appt_details):,}")
print(f"Converted to order:               {converted_count:,} ({conv_rate:.1f}%)")
print(f"Did not convert:                  {not_converted:,} ({100-conv_rate:.1f}%)")
