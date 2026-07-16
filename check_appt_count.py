"""Count Sales Appointments using ActivityType field."""
import urllib.request, urllib.parse, json, base64
from collections import Counter

from insyte_env import EMAIL, KEY
BASE  = "https://api.myinsyte.com.au/v2"
AUTH  = "Basic " + base64.b64encode(f"{EMAIL}:{KEY}".encode()).decode()

def _get(path):
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

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

# All ActivityType values in 2026 (sample 5000 to see variety)
print("Checking ActivityType field values...")
f = urllib.parse.quote("Start ge 2026-01-01T00:00:00Z and Start le 2026-06-27T23:59:59Z")
sample = _get(f"/Activities?$filter={f}&$top=500")
rows = sample.get("value", [])
types = Counter(a.get("ActivityType","null") for a in rows)
print("ActivityType values in first 500:")
for t,n in sorted(types.items(), key=lambda x:-x[1]):
    print(f"  {n:>5}  {repr(t)}")

# Count Sales Appointments only — 2026 H1
print("\nFetching 2026 Sales Appointments...")
fa = urllib.parse.quote("Start ge 2026-01-01T00:00:00Z and Start le 2026-06-27T23:59:59Z and ActivityType eq 'Sales Appointment'")
try:
    acts26 = fetch_all(f"/Activities?$filter={fa}", "2026 SA")
    print(f"  Total: {len(acts26):,}")
    # Exclude cancelled
    not_cancelled = [a for a in acts26 if not a.get("Cancelled")]
    print(f"  Excl. Cancelled: {len(not_cancelled):,}")
    # By status
    status_counts = Counter(a.get("Status","?") for a in acts26)
    print("  By Status:")
    for s,n in sorted(status_counts.items(), key=lambda x:-x[1]):
        print(f"    {n:>5}  {s}")
    # Weekly breakdown
    from collections import defaultdict
    by_week = defaultdict(int)
    for a in not_cancelled:
        d = (a.get("Start") or "")[:10]
        if d:
            import datetime
            dt = datetime.date.fromisoformat(d)
            wk = dt.isocalendar()[:2]
            by_week[wk] += 1
    print(f"\n  Weekly counts (non-cancelled):")
    for wk, cnt in sorted(by_week.items()):
        print(f"    Week {wk[1]:>2} ({wk[0]}): {cnt}")
except Exception as e:
    print(f"Server-side filter failed: {e}")
    print("Trying client-side filter on full pull...")
    # fallback: just show counts
