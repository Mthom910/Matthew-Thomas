"""
Insyte Web API Client
Base URL : https://api.myinsyte.com.au/v2
Auth     : HTTP Basic — email address + API key
Protocol : OData v4
"""
from __future__ import annotations

import base64
import urllib.request
import urllib.parse
import urllib.error
import json
from typing import Any


# ---------------------------------------------------------------------------
# Configuration — edit these or load from environment variables
# ---------------------------------------------------------------------------
API_BASE   = "https://api.myinsyte.com.au/v2"
from insyte_env import EMAIL as API_EMAIL, KEY as API_KEY


# ---------------------------------------------------------------------------
# Low-level HTTP helper
# ---------------------------------------------------------------------------

def _auth_header() -> str:
    token = base64.b64encode(f"{API_EMAIL}:{API_KEY}".encode()).decode()
    return f"Basic {token}"


def _request(
    path: str,
    method: str = "GET",
    body: dict | None = None,
    params: dict | None = None,
) -> Any:
    """
    Make an authenticated request to the Insyte API.
    Returns parsed JSON (dict / list) or None for 204 No Content.
    Raises RuntimeError on HTTP errors.
    """
    url = f"{API_BASE}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _auth_header())
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason} — {url}\n{body_text}") from e


def _get_all(path: str, params: dict | None = None) -> list[dict]:
    """Fetch an OData collection, following @odata.nextLink pages."""
    result = []
    url_path = path
    page_params = dict(params or {})

    while True:
        data = _request(url_path, params=page_params if page_params else None)
        values = data.get("value", data) if isinstance(data, dict) else data
        result.extend(values)
        next_link = data.get("@odata.nextLink") if isinstance(data, dict) else None
        if not next_link:
            break
        # nextLink is a full URL — extract path+query for next iteration
        parsed = urllib.parse.urlparse(next_link)
        url_path = parsed.path.replace(f"/v2/", "")
        page_params = dict(urllib.parse.parse_qsl(parsed.query))

    return result


# ---------------------------------------------------------------------------
# CRM — Contacts & Companies
# ---------------------------------------------------------------------------

class Contacts:
    @staticmethod
    def list(top: int = 100, skip: int = 0, filter_: str = "") -> list[dict]:
        p = {"$top": top, "$skip": skip}
        if filter_:
            p["$filter"] = filter_
        return _get_all("Contacts", p)

    @staticmethod
    def get(contact_id: int) -> dict:
        return _request(f"Contacts({contact_id})")

    @staticmethod
    def create(data: dict) -> dict:
        return _request("Contacts", method="POST", body=data)

    @staticmethod
    def update(contact_id: int, data: dict) -> dict:
        return _request(f"Contacts({contact_id})", method="PATCH", body=data)

    @staticmethod
    def search(name: str = "", email: str = "") -> list[dict]:
        parts = []
        if name:
            parts.append(f"contains(tolower(LastName),'{name.lower()}')")
        if email:
            parts.append(f"tolower(Email) eq '{email.lower()}'")
        return Contacts.list(filter_=" and ".join(parts))


class Companies:
    @staticmethod
    def list(top: int = 100, skip: int = 0, filter_: str = "") -> list[dict]:
        p = {"$top": top, "$skip": skip}
        if filter_:
            p["$filter"] = filter_
        return _get_all("Companies", p)

    @staticmethod
    def get(company_id: int) -> dict:
        return _request(f"Companies({company_id})")

    @staticmethod
    def create(data: dict) -> dict:
        return _request("Companies", method="POST", body=data)

    @staticmethod
    def update(company_id: int, data: dict) -> dict:
        return _request(f"Companies({company_id})", method="PATCH", body=data)


# ---------------------------------------------------------------------------
# Sales — Opportunities & Activities
# ---------------------------------------------------------------------------

