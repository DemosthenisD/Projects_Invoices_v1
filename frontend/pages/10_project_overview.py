"""
Page 8 — Project Overview.

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
years: list[int] = [cy - i for i in range(4)]

# ------------------------------------------------------------------
# Filters — row 1: Client, Status, Source
# ------------------------------------------------------------------

all_clients  = sorted(df["client"].unique())
all_statuses = sorted(df["status"].unique())
all_sources  = sorted(df["project_source"].unique())
all_types    = sorted(df["client_type"].unique())
all_groups   = sorted({g for cell in df["groups_with_hours"] for g in cell.split(",") if g})
all_consults = sorted({c for cell in df["consultants_with_hours"] for c in cell.split(",") if c})

col1, col2, col3 = st.columns(3)
with col1:
    client_sel = st.multiselect("Client", all_clients)
with col2:
    status_sel = st.multiselect("Status", all_statuses, default=["Active"])
with col3:
    source_sel = st.multiselect("Source / Office", all_sources)

col4, col5, col6 = st.columns(3)
with col4:
    type_sel = st.multiselect("Type", all_types)
with col5:
    group_sel = st.multiselect("Consultant Group", all_groups)
with col6:
    consult_sel = st.multiselect("Consultant", all_consults)

filtered = df.copy()
if client_sel:
    filtered = filtered[filtered["client"].isin(client_sel)]
if status_sel:
    filtered = filtered[filtered["status"].isin(status_sel)]
if source_sel:
    filtered = filtered[filtered["project_source"].isin(source_sel)]
if type_sel:
    filtered = filtered[filtered["client_type"].isin(type_sel)]
if group_sel:
    filtered = filtered[filtered["groups_with_hours"].apply(
        lambda v: any(g in v.split(",") for g in group_sel)
    )]
if consult_sel:
    filtered = filtered[filtered["consultants_with_hours"].apply(
        lambda v: any(c in v.split(",") for c in consult_sel)
    )]

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Projects",     len(filtered))
c2.metric("Budget (€)",   f"{filtered['budget'].sum():,.0f}")
c3.metric("Billable (€)", f"{filtered['billable_charges'].sum():,.0f}")
c4.metric("Invoiced (€)", f"{filtered['invoiced'].sum():,.0f}")

st.divider()

# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

_MONEY_FMT = "{:,.0f}"
_MONEY2_FMT = "{:,.2f}"

def _style_money(df_in: pd.DataFrame, cols: list[str], dec: int = 0) -> "pd.io.formats.style.Styler":
    fmt = _MONEY_FMT if dec == 0 else _MONEY2_FMT
    return df_in.style.format({c: fmt for c in cols if c in df_in.columns}, na_rep="—")

def _totals_row(display: pd.DataFrame, label_col: str, label: str, num_cols: list[str]) -> pd.DataFrame:
    row = {c: display[c].sum() if c in num_cols else ("" if c != label_col else label)
           for c in display.columns}
    return pd.concat([display, pd.DataFrame([row])], ignore_index=True)

# ------------------------------------------------------------------
# View toggle
# ------------------------------------------------------------------

view = st.radio("View", ["Summary", "Year-by-Year"], horizontal=True, label_visibility="collapsed")

_NUM_COLS = ["Budget (€)", "Billable (€)", "Write-offs (€)", "Net (€)", "Invoiced (€)", "Remaining (€)"]

if view == "Summary":
    display = filtered[[
        "client", "project", "project_source", "client_type", "code_count",
        "budget", "billable_charges", "write_offs", "net_charges", "invoiced", "remaining", "status",
    ]].rename(columns={
        "client":           "Client",
        "project":          "Project",
        "project_source":   "Source",
        "client_type":      "Type",
        "code_count":       "Codes",
        "budget":           "Budget (€)",
        "billable_charges": "Billable (€)",
        "write_offs":       "Write-offs (€)",
        "net_charges":      "Net (€)",
        "invoiced":         "Invoiced (€)",
        "remaining":        "Remaining (€)",
        "status":           "Status",
    })

    display = _totals_row(display, "Client", "TOTAL", _NUM_COLS)
    st.dataframe(
        _style_money(display, _NUM_COLS),
        use_container_width=True, hide_index=True,
    )

else:
    if f"invoiced_{years[0]}" not in filtered.columns:
        st.warning(
            "Year-by-year columns not available — restart the Streamlit server and revisit this page."
        )
        st.stop()

    base_cols   = ["client", "project", "status"]
    base_rename = {"client": "Client", "project": "Project", "status": "Status"}

    for prefix, total_col, label in [
        ("invoiced",  "invoiced",         "Invoiced (€)"),
        ("charges",   "billable_charges", "Time Charges (€)"),
        ("writeoffs", "write_offs",       "Write-offs (€)"),
    ]:
        yr_cols = {f"{prefix}_{yr}": str(yr) for yr in years}
        tbl = filtered[base_cols + [total_col] + list(yr_cols)].copy().rename(columns={
            **base_rename,
            total_col: f"Total",
            **yr_cols,
        })
        num_cols = ["Total"] + [str(yr) for yr in years]
        tbl = _totals_row(tbl, "Client", "TOTAL", num_cols)
        st.subheader(label)
        st.dataframe(_style_money(tbl, num_cols), use_container_width=True, hide_index=True)
        st.divider()

# ------------------------------------------------------------------
# Export to Excel
# ------------------------------------------------------------------

def _build_excel(data: pd.DataFrame, yrs: list[int]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_cols = {
            "client": "Client", "project": "Project", "project_source": "Source",
            "client_type": "Type", "code_count": "Codes", "budget": "Budget (€)",
            "billable_charges": "Billable (€)", "write_offs": "Write-offs (€)",
            "net_charges": "Net (€)", "invoiced": "Invoiced (€)",
            "remaining": "Remaining (€)", "status": "Status",
        }
        data[list(summary_cols)].rename(columns=summary_cols).to_excel(
            writer, sheet_name="Summary", index=False
        )
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
