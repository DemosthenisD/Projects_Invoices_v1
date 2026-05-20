"""
Page 11 — Receivables.

Track amounts owed to us by other Milliman entities: recurring fee splits,
one-off project reimbursements, and commission arrangements.
Receivables are independent of invoices — they represent our share of revenue
billed by another team on our behalf.
"""
import sys
import os
from datetime import date as date_type

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd

import backend.db as db
from shared.ui import require_auth

require_auth()

st.title("Receivables")
st.caption(
    "Amounts owed to us by other Milliman entities — recurring fee splits, "
    "one-off project reimbursements, and commission arrangements. "
    "Record payments as they arrive; outstanding items are flagged when overdue."
)

today_iso = date_type.today().isoformat()
cy        = date_type.today().year

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _summary():
    return db.get_outstanding_receivables_summary()

summary        = _summary()
total_os       = sum(r["outstanding"] for r in summary)
overdue_rows   = [r for r in summary if r.get("due_date") and r["due_date"] < today_iso]
overdue_amount = sum(r["outstanding"] for r in overdue_rows)

sm1, sm2, sm3 = st.columns(3)
sm1.metric("Total Outstanding (€)", f"€{total_os:,.0f}")
sm2.metric("Overdue (€)",           f"€{overdue_amount:,.0f}",
           delta=f"{len(overdue_rows)} item(s)" if overdue_rows else None,
           delta_color="inverse")
sm3.metric("Open Items",            len(summary))

if overdue_rows:
    st.error(
        f"⚠️ **{len(overdue_rows)} receivable(s) past their due date** "
        f"— €{overdue_amount:,.2f} outstanding."
    )

st.divider()

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

@st.cache_data(ttl=120)
def _recv_projects():
    return [p for p in db.get_projects() if p.billing_arrangement == "receivable"]

recv_projects = _recv_projects()
proj_name_map = {p.id: p.name for p in sorted(recv_projects, key=lambda p: p.name)}

fc1, fc2 = st.columns(2)
proj_filter  = fc1.selectbox(
    "Filter by project",
    options=[None] + list(proj_name_map.keys()),
    format_func=lambda x: "All receivable projects" if x is None else proj_name_map[x],
    key="rec_proj_filter",
)
show_settled = fc2.checkbox("Include fully settled", value=False)

# ------------------------------------------------------------------
# Receivables list
# ------------------------------------------------------------------

receivables = db.get_receivables(project_id=proj_filter, outstanding_only=not show_settled)

if not receivables:
    st.info("No outstanding receivables. ✓" if not show_settled else "No receivables found.")
else:
    st.markdown(f"**{len(receivables)} receivable(s)**")
    for rec in receivables:
        outstanding = float(rec["outstanding"])
        total_paid  = float(rec["total_paid"])
        is_settled  = outstanding <= 0.001
        is_overdue  = (not is_settled and rec.get("due_date")
                       and rec["due_date"] < today_iso)
        icon = "✅" if is_settled else ("🔴" if is_overdue else "🟡")
        type_label  = "Capped" if rec["receivable_type"] == "capped" else "Time-based"

        exp_title = (
            f"{icon} **{rec['project_name']}** — {rec['description']} "
            f"| Due {rec.get('due_date') or '—'} "
            f"| €{outstanding:,.0f} outstanding"
        )

        with st.expander(exp_title, expanded=is_overdue and not is_settled):
            ri1, ri2, ri3, ri4 = st.columns(4)
            ri1.metric("Expected (€)",    f"€{rec['expected_amount']:,.2f}")
            ri2.metric("Received (€)",    f"€{total_paid:,.2f}")
            ri3.metric("Outstanding (€)", f"€{outstanding:,.2f}")
            ri4.metric("Type",            type_label)

            if rec.get("cap_amount") and float(rec["cap_amount"]) > 0:
                st.caption(f"Pre-agreed cap: €{float(rec['cap_amount']):,.2f}")

            # Payment history
            payments = db.get_receivable_payments(rec["id"])
            if payments:
                st.markdown("**Payment history:**")
                df_pay = pd.DataFrame([{
                    "Date":       p["date"],
                    "Amount (€)": p["amount"],
                    "Notes":      p["notes"] or "—",
                } for p in payments])
                st.dataframe(
                    df_pay.style.format({"Amount (€)": "{:,.2f}"}),
                    use_container_width=True, hide_index=True,
                )

            st.markdown("---")
            tab_pay, tab_edit = st.tabs(["Record Payment", "Edit"])

            with tab_pay:
                if is_settled:
                    st.success("Fully settled — nothing outstanding.")
                else:
                    with st.form(key=f"pay_{rec['id']}"):
                        pa1, pa2, pa3 = st.columns(3)
                        pay_amt  = pa1.number_input(
                            "Amount received (€)",
                            min_value=0.01,
                            value=round(outstanding, 2),
                            step=100.0,
                        )
                        pay_date = pa2.date_input("Date received", value=date_type.today())
                        pay_note = pa3.text_input("Notes", placeholder="Reference / remarks")
                        if st.form_submit_button("Record Payment", type="primary"):
                            db.add_receivable_payment(
                                rec["id"], pay_amt, pay_date.isoformat(), pay_note
                            )
                            st.success(f"Payment of €{pay_amt:,.2f} recorded.")
                            st.cache_data.clear()
                            st.rerun()

            with tab_edit:
                with st.form(key=f"edit_rec_{rec['id']}"):
                    er1, er2 = st.columns(2)
                    e_desc = er1.text_input("Description", value=rec["description"])
                    e_type = er2.selectbox(
                        "Type", ["capped", "time_based"],
                        index=0 if rec["receivable_type"] == "capped" else 1,
                        format_func=lambda x: "Capped" if x == "capped" else "Time-based",
                    )
                    ef1, ef2, ef3 = st.columns(3)
                    e_cap = ef1.number_input(
                        "Cap amount (€)", value=float(rec.get("cap_amount") or 0),
                        min_value=0.0, step=100.0,
                    )
                    e_exp = ef2.number_input(
                        "Expected amount (€)", value=float(rec["expected_amount"]),
                        min_value=0.0, step=100.0,
                    )
                    e_due_raw = (date_type.fromisoformat(rec["due_date"])
                                 if rec.get("due_date") else date_type.today())
                    e_due  = ef3.date_input("Due date", value=e_due_raw)
                    e_note = st.text_area("Notes", value=rec.get("notes") or "", height=70)
                    if st.form_submit_button("Save Changes", type="primary"):
                        db.update_receivable(
                            rec["id"], e_desc, e_exp,
                            e_due.isoformat(), e_type, e_cap, e_note,
                        )
                        st.success("Updated.")
                        st.cache_data.clear()
                        st.rerun()

