"""
Page 3 — Pipeline / CRM.

Features:
  - Add Prospect form (minimal fields — no client/project record required)
  - Summary metrics by stage
  - Inline editing via st.data_editor for all entries (linked + prospects)
  - Convert Prospect to Project workflow
  - Delete prospect
  - Filter by stage, client/company, country, client type
  - Probability-weighted forecast totals
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import backend.db as db
from shared.ui import require_auth
from datetime import datetime

require_auth()

st.title("Pipeline / CRM")

STAGES = ["Prospect", "Active", "On Hold", "Completed"]
CLIENT_TYPES = ["managed", "external", "internal"]

# ------------------------------------------------------------------
# Add Prospect form
# ------------------------------------------------------------------

with st.expander("➕ Add Prospect", expanded=False):
    with st.form("add_prospect_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        ap_company  = col1.text_input("Company name *")
        ap_opp      = col2.text_input("Opportunity name", placeholder="e.g. IFRS17 Phase 2")
        ap_desc     = st.text_input("Description / notes on opportunity")
        col3, col4, col5 = st.columns(3)
        ap_country  = col3.text_input("Country")
        ap_stage    = col3.selectbox("Stage", STAGES, index=0)
        ap_min      = col4.number_input("Budget Min (€)", min_value=0.0, step=1000.0)
        ap_est      = col4.number_input("Budget Est (€)", min_value=0.0, step=1000.0)
        ap_max      = col5.number_input("Budget Max (€)", min_value=0.0, step=1000.0)
        ap_prob     = col5.slider("Probability %", 0, 100, 50, step=5)
        ap_submitted = st.form_submit_button("Add Prospect", type="primary")
    if ap_submitted:
        if not ap_company.strip():
            st.error("Company name is required.")
        else:
            db.add_prospect(
                company_name=ap_company.strip(),
                prospect_name=ap_opp.strip(),
                description=ap_desc.strip(),
                country=ap_country.strip(),
                stage=ap_stage,
                budget_min=ap_min,
                budget_est=ap_est,
                budget_max=ap_max,
                probability=ap_prob / 100.0,
            )
            st.success(f"Prospect '{ap_company.strip()}' added.")
            st.cache_data.clear()
            st.rerun()

# ------------------------------------------------------------------
# Load data + ensure every linked project has a pipeline entry
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load_pipeline():
    return db.get_pipeline()

pipeline = _load_pipeline()

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Filters — cascade: each dropdown narrows the next
# ------------------------------------------------------------------

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    stage_filter = st.selectbox("Stage", ["All"] + STAGES)

# Stage cascade → available clients
_after_stage = pipeline if stage_filter == "All" else [r for r in pipeline if r["stage"] == stage_filter]
all_display_clients = sorted({r["display_client"] for r in _after_stage if r.get("display_client")})
with col2:
    client_filter = st.selectbox("Client / Company", ["All"] + all_display_clients)

# Stage + client cascade → available countries
_after_client = _after_stage if client_filter == "All" else [r for r in _after_stage if r.get("display_client") == client_filter]
all_opp_countries    = sorted({r["opportunity_country"] for r in _after_client if r.get("opportunity_country")})
all_client_countries = sorted({r["country"] for r in _after_client if r.get("country")})
with col3:
    opp_country_filter = st.multiselect("Opportunity Country", all_opp_countries, key="pl_opp_country",
                                         default=[v for v in st.session_state.get("pl_opp_country", []) if v in all_opp_countries])
with col4:
    country_filter = st.multiselect("Client Country", all_client_countries, key="pl_country",
                                     default=[v for v in st.session_state.get("pl_country", []) if v in all_client_countries])
with col5:
    type_filter = st.multiselect("Client Type", CLIENT_TYPES, key="pl_type",
                                  help="Only applies to linked (non-prospect) entries")

filtered = pipeline
if stage_filter != "All":
    filtered = [r for r in filtered if r["stage"] == stage_filter]
if client_filter != "All":
    filtered = [r for r in filtered if r.get("display_client") == client_filter]
if opp_country_filter:
    filtered = [r for r in filtered if r.get("opportunity_country") in opp_country_filter]
if country_filter:
    filtered = [r for r in filtered if r.get("country") in country_filter]
if type_filter:
    filtered = [r for r in filtered if not r.get("is_prospect") and r.get("client_type") in type_filter]

# ------------------------------------------------------------------
# Summary metrics by stage
# ------------------------------------------------------------------

st.subheader("Summary by Stage")
summary_cols = st.columns(len(STAGES))
for col, stage in zip(summary_cols, STAGES):
    rows_for_stage = [r for r in pipeline if r["stage"] == stage]
    total_value = sum(r["value"] or 0 for r in rows_for_stage)
    label = f"{len(rows_for_stage)} entries"
    col.metric(stage, label, f"€{total_value:,.0f}")

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

st.subheader(f"Pipeline Table ({len(filtered)} entries)")

if not filtered:
    st.info("No entries match the selected filters.")
else:
    editor_rows = [
        {
            "_id":               r["id"],
            "_project_id":       r["project_id"] or "",
            "_is_prospect":      bool(r.get("is_prospect")),
            "Client / Company":  r.get("display_client") or "",
            "Country":           r.get("country") or "—",
            "Opp. Country":      r.get("opportunity_country") or "",
            "Project / Opp.":    r.get("display_project") or "",
            "Stage":             r["stage"],
            "Value (€)":         float(r["value"] or 0),
            "Min (€)":           float(r.get("budget_min") or 0),
            "Est (€)":           float(r.get("budget_est") or 0),
            "Max (€)":           float(r.get("budget_max") or 0),
            "Prob %":            round(float(r.get("probability") or 0.5) * 100, 0),
            "Notes":             r["notes"] or "",
            "In Pipeline":       (r.get("date_entered_pipeline") or "")[:10],
            "In Stage Since":    (r.get("date_entered_stage") or "")[:10],
        }
        for r in filtered
    ]
    editor_df = pd.DataFrame(editor_rows)

    edited = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        disabled=["_id", "_project_id", "_is_prospect", "Client / Company", "Country",
                  "Project / Opp.", "In Pipeline", "In Stage Since"],
        column_config={
            "_id":              st.column_config.NumberColumn("_id",           width="small"),
            "_project_id":      st.column_config.TextColumn("_project_id",     width="small"),
            "_is_prospect":     st.column_config.CheckboxColumn("Prospect?",   width="small"),
            "Client / Company": st.column_config.TextColumn("Client / Company", width="medium"),
            "Country":          st.column_config.TextColumn("Country",          width="small"),
            "Opp. Country":     st.column_config.TextColumn("Opp. Country",     width="small"),
            "Project / Opp.":   st.column_config.TextColumn("Project / Opp.",   width="medium"),
            "Stage":            st.column_config.SelectboxColumn("Stage", options=STAGES, width="medium"),
            "Value (€)":        st.column_config.NumberColumn("Value (€)",      min_value=0, step=1000, format="%.0f"),
            "Min (€)":          st.column_config.NumberColumn("Min (€)",        min_value=0, step=1000, format="%.0f"),
            "Est (€)":          st.column_config.NumberColumn("Est (€)",        min_value=0, step=1000, format="%.0f"),
            "Max (€)":          st.column_config.NumberColumn("Max (€)",        min_value=0, step=1000, format="%.0f"),
            "Prob %":           st.column_config.NumberColumn("Prob %",         min_value=0, max_value=100, step=5, format="%.0f%%"),
            "Notes":            st.column_config.TextColumn("Notes",            width="large"),
            "In Pipeline":      st.column_config.TextColumn("In Pipeline",      width="small"),
            "In Stage Since":   st.column_config.TextColumn("In Stage Since",   width="small"),
        },
        key="pipeline_editor",
    )

    # Live subtotals
    st.caption(f"Filtered totals — {len(edited)} entr{'y' if len(edited)==1 else 'ies'}")
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
            if orig.get("is_prospect"):
                db.update_prospect(
                    pipeline_id=int(row["_id"]),
                    company_name=str(row["Client / Company"]),
                    prospect_name=orig.get("prospect_name", ""),
                    description=orig.get("description", ""),
                    stage=str(row["Stage"]),
                    value=float(row["Value (€)"] or 0),
                    budget_min=float(row["Min (€)"] or 0),
                    budget_est=float(row["Est (€)"] or 0),
                    budget_max=float(row["Max (€)"] or 0),
                    probability=float(row["Prob %"] or 50) / 100.0,
                    notes=str(row["Notes"] or ""),
                    opportunity_country=str(row["Opp. Country"] or ""),
                )
            else:
                db.upsert_pipeline(
                    int(row["_project_id"]),
                    str(row["Stage"]),
                    float(row["Value (€)"] or 0),
                    str(row["Notes"] or ""),
                    budget_min=float(row["Min (€)"] or 0),
                    budget_est=float(row["Est (€)"] or 0),
                    budget_max=float(row["Max (€)"] or 0),
                    probability=float(row["Prob %"] or 50) / 100.0,
                    opportunity_country=str(row["Opp. Country"] or ""),
                )
            changed += 1
        st.success(f"Saved {changed} pipeline entr{'y' if changed==1 else 'ies'}.")
        st.cache_data.clear()
        st.rerun()

# ------------------------------------------------------------------
# Prospect Actions: Edit | Convert | Delete | Activity Log
# ------------------------------------------------------------------

prospect_rows = [r for r in pipeline if r.get("is_prospect")]
if prospect_rows:
    st.divider()
    st.subheader("Prospect Actions")
    prospect_options = {
        f"{r['display_client']} — {r.get('display_project') or '(no opp. name)'} (id {r['id']})": r
        for r in prospect_rows
    }
    sel_label    = st.selectbox("Select prospect", list(prospect_options.keys()), key="prospect_sel")
    sel_prospect = prospect_options[sel_label]

    tab_edit, tab_convert, tab_log = st.tabs(["Edit", "Convert / Delete", "Activity Log"])

    # ── Edit tab ────────────────────────────────────────────────────
    with tab_edit:
        with st.form("edit_prospect_form"):
            ep_col1, ep_col2 = st.columns(2)
            ep_company = ep_col1.text_input("Company name *",    value=sel_prospect["display_client"])
            ep_opp     = ep_col2.text_input("Opportunity name",  value=sel_prospect.get("prospect_name") or "")
            ep_desc    = st.text_input("Description / notes on opportunity",
                                       value=sel_prospect.get("description") or "")
            ep_col3, ep_col4, ep_col5 = st.columns(3)
            ep_country = ep_col3.text_input("Opportunity Country",
                                            value=sel_prospect.get("opportunity_country") or "")
            ep_stage   = ep_col3.selectbox("Stage", STAGES,
                                            index=STAGES.index(sel_prospect["stage"])
                                            if sel_prospect["stage"] in STAGES else 0)
            ep_min     = ep_col4.number_input("Budget Min (€)", min_value=0.0, step=1000.0,
                                               value=float(sel_prospect.get("budget_min") or 0))
            ep_est     = ep_col4.number_input("Budget Est (€)", min_value=0.0, step=1000.0,
                                               value=float(sel_prospect.get("budget_est") or 0))
            ep_max     = ep_col5.number_input("Budget Max (€)", min_value=0.0, step=1000.0,
                                               value=float(sel_prospect.get("budget_max") or 0))
            ep_prob    = ep_col5.slider("Probability %", 0, 100,
                                        int(round((sel_prospect.get("probability") or 0.5) * 100)), step=5)
            ep_notes   = st.text_area("Notes", value=sel_prospect.get("notes") or "", height=60)
            if st.form_submit_button("Save changes", type="primary"):
                if not ep_company.strip():
                    st.error("Company name is required.")
                else:
                    db.update_prospect(
                        pipeline_id=sel_prospect["id"],
                        company_name=ep_company.strip(),
                        prospect_name=ep_opp.strip(),
                        description=ep_desc.strip(),
                        stage=ep_stage,
                        value=ep_est,
                        budget_min=ep_min,
                        budget_est=ep_est,
                        budget_max=ep_max,
                        probability=ep_prob / 100.0,
                        notes=ep_notes.strip(),
                        opportunity_country=ep_country.strip(),
                    )
                    st.success("Prospect updated.")
                    st.cache_data.clear()
                    st.rerun()

    # ── Convert / Delete tab ────────────────────────────────────────
    with tab_convert:
        st.caption("Convert to Project: navigates to Add New Project with this prospect's details pre-filled. "
                   "The pipeline entry will be linked to the new project on save.")
        if st.button("Convert to Project →", type="secondary"):
            st.session_state["_pipeline_convert"] = {
                "id":          sel_prospect["id"],
                "company":     sel_prospect["display_client"],
                "description": sel_prospect.get("description", ""),
                "prospect":    sel_prospect.get("prospect_name", "") or sel_prospect.get("display_project", ""),
            }
            st.switch_page("pages/11_add_new_project.py")

        st.divider()
        st.caption("Delete this prospect entry permanently.")
        if st.button("Delete Prospect", type="secondary", key="btn_del_prospect"):
            db.delete_prospect(sel_prospect["id"])
            st.success(f"Prospect '{sel_prospect['display_client']}' deleted.")
            st.cache_data.clear()
            st.rerun()

    # ── Activity Log tab ────────────────────────────────────────────
    with tab_log:
        st.caption("Timestamped notes — keep a running history of activity, conversations, and decisions for this prospect.")
        existing_notes = db.get_pipeline_notes(sel_prospect["id"])
        if existing_notes:
            for entry in existing_notes:
                ts = entry["created_at"][:16].replace("T", " ")
                st.markdown(f"**{ts}** — {entry['note']}")
        else:
            st.info("No activity notes yet.")
        st.divider()
        with st.form("add_pipeline_note_form", clear_on_submit=True):
            new_note = st.text_area("Add note", height=80, placeholder="e.g. Called client — interested, follow up next week.")
            if st.form_submit_button("Add note"):
                if new_note.strip():
                    db.add_pipeline_note(sel_prospect["id"], new_note.strip())
                    st.rerun()
                else:
                    st.warning("Note cannot be empty.")
