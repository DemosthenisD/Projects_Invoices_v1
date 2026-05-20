"""
Page 4 — Revenue Dashboard.

Features:
  - Year selector (current year default)
  - Global Client / Client Type / Country multiselect filters
  - YTD metrics: absolute + % change vs same-period prior year
  - Monthly revenue bar chart (net vs gross)
  - Revenue by client bar chart with client multiselect
  - VAT summary table
  - Pipeline forecast
"""
import sys
import os
from datetime import date as date_type
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd

import backend.db as db
from shared.ui import require_auth

require_auth()

st.title("Revenue Dashboard")

# ------------------------------------------------------------------
# Year selector
# ------------------------------------------------------------------

current_year = date_type.today().year

@st.cache_data(ttl=120)
def _all_years():
    invoices = db.get_invoices()
    years = sorted({i.year for i in invoices}, reverse=True)
    return years if years else [current_year]

all_years = _all_years()
selected_year = st.selectbox("Year", all_years, index=0)
prior_year = selected_year - 1

# ------------------------------------------------------------------
# Billing reminders — recurring occurrences due within 60 days
# ------------------------------------------------------------------

@st.cache_data(ttl=300)
def _billing_reminders() -> list[dict]:
    return db.get_pending_occurrences(days_ahead=60)

_all_pending   = _billing_reminders()
_we_bill_due   = [o for o in _all_pending if o["billing_type"] == "we_bill"]
_overdue       = [o for o in _we_bill_due
                  if o["due_date"] < date_type.today().isoformat()]
_upcoming      = [o for o in _we_bill_due
                  if o["due_date"] >= date_type.today().isoformat()]

if _overdue:
    st.error(
        f"⚠️ **{len(_overdue)} recurring invoice(s) overdue** — "
        "go to Project Overview → Recurring Fees to action."
    )
if _upcoming:
    st.warning(f"🔔 **{len(_upcoming)} recurring invoice(s) due within 60 days.**")

if _we_bill_due:
    with st.expander(
        f"{'⚠️ ' if _overdue else ''}View {len(_we_bill_due)} billing reminder(s)",
        expanded=bool(_overdue),
    ):
        _df_rem = pd.DataFrame([{
            "Client":      o["client_name"],
            "Project":     o["project_name"],
            "Code":        f"{o['client_code']}{o['client_suffix']}",
            "Description": o["fee_description"],
            "Due Date":    o["due_date"],
            "Amount (€)":  o["amount"],
            "Split (€)":   o["split_amount"],
            "Frequency":   o["frequency"],
        } for o in _we_bill_due])
        st.dataframe(
            _df_rem.style.format({"Amount (€)": "{:,.2f}", "Split (€)": "{:,.2f}"}),
            use_container_width=True, hide_index=True,
        )
        st.caption(
            "Invoice from a pending occurrence via **Generate Invoice** "
            "or manage fees in **Project Overview → Recurring Fees**."
        )

# ------------------------------------------------------------------
# Load detailed invoice data for both years
# ------------------------------------------------------------------

@st.cache_data(ttl=120)
def _detail(year):
    return db.get_invoices_detailed(year)

cur_rows  = _detail(selected_year)
prev_rows = _detail(prior_year)

# ------------------------------------------------------------------
# Global filters: Client Type, Country, Client
# ------------------------------------------------------------------

all_types = sorted({r["client_type"] for r in cur_rows if r.get("client_type")})

fc1, fc2, fc3 = st.columns(3)
f_types = fc1.multiselect("Client Type", all_types, key="dash_types")

# Cascade: countries available after type filter is applied
_rows_after_type = [r for r in cur_rows if not f_types or r.get("client_type") in f_types]
all_countries = sorted({r["country"] for r in _rows_after_type if r.get("country")})
f_countries = fc2.multiselect("Country", all_countries, key="dash_countries",
                               default=[v for v in st.session_state.get("dash_countries", []) if v in all_countries])

# Cascade: clients available after type + country filters are applied
_rows_after_country = [r for r in _rows_after_type if not f_countries or r.get("country") in f_countries]
all_clients = sorted({r["client"] for r in _rows_after_country if r.get("client")})
f_clients = fc3.multiselect("Client", all_clients, key="dash_clients",
                              default=[v for v in st.session_state.get("dash_clients", []) if v in all_clients])