st.divider()

# ------------------------------------------------------------------
# Add standalone receivable
# ------------------------------------------------------------------

st.subheader("Add Receivable")

if not recv_projects:
    st.warning(
        "No projects with receivable billing arrangement. "
        "Update a project's billing arrangement in **Project Overview** first."
    )
    st.stop()

# ------------------------------------------------------------------
# Project selector outside the form so it drives the code list
# and the time-charges reference context reactively
# ------------------------------------------------------------------

@st.cache_data(ttl=120)
def _io_charges(year: int) -> dict:
    return {r["project_id"]: r for r in db.get_interoffice_charges(year)}

io_by_proj = _io_charges(cy)

add_proj_id = st.selectbox(
    "Project*",
    options=list(proj_name_map.keys()),
    format_func=lambda x: proj_name_map[x],
    key="rec_add_proj",
)

# Time charges reference card
if add_proj_id and add_proj_id in io_by_proj:
    ch = io_by_proj[add_proj_id]
    st.info(
        f"**{cy} time charges for this project:** "
        f"€{ch['billable_charges']:,.2f} across {ch['billable_hours']:.1f} billable hours — "
        "use as a reference when setting the expected amount below."
    )

codes_for_proj = db.get_project_codes(project_id=add_proj_id) if add_proj_id else []
code_opts = {None: "— none (project-level) —"}
code_opts.update({
    pc.id: f"{pc.client_code}{pc.client_suffix}" + (f" — {pc.name}" if pc.name else "")
    for pc in codes_for_proj
})

with st.form("add_receivable_form"):
    fa1, fa2 = st.columns(2)
    new_desc    = fa1.text_input("Description*",
                                  placeholder="e.g. Commission Q1 2026 — Platform fee")
    new_code_id = fa2.selectbox(
        "Link to project code (optional)",
        options=list(code_opts.keys()),
        format_func=lambda x: code_opts[x],
    )

    fb1, fb2, fb3 = st.columns(3)
    new_type = fb1.selectbox(
        "Receivable type",
        ["capped", "time_based"],
        format_func=lambda x: "Capped (pre-agreed amount)" if x == "capped"
                               else "Time-based (follows charges)",
    )
    new_cap  = fb2.number_input(
        "Cap / agreed amount (€)", min_value=0.0, step=100.0,
        help="Pre-agreed maximum; used as the starting reference for expected amount",
    )
    new_exp  = fb3.number_input(
        "Expected amount (€)*", min_value=0.0, step=100.0,
        help="Always editable — override cap or time charges as needed",
    )

    fc1, fc2 = st.columns(2)
    new_due   = fc1.date_input("Due date*", value=date_type.today())
    new_notes = fc2.text_area("Notes", height=70)

    if st.form_submit_button("Add Receivable", type="primary"):
        errs = []
        if not new_desc.strip():
            errs.append("Description is required.")
        if new_exp <= 0:
            errs.append("Expected amount must be greater than zero.")
        if errs:
            for e in errs:
                st.error(e)
        else:
            db.add_receivable(
                project_id=add_proj_id,
                description=new_desc.strip(),
                expected_amount=new_exp,
                due_date=new_due.isoformat(),
                receivable_type=new_type,
                cap_amount=new_cap,
                project_code_id=new_code_id,
                notes=new_notes,
            )
            st.success("Receivable added.")
            st.cache_data.clear()
            st.rerun()
