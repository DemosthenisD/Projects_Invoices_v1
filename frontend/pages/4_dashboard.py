"""
Page 4 — Revenue Dashboard.

Features:
  - Year selector (current year default)
  - Monthly revenue bar chart (net vs gross)
  - Revenue by client bar chart
  - VAT summary table (net + VAT + gross)
  - YTD vs prior year comparison metrics
"""
import sys
import os
from datetime import date as date_type

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd

import backend.db as db

# ------------------------------------------------------------------
# Auth guard
# ------------------------------------------------------------------

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

# ------------------------------------------------------------------
# Page setup
# ------------------------------------------------------------------

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
# Load analytics data
# ------------------------------------------------------------------

@st.cache_data(ttl=120)
def _monthly(year):
    return db.get_monthly_revenue(year)

@st.cache_data(ttl=120)
def _by_client(year):
    return db.get_revenue_by_client(year)

monthly_data   = _monthly(selected_year)
client_data    = _by_client(selected_year)
prior_monthly  = _monthly(prior_year)
prior_client   = _by_client(prior_year)

# ------------------------------------------------------------------
# Helper: totals
# ------------------------------------------------------------------

def _totals(monthly_rows: list[dict]) -> tuple[float, float, float]:
    net   = sum(r["net"]   or 0 for r in monthly_rows)
    vat   = sum(r["vat"]   or 0 for r in monthly_rows)
    gross = sum(r["gross"] or 0 for r in monthly_rows)
    return net, vat, gross

ytd_net,   ytd_vat,   ytd_gross   = _totals(monthly_data)
prior_net, prior_vat, prior_gross = _totals(prior_monthly)

# ------------------------------------------------------------------
# YTD vs prior year metrics
# ------------------------------------------------------------------

st.subheader(f"YTD {selected_year} vs {prior_year}")

def _delta(current: float, prior: float) -> str:
    if prior == 0:
        return None
    pct = (current - prior) / prior * 100
    return f"{pct:+.1f}%"

col1, col2, col3 = st.columns(3)
col1.metric("Net revenue (€)",   f"{ytd_net:,.0f}",   _delta(ytd_net,   prior_net))
col2.metric("VAT collected (€)", f"{ytd_vat:,.0f}",   _delta(ytd_vat,   prior_vat))
col3.metric("Gross (€)",         f"{ytd_gross:,.0f}", _delta(ytd_gross, prior_gross))

st.divider()

# ------------------------------------------------------------------
# Monthly revenue bar chart
# ------------------------------------------------------------------

st.subheader(f"Monthly Revenue — {selected_year}")

if monthly_data:
    df_monthly = pd.DataFrame(monthly_data)
    df_monthly = df_monthly.rename(columns={"month": "Month", "net": "Net (€)", "gross": "Gross (€)"})
    df_monthly = df_monthly.set_index("Month")
    st.bar_chart(df_monthly[["Net (€)", "Gross (€)"]])
else:
    st.info(f"No invoice data for {selected_year}.")

st.divider()

# ------------------------------------------------------------------
# Revenue by client
# ------------------------------------------------------------------

st.subheader(f"Revenue by Client — {selected_year}")

if client_data:
    df_clients = pd.DataFrame(client_data)
    df_clients = df_clients.rename(columns={"client": "Client", "net": "Net (€)", "vat": "VAT (€)"})
    df_clients["Gross (€)"] = df_clients["Net (€)"] + df_clients["VAT (€)"]
    df_clients = df_clients.set_index("Client")
    st.bar_chart(df_clients[["Net (€)", "Gross (€)"]])
else:
    st.info(f"No client data for {selected_year}.")

st.divider()

# ------------------------------------------------------------------
# VAT summary table
# ------------------------------------------------------------------

st.subheader(f"VAT Summary — {selected_year}")

if monthly_data:
    df_vat = pd.DataFrame(monthly_data)
    df_vat = df_vat.rename(columns={
        "month": "Month", "net": "Net (€)", "vat": "VAT (€)", "gross": "Gross (€)"
    })
    totals_row = pd.DataFrame([{
        "Month": "TOTAL",
        "Net (€)":   ytd_net,
        "VAT (€)":   ytd_vat,
        "Gross (€)": ytd_gross,
    }])
    df_vat = pd.concat([df_vat, totals_row], ignore_index=True)
    st.dataframe(
        df_vat.style.format({"Net (€)": "{:,.2f}", "VAT (€)": "{:,.2f}", "Gross (€)": "{:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(f"No VAT data for {selected_year}.")

st.divider()

# ------------------------------------------------------------------
# Pipeline Forecast
# ------------------------------------------------------------------

st.subheader("Pipeline Forecast")

@st.cache_data(ttl=120)
def _pipeline():
    return db.get_pipeline()

pipeline = _pipeline()
forecast_rows = [
    r for r in pipeline
    if (r.get("budget_min") or r.get("budget_est") or r.get("budget_max"))
    and r.get("probability") is not None
]

if forecast_rows:
    fw_min = sum((r["budget_min"] or 0) * (r["probability"] or 0) for r in forecast_rows)
    fw_est = sum((r["budget_est"] or 0) * (r["probability"] or 0) for r in forecast_rows)
    fw_max = sum((r["budget_max"] or 0) * (r["probability"] or 0) for r in forecast_rows)

    fc1, fc2, fc3 = st.columns(3)
    fc1.metric("Weighted Min (€)", f"{fw_min:,.0f}")
    fc2.metric("Weighted Est (€)", f"{fw_est:,.0f}")
    fc3.metric("Weighted Max (€)", f"{fw_max:,.0f}")
    st.caption(f"Based on {len(forecast_rows)} pipeline projects with budget fields set. "
               "Σ(budget × probability). Edit budgets and probabilities on the Pipeline / CRM page.")
else:
    st.info("No pipeline forecast data. Set Min/Est/Max budgets and probabilities on the Pipeline / CRM page.")
