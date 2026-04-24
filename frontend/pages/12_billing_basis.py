"""Page 12 — Billing Basis

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
    get_billing_basis,
    get_billing_basis_from_time_entries,
    upsert_billing_basis,
)

if not st.session_state.get("authenticated"):
    st.warning("Please log in.")
    st.stop()

st.title("Billing Basis")
st.caption("Annual billing summary per consultant — the basis for productivity-bonus calculation.")

# ---------------------------------------------------------------------------
# Year selector
# ---------------------------------------------------------------------------
current_year = datetime.now().year
year = st.selectbox(
    "Financial Year",
    options=list(range(current_year - 1, current_year - 6, -1)),
    index=0,
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
    rate   = float(row.get("hourly_rate", 0) or 0)

    grand_total    = billed + cpp + cup + co + paid + ub
    basis          = grand_total - co
    equiv_hrs      = basis / rate if rate > 0 else 0.0
    prod_bonus_pct = max(equiv_hrs - 800, 0) / 40 * 0.01

    return {
        "Grand Total £":      round(grand_total, 2),
        "Basis for Bonus £":  round(basis, 2),
        "Equiv Hrs":          round(equiv_hrs, 1),
        "Productivity Bonus": f"{prod_bonus_pct:.2%}",
    }


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_auto, tab_manual, tab_saved = st.tabs(["Auto (from Time Tracking)", "Manual Entry", "Saved Basis"])

# ── Auto tab ────────────────────────────────────────────────────────────────
with tab_auto:
    st.subheader(f"Auto-aggregate from Time Tracking — {year}")
    st.info(
        "Aggregates **non_z_charges** per consultant from imported time entries for the selected year. "
        "Write-offs recorded in the same calendar year are mapped to the *Charged Off* column. "
        "Other billing categories (Billed, Unbilled, Pre-bill) are not tracked in time entries — "
        "set them via Manual Entry if needed."
    )

    if st.button("Load from Time Tracking", key="btn_auto_load"):
        rows = get_billing_basis_from_time_entries(year)
        if not rows:
            st.warning(f"No time entries found for {year}.")
        else:
            st.session_state["_bb_auto_rows"] = rows

    if "_bb_auto_rows" in st.session_state:
        rows = st.session_state["_bb_auto_rows"]
        records = []
        for r in rows:
            derived = _derive(r)
            records.append({
                "Emp #":            r["emp_nbr"],
                "Consultant":       r.get("consultant", ""),
                "Billed £":         r["billed"],
                "Capped Paid £":    r["capped_paid_prebill"],
                "Capped Unpaid £":  r["capped_unpaid_prebill"],
                "Charged Off £":    r["charged_off"],
                "Paid £":           r["paid"],
                "Unbilled £":       r["unbilled"],
                **derived,
            })
        df = pd.DataFrame(records)
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.form("form_auto_save"):
            st.caption("Hourly rates below are required to compute equivalent hours. Enter before saving.")
            rate_rows = []
            for r in rows:
                existing = get_billing_basis(r["emp_nbr"], year)
                default_rate = existing.hourly_rate if existing else 0.0
                rate_rows.append((r["emp_nbr"], r.get("consultant", r["emp_nbr"]), default_rate))

            rate_cols = st.columns(min(len(rate_rows), 4))
            rates: dict[str, float] = {}
            for i, (emp, name, default_rate) in enumerate(rate_rows):
                col = rate_cols[i % len(rate_cols)]
                rates[emp] = col.number_input(
                    f"{name} rate (£/hr)", value=float(default_rate),
                    min_value=0.0, step=5.0, key=f"auto_rate_{emp}"
                )

            if st.form_submit_button("Save Auto Basis"):
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
                        hourly_rate=rates.get(r["emp_nbr"], 0.0),
                    )
                del st.session_state["_bb_auto_rows"]
                st.success(f"Saved billing basis for {len(rows)} consultant(s) — {year}.")
                st.rerun()

# ── Manual Entry tab ─────────────────────────────────────────────────────────
with tab_manual:
    st.subheader(f"Manual Entry — {year}")
    st.caption(
        "Enter billing amounts directly (e.g. from a billing system pivot). "
        "Grand Total and all derived columns are computed automatically."
    )

    consultants = get_consultant_groups()
    if not consultants:
        st.info("No consultants found. Import time entries first or add consultants via Time Tracking page.")
    else:
        # Pre-populate table from DB if data exists for this year
        existing_rows = {b.emp_nbr: b for b in get_billing_basis_year(year)}

        manual_data = []
        for cg in consultants:
            emp = cg["emp_nbr"] or ""
            existing = existing_rows.get(emp)
            manual_data.append({
                "Emp #":            emp,
                "Consultant":       cg["consultant"],
                "Billed £":         existing.billed if existing else 0.0,
                "Capped Paid Prebill £":   existing.capped_paid_prebill if existing else 0.0,
                "Capped Unpaid Prebill £": existing.capped_unpaid_prebill if existing else 0.0,
                "Charged Off £":    existing.charged_off if existing else 0.0,
                "Paid £":           existing.paid if existing else 0.0,
                "Unbilled £":       existing.unbilled if existing else 0.0,
                "Hourly Rate £/hr": existing.hourly_rate if existing else 0.0,
                "Notes":            existing.notes if existing else "",
            })

        df_edit = pd.DataFrame(manual_data)
        edited = st.data_editor(
            df_edit,
            use_container_width=True,
            hide_index=True,
            disabled=["Emp #", "Consultant"],
            num_rows="fixed",
            column_config={
                "Billed £":                  st.column_config.NumberColumn(format="£%.2f"),
                "Capped Paid Prebill £":     st.column_config.NumberColumn(format="£%.2f"),
                "Capped Unpaid Prebill £":   st.column_config.NumberColumn(format="£%.2f"),
                "Charged Off £":             st.column_config.NumberColumn(format="£%.2f"),
                "Paid £":                    st.column_config.NumberColumn(format="£%.2f"),
                "Unbilled £":                st.column_config.NumberColumn(format="£%.2f"),
                "Hourly Rate £/hr":          st.column_config.NumberColumn(format="£%.0f"),
            },
        )

        # Computed preview
        preview_rows = []
        for _, row in edited.iterrows():
            d = {
                "Consultant":    row["Consultant"],
                "Grand Total £": 0.0,
                "Basis for Bonus £": 0.0,
                "Equiv Hrs": 0.0,
                "Productivity Bonus": "—",
            }
            r_dict = {
                "billed":                row["Billed £"],
                "capped_paid_prebill":   row["Capped Paid Prebill £"],
                "capped_unpaid_prebill": row["Capped Unpaid Prebill £"],
                "charged_off":           row["Charged Off £"],
                "paid":                  row["Paid £"],
                "unbilled":              row["Unbilled £"],
                "hourly_rate":           row["Hourly Rate £/hr"],
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
                "Grand Total £":     st.column_config.NumberColumn(format="£%.2f"),
                "Basis for Bonus £": st.column_config.NumberColumn(format="£%.2f"),
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
                    billed=float(row["Billed £"] or 0),
                    capped_paid_prebill=float(row["Capped Paid Prebill £"] or 0),
                    capped_unpaid_prebill=float(row["Capped Unpaid Prebill £"] or 0),
                    charged_off=float(row["Charged Off £"] or 0),
                    paid=float(row["Paid £"] or 0),
                    unbilled=float(row["Unbilled £"] or 0),
                    hourly_rate=float(row["Hourly Rate £/hr"] or 0),
                    notes=str(row["Notes"] or ""),
                )
                saved += 1
            st.success(f"Saved {saved} rows for {year}.")
            st.rerun()

# ── Saved Basis tab ──────────────────────────────────────────────────────────
with tab_saved:
    st.subheader(f"Saved Billing Basis — {year}")
    saved_rows = get_billing_basis_year(year)
    if not saved_rows:
        st.info(f"No billing basis saved for {year} yet.")
    else:
        records = []
        for b in saved_rows:
            derived = _derive({
                "billed": b.billed, "capped_paid_prebill": b.capped_paid_prebill,
                "capped_unpaid_prebill": b.capped_unpaid_prebill, "charged_off": b.charged_off,
                "paid": b.paid, "unbilled": b.unbilled, "hourly_rate": b.hourly_rate,
            })
            records.append({
                "Emp #":             b.emp_nbr,
                "Billed £":          b.billed,
                "Capped Paid £":     b.capped_paid_prebill,
                "Capped Unpaid £":   b.capped_unpaid_prebill,
                "Charged Off £":     b.charged_off,
                "Paid £":            b.paid,
                "Unbilled £":        b.unbilled,
                "Hrly Rate":         b.hourly_rate,
                "Source":            b.source,
                **derived,
            })
        df_saved = pd.DataFrame(records)
        st.dataframe(
            df_saved,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Billed £":          st.column_config.NumberColumn(format="£%.2f"),
                "Capped Paid £":     st.column_config.NumberColumn(format="£%.2f"),
                "Capped Unpaid £":   st.column_config.NumberColumn(format="£%.2f"),
                "Charged Off £":     st.column_config.NumberColumn(format="£%.2f"),
                "Paid £":            st.column_config.NumberColumn(format="£%.2f"),
                "Unbilled £":        st.column_config.NumberColumn(format="£%.2f"),
                "Grand Total £":     st.column_config.NumberColumn(format="£%.2f"),
                "Basis for Bonus £": st.column_config.NumberColumn(format="£%.2f"),
                "Equiv Hrs":         st.column_config.NumberColumn(format="%.1f hrs"),
            },
        )

        buf = _export_billing_basis_excel(saved_rows, year)
        st.download_button(
            "Export to Excel",
            data=buf,
            file_name=f"billing_basis_{year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _export_billing_basis_excel(rows: list, year: int) -> bytes:
    import io
    records = []
    for b in rows:
        derived = _derive({
            "billed": b.billed, "capped_paid_prebill": b.capped_paid_prebill,
            "capped_unpaid_prebill": b.capped_unpaid_prebill, "charged_off": b.charged_off,
            "paid": b.paid, "unbilled": b.unbilled, "hourly_rate": b.hourly_rate,
        })
        records.append({
            "Year": year, "Emp #": b.emp_nbr, "Source": b.source,
            "Billed": b.billed, "Capped Paid Prebill": b.capped_paid_prebill,
            "Capped Unpaid Prebill": b.capped_unpaid_prebill,
            "Charged Off": b.charged_off, "Paid": b.paid, "Unbilled": b.unbilled,
            "Hourly Rate": b.hourly_rate,
            "Grand Total": derived["Grand Total £"],
            "Basis for Bonus": derived["Basis for Bonus £"],
            "Equiv Hrs": derived["Equiv Hrs"],
            "Productivity Bonus %": derived["Productivity Bonus"],
        })
    buf = io.BytesIO()
    pd.DataFrame(records).to_excel(buf, index=False, sheet_name=f"Billing Basis {year}")
    buf.seek(0)
    return buf.read()
