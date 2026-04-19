"""
Page 6 — Time Tracking.

Three tabs:
  Import  — upload fixed-format CSV; validate & import
  Entries — browse/filter raw time entries; delete by batch
  Rollup  — per-code budget vs billable vs write-offs vs invoiced
"""
import sys
import os
from datetime import datetime, timezone

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

st.title("Time Tracking")

tab_import, tab_entries, tab_rollup, tab_groups = st.tabs(["Import", "Entries", "Rollup", "Consultant Groups"])

# Expected CSV columns (fixed format matching sample_time_sheet.csv)
REQUIRED_COLS = {
    "period", "emp_nbr", "name_fam_last_first",
    "client_code", "client_suffix",
    "total_hours", "non_z_hours", "z_hours",
    "total_charges", "non_z_charges", "z_charges",
}

# ==================================================================
# TAB 1 — IMPORT
# ==================================================================

with tab_import:
    st.subheader("Import Time Charges")
    st.caption(
        "Upload a CSV in the standard timesheet extract format. "
        "Each row is matched to a project code by **client_code + client_suffix**. "
        "Rows already in the database (same period / person / code) are skipped automatically."
    )

    uploaded = st.file_uploader("Choose CSV file", type=["csv"])

    if uploaded:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        # Validate required columns
        missing = REQUIRED_COLS - set(df.columns)
        if missing:
            st.error(f"Missing columns: {', '.join(sorted(missing))}")
            st.stop()

        st.write(f"**{len(df)} rows** found. Preview:")
        st.dataframe(df.head(10), use_container_width=True)

        # Pre-flight: check which (client_code, client_suffix) pairs are unrecognised
        pairs = df[["client_code", "client_suffix"]].drop_duplicates()
        unmatched_pairs = []
        for _, row in pairs.iterrows():
            if db.get_project_code_by_keys(str(row["client_code"]), str(row["client_suffix"])) is None:
                unmatched_pairs.append(f"{row['client_code']} / {row['client_suffix']}")

        if unmatched_pairs:
            st.warning(
                f"**{len(unmatched_pairs)} unmatched code(s)** — these rows will NOT be imported "
                "(add them on the Project Codes page first):\n\n"
                + "\n".join(f"- {p}" for p in unmatched_pairs)
            )

        matched_count = len(df) - len(
            df[df.apply(
                lambda r: f"{r['client_code']} / {r['client_suffix']}" in unmatched_pairs, axis=1
            )]
        )
        st.info(f"**{matched_count}** row(s) will be attempted for import.")

        batch_ref = f"{uploaded.name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        if st.button("Confirm Import", type="primary"):
            entries = []
            for _, row in df.iterrows():
                entries.append({
                    "period":        str(int(row["period"])),
                    "emp_nbr":       str(row["emp_nbr"]),
                    "consultant":    str(row.get("name_fam_last_first", "")),
                    "client_code":   str(row["client_code"]),
                    "client_suffix": str(row["client_suffix"]),
                    "total_hours":   float(row.get("total_hours", 0) or 0),
                    "non_z_hours":   float(row.get("non_z_hours", 0) or 0),
                    "z_hours":       float(row.get("z_hours", 0) or 0),
                    "total_charges": float(row.get("total_charges", 0) or 0),
                    "non_z_charges": float(row.get("non_z_charges", 0) or 0),
                    "z_charges":     float(row.get("z_charges", 0) or 0),
                    "description":   str(row.get("description", "") or ""),
                    "batch_ref":     batch_ref,
                })

            result = db.add_time_entries_bulk(entries)
            # Register new consultants in consultant_groups (default group = Other)
            for e in entries:
                if e.get("emp_nbr") and e.get("consultant"):
                    db.ensure_consultant_group(e["emp_nbr"], e["consultant"])
            st.success(
                f"Import complete — "
                f"**{result['inserted']} inserted**, "
                f"{result['skipped']} duplicate(s) skipped, "
                f"{result['unmatched']} unmatched."
            )
            st.caption(f"Batch reference: `{batch_ref}`")

