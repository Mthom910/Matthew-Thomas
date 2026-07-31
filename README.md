# Appointment Health Dashboard — Insyte integration

`appointment_health_dashboard.html` shows fill rate, no-show rate, wait-to-book,
a weekly diary strip, a consultant/region breakdown, an 8-week fill-rate trend,
and cancellation/no-show reasons — for **Victory Curtains & Blinds** sales
appointments, pulled live from Insyte.

Data flow: `refresh_appointment_data.py` (run on a schedule) → `insyte_appointment_data.json`
→ the dashboard `fetch()`s that file on load. There is no live polling from the
browser and no backend server — the refresh script just writes a static file.

## Setup

1. Copy `.env.example` to `.env` and fill in your Insyte credentials:
   ```
   INSYTE_BASE_URL=https://api.myinsyte.com.au/v2
   INSYTE_EMAIL=you@example.com
   INSYTE_API_KEY=your-api-key
   ```
   `.env` is read by the script at startup and is never committed or hardcoded.
2. Install the one dependency (if not already present):
   ```bash
   pip install requests
   ```

## Running it

```bash
python refresh_appointment_data.py
```

This fetches Sales Appointment + Calendar Note activity data for the last
`TREND_WEEKS` (8) weeks plus the current week, and writes `insyte_appointment_data.json`
next to the HTML file. Open `appointment_health_dashboard.html` (via a local
static file server, not `file://`, so `fetch()` works — e.g. `python -m http.server`)
and it will load that JSON automatically. If the file is missing or the fetch
fails, the dashboard falls back to its original sample data and shows why in
the banner under the title.

## Scheduling (Windows Task Scheduler)

Run every 15–30 minutes via `schtasks`:

```bash
schtasks /Create /SC MINUTE /MO 20 /TN "InsyteAppointmentRefresh" /TR "python C:\Users\Matthew.Thomas\Dashboards\refresh_appointment_data.py" /ST 07:00
```

Or set it up interactively: Task Scheduler → Create Task → Trigger: "Repeat
task every 20 minutes, for a duration of Indefinitely" → Action: Start a
program → `python.exe` with argument `C:\Users\Matthew.Thomas\Dashboards\refresh_appointment_data.py`.

The dashboard's status banner flags the feed as **stale** if `generatedAt` is
more than 60 minutes old, so a missed/failed refresh run is visible at a glance.

## What you still need to provide / confirm

- **Wynstan credentials.** The Insyte account currently in use only has
  visibility into Victory business units (confirmed by paginating all 327
  users and recent Jobs — zero Wynstan records anywhere). Wynstan is very
  likely a separate Insyte tenant. Wynstan continues to show the original
  sample data until you provide a base URL + email/API key for it. Once you
  do, the ingestion script can be extended to pull both brands.
- **Consultant list is unfiltered.** Every `Representative` who has a real
  "Sales Appointment" booking is included as-is — no name-based exclusion of
  test/inactive accounts (e.g. names tagged "(Tech)", "Tester"). If any of
  these shouldn't appear on the dashboard, tell me which and I'll add an
  exclusion list.
- **On-time rate is not tracked.** Insyte's `Activities` entity only has
  scheduled `Start`/`End` — no actual-arrival field exists anywhere in the
  API. The dashboard now shows "N/A — Not tracked in Insyte" for this KPI
  rather than a fabricated number. If this needs to be real, it has to come
  from a different system (e.g. a check-in app) or a new Insyte field.

## Assumptions baked into the pipeline (documented so they're easy to revisit)

- **No-show definition**: an appointment whose Insyte `Status` never got
  closed out (`activity_status_open`) after its scheduled `End` time has
  passed. This was confirmed as the correct real-world signal — Insyte has
  no explicit no-show flag.
- **Slot capacity** comes from `Calendar Note` activities, where staff log
  free-text rosters like `"2 @ 9 - 12, 2 @ 12 - 3"` (slot counts per time
  window) or `"off"` / `"leave"` (day off). Roughly **40% of Calendar Notes
  parse cleanly** into a capacity signal — the rest are either genuine day-off
  markers or unrelated notes that got logged under the same activity type:
  area/product restrictions ("no outdoor", "do not book in CBD"), finance
  admin ("payments confirmed", "awaiting payment" — the single largest
  unparsed bucket), meeting notes, and an ambiguous `"N @ locked"` convention
  whose meaning I didn't want to guess at. Days/consultants with no parseable
  note are **excluded from the fill-rate denominator** rather than guessed —
  the actual coverage for whatever period was last pulled is in
  `insyte_appointment_data.json` → `dataQuality.capacityNoteCoverage`, and
  shown live in the dashboard's status banner. If you can tell me what
  `"N @ locked"` means, or whether "payments confirmed"-style notes should be
  filtered out entirely, coverage (and therefore fill-rate accuracy) improves.
- **Diary grid resolution**: the dashboard's diary is a fixed 3-slots/day
  (morning / midday / afternoon) × 5-day layout. Real appointments and roster
  windows are bucketed into those 3 windows rather than shown at their true
  (often half-hourly) resolution, to match the existing UI without redesigning
  it. A day marked "off" in Calendar Note has no distinct visual state in the
  current UI, so it renders as "open" (lost capacity) rather than "unavailable"
  — a possible future UI enhancement.
