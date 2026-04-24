"""Page 14 — Annual Review

Per-consultant annual performance assessment and compensation calculation.

Sections:
  1. Compensation & Bonus  — salary chain + productivity/objective bonus
  2. Performance Scores    — three groups: Professionalism, Management, Social Skills
  3. Summary & Export      — formatted summary card + Excel export
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from datetime import datetime
import io

from backend.db import (
    get_consultant_groups,
    get_consultant_profile,
    get_salary_record,
    upsert_salary_record,
    get_billing_basis,
    get_review_scores,
    get_review_scores_multi_year,
    upsert_review_scores,
)
from shared.models import SCORE_GROUPS, MILLIMAN_STATUSES, EXTERNAL_LEVELS

if not st.session_state.get("authenticated"):
    st.warning("Please log in.")
    st.stop()

st.title("Annual Review")
st.caption("Performance assessment and compensation calculation per consultant per year.")

# ---------------------------------------------------------------------------
# Header row: consultant, year, assessor, date
# ---------------------------------------------------------------------------
consultants = get_consultant_groups()
if not consultants:
    st.info("No consultants found. Import time entries first.")
    st.stop()

consultant_options = {cg["consultant"]: cg for cg in consultants}

hdr_col1, hdr_col2, hdr_col3, hdr_col4 = st.columns([3, 1, 2, 2])
selected_name  = hdr_col1.selectbox("Consultant", list(consultant_options.keys()))
current_year   = datetime.now().year
review_year    = hdr_col2.number_input("Year", value=current_year - 1, min_value=2000,
                                        max_value=current_year, step=1)
assessor       = hdr_col3.text_input("Assessor", value="Demosthenous")
assess_date    = hdr_col4.text_input("Date of Assessment", value=datetime.now().strftime("%d/%m/%Y"))

cg      = consultant_options[selected_name]
emp_nbr = cg["emp_nbr"] or ""
if not emp_nbr:
    st.warning("No employee number for this consultant — import a time sheet to assign one.")
    st.stop()

profile     = get_consultant_profile(emp_nbr)
salary_rec  = get_salary_record(emp_nbr, int(review_year))
prior_rec   = get_salary_record(emp_nbr, int(review_year) - 1)
billing     = get_billing_basis(emp_nbr, int(review_year))

st.divider()

# ---------------------------------------------------------------------------
# Helper: compute bonus basis from a BillingBasis row
# ---------------------------------------------------------------------------
def _productivity_bonus(bb) -> tuple[float, float, float]:
    """Returns (equiv_hrs, prod_bonus_pct, basis_for_bonus) from a BillingBasis object."""
    if bb is None or bb.hourly_rate <= 0:
        return 0.0, 0.0, 0.0
    grand = bb.billed + bb.capped_paid_prebill + bb.capped_unpaid_prebill + bb.charged_off + bb.paid + bb.unbilled
    basis = grand - bb.charged_off
    equiv_hrs = basis / bb.hourly_rate
    prod_pct = max(equiv_hrs - 800, 0) / 40 * 0.01
    return round(equiv_hrs, 1), round(prod_pct, 6), round(basis, 2)


# ---------------------------------------------------------------------------
# Section 1 — Compensation & Bonus
# ---------------------------------------------------------------------------
with st.expander("1 — Compensation & Bonus", expanded=True):

    equiv_hrs, prod_pct, basis = _productivity_bonus(billing)

    if billing is None:
        st.warning(
            f"No billing basis found for {selected_name} / {review_year}. "
            "Go to **Page 12 — Billing Basis** to enter or import billing data first. "
            "Productivity bonus will be 0% until billing basis is saved."
        )
    else:
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Basis for Bonus £", f"£{basis:,.0f}")
        col_b.metric("Equivalent Hours", f"{equiv_hrs:,.1f} hrs")
        col_c.metric("Productivity Bonus", f"{prod_pct:.2%}")

    st.subheader("Salary & Bonus Inputs")

    # Default starting salary: carry forward from prior year's updated salary
    if prior_rec:
        prior_exam_raise = prior_rec.exams_passed * prior_rec.exam_raise_per_exam
        prior_updated = prior_rec.starting_salary + prior_exam_raise + prior_rec.other_raise
    else:
        prior_updated = 0.0

    with st.form("form_compensation"):
        c1, c2, c3 = st.columns(3)

        start_sal = c1.number_input(
            "Starting Salary £",
            value=float(salary_rec.starting_salary if salary_rec else prior_updated),
            min_value=0.0, step=500.0,
            help="Carried forward automatically from prior year's updated salary.",
        )
        exams = c2.number_input(
            "Exams Passed (this year)",
            value=float(salary_rec.exams_passed if salary_rec else 0.0),
            min_value=0.0, step=0.5,
        )
        exam_raise_per = c3.number_input(
            "Raise per Exam £",
            value=float(salary_rec.exam_raise_per_exam if salary_rec else 1000.0),
            min_value=0.0, step=100.0,
        )
        other_raise = c1.number_input(
            "Other / Discretionary Raise £",
            value=float(salary_rec.other_raise if salary_rec else 0.0),
            min_value=0.0, step=100.0,
        )
        eff_date = c2.text_input(
            "Effective Date (YYYY-MM-DD)",
            value=salary_rec.effective_date if salary_rec else "",
        )
        obj_bonus_pct_in = c3.number_input(
            "Objective Bonus %",
            value=float((salary_rec.objective_bonus_pct or 0) * 100 if salary_rec else 0.0),
            min_value=0.0, max_value=100.0, step=0.5,
            help="Enter as percentage, e.g. 7 for 7%",
        )
        bonus_paid = c1.number_input(
            "Bonus Paid £ (actual, for record)",
            value=float(salary_rec.bonus_paid if salary_rec else 0.0),
            min_value=0.0, step=100.0,
        )
        proposed_rate = c2.number_input(
            "Proposed Billing Rate £/hr",
            value=float(salary_rec.proposed_rate if salary_rec else 0.0),
            min_value=0.0, step=5.0,
        )
        comp_notes = c3.text_input(
            "Notes", value=salary_rec.notes if salary_rec else ""
        )

        # Live preview
        obj_bonus_pct = obj_bonus_pct_in / 100
        exam_raise    = exams * exam_raise_per
        total_raise   = exam_raise + other_raise
        updated_sal   = start_sal + total_raise
        total_bonus   = prod_pct + obj_bonus_pct
        bonus_amount  = updated_sal * total_bonus

        st.subheader("Computed Results")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Exam Raise £",     f"£{exam_raise:,.0f}")
        m2.metric("Total Raise £",    f"£{total_raise:,.0f}")
        m3.metric("Updated Salary £", f"£{updated_sal:,.0f}")
        m4.metric("Total Bonus %",    f"{total_bonus:.2%}")
        m5.metric("Bonus Amount £",   f"£{bonus_amount:,.0f}")

        if st.form_submit_button("Save Compensation", type="primary"):
            upsert_salary_record(
                emp_nbr=emp_nbr,
                year=int(review_year),
                starting_salary=start_sal,
                exams_passed=exams,
                exam_raise_per_exam=exam_raise_per,
                other_raise=other_raise,
                effective_date=eff_date.strip(),
                objective_bonus_pct=obj_bonus_pct,
                bonus_paid=bonus_paid,
                proposed_rate=proposed_rate,
                notes=comp_notes.strip(),
            )
            st.success("Compensation record saved.")
            st.rerun()

# ---------------------------------------------------------------------------
# Section 2 — Performance Scores
# ---------------------------------------------------------------------------
with st.expander("2 — Performance Scores", expanded=True):

    st.caption(
        "Score each item 1.0–5.0 (two decimal places). "
        "Group 2 (Management) is shown for all consultants — set to 0 if not applicable."
    )

    # Load existing scores and history (prior 3 years)
    current_scores = get_review_scores(emp_nbr, int(review_year))
    hist_years = [int(review_year) - 1, int(review_year) - 2, int(review_year) - 3]
    hist_scores = get_review_scores_multi_year(emp_nbr, hist_years)

    # Collect new scores into a dict as user edits
    new_scores: dict[str, dict[str, float]] = {}

    for group_name, items in SCORE_GROUPS.items():
        st.subheader(group_name)
        if group_name == "Management":
            st.caption("Manager-level only — leave at 0 if not applicable.")

        # Build a dataframe for display: Item | Current Year score | Y-1 | Y-2 | Y-3
        score_rows = []
        input_vals: dict[str, float] = {}
        for item in items:
            current_val = current_scores.get(group_name, {}).get(item, 0.0)
            input_vals[item] = current_val

        # Score input — use columns (4 items per row for readability)
        new_scores[group_name] = {}
        num_cols = min(len(items), 4)
        cols = st.columns(num_cols)
        for idx, item in enumerate(items):
            default = current_scores.get(group_name, {}).get(item, 0.0)
            val = cols[idx % num_cols].number_input(
                item,
                value=float(default),
                min_value=0.0,
                max_value=5.0,
                step=0.25,
                key=f"score_{group_name}_{item}_{review_year}",
                format="%.2f",
            )
            new_scores[group_name][item] = val

        # Historical comparison table
        rows_hist = []
        for item in items:
            row = {"Item": item}
            row[f"{review_year}"] = new_scores[group_name].get(item, 0.0)
            for hy in hist_years:
                row[str(hy)] = hist_scores.get(hy, {}).get(group_name, {}).get(item, "—")
            rows_hist.append(row)

        df_hist = pd.DataFrame(rows_hist)
        # Group average row
        avg_row = {"Item": f"► {group_name} Average"}
        for hy in [review_year] + hist_years:
            col_key = str(hy)
            if col_key in df_hist.columns:
                numeric_vals = [v for v in df_hist[col_key] if isinstance(v, (int, float))]
                avg_row[col_key] = round(sum(numeric_vals) / len(numeric_vals), 2) if numeric_vals else "—"
        rows_hist.append(avg_row)

        st.dataframe(
            pd.DataFrame(rows_hist),
            use_container_width=True,
            hide_index=True,
            column_config={str(review_year): st.column_config.NumberColumn(format="%.2f")},
        )

    if st.button("Save All Scores", type="primary", key="btn_save_scores"):
        upsert_review_scores(emp_nbr, int(review_year), new_scores)
        st.success(f"Performance scores saved for {selected_name} / {review_year}.")
        st.rerun()

# ---------------------------------------------------------------------------
# Section 3 — Summary & Export
# ---------------------------------------------------------------------------
with st.expander("3 — Summary & Export", expanded=False):

    # Reload saved values for display
    salary_rec = get_salary_record(emp_nbr, int(review_year))
    scores_saved = get_review_scores(emp_nbr, int(review_year))

    exam_raise_s   = (salary_rec.exams_passed * salary_rec.exam_raise_per_exam) if salary_rec else 0
    total_raise_s  = exam_raise_s + (salary_rec.other_raise if salary_rec else 0)
    updated_sal_s  = (salary_rec.starting_salary if salary_rec else 0) + total_raise_s
    obj_pct_s      = salary_rec.objective_bonus_pct if salary_rec else 0
    total_bonus_s  = prod_pct + obj_pct_s
    bonus_amount_s = updated_sal_s * total_bonus_s

    st.subheader(f"Review Summary — {selected_name} — {review_year}")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(f"**Assessor:** {assessor}  \n**Date:** {assess_date}")
        if profile:
            st.markdown(
                f"**Status:** {profile.milliman_status}  \n"
                f"**Level:** {profile.external_level}  \n"
                f"**Role:** {profile.current_role}"
            )
        st.markdown("---")
        st.markdown("**Compensation**")
        st.markdown(
            f"Starting Salary: £{(salary_rec.starting_salary if salary_rec else 0):,.0f}  \n"
            f"Exams passed: {(salary_rec.exams_passed if salary_rec else 0)} × "
            f"£{(salary_rec.exam_raise_per_exam if salary_rec else 1000):,.0f} = "
            f"£{exam_raise_s:,.0f}  \n"
            f"Other raise: £{(salary_rec.other_raise if salary_rec else 0):,.0f}  \n"
            f"**Updated Salary: £{updated_sal_s:,.0f}**  \n"
            f"Effective: {(salary_rec.effective_date if salary_rec else '—')}"
        )
        st.markdown(
            f"Productivity Bonus: {prod_pct:.2%}  \n"
            f"Objective Bonus: {obj_pct_s:.2%}  \n"
            f"**Total Bonus: {total_bonus_s:.2%} → £{bonus_amount_s:,.0f}**"
        )
        if billing:
            st.markdown(
                f"Billing Basis: £{basis:,.0f} · "
                f"Equiv Hrs: {equiv_hrs:,.1f} · "
                f"Rate: £{billing.hourly_rate:,.0f}/hr"
            )

    with col_r:
        st.markdown("**Performance Scores**")
        for group_name, items in SCORE_GROUPS.items():
            group_scores = scores_saved.get(group_name, {})
            vals = [group_scores.get(i, 0.0) for i in items if group_scores.get(i, 0.0) > 0]
            avg  = round(sum(vals) / len(vals), 2) if vals else "—"
            st.markdown(f"**{group_name}:** {avg}")
            for item in items:
                score = group_scores.get(item, 0.0)
                if score > 0:
                    st.markdown(f"&nbsp;&nbsp;· {item}: **{score:.2f}**")

    # Proposed rate for next year
    if salary_rec and salary_rec.proposed_rate:
        st.success(f"Proposed billing rate for {int(review_year) + 1}: **£{salary_rec.proposed_rate:,.0f}/hr**")

    st.divider()
    if st.button("Export Review to Excel", key="btn_export_review"):
        buf = _build_review_excel(
            name=selected_name,
            emp_nbr=emp_nbr,
            year=int(review_year),
            assessor=assessor,
            assess_date=assess_date,
            profile=profile,
            salary_rec=salary_rec,
            billing=billing,
            scores=scores_saved,
            prod_pct=prod_pct,
            equiv_hrs=equiv_hrs,
            basis=basis,
        )
        st.download_button(
            "Download Excel",
            data=buf,
            file_name=f"review_{selected_name.replace(' ', '_')}_{review_year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ---------------------------------------------------------------------------
# Excel export builder
# ---------------------------------------------------------------------------
def _build_review_excel(
    name, emp_nbr, year, assessor, assess_date,
    profile, salary_rec, billing, scores, prod_pct, equiv_hrs, basis
) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # Sheet 1 — Summary
        exam_raise_v  = (salary_rec.exams_passed * salary_rec.exam_raise_per_exam) if salary_rec else 0
        total_raise_v = exam_raise_v + (salary_rec.other_raise if salary_rec else 0)
        updated_sal_v = (salary_rec.starting_salary if salary_rec else 0) + total_raise_v
        obj_pct_v     = salary_rec.objective_bonus_pct if salary_rec else 0
        total_bonus_v = prod_pct + obj_pct_v
        bonus_v       = updated_sal_v * total_bonus_v

        summary_data = {
            "Field": [
                "Consultant", "Emp #", "Year", "Assessor", "Date of Assessment",
                "Milliman Status", "External Level", "Current Role",
                "", "Starting Salary £", "Exams Passed", "Raise per Exam £",
                "Exam Raise £", "Other Raise £", "Total Raise £", "Updated Salary £",
                "Effective Date",
                "", "Billing Basis £", "Equiv Hours", "Hourly Rate £/hr",
                "Productivity Bonus %", "Objective Bonus %",
                "Total Bonus %", "Bonus Amount £", "Proposed Rate £/hr",
            ],
            "Value": [
                name, emp_nbr, year, assessor, assess_date,
                profile.milliman_status if profile else "", profile.external_level if profile else "",
                profile.current_role if profile else "",
                "",
                salary_rec.starting_salary if salary_rec else 0,
                salary_rec.exams_passed if salary_rec else 0,
                salary_rec.exam_raise_per_exam if salary_rec else 1000,
                exam_raise_v, total_raise_v - exam_raise_v, total_raise_v, updated_sal_v,
                salary_rec.effective_date if salary_rec else "",
                "",
                basis, equiv_hrs, billing.hourly_rate if billing else 0,
                f"{prod_pct:.2%}", f"{obj_pct_v:.2%}",
                f"{total_bonus_v:.2%}", round(bonus_v, 2),
                salary_rec.proposed_rate if salary_rec else 0,
            ],
        }
        pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name="Summary")

        # Sheet 2 — Performance Scores
        score_rows = []
        for group, items in SCORE_GROUPS.items():
            for item in items:
                score_rows.append({
                    "Group": group,
                    "Item":  item,
                    f"{year} Score": scores.get(group, {}).get(item, 0.0),
                })
        pd.DataFrame(score_rows).to_excel(writer, index=False, sheet_name="Performance Scores")

    buf.seek(0)
    return buf.read()
