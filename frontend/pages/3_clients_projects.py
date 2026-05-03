"""
Page 2 — Clients & Projects.

Tabbed CRUD:
  Clients   — tabular overview with counts, add + edit panel (internal hidden by default)
  Projects  — list by client with status filter, budget breakdown, add, edit, delete
  Addresses — list by client, add, delete
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import backend.db as db
from shared.config import TEMPLATES_DIR

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

st.title("Clients & Projects")

tab_clients, tab_projects, tab_addresses = st.tabs(["Clients", "Projects", "Addresses"])

def _templates() -> list[str]:
    return sorted(
        f.replace(".docx", "")
        for f in os.listdir(TEMPLATES_DIR)
        if f.endswith(".docx") and not f.startswith("filled")
    )

PROJECT_STATUSES = ["Active", "On Hold", "Completed", "Prospect"]
CLIENT_TYPES     = ["managed", "external", "internal"]

for _k in ("_add_client_v", "_add_proj_v", "_add_addr_v"):
    st.session_state.setdefault(_k, 0)

# ==================================================================
# TAB 1 — CLIENTS
# ==================================================================

with tab_clients:
    st.subheader("Clients")

    if _msg := st.session_state.pop("_client_msg", None):
        st.success(_msg)

    show_internal = st.checkbox("Show internal / non-billable clients (0009xxx)", value=False)
    exclude = [] if show_internal else ["internal"]

    # ---- Summary table ----
    rows_with_counts = db.get_clients_with_counts(exclude_types=exclude)
    if rows_with_counts:
        TYPE_BADGE = {"managed": "🟢", "external": "🔵", "internal": "⚪"}
        summary_rows = [
            {
                "": TYPE_BADGE.get(r["client_type"], ""),
                "Name": r["name"],
                "Code": r["client_code"] or "—",
                "Type": r["client_type"],
                "Country": r["country"] or "—",
                "Name for invoices": r["name_for_invoices"] or "—",
                "Projects": r["total_projects"],
                "Active projects": r["active_projects"],
                "Active codes": r["active_codes"],
            }
            for r in rows_with_counts
        ]
        st.dataframe(
            pd.DataFrame(summary_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "": st.column_config.TextColumn(width="small"),
                "Projects": st.column_config.NumberColumn(width="small"),
                "Active projects": st.column_config.NumberColumn(width="small"),
                "Active codes": st.column_config.NumberColumn(width="small"),
            },
        )
    else:
        st.info("No clients found." + ("" if show_internal else " (Internal clients are hidden — toggle above to show.)"))

    st.divider()

    # ---- Add new client ----
    with st.expander("Add new client", expanded=False):
        with st.form(f"add_client_form_{st.session_state['_add_client_v']}"):
            new_name     = st.text_input("Internal name *", placeholder="e.g. Ethniki CY")
            new_inv_name = st.text_input("Name for invoices", placeholder="Formal legal name")
            col_a, col_b = st.columns(2)
            new_code     = col_a.text_input("Client code", placeholder="e.g. 0478ETH30")
            new_country  = col_b.text_input("Country", placeholder="e.g. Cyprus")
            new_vat      = st.text_input("VAT number")
            new_type     = st.selectbox("Client type", CLIENT_TYPES,
                                        help="managed = full; external = time tracking only; internal = non-billable overhead")
            submitted    = st.form_submit_button("Add client")

        if submitted:
            if not new_name.strip():
                st.error("Internal name is required.")
            elif any(c.name.lower() == new_name.strip().lower() for c in db.get_clients()):
                st.error(f"Client '{new_name.strip()}' already exists.")
            else:
                db.add_client(
                    name=new_name.strip(),
                    name_for_invoices=new_inv_name.strip() or new_name.strip(),
                    client_code=new_code.strip(),
                    vat_number=new_vat.strip(),
                    client_type=new_type,
                    country=new_country.strip(),
                )
                st.session_state["_add_client_v"] += 1
                st.session_state["_client_msg"] = f"Client '{new_name.strip()}' added."
                st.cache_data.clear()
                st.rerun()

    # ---- Edit existing client ----
    clients = db.get_clients(exclude_types=exclude)
    if clients:
        with st.expander("Edit / delete a client", expanded=False):
            edit_name = st.selectbox("Select client to edit", [c.name for c in clients], key="edit_client_sel")
            client_obj = next(c for c in clients if c.name == edit_name)

            with st.form(f"edit_client_{client_obj.id}"):
                e_inv    = st.text_input("Name for invoices", value=client_obj.name_for_invoices)
                col_a, col_b = st.columns(2)
                e_code   = col_a.text_input("Client code",   value=client_obj.client_code)
                e_country= col_b.text_input("Country",       value=client_obj.country)
                e_vat    = st.text_input("VAT number",       value=client_obj.vat_number)
                type_idx = CLIENT_TYPES.index(client_obj.client_type) if client_obj.client_type in CLIENT_TYPES else 0
                e_type   = st.selectbox("Client type", CLIENT_TYPES, index=type_idx)
                col_save, col_del, _ = st.columns([1, 1, 4])
                save     = col_save.form_submit_button("Save")
                delete   = col_del.form_submit_button("Delete", type="secondary")

            if save:
                db.update_client(client_obj.id, e_inv, e_code, e_vat, e_type, e_country)
                st.success("Updated.")
                st.cache_data.clear()
                st.rerun()

            if delete:
                invoices = db.get_invoices(client_id=client_obj.id)
                if invoices:
                    st.error(f"Cannot delete — {len(invoices)} invoice(s) linked to this client.")
                else:
                    db.delete_client(client_obj.id)
                    st.session_state["_client_msg"] = f"Deleted '{client_obj.name}'."
                    st.cache_data.clear()
                    st.rerun()

# ==================================================================
# TAB 2 — PROJECTS
# ==================================================================

with tab_projects:
    st.subheader("Projects")

    if _msg := st.session_state.pop("_proj_msg", None):
        st.success(_msg)

    # Only managed + external clients make sense for project management
    clients = db.get_clients(exclude_types=["internal"])
    if not clients:
        st.info("Add a client first.")
        st.stop()

    col_cl, col_st = st.columns([3, 2])
    selected_client = col_cl.selectbox("Client", [c.name for c in clients], key="proj_client_select")
    client_obj = next(c for c in clients if c.name == selected_client)

    status_filter = col_st.multiselect(
        "Show statuses", PROJECT_STATUSES, default=["Active"],
        key="proj_status_filter"
    )

    # ---- Add new project ----
    with st.expander("Add new project", expanded=False):
        templates = _templates()
        with st.form(f"add_project_form_{st.session_state['_add_proj_v']}"):
            p_name  = st.text_input("Project name *")
            p_desc  = st.text_area("Description", height=70)
            p_start = st.text_input("Start date (YYYY-MM-DD)", placeholder="e.g. 2024-01-01")
            c1, c2 = st.columns(2)
            p_vat   = c1.number_input("VAT %", min_value=0.0, max_value=100.0,
                                      value=19.0, step=1.0)
            p_stat  = c2.selectbox("Status", PROJECT_STATUSES)
            p_tmpl  = st.selectbox("Template", templates)
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
                        date_start=p_start.strip(),
                    )
                    st.session_state["_add_proj_v"] += 1
                    st.session_state["_proj_msg"] = f"Project '{p_name.strip()}' added."
                    st.cache_data.clear()
                    st.rerun()

    st.divider()

    # ---- List & edit/delete ----
    all_projects = db.get_projects(client_id=client_obj.id)
    projects = [p for p in all_projects if (not status_filter or p.status in status_filter)]

    if not projects:
        msg = "No projects for this client yet." if not all_projects else \
              f"No projects with status {status_filter}. Clear the filter to see all."
        st.info(msg)
    else:
        templates = _templates()
        for proj in projects:
            start_label = f"  started {proj.date_start}" if proj.date_start else ""
            label = f"{proj.name}  [{proj.status}]{start_label}"
            with st.expander(label, expanded=False):

                # ---- Edit form ----
                with st.form(f"edit_proj_{proj.id}"):
                    e_desc  = st.text_area("Description", value=proj.description, height=70)
                    e_start = st.text_input("Start date (YYYY-MM-DD)", value=proj.date_start)
                    c1, c2 = st.columns(2)
                    e_vat   = c1.number_input("VAT %", min_value=0.0, max_value=100.0,
                                              value=proj.vat_pct, step=1.0,
                                              key=f"vat_{proj.id}")
                    e_stat  = c2.selectbox("Status", PROJECT_STATUSES,
                                           index=PROJECT_STATUSES.index(proj.status)
                                           if proj.status in PROJECT_STATUSES else 0,
                                           key=f"stat_{proj.id}")
                    tmpl_idx = templates.index(proj.template) if proj.template in templates else 0
                    e_tmpl  = st.selectbox("Template", templates, index=tmpl_idx,
                                           key=f"tmpl_{proj.id}")
                    col_save, col_del, _ = st.columns([1, 1, 4])
                    save   = col_save.form_submit_button("Save")
                    delete = col_del.form_submit_button("Delete", type="secondary")

                if save:
                    closed = db.update_project(proj.id, e_desc, e_vat, e_tmpl, e_stat, e_start)
                    msg = "Updated."
                    if closed:
                        msg += f" {closed} project code(s) automatically set to Completed."
                    st.success(msg)
                    st.cache_data.clear()
                    st.rerun()

                if delete:
                    invoices = db.get_invoices(project_name=proj.name)
                    if invoices:
                        st.error(f"Cannot delete — {len(invoices)} invoice(s) linked to this project.")
                    else:
                        db.delete_project(proj.id)
                        st.session_state["_proj_msg"] = f"Deleted '{proj.name}'."
                        st.cache_data.clear()
                        st.rerun()

                # ---- Budget breakdown by project codes ----
                codes = db.get_project_codes(project_id=proj.id)
                if codes:
                    st.divider()
                    st.caption("**Budget by project code**")
                    code_rows = [
                        {
                            "Code": f"{pc.client_code} / {pc.client_suffix}",
                            "Name": pc.name or "—",
                            "Description": pc.description or "—",
                            "Budget (€)": f"{pc.budget_amount:,.0f}" if pc.budget_amount else "—",
                            "Status": pc.status,
                            "From": pc.date_start or "—",
                            "To": pc.date_end or "open",
                        }
                        for pc in codes
                    ]
                    total_budget = sum(pc.budget_amount for pc in codes)
                    st.dataframe(pd.DataFrame(code_rows), use_container_width=True, hide_index=True)
                    if total_budget:
                        st.caption(f"Total budget across all codes: **€{total_budget:,.0f}**")

                # ---- Billing summary ----
                totals = db.get_project_time_totals(proj.id)
                if totals["billable_charges"] > 0 or totals["invoiced"] > 0:
                    st.divider()
                    st.caption("**Billing summary**")
                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("Billable charges (€)", f"{totals['billable_charges']:,.2f}")
                    s2.metric("Write-offs (€)",       f"{totals['write_offs']:,.2f}")
                    s3.metric("Net billable (€)",     f"{totals['net_charges']:,.2f}")
                    s4.metric("Invoiced net (€)",     f"{totals['invoiced']:,.2f}")

# ==================================================================
# TAB 3 — ADDRESSES
# ==================================================================

with tab_addresses:
    st.subheader("Addresses")

    if _msg := st.session_state.pop("_addr_msg", None):
        st.success(_msg)

    clients = db.get_clients(exclude_types=["internal"])
    if not clients:
        st.info("Add a client first.")
        st.stop()

    selected_client_addr = st.selectbox(
        "Client", [c.name for c in clients], key="addr_client_select"
    )
    client_addr = next(c for c in clients if c.name == selected_client_addr)

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