- **KPI deltas** are calendar month-to-date vs. the same elapsed-day range in
  the previous month, matching the dashboard's existing "vs last MTD" label.
- **Reasons chart** now shows real cancellation/no-show reason categories
  (e.g. "Cancelled by customer", "No-show (not cancelled in advance)",
  "Rescheduled") derived from Insyte's free-text `CancelledReason` field,
  replacing the original sample's fabricated categories ("Understaffed slot",
  etc.) which have no equivalent real data source.

## Files

- `refresh_appointment_data.py` — ingestion/aggregation script (run manually or on schedule)
- `.env.example` — credential template (copy to `.env`, which is gitignored/local-only)
- `insyte_appointment_data.json` — generated output the dashboard fetches (regenerated each run)
- `appointment_health_dashboard.html` — the dashboard itself (visual design unchanged)

---

# Revenue Management Initiative Dashboard

`insyte_revenue_initiative.html` analyses the 35–40% discount bracket initiative:
consultants get a tiered commission premium (on top of the base rate) for
writing $5K+ jobs discounted 35–40%, to test whether the incentive increases
conversion in that value tier without eroding margin too much.

Data flow: `refresh_initiative_data.py` → `insyte_initiative_data.json` → the
dashboard fetches that file and does **all aggregation client-side in JS**.
This is a deliberate difference from the category/appointment dashboards:
the Config panel lets you change Min Job Value, commission rates, and the
YTD date ranges and hit **Save & Load** to instantly recompute every KPI,
table and chart from the same raw records — no re-run of the Python script
needed. **Refresh** re-fetches the JSON file (useful after a scheduled
Python run); it does not call Insyte from the browser, and the API key is
never embedded in the HTML.

## Running it

```bash
python refresh_initiative_data.py
python -m http.server 8843
```

Then open `http://localhost:8843/insyte_revenue_initiative.html`.

## Key assumptions baked into the analysis

- **Won = order intake, not installed revenue.** A job counts as "won" the
  moment it receives its **first confirmed payment** (a deposit) — via
  `JobPaymentAllocations` → `Payment.Date`, `Status = status_payment_confirmed`,
  `Type = type_payment_payment` — not when Insyte's internal `Stage`/`OrderDate`
  fields flip, which track manufacturing/dispatch and can lag the actual sale
  by weeks. We deliberately don't filter on `Payment.IsDeposit` — it's `null`
  on ~55% of Payment records tenant-wide, so relying on it would silently
  drop about half of all real deposits; the earliest confirmed payment on a
  job is treated as its deposit. **Lost**/**Quote** (for jobs with no
  confirmed payment yet) map to `stage_job_lost` / `stage_job_quote`.
  Revisions are deduped by base job reference (e.g. `J0108483-1` superseded
  by `J0108483-2`), same logic as `refresh_category_data.py`. The dashboard's
  data-quality footer reports how many Insyte "order" stage jobs have no
  matching confirmed payment in the pulled window (i.e. would have been
  counted as won under the old Stage-based definition, but aren't here).
- **Quote Pipeline table** buckets each base job reference into its YTD
  window by the *first* sub-job's date (when it entered the pipeline), but
  shows its *current* stage — so a job quoted in June and won in August
  still counts as "confirmed" in the June pipeline snapshot.
- **Tiered initiative commission**: the 35–40% bracket is split into four
  equal 1.25-point sub-bands, each with its own configurable premium rate
  (defaults 7% / 6% / 5% / 4%, highest at the low end of the bracket). This
  is a simplification of "give consultants a bigger commission the more of
  the 35–40% band they use" — adjust the four tier-rate fields in Config if
  the real policy differs.
- **2025 commission figures are retroactive**: the initiative only exists in
  2026, so 2025 "commission" numbers apply the *current* base+tier rules to
  2025's actual jobs purely for a like-for-like comparison, not real 2025
  payouts.
- **Opportunity Pipeline chart is expected to render empty.** Insyte's
  `Opportunities.ExpectedRevenue` field is populated on only ~14 records
  tenant-wide (confirmed by querying the live API), so it can't drive a
  meaningful $5K+ pipeline view. The Quote Pipeline table (built from Jobs,
  not Opportunities) is the reliable source for pipeline volume — this is a
  data-quality limitation in the source system, not a bug.
- **Lead funnel / waterfall** derive "leads" from appointments using a
  configurable Lead→Appointment rate (default 83%) and Lead Cost (default
  $135) — Insyte has no native "lead" entity, so this is an estimate, not a
  measured figure.

## Files

- `refresh_initiative_data.py` — ingestion script; pulls ~19 months of
  JobLines, Sales Appointment activities, and Opportunities, and writes
  near-raw canonical records (aggregation happens in the browser, not here)
- `insyte_initiative_data.json` — generated output (regenerated each run)
- `insyte_revenue_initiative.html` — the dashboard
