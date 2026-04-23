"""
Page 5 — Project Codes.

Define and manage project codes (client_code + client_suffix) per project.
Each code links a scope of work to a project and optionally carries a budget.
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

st.title("Project Codes")

st.caption(
    "A project code is a **client_code + client_suffix** combination (e.g. 0478EUR30 / 07). "
    "The client code is derived automatically from the selected client. "
    "The same suffix can be reused for a later project by setting a **Date Start** on the new code — "
    "time entries are routed to the correct project based on their period date."
)

# Form-key counters
st.session_state.setdefault("_add_code_v", 0)

# ------------------------------------------------------------------
# Client → Project selector
# ------------------------------------------------------------------

clients = db.get_clients()
if not clients:
    st.info("Add a client first (Clients & Projects page).")
    st.stop()

col_client, col_project = st.columns(2)
with col_client:
    selected_client = st.selectbox("Client", [c.name for c in clients], key="pc_client_sel")
client_obj = next(c for c in clients if c.name == selected_client)

projects = db.get_projects(client_id=client_obj.id)
with col_project:
    if not projects:
        st.info("No projects for this client.")
        st.stop()
    selected_project = st.selectbox("Project", [p.name for p in projects], key="pc_project_sel")
project_obj = next(p for p in projects if p.name == selected_project)

st.divider()

# ------------------------------------------------------------------
# Pending messages
# ------------------------------------------------------------------

if _msg := st.session_state.pop("_code_msg", None):
    st.success(_msg)
if _err := st.session_state.pop("_code_err", None):
    st.error(_err)

# ------------------------------------------------------------------
# Add new project code
# ------------------------------------------------------------------

with st.expander("Add project code", expanded=False):
    st.caption(
        f"Client code will be set automatically to **{client_obj.client_code or '(not set on client)'}**. "
        "Leave Date Start blank for a first-use suffix. Set Date Start only when reusing a suffix "
        "that already belongs to another project — time entries on or after that date will route here."
    )
    with st.form(f"add_code_form_{st.session_state['_add_code_v']}"):
        col1, col2 = st.columns(2)
        new_cs     = col1.text_input("Client suffix *", placeholder="e.g. 01")
        new_budget = col2.number_input("Budget (€)", min_value=0.0, step=500.0)
        new_name   = st.text_input("Name", placeholder="e.g. IFRS17 Phase 1")
        new_desc   = st.text_area("Description", height=60)
        col3, col4, col5 = st.columns(3)
        new_ds_raw = col3.text_input("Date Start (YYYY-MM-DD)", placeholder="leave blank if first use")
        new_de_raw = col4.text_input("Date End   (YYYY-MM-DD)", placeholder="leave blank if open-ended")
        new_status = col5.selectbox("Status", ["Active", "On Hold", "Completed"])
        submitted  = st.form_submit_button("Add project code")

    if submitted:
        new_ds = new_ds_raw.strip()
        new_de = new_de_raw.strip()
        if not new_cs.strip():
            st.error("Client suffix is required.")
        elif not client_obj.client_code:
            st.error("This client has no client code set — please add one in Clients & Projects first.")
        else:
            # Warn if same suffix+date_start already exists (first-use or reuse clash)
            existing = db.get_project_code_by_keys(client_obj.client_code, new_cs.strip())
            clash = existing and existing.date_start == new_ds
            if clash:
                st.error(
                    f"A code {client_obj.client_code} / {new_cs.strip()} with "
                    f"Date Start '{new_ds or '(none)'}' already exists "
                    f"(project ID {existing.project_id})."
                )
            else:
                db.add_project_code(
                    project_id=project_obj.id,
                    client_suffix=new_cs.strip(),
                    name=new_name.strip(),
                    description=new_desc.strip(),
                    budget_amount=new_budget,
                    status=new_status,
                    date_start=new_ds,
                    date_end=new_de,
                )
                st.session_state["_add_code_v"] += 1
                st.session_state["_code_msg"] = (
                    f"Project code {client_obj.client_code} / {new_cs.strip()} added."
                )
                st.rerun()

st.divider()

# ------------------------------------------------------------------
# Existing codes for selected project
# ------------------------------------------------------------------

codes = db.get_project_codes(project_id=project_obj.id)

if not codes:
    st.info("No project codes yet for this project.")
else:
    summary = db.get_time_summary(project_obj.id)
    summary_by_id = {s["project_code_id"]: s for s in summary}

    for code in codes:
        s = summary_by_id.get(code.id, {})
        billable    = s.get("non_z_charges", 0.0)
        write_offs  = s.get("write_off_amount", 0.0)
        net         = s.get("net_charges", 0.0)
        remaining   = (code.budget_amount - net) if code.budget_amount else None

        date_range = ""
        if code.date_start or code.date_end:
            date_range = f"  [{code.date_start or '…'} → {code.date_end or '…'}]"
        label = (
            f"{code.client_code} / {code.client_suffix}"
            + date_range
            + (f"  —  {code.name}" if code.name else "")
            + f"  [{code.status}]"
        )
        with st.expander(label, expanded=False):
            # Metrics row
            mcols = st.columns(4)
            mcols[0].metric("Budget (€)",    f"{code.budget_amount:,.2f}" if code.budget_amount else "—")
            mcols[1].metric("Billable (€)",  f"{billable:,.2f}")
            mcols[2].metric("Write-offs (€)", f"{write_offs:,.2f}")
            if remaining is not None:
                colour = "normal" if remaining >= 0 else "inverse"
                mcols[3].metric("Remaining (€)", f"{remaining:,.2f}", delta_color=colour)
            else:
                mcols[3].metric("Remaining (€)", "—")

            st.divider()

            # Edit form
            with st.form(f"edit_code_{code.id}"):
                e_name   = st.text_input("Name",        value=code.name)
                e_desc   = st.text_area("Description",  value=code.description, height=60)
                col_a, col_b = st.columns(2)
                e_budget = col_a.number_input("Budget (€)", min_value=0.0, step=500.0,
                                              value=code.budget_amount, key=f"bgt_{code.id}")
                e_status = col_b.selectbox(
                    "Status", ["Active", "On Hold", "Completed"],
                    index=["Active", "On Hold", "Completed"].index(code.status)
                    if code.status in ["Active", "On Hold", "Completed"] else 0,
                    key=f"stat_{code.id}"
                )
                col_c, col_d = st.columns(2)
                e_ds = col_c.text_input("Date Start (YYYY-MM-DD)", value=code.date_start,
                                        key=f"ds_{code.id}")
                e_de = col_d.text_input("Date End (YYYY-MM-DD)",   value=code.date_end,
                                        key=f"de_{code.id}")
                col_save, col_del, _ = st.columns([1, 1, 4])
                save   = col_save.form_submit_button("Save")
                delete = col_del.form_submit_button("Delete", type="secondary")

            if save:
                db.update_project_code(code.id, e_name, e_desc, e_budget, e_status,
                                       e_ds.strip(), e_de.strip())
                st.session_state["_code_msg"] = "Updated."
                st.rerun()

            if delete:
                try:
                    db.delete_project_code(code.id)
                    st.session_state["_code_msg"] = (
                        f"Deleted {code.client_code} / {code.client_suffix}."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.session_state["_code_err"] = str(exc)
                    st.rerun()
