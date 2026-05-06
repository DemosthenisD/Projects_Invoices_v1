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

    # ---- Filters ----
    TYPE_BADGE = {"managed": "🟢", "external": "🔵", "internal": "⚪"}
    rows_with_counts = db.get_clients_with_counts(exclude_types=exclude)

    fcol1, fcol2, fcol3 = st.columns([3, 2, 2])
    name_search   = fcol1.text_input("Search name", placeholder="Type to filter…", key="cl_name_search")
    all_types     = sorted({r["client_type"] for r in rows_with_counts if r["client_type"]})
    type_filter   = fcol2.multiselect("Type", all_types, key="cl_type_filter")
    all_countries = sorted({r["country"] for r in rows_with_counts if r["country"]})
    country_filter = fcol3.multiselect("Country", all_countries, key="cl_country_filter")

    filtered_rows = rows_with_counts
    if name_search:
        filtered_rows = [r for r in filtered_rows if name_search.lower() in r["name"].lower()]
    if type_filter:
        filtered_rows = [r for r in filtered_rows if r["client_type"] in type_filter]
    if country_filter:
        filtered_rows = [r for r in filtered_rows if r["country"] in country_filter]

    # ---- Summary table ----
    if filtered_rows:
        summary_rows = [
            {
                "Status": TYPE_BADGE.get(r["client_type"], ""),
                "Name": r["name"],
                "Code": r["client_code"] or "—",
                "Type": r["client_type"],
                "Country": r["country"] or "—",
                "Name for invoices": r["name_for_invoices"] or "—",
                "Projects": r["total_projects"],
                "Active projects": r["active_projects"],
                "Active codes": r["active_codes"],
            }
            for r in filtered_rows
        ]
        st.caption("🟢 managed · 🔵 external · ⚪ internal")
        st.dataframe(
            pd.DataFrame(summary_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(width="small"),
                "Projects": st.column_config.NumberColumn(width="small"),
                "Active projects": st.column_config.NumberColumn(width="small"),
                "Active codes": st.column_config.NumberColumn(width="small"),
            },
        )
    else:
        st.info("No clients match the selected filters." + ("" if show_internal else " Internal clients are hidden — toggle above to show."))

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

    col_cl, col_st, col_tp = st.columns([3, 2, 2])
    client_options = ["All"] + [c.name for c in clients]
    selected_client = col_cl.selectbox("Client", client_options, key="proj_client_select")
    show_all = selected_client == "All"
    client_obj = None if show_all else next(c for c in clients if c.name == selected_client)

    status_filter = col_st.multiselect(
        "Show statuses", PROJECT_STATUSES, default=["Active"],
        key="proj_status_filter"
    )
    type_filter_proj = col_tp.multiselect(
        "Client type", CLIENT_TYPES, key="proj_type_filter",
        help="Filter projects by their client's type (e.g. hide internal).",
    )

    # ---- Summary table ----
    all_proj_summary = db.get_projects_with_summary(None if show_all else client_obj.id)
    filtered_summary = [
        r for r in all_proj_summary
        if (not status_filter or r["status"] in status_filter)
        and (not type_filter_proj or r.get("client_type") in type_filter_proj)
    ]

    STATUS_PROJ_BADGE = {"Active": "🟢", "On Hold": "🟡", "Completed": "⚫", "Prospect": "🔵"}

    if filtered_summary:
        table_rows = [
            {
                "Status": STATUS_PROJ_BADGE.get(r["status"], ""),
                **( {"Client": r["client_name"]} if show_all else {} ),
                "Project": r["name"],
                "Stage": r["status"],
                "Country": r.get("client_country") or "—",
                "Started": r["date_start"] or "—",
                "VAT %": r["vat_pct"],
                "Codes": r["code_count"],
                "Budget (€)": int(r["total_budget"]),
                "Billable (€)": int(r["billable_charges"]),
                "Write-offs (€)": int(r["write_offs"]),
                "Invoiced (€)": int(r["invoiced"]),
            }
            for r in filtered_summary
        ]
        st.caption("🟢 Active · 🟡 On Hold · ⚫ Completed · 🔵 Prospect")
        st.dataframe(
            pd.DataFrame(table_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(width="small"),
                "VAT %": st.column_config.NumberColumn(format="%.0f%%", width="small"),
                "Codes": st.column_config.NumberColumn(width="small"),
                "Budget (€)": st.column_config.NumberColumn(format="%d", width="medium"),
                "Billable (€)": st.column_config.NumberColumn(format="%d", width="medium"),
                "Write-offs (€)": st.column_config.NumberColumn(format="%d", width="medium"),
                "Invoiced (€)": st.column_config.NumberColumn(format="%d", width="medium"),
            },
        )
        # Totals bar
        t_budget  = sum(r["total_budget"]     for r in filtered_summary)
        t_bill    = sum(r["billable_charges"]  for r in filtered_summary)
        t_wo      = sum(r["write_offs"]        for r in filtered_summary)
        t_inv     = sum(r["invoiced"]          for r in filtered_summary)
        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.metric("Budget (€)",      f"{t_budget:,.0f}")
        tc2.metric("Billable (€)",    f"{t_bill:,.0f}")
        tc3.metric("Write-offs (€)",  f"{t_wo:,.0f}")
        tc4.metric("Invoiced (€)",    f"{t_inv:,.0f}")

        with st.expander("Admin: sync completed project budgets", expanded=False):
            st.caption(
                "For **Completed** projects whose project codes all have a zero budget, "
                "this sets each code's budget to an equal share of the total invoiced amount. "
                "Projects that already have at least one non-zero budget are left untouched."
            )
            if st.button("Run sync now", key="sync_budgets"):
                result = db.sync_completed_project_budgets()
                if result["updated"]:
                    st.success(f"Updated {len(result['updated'])} project(s): " +
                               ", ".join(result["updated"]))
                else:
                    st.info("No projects required updating.")
                if result["skipped_no_codes"]:
                    st.warning("Skipped (no project codes): " +
                               ", ".join(result["skipped_no_codes"]))
                if result["skipped_has_budget"]:
                    st.info("Skipped (budget already set): " +
                            ", ".join(result["skipped_has_budget"]))
                st.cache_data.clear()
    elif all_proj_summary:
        st.info(f"No projects match the selected filters. Clear filters to see all.")
    else:
        st.info("No projects for this client yet." if not show_all else "No projects found.")

    st.divider()

    if show_all:
        st.caption("Select a specific client above to add or edit projects.")
    else:
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

    # ---- Edit / delete a project ----
    all_projects = [] if show_all else db.get_projects(client_id=client_obj.id)
    if all_projects:
        with st.expander("Edit / delete a project", expanded=False):
            proj_names = [p.name for p in all_projects]
            edit_proj_name = st.selectbox(
                "Select project to edit", proj_names, key="edit_proj_sel"
            )
            proj = next(p for p in all_projects if p.name == edit_proj_name)
            templates = _templates()

            with st.form(f"edit_proj_{proj.id}"):
                e_desc  = st.text_area("Description", value=proj.description, height=70)
                e_start = st.text_input("Start date (YYYY-MM-DD)", value=proj.date_start)
                c1, c2 = st.columns(2)
                e_vat   = c1.number_input("VAT %", min_value=0.0, max_value=100.0,
                                          value=proj.vat_pct, step=1.0)
                e_stat  = c2.selectbox(
                    "Status", PROJECT_STATUSES,
                    index=PROJECT_STATUSES.index(proj.status) if proj.status in PROJECT_STATUSES else 0,
                )
                tmpl_idx = templates.index(proj.template) if proj.template in templates else 0
                e_tmpl  = st.selectbox("Template", templates, index=tmpl_idx)
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
