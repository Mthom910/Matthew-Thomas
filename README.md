# Insyte API Connection

Python client for the Insyte Web API (OData v4, Basic auth).

## Files

| File | Purpose |
|------|---------|
| `insyte_client.py` | API client — all endpoints + dashboard helpers |

## Quick start

```python
from insyte_client import Contacts, Opportunities, Dashboard, test_connection

# Verify credentials
test_connection()

# --- CRM ---
contacts = Contacts.list(top=50)
contact  = Contacts.get(123)
results  = Contacts.search(name="Smith", email="")

companies = Companies.list()

# --- Sales pipeline ---
pipeline   = Opportunities.pipeline()          # all open opps, ordered by stage
won        = Opportunities.by_status("Won")
rep_opps   = Opportunities.by_rep(rep_id=7)

activities = Activities.by_rep(rep_id=7)

# --- Jobs ---
jobs      = Jobs.by_rep(rep_id=7)
job_lines = JobLines.list(job_id=1001)

# --- Invoices & Payments ---
outstanding = Invoices.outstanding()
payments    = Payments.list(top=100)

# --- Reference data ---
users          = Users.list()
business_units = BusinessUnits.list()
lead_sources   = LeadSources.list()

# --- Dashboard summaries ---
pipeline_summary = Dashboard.sales_pipeline_summary()
rep_stats        = Dashboard.rep_performance(rep_id=7)
invoice_summary  = Dashboard.outstanding_invoices_summary()
recent_contacts  = Dashboard.recent_contacts(top=20)
```

## Authentication

Credentials are loaded from environment variables via the shared `insyte_env.py` module,
which reads `INSYTE_EMAIL` / `INSYTE_KEY` from your environment or a local `.env` file
(not committed to git — copy `.env.example` to `.env` and fill in your own values).

```python
from insyte_env import EMAIL, KEY
```

The `insyte_*.html` dashboards prompt for credentials in-browser on first use (or via
their Config panel) and cache them in that browser's `localStorage` — the API key is
never written into the HTML source.

## OData filtering

All `.list()` methods accept an OData `filter_` string:

```python
# Opportunities created after a date
Opportunities.list(filter_="LeadDate gt 2025-01-01T00:00:00Z")

# Jobs with a specific status
Jobs.list(filter_="Status eq 'Completed'")

# Contacts in a company
Contacts.list(filter_="CompanyID eq 42")
```

## Entity reference (key entities)

| Entity | Key fields |
|--------|-----------|
| Contacts | FirstName, LastName, Email, Mobile, CompanyID |
| Companies | Name, Phone, Email, AccountType |
| Opportunities | Status, PipelineStage, ExpectedRevenue, RepresentativeID |
| Jobs | Status, Stage, SalesRepID, JobType |
| Activities | Subject, Start, End, Status, RepresentativeID |
| Invoices | InvoiceNo, Status, DueDate, JobID |
| Payments | Date, Amount, Type, ContactID |

## API notes

- **Preview API** — may change without notice
- **Pagination** — `_get_all()` follows `@odata.nextLink` automatically
- **Rate limits** — not documented; use `$top`/`$skip` for large datasets
- **OData docs** — `https://api.myinsyte.com.au/v2/$metadata` (requires auth)