class Opportunities:
    @staticmethod
    def list(top: int = 100, skip: int = 0, filter_: str = "") -> list[dict]:
        p = {"$top": top, "$skip": skip}
        if filter_:
            p["$filter"] = filter_
        return _get_all("Opportunities", p)

    @staticmethod
    def get(opp_id: int) -> dict:
        return _request(f"Opportunities({opp_id})")

    @staticmethod
    def create(data: dict) -> dict:
        return _request("Opportunities", method="POST", body=data)

    @staticmethod
    def update(opp_id: int, data: dict) -> dict:
        return _request(f"Opportunities({opp_id})", method="PATCH", body=data)

    @staticmethod
    def by_status(status: str) -> list[dict]:
        """status: Open | Won | Lost"""
        return Opportunities.list(filter_=f"Status eq '{status}'")

    @staticmethod
    def by_rep(rep_id: int) -> list[dict]:
        return Opportunities.list(filter_=f"RepresentativeID eq {rep_id}")

    @staticmethod
    def pipeline() -> list[dict]:
        """All open opportunities ordered by pipeline stage."""
        return _get_all("Opportunities", {
            "$filter": "Status eq 'Open'",
            "$orderby": "PipelineStage asc",
            "$top": 500,
        })


class Activities:
    @staticmethod
    def list(top: int = 100, skip: int = 0, filter_: str = "") -> list[dict]:
        p = {"$top": top, "$skip": skip}
        if filter_:
            p["$filter"] = filter_
        return _get_all("Activities", p)

    @staticmethod
    def get(activity_id: int) -> dict:
        return _request(f"Activities({activity_id})")

    @staticmethod
    def create(data: dict) -> dict:
        return _request("Activities", method="POST", body=data)

    @staticmethod
    def by_rep(rep_id: int, closed: bool = False) -> list[dict]:
        status_filter = "Closed eq true" if closed else "Closed eq false"
        return Activities.list(filter_=f"RepresentativeID eq {rep_id} and {status_filter}")


# ---------------------------------------------------------------------------
# Jobs & Quotes
# ---------------------------------------------------------------------------

class Jobs:
    @staticmethod
    def list(top: int = 100, skip: int = 0, filter_: str = "") -> list[dict]:
        p = {"$top": top, "$skip": skip}
        if filter_:
            p["$filter"] = filter_
        return _get_all("Jobs", p)

    @staticmethod
    def get(job_id: int) -> dict:
        return _request(f"Jobs({job_id})")

    @staticmethod
    def create(data: dict) -> dict:
        return _request("Jobs", method="POST", body=data)

    @staticmethod
    def update(job_id: int, data: dict) -> dict:
        return _request(f"Jobs({job_id})", method="PATCH", body=data)

    @staticmethod
    def by_status(status: str) -> list[dict]:
        return Jobs.list(filter_=f"Status eq '{status}'")

    @staticmethod
    def by_rep(rep_id: int) -> list[dict]:
        return Jobs.list(filter_=f"SalesRepID eq {rep_id}")


class JobLines:
    @staticmethod
    def list(job_id: int) -> list[dict]:
        return _get_all("JobLines", {"$filter": f"JobID eq {job_id}"})

    @staticmethod
    def get(line_id: int) -> dict:
        return _request(f"JobLines({line_id})")


# ---------------------------------------------------------------------------
# Invoices & Payments
# ---------------------------------------------------------------------------

class Invoices:
    @staticmethod
    def list(top: int = 100, skip: int = 0, filter_: str = "") -> list[dict]:
        p = {"$top": top, "$skip": skip}
        if filter_:
            p["$filter"] = filter_
        return _get_all("Invoices", p)

    @staticmethod
    def get(invoice_id: int) -> dict:
        return _request(f"Invoices({invoice_id})")

    @staticmethod
    def by_status(status: str) -> list[dict]:
        return Invoices.list(filter_=f"Status eq '{status}'")

    @staticmethod
    def outstanding() -> list[dict]:
        return Invoices.list(filter_="Status ne 'Paid' and CreditNote eq false", top=500)