# ==================================================================
# TAB 2 — ENTRIES
# ==================================================================

with tab_entries:
    st.subheader("Time Entries")

    clients = db.get_clients()
    if not clients:
        st.info("No clients yet.")
        st.stop()

    # Filters
    fcols = st.columns([2, 2, 1, 1, 1])
    f_client = fcols[0].selectbox("Client", ["All"] + [c.name for c in clients],
                                  key="te_client_filter")
    client_obj = next((c for c in clients if c.name == f_client), None)

    projects = db.get_projects(client_id=client_obj.id) if client_obj else []
    f_project = fcols[1].selectbox(
        "Project", ["All"] + [p.name for p in projects], key="te_project_filter"
    )
    project_obj = next((p for p in projects if p.name == f_project), None)

    f_period_from = fcols[2].text_input("Period from", placeholder="yyyymm", key="te_pf")
    f_period_to   = fcols[3].text_input("Period to",   placeholder="yyyymm", key="te_pt")
    f_billable    = fcols[4].checkbox("Billable only", key="te_bill")

    entries = db.get_time_entries(
        project_id=project_obj.id if project_obj else None,
        period_from=f_period_from or None,
        period_to=f_period_to or None,
        include_internal=not f_billable,
    )

    if not entries:
        st.info("No entries match the current filters.")
    else:
        rows = [
            {
                "Period":       e.period,
                "Person":       e.consultant,
                "Client code":  e.client_code,
                "Suffix":       e.client_suffix,
                "Tot hrs":      e.total_hours,
                "Bill hrs":     e.non_z_hours,
                "Int hrs":      e.z_hours,
                "Bill €":       e.non_z_charges,
                "Int €":        e.z_charges,
                "Batch":        e.batch_ref,
            }
            for e in entries
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(f"{len(entries)} row(s)")

        st.divider()
        st.subheader("Delete a batch")
        batches = sorted({e.batch_ref for e in entries if e.batch_ref})
        if batches:
            del_batch = st.selectbox("Batch reference", batches, key="te_del_batch")
            batch_count = sum(1 for e in entries if e.batch_ref == del_batch)
            st.warning(f"This will delete **{batch_count}** row(s).")
            if st.button("Delete batch", type="secondary"):
                deleted = db.delete_time_batch(del_batch)
                st.success(f"Deleted {deleted} row(s) from batch `{del_batch}`.")
                st.rerun()
        else:
            st.info("No batch references found in current results.")

# ==================================================================
# TAB 3 — ROLLUP
# ==================================================================

with tab_rollup:
    st.subheader("Billability Rollup")

    clients = db.get_clients()
    if not clients:
        st.info("No clients yet.")
        st.stop()

    rcols = st.columns(2)
    r_client = rcols[0].selectbox("Client", [c.name for c in clients], key="ru_client")
    client_obj = next(c for c in clients if c.name == r_client)

    projects = db.get_projects(client_id=client_obj.id)
    if not projects:
        st.info("No projects for this client.")
        st.stop()

    r_project = rcols[1].selectbox("Project", [p.name for p in projects], key="ru_project")
    project_obj = next(p for p in projects if p.name == r_project)

    summary  = db.get_time_summary(project_obj.id)
    totals   = db.get_project_time_totals(project_obj.id)
    invoices = db.get_invoices(project_id=project_obj.id)
    invoiced = sum(i.amount for i in invoices)

    # Project-level metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Billable charges (€)", f"{totals['billable_charges']:,.2f}")
    m2.metric("Write-offs (€)",       f"{totals['write_offs']:,.2f}")
    m3.metric("Net billable (€)",     f"{totals['net_charges']:,.2f}")
    m4.metric("Invoiced net (€)",     f"{invoiced:,.2f}")

    st.divider()

    if not summary:
        st.info("No project codes or time entries for this project yet.")
    else:
        rows = []
        for s in summary:
            budget    = s["budget_amount"]
            remaining = (budget - s["net_charges"]) if budget else None
            rows.append({
                "Code":          s["client_code"] + " / " + s["client_suffix"],
                "Name":          s["name"],
                "Budget (€)":   f"{budget:,.2f}" if budget else "—",
                "Billable (€)": f"{s['non_z_charges']:,.2f}",
                "Write-offs (€)": f"{s['write_off_amount']:,.2f}",
                "Net bill. (€)": f"{s['net_charges']:,.2f}",
                "Remaining (€)": f"{remaining:,.2f}" if remaining is not None else "—",
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Internal hours section
        entries_all = db.get_time_entries(project_id=project_obj.id, include_internal=True)
        z_hours = sum(e.z_hours for e in entries_all)
        if z_hours > 0:
            st.caption(f"Internal (non-billable) hours on this project: **{z_hours:,.1f} hrs**")

        # Local / ICEE / Other breakdown
        group_summary = db.get_time_summary_by_group(project_obj.id)
        if group_summary:
            st.divider()
            st.subheader("Breakdown by Consultant Group")
            grp_rows = [
                {
                    "Group":         g["group_name"],
                    "Billable hrs":  f"{g['billable_hrs']:,.1f}" if g["billable_hrs"] else "—",
                    "Billable (€)":  f"{g['billable_chg']:,.2f}" if g["billable_chg"] else "—",
                }
                for g in group_summary
            ]
            st.dataframe(pd.DataFrame(grp_rows), use_container_width=True, hide_index=True)
            st.caption("Groups are assigned on the Consultant Groups tab. "
                       "Unassigned consultants appear as 'Other'.")

# ==================================================================
# TAB 4 — CONSULTANT GROUPS
# ==================================================================

with tab_groups:
    st.subheader("Consultant Groups")
    st.caption(
        "Assign each consultant to **Local**, **ICEE**, or **Other**. "
        "New consultants are added automatically (as 'Other') when time entries are imported. "
        "Run `scripts/seed_consultant_groups.py` to pre-populate from the ICEE Plan CY Excel."
    )

    groups = db.get_consultant_groups()

    if not groups:
        st.info("No consultant groups yet. Import time entries or run the seed script.")
    else:
        # Editable table
        GROUP_OPTIONS = ["Local", "ICEE", "Other"]
        for g in groups:
            with st.expander(f"{g['consultant']} — **{g['group_name']}**", expanded=False):
                with st.form(f"cg_{g['id']}"):
                    col_grp, col_emp = st.columns(2)
                    new_group = col_grp.selectbox(
                        "Group", GROUP_OPTIONS,
                        index=GROUP_OPTIONS.index(g["group_name"]) if g["group_name"] in GROUP_OPTIONS else 2,
                        key=f"cg_grp_{g['id']}",
                    )
                    new_emp = col_emp.text_input("emp_nbr", value=g.get("emp_nbr") or "",
                                                 key=f"cg_emp_{g['id']}")
                    if st.form_submit_button("Save"):
                        db.upsert_consultant_group(
                            consultant=g["consultant"],
                            group_name=new_group,
                            emp_nbr=new_emp or None,
                        )
                        st.success("Saved.")
                        st.rerun()

    st.divider()
    st.subheader("Add new consultant")
    with st.form("cg_add"):
        na_name  = st.text_input("Consultant name (Last, First)")
        na_group = st.selectbox("Group", ["Local", "ICEE", "Other"])
        na_emp   = st.text_input("emp_nbr (optional)")
        if st.form_submit_button("Add"):
            if na_name.strip():
                db.upsert_consultant_group(na_name.strip(), na_group, na_emp.strip() or None)
                st.success(f"Added {na_name}.")
                st.rerun()
            else:
                st.error("Consultant name is required.")
