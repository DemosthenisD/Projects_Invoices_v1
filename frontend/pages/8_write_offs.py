"""
Page 7 — Write-offs.

Record and manage write-off decisions at project or code+person level.
Write-offs reduce net billable charges without altering the underlying time entries.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
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

st.title("Write-offs")

tab_create, tab_log = st.tabs(["Create Write-off", "Write-off Log"])

# Form-key counter
st.session_state.setdefault("_wo_v", 0)

# ==================================================================
# TAB 1 — CREATE
# ==================================================================

with tab_create:
    st.subheader("Record a Write-off")

    clients = db.get_clients()
    if not clients:
        st.info("No clients yet.")
        st.stop()

    ccols = st.columns(2)
    sel_client = ccols[0].selectbox("Client", [c.name for c in clients], key="wo_client")
    client_obj = next(c for c in clients if c.name == sel_client)

    projects = db.get_projects(client_id=client_obj.id)
    if not projects:
        st.info("No projects for this client.")
        st.stop()

    sel_project = ccols[1].selectbox("Project", [p.name for p in projects], key="wo_project")
    project_obj = next(p for p in projects if p.name == sel_project)

    codes = db.get_project_codes(project_id=project_obj.id)
    totals = db.get_project_time_totals(project_obj.id)

    # Current project metrics for context
    m1, m2, m3 = st.columns(3)
    m1.metric("Billable charges (€)", f"{totals['billable_charges']:,.2f}")
    m2.metric("Active write-offs (€)", f"{totals['write_offs']:,.2f}")
    m3.metric("Net billable (€)",     f"{totals['net_charges']:,.2f}")

    st.divider()

    if _msg := st.session_state.pop("_wo_msg", None):
        st.success(_msg)
    if _err := st.session_state.pop("_wo_err", None):
        st.error(_err)

    wo_type = st.radio(
        "Write-off type",
        ["Project-level (auto pro-rata)", "Ad-hoc (specific code & person)"],
        horizontal=True,
        key="wo_type",
    )

    with st.form(f"wo_form_{st.session_state['_wo_v']}"):
        wo_amount = st.number_input("Amount (€) *", min_value=0.01, step=100.0)
        wo_reason = st.text_input("Reason *", placeholder="e.g. Budget overrun — client agreed reduction")
        wo_notes  = st.text_area("Notes", height=60)

        if wo_type.startswith("Ad-hoc"):
            if not codes:
                st.warning("No project codes defined for this project.")
            else:
                code_labels = [f"{c.client_code} / {c.client_suffix}" + (f" — {c.name}" if c.name else "")
                               for c in codes]
                sel_code_idx = st.selectbox("Project code", range(len(codes)),
                                            format_func=lambda i: code_labels[i],
                                            key="wo_code_sel")

            # Consultant selector — built from time entries for this project
            entries = db.get_time_entries(project_id=project_obj.id, include_internal=False)
            consultants = sorted({f"{e.emp_nbr} — {e.consultant}" for e in entries})
            if consultants:
                sel_consultant = st.selectbox("Consultant", consultants, key="wo_consultant")
            else:
                sel_consultant = None
                st.info("No billable time entries found for consultant selection.")

        submitted = st.form_submit_button("Record write-off", type="primary")

    if submitted:
        if not wo_reason.strip():
            st.session_state["_wo_err"] = "Reason is required."
            st.rerun()
        elif wo_type.startswith("Project-level"):
            try:
                ids = db.add_write_off_project(project_obj.id, wo_amount, wo_reason.strip(), wo_notes.strip())
                st.session_state["_wo_v"] += 1
                st.session_state["_wo_msg"] = (
                    f"Write-off of €{wo_amount:,.2f} recorded and allocated across {len(ids)} (code, person) combination(s)."
                )
                st.rerun()
            except ValueError as e:
                st.session_state["_wo_err"] = str(e)
                st.rerun()
        else:
            if not codes:
                st.session_state["_wo_err"] = "No project codes available."
                st.rerun()
            elif not sel_consultant:
                st.session_state["_wo_err"] = "No consultant selected."
                st.rerun()
            else:
                code_obj = codes[sel_code_idx]
                emp_nbr, consultant = sel_consultant.split(" — ", 1)
                db.add_write_off_adhoc(
                    project_id=project_obj.id,
                    project_code_id=code_obj.id,
                    emp_nbr=emp_nbr,
                    consultant=consultant,
                    amount=wo_amount,
                    reason=wo_reason.strip(),
                    notes=wo_notes.strip(),
                )
                st.session_state["_wo_v"] += 1
                st.session_state["_wo_msg"] = (
                    f"Ad-hoc write-off of €{wo_amount:,.2f} recorded for {consultant}."
                )
                st.rerun()

    # Pro-rata preview (project-level only, before submitting)
    if wo_type.startswith("Project-level"):
        entries = db.get_time_entries(project_id=project_obj.id, include_internal=False)
        if entries:
            from collections import defaultdict
            group_charges: dict = defaultdict(float)
            group_labels: dict = {}
            for e in entries:
                key = (e.project_code_id, e.emp_nbr)
                group_charges[key] += e.non_z_charges
                group_labels[key]  = f"{e.client_code}/{e.client_suffix} — {e.consultant}"
            total = sum(group_charges.values())
            if total > 0:
                preview_rows = [
                    {
                        "Code / Person": group_labels[k],
                        "Charges (€)":  f"{v:,.2f}",
                        "Share":        f"{v/total*100:.1f}%",
                    }
                    for k, v in sorted(group_charges.items(), key=lambda x: -x[1])
                ]
                with st.expander("Allocation preview", expanded=True):
                    st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
                    st.caption("Actual amounts are calculated at the time of saving based on the amount entered above.")

# ==================================================================
# TAB 2 — LOG
# ==================================================================

with tab_log:
    st.subheader("Write-off Log")

    clients = db.get_clients()
    if not clients:
        st.info("No clients yet.")
        st.stop()

    lcols = st.columns([2, 2, 1])
    l_client  = lcols[0].selectbox("Client",  ["All"] + [c.name for c in clients], key="wol_client")
    client_lo = next((c for c in clients if c.name == l_client), None)

    projects_lo = db.get_projects(client_id=client_lo.id) if client_lo else []
    l_project   = lcols[1].selectbox("Project", ["All"] + [p.name for p in projects_lo],
                                      key="wol_project")
    project_lo  = next((p for p in projects_lo if p.name == l_project), None)

    show_reversed = lcols[2].checkbox("Show reversed", key="wol_reversed")

    if _rev_msg := st.session_state.pop("_rev_msg", None):
        st.success(_rev_msg)

    write_offs = db.get_write_offs(
        project_id=project_lo.id if project_lo else None,
        include_reversed=show_reversed,
    )

    if not write_offs:
        st.info("No write-offs found.")
    else:
        # Resolve project code labels
        all_codes = {c.id: f"{c.client_code}/{c.client_suffix}" + (f" — {c.name}" if c.name else "")
                     for proj in (projects_lo if project_lo else db.get_projects())
                     for c in db.get_project_codes(project_id=proj.id)}

        for wo in write_offs:
            code_label = all_codes.get(wo.project_code_id, "—")
            status     = "Reversed" if wo.reversed else "Active"
            header     = (
                f"{'~~' if wo.reversed else ''}€{wo.amount:,.2f}  |  "
                f"{code_label}  |  {wo.consultant or '—'}  |  {status}"
                f"{'~~' if wo.reversed else ''}"
            )
            with st.expander(header, expanded=False):
                col_info, col_action = st.columns([3, 1])
                with col_info:
                    st.write(f"**Reason:** {wo.reason}")
                    if wo.notes:
                        st.write(f"**Notes:** {wo.notes}")
                    st.caption(
                        f"Type: {wo.allocation_type}  |  "
                        f"Person: {wo.emp_nbr} {wo.consultant}  |  "
                        f"Created: {wo.created_at[:10] if wo.created_at else '—'}"
                    )
                    if wo.reversed:
                        st.caption(
                            f"Reversed: {wo.reversed_at[:10] if wo.reversed_at else '—'}  "
                            f"— {wo.reversed_reason}"
                        )

                with col_action:
                    if not wo.reversed:
                        rev_reason = st.text_input("Reversal reason", key=f"rev_reason_{wo.id}")
                        if st.button("Reverse", key=f"rev_{wo.id}", type="secondary"):
                            if not rev_reason.strip():
                                st.error("Reversal reason required.")
                            else:
                                db.reverse_write_off(wo.id, rev_reason.strip())
                                st.session_state["_rev_msg"] = f"Write-off reversed."
                                st.rerun()
