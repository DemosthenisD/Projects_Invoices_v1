"""Page 13 — Consultant Profiles

Extended master data and salary history per consultant.
  Tab 1 — Profile   : employment date, experience, Milliman status, level, languages, tools
  Tab 2 — Salary History : year-by-year salary chain with full compensation details
  Tab 3 — Rates         : billing rates by year (from billing_basis + salary_history)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from datetime import datetime

from backend.db import (
    get_consultant_groups,
    get_consultant_profile,
    upsert_consultant_profile,
    get_salary_history,
    get_salary_record,
    upsert_salary_record,
    get_billing_basis,
)
from shared.models import MILLIMAN_STATUSES, EXTERNAL_LEVELS

if not st.session_state.get("authenticated"):
    st.warning("Please log in.")
    st.stop()

st.title("Consultant Profiles")
st.caption("Employment details, salary history, and billing rates per consultant.")

# ---------------------------------------------------------------------------
# Consultant selector
# ---------------------------------------------------------------------------
consultants = get_consultant_groups()
if not consultants:
    st.info("No consultants found. Import time entries first to populate the consultant list.")
    st.stop()

consultant_options = {cg["consultant"]: cg for cg in consultants}
selected_name = st.selectbox("Select Consultant", options=list(consultant_options.keys()))
cg = consultant_options[selected_name]
emp_nbr = cg["emp_nbr"] or ""
profile = get_consultant_profile(emp_nbr) if emp_nbr else None

if not emp_nbr:
    st.warning("This consultant has no employee number recorded. Import a time sheet to assign one.")
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_profile, tab_salary, tab_rates = st.tabs(["Profile", "Salary History", "Rates by Year"])

# ── Profile tab ──────────────────────────────────────────────────────────────
with tab_profile:
    st.subheader(f"Profile — {selected_name}")

    with st.form("form_profile"):
        col1, col2 = st.columns(2)

        emp_date = col1.text_input(
            "Employment Start Date (YYYY-MM-DD)",
            value=profile.employment_date if profile else "",
        )
        prior_exp = col2.number_input(
            "Prior Experience (years before Milliman)",
            value=float(profile.prior_exp_years) if profile else 0.0,
            min_value=0.0, step=0.5,
        )
        mill_status_idx = MILLIMAN_STATUSES.index(profile.milliman_status) if (
            profile and profile.milliman_status in MILLIMAN_STATUSES
        ) else 0
        mill_status = col1.selectbox(
            "Milliman Professional Status",
            options=MILLIMAN_STATUSES,
            index=mill_status_idx,
        )
        ext_level_idx = EXTERNAL_LEVELS.index(profile.external_level) if (
            profile and profile.external_level in EXTERNAL_LEVELS
        ) else 0
        ext_level = col2.selectbox(
            "External Level",
            options=EXTERNAL_LEVELS,
            index=ext_level_idx,
        )
        current_role = col1.text_input(
            "Current Role / Title",
            value=profile.current_role if profile else "",
        )
        languages = col1.text_input(
            "Languages (e.g. Greek (A), English (A))",
            value=profile.languages if profile else "",
        )
        tools = col2.text_area(
            "Tools (e.g. Prophet (B), Arius (A), VBA (A))",
            value=profile.tools if profile else "",
            height=80,
        )
        notes = st.text_area(
            "Notes",
            value=profile.notes if profile else "",
            height=80,
        )

        if st.form_submit_button("Save Profile", type="primary"):
            upsert_consultant_profile(
                emp_nbr=emp_nbr,
                employment_date=emp_date.strip(),
                prior_exp_years=prior_exp,
                milliman_status=mill_status,
                external_level=ext_level,
                languages=languages.strip(),
                tools=tools.strip(),
                current_role=current_role.strip(),
                notes=notes.strip(),
            )
            st.success("Profile saved.")
            st.rerun()

    # Years at Milliman (computed from employment_date)
    if profile and profile.employment_date:
        try:
            emp_dt = datetime.strptime(profile.employment_date, "%Y-%m-%d")
            years_mill = round((datetime.now() - emp_dt).days / 365.25, 1)
            total_exp = round(years_mill + profile.prior_exp_years, 1)
            st.info(
                f"**{years_mill} yrs** at Milliman · "
                f"**{profile.prior_exp_years} yrs** prior · "
                f"**{total_exp} yrs** total experience"
            )
        except ValueError:
            pass

# ── Salary History tab ───────────────────────────────────────────────────────
with tab_salary:
    st.subheader(f"Salary History — {selected_name}")

    history = get_salary_history(emp_nbr)

    if history:
        rows = []
        for h in history:
            exam_raise = round(h.exams_passed * h.exam_raise_per_exam, 2)
            total_raise = round(exam_raise + h.other_raise, 2)
            updated_salary = round(h.starting_salary + total_raise, 2)
            total_bonus_pct = h.objective_bonus_pct  # productivity bonus shown separately

            # Pull productivity bonus from billing_basis if available
            bb = get_billing_basis(emp_nbr, h.year)
            if bb and bb.hourly_rate > 0:
                grand = bb.billed + bb.capped_paid_prebill + bb.capped_unpaid_prebill + bb.charged_off + bb.paid + bb.unbilled
                basis = grand - bb.charged_off
                equiv_hrs = basis / bb.hourly_rate
                prod_pct = max(equiv_hrs - 800, 0) / 40 * 0.01
            else:
                prod_pct = 0.0

            bonus_pct = round(prod_pct + h.objective_bonus_pct, 4)
            bonus_amount = round(updated_salary * bonus_pct, 2)

            rows.append({
                "Year":               h.year,
                "Start Salary €":     h.starting_salary,
                "Exams":              h.exams_passed,
                "Raise/Exam €":       h.exam_raise_per_exam,
                "Exam Raise €":       exam_raise,
                "Other Raise €":      h.other_raise,
                "Total Raise €":      total_raise,
                "Updated Salary €":   updated_salary,
                "Effective Date":     h.effective_date,
                "Prod Bonus %":       f"{prod_pct:.2%}",
                "Obj Bonus %":        f"{h.objective_bonus_pct:.2%}",
                "Total Bonus %":      f"{bonus_pct:.2%}",
                "Bonus Amount €":     bonus_amount,
                "Bonus Paid €":       h.bonus_paid,
                "Proposed Rate €/hr": h.proposed_rate,
            })

        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Start Salary €":     st.column_config.NumberColumn(format="€%.0f"),
                "Exam Raise €":       st.column_config.NumberColumn(format="€%.0f"),
                "Other Raise €":      st.column_config.NumberColumn(format="€%.0f"),
                "Total Raise €":      st.column_config.NumberColumn(format="€%.0f"),
                "Updated Salary €":   st.column_config.NumberColumn(format="€%.0f"),
                "Bonus Amount €":     st.column_config.NumberColumn(format="€%.0f"),
                "Bonus Paid €":       st.column_config.NumberColumn(format="€%.0f"),
                "Raise/Exam €":       st.column_config.NumberColumn(format="€%.0f"),
                "Proposed Rate €/hr": st.column_config.NumberColumn(format="€%.0f"),
            },
        )

        # Export
        buf = _export_salary_history_excel(selected_name, rows)
        st.download_button(
            "Export Salary History to Excel",
            data=buf,
            file_name=f"salary_history_{selected_name.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("No salary history yet. Add a year record below.")

    st.divider()
    st.subheader("Add / Edit Year Record")

    current_year = datetime.now().year
    existing_years = [h.year for h in history]

    with st.form("form_salary_add"):
        col1, col2, col3 = st.columns(3)

        year_sel = col1.number_input(
            "Year", value=current_year - 1, min_value=2000, max_value=current_year + 1, step=1
        )

        # Pre-fill from existing record or carry forward from prior year
        existing_rec = get_salary_record(emp_nbr, int(year_sel))
        prior_rec = get_salary_record(emp_nbr, int(year_sel) - 1)

        # Compute prior year's updated_salary as the default starting salary
        if prior_rec:
            prior_exam_raise = prior_rec.exams_passed * prior_rec.exam_raise_per_exam
            prior_updated = prior_rec.starting_salary + prior_exam_raise + prior_rec.other_raise
        else:
            prior_updated = 0.0

        start_sal = col1.number_input(
            "Starting Salary €",
            value=float(existing_rec.starting_salary if existing_rec else prior_updated),
            min_value=0.0, step=500.0,
        )
        exams = col2.number_input(
            "Exams Passed (this year)",
            value=float(existing_rec.exams_passed if existing_rec else 0.0),
            min_value=0.0, step=0.5,
        )
        exam_raise_per = col2.number_input(
            "Raise per Exam €",
            value=float(existing_rec.exam_raise_per_exam if existing_rec else 1000.0),
            min_value=0.0, step=100.0,
        )
        other_raise = col3.number_input(
            "Other Raise €",
            value=float(existing_rec.other_raise if existing_rec else 0.0),
            min_value=0.0, step=100.0,
        )
        eff_date = col1.text_input(
            "Effective Date (YYYY-MM-DD)",
            value=existing_rec.effective_date if existing_rec else "",
        )

        col4, col5, col6 = st.columns(3)
        obj_bonus = col4.number_input(
            "Objective Bonus %",
            value=float((existing_rec.objective_bonus_pct or 0) * 100 if existing_rec else 0.0),
            min_value=0.0, max_value=100.0, step=0.5,
            help="Enter as a percentage, e.g. 7 for 7%",
        )
        bonus_paid = col5.number_input(
            "Bonus Paid € (historical)",
            value=float(existing_rec.bonus_paid if existing_rec else 0.0),
            min_value=0.0, step=100.0,
        )
        proposed_rate = col6.number_input(
            "Proposed Billing Rate €/hr",
            value=float(existing_rec.proposed_rate if existing_rec else 0.0),
            min_value=0.0, step=5.0,
        )
        rec_notes = st.text_input(
            "Notes", value=existing_rec.notes if existing_rec else ""
        )

        # Live preview of computed values
        exam_raise_preview = exams * exam_raise_per
        total_raise_preview = exam_raise_preview + other_raise
        updated_sal_preview = start_sal + total_raise_preview
        st.caption(
            f"Preview → Exam Raise: **€{exam_raise_preview:,.0f}** · "
            f"Total Raise: **€{total_raise_preview:,.0f}** · "
            f"Updated Salary: **€{updated_sal_preview:,.0f}**"
        )

        if st.form_submit_button("Save Year Record", type="primary"):
            upsert_salary_record(
                emp_nbr=emp_nbr,
                year=int(year_sel),
                starting_salary=start_sal,
                exams_passed=exams,
                exam_raise_per_exam=exam_raise_per,
                other_raise=other_raise,
                effective_date=eff_date.strip(),
                objective_bonus_pct=obj_bonus / 100,
                bonus_paid=bonus_paid,
                proposed_rate=proposed_rate,
                notes=rec_notes.strip(),
            )
            st.success(f"Saved {int(year_sel)} record for {selected_name}.")
            st.rerun()

# ── Rates by Year tab ─────────────────────────────────────────────────────────
with tab_rates:
    st.subheader(f"Billing Rates by Year — {selected_name}")

    history = get_salary_history(emp_nbr)
    if not history:
        st.info("No salary history. Add year records in the Salary History tab.")
    else:
        rate_rows = []
        for h in history:
            bb = get_billing_basis(emp_nbr, h.year)
            rate_rows.append({
                "Year":                  h.year,
                "Proposed Rate €/hr":    h.proposed_rate,
                "Billing Basis Rate €/hr": bb.hourly_rate if bb else "—",
                "Source":                bb.source if bb else "—",
            })
        st.dataframe(pd.DataFrame(rate_rows), use_container_width=True, hide_index=True)


def _export_salary_history_excel(name: str, rows: list[dict]) -> bytes:
    import io
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False, sheet_name="Salary History")
    buf.seek(0)
    return buf.read()
