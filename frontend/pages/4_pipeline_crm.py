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
from shared.ui import require_auth, faceted_filters
from datetime import datetime, date

require_auth()

st.title("Pipeline / CRM")

STAGES = ["Prospect", "Active", "On Hold", "Completed", "Lost"]
# Optional sub-steps while a prospect is still in the Prospect stage
PROSPECT_STEPS = ["", "Lead", "Proposal sent", "Negotiation"]
STALE_DAYS = 60


def _s(v) -> str:
    """Cell value -> clean string (data_editor can return None / NaN for blanks)."""
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def _iso(v) -> str:
    """Return an ISO date string, or '' if blank. Raises ValueError for anything unparseable."""
    t = _s(v)[:10]
    if not t:
        return ""
    return date.fromisoformat(t).isoformat()


def _flag(r) -> str:
    """Follow-up warning for a prospect: overdue next action, or long time in stage."""
    if not (r.get("is_prospect") and r["stage"] == "Prospect"):
        return ""
    today = date.today()
    nad = _s(r.get("next_action_date"))[:10]
    if nad and nad < today.isoformat():
        return "⏰ action overdue"
    since = _s(r.get("date_entered_stage"))[:10] or _s(r.get("date_entered_pipeline"))[:10]
    try:
        days = (today - date.fromisoformat(since)).days
    except ValueError:
        return ""
    return f"💤 {days}d in stage" if days > STALE_DAYS else ""

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
        col6, col7, col8 = st.columns(3)
        ap_step     = col6.selectbox("Prospect step", PROSPECT_STEPS, format_func=lambda x: x or "—")
        ap_close    = col6.date_input("Expected close", value=None)
        ap_action   = col7.text_input("Next action", placeholder="e.g. Send proposal")
        ap_action_d = col8.date_input("Next action date", value=None)
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
                prospect_step=ap_step,
                expected_close=ap_close.isoformat() if ap_close else "",
                next_action=ap_action.strip(),
                next_action_date=ap_action_d.isoformat() if ap_action_d else "",
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

_match = faceted_filters(pipeline, [
    {"key": "pl_stage",       "label": "Stage",               "get": lambda r: r["stage"], "single": True},
    {"key": "pl_client",      "label": "Client / Company",    "get": lambda r: r.get("display_client"), "single": True},
    {"key": "pl_opp_country", "label": "Opportunity Country", "get": lambda r: r.get("opportunity_country")},
    {"key": "pl_country",     "label": "Client Country",      "get": lambda r: r.get("country")},
    {"key": "pl_type",        "label": "Client Type",         "get": lambda r: "" if r.get("is_prospect") else r.get("client_type"),
     "help": "Only applies to linked (non-prospect) entries"},
])
filtered = [r for r in pipeline if _match(r)]

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
# Prospect funnel (prospects still in the Prospect stage, by step)
# ------------------------------------------------------------------

st.subheader("Prospect funnel")
_open_prospects = [r for r in pipeline if r.get("is_prospect") and r["stage"] == "Prospect"]
_funnel_steps = [x for x in PROSPECT_STEPS if x] + ["(no step)"]
for col, step in zip(st.columns(len(_funnel_steps)), _funnel_steps):
    _rows = [r for r in _open_prospects if (_s(r.get("prospect_step")) or "(no step)") == step]
    _w = sum((r.get("budget_est") or 0) * (r.get("probability") or 0) for r in _rows)
    col.metric(step, f"{len(_rows)} prospect(s)", f"€{_w:,.0f} weighted est.", delta_color="off")
_lost_rows = [r for r in pipeline if r["stage"] == "Lost"]
if _lost_rows:
    st.caption(f"Lost to date: {len(_lost_rows)} (reasons in the table below; filter Stage = Lost).")
st.divider()

# ------------------------------------------------------------------
# Probability-weighted forecast
# ------------------------------------------------------------------

