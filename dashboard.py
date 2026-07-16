"""
Insyte CRM & Performance Dashboard
Run with: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Import our API client
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from insyte_client import (
    Contacts, Companies, Opportunities, Activities,
    Jobs, Invoices, Payments, Users, Dashboard, _request
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Insyte Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card {
        background: #f0f2f6;
        border-radius: 8px;
        padding: 16px;
        margin: 4px 0;
    }
    .stMetric { background: #f0f2f6; border-radius: 8px; padding: 12px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — navigation
# ---------------------------------------------------------------------------
st.sidebar.title("Insyte Dashboard")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["Overview", "CRM — Contacts", "CRM — Companies", "Sales Pipeline",
     "Jobs & Quotes", "Invoices & Payments", "Rep Performance"],
)
st.sidebar.markdown("---")
st.sidebar.caption("Connected to api.myinsyte.com.au/v2")

# ---------------------------------------------------------------------------
# Cached data loaders (5-min cache)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_users():
    return Users.list()

@st.cache_data(ttl=300)
def load_contacts(top=500):
    return Contacts.list(top=top)

@st.cache_data(ttl=300)
def load_companies(top=500):
    return Companies.list(top=top)

@st.cache_data(ttl=300)
def load_opportunities(top=500):
    return Opportunities.list(top=top)

@st.cache_data(ttl=300)
def load_activities(top=500):
    return Activities.list(top=top)

@st.cache_data(ttl=300)
def load_jobs(top=500):
    return Jobs.list(top=top)

@st.cache_data(ttl=300)
def load_invoices(top=500):
    return Invoices.list(top=top)

@st.cache_data(ttl=300)
def load_payments(top=200):
    return Payments.list(top=top)

def safe_df(records: list) -> pd.DataFrame:
    """Convert list of dicts to DataFrame, returning empty DF on failure."""
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)

# ---------------------------------------------------------------------------
# Helper — user lookup map
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def user_map():
    users = load_users()
    return {u.get("ID") or u.get("Id"): u.get("FullName", "Unknown") for u in users}


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------
if page == "Overview":
    st.title("Dashboard Overview")
    st.caption(f"Last refreshed: {datetime.now().strftime('%d %b %Y %H:%M')}")

    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("Loading data..."):
        opps     = safe_df(load_opportunities())
        jobs     = safe_df(load_jobs())
        invoices = safe_df(load_invoices())
        contacts = safe_df(load_contacts())

    # KPI row
    col1, col2, col3, col4, col5 = st.columns(5)

    open_opps = opps[opps.get("Status", pd.Series()) == "Open"] if not opps.empty and "Status" in opps else pd.DataFrame()
    won_opps  = opps[opps["Status"] == "Won"] if not opps.empty and "Status" in opps else pd.DataFrame()

    col1.metric("Total Contacts",    len(contacts) if not contacts.empty else "–")
    col2.metric("Open Opportunities", len(open_opps))
    col3.metric("Won Opportunities",  len(won_opps))
    col4.metric("Total Jobs",         len(jobs) if not jobs.empty else "–")
    col5.metric("Total Invoices",     len(invoices) if not invoices.empty else "–")

    st.markdown("---")

    # Pipeline by stage chart
    if not opps.empty and "PipelineStage" in opps.columns:
        st.subheader("Pipeline by Stage")
        pipeline_open = opps[opps["Status"] == "Open"] if "Status" in opps.columns else opps
        stage_counts  = pipeline_open.groupby("PipelineStage").size().reset_index(name="Count")
        fig = px.bar(stage_counts, x="PipelineStage", y="Count",
                     color="Count", color_continuous_scale="Blues",
                     labels={"PipelineStage": "Stage", "Count": "Opportunities"})
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)

    # Opportunity status breakdown
    if not opps.empty and "Status" in opps.columns:
        with col_left:
            st.subheader("Opportunity Status")
            status_counts = opps["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig2 = px.pie(status_counts, names="Status", values="Count",
                          color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_layout(height=300)
            st.plotly_chart(fig2, use_container_width=True)

    # Job status breakdown
    if not jobs.empty and "Status" in jobs.columns:
        with col_right:
            st.subheader("Job Status")
            job_status = jobs["Status"].value_counts().reset_index()
            job_status.columns = ["Status", "Count"]
            fig3 = px.pie(job_status, names="Status", values="Count",
                          color_discrete_sequence=px.colors.qualitative.Pastel)
            fig3.update_layout(height=300)
            st.plotly_chart(fig3, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: CRM — Contacts
# ---------------------------------------------------------------------------
elif page == "CRM — Contacts":
    st.title("Contacts")

    with st.spinner("Loading contacts..."):
        contacts = safe_df(load_contacts())

    if contacts.empty:
        st.warning("No contacts found.")
    else:
        # Search
        search = st.text_input("Search by name or email", placeholder="e.g. Smith")
        df = contacts.copy()
        if search:
            mask = df.apply(lambda r: search.lower() in str(r).lower(), axis=1)
            df   = df[mask]

        st.caption(f"Showing {len(df)} of {len(contacts)} contacts")

        # Display key columns
        display_cols = [c for c in ["FirstName","LastName","Email","Mobile","WorkPhone","JobTitle"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        # Export
        st.download_button(
            "Download CSV",
            df[display_cols].to_csv(index=False),
            file_name="contacts.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Page: CRM — Companies
# ---------------------------------------------------------------------------
elif page == "CRM — Companies":
    st.title("Companies")

    with st.spinner("Loading companies..."):
        companies = safe_df(load_companies())

    if companies.empty:
        st.warning("No companies found.")
    else:
        search = st.text_input("Search by name", placeholder="e.g. Acme")
        df = companies.copy()
        if search:
            mask = df.apply(lambda r: search.lower() in str(r).lower(), axis=1)
            df   = df[mask]

        st.caption(f"Showing {len(df)} of {len(companies)} companies")
        display_cols = [c for c in ["Name","Phone","Email","AccountType","CreditLimit","AccountOnHold"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        st.download_button(
            "Download CSV",
            df[display_cols].to_csv(index=False),
            file_name="companies.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Page: Sales Pipeline
# ---------------------------------------------------------------------------
elif page == "Sales Pipeline":
    st.title("Sales Pipeline")

    with st.spinner("Loading opportunities..."):
        opps = safe_df(load_opportunities())

    if opps.empty:
        st.warning("No opportunities found.")
    else:
        # Filters
        col1, col2 = st.columns(2)
        statuses = ["All"] + sorted(opps["Status"].dropna().unique().tolist()) if "Status" in opps.columns else ["All"]
        status_filter = col1.selectbox("Status", statuses)

        stages = ["All"] + sorted(opps["PipelineStage"].dropna().unique().tolist()) if "PipelineStage" in opps.columns else ["All"]
        stage_filter  = col2.selectbox("Pipeline Stage", stages)

        df = opps.copy()
        if status_filter != "All" and "Status" in df.columns:
            df = df[df["Status"] == status_filter]
        if stage_filter != "All" and "PipelineStage" in df.columns:
            df = df[df["PipelineStage"] == stage_filter]

        # KPIs
        k1, k2, k3 = st.columns(3)
        k1.metric("Count", len(df))
        total_rev = df["ExpectedRevenue"].apply(pd.to_numeric, errors="coerce").sum() if "ExpectedRevenue" in df.columns else 0
        k2.metric("Total Expected Revenue", f"${total_rev:,.0f}")
        won_df   = opps[opps["Status"] == "Won"] if "Status" in opps.columns else pd.DataFrame()
        lost_df  = opps[opps["Status"] == "Lost"] if "Status" in opps.columns else pd.DataFrame()
        win_rate = len(won_df) / max(len(won_df) + len(lost_df), 1) * 100
        k3.metric("Overall Win Rate", f"{win_rate:.1f}%")

        st.markdown("---")

        # Pipeline funnel
        if "PipelineStage" in df.columns:
            stage_rev = df.groupby("PipelineStage").agg(
                Count=("PipelineStage", "count"),
                Revenue=("ExpectedRevenue", lambda x: pd.to_numeric(x, errors="coerce").sum()),
            ).reset_index()
            fig = px.funnel(stage_rev, x="Count", y="PipelineStage",
                            color="Revenue", title="Pipeline Funnel")
            st.plotly_chart(fig, use_container_width=True)

        display_cols = [c for c in ["Description","Status","PipelineStage","ExpectedRevenue","CloseDate"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Page: Jobs & Quotes
# ---------------------------------------------------------------------------
elif page == "Jobs & Quotes":
    st.title("Jobs & Quotes")

    with st.spinner("Loading jobs..."):
        jobs = safe_df(load_jobs())

    if jobs.empty:
        st.warning("No jobs found.")
    else:
        col1, col2 = st.columns(2)
        statuses = ["All"] + sorted(jobs["Status"].dropna().unique().tolist()) if "Status" in jobs.columns else ["All"]
        status_filter = col1.selectbox("Status", statuses)
        types    = ["All"] + sorted(jobs["JobType"].dropna().unique().tolist()) if "JobType" in jobs.columns else ["All"]
        type_filter   = col2.selectbox("Job Type", types)

        df = jobs.copy()
        if status_filter != "All" and "Status" in df.columns:
            df = df[df["Status"] == status_filter]
        if type_filter != "All" and "JobType" in df.columns:
            df = df[df["JobType"] == type_filter]

        st.caption(f"{len(df)} jobs")
        display_cols = [c for c in ["Reference","Status","Stage","JobType","JobDate","HandoverDate","SalesRepID"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        st.download_button(
            "Download CSV",
            df[display_cols].to_csv(index=False),
            file_name="jobs.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Page: Invoices & Payments
# ---------------------------------------------------------------------------
elif page == "Invoices & Payments":
    st.title("Invoices & Payments")

    with st.spinner("Loading financial data..."):
        invoices = safe_df(load_invoices())
        payments = safe_df(load_payments())

    if not invoices.empty:
        # Invoice status breakdown
        col1, col2 = st.columns([2, 1])
        with col1:
            if "Status" in invoices.columns:
                inv_status = invoices["Status"].value_counts().reset_index()
                inv_status.columns = ["Status", "Count"]
                fig = px.bar(inv_status, x="Status", y="Count", title="Invoices by Status",
                             color="Status")
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Summary")
            total_inv = len(invoices)
            st.metric("Total Invoices", total_inv)
            if "Status" in invoices.columns:
                paid   = len(invoices[invoices["Status"] == "Paid"])
                unpaid = total_inv - paid
                st.metric("Paid", paid)
                st.metric("Outstanding", unpaid)

        # Filter invoices
        status_filter = st.selectbox(
            "Filter by status",
            ["All"] + sorted(invoices["Status"].dropna().unique().tolist()) if "Status" in invoices.columns else ["All"]
        )
        df = invoices if status_filter == "All" else invoices[invoices["Status"] == status_filter]
        display_cols = [c for c in ["InvoiceNo","InvoiceDate","DueDate","Status","JobID"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Recent Payments")
    if not payments.empty:
        display_cols = [c for c in ["Date","Amount","Type","Status","ReceiptNumber"] if c in payments.columns]
        st.dataframe(payments[display_cols].head(50), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Page: Rep Performance
# ---------------------------------------------------------------------------
elif page == "Rep Performance":
    st.title("Sales Rep Performance")

    with st.spinner("Loading data..."):
        users = load_users()
        opps  = safe_df(load_opportunities())
        jobs  = safe_df(load_jobs())
        acts  = safe_df(load_activities())

    if not users:
        st.warning("No users found.")
    else:
        # Build per-rep summary
        rows = []
        rep_field = "RepresentativeID"
        for u in users:
            uid  = u.get("ID") or u.get("Id")
            name = u.get("FullName", f"User {uid}")

            u_opps = opps[opps[rep_field] == uid] if not opps.empty and rep_field in opps.columns else pd.DataFrame()
            u_jobs = jobs[jobs["SalesRepID"] == uid] if not jobs.empty and "SalesRepID" in jobs.columns else pd.DataFrame()
            u_acts = acts[acts[rep_field] == uid] if not acts.empty and rep_field in acts.columns else pd.DataFrame()

            won   = len(u_opps[u_opps["Status"] == "Won"])  if not u_opps.empty and "Status" in u_opps.columns else 0
            lost  = len(u_opps[u_opps["Status"] == "Lost"]) if not u_opps.empty and "Status" in u_opps.columns else 0
            open_ = len(u_opps[u_opps["Status"] == "Open"]) if not u_opps.empty and "Status" in u_opps.columns else 0
            rev   = u_opps[u_opps["Status"] == "Open"]["ExpectedRevenue"].apply(pd.to_numeric, errors="coerce").sum() if not u_opps.empty and "ExpectedRevenue" in u_opps.columns else 0

            rows.append({
                "Rep":              name,
                "Open Opps":        open_,
                "Won":              won,
                "Lost":             lost,
                "Win Rate %":       round(won / max(won + lost, 1) * 100, 1),
                "Pipeline Value":   round(float(rev), 2),
                "Jobs":             len(u_jobs),
                "Activities Open":  len(u_acts[~u_acts["Closed"].astype(bool)]) if not u_acts.empty and "Closed" in u_acts.columns else len(u_acts),
            })

        df_reps = pd.DataFrame(rows).sort_values("Pipeline Value", ascending=False)

        # Chart: pipeline value per rep
        fig = px.bar(df_reps, x="Rep", y="Pipeline Value", color="Win Rate %",
                     color_continuous_scale="RdYlGn",
                     title="Pipeline Value by Rep")
        st.plotly_chart(fig, use_container_width=True)

        # Win rate chart
        fig2 = px.bar(df_reps, x="Rep", y="Win Rate %", title="Win Rate by Rep",
                      color="Win Rate %", color_continuous_scale="RdYlGn", range_color=[0, 100])
        st.plotly_chart(fig2, use_container_width=True)

        # Full table
        st.subheader("Rep Scorecard")
        st.dataframe(df_reps, use_container_width=True, hide_index=True)

        st.download_button(
            "Download Rep Scorecard",
            df_reps.to_csv(index=False),
            file_name="rep_scorecard.csv",
            mime="text/csv",
        )