def _apply_filters(rows):
    out = rows
    if f_types:
        out = [r for r in out if r.get("client_type") in f_types]
    if f_countries:
        out = [r for r in out if r.get("country") in f_countries]
    if f_clients:
        out = [r for r in out if r.get("client") in f_clients]
    return out

cur_f  = _apply_filters(cur_rows)
prev_f = _apply_filters(prev_rows)

# ------------------------------------------------------------------
# Same-period cutoff: if viewing current year, limit prior year to
# the same months (Jan → current month).
# ------------------------------------------------------------------

cutoff_month = date_type.today().month if selected_year == current_year else 12
prev_same_period = [
    r for r in prev_f
    if r.get("month") and int(r["month"].split("-")[1]) <= cutoff_month
]

# ------------------------------------------------------------------
# Aggregate helpers
# ------------------------------------------------------------------

def _sum(rows, field):
    return sum(r.get(field) or 0 for r in rows)

ytd_net   = _sum(cur_f, "net")
ytd_vat   = _sum(cur_f, "vat")
ytd_gross = _sum(cur_f, "gross")

prior_net   = _sum(prev_same_period, "net")
prior_vat   = _sum(prev_same_period, "vat")
prior_gross = _sum(prev_same_period, "gross")

# ------------------------------------------------------------------
# YTD metrics
# ------------------------------------------------------------------

period_label = (
    f"Jan–{'JFMAMJJASOND'[cutoff_month-1:cutoff_month]} {selected_year}"
    if selected_year == current_year
    else str(selected_year)
)
prior_period_label = (
    f"Jan–{'JFMAMJJASOND'[cutoff_month-1:cutoff_month]} {prior_year}"
    if selected_year == current_year
    else str(prior_year)
)

# Build the abbreviated month name properly
import calendar
month_abbr = calendar.month_abbr[cutoff_month]
period_label       = f"Jan–{month_abbr} {selected_year}" if selected_year == current_year else str(selected_year)
prior_period_label = f"Jan–{month_abbr} {prior_year}"   if selected_year == current_year else str(prior_year)

st.subheader(f"YTD {period_label} vs {prior_period_label}")

def _pct_change(current: float, prior: float) -> float | None:
    if prior == 0:
        return None
    return (current - prior) / prior * 100

def _metric(col, label, cur, pri):
    """Render a metric with signed delta so Streamlit colors it correctly."""
    pct = _pct_change(cur, pri)
    if pct is not None:
        sign = "+" if pct >= 0 else ""
        delta_str = f"{sign}{pct:.1f}% vs {prior_period_label} (€{pri:,.0f})"
    else:
        delta_str = f"vs {prior_period_label}: €{pri:,.0f}" if pri else None
    col.metric(label, f"€{cur:,.0f}", delta_str)

@st.cache_data(ttl=120)
def _outstanding_balance() -> float:
    return sum(
        (inv.amount + inv.vat_amount + inv.expenses_net + inv.expenses_vat) - inv.total_paid
        for inv in db.get_invoices()
        if inv.status in ("outstanding", "partial")
    )

col1, col2, col3, col4 = st.columns(4)
_metric(col1, "Net Revenue (€)",   ytd_net,   prior_net)
_metric(col2, "VAT Collected (€)", ytd_vat,   prior_vat)
_metric(col3, "Gross Revenue (€)", ytd_gross, prior_gross)
col4.metric("Outstanding (€)", f"€{_outstanding_balance():,.0f}",
            help="Gross balance due on all open/partial invoices across all years")

st.divider()

# ------------------------------------------------------------------
# Monthly revenue bar chart
# ------------------------------------------------------------------

st.subheader(f"Monthly Revenue — {selected_year}")

