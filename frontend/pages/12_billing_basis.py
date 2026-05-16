"""Page 11 — Billing Basis

Annual billing summary per consultant used as the basis for productivity-bonus calculation.
Supports two input modes:
  • Auto  — aggregates from existing time_entries + write_offs tables
  • Manual — user enters billing amounts directly (matching the Sheet5 D-K layout)

Derived values (grand total, basis for bonus, equivalent hours, productivity bonus %)
are computed on the fly; only the raw amounts are stored.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from datetime import datetime

from backend.db import (
    get_consultant_groups,
    get_billing_basis_year,
    get_billing_basis_year_by_source,
    get_billing_basis,
    get_billing_basis_by_source,
    get_billing_basis_from_time_entries,
    get_monthly_billing_rate_breakdown,
    upsert_billing_basis,
    set_billing_basis_preferred,
    get_billing_basis_summary,
)
from shared.ui import dataframe_with_total, require_auth

require_auth()

st.title("Billing Basis")
st.caption("Annual billing summary per consultant — the basis for productivity-bonus calculation.")

# ---------------------------------------------------------------------------
# Year + group selectors
# ---------------------------------------------------------------------------
current_year = datetime.now().year
col_yr, col_grp = st.columns([2, 3])
year = col_yr.selectbox(
    "Financial Year",
    options=list(range(current_year, current_year - 6, -1)),
    index=0,
)

_all_cg = get_consultant_groups()
_all_groups = sorted({cg["group_name"] for cg in _all_cg})
group_filter = col_grp.radio(
    "Consultant Team",
    ["All"] + _all_groups,
    index=(["All"] + _all_groups).index("Local") if "Local" in _all_groups else 0,
    horizontal=True,
)

# ---------------------------------------------------------------------------
# Helper: compute derived columns for a billing row (dict or BillingBasis)
# ---------------------------------------------------------------------------
def _derive(row: dict) -> dict:
    billed = float(row.get("billed", 0) or 0)
    cpp    = float(row.get("capped_paid_prebill", 0) or 0)
    cup    = float(row.get("capped_unpaid_prebill", 0) or 0)
    co     = float(row.get("charged_off", 0) or 0)
    paid   = float(row.get("paid", 0) or 0)
    ub     = float(row.get("unbilled", 0) or 0)
    # Prefer avg_annual_rate (weighted from time entries) over simple hourly_rate
    avg_rate  = float(row.get("avg_annual_rate", 0) or 0)
    hourly    = float(row.get("hourly_rate", 0) or 0)
    rate      = avg_rate if avg_rate > 0 else hourly
    rate_src  = "avg" if avg_rate > 0 else "manual"

    grand_total    = billed + cpp + cup + co + paid + ub
    basis          = grand_total - co
    equiv_hrs      = basis / rate if rate > 0 else 0.0
    prod_bonus_pct = max(equiv_hrs - 800, 0) / 40 * 0.01

    return {
        "Grand Total €":      round(grand_total, 2),
        "Basis for Bonus €":  round(basis, 2),
        "Rate Used €/hr":     round(rate, 1),
        "Rate Source":        rate_src,
        "Equiv Hrs":          round(equiv_hrs, 1),
        "Productivity Bonus": f"{prod_bonus_pct:.2%}",
    }


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def _export_billing_basis_excel(rows: list, year: int) -> bytes:
    import io
    records = []
    for b in rows:
        derived = _derive({
            "billed": b.billed, "capped_paid_prebill": b.capped_paid_prebill,
            "capped_unpaid_prebill": b.capped_unpaid_prebill, "charged_off": b.charged_off,
            "paid": b.paid, "unbilled": b.unbilled,
            "avg_annual_rate": b.avg_annual_rate, "hourly_rate": b.hourly_rate,
        })
        records.append({
            "Year": year, "Emp #": b.emp_nbr, "Source": b.source,
            "Billed": b.billed, "Capped Paid Prebill": b.capped_paid_prebill,
            "Capped Unpaid Prebill": b.capped_unpaid_prebill,
            "Charged Off": b.charged_off, "Paid": b.paid, "Unbilled": b.unbilled,
            "Avg Annual Rate": b.avg_annual_rate, "Hourly Rate": b.hourly_rate,
            "Rate Used": derived["Rate Used €/hr"], "Rate Source": derived["Rate Source"],
            "Grand Total": derived["Grand Total €"],
            "Basis for Bonus": derived["Basis for Bonus €"],
            "Equiv Hrs": derived["Equiv Hrs"],
            "Productivity Bonus %": derived["Productivity Bonus"],
        })
    buf = io.BytesIO()
    pd.DataFrame(records).to_excel(buf, index=False, sheet_name=f"Billing Basis {year}")
    buf.seek(0)
    return buf.read()


tab_auto, tab_manual, tab_saved = st.tabs(["Auto (from Time Tracking)", "Manual Entry", "Saved Basis"])

# ── Auto tab ────────────────────────────────────────────────────────────────
with tab_auto:
    st.subheader(f"Auto-aggregate from Time Tracking — {year}")
    st.info(
        "Aggregates time entries for the selected year: "
        "**non_z_charges** (billable charges) → *Paid* column; "
        "write-offs for the same year → *Charged Off* column. "
        "Other billing categories (Billed, Capped Pre-bill, Unbilled) are not tracked in time entries — "
        "set them via Manual Entry if needed.  \n"
        "**Saving here only writes to the Auto source and never touches Manual entries.**"
    )

    if st.button("Load from Time Tracking", key="btn_auto_load"):
        rows = get_billing_basis_from_time_entries(year)
        if not rows:
            st.warning(f"No time entries found for {year}.")
        else:
            st.session_state["_bb_auto_rows"] = rows

    if "_bb_auto_rows" in st.session_state:
        _all_auto_rows = st.session_state["_bb_auto_rows"]
        _grp_lookup = {cg["emp_nbr"]: cg["group_name"] for cg in _all_cg if cg.get("emp_nbr")}
        rows = (
            _all_auto_rows if group_filter == "All"
            else [r for r in _all_auto_rows if _grp_lookup.get(r["emp_nbr"], "Other") == group_filter]
        )

        if not rows:
            st.info(f"No time entries found for group '{group_filter}' in {year}.")
        else:
            # Check which consultants have existing manual entries — show a warning
            _manual_saved = {b.emp_nbr for b in get_billing_basis_year_by_source(year, "manual")}
            if _manual_saved:
                _names_with_manual = [r.get("consultant", r["emp_nbr"]) for r in rows
                                       if r["emp_nbr"] in _manual_saved]
                if _names_with_manual:
                    st.warning(
                        f"The following consultant(s) already have **Manual entries** saved for {year}: "
                        f"{', '.join(_names_with_manual)}. "
                        "Saving Auto data stores it separately — Manual entries are preserved. "
                        "Annual Review uses Manual entries when available."
                    )

            # Compute avg_annual_rate from time entries per consultant
            _monthly_data: dict[str, list] = {}
            _avg_rates: dict[str, float] = {}
            for r in rows:
                monthly = get_monthly_billing_rate_breakdown(r["emp_nbr"], year)
                _monthly_data[r["emp_nbr"]] = monthly
                total_hrs = sum(m["non_z_hours"] or 0 for m in monthly)
                total_chg = sum(m["non_z_charges"] or 0 for m in monthly)
                _avg_rates[r["emp_nbr"]] = round(total_chg / total_hrs, 1) if total_hrs > 0 else 0.0

            # Compute defaults: saved DB value takes priority over auto-computed rate
            _defaults: dict[str, tuple[float, float]] = {}  # emp_nbr → (default_avg, default_hourly)
            for r in rows:
                _existing = get_billing_basis_by_source(r["emp_nbr"], year, "time_tracking")
                _saved_avg    = _existing.avg_annual_rate if _existing else 0.0
                _saved_hourly = _existing.hourly_rate     if _existing else 0.0
                _computed_avg = _avg_rates.get(r["emp_nbr"], 0.0)
                _defaults[r["emp_nbr"]] = (
                    _saved_avg if _saved_avg > 0 else _computed_avg,
                    _saved_hourly,
                )

            # Rate inputs — OUTSIDE a form so the preview below updates live on every change
            st.caption(
                "**Avg Annual Rate** is pre-filled from time entries (weighted avg NonZ rate). "
                "Edit if needed — the bonus calculation below updates immediately. "
                "**Hourly Rate** is your reference/proposed rate (shown on Rates by Year only)."
            )
            rate_cols = st.columns(min(len(rows), 3))
            hourly_rates: dict[str, float] = {}
            avg_rates_input: dict[str, float] = {}
            for i, r in enumerate(rows):
                _emp  = r["emp_nbr"]
                _name = r.get("consultant", _emp)
                _col  = rate_cols[i % len(rate_cols)]
                _col.markdown(f"**{_name}**")
                _def_avg, _def_hourly = _defaults[_emp]
                avg_rates_input[_emp] = _col.number_input(
                    "Avg Annual Rate €/hr", value=float(_def_avg),
                    min_value=0.0, step=1.0, key=f"auto_avg_{_emp}",
                    help="Weighted avg from time entries — used for bonus %"
                )
                hourly_rates[_emp] = _col.number_input(
                    "Hourly Rate €/hr (reference)", value=float(_def_hourly),
                    min_value=0.0, step=5.0, key=f"auto_rate_{_emp}",
                    help="Proposed/current rate — shown on Rates by Year"
                )

            # Preview table — built using CURRENT widget values so bonus calc is always in sync
            records = []
            for r in rows:
                _emp = r["emp_nbr"]
                derived = _derive({
                    **r,
                    "avg_annual_rate": avg_rates_input.get(_emp, _defaults[_emp][0]),
                    "hourly_rate":     hourly_rates.get(_emp, _defaults[_emp][1]),
                })
                records.append({
                    "Emp #":            r["emp_nbr"],
                    "Consultant":       r.get("consultant", ""),
                    "Billed €":         r["billed"],
                    "Capped Paid €":    r["capped_paid_prebill"],
                    "Capped Unpaid €":  r["capped_unpaid_prebill"],
                    "Charged Off €":    r["charged_off"],
                    "Paid €":           r["paid"],
                    "Unbilled €":       r["unbilled"],
                    **derived,
                })
            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Monthly rate breakdown per consultant
            with st.expander("Monthly rate breakdown (basis for Avg Annual Rate)", expanded=False):
                st.caption(
                    "**NonZ Rate** = non_z_charges ÷ non_z_hours per period. "
                    "The **Avg Annual Rate** (Grand Total row) is the weighted average across all periods "
                    "and is used instead of the simple Hourly Rate for the bonus calculation."
                )
                for r in rows:
                    monthly = _monthly_data.get(r["emp_nbr"], [])
                    if not monthly:
                        continue
                    name = r.get("consultant", r["emp_nbr"])
                    avg  = _avg_rates.get(r["emp_nbr"], 0.0)
                    st.markdown(f"**{name}** — Auto-computed weighted avg: **€{avg:.1f}/hr**")
                    df_m = pd.DataFrame([{
                        "Period":        m["period"],
                        "NonZ Hours":    m["non_z_hours"],
                        "NonZ Charges €": m["non_z_charges"],
                        "NonZ Rate €/hr": m["avg_nonz_rate"],
                        "Total Hours":   m["total_hours"],
                        "Total Charges €": m["total_charges"],
                        "Total Rate €/hr": m["avg_total_rate"],
                    } for m in monthly] + [{
                        "Period":        "TOTAL / AVG",
                        "NonZ Hours":    sum(m["non_z_hours"] or 0 for m in monthly),
                        "NonZ Charges €": sum(m["non_z_charges"] or 0 for m in monthly),
                        "NonZ Rate €/hr": avg,
                        "Total Hours":   sum(m["total_hours"] or 0 for m in monthly),
                        "Total Charges €": sum(m["total_charges"] or 0 for m in monthly),
                        "Total Rate €/hr": round(
                            sum(m["total_charges"] or 0 for m in monthly) /
                            sum(m["total_hours"] or 0 for m in monthly), 1
                        ) if sum(m["total_hours"] or 0 for m in monthly) > 0 else 0.0,
                    }])
                    st.dataframe(df_m, use_container_width=True, hide_index=True)

            if st.button("Save Basis", type="primary", key="btn_save_auto"):
                for r in rows:
                    upsert_billing_basis(
                        emp_nbr=r["emp_nbr"],
                        year=year,
                        source="time_tracking",
                        billed=r["billed"],
                        capped_paid_prebill=r["capped_paid_prebill"],
                        capped_unpaid_prebill=r["capped_unpaid_prebill"],
                        charged_off=r["charged_off"],
                        paid=r["paid"],
                        unbilled=r["unbilled"],
                        hourly_rate=hourly_rates.get(r["emp_nbr"], 0.0),
                        avg_annual_rate=avg_rates_input.get(r["emp_nbr"], 0.0),
                    )
                del st.session_state["_bb_auto_rows"]
                st.success(f"Saved billing basis for {len(rows)} consultant(s) — {year}.")
                st.rerun()

# ── Manual Entry tab ─────────────────────────────────────────────────────────
with tab_manual:
    st.subheader(f"Manual Entry — {year}")
    st.info(
        "Enter billing amounts directly (e.g. from a billing system export). "
        "Grand Total and all derived columns are computed automatically.  \n"
        "**Manual entries are stored separately from Auto entries and are never overwritten by Auto imports.** "
        "Rows pre-fill from any previously saved manual entries for this year (all zeros if none saved yet). "
        "Annual Review uses Manual entries when available, falling back to Auto."
    )

    consultants = (
        _all_cg if group_filter == "All"
        else [cg for cg in _all_cg if cg["group_name"] == group_filter]
    )
    if not consultants:
        st.info(f"No consultants in group '{group_filter}'.")
    else:
        # Pre-populate from manual-source records only (0s if no manual entry saved yet)
        existing_rows = {b.emp_nbr: b for b in get_billing_basis_year_by_source(year, "manual")}

        manual_data = []
        for cg in consultants:
            emp = cg["emp_nbr"] or ""
            existing = existing_rows.get(emp)
            manual_data.append({
                "Emp #":               emp,
                "Consultant":          cg["consultant"],
                "Billed €":            existing.billed if existing else 0.0,
                "Capped Paid Prebill €":   existing.capped_paid_prebill if existing else 0.0,
                "Capped Unpaid Prebill €": existing.capped_unpaid_prebill if existing else 0.0,
                "Charged Off €":       existing.charged_off if existing else 0.0,
                "Paid €":              existing.paid if existing else 0.0,
                "Unbilled €":          existing.unbilled if existing else 0.0,
                "Avg Annual Rate €/hr": existing.avg_annual_rate if existing else 0.0,
                "Hourly Rate €/hr":    existing.hourly_rate if existing else 0.0,
                "Notes":               existing.notes if existing else "",
            })

        df_edit = pd.DataFrame(manual_data)
        edited = st.data_editor(
            df_edit,
            use_container_width=True,
            hide_index=True,
            disabled=["Emp #", "Consultant"],
            num_rows="fixed",
            column_config={
                "Billed €":                  st.column_config.NumberColumn(format="€%.2f"),
                "Capped Paid Prebill €":     st.column_config.NumberColumn(format="€%.2f"),
                "Capped Unpaid Prebill €":   st.column_config.NumberColumn(format="€%.2f"),
                "Charged Off €":             st.column_config.NumberColumn(format="€%.2f"),
                "Paid €":                    st.column_config.NumberColumn(format="€%.2f"),
                "Unbilled €":                st.column_config.NumberColumn(format="€%.2f"),
                "Avg Annual Rate €/hr":      st.column_config.NumberColumn(format="€%.1f",
                    help="Weighted avg rate used for bonus % — enter from time-tracking breakdown or leave 0 to use Hourly Rate"),
                "Hourly Rate €/hr":          st.column_config.NumberColumn(format="€%.0f",
                    help="Reference/proposed rate shown on Rates by Year"),
            },
        )

        # Computed preview
        preview_rows = []
        for _, row in edited.iterrows():
            d = {
                "Consultant":    row["Consultant"],
                "Grand Total €": 0.0,
                "Basis for Bonus €": 0.0,
                "Equiv Hrs": 0.0,
                "Productivity Bonus": "—",
            }
            r_dict = {
                "billed":                row["Billed €"],
                "capped_paid_prebill":   row["Capped Paid Prebill €"],
                "capped_unpaid_prebill": row["Capped Unpaid Prebill €"],
                "charged_off":           row["Charged Off €"],
                "paid":                  row["Paid €"],
                "unbilled":              row["Unbilled €"],
                "avg_annual_rate":       row["Avg Annual Rate €/hr"],
                "hourly_rate":           row["Hourly Rate €/hr"],
            }
            derived = _derive(r_dict)
            d.update(derived)
            preview_rows.append(d)

        st.subheader("Computed Summary")
        st.dataframe(
            pd.DataFrame(preview_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Grand Total €":     st.column_config.NumberColumn(format="€%.2f"),
                "Basis for Bonus €": st.column_config.NumberColumn(format="€%.2f"),
                "Equiv Hrs":         st.column_config.NumberColumn(format="%.1f hrs"),
            },
        )

        if st.button("Save Manual Basis", type="primary"):
            saved = 0
            for _, row in edited.iterrows():
                emp = row["Emp #"]
                if not emp:
                    continue
                upsert_billing_basis(
                    emp_nbr=emp,
                    year=year,
                    source="manual",
                    billed=float(row["Billed €"] or 0),
                    capped_paid_prebill=float(row["Capped Paid Prebill €"] or 0),
                    capped_unpaid_prebill=float(row["Capped Unpaid Prebill €"] or 0),
                    charged_off=float(row["Charged Off €"] or 0),
                    paid=float(row["Paid €"] or 0),
                    unbilled=float(row["Unbilled €"] or 0),
                    avg_annual_rate=float(row["Avg Annual Rate €/hr"] or 0),
                    hourly_rate=float(row["Hourly Rate €/hr"] or 0),
                    notes=str(row["Notes"] or ""),
                )
                saved += 1
            st.success(f"Saved {saved} rows for {year}.")
            st.rerun()

# ── Saved Basis tab ──────────────────────────────────────────────────────────
with tab_saved:
    st.subheader(f"Saved Billing Basis — {year}")
    _manual_saved = get_billing_basis_year_by_source(year, "manual")
    _auto_saved   = get_billing_basis_year_by_source(year, "time_tracking")
    saved_rows    = _manual_saved + _auto_saved
    _emps_with_manual = {b.emp_nbr for b in _manual_saved}
    if not saved_rows:
        st.info(f"No billing basis saved for {year} yet.")
    else:
        _all_cg_sv = get_consultant_groups()
        _name_map  = {cg["emp_nbr"]: cg["consultant"] for cg in _all_cg_sv if cg.get("emp_nbr")}
        _grp_map   = {cg["emp_nbr"]: cg["group_name"]  for cg in _all_cg_sv if cg.get("emp_nbr")}

        # Group filter
        _sv_groups    = sorted({_grp_map.get(b.emp_nbr, "Other") for b in saved_rows})
        _sv_grp_opts  = ["All"] + _sv_groups
        _sv_grp_sel   = st.radio("Filter by Group", _sv_grp_opts, horizontal=True, key="sv_grp")

        # View mode toggle
        VIEW_MODES = [
            "By Consultant",
            "By Group",
            "By Consultant → Project",
            "By Project",
            "By Project → Group",
            "By Project → Consultant",
            "By Project → Group → Consultant",
        ]
        sv_view = st.selectbox("Re-arrange to Show By", VIEW_MODES, key="sv_view")

        _MONEY_COLS = ["Billed €", "Capped Paid €", "Capped Unpaid €",
                       "Charged Off €", "Paid €", "Unbilled €",
                       "Grand Total €", "Basis for Bonus €"]
        _RATE_COLS = ["Avg Rate €/hr", "Rate €/hr"]
        _HR_COL = "Equiv Hrs"

        def _sv_fmt_dict(df_in: pd.DataFrame) -> dict:
            mc = [c for c in _MONEY_COLS if c in df_in.columns]
            rc = [c for c in _RATE_COLS if c in df_in.columns]
            hc = [c for c in [_HR_COL] if c in df_in.columns]
            return {**{c: "{:,.0f}" for c in mc}, **{c: "{:,.1f}" for c in rc + hc}}

        def _sv_total_dict(df_in: pd.DataFrame, label_col: str, label: str = "TOTAL") -> dict:
            mc = [c for c in _MONEY_COLS + [_HR_COL] if c in df_in.columns]
            return {c: df_in[c].sum() if c in mc else (label if c == label_col else "")
                    for c in df_in.columns}

        if sv_view in ("By Consultant", "By Group", "By Consultant → Project",
                       "By Project", "By Project → Group",
                       "By Project → Consultant", "By Project → Group → Consultant"):

            if sv_view in ("By Project", "By Project → Group",
                           "By Project → Consultant", "By Project → Group → Consultant",
                           "By Consultant → Project"):
                # Use time_entry data to get project breakdown
                proj_data = get_billing_basis_summary(year)
                if _sv_grp_sel != "All":
                    proj_data = [r for r in proj_data if r["group_name"] == _sv_grp_sel]
                if not proj_data:
                    st.info("No time entry data for the selected year / group.")
                else:
                    pj_df = pd.DataFrame(proj_data)

                    if sv_view == "By Consultant → Project":
                        pj_agg = (pj_df.groupby(["consultant", "group_name", "project_name", "client_name"],
                                                  as_index=False)
                                  .agg({"billable_charges": "sum", "billable_hrs": "sum"})
                                  .rename(columns={"consultant": "Consultant", "group_name": "Group",
                                                   "project_name": "Project", "client_name": "Client",
                                                   "billable_charges": "Paid €", "billable_hrs": "Equiv Hrs"}))
                        dataframe_with_total(pj_agg, _sv_total_dict(pj_agg, "Consultant"), _sv_fmt_dict(pj_agg))

                    elif sv_view == "By Project":
                        pj_agg = (pj_df.groupby(["project_name", "client_name"], as_index=False)
                                  .agg({"billable_charges": "sum", "billable_hrs": "sum"})
                                  .rename(columns={"project_name": "Project", "client_name": "Client",
                                                   "billable_charges": "Paid €", "billable_hrs": "Equiv Hrs"}))
                        dataframe_with_total(pj_agg, _sv_total_dict(pj_agg, "Project"), _sv_fmt_dict(pj_agg))

                    elif sv_view == "By Project → Group":
                        pj_agg = (pj_df.groupby(["project_name", "client_name", "group_name"], as_index=False)
                                  .agg({"billable_charges": "sum", "billable_hrs": "sum"})
                                  .rename(columns={"project_name": "Project", "client_name": "Client",
                                                   "group_name": "Group",
                                                   "billable_charges": "Paid €", "billable_hrs": "Equiv Hrs"}))
                        dataframe_with_total(pj_agg, _sv_total_dict(pj_agg, "Project"), _sv_fmt_dict(pj_agg))

                    elif sv_view == "By Project → Consultant":
                        pj_agg = (pj_df.groupby(["project_name", "client_name", "consultant"], as_index=False)
                                  .agg({"billable_charges": "sum", "billable_hrs": "sum"})
                                  .rename(columns={"project_name": "Project", "client_name": "Client",
                                                   "consultant": "Consultant",
                                                   "billable_charges": "Paid €", "billable_hrs": "Equiv Hrs"}))
                        dataframe_with_total(pj_agg, _sv_total_dict(pj_agg, "Project"), _sv_fmt_dict(pj_agg))

                    elif sv_view == "By Project → Group → Consultant":
                        pj_agg = (pj_df.groupby(
                            ["project_name", "client_name", "group_name", "consultant"], as_index=False)
                                  .agg({"billable_charges": "sum", "billable_hrs": "sum"})
                                  .rename(columns={"project_name": "Project", "client_name": "Client",
                                                   "group_name": "Group", "consultant": "Consultant",
                                                   "billable_charges": "Paid €", "billable_hrs": "Equiv Hrs"}))
                        dataframe_with_total(pj_agg, _sv_total_dict(pj_agg, "Project"), _sv_fmt_dict(pj_agg))

            else:
                # Consultant-level views from saved billing_basis table
                records = []
                for b in saved_rows:
                    grp = _grp_map.get(b.emp_nbr, "Other")
                    if _sv_grp_sel != "All" and grp != _sv_grp_sel:
                        continue
                    derived = _derive({
                        "billed": b.billed, "capped_paid_prebill": b.capped_paid_prebill,
                        "capped_unpaid_prebill": b.capped_unpaid_prebill, "charged_off": b.charged_off,
                        "paid": b.paid, "unbilled": b.unbilled,
                        "avg_annual_rate": b.avg_annual_rate, "hourly_rate": b.hourly_rate,
                    })
                    is_active = bool(b.is_preferred)
                    records.append({
                        "Consultant":        _name_map.get(b.emp_nbr, b.emp_nbr),
                        "Group":             grp,
                        "Source":            b.source,
                        "Active for Review": "✓" if is_active else "",
                        "Billed €":          float(b.billed),
                        "Capped Paid €":     float(b.capped_paid_prebill),
                        "Capped Unpaid €":   float(b.capped_unpaid_prebill),
                        "Charged Off €":     float(b.charged_off),
                        "Paid €":            float(b.paid),
                        "Unbilled €":        float(b.unbilled),
                        "Avg Rate €/hr":     float(b.avg_annual_rate),
                        "Rate €/hr":         float(derived["Rate Used €/hr"]),
                        "Grand Total €":     float(derived["Grand Total €"]),
                        "Basis for Bonus €": float(derived["Basis for Bonus €"]),
                        "Equiv Hrs":         float(derived["Equiv Hrs"]),
                        "Productivity Bonus":derived["Productivity Bonus"],
                    })

                if not records:
                    st.info("No records for the selected group.")
                else:
                    df_saved = pd.DataFrame(records)
                    df_active = df_saved[df_saved["Active for Review"] == "✓"]

                    if sv_view == "By Group":
                        # Aggregate only Active records to avoid double-counting
                        grp_agg = (df_active.groupby("Group", as_index=False)
                                   [_MONEY_COLS + [_HR_COL]].sum())
                        dataframe_with_total(grp_agg, _sv_total_dict(grp_agg, "Group"), _sv_fmt_dict(grp_agg))
                    else:
                        # By Consultant — shows all records (manual + auto) with Source / Active columns
                        st.caption(
                            "Both manual and auto records are shown. "
                            "'✓' in **Active for Review** is the record used by the Annual Review. "
                            "Use the selector below to change which source is used per consultant."
                        )
                        st.dataframe(df_saved, use_container_width=True, hide_index=True)

                        # --- Explicit source-selection for consultants with both records ---
                        _both_emps_from_records = []
                        seen_emps: set[str] = set()
                        for rec in records:
                            emp = next((b.emp_nbr for b in (_manual_saved + _auto_saved)
                                        if _name_map.get(b.emp_nbr, b.emp_nbr) == rec["Consultant"]), None)
                            if emp and emp not in seen_emps:
                                has_manual = any(b.emp_nbr == emp for b in _manual_saved)
                                has_auto   = any(b.emp_nbr == emp for b in _auto_saved)
                                if has_manual and has_auto:
                                    _both_emps_from_records.append((emp, rec["Consultant"]))
                                    seen_emps.add(emp)

                        if _both_emps_from_records:
                            st.markdown("**Set Annual Review source** *(only shown for consultants with both manual and auto entries)*")
                            with st.form(f"form_pref_{year}"):
                                _choices: dict[str, str] = {}
                                for emp, name in _both_emps_from_records:
                                    current = get_billing_basis(emp, year)
                                    cur_src = current.source if current else "manual"
                                    _choices[emp] = st.radio(
                                        name,
                                        ["manual", "time_tracking"],
                                        index=0 if cur_src == "manual" else 1,
                                        horizontal=True,
                                        key=f"pref_{emp}_{year}",
                                    )
                                if st.form_submit_button("Save preferences", type="primary"):
                                    for emp, src in _choices.items():
                                        set_billing_basis_preferred(emp, year, src)
                                    st.success("Annual Review source preferences saved.")
                                    st.rerun()

        buf = _export_billing_basis_excel(saved_rows, year)
        st.download_button(
            "Export to Excel",
            data=buf,
            file_name=f"billing_basis_{year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