prob_rows = [r for r in filtered if r["stage"] != "Lost" and r.get("probability") and (
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
            "Step":              _s(r.get("prospect_step")),
            "Expected close":    _s(r.get("expected_close"))[:10],
            "Next action":       _s(r.get("next_action")),
            "Next action date":  _s(r.get("next_action_date"))[:10],
            "Lost reason":       _s(r.get("lost_reason")),
            "Flag":              _flag(r),
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
                  "Project / Opp.", "Flag", "In Pipeline", "In Stage Since"],
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
            "Step":             st.column_config.SelectboxColumn("Step", options=PROSPECT_STEPS, width="small",
                                                                 help="Prospects only"),
            "Expected close":   st.column_config.TextColumn("Expected close",   width="small", help="YYYY-MM-DD (prospects only)"),
            "Next action":      st.column_config.TextColumn("Next action",      width="medium", help="Prospects only"),
            "Next action date": st.column_config.TextColumn("Next action date", width="small", help="YYYY-MM-DD (prospects only)"),
            "Lost reason":      st.column_config.TextColumn("Lost reason",      width="medium", help="Prospects only"),
            "Flag":             st.column_config.TextColumn("Flag",             width="small"),
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
        bad_dates: list[str] = []
        for _, row in edited.iterrows():
            orig = next((r for r in filtered if r["id"] == int(row["_id"])), None)
            if orig is None:
                continue
            if orig.get("is_prospect"):
                try:
                    _close, _nad = _iso(row["Expected close"]), _iso(row["Next action date"])
                except ValueError:
                    bad_dates.append(str(row["Client / Company"]))
                    continue
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
                    prospect_step=_s(row["Step"]),
                    expected_close=_close,
                    next_action=_s(row["Next action"]),
                    next_action_date=_nad,
                    lost_reason=_s(row["Lost reason"]),
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
        if bad_dates:
            st.error("Not saved - dates must be YYYY-MM-DD: " + ", ".join(bad_dates))
        else:
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

    tab_edit, tab_convert, tab_log = st.tabs(["Edit", "Convert / Lost / Delete", "Activity Log"])

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
            def _d(v):
                try:
                    return date.fromisoformat(_s(v)[:10]) if _s(v) else None
                except ValueError:
                    return None
            ef1, ef2, ef3 = st.columns(3)
            _cur_step = _s(sel_prospect.get("prospect_step"))
            ep_step    = ef1.selectbox("Prospect step", PROSPECT_STEPS, format_func=lambda x: x or "—",
                                       index=PROSPECT_STEPS.index(_cur_step) if _cur_step in PROSPECT_STEPS else 0)
            ep_close   = ef1.date_input("Expected close", value=_d(sel_prospect.get("expected_close")))
            ep_action  = ef2.text_input("Next action", value=_s(sel_prospect.get("next_action")))
            ep_action_d = ef3.date_input("Next action date", value=_d(sel_prospect.get("next_action_date")))
            ep_lost    = st.text_input("Lost reason (when stage is Lost)", value=_s(sel_prospect.get("lost_reason")))
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
                        prospect_step=ep_step,
                        expected_close=ep_close.isoformat() if ep_close else "",
                        next_action=ep_action.strip(),
                        next_action_date=ep_action_d.isoformat() if ep_action_d else "",
                        lost_reason=ep_lost.strip(),
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
        st.caption("Mark as Lost keeps the record (and its activity log) so you can see what was lost and why. "
                   "It drops out of the forecast.")
        lost_reason_in = st.text_input("Reason", key="lost_reason_in",
                                       placeholder="e.g. went with incumbent / budget cancelled")
        if st.button("Mark as Lost", key="btn_mark_lost", disabled=sel_prospect["stage"] == "Lost"):
            db.mark_prospect_lost(sel_prospect["id"], lost_reason_in)
            st.success(f"'{sel_prospect['display_client']}' marked as Lost.")
            st.cache_data.clear()
            st.rerun()

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