class Payments:
    @staticmethod
    def list(top: int = 100, skip: int = 0, filter_: str = "") -> list[dict]:
        p = {"$top": top, "$skip": skip}
        if filter_:
            p["$filter"] = filter_
        return _get_all("Payments", p)

    @staticmethod
    def get(payment_id: int) -> dict:
        return _request(f"Payments({payment_id})")


# ---------------------------------------------------------------------------
# Reference / Lookup Data
# ---------------------------------------------------------------------------

class Users:
    @staticmethod
    def list() -> list[dict]:
        return _get_all("Users")

    @staticmethod
    def get(user_id: int) -> dict:
        return _request(f"Users({user_id})")


class BusinessUnits:
    @staticmethod
    def list() -> list[dict]:
        return _get_all("BusinessUnits")


class LeadSources:
    @staticmethod
    def list() -> list[dict]:
        return _get_all("LeadSources")


class OutcomeReasons:
    @staticmethod
    def list() -> list[dict]:
        return _get_all("OutcomeReasons")


# ---------------------------------------------------------------------------
# Dashboard helpers — aggregations useful for a performance dashboard
# ---------------------------------------------------------------------------

class Dashboard:
    """Pre-built queries for a sales / CRM performance dashboard."""

    @staticmethod
    def sales_pipeline_summary() -> dict:
        """Count and expected revenue by pipeline stage."""
        opps = Opportunities.pipeline()
        stages: dict[str, dict] = {}
        for o in opps:
            stage = o.get("PipelineStage", "Unknown")
            if stage not in stages:
                stages[stage] = {"count": 0, "expected_revenue": 0.0}
            stages[stage]["count"] += 1
            stages[stage]["expected_revenue"] += float(o.get("ExpectedRevenue") or 0)
        return stages

    @staticmethod
    def rep_performance(rep_id: int) -> dict:
        """Jobs, opportunities, and activity counts for a sales rep."""
        jobs  = Jobs.by_rep(rep_id)
        opps  = Opportunities.by_rep(rep_id)
        acts  = Activities.by_rep(rep_id, closed=False)

        won   = [o for o in opps if o.get("Status") == "Won"]
        lost  = [o for o in opps if o.get("Status") == "Lost"]
        open_ = [o for o in opps if o.get("Status") == "Open"]

        return {
            "rep_id": rep_id,
            "jobs_total": len(jobs),
            "opportunities": {
                "open": len(open_),
                "won":  len(won),
                "lost": len(lost),
                "win_rate": round(len(won) / max(len(won) + len(lost), 1) * 100, 1),
            },
            "open_activities": len(acts),
            "pipeline_value": sum(float(o.get("ExpectedRevenue") or 0) for o in open_),
        }

    @staticmethod
    def outstanding_invoices_summary() -> dict:
        """Total outstanding invoice amounts."""
        invoices = Invoices.outstanding()
        total = sum(float(inv.get("Amount") or inv.get("TotalAmount") or 0) for inv in invoices)
        return {
            "count": len(invoices),
            "total_outstanding": round(total, 2),
            "invoices": invoices,
        }

    @staticmethod
    def recent_contacts(top: int = 20) -> list[dict]:
        return _get_all("Contacts", {"$top": top, "$orderby": "CreatedOn desc"})

    @staticmethod
    def recent_opportunities(top: int = 20) -> list[dict]:
        return _get_all("Opportunities", {"$top": top, "$orderby": "CreatedOn desc"})


# ---------------------------------------------------------------------------
# Quick connection test
# ---------------------------------------------------------------------------

def test_connection() -> bool:
    """Verify credentials work. Returns True on success."""
    try:
        result = _request("Users", params={"$top": 1})
        print("Connection OK —", result)
        return True
    except RuntimeError as e:
        print("Connection FAILED:", e)
        return False


if __name__ == "__main__":
    test_connection()
