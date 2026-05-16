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

all_types     = sorted({r["client_type"] for r in cur_rows if r.get("client_type")})
all_countries = sorted({r["country"] for r in cur_rows if r.get("country")})
all_clients   = sorted({r["client"] for r in cur_rows if r.get("client")})

fc1, fc2, fc3 = st.columns(3)
f_types    = fc1.multiselect("Client Type", all_types,    key="dash_types")
f_countries= fc2.multiselect("Country",     all_countries, key="dash_countries")
f_clients  = fc3.multiselect("Client",      all_clients,   key="dash_clients")

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

