"""
Page 9 — Time Tracking.

Tabs:
  Import       — upload fixed-format CSV; validate & import
  Entries      — browse/filter raw time entries; delete by batch
  Rollup       — per-code budget vs billable vs write-offs vs invoiced (period-filtered)
  Team Summary — cross-client consultant summary with project breakdown
  Consultant Groups — manage group assignments
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import backend.db as db
from shared.gap_report import build_gap_excel
from shared.config import load_office_codes
from shared.ui import dataframe_with_total

_OFFICE_CODES = load_office_codes()

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

tab_import, tab_entries, tab_rollup, tab_summary, tab_groups = st.tabs(
    ["Import", "Entries", "Rollup", "Team Summary", "Consultant Teams"]
)

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
        df = None
        for _enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
            try:
                uploaded.seek(0)
                df = pd.read_csv(uploaded, dtype={"client_suffix": str}, encoding=_enc)
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                st.error(f"Could not read file: {e}")
                st.stop()
        if df is None:
            st.error("Could not decode file — unexpected encoding. Try re-saving the CSV as UTF-8.")
            st.stop()

        # Validate required columns
        missing = REQUIRED_COLS - set(df.columns)
        if missing:
            st.error(f"Missing columns: {', '.join(sorted(missing))}")
            st.stop()

        st.write(f"**{len(df)} rows** found. Preview:")
        st.dataframe(df.head(10), use_container_width=True)

        # Pre-flight gap analysis
        rc_df = df.groupby(["client_code", "client_suffix"]).size().reset_index(name="n")
        rc = {(str(r["client_code"]), str(r["client_suffix"])): r["n"] for _, r in rc_df.iterrows()}

        pairs_list = list(rc.keys())
        gaps = db.analyse_csv_gaps(pairs_list)

        # Classify missing_client entries into three buckets
        # 0009 = internal overhead; 0478 = managed CY (need proper setup); everything else = quick-setup candidates
        SKIP_PREFIXES = ("0009", "0478")
        quick_candidates = [
            i for i in gaps["missing_client"]
            if not any(i["client_code"].startswith(p) for p in SKIP_PREFIXES)
        ]
        needs_manual = [
            i for i in gaps["missing_client"]
            if i["client_code"].startswith("0478")
        ]
        intl = [i for i in gaps["missing_client"] if i["is_internal"]]

        n_miss = len(gaps["missing_code"]) + len(gaps["missing_client"])
        matched_rows = sum(rc.get(p, 0) for p in gaps["matched"])
        unmatched_rows = len(df) - matched_rows

        if n_miss == 0:
            st.success(f"All {len(gaps['matched'])} code(s) matched — **{len(df)} row(s)** ready to import.")
        else:
            st.warning(
                f"**{n_miss} unmatched code(s)** found — "
                f"**{unmatched_rows} row(s) will be skipped** until those codes are set up. "
                f"{matched_rows} row(s) from {len(gaps['matched'])} matched code(s) will import."
            )

            # ── Quick Setup (unknown external codes — not 0009 or 0478) ──────
            if quick_candidates:
                st.markdown(
                    f"**{len(quick_candidates)} unknown external code(s)** — "
                    "not a CY managed client (0478) or internal overhead (0009). "
                    "Click below to auto-create placeholder client, project, and project code records "
                    "so these rows import immediately."
                )
                st.dataframe(pd.DataFrame([
                    {
                        "Client code":  i["client_code"],
                        "Office":       _OFFICE_CODES.get(i["client_code"][:4], "Unknown"),
                        "Suffix":       i["client_suffix"],
                        "Rows":         rc.get((i["client_code"], i["client_suffix"]), 0),
                        "Will create":  (
                            f"{i['client_code']}_Default_Client / "
                            f"{i['client_code']}_Default_Project / "
                            f"{i['client_code']}_{i['client_suffix']}_Default_SuffixCode"
                        ),
                    }
                    for i in sorted(quick_candidates, key=lambda x: x["client_code"])
                ]), use_container_width=True, hide_index=True)

                if st.button(
                    f"Auto-create placeholder records for {len(quick_candidates)} code(s)",
                    type="secondary",
                    key="btn_quick_setup",
                ):
                    result = db.quick_setup_external_codes(quick_candidates)
                    st.success(
                        f"Done — {result['created_clients']} client(s), "
                        f"{result['created_projects']} project(s), "
                        f"{result['created_codes']} code(s) created. "
                        "Re-analysing gaps…"
                    )
                    st.rerun()

            # ── Group A — client exists, missing project code ─────────────────
            if gaps["missing_code"]:
                with st.expander(
                    f"Group A — {len(gaps['missing_code'])} code(s): client exists, just add the Project Code (page 5 — Project Codes)"
                ):
                    st.dataframe(pd.DataFrame([
                        {
                            "Client": f"{i['client_name']} ({i['client_code']})",
                            "Suffix": i["client_suffix"],
                            "Rows": rc.get((i["client_code"], i["client_suffix"]), 0),
                            "Existing projects": " | ".join(i["existing_projects"]),
                        }
                        for i in sorted(gaps["missing_code"], key=lambda x: x["client_code"])
                    ]), use_container_width=True, hide_index=True)

            # ── Group B — needs full manual setup ────────────────────────────
            if needs_manual or intl:
                with st.expander(
                    f"Group B — {len(needs_manual) + len(intl)} code(s): add Client + Project + Code via page 4 — Add New Project  "
                    f"[{len(needs_manual)} managed CY, {len(intl)} internal/overhead]"
                ):
                    if needs_manual:
                        st.caption(f"**Managed CY clients — 0478xxx ({len(needs_manual)}) — set up via 4. Add New Project**")
                        st.dataframe(pd.DataFrame([
                            {"Client code": i["client_code"],
                             "Office": _OFFICE_CODES.get(i["client_code"][:4], "Unknown"),
                             "Suffix": i["client_suffix"],
                             "Rows": rc.get((i["client_code"], i["client_suffix"]), 0)}
                            for i in sorted(needs_manual, key=lambda x: x["client_code"])
                        ]), use_container_width=True, hide_index=True)
                    if intl:
                        st.caption(f"**Internal / overhead 0009xxx codes ({len(intl)}) — add only if you want to track them**")
                        st.dataframe(pd.DataFrame([
                            {"Client code": i["client_code"], "Suffix": i["client_suffix"],
                             "Rows": rc.get((i["client_code"], i["client_suffix"]), 0)}
                            for i in sorted(intl, key=lambda x: x["client_code"])
                        ]), use_container_width=True, hide_index=True)

            excel_bytes = build_gap_excel(gaps, rc)
            st.download_button(
                label="Download gap report (Excel)",
                data=excel_bytes,
                file_name=f"gap_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.info(f"**{matched_rows if n_miss else len(df)}** row(s) will be attempted for import.")

        batch_ref = f"{uploaded.name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        def _flt(v) -> float:
            """Convert a value to float, tolerating comma thousands-separators and surrounding spaces."""
            try:
                return float(str(v).replace(",", "").strip()) if v not in (None, "", "nan") else 0.0
            except (ValueError, TypeError):
                return 0.0

        if st.button("Confirm Import", type="primary"):
            entries = []
            for _, row in df.iterrows():
                entries.append({
                    "period":        str(int(row["period"])),
                    "emp_nbr":       str(row["emp_nbr"]),
                    "consultant":    str(row.get("name_fam_last_first", "")),
                    "client_code":   str(row["client_code"]),
                    "client_suffix": str(row["client_suffix"]),
                    "total_hours":   _flt(row.get("total_hours", 0)),
                    "non_z_hours":   _flt(row.get("non_z_hours", 0)),
                    "z_hours":       _flt(row.get("z_hours", 0)),
                    "total_charges": _flt(row.get("total_charges", 0)),
                    "non_z_charges": _flt(row.get("non_z_charges", 0)),
                    "z_charges":     _flt(row.get("z_charges", 0)),
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

    _te_all_clients = db.get_clients()
    if not _te_all_clients:
        st.info("No clients yet.")
        st.stop()

    # Row 1 — Client (multi), Type (multi), Country (multi), period, billable
    _te_all_types     = sorted({c.client_type for c in _te_all_clients if c.client_type})
    _te_all_countries = sorted({c.country for c in _te_all_clients if c.country})
    fcols = st.columns([3, 2, 2, 1, 1, 1])
    f_clients  = fcols[0].multiselect("Client", [c.name for c in _te_all_clients], key="te_client_filter")
    f_types    = fcols[1].multiselect("Client Type", _te_all_types, key="te_type_filter")
    f_countries= fcols[2].multiselect("Country", _te_all_countries, key="te_country_filter")
    f_period_from = fcols[3].text_input("Period from", placeholder="yyyymm", key="te_pf")
    f_period_to   = fcols[4].text_input("Period to",   placeholder="yyyymm", key="te_pt")
    f_billable    = fcols[5].checkbox("Billable only", key="te_bill")

    # Derive filtered client set for project multiselect
    _te_visible_clients = [
        c for c in _te_all_clients
        if (not f_clients or c.name in f_clients)
        and (not f_types or c.client_type in f_types)
        and (not f_countries or c.country in f_countries)
    ]
    _te_client_ids = {c.id for c in _te_visible_clients}

    # Row 2 — Project (multi from visible clients), Consultant Team, Consultant
    _all_cg = db.get_consultant_groups()
    _all_groups = sorted({cg["group_name"] for cg in _all_cg})
    r2cols = st.columns([3, 2, 4])
    _te_all_projects = db.get_projects() if not f_clients and not f_types and not f_countries else []
    if _te_visible_clients:
        _te_proj_list: list = []
        for _c in _te_visible_clients:
            _te_proj_list.extend(db.get_projects(client_id=_c.id))
    else:
        _te_proj_list = []
    f_projects = r2cols[0].multiselect("Project", [p.name for p in _te_proj_list], key="te_project_filter")
    f_group = r2cols[1].selectbox("Consultant Team", ["All"] + _all_groups, key="te_group_filter")
    _consultants_in_group = (
        [cg["consultant"] for cg in _all_cg]
        if f_group == "All"
        else [cg["consultant"] for cg in _all_cg if cg["group_name"] == f_group]
    )
    f_consultants = r2cols[2].multiselect("Consultant(s)", sorted(_consultants_in_group),
                                           key="te_consultant_filter")

    # Fetch and filter entries
    _selected_proj_ids = [p.id for p in _te_proj_list if p.name in f_projects] if f_projects else None
    if _selected_proj_ids and len(_selected_proj_ids) == 1:
        entries = db.get_time_entries(
            project_id=_selected_proj_ids[0],
            period_from=f_period_from or None,
            period_to=f_period_to or None,
            consultants=f_consultants if f_consultants else None,
            include_internal=not f_billable,
        )
    else:
        entries = db.get_time_entries(
            period_from=f_period_from or None,
            period_to=f_period_to or None,
            consultants=f_consultants if f_consultants else None,
            include_internal=not f_billable,
        )
        # Apply multi-project and client filters in Python
        if _selected_proj_ids:
            entries = [e for e in entries if e.project_id in _selected_proj_ids]
        elif _te_client_ids and (f_clients or f_types or f_countries):
            _te_proj_ids_from_clients = {p.id for p in _te_proj_list}
            entries = [e for e in entries if e.project_id in _te_proj_ids_from_clients]

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

    # Client Type + Country pre-filters to narrow the Client list
    _all_types     = sorted({c.client_type for c in clients if c.client_type})
    _all_countries = sorted({c.country for c in clients if c.country})
    pf_cols = st.columns([2, 2, 2, 2, 1, 1])
    r_type    = pf_cols[0].selectbox("Client Type", ["All"] + _all_types, key="ru_type")
    r_country = pf_cols[1].selectbox("Country",     ["All"] + _all_countries, key="ru_country")

    visible_clients = [
        c for c in clients
        if (r_type == "All" or c.client_type == r_type)
        and (r_country == "All" or c.country == r_country)
    ]
    if not visible_clients:
        st.info("No clients match the selected Type / Country.")
        st.stop()

    r_client   = pf_cols[2].selectbox("Client", [c.name for c in visible_clients], key="ru_client")
    client_obj = next(c for c in visible_clients if c.name == r_client)

    projects = db.get_projects(client_id=client_obj.id)
    if not projects:
        st.info("No projects for this client.")
        st.stop()

    r_project   = pf_cols[3].selectbox("Project", [p.name for p in projects], key="ru_project")
    project_obj = next(p for p in projects if p.name == r_project)

    r_period_from = pf_cols[4].text_input("Period from", placeholder="yyyymm", key="ru_pf")
    r_period_to   = pf_cols[5].text_input("Period to",   placeholder="yyyymm", key="ru_pt")

    summary  = db.get_time_summary(project_obj.id)
    totals   = db.get_project_time_totals(project_obj.id)
    invoices = db.get_invoices(project_id=project_obj.id)
    invoiced = sum(i.amount for i in invoices)

    # Project-level metrics (all-time)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Billable charges (€)", f"{totals['billable_charges']:,.0f}")
    m2.metric("Write-offs (€)",       f"{totals['write_offs']:,.0f}")
    m3.metric("Net billable (€)",     f"{totals['net_charges']:,.0f}")
    m4.metric("Invoiced (€)",         f"{invoiced:,.0f}")

    st.divider()

    # View toggle: current vs year-by-year
    ru_view = st.radio("View", ["By Code (current)", "Year-by-Year"], horizontal=True, key="ru_view")

    if not summary:
        st.info("No project codes or time entries for this project yet.")
    else:
        if ru_view == "By Code (current)":
            _ru_num = ["Budget (€)", "Billable (€)", "Write-offs (€)", "Net (€)", "Remaining (€)"]
            ru_rows = []
            for s in summary:
                budget = s["budget_amount"] or 0.0
                ru_rows.append({
                    "Code":          s["client_code"] + " / " + s["client_suffix"],
                    "Name":          s["name"],
                    "Budget (€)":    float(budget),
                    "Billable (€)":  float(s["non_z_charges"]),
                    "Write-offs (€)":float(s["write_off_amount"]),
                    "Net (€)":       float(s["net_charges"]),
                    "Remaining (€)": float(budget - s["net_charges"]) if budget else 0.0,
                })
            ru_df = pd.DataFrame(ru_rows)
            _tot = {c: ru_df[c].sum() if c in _ru_num else ("TOTAL" if c == "Code" else "")
                    for c in ru_df.columns}
            dataframe_with_total(ru_df, _tot, {c: "{:,.0f}" for c in _ru_num})
        else:
            yr_data = db.get_time_summary_by_year(project_obj.id)
            if not yr_data:
                st.info("No time entries recorded for this project yet.")
            else:
                yby_df = pd.DataFrame(yr_data)
                yby_df["Code"] = yby_df["client_code"] + " / " + yby_df["client_suffix"]
                pivot = yby_df.pivot_table(
                    index="Code", columns="year",
                    values=["billable_hrs", "billable_charges"],
                    aggfunc="sum", fill_value=0,
                )
                pivot.columns = [f"{v} {yr}" for v, yr in pivot.columns]
                pivot = pivot.reset_index()
                hr_cols  = [c for c in pivot.columns if "billable_hrs" in c]
                chg_cols = [c for c in pivot.columns if "billable_charges" in c]
                _tot_yby = {"Code": "TOTAL"}
                for c in hr_cols + chg_cols:
                    _tot_yby[c] = pivot[c].sum()
                _yby_fmt = {c: "{:,.1f}" for c in hr_cols}
                _yby_fmt.update({c: "{:,.0f}" for c in chg_cols})
                dataframe_with_total(pivot, _tot_yby, _yby_fmt)

        # Period-filtered sections
        entries_all = db.get_time_entries(
            project_id=project_obj.id, include_internal=True,
            period_from=r_period_from.strip() or None,
            period_to=r_period_to.strip() or None,
        )
        z_hours = sum(e.z_hours for e in entries_all)
        _period_note = ""
        if r_period_from or r_period_to:
            _period_note = f" ({r_period_from or '…'} – {r_period_to or '…'})"
            st.caption("*Budget vs actual above is all-time. Period filter applies to sections below.*")
        if z_hours > 0:
            st.caption(f"Internal (non-billable) hours{_period_note}: **{z_hours:,.1f} hrs**")

        if entries_all:
            from collections import defaultdict
            _cg_map = {cg["consultant"]: cg["group_name"] for cg in db.get_consultant_groups()}

            # Breakdown by Group
            _grp_acc: dict = defaultdict(lambda: {"billable_hrs": 0.0, "billable_chg": 0.0})
            # Breakdown by Consultant
            _con_acc: dict = defaultdict(lambda: {"group": "Other", "billable_hrs": 0.0, "billable_chg": 0.0})
            for _e in entries_all:
                _g = _cg_map.get(_e.consultant, "Other")
                _grp_acc[_g]["billable_hrs"] += _e.non_z_hours
                _grp_acc[_g]["billable_chg"] += _e.non_z_charges
                _con_acc[_e.consultant]["group"] = _g
                _con_acc[_e.consultant]["billable_hrs"] += _e.non_z_hours
                _con_acc[_e.consultant]["billable_chg"] += _e.non_z_charges

            grp_rows = [
                {"Consultant Team": grp, "Bill Hrs": v["billable_hrs"], "Bill €": v["billable_chg"]}
                for grp, v in sorted(_grp_acc.items())
                if v["billable_hrs"] > 0 or v["billable_chg"] > 0
            ]
            if grp_rows:
                st.divider()
                st.subheader(f"Breakdown by Consultant Team{_period_note}")
                _grp_df = pd.DataFrame(grp_rows)
                _tot_grp = {"Consultant Team": "TOTAL", "Bill Hrs": _grp_df["Bill Hrs"].sum(),
                            "Bill €": _grp_df["Bill €"].sum()}
                dataframe_with_total(_grp_df, _tot_grp, {"Bill Hrs": "{:,.1f}", "Bill €": "{:,.0f}"})

            # Breakdown by Consultant with optional Consultant Team filter
            con_rows = [
                {"Consultant": con, "Consultant Team": v["group"],
                 "Bill Hrs": v["billable_hrs"], "Bill €": v["billable_chg"]}
                for con, v in sorted(_con_acc.items())
                if v["billable_hrs"] > 0 or v["billable_chg"] > 0
            ]
            if con_rows:
                st.divider()
                _con_all_groups = sorted({r["Consultant Team"] for r in con_rows})
                _con_grp_filter = st.radio(
                    "Consultant Team filter", ["All"] + _con_all_groups,
                    horizontal=True, key="ru_con_grp",
                )
                _filtered_con = [r for r in con_rows
                                  if _con_grp_filter == "All" or r["Consultant Team"] == _con_grp_filter]
                if _filtered_con:
                    st.subheader(f"Breakdown by Consultant{_period_note}")
                    _con_df = pd.DataFrame(_filtered_con)
                    _tot_con = {"Consultant": "TOTAL", "Consultant Team": "",
                                "Bill Hrs": _con_df["Bill Hrs"].sum(),
                                "Bill €": _con_df["Bill €"].sum()}
                    dataframe_with_total(_con_df, _tot_con, {"Bill Hrs": "{:,.1f}", "Bill €": "{:,.0f}"})
                    st.caption("Teams assigned on the Consultant Teams tab; unassigned → 'Other'.")

# ==================================================================
# TAB 4 — TEAM SUMMARY
# ==================================================================

with tab_summary:
    st.subheader("Team Summary")
    st.caption("Cross-client billable summary per consultant, aggregated across all projects.")

    _ts_cg = db.get_consultant_groups()
    _ts_groups = sorted({cg["group_name"] for cg in _ts_cg})

    ts_fcols = st.columns([1, 1, 3])
    ts_period_from = ts_fcols[0].text_input(
        "Period from (yyyymm)", placeholder=f"{datetime.now().year}01", key="ts_pf"
    )
    ts_period_to = ts_fcols[1].text_input(
        "Period to (yyyymm)", placeholder=f"{datetime.now().year}12", key="ts_pt"
    )
    ts_group = ts_fcols[2].radio(
        "Consultant Team", ["All"] + _ts_groups,
        index=(["All"] + _ts_groups).index("Local") if "Local" in _ts_groups else 0,
        horizontal=True, key="ts_group",
    )
    _ts_opts = (
        [cg["consultant"] for cg in _ts_cg] if ts_group == "All"
        else [cg["consultant"] for cg in _ts_cg if cg["group_name"] == ts_group]
    )
    ts_consultants = st.multiselect(
        "Consultant(s) (leave blank for all)", sorted(_ts_opts), key="ts_consultants"
    )

    _ts_group_filter = None if ts_group == "All" else [ts_group]
    ts_rows = db.get_team_time_summary(
        period_from=ts_period_from.strip() or None,
        period_to=ts_period_to.strip() or None,
        group_names=_ts_group_filter,
    )

    if not ts_rows:
        st.info("No time entries for the selected period / group.")
    else:
        ts_df = pd.DataFrame(ts_rows)
        if ts_consultants:
            ts_df = ts_df[ts_df["consultant"].isin(ts_consultants)]
        if ts_df.empty:
            st.info("No data for the selected consultants.")
        else:
            # Consultant summary aggregated across all periods
            st.subheader("By Consultant")
            cons_df = (
                ts_df.groupby(["consultant", "group_name"], as_index=False)
                .agg(
                    Bill_Hrs = ("billable_hrs",     "sum"),
                    Bill_EUR = ("billable_charges", "sum"),
                    Int_Hrs  = ("internal_hrs",     "sum"),
                    Tot_Hrs  = ("total_hrs",        "sum"),
                )
            )
            cons_df["Bill_pct"] = (
                cons_df["Bill_Hrs"] / cons_df["Tot_Hrs"].replace(0, float("nan")) * 100
            ).round(1)
            _t = cons_df[["Bill_Hrs", "Bill_EUR", "Int_Hrs", "Tot_Hrs"]].sum()
            _tot_pct = _t["Bill_Hrs"] / _t["Tot_Hrs"] * 100 if _t["Tot_Hrs"] > 0 else 0.0
            _cons_display = cons_df.rename(columns={
                "consultant": "Consultant", "group_name": "Consultant Team",
                "Bill_Hrs": "Bill Hrs", "Bill_EUR": "Bill €",
                "Int_Hrs": "Int Hrs", "Tot_Hrs": "Tot Hrs", "Bill_pct": "Bill %",
            })
            _tot_cons = {
                "Consultant": "TOTAL", "Consultant Team": "",
                "Bill Hrs": _t["Bill_Hrs"], "Bill €": _t["Bill_EUR"],
                "Int Hrs": _t["Int_Hrs"], "Tot Hrs": _t["Tot_Hrs"],
                "Bill %": round(_tot_pct, 1),
            }
            _cons_fmt = {c: "{:,.1f}" for c in ["Bill Hrs", "Int Hrs", "Tot Hrs"]}
            _cons_fmt["Bill €"] = "{:,.0f}"
            _cons_fmt["Bill %"] = "{:.1f}"
            dataframe_with_total(_cons_display, _tot_cons, _cons_fmt)

            # By Consultant & Project
            st.divider()
            st.subheader("By Consultant & Project")
            proj_rows = db.get_team_time_summary_by_project(
                period_from=ts_period_from.strip() or None,
                period_to=ts_period_to.strip() or None,
                group_names=_ts_group_filter,
            )
            if proj_rows:
                proj_df = pd.DataFrame(proj_rows)
                if ts_consultants:
                    proj_df = proj_df[proj_df["consultant"].isin(ts_consultants)]
                if not proj_df.empty:
                    _tot_proj_hrs = proj_df["billable_hrs"].sum()
                    _tot_proj_chg = proj_df["billable_charges"].sum()
                    proj_display = proj_df.rename(columns={
                        "consultant": "Consultant", "group_name": "Consultant Team",
                        "project": "Project", "client": "Client",
                        "billable_hrs": "Bill Hrs", "billable_charges": "Bill €",
                    })
                    _tot_proj_d = {"Consultant": "TOTAL", "Consultant Team": "", "Project": "", "Client": "",
                                   "Bill Hrs": _tot_proj_hrs, "Bill €": _tot_proj_chg}
                    dataframe_with_total(proj_display, _tot_proj_d, {"Bill Hrs": "{:,.1f}", "Bill €": "{:,.0f}"})

            # Period breakdown pivot
            st.divider()
            st.subheader("Period Breakdown")
            _pgcols = st.columns([2, 2])
            ts_gran   = _pgcols[0].radio("Granularity", ["Month", "Quarter", "Year"],
                                          horizontal=True, key="ts_gran")
            ts_metric = _pgcols[1].radio("Show", ["Bill Hrs", "Bill €"],
                                          horizontal=True, key="ts_metric")

            def _ts_label(p: str, gran: str) -> str:
                try:
                    y, m = int(str(p)[:4]), int(str(p)[4:6])
                    if gran == "Year":    return str(y)
                    if gran == "Quarter": return f"{y}-Q{(m-1)//3+1}"
                    return f"{y}-{m:02d}"
                except (ValueError, IndexError):
                    return str(p)

            ts_df["label"] = ts_df["period"].apply(lambda p: _ts_label(str(p), ts_gran))
            _ts_col = "billable_hrs" if ts_metric == "Bill Hrs" else "billable_charges"
            piv = ts_df.groupby(["consultant", "label"])[_ts_col].sum().reset_index()
            piv_wide = piv.pivot_table(index="consultant", columns="label", values=_ts_col, fill_value=0)
            piv_wide = piv_wide.reindex(sorted(piv_wide.columns), axis=1)
            piv_wide["TOTAL"] = piv_wide.sum(axis=1)
            # Totals row
            _piv_fmt = "{:,.0f}" if ts_metric == "Bill €" else "{:,.1f}"
            piv_wide_display = piv_wide.reset_index().rename(columns={"consultant": "Consultant"})
            _piv_num_cols = [c for c in piv_wide_display.columns if c != "Consultant"]
            _piv_tot = {c: piv_wide_display[c].sum() if c in _piv_num_cols else "TOTAL"
                        for c in piv_wide_display.columns}
            dataframe_with_total(piv_wide_display, _piv_tot, {c: _piv_fmt for c in _piv_num_cols})

# ==================================================================
# TAB 5 — CONSULTANT GROUPS
# ==================================================================

with tab_groups:
    st.subheader("Consultant Teams")
    st.caption(
        "Assign each consultant to **Local**, **ICEE**, or **Other**. "
        "New consultants are added automatically (as 'Other') when time entries are imported."
    )

    groups = db.get_consultant_groups()

    if not groups:
        st.info("No consultants yet. Import time entries to populate the list.")
    else:
        GROUP_OPTIONS = ["Local", "ICEE", "Other"]
        _cg_group_names = sorted({g["group_name"] for g in groups})
        _cg_view = st.radio("Show team", _cg_group_names, horizontal=True, key="cg_view_group")
        _cg_visible = [g for g in groups if g["group_name"] == _cg_view]

        STATUS_OPTIONS = ["Active", "Inactive"]
        for g in sorted(_cg_visible, key=lambda x: x["consultant"]):
            _is_local = g["group_name"] == "Local"
            _status = g.get("status", "Active")
            _label = g["consultant"] if not _is_local else f"{g['consultant']} ({_status})"
            with st.expander(_label, expanded=False):
                with st.form(f"cg_{g['id']}"):
                    col_grp, col_emp, col_status = st.columns(3)
                    new_group = col_grp.selectbox(
                        "Consultant Team", GROUP_OPTIONS,
                        index=GROUP_OPTIONS.index(g["group_name"]) if g["group_name"] in GROUP_OPTIONS else 2,
                        key=f"cg_grp_{g['id']}",
                    )
                    new_emp = col_emp.text_input("emp_nbr", value=g.get("emp_nbr") or "",
                                                 key=f"cg_emp_{g['id']}")
                    if _is_local:
                        new_status = col_status.selectbox(
                            "Employment Status", STATUS_OPTIONS,
                            index=STATUS_OPTIONS.index(_status) if _status in STATUS_OPTIONS else 0,
                            key=f"cg_status_{g['id']}",
                        )
                    else:
                        col_status.markdown("&nbsp;")
                        new_status = None
                    if st.form_submit_button("Save"):
                        db.upsert_consultant_group(
                            consultant=g["consultant"],
                            group_name=new_group,
                            emp_nbr=new_emp or None,
                            status=new_status,
                        )
                        st.success("Saved.")
                        st.rerun()

    st.divider()
    st.subheader("Add new consultant")
    with st.form("cg_add"):
        na_name  = st.text_input("Consultant name (Last, First)")
        na_group = st.selectbox("Consultant Team", ["Local", "ICEE", "Other"])
        na_emp   = st.text_input("emp_nbr (optional)")
        if st.form_submit_button("Add"):
            if na_name.strip():
                db.upsert_consultant_group(na_name.strip(), na_group, na_emp.strip() or None)
                st.success(f"Added {na_name}.")
                st.rerun()
            else:
                st.error("Consultant name is required.")
