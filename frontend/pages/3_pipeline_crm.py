"""
Page 3 — Pipeline / CRM.

Features:
  - Tabular summary of all pipeline entries (SP5a)
  - Filter by stage and client
  - Inline stage / value / budget / probability editing per project (SP5b)
  - Summary metrics by stage
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

pipeline     = _load_pipeline()
all_projects = _load_projects()
all_clients  = _load_clients()
client_names = sorted({c.name for c in all_clients})

# Ensure every project has a pipeline entry
pipeline_project_ids = {row["project_id"] for row in pipeline}
for proj in all_projects:
    if proj.id not in pipeline_project_ids:
        db.upsert_pipeline(proj.id, stage=proj.status if proj.status in STAGES else "Prospect")

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
# Summary metrics by stage
# ------------------------------------------------------------------

st.subheader("Summary by Stage")
summary_cols = st.columns(len(STAGES))
for col, stage in zip(summary_cols, STAGES):
    rows_for_stage = [r for r in pipeline if r["stage"] == stage]
    total_value = sum(r["value"] or 0 for r in rows_for_stage)
    col.metric(stage, f"{len(rows_for_stage)} projects", f"€{total_value:,.0f}")

# ------------------------------------------------------------------
# Tabular overview (SP5a)
# ------------------------------------------------------------------

st.divider()
st.subheader(f"Pipeline Table ({len(filtered)} projects)")

if filtered:
    table_data = [
        {
            "Client":      r["client_name"],
            "Project":     r["project_name"],
            "Stage":       r["stage"],
            "Value (€)":   f"{r['value']:,.0f}" if r["value"] else "—",
            "Min (€)":     f"{r['budget_min']:,.0f}" if r.get("budget_min") else "—",
            "Est (€)":     f"{r['budget_est']:,.0f}" if r.get("budget_est") else "—",
            "Max (€)":     f"{r['budget_max']:,.0f}" if r.get("budget_max") else "—",
            "Probability": f"{r['probability']*100:.0f}%" if r.get("probability") is not None else "—",
            "Notes":       (r["notes"] or "")[:60],
            "Updated":     r["updated_at"][:10] if r.get("updated_at") else "",
        }
        for r in filtered
    ]
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    # Probability-weighted forecast totals
    prob_rows = [r for r in filtered if r.get("probability") and (
        r.get("budget_min") or r.get("budget_est") or r.get("budget_max"))]
    if prob_rows:
        st.caption("Probability-weighted forecast (for projects with budget fields set):")
        fw_min = sum((r["budget_min"] or 0) * (r["probability"] or 0) for r in prob_rows)
        fw_est = sum((r["budget_est"] or 0) * (r["probability"] or 0) for r in prob_rows)
        fw_max = sum((r["budget_max"] or 0) * (r["probability"] or 0) for r in prob_rows)
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("Weighted Min (€)", f"{fw_min:,.0f}")
        fc2.metric("Weighted Est (€)", f"{fw_est:,.0f}")
        fc3.metric("Weighted Max (€)", f"{fw_max:,.0f}")

st.divider()

# ------------------------------------------------------------------
# Per-project editing
# ------------------------------------------------------------------

st.subheader("Edit Projects")

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
                new_value = st.number_input("Contracted value (€)", min_value=0.0,
                                            value=float(row["value"] or 0),
                                            step=1000.0, key=f"val_{row['id']}")

            st.markdown("**Budget forecast**")
            bc1, bc2, bc3, bc4 = st.columns(4)
            new_bmin = bc1.number_input("Min (€)", min_value=0.0,
                                        value=float(row.get("budget_min") or 0),
                                        step=1000.0, key=f"bmin_{row['id']}")
            new_best = bc2.number_input("Est (€)", min_value=0.0,
                                        value=float(row.get("budget_est") or 0),
                                        step=1000.0, key=f"best_{row['id']}")
            new_bmax = bc3.number_input("Max (€)", min_value=0.0,
                                        value=float(row.get("budget_max") or 0),
                                        step=1000.0, key=f"bmax_{row['id']}")
            new_prob = bc4.number_input("Probability (%)", min_value=0.0, max_value=100.0,
                                        value=float((row.get("probability") or 0.5) * 100),
                                        step=5.0, key=f"prob_{row['id']}")

            new_notes = st.text_area("Notes", value=row["notes"] or "",
                                     height=70, key=f"notes_{row['id']}")
            saved = st.form_submit_button("Save")

        if saved:
            db.upsert_pipeline(
                row["project_id"], new_stage, new_value, new_notes,
                budget_min=new_bmin, budget_est=new_best, budget_max=new_bmax,
                probability=new_prob / 100.0,
            )
            st.success("Updated.")
            st.cache_data.clear()
            st.rerun()

        st.caption(f"Last updated: {row['updated_at']}")