if cur_f:
    monthly_agg: dict = defaultdict(lambda: {"net": 0.0, "gross": 0.0})
    for r in cur_f:
        m = r.get("month") or "Unknown"
        monthly_agg[m]["net"]   += r.get("net") or 0
        monthly_agg[m]["gross"] += r.get("gross") or 0
    df_monthly = pd.DataFrame([
        {"Month": m, "Net (€)": v["net"], "Gross (€)": v["gross"]}
        for m, v in sorted(monthly_agg.items())
    ]).set_index("Month")
    st.bar_chart(df_monthly[["Net (€)", "Gross (€)"]])
else:
    st.info(f"No invoice data for {selected_year} matching the selected filters.")

st.divider()

# ------------------------------------------------------------------
# Revenue by client
# ------------------------------------------------------------------

st.subheader(f"Revenue by Client — {selected_year}")

if cur_f:
    client_agg: dict = defaultdict(lambda: {"net": 0.0, "vat": 0.0})
    for r in cur_f:
        cl = r.get("client") or "Unknown"
        client_agg[cl]["net"] += r.get("net") or 0
        client_agg[cl]["vat"] += r.get("vat") or 0
    df_clients_all = pd.DataFrame([
        {"Client": cl, "Net (€)": v["net"], "VAT (€)": v["vat"],
         "Gross (€)": v["net"] + v["vat"]}
        for cl, v in sorted(client_agg.items(), key=lambda x: -x[1]["net"])
    ])

    # Client-level multiselect inside Revenue by Client section
    _chart_client_opts = df_clients_all["Client"].tolist()
    _chart_clients = st.multiselect(
        "Filter clients in chart", _chart_client_opts, key="dash_chart_clients",
        help="Leave empty to show all"
    )
    df_chart = (
        df_clients_all[df_clients_all["Client"].isin(_chart_clients)]
        if _chart_clients else df_clients_all
    ).set_index("Client")
    st.bar_chart(df_chart[["Net (€)", "Gross (€)"]])
else:
    st.info(f"No client data for {selected_year} matching the selected filters.")

st.divider()

# ------------------------------------------------------------------
# VAT summary table
# ------------------------------------------------------------------

st.subheader(f"VAT Summary — {selected_year}")

