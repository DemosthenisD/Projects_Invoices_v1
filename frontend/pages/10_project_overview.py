"""
Page 9 — Project Overview.

Full project-level financial summary across all clients with multi-select filters
and Excel export.
"""
import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import backend.db as db

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

st.title("Project Overview")

# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------

@st.cache_data(ttl=120)
def _load():
    return db.get_all_projects_overview()

rows = _load()

if not rows:
    st.info("No projects found.")
    st.stop()

df = pd.DataFrame(rows)

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

col1, col2, col3 = st.columns(3)

all_clients = sorted(df["client"].unique())
all_statuses = sorted(df["status"].unique())
all_sources = sorted(df["project_source"].unique())

with col1:
    client_sel = st.multiselect("Client", all_clients)
with col2:
    status_sel = st.multiselect("Status", all_statuses, default=["Active"])
with col3:
    source_sel = st.multiselect("Source", all_sources)

filtered = df.copy()
if client_sel:
    filtered = filtered[filtered["client"].isin(client_sel)]
if status_sel:
    filtered = filtered[filtered["status"].isin(status_sel)]
if source_sel:
    filtered = filtered[filtered["project_source"].isin(source_sel)]

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Projects", len(filtered))
c2.metric("Budget (€)", f"{filtered['budget'].sum():,.0f}")
c3.metric("Billable (€)", f"{filtered['billable_charges'].sum():,.0f}")
c4.metric("Invoiced (€)", f"{filtered['invoiced'].sum():,.0f}")

st.divider()

# ------------------------------------------------------------------
# Table
# ------------------------------------------------------------------

display = filtered[[
    "client", "project", "project_source", "code_count",
    "budget", "billable_charges", "write_offs", "net_charges", "invoiced", "remaining",
    "status",
]].rename(columns={
    "client":           "Client",
    "project":          "Project",
    "project_source":   "Source",
    "code_count":       "Codes",
    "budget":           "Budget (€)",
    "billable_charges": "Billable (€)",
    "write_offs":       "Write-offs (€)",
    "net_charges":      "Net (€)",
    "invoiced":         "Invoiced (€)",
    "remaining":        "Remaining (€)",
    "status":           "Status",
})

# Format currency columns
for col in ["Budget (€)", "Billable (€)", "Write-offs (€)", "Net (€)", "Invoiced (€)", "Remaining (€)"]:
    display[col] = display[col].map(lambda x: f"{x:,.0f}" if x else "—")

st.dataframe(display, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------
# Export to Excel
# ------------------------------------------------------------------

def _build_excel(data: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    data.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()

st.download_button(
    label="Export to Excel",
    data=_build_excel(display),
    file_name="project_overview.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
