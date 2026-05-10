"""
Page 3 — Pipeline / CRM.

Features:
  - Summary metrics by stage
  - Inline editing via st.data_editor (Stage, Value, Budget min/est/max, Probability %, Notes)
  - Filter by stage, client, country, and client type
  - Probability-weighted forecast totals
  - Date entered pipeline + date entered current stage (auto-updated on stage change)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import backend.db as db

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

st.title("Pipeline / CRM")

STAGES = ["Prospect", "Active", "On Hold", "Completed"]
CLIENT_TYPES = ["managed", "external", "internal"]

# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load_pipeline():
    return db.get_pipeline()

@st.cache_data(ttl=300)
def _load_projects():
    return db.get_projects()

pipeline     = _load_pipeline()
all_projects = _load_projects()

# Ensure every project has a pipeline entry
pipeline_project_ids = {row["project_id"] for row in pipeline}
for proj in all_projects:
    if proj.id not in pipeline_project_ids:
        db.upsert_pipeline(proj.id, stage=proj.status if proj.status in STAGES else "Prospect")

pipeline = db.get_pipeline()

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

client_names        = sorted({r["client_name"] for r in pipeline})
all_client_countries = sorted({r["country"] for r in pipeline if r.get("country")})
all_opp_countries   = sorted({r["opportunity_country"] for r in pipeline if r.get("opportunity_country")})

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    stage_filter = st.selectbox("Stage", ["All"] + STAGES)
with col2:
    client_filter = st.selectbox("Client", ["All"] + client_names)
with col3:
    opp_country_filter = st.multiselect("Opportunity Country", all_opp_countries, key="pl_opp_country_filter")
with col4:
    country_filter = st.multiselect("Client Country", all_client_countries, key="pl_country_filter")
with col5:
    type_filter = st.multiselect(
        "Client Type", CLIENT_TYPES, key="pl_type_filter",
        help="e.g. exclude 'internal' to see only billable pipeline",
    )

filtered = pipeline
if stage_filter != "All":
    filtered = [r for r in filtered if r["stage"] == stage_filter]
if client_filter != "All":
    filtered = [r for r in filtered if r["client_name"] == client_filter]
if opp_country_filter:
    filtered = [r for r in filtered if r.get("opportunity_country") in opp_country_filter]
if country_filter:
    filtered = [r for r in filtered if r.get("country") in country_filter]
if type_filter:
    filtered = [r for r in filtered if r.get("client_type") in type_filter]

# ------------------------------------------------------------------
# Summary metrics by stage
# ------------------------------------------------------------------

st.subheader("Summary by Stage")
summary_cols = st.columns(len(STAGES))
for col, stage in zip(summary_cols, STAGES):
    rows_for_stage = [r for r in pipeline if r["stage"] == stage]
    total_value = sum(r["value"] or 0 for r in rows_for_stage)
    col.metric(stage, f"{len(rows_for_stage)} projects", f"€{total_value:,.0f}")

st.divider()

# ------------------------------------------------------------------
# Probability-weighted forecast
# ------------------------------------------------------------------

prob_rows = [r for r in filtered if r.get("probability") and (
    r.get("budget_min") or r.get("budget_est") or r.get("budget_max"))]
if prob_rows:
    fw_min = sum((r["budget_min"] or 0) * (r["probability"] or 0) for r in prob_rows)
    fw_est = sum((r["budget_est"] or 0) * (r["probability"] or 0) for r in prob_rows)
    fw_max = sum((r["budget_max"] or 0) * (r["probability"] or 0) for r in prob_rows)
    fc1, fc2, fc3 = st.columns(3)
    fc1.metric("Weighted Min (€)", f"{fw_min:,.0f}")
    fc2.metric("Weighted Est (€)", f"{fw_est:,.0f}")
    fc3.metric("Weighted Max (€)", f"{fw_max:,.0f}")
    st.divider()

# ------------------------------------------------------------------
# Inline editing table
# ------------------------------------------------------------------

st.subheader(f"Pipeline Table ({len(filtered)} projects)")

if not filtered:
    st.info("No projects match the selected filters.")
    st.stop()

# Build editable DataFrame — internal IDs kept for save round-trip
editor_rows = [
    {
        "_id":                  r["id"],
        "_project_id":          r["project_id"],
        "Client":               r["client_name"],
        "Client Country":       r.get("country") or "—",
        "Opportunity Country":  r.get("opportunity_country") or "",
        "Project":              r["project_name"],
        "Stage":                r["stage"],
        "Value (€)":            float(r["value"] or 0),
        "Min (€)":              float(r.get("budget_min") or 0),
        "Est (€)":              float(r.get("budget_est") or 0),
        "Max (€)":              float(r.get("budget_max") or 0),
        "Prob %":               round(float(r.get("probability") or 0.5) * 100, 0),
        "Notes":                r["notes"] or "",
        "In Pipeline":          (r.get("date_entered_pipeline") or "")[:10],
        "In Stage Since":       (r.get("date_entered_stage") or "")[:10],
        "Updated":              (r["updated_at"] or "")[:10],
    }
    for r in filtered
]
editor_df = pd.DataFrame(editor_rows)

edited = st.data_editor(
    editor_df,
    use_container_width=True,
    hide_index=True,
    disabled=["_id", "_project_id", "Client", "Client Country", "Project",
              "In Pipeline", "In Stage Since", "Updated"],
    column_config={
        "_id":                  st.column_config.NumberColumn("_id",              width="small"),
        "_project_id":          st.column_config.NumberColumn("_project_id",      width="small"),
        "Client Country":       st.column_config.TextColumn("Client Country",     width="small"),
        "Opportunity Country":  st.column_config.TextColumn("Opportunity Country",width="small"),
        "Stage":                st.column_config.SelectboxColumn("Stage", options=STAGES, width="medium"),
        "Value (€)":            st.column_config.NumberColumn("Value (€)",        min_value=0, step=1000, format="%.0f"),
        "Min (€)":              st.column_config.NumberColumn("Min (€)",          min_value=0, step=1000, format="%.0f"),
        "Est (€)":              st.column_config.NumberColumn("Est (€)",          min_value=0, step=1000, format="%.0f"),
        "Max (€)":              st.column_config.NumberColumn("Max (€)",          min_value=0, step=1000, format="%.0f"),
        "Prob %":               st.column_config.NumberColumn("Prob %",           min_value=0, max_value=100, step=5, format="%.0f%%"),
        "Notes":                st.column_config.TextColumn("Notes",              width="large"),
        "In Pipeline":          st.column_config.TextColumn("In Pipeline",        width="small"),
        "In Stage Since":       st.column_config.TextColumn("In Stage Since",     width="small"),
        "Updated":              st.column_config.TextColumn("Updated",            width="small"),
    },
    key="pipeline_editor",
)

# Live subtotals (reflect unsaved edits in the editor)
st.caption(f"Filtered totals — {len(edited)} project(s)")
_tc = st.columns(4)
_tc[0].metric("Value (€)",  f"{edited['Value (€)'].sum():,.0f}")
_tc[1].metric("Min (€)",    f"{edited['Min (€)'].sum():,.0f}")
_tc[2].metric("Est (€)",    f"{edited['Est (€)'].sum():,.0f}")
_tc[3].metric("Max (€)",    f"{edited['Max (€)'].sum():,.0f}")

if st.button("Save changes", type="primary"):
    changed = 0
    for _, row in edited.iterrows():
        orig = next((r for r in filtered if r["id"] == int(row["_id"])), None)
        if orig is None:
            continue
        db.upsert_pipeline(
            int(row["_project_id"]),
            str(row["Stage"]),
            float(row["Value (€)"] or 0),
            str(row["Notes"] or ""),
            budget_min=float(row["Min (€)"] or 0),
            budget_est=float(row["Est (€)"] or 0),
            budget_max=float(row["Max (€)"] or 0),
            probability=float(row["Prob %"] or 50) / 100.0,
            opportunity_country=str(row["Opportunity Country"] or ""),
        )
        changed += 1
    st.success(f"Saved {changed} pipeline row(s).")
    st.cache_data.clear()
    st.rerun()
