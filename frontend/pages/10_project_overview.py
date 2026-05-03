"""
Page 9 — Project Overview.

Full project-level financial summary across all clients with multi-select filters,
year-by-year breakdown, and Excel export.
"""
import sys
import os
import io
from datetime import date

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

@st.cache_data(ttl=60)
def _load():
    return db.get_all_projects_overview()

rows = _load()

if not rows:
    st.info("No projects found.")
    st.stop()

df = pd.DataFrame(rows)
cy = date.today().year
years: list[int] = [cy - i for i in range(4)]   # e.g. [2026, 2025, 2024, 2023]

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

col1, col2, col3 = st.columns(3)

all_clients  = sorted(df["client"].unique())
all_statuses = sorted(df["status"].unique())
all_sources  = sorted(df["project_source"].unique())

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
c1.metric("Projects",    len(filtered))
c2.metric("Budget (€)",  f"{filtered['budget'].sum():,.0f}")
c3.metric("Billable (€)",f"{filtered['billable_charges'].sum():,.0f}")
c4.metric("Invoiced (€)",f"{filtered['invoiced'].sum():,.0f}")

st.divider()

# ------------------------------------------------------------------
# View toggle
# ------------------------------------------------------------------

view = st.radio("View", ["Summary", "Year-by-Year"], horizontal=True, label_visibility="collapsed")

def _fmt(x):
    return f"{x:,.0f}" if x else "—"

if view == "Summary":
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
    for col in ["Budget (€)", "Billable (€)", "Write-offs (€)", "Net (€)", "Invoiced (€)", "Remaining (€)"]:
        display[col] = display[col].map(_fmt)

    st.dataframe(display, use_container_width=True, hide_index=True)

else:
    if f"invoiced_{years[0]}" not in filtered.columns:
        st.warning(
            "Year-by-year columns are not available in the cached data. "
            "Please **restart the Streamlit server** to reload the updated database module, then revisit this page."
        )
        st.stop()

    # Year-by-year view: one section per metric group
    base_cols = ["client", "project", "status"]
    base_rename = {"client": "Client", "project": "Project", "status": "Status"}

    for metric, label, prefix in [
        ("invoiced",    "Invoiced (€)",          "invoiced"),
        ("charges",     "Time Charges (€)",       "charges"),
        ("write_offs",  "Write-offs (€)",         "writeoffs"),
    ]:
        # Total column + per-year columns
        yr_cols = {f"{prefix}_{yr}": str(yr) for yr in years}
        cols_needed = base_cols + [metric] + list(yr_cols.keys())
        # write_offs total key differs from prefix
        if metric == "write_offs":
            total_col = "write_offs"
        elif metric == "invoiced":
            total_col = "invoiced"
        else:
            total_col = "billable_charges"

        cols_needed = base_cols + [total_col] + list(yr_cols.keys())
        tbl = filtered[cols_needed].copy().rename(columns={
            **base_rename,
            total_col: f"Total — {label}",
            **{k: v for k, v in yr_cols.items()},
        })
        for col in [f"Total — {label}"] + list(yr_cols.values()):
            tbl[col] = tbl[col].map(_fmt)

        st.subheader(label)
        st.dataframe(tbl, use_container_width=True, hide_index=True)
        st.divider()

# ------------------------------------------------------------------
# Export to Excel  (always exports both views)
# ------------------------------------------------------------------

def _build_excel(data: pd.DataFrame, yrs: list[int]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # Summary sheet
        summary_cols = {
            "client": "Client", "project": "Project", "project_source": "Source",
            "code_count": "Codes", "budget": "Budget (€)",
            "billable_charges": "Billable (€)", "write_offs": "Write-offs (€)",
            "net_charges": "Net (€)", "invoiced": "Invoiced (€)",
            "remaining": "Remaining (€)", "status": "Status",
        }
        data[list(summary_cols)].rename(columns=summary_cols).to_excel(
            writer, sheet_name="Summary", index=False
        )

        # Year-by-year sheet
        yby_cols = {"client": "Client", "project": "Project", "status": "Status"}
        for yr in yrs:
            yby_cols[f"invoiced_{yr}"]  = f"Invoiced {yr}"
            yby_cols[f"charges_{yr}"]   = f"Charges {yr}"
            yby_cols[f"writeoffs_{yr}"] = f"Write-offs {yr}"
        data[[c for c in yby_cols if c in data.columns]].rename(columns=yby_cols).to_excel(
            writer, sheet_name="Year-by-Year", index=False
        )
    return buf.getvalue()

st.download_button(
    label="Export to Excel",
    data=_build_excel(filtered, years),
    file_name="project_overview.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
