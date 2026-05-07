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
from shared.gap_report import build_gap_excel
from shared.config import load_office_codes

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
    ["Import", "Entries", "Rollup", "Team Summary", "Consultant Groups"]
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
                    f"Group A — {len(gaps['missing_code'])} code(s): client exists, just add the Project Code (page 5)"
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
                    f"Group B — {len(needs_manual) + len(intl)} code(s): add Client + Project + Code via page 11  "
                    f"[{len(needs_manual)} managed CY, {len(intl)} internal/overhead]"
                ):
                    if needs_manual:
                        st.caption(f"**Managed CY clients — 0478xxx ({len(needs_manual)}) — set up via Add New Project (page 11)**")
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

    clients = db.get_clients()
    if not clients:
        st.info("No clients yet.")
        st.stop()

    # Row 1 — client / project / period / billable
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

    # Row 2 — consultant / group filters (applied in Python after fetch)
    _all_cg = db.get_consultant_groups()
    _all_groups = sorted({cg["group_name"] for cg in _all_cg})
    gcols = st.columns([2, 4])
    f_group = gcols[0].selectbox("Group", ["All"] + _all_groups, key="te_group_filter")
    _consultants_in_group = (
        [cg["consultant"] for cg in _all_cg]
        if f_group == "All"
        else [cg["consultant"] for cg in _all_cg if cg["group_name"] == f_group]
    )
    f_consultants = gcols[1].multiselect("Consultant(s)", sorted(_consultants_in_group),
                                          key="te_consultant_filter")

    entries = db.get_time_entries(
        project_id=project_obj.id if project_obj else None,
        period_from=f_period_from or None,
        period_to=f_period_to or None,
        consultants=f_consultants if f_consultants else None,
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

    rcols = st.columns([2, 2, 1, 1])
    r_client = rcols[0].selectbox("Client", [c.name for c in clients], key="ru_client")
    client_obj = next(c for c in clients if c.name == r_client)

    projects = db.get_projects(client_id=client_obj.id)
    if not projects:
        st.info("No projects for this client.")
        st.stop()

    r_project = rcols[1].selectbox("Project", [p.name for p in projects], key="ru_project")
    project_obj = next(p for p in projects if p.name == r_project)

    r_period_from = rcols[2].text_input("Period from", placeholder="yyyymm", key="ru_pf")
    r_period_to   = rcols[3].text_input("Period to",   placeholder="yyyymm", key="ru_pt")

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

        # Internal hours and group breakdown — period-filtered when filters are set
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

        # Compute group breakdown from period-filtered entries
        if entries_all:
            from collections import defaultdict
            _cg_map = {cg["consultant"]: cg["group_name"] for cg in db.get_consultant_groups()}
            _grp_acc: dict = defaultdict(lambda: {"billable_hrs": 0.0, "billable_chg": 0.0})
            for _e in entries_all:
                _g = _cg_map.get(_e.consultant, "Other")
                _grp_acc[_g]["billable_hrs"] += _e.non_z_hours
                _grp_acc[_g]["billable_chg"] += _e.non_z_charges
            grp_rows = [
                {"Group": grp, "Billable hrs": f"{v['billable_hrs']:,.1f}",
                 "Billable (€)": f"{v['billable_chg']:,.2f}"}
                for grp, v in sorted(_grp_acc.items())
                if v["billable_hrs"] > 0 or v["billable_chg"] > 0
            ]
            if grp_rows:
                st.divider()
                st.subheader(f"Breakdown by Consultant Group{_period_note}")
                st.dataframe(pd.DataFrame(grp_rows), use_container_width=True, hide_index=True)
                st.caption("Groups assigned on the Consultant Groups tab; unassigned → 'Other'.")

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
        "Group", ["All"] + _ts_groups,
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
            cons_df = pd.concat([cons_df, pd.DataFrame([{
                "consultant": "TOTAL", "group_name": "",
                "Bill_Hrs": _t["Bill_Hrs"], "Bill_EUR": _t["Bill_EUR"],
                "Int_Hrs": _t["Int_Hrs"], "Tot_Hrs": _t["Tot_Hrs"],
                "Bill_pct": round(_tot_pct, 1),
            }])], ignore_index=True)
            st.dataframe(
                cons_df.rename(columns={
                    "consultant": "Consultant", "group_name": "Group",
                    "Bill_Hrs": "Bill Hrs", "Bill_EUR": "Bill €",
                    "Int_Hrs": "Int Hrs", "Tot_Hrs": "Tot Hrs", "Bill_pct": "Bill %",
                }),
                use_container_width=True, hide_index=True,
                column_config={
                    "Bill €": st.column_config.NumberColumn(format="€%.2f"),
                    "Bill %": st.column_config.NumberColumn(format="%.1f"),
                },
            )

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
            piv_wide = piv_wide.reset_index()
            _ts_fmt = "€%.0f" if ts_metric == "Bill €" else "%.1f"
            _ts_cc  = {c: st.column_config.NumberColumn(format=_ts_fmt)
                       for c in piv_wide.columns if c != "consultant"}
            st.dataframe(
                piv_wide.rename(columns={"consultant": "Consultant"}),
                use_container_width=True, hide_index=True,
                column_config=_ts_cc,
            )

# ==================================================================
# TAB 5 — CONSULTANT GROUPS
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
