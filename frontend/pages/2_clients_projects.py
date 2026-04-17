"""
Page 2 — Clients & Projects.

Tabbed CRUD:
  Clients   — list, add (duplicate detection), edit, delete
  Projects  — list by client, add, edit (description/VAT/template/status), delete
  Addresses — list by client, add, delete
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import backend.db as db
from shared.config import TEMPLATES_DIR

# ------------------------------------------------------------------
# Auth guard
# ------------------------------------------------------------------

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

# ------------------------------------------------------------------
# Page setup
# ------------------------------------------------------------------

st.title("Clients & Projects")

tab_clients, tab_projects, tab_addresses = st.tabs(["Clients", "Projects", "Addresses"])

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _templates() -> list[str]:
    return sorted(
        f.replace(".docx", "")
        for f in os.listdir(TEMPLATES_DIR)
        if f.endswith(".docx") and not f.startswith("filled")
    )

PROJECT_STATUSES = ["Active", "On Hold", "Completed", "Prospect"]

# Form-key counters — incrementing these forces Streamlit to treat the
# form as brand-new on rerun, preventing double-submission of add forms.
for _k in ("_add_client_v", "_add_proj_v", "_add_addr_v"):
    st.session_state.setdefault(_k, 0)

# ==================================================================
# TAB 1 — CLIENTS
# ==================================================================

with tab_clients:
    st.subheader("Clients")

    # Show any pending success message from a previous rerun
    if _msg := st.session_state.pop("_client_msg", None):
        st.success(_msg)

    clients = db.get_clients()

    # ---- Add new client ----
    with st.expander("Add new client", expanded=False):
        with st.form(f"add_client_form_{st.session_state['_add_client_v']}"):
            new_name     = st.text_input("Internal name *", placeholder="e.g. Ethniki CY")
            new_inv_name = st.text_input("Name for invoices", placeholder="Formal legal name")
            new_code     = st.text_input("Client code", placeholder="e.g. ETN")
            new_vat      = st.text_input("VAT number")
            submitted    = st.form_submit_button("Add client")

        if submitted:
            if not new_name.strip():
                st.error("Internal name is required.")
            elif any(c.name.lower() == new_name.strip().lower() for c in clients):
                st.error(f"Client '{new_name.strip()}' already exists.")
            else:
                db.add_client(
                    name=new_name.strip(),
                    name_for_invoices=new_inv_name.strip() or new_name.strip(),
                    client_code=new_code.strip(),
                    vat_number=new_vat.strip(),
                )
                st.session_state["_add_client_v"] += 1
                st.session_state["_client_msg"] = f"Client '{new_name.strip()}' added."
                st.cache_data.clear()
                st.rerun()

    st.divider()

    # ---- List & edit/delete ----
    if not clients:
        st.info("No clients yet.")
    else:
        for client in clients:
            with st.expander(f"{client.name}  ({client.client_code or '—'})", expanded=False):
                with st.form(f"edit_client_{client.id}"):
                    e_inv  = st.text_input("Name for invoices", value=client.name_for_invoices)
                    e_code = st.text_input("Client code",       value=client.client_code)
                    e_vat  = st.text_input("VAT number",        value=client.vat_number)
                    col_save, col_del, _ = st.columns([1, 1, 4])
                    save   = col_save.form_submit_button("Save")
                    delete = col_del.form_submit_button("Delete", type="secondary")

                if save:
                    db.update_client(client.id, e_inv, e_code, e_vat)
                    st.success("Updated.")
                    st.cache_data.clear()
                    st.rerun()

                if delete:
                    invoices = db.get_invoices(client_id=client.id)
                    if invoices:
                        st.error(
                            f"Cannot delete — {len(invoices)} invoice(s) linked to this client."
                        )
                    else:
                        db.delete_client(client.id)
                        st.session_state["_client_msg"] = f"Deleted '{client.name}'."
                        st.cache_data.clear()
                        st.rerun()

# ==================================================================
# TAB 2 — PROJECTS
# ==================================================================

with tab_projects:
    st.subheader("Projects")

    if _msg := st.session_state.pop("_proj_msg", None):
        st.success(_msg)

    clients = db.get_clients()
    if not clients:
        st.info("Add a client first.")
        st.stop()

    selected_client = st.selectbox(
        "Client", [c.name for c in clients], key="proj_client_select"
    )
    client_obj = next(c for c in clients if c.name == selected_client)

    # ---- Add new project ----
    with st.expander("Add new project", expanded=False):
        templates = _templates()
        with st.form(f"add_project_form_{st.session_state['_add_proj_v']}"):
            p_name  = st.text_input("Project name *")
            p_desc  = st.text_area("Description", height=70)
            p_vat   = st.number_input("VAT %", min_value=0.0, max_value=100.0,
                                      value=19.0, step=1.0)
            p_tmpl  = st.selectbox("Template", templates)
            p_stat  = st.selectbox("Status", PROJECT_STATUSES)
            add_btn = st.form_submit_button("Add project")

        if add_btn:
            if not p_name.strip():
                st.error("Project name is required.")
            else:
                existing = db.get_projects(client_id=client_obj.id)
                if any(p.name.lower() == p_name.strip().lower() for p in existing):
                    st.error(f"Project '{p_name.strip()}' already exists for this client.")
                else:
                    db.add_project(
                        client_id=client_obj.id,
                        name=p_name.strip(),
                        description=p_desc.strip(),
                        vat_pct=p_vat,
                        template=p_tmpl,
                        status=p_stat,
                    )
                    st.session_state["_add_proj_v"] += 1
                    st.session_state["_proj_msg"] = f"Project '{p_name.strip()}' added."
                    st.cache_data.clear()
                    st.rerun()

    st.divider()

    # ---- List & edit/delete ----
    projects = db.get_projects(client_id=client_obj.id)
    if not projects:
        st.info("No projects for this client yet.")
    else:
        templates = _templates()
        for proj in projects:
            label = f"{proj.name}  [{proj.status}]"
            with st.expander(label, expanded=False):
                with st.form(f"edit_proj_{proj.id}"):
                    e_desc = st.text_area("Description", value=proj.description, height=70)
                    e_vat  = st.number_input("VAT %", min_value=0.0, max_value=100.0,
                                             value=proj.vat_pct, step=1.0,
                                             key=f"vat_{proj.id}")
                    tmpl_idx = templates.index(proj.template) if proj.template in templates else 0
                    e_tmpl = st.selectbox("Template", templates, index=tmpl_idx,
                                          key=f"tmpl_{proj.id}")
                    stat_idx = PROJECT_STATUSES.index(proj.status) if proj.status in PROJECT_STATUSES else 0
                    e_stat = st.selectbox("Status", PROJECT_STATUSES, index=stat_idx,
                                          key=f"stat_{proj.id}")
                    col_save, col_del, _ = st.columns([1, 1, 4])
                    save   = col_save.form_submit_button("Save")
                    delete = col_del.form_submit_button("Delete", type="secondary")

                if save:
                    db.update_project(proj.id, e_desc, e_vat, e_tmpl, e_stat)
                    st.success("Updated.")
                    st.cache_data.clear()
                    st.rerun()

                if delete:
                    invoices = db.get_invoices(project_name=proj.name)
                    if invoices:
                        st.error(
                            f"Cannot delete — {len(invoices)} invoice(s) linked to this project."
                        )
                    else:
                        db.delete_project(proj.id)
                        st.session_state["_proj_msg"] = f"Deleted '{proj.name}'."
                        st.cache_data.clear()
                        st.rerun()

# ==================================================================
# TAB 3 — ADDRESSES
# ==================================================================

with tab_addresses:
    st.subheader("Addresses")

    if _msg := st.session_state.pop("_addr_msg", None):
        st.success(_msg)

    clients = db.get_clients()
    if not clients:
        st.info("Add a client first.")
        st.stop()

    selected_client_addr = st.selectbox(
        "Client", [c.name for c in clients], key="addr_client_select"
    )
    client_addr = next(c for c in clients if c.name == selected_client_addr)

    # ---- Add address ----
    with st.expander("Add address", expanded=False):
        with st.form(f"add_address_form_{st.session_state['_add_addr_v']}"):
            new_addr = st.text_area("Address *", height=80)
            add_addr = st.form_submit_button("Add address")

        if add_addr:
            if not new_addr.strip():
                st.error("Address cannot be empty.")
            else:
                db.add_address(client_addr.id, new_addr.strip())
                st.session_state["_add_addr_v"] += 1
                st.session_state["_addr_msg"] = "Address added."
                st.cache_data.clear()
                st.rerun()

    st.divider()

    # ---- List & delete ----
    addresses = db.get_addresses(client_addr.id)
    if not addresses:
        st.info("No addresses for this client yet.")
    else:
        for addr in addresses:
            col_text, col_del = st.columns([5, 1])
            col_text.write(addr.address)
            if col_del.button("Delete", key=f"del_addr_{addr.id}"):
                db.delete_address(addr.id)
                st.session_state["_addr_msg"] = "Address deleted."
                st.cache_data.clear()
                st.rerun()