if cur_f:
    monthly_vat: dict = defaultdict(lambda: {"net": 0.0, "vat": 0.0, "gross": 0.0})
    for r in cur_f:
        m = r.get("month") or "Unknown"
        monthly_vat[m]["net"]   += r.get("net") or 0
        monthly_vat[m]["vat"]   += r.get("vat") or 0
        monthly_vat[m]["gross"] += r.get("gross") or 0
    vat_rows = [
        {"Month": m, "Net (€)": v["net"], "VAT (€)": v["vat"], "Gross (€)": v["gross"]}
        for m, v in sorted(monthly_vat.items())
    ]
    totals_row = {
        "Month": "TOTAL",
        "Net (€)": ytd_net, "VAT (€)": ytd_vat, "Gross (€)": ytd_gross,
    }
    df_vat = pd.DataFrame(vat_rows + [totals_row])
    st.dataframe(
        df_vat.style.format({"Net (€)": "{:,.2f}", "VAT (€)": "{:,.2f}", "Gross (€)": "{:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(f"No VAT data for {selected_year} matching the selected filters.")

# ------------------------------------------------------------------
# Inter-office revenue (receivable-arrangement projects)
# ------------------------------------------------------------------

st.divider()
st.subheader(f"Inter-office Revenue — {selected_year}")
st.caption(
    "Time charges logged on projects where another Milliman entity holds the client contract. "
    "These do not appear in the invoice-based revenue above. "
    "Toggle the section below to include them in your total view."
)

@st.cache_data(ttl=120)
def _interoffice(year: int) -> list[dict]:
    return db.get_interoffice_charges(year)

io_rows      = _interoffice(selected_year)
io_rows_prev = _interoffice(prior_year)

io_total      = sum(r["billable_charges"] for r in io_rows)
io_total_prev = sum(r["billable_charges"] for r in io_rows_prev)

ioc1, ioc2, ioc3 = st.columns(3)
ioc1.metric(
    f"Inter-office Charges {selected_year} (€)",
    f"€{io_total:,.0f}",
)
ioc2.metric(
    f"Prior year {prior_year} (€)",
    f"€{io_total_prev:,.0f}",
)
combined = ytd_net + io_total
ioc3.metric(
    "Combined Net + Inter-office (€)",
    f"€{combined:,.0f}",
    help="Local net revenue plus inter-office charges — total economic contribution",
)

if io_rows:
    with st.expander(f"View {len(io_rows)} inter-office project(s)", expanded=False):
        df_io = pd.DataFrame([{
            "Client":            r["client_name"],
            "Project":           r["project_name"],
            "Billable Hrs":      r["billable_hours"],
            "Billable Charges (€)": r["billable_charges"],
            "Overhead Hrs":      r["overhead_hours"],
        } for r in io_rows])
        _io_tot = {
            "Client": "TOTAL",
            "Project": "",
            "Billable Hrs":         df_io["Billable Hrs"].sum(),
            "Billable Charges (€)": df_io["Billable Charges (€)"].sum(),
            "Overhead Hrs":         df_io["Overhead Hrs"].sum(),
        }
        st.dataframe(
            df_io.style.format({
                "Billable Charges (€)": "{:,.2f}",
                "Billable Hrs": "{:.1f}",
                "Overhead Hrs": "{:.1f}",
            }),
            use_container_width=True, hide_index=True,
        )
        st.caption(
            f"Total: **€{io_total:,.0f}** across {len(io_rows)} project(s). "
            "Manage receivables for these projects in the **Receivables** section below "
            "or via **Project Overview**."
        )
else:
    st.info(f"No inter-office time charges recorded for {selected_year}.")

# ------------------------------------------------------------------
# Receivables Aging
# ------------------------------------------------------------------

st.divider()
st.subheader("Receivables Aging")

@st.cache_data(ttl=120)
def _aging_data(today_iso: str) -> list[dict]:
    all_inv     = db.get_invoices()
    client_lkp  = {c.id: c.name for c in db.get_clients()}
    today       = date_type.fromisoformat(today_iso)
    rows = []
    for inv in all_inv:
        if inv.status not in ("outstanding", "partial"):
            continue
        due = (inv.amount + inv.vat_amount + inv.expenses_net + inv.expenses_vat) - inv.total_paid
        if due <= 0:
            continue
        try:
            days = (today - date_type.fromisoformat(inv.date)).days
        except ValueError:
            days = 0
        rows.append({
            "Client":    client_lkp.get(inv.client_id, "Unknown"),
            "Invoice":   f"{inv.invoice_number}/{inv.year}",
            "Date":      inv.date,
            "Status":    inv.status,
            "Due (€)":   round(due, 2),
            "Days":      days,
            "Bracket":   ("0–30 d" if days <= 30 else
                          "31–60 d" if days <= 60 else
                          "61–90 d" if days <= 90 else
                          "90+ d"),
        })
    return sorted(rows, key=lambda r: -r["Days"])

_today_iso = date_type.today().isoformat()
aging_rows = _aging_data(_today_iso)

if not aging_rows:
    st.info("No outstanding or partial invoices.")
else:
    BRACKETS = ["0–30 d", "31–60 d", "61–90 d", "90+ d"]
    _b_cols = st.columns(4)
    for _col, _bkt in zip(_b_cols, BRACKETS):
        _bkt_rows = [r for r in aging_rows if r["Bracket"] == _bkt]
        _bkt_total = sum(r["Due (€)"] for r in _bkt_rows)
        _col.metric(_bkt, f"€{_bkt_total:,.0f}", f"{len(_bkt_rows)} invoice(s)" if _bkt_rows else "—")

    _age_filter = st.multiselect("Filter by age bracket", BRACKETS, key="dash_age_filter")
    _age_rows   = [r for r in aging_rows if not _age_filter or r["Bracket"] in _age_filter]
    df_aging = pd.DataFrame(_age_rows)
    st.dataframe(
        df_aging.style.format({"Due (€)": "{:,.2f}"}),
        use_container_width=True, hide_index=True,
    )
    st.caption(
        f"Total outstanding: **€{sum(r['Due (€)'] for r in _age_rows):,.0f}** "
        f"across {len(_age_rows)} invoice(s)"
    )

st.divider()
st.page_link("pages/1_how_to_use.py", label="New here? Read the How to Use guide", icon="📖")

