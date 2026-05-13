"""Page 13 — Annual Review

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
import json

from backend.db import (
    get_consultant_groups,
    get_consultant_profile,
    get_salary_record,
    upsert_salary_record,
    get_billing_basis,
    get_review_scores,
    get_review_scores_multi_year,
    upsert_review_scores,
    get_review_feedback,
    upsert_review_feedback,
    get_consultant_project_hours,
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
all_consultants = get_consultant_groups()
if not all_consultants:
    st.info("No consultants found. Import time entries first.")
    st.stop()

consultants = [
    cg for cg in all_consultants
    if cg["group_name"] == "Local" and cg.get("status", "Active") == "Active"
]
if not consultants:
    st.info("No active Local consultants found. Check Consultant Groups (Page 9).")
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
# Helpers — defined before expanders/buttons that call them
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


def _build_review_excel(
    name, emp_nbr, year, assessor, assess_date,
    profile, salary_rec, billing, scores, prod_pct, equiv_hrs, basis
) -> bytes:
    import io as _io
    buf = _io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        exam_raise_v  = (salary_rec.exams_passed * salary_rec.exam_raise_per_exam) if salary_rec else 0
        total_raise_v = exam_raise_v + (salary_rec.other_raise if salary_rec else 0)
        updated_sal_v = (salary_rec.starting_salary if salary_rec else 0) + total_raise_v
        obj_pct_v     = salary_rec.objective_bonus_pct if salary_rec else 0
        total_bonus_v = prod_pct + obj_pct_v
        start_sal_v   = salary_rec.starting_salary if salary_rec else 0
        bonus_v       = start_sal_v * total_bonus_v
        summary_data = {
            "Field": [
                "Consultant", "Emp #", "Year", "Assessor", "Date of Assessment",
                "Milliman Status", "External Level", "Current Role",
                "", "Starting Salary €", "Exams Passed", "Raise per Exam €",
                "Exam Raise €", "Other Raise €", "Total Raise €", "Updated Salary €", "Effective Date",
                "", "Billing Basis €", "Equiv Hours", "Hourly Rate €/hr",
                "Productivity Bonus %", "Objective Bonus %", "Total Bonus %", "Bonus Amount €", "Proposed Rate €/hr",
            ],
            "Value": [
                name, emp_nbr, year, assessor, assess_date,
                profile.milliman_status if profile else "", profile.external_level if profile else "",
                profile.current_role if profile else "", "",
                salary_rec.starting_salary if salary_rec else 0,
                salary_rec.exams_passed if salary_rec else 0,
                salary_rec.exam_raise_per_exam if salary_rec else 1000,
                exam_raise_v, total_raise_v - exam_raise_v, total_raise_v, updated_sal_v,
                salary_rec.effective_date if salary_rec else "", "",
                basis, equiv_hrs, billing.hourly_rate if billing else 0,
                f"{prod_pct:.2%}", f"{obj_pct_v:.2%}",
                f"{total_bonus_v:.2%}", round(bonus_v, 2),
                salary_rec.proposed_rate if salary_rec else 0,
            ],
        }
        pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name="Summary")
        score_rows = []
        for group, items in SCORE_GROUPS.items():
            for item in items:
                score_rows.append({"Group": group, "Item": item,
                                   f"{year} Score": scores.get(group, {}).get(item, 0.0)})
        pd.DataFrame(score_rows).to_excel(writer, index=False, sheet_name="Performance Scores")
    buf.seek(0)
    return buf.read()


def _unique_colleagues(raw: str, exclude_name: str) -> str:
    """Return a deduplicated, self-excluded comma-separated colleagues string.

    Handles ' | '-separated input (from DB) as well as plain comma-separated
    text (user-edited fields).  Names in 'Lastname, Firstname' format are kept
    intact when the pipe separator is used.
    """
    seen: set[str] = set()
    unique: list[str] = []
    if " | " in raw:
        parts = [p.strip() for p in raw.split(" | ") if p.strip()]
    else:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
    for n in parts:
        if n not in seen and n != exclude_name:
            seen.add(n)
            unique.append(n)
    return ", ".join(unique)


def _generate_feedback_docx(
    name: str,
    assessor: str,
    assess_date: str,
    profile,
    year: int,
    proj_rows: list[dict],
    area_comment_vals: dict[str, tuple[str, str]],
    area_scores: dict[str, float],
    other_comments: str,
) -> tuple[bytes, str]:
    import io as _io
    from docx import Document
    from datetime import datetime as _dt

    # Total experience (Milliman + prior)
    total_exp_str = ""
    if profile and profile.employment_date:
        try:
            emp_dt = _dt.strptime(profile.employment_date, "%Y-%m-%d")
            mill_yrs = round((_dt.now() - emp_dt).days / 365.25, 1)
            total_exp_str = str(round(mill_yrs + profile.prior_exp_years, 1))
        except ValueError:
            total_exp_str = str(getattr(profile, "prior_exp_years", ""))

    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    template_path = os.path.join(_root, "template_other", "Feedback Form_2025 DRAFT Example.docx")
    doc = Document(template_path)
    tables = doc.tables

    def _cell(cell, text: str) -> None:
        """Clear a table cell and write plain text, preserving cell-level formatting."""
        for para in cell.paragraphs:
            for run in para.runs:
                run.text = ""
        if cell.paragraphs:
            cell.paragraphs[0].runs[0].text = text if cell.paragraphs[0].runs else None
            if not cell.paragraphs[0].runs:
                cell.paragraphs[0].add_run(text)
        else:
            cell.add_paragraph(text)

    # Table 0 — Basic info
    t0 = tables[0]
    t0.rows[1].cells[0].text = name
    t0.rows[1].cells[1].text = profile.current_role if profile else ""
    t0.rows[1].cells[2].text = assessor
    t0.rows[1].cells[3].text = assess_date

    # Table 1 — Background
    t1 = tables[1]
    t1.rows[1].cells[1].text = total_exp_str
    t1.rows[2].cells[1].text = profile.milliman_status if profile else ""
    t1.rows[3].cells[1].text = profile.languages if profile else ""
    t1.rows[4].cells[1].text = profile.tools if profile else ""

    # Table 2 — Project rows (dynamic: remove template rows, add one per project)
    t2 = tables[2]
    while len(t2.rows) > 1:
        t2._tbl.remove(t2.rows[-1]._tr)
    for proj in proj_rows:
        row = t2.add_row()
        assign = proj["project_name"]
        if proj["description"]:
            assign += f" — {proj['description']}"
        row.cells[0].text = proj["client"]
        row.cells[1].text = assign
        row.cells[2].text = _unique_colleagues(proj["colleagues"], name)
        row.cells[3].text = f"{proj['hours_pct']:.0f}%"

    # Table 3 — Assessment: score + comments + development ideas per area
    t3 = tables[3]
    for row_idx, area in enumerate(["Professionalism", "Management", "Social Skills"], start=1):
        score = area_scores.get(area, 0.0)
        comments_v, dev_v = area_comment_vals.get(area, ("", ""))
        t3.rows[row_idx].cells[1].text = f"{score:.2f}" if score > 0 else "NA"
        t3.rows[row_idx].cells[2].text = comments_v
        t3.rows[row_idx].cells[3].text = dev_v

    # Table 4 — Other comments
    tables[4].rows[0].cells[0].text = other_comments

    buf = _io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    safe_name = name.replace(" ", "_")
    return buf.read(), f"feedback_{safe_name}_{year}.docx"


# ---------------------------------------------------------------------------
# Section 1 — Compensation & Bonus
# ---------------------------------------------------------------------------
with st.expander("1 — Compensation & Bonus", expanded=True):

    equiv_hrs, prod_pct, basis = _productivity_bonus(billing)

    if billing is None:
        _hint = ""
        if salary_rec and salary_rec.proposed_rate:
            _hint = (
                f" Note: a **Proposed Billing Rate of €{salary_rec.proposed_rate:,.0f}/hr** exists "
                "in Salary History — that is a different field. "
                "Page 11 needs the actual annual billing amounts (Billed, Charged Off, etc.) "
                "to compute Equivalent Hours and Productivity Bonus."
            )
        st.warning(
            f"No billing basis found for **{selected_name} / {review_year}**. "
            f"Go to **Page 11 — Billing Basis** to enter or auto-import billing amounts first.{_hint}"
        )
    else:
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Basis for Bonus €", f"€{basis:,.0f}")
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
            "Starting Salary €",
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
            "Raise per Exam €",
            value=float(salary_rec.exam_raise_per_exam if salary_rec else 1000.0),
            min_value=0.0, step=100.0,
        )
        other_raise = c1.number_input(
            "Other / Discretionary Raise €",
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
            "Bonus Paid € (actual, for record)",
            value=float(salary_rec.bonus_paid if salary_rec else 0.0),
            min_value=0.0, step=100.0,
        )
        proposed_rate = c2.number_input(
            "Proposed Billing Rate €/hr",
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
        bonus_amount  = start_sal * total_bonus

        st.subheader("Computed Results")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Exam Raise €",     f"€{exam_raise:,.0f}")
        m2.metric("Total Raise €",    f"€{total_raise:,.0f}")
        m3.metric("Updated Salary €", f"€{updated_sal:,.0f}")
        m4.metric("Total Bonus %",    f"{total_bonus:.2%}")
        m5.metric("Bonus Amount €",   f"€{bonus_amount:,.0f}")

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
        "Score each item 1.0–4.0  (1=Significant underperformance · 2=Does not meet expectations · "
        "3=Meets expectations · 4=Exceeds expectations). "
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
                max_value=4.0,
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
    bonus_amount_s = (salary_rec.starting_salary if salary_rec else 0) * total_bonus_s

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
            f"Starting Salary: €{(salary_rec.starting_salary if salary_rec else 0):,.0f}  \n"
            f"Exams passed: {(salary_rec.exams_passed if salary_rec else 0)} × "
            f"€{(salary_rec.exam_raise_per_exam if salary_rec else 1000):,.0f} = "
            f"€{exam_raise_s:,.0f}  \n"
            f"Other raise: €{(salary_rec.other_raise if salary_rec else 0):,.0f}  \n"
            f"**Updated Salary: €{updated_sal_s:,.0f}**  \n"
            f"Effective: {(salary_rec.effective_date if salary_rec else '—')}"
        )
        st.markdown(
            f"Productivity Bonus: {prod_pct:.2%}  \n"
            f"Objective Bonus: {obj_pct_s:.2%}  \n"
            f"**Total Bonus: {total_bonus_s:.2%} → €{bonus_amount_s:,.0f}**"
        )
        if billing:
            st.markdown(
                f"Billing Basis: €{basis:,.0f} · "
                f"Equiv Hrs: {equiv_hrs:,.1f} · "
                f"Rate: €{billing.hourly_rate:,.0f}/hr"
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
        st.success(f"Proposed billing rate for {int(review_year) + 1}: **€{salary_rec.proposed_rate:,.0f}/hr**")

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
# Section 4 — Feedback Form Export
# ---------------------------------------------------------------------------
with st.expander("4 — Feedback Form Export", expanded=False):
    st.caption(
        "Fills the ICEE Feedback Form Word template and saves it to the exports/ folder. "
        "Save compensation (Section 1) and scores (Section 2) first."
    )

    scores_for_fb = get_review_scores(emp_nbr, int(review_year))
    saved_fb      = get_review_feedback(emp_nbr, int(review_year))
    proj_hours    = get_consultant_project_hours(selected_name, int(review_year))

    def _group_avg_fb(group_name: str) -> float:
        vals = [v for v in scores_for_fb.get(group_name, {}).values() if v > 0]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    # ── A: Project breakdown ────────────────────────────────────────────────
    st.subheader("A — Project Breakdown")
    if not proj_hours:
        st.info(
            f"No billable time entries found for **{selected_name}** in **{review_year}**. "
            "Import time entries for this year first (Page 9 — Time Tracking)."
        )
    else:
        st.caption(
            "Auto-filled from time entries. "
            "Choose Include / Aggregate / Exclude per project — rows < 2% fees are auto-set to Aggregate. "
            "Aggregate rows are merged into a single 'Other Projects' line in the exported document."
        )

        # Load saved project row decisions
        _pr_fb = saved_fb.get("_project_rows")
        try:
            _saved_decisions: dict = json.loads(_pr_fb.comments) if _pr_fb and _pr_fb.comments else {}
        except (ValueError, TypeError):
            _saved_decisions = {}

        _TOGGLE_OPTIONS = ["Include", "Aggregate", "Exclude"]

        h0, h1, h2, h3, h4, h5 = st.columns([2, 4, 3, 1, 1, 1])
        h0.markdown("**Client**")
        h1.markdown("**Assignment**")
        h2.markdown("**Colleagues involved**")
        h3.markdown("**Hrs %**")
        h4.markdown("**Fees %**")
        h5.markdown("**Action**")

        colleague_vals: dict[int, str] = {}
        row_decisions: dict[int, str] = {}
        for i, proj in enumerate(proj_hours):
            c0, c1, c2, c3, c4, c5 = st.columns([2, 4, 3, 1, 1, 1])
            assign = proj["project_name"]
            if proj["description"]:
                assign += f" — {proj['description']}"
            c0.markdown(proj["client"])
            c1.markdown(assign)
            colleague_vals[i] = c2.text_input(
                "Colleagues",
                value=proj["colleagues"],
                key=f"fb_coll_{i}_{review_year}",
                label_visibility="collapsed",
                placeholder="e.g. Savva K, Petros A",
            )
            c3.markdown(f"**{proj['hours_pct']:.0f}%**")
            c4.markdown(f"**{proj['fees_pct']:.0f}%**")
            _proj_key = proj["project_name"]
            _default_dec = "Aggregate" if proj["fees_pct"] < 2 else "Include"
            _saved_dec = _saved_decisions.get(_proj_key, _default_dec)
            if _saved_dec not in _TOGGLE_OPTIONS:
                _saved_dec = _default_dec
            row_decisions[i] = c5.selectbox(
                "Action",
                _TOGGLE_OPTIONS,
                index=_TOGGLE_OPTIONS.index(_saved_dec),
                key=f"fb_action_{i}_{review_year}",
                label_visibility="collapsed",
            )

    # ── B: Assessment comments ──────────────────────────────────────────────
    st.subheader("B — Assessment Comments & Development Ideas")
    area_comment_vals: dict[str, tuple[str, str]] = {}
    for area in ["Professionalism", "Management", "Social Skills"]:
        avg = _group_avg_fb(area)
        fb  = saved_fb.get(area)
        avg_str = f"{avg:.2f}" if avg > 0 else "no scores yet"
        suffix  = " *(set NA if not applicable)*" if area == "Management" else ""
        st.markdown(f"**{area}** — avg score: {avg_str}{suffix}")
        c1, c2 = st.columns(2)
        comments_v = c1.text_area(
            "Comments from Feedback Provider",
            value=fb.comments if fb else "",
            height=90,
            key=f"fb_comments_{area}_{review_year}",
        )
        dev_v = c2.text_area(
            "Development ideas",
            value=fb.development_ideas if fb else "",
            height=90,
            key=f"fb_dev_{area}_{review_year}",
        )
        area_comment_vals[area] = (comments_v, dev_v)

    # ── C: Other comments ───────────────────────────────────────────────────
    st.subheader("C — Other Comments")
    other_fb = saved_fb.get("Other")
    other_comments_v = st.text_area(
        "General narrative / additional comments",
        value=other_fb.comments if other_fb else "",
        height=120,
        key=f"fb_other_{review_year}",
        placeholder=(
            "In the first half of the year, [name] supported the team mainly on ... "
            "For [next year], we expect continued improvement in ..."
        ),
    )

    # ── Generate ────────────────────────────────────────────────────────────
    st.divider()
    if st.button("Save & Generate Feedback Form", type="primary", key="btn_gen_feedback"):
        # Persist feedback
        for area, (c_v, d_v) in area_comment_vals.items():
            upsert_review_feedback(emp_nbr, int(review_year), area, c_v, d_v)
        upsert_review_feedback(emp_nbr, int(review_year), "Other", other_comments_v, "")

        # Persist project row decisions
        if proj_hours:
            _decisions_to_save = {
                proj["project_name"]: row_decisions.get(i, "Include")
                for i, proj in enumerate(proj_hours)
            }
            upsert_review_feedback(emp_nbr, int(review_year), "_project_rows",
                                   json.dumps(_decisions_to_save), "")

        # Build final project rows applying Include/Aggregate/Exclude
        if proj_hours:
            _included_rows = []
            _aggregate_rows = []
            for i, proj in enumerate(proj_hours):
                _p = {**proj, "colleagues": colleague_vals.get(i, proj["colleagues"])}
                _dec = row_decisions.get(i, "Include")
                if _dec == "Include":
                    _included_rows.append(_p)
                elif _dec == "Aggregate":
                    _aggregate_rows.append(_p)
            final_proj_rows = _included_rows
            if _aggregate_rows:
                # Merge colleague lists from all aggregated rows.
                # Each r["colleagues"] may be ' | '-separated (from DB) or
                # comma-separated (user-edited). Collect unique names via
                # _unique_colleagues applied per row, then join with ' | '.
                _agg_seen: set[str] = set()
                _agg_names: list[str] = []
                for _ar in _aggregate_rows:
                    for _n in _unique_colleagues(_ar["colleagues"], selected_name).split(", "):
                        _n = _n.strip()
                        if _n and _n not in _agg_seen:
                            _agg_seen.add(_n)
                            _agg_names.append(_n)
                final_proj_rows.append({
                    "client":        "",
                    "project_name":  "Other Projects",
                    "description":   "",
                    "colleagues":    ", ".join(_agg_names),
                    "hours_pct":     sum(r["hours_pct"] for r in _aggregate_rows),
                    "fees_pct":      sum(r["fees_pct"] for r in _aggregate_rows),
                })
        else:
            final_proj_rows = []

        area_scores_map = {a: _group_avg_fb(a) for a in ["Professionalism", "Management", "Social Skills"]}

        try:
            file_bytes, filename = _generate_feedback_docx(
                name=selected_name,
                assessor=assessor,
                assess_date=assess_date,
                profile=profile,
                year=int(review_year),
                proj_rows=final_proj_rows,
                area_comment_vals=area_comment_vals,
                area_scores=area_scores_map,
                other_comments=other_comments_v,
            )
            _exports = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "exports",
            )
            os.makedirs(_exports, exist_ok=True)
            with open(os.path.join(_exports, filename), "wb") as fh:
                fh.write(file_bytes)
            st.success(f"Saved to `exports/{filename}`")
            st.download_button(
                "Download Feedback Form",
                data=file_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="dl_feedback",
            )
        except Exception as exc:
            st.error(f"Error generating document: {exc}")
