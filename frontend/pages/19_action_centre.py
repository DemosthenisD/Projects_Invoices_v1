"""
Page — Action Centre (landing page).

One place that answers "what needs my attention today?":
overdue invoices, recurring fees to bill, overdue receivables,
stale prospects, and active projects with time charged but not invoiced.
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import backend.db as db
from shared.ui import require_auth, go_invoice, fmt_date

require_auth()

st.title("Action Centre")
today = date.today()
st.caption(f"What needs attention today — {today.strftime('%A %d %B %Y')}")

# ------------------------------------------------------------------
# Thresholds (kept for this browser session)
# ------------------------------------------------------------------

with st.expander("Settings", expanded=False):
    s1, s2, s3 = st.columns(3)
    overdue_days = s1.number_input("Invoice overdue after (days from invoice date)", 1, 365, 30, key="ac_overdue_days")
    stale_days = s2.number_input("Prospect stale after (days in stage)", 1, 730, 60, key="ac_stale_days")
    unbilled_min = s3.number_input("Unbilled time threshold (€)", 0, 1_000_000, 5000, step=1000, key="ac_unbilled_min")


@st.cache_data(ttl=60)
def _invoices():
    return db.get_invoices()


@st.cache_data(ttl=60)
def _recurring_due():
    return [o for o in db.get_pending_occurrences(days_ahead=30) if o["billing_type"] == "we_bill"]


@st.cache_data(ttl=60)
def _receivables():
    return db.get_receivables(outstanding_only=True)


@st.cache_data(ttl=60)
def _pipeline():
    return db.get_pipeline()


@st.cache_data(ttl=60)
def _unbilled_source():
    arrangement = {p.id: p.billing_arrangement for p in db.get_projects()}
    return [r for r in db.get_all_projects_overview()
            if r["status"] == "Active" and arrangement.get(r["project_id"]) == "local"
            and r["client_type"] != "internal"]


# ------------------------------------------------------------------
# Gather
# ------------------------------------------------------------------

client_name = {c.id: c.name for c in db.get_clients()}

overdue_inv = []
for i in _invoices():
    gross = i.amount + i.vat_amount + i.expenses_net + i.expenses_vat
    if i.status in ("outstanding", "partial") and gross > 0:
        age = (today - date.fromisoformat(i.date)).days
        if age > overdue_days:
            overdue_inv.append({
                "Invoice": f"{i.invoice_number}/{i.year}", "Date": fmt_date(i.date),
                "Client": client_name.get(i.client_id, "—"), "Project": i.project_name or "—",
                "Days old": age, "Balance (€)": round(gross - i.total_paid, 2),
            })
overdue_inv.sort(key=lambda r: -r["Days old"])

rec_due = _recurring_due()
rec_overdue = [o for o in rec_due if o["due_date"] < today.isoformat()]

recv_overdue = [r for r in _receivables() if r["due_date"] and r["due_date"] < today.isoformat()]

stale = []
for p in _pipeline():
    if p["is_prospect"] and p["stage"] == "Prospect":
        since = p.get("date_entered_stage") or p.get("date_entered_pipeline") or (p.get("updated_at") or "")[:10]
        try:
            days = (today - date.fromisoformat(since)).days
        except ValueError:
            days = 0
        nad = (p.get("next_action_date") or "")[:10]
        reasons = []
        if nad and nad < today.isoformat():
            reasons.append(f"next action overdue since {fmt_date(nad)}")
        if days > stale_days:
            reasons.append(f"{days} days in stage")
        if reasons:
            stale.append({"Company": p["company_name"], "Opportunity": p["prospect_name"] or "—",
                          "Step": p.get("prospect_step") or "—",
                          "Next action": p.get("next_action") or "—",
                          "Why": "; ".join(reasons), "Days": days,
                          "Est. budget (€)": p["budget_est"], "Probability": f"{(p['probability'] or 0) * 100:.0f}%"})
stale.sort(key=lambda r: -r["Days"])

unbilled = []
for r in _unbilled_source():
    gap = r["billable_charges"] - r["write_offs"] - r["invoiced"]
    if gap > unbilled_min:
        unbilled.append({"project_id": r["project_id"], "Client": r["client"], "Project": r["project"],
                         "Time charges (€)": r["billable_charges"], "Write-offs (€)": r["write_offs"],
                         "Invoiced (€)": r["invoiced"], "Not yet invoiced (€)": gap})
unbilled.sort(key=lambda r: -r["Not yet invoiced (€)"])

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Overdue invoices", len(overdue_inv), f"€{sum(r['Balance (€)'] for r in overdue_inv):,.0f}", delta_color="off")
m2.metric("Recurring to bill", len(rec_due), f"{len(rec_overdue)} overdue", delta_color="off")
m3.metric("Overdue receivables", len(recv_overdue),
          f"€{sum(r['outstanding'] for r in recv_overdue):,.0f}", delta_color="off")
m4.metric("Prospects to chase", len(stale))
m5.metric("Time not invoiced", len(unbilled), f"€{sum(r['Not yet invoiced (€)'] for r in unbilled):,.0f}", delta_color="off")

total = len(overdue_inv) + len(rec_due) + len(recv_overdue) + len(stale) + len(unbilled)
if total == 0:
    st.success("✅ Nothing needs attention right now.")

st.divider()

# ------------------------------------------------------------------
# Sections
# ------------------------------------------------------------------

with st.expander(f"🧾 Overdue invoices ({len(overdue_inv)})", expanded=bool(overdue_inv)):
    if overdue_inv:
        st.dataframe(pd.DataFrame(overdue_inv).style.format({"Balance (€)": "{:,.2f}"}),
                     use_container_width=True, hide_index=True)
        st.page_link("pages/2_invoice_log.py", label="Record payments in the Invoice Log →", icon="📋")
    else:
        st.caption(f"No invoice is more than {overdue_days} days old and unpaid.")

with st.expander(f"🔁 Recurring invoices to raise — overdue or due in 30 days ({len(rec_due)})", expanded=bool(rec_due)):
    if rec_due:
        for o in rec_due:
            late = o["due_date"] < today.isoformat()
            c1, c2, c3 = st.columns([6, 2, 2])
            c1.markdown(f"{'🔴' if late else '🟡'} **{o['client_name']} — {o['project_name']}** · "
                        f"{o['fee_description']} · due {fmt_date(o['due_date'])}")
            c2.write(f"€{float(o['amount']):,.2f}")
            if c3.button("Invoice this →", key=f"ac_rec_{o['id']}", use_container_width=True):
                go_invoice(o["project_id"], o["id"])
    else:
        st.caption("No recurring invoices due in the next 30 days.")

with st.expander(f"📥 Overdue receivables ({len(recv_overdue)})", expanded=bool(recv_overdue)):
    if recv_overdue:
        st.dataframe(pd.DataFrame([{
            "Client": r["client_name"], "Project": r["project_name"], "Description": r["description"],
            "Due": fmt_date(r["due_date"]), "Outstanding (€)": round(r["outstanding"], 2),
        } for r in recv_overdue]).style.format({"Outstanding (€)": "{:,.2f}"}),
            use_container_width=True, hide_index=True)
        st.page_link("pages/17_receivables.py", label="Record receipts in Receivables →", icon="📥")
    else:
        st.caption("No overdue receivables.")

with st.expander(f"🎯 Prospects to chase - overdue next action or stale ({len(stale)})", expanded=bool(stale)):
    if stale:
        st.dataframe(pd.DataFrame(stale).style.format({"Est. budget (€)": "{:,.0f}"}),
                     use_container_width=True, hide_index=True)
        st.page_link("pages/4_pipeline_crm.py", label="Update them in Pipeline / CRM →", icon="📊")
    else:
        st.caption(f"No overdue next actions, and no prospect in its stage for more than {stale_days} days.")

with st.expander(f"⏱️ Active projects with time charged but not invoiced ({len(unbilled)})", expanded=bool(unbilled)):
    st.caption("Time charges − write-offs − invoiced, for active projects we invoice directly. "
               "Large gaps may mean an invoice is due, or a write-off / close-out is needed "
               "(Project Overview → Project Close-out).")
    if unbilled:
        for r in unbilled[:15]:
            c1, c2, c3 = st.columns([6, 2, 2])
            c1.markdown(f"**{r['Client']} — {r['Project']}**")
            c2.write(f"€{r['Not yet invoiced (€)']:,.0f}")
            if c3.button("Invoice →", key=f"ac_unb_{r['project_id']}", use_container_width=True):
                go_invoice(r["project_id"])
        if len(unbilled) > 15:
            st.caption(f"… and {len(unbilled) - 15} more")
    else:
        st.caption(f"No active project has more than €{unbilled_min:,.0f} of time not yet invoiced.")
