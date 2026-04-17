"""
Page 3 — Pipeline / CRM.

Features:
  - Filter by stage and client
  - Inline stage / value / notes editing per project
  - Summary by stage (project count + total value)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import backend.db as db

# ------------------------------------------------------------------
# Auth guard
# ------------------------------------------------------------------

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

# ------------------------------------------------------------------
# Page setup
# ------------------------------------------------------------------

st.title("Pipeline / CRM")

STAGES = ["Prospect", "Active", "On Hold", "Completed"]

# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load_pipeline():
    return db.get_pipeline()

@st.cache_data(ttl=300)
def _load_projects():
    return db.get_projects()

@st.cache_data(ttl=300)
def _load_clients():
    return db.get_clients()

pipeline   = _load_pipeline()
all_projects = _load_projects()
all_clients  = _load_clients()
client_names = sorted({c.name for c in all_clients})

# Ensure every active project has a pipeline entry
pipeline_project_ids = {row["project_id"] for row in pipeline}
for proj in all_projects:
    if proj.id not in pipeline_project_ids:
        db.upsert_pipeline(proj.id, stage=proj.status if proj.status in STAGES else "Prospect")

# Reload after any upserts
pipeline = db.get_pipeline()

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

col1, col2 = st.columns(2)
with col1:
    stage_filter = st.selectbox("Stage", ["All"] + STAGES)
with col2:
    client_filter = st.selectbox("Client", ["All"] + client_names)

filtered = pipeline
if stage_filter != "All":
    filtered = [r for r in filtered if r["stage"] == stage_filter]
if client_filter != "All":
    filtered = [r for r in filtered if r["client_name"] == client_filter]

# ------------------------------------------------------------------
# Summary by stage
# ------------------------------------------------------------------

st.subheader("Summary")
summary_cols = st.columns(len(STAGES))
for col, stage in zip(summary_cols, STAGES):
    rows_for_stage = [r for r in pipeline if r["stage"] == stage]
    total_value = sum(r["value"] or 0 for r in rows_for_stage)
    col.metric(stage, f"{len(rows_for_stage)} projects", f"€{total_value:,.0f}")

st.divider()

# ------------------------------------------------------------------
# Pipeline table with inline editing
# ------------------------------------------------------------------

st.subheader(f"Projects ({len(filtered)})")

if not filtered:
    st.info("No projects match the selected filters.")
    st.stop()

for row in filtered:
    header = f"**{row['project_name']}** — {row['client_name']}  `{row['stage']}`"
    with st.expander(header, expanded=False):
        with st.form(f"pipeline_{row['id']}"):
            col_stage, col_value = st.columns(2)
            with col_stage:
                stage_idx = STAGES.index(row["stage"]) if row["stage"] in STAGES else 0
                new_stage = st.selectbox("Stage", STAGES, index=stage_idx,
                                         key=f"stg_{row['id']}")
            with col_value:
                new_value = st.number_input("Estimated value (€)", min_value=0.0,
                                            value=float(row["value"] or 0),
                                            step=1000.0, key=f"val_{row['id']}")
            new_notes = st.text_area("Notes", value=row["notes"] or "",
                                     height=70, key=f"notes_{row['id']}")
            saved = st.form_submit_button("Save")

        if saved:
            db.upsert_pipeline(row["project_id"], new_stage, new_value, new_notes)
            st.success("Updated.")
            st.cache_data.clear()
            st.rerun()

        st.caption(f"Last updated: {row['updated_at']}")
