"""
Page 12 — Recurring Fees.

Cross-project view of all active recurring fees: next due dates, occurrence
history, split details, and quick actions (skip, mark invoiced manually).
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

st.title("Recurring Fees")
st.caption(
    "All active recurring fees across every project. "
    "Use this page to monitor upcoming billing, skip occurrences, and record manual invoicing. "
    "To add or edit fees, go to **Project Overview**."
)

today_iso = date_type.today().isoformat()

BILLING_TYPE_LABELS = {
    "we_bill":       "We bill client",
    "third_party_bills": "Third-party bills us",
}
FREQ_LABELS = {
    "monthly": "Monthly", "quarterly": "Quarterly",
    "semi-annual": "Semi-annual", "annual": "Annual",
}

# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load():
    return db.get_all_recurring_fees(status="Active")

fees = _load()

if not fees:
    st.info("No active recurring fees found. Add fees via **Project Overview**.")
    st.stop()

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------

overdue     = [f for f in fees if f.get("next_due") and f["next_due"] < today_iso]
due_30      = [f for f in fees if f.get("next_due") and today_iso <= f["next_due"] <= date_type.today().replace(day=min(date_type.today().day, 28)).isoformat()]
we_bill     = [f for f in fees if f["billing_type"] == "we_bill"]
third_party = [f for f in fees if f["billing_type"] == "third_party_bills"]

# Simpler: due within 30 days from today
from datetime import timedelta
in_30_days = (date_type.today() + timedelta(days=30)).isoformat()
due_soon = [f for f in fees if f.get("next_due") and today_iso <= f["next_due"] <= in_30_days]

sm1, sm2, sm3, sm4 = st.columns(4)
sm1.metric("Active Fees",    len(fees))
sm2.metric("Overdue",        len(overdue),  delta=f"{len(overdue)} past due" if overdue else None, delta_color="inverse")
sm3.metric("Due within 30d", len(due_soon))
sm4.metric("We Bill / Recv", f"{len(we_bill)} / {len(third_party)}")

if overdue:
    st.error(
        f"⚠️ **{len(overdue)} fee(s) with overdue occurrences** — next due date already passed."
    )

st.divider()

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

all_clients  = sorted({f["client_name"] for f in fees})
all_projects = sorted({f["project_name"] for f in fees})

fc1, fc2, fc3 = st.columns(3)
f_client  = fc1.multiselect("Client",       all_clients,                             key="rf_client")
f_project = fc2.multiselect("Project",      all_projects,                            key="rf_project")
f_btype   = fc3.multiselect("Billing type", list(BILLING_TYPE_LABELS.values()),      key="rf_btype")

filtered = [
    f for f in fees
    if (not f_client  or f["client_name"]  in f_client)
    and (not f_project or f["project_name"] in f_project)
    and (not f_btype  or BILLING_TYPE_LABELS.get(f["billing_type"], f["billing_type"]) in f_btype)
]

if not filtered:
    st.info("No fees match the selected filters.")
    st.stop()

# ------------------------------------------------------------------
# Fee list
# ------------------------------------------------------------------

st.markdown(f"**{len(filtered)} active fee(s)**")

for fee in filtered:
    next_due     = fee.get("next_due") or "—"
    next_amt     = float(fee.get("next_amount") or 0)
    next_split   = float(fee.get("next_split_amount") or 0)
    is_overdue   = next_due != "—" and next_due < today_iso
    is_due_soon  = (not is_overdue and next_due != "—"
                    and next_due <= in_30_days)

    icon = "🔴" if is_overdue else ("🟡" if is_due_soon else "🟢")
    bt_label = BILLING_TYPE_LABELS.get(fee["billing_type"], fee["billing_type"])
    code_str = f"{fee['client_code']}{fee['client_suffix']}" + (f" — {fee['code_name']}" if fee.get("code_name") else "")

    title = (
        f"{icon} **{fee['client_name']}** › {fee['project_name']} "
        f"| {fee['description']} "
        f"| {FREQ_LABELS.get(fee['frequency'], fee['frequency'])} "
        f"| Next: {next_due} (€{next_amt:,.0f})"
    )

    with st.expander(title, expanded=is_overdue):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Billing type",    bt_label)
        c2.metric("Frequency",       FREQ_LABELS.get(fee["frequency"], fee["frequency"]))
        c3.metric("Base fee (€)",    f"€{float(fee['fee_amount']):,.2f}")
        c4.metric("Occurrences",     f"{fee['invoiced_count']} invoiced / {fee['pending_count']} pending")

        if fee["billing_type"] == "third_party_bills" and fee.get("split_party"):
            st.info(
                f"Split with **{fee['split_party']}** — "
                f"our share next period: €{next_split:,.2f}"
            )

        d1, d2, d3 = st.columns(3)
        d1.markdown(f"**Project code:** {code_str}")
        d2.markdown(f"**Coverage start:** {fee['coverage_start'] or '—'}")
        d3.markdown(f"**Expected end:** {fee['expected_end'] or 'Rolling (no end)'}")

        if fee.get("notes"):
            st.caption(f"Notes: {fee['notes']}")

        st.markdown("---")

        # ---- Upcoming occurrences --------------------------------
        occurrences = db.get_occurrences(fee["id"])
        pending_occ = [o for o in occurrences if o["status"] == "pending"]
        past_occ    = [o for o in occurrences if o["status"] != "pending"]

        col_upcoming, col_history = st.columns([2, 1])

        with col_upcoming:
            st.markdown("**Upcoming (pending)**")
            if pending_occ:
                show_occ = pending_occ[:6]
                for occ in show_occ:
                    is_late = occ["due_date"] < today_iso
                    occ_icon = "🔴" if is_late else "⏳"
                    with st.form(key=f"occ_rf_{occ['id']}"):
                        oc1, oc2, oc3, oc4, oc5 = st.columns([2, 2, 2, 1, 1])
                        oc1.markdown(f"{occ_icon} **{occ['due_date']}**")
                        new_amt = oc2.number_input(
                            "Amount (€)", value=float(occ["amount"]),
                            min_value=0.0, step=100.0, key=f"ramt_{occ['id']}",
                        )
                        new_spl = oc3.number_input(
                            "Split (€)", value=float(occ["split_amount"] or 0),
                            min_value=0.0, step=100.0, key=f"rspl_{occ['id']}",
                        )
                        save_clicked = oc4.form_submit_button("💾")
                        skip_clicked = oc5.form_submit_button("Skip")
                        if save_clicked:
                            db.update_occurrence_amount(occ["id"], new_amt, new_spl)
                            st.success(f"{occ['due_date']} updated.")
                            st.cache_data.clear()
                            st.rerun()
                        if skip_clicked:
                            db.skip_occurrence(occ["id"], note="Skipped manually")
                            st.success(f"{occ['due_date']} skipped.")
                            st.cache_data.clear()
                            st.rerun()

                if len(pending_occ) > 6:
                    st.caption(f"… and {len(pending_occ) - 6} more pending")
            else:
                st.caption("No pending occurrences — fee may have ended.")

        with col_history:
            st.markdown("**History**")
            if past_occ:
                df_hist = pd.DataFrame([{
                    "Date":   o["due_date"],
                    "Status": o["status"].capitalize(),
                    "€":      f"{float(o['amount']):,.0f}",
                } for o in past_occ[-5:]])
                st.dataframe(df_hist, use_container_width=True, hide_index=True)
                if len(past_occ) > 5:
                    st.caption(f"Showing last 5 of {len(past_occ)}")
            else:
                st.caption("No past occurrences yet.")

        # ---- Manual invoice tab ---------------------------------
        st.markdown("---")
        st.markdown("**Mark as invoiced manually**")
        st.caption(
            "Use this only if the occurrence was invoiced outside the Generate Invoice flow. "
            "For normal invoicing, use **Generate Invoice** and select this fee."
        )

        first_pending = next((o for o in pending_occ), None)
        if first_pending:
            with st.form(key=f"manual_inv_{fee['id']}"):
                mi1, mi2 = st.columns(2)
                occ_options = {o["id"]: f"{o['due_date']}  (€{float(o['amount']):,.0f})"
                               for o in pending_occ}
                selected_occ_id = mi1.selectbox(
                    "Occurrence",
                    options=list(occ_options.keys()),
                    format_func=lambda x: occ_options[x],
                )
                inv_ref = mi2.text_input("Invoice reference / ID",
                                         placeholder="e.g. INV-2026-045")
                if st.form_submit_button("Mark Invoiced"):
                    if not inv_ref.strip():
                        st.error("Please provide an invoice reference.")
                    else:
                        # invoice_id stored as 0 for manual (no FK enforcement needed)
                        db.invoice_occurrence(selected_occ_id, invoice_id=0)
                        st.success(f"Occurrence marked as invoiced (ref: {inv_ref.strip()}).")
                        st.cache_data.clear()
                        st.rerun()
        else:
            st.info("No pending occurrences to mark as invoiced.")

# ------------------------------------------------------------------
# Summary table
# ------------------------------------------------------------------

st.divider()
st.subheader("Summary Table")

summary_rows = []
for f in filtered:
    summary_rows.append({
        "Client":        f["client_name"],
        "Project":       f["project_name"],
        "Description":   f["description"],
        "Billing":       BILLING_TYPE_LABELS.get(f["billing_type"], f["billing_type"]),
        "Frequency":     FREQ_LABELS.get(f["frequency"], f["frequency"]),
        "Base Fee (€)":  float(f["fee_amount"]),
        "Next Due":      f.get("next_due") or "—",
        "Next Amt (€)":  float(f.get("next_amount") or 0),
        "Invoiced":      f["invoiced_count"],
        "Pending":       f["pending_count"],
        "Ends":          f["expected_end"] or "Rolling",
    })

df_sum = pd.DataFrame(summary_rows)
st.dataframe(
    df_sum.style.format({"Base Fee (€)": "{:,.0f}", "Next Amt (€)": "{:,.0f}"}),
    use_container_width=True, hide_index=True,
)
