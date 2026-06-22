"""
Pipeline Financial Dashboard.

Shows Prospect / Active / On Hold pipeline entries side-by-side with
financial actuals (time charges, invoiced, paid) and four budget columns:

  Budget if Converted  — raw budget without probability discount
  Budget Realistic     — budget × probability (prospects) or code_budget (active/on hold)
  Min Expected         — budget_min × probability
  Max Possible         — budget_max × probability

All "Remaining" columns use Budget Realistic as the base.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from collections import defaultdict

import backend.db as db
from shared.ui import require_auth, dataframe_with_total

require_auth()

st.title("Pipeline Financial Dashboard")
st.caption(
    "Prospect, Active and On Hold entries with probability-adjusted budget columns and financial actuals. "
    "Active / On Hold projects use their contracted project-code budgets (probability = 100%). "
    "Prospects use their pipeline budget estimates discounted by probability of winning."
)

STAGES = ["Active", "On Hold", "Prospect"]
STAGE_COLORS = {"Active": "🟢", "On Hold": "🟡", "Prospect": "🔵"}

# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load():
    rows        = db.get_pipeline_financial_summary()
    source_teams = db.get_pipeline_source_teams()
    return rows, source_teams

raw_rows, source_teams = _load()

if not raw_rows:
    st.info("No pipeline entries found for the selected stages.")
    st.stop()

# ------------------------------------------------------------------
# Compute derived budget columns
# ------------------------------------------------------------------

def _budget_cols(r: dict) -> dict:
    is_prospect = bool(r["is_prospect"])
    prob        = float(r["probability"])
    eff_prob    = prob if is_prospect else 1.0

    if is_prospect:
        b_base = float(r["budget_est"])
        b_min  = float(r["budget_min"])
        b_max  = float(r["budget_max"])
    else:
        b_base = float(r["code_budget"])
        b_min  = float(r["budget_min"]) if float(r["budget_min"]) > 0 else b_base
        b_max  = float(r["budget_max"]) if float(r["budget_max"]) > 0 else b_base

    budget_if_conv  = b_base
    budget_realistic = b_base * eff_prob
    min_expected    = b_min  * eff_prob
    max_possible    = b_max  * eff_prob
    time_charges    = float(r["time_charges"])
    invoiced        = float(r["invoiced_amount"])
    paid            = float(r["paid_amount"])

    return {
        "budget_if_conv":   budget_if_conv,
        "budget_realistic": budget_realistic,
        "min_expected":     min_expected,
        "max_possible":     max_possible,
        "time_charges":     time_charges,
        "invoiced":         invoiced,
        "paid":             paid,
        "rem_budget":       budget_realistic - time_charges,
        "rem_to_invoice":   budget_realistic - invoiced,
        "rem_cash":         budget_realistic - paid,
        "prob":             eff_prob,
    }

enriched = []
for r in raw_rows:
    bc = _budget_cols(r)
    enriched.append({**r, **bc, "source_team": source_teams.get(r["project_id"] or -1, "—")})

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

all_countries  = sorted({r["country"]     for r in enriched if r.get("country")})
all_types      = sorted({r["client_type"] for r in enriched if r.get("client_type")})
all_teams      = sorted({r["source_team"] for r in enriched if r.get("source_team") and r["source_team"] != "—"})

fc1, fc2, fc3, fc4 = st.columns(4)
f_stages  = fc1.multiselect("Stage",       STAGES,       default=STAGES,   key="pf_stages")
f_country = fc2.multiselect("Country",     all_countries,                  key="pf_country")
f_type    = fc3.multiselect("Client Type", all_types,                      key="pf_type")
f_team    = fc4.multiselect("Source Team", all_teams,                      key="pf_team")

filtered = [
    r for r in enriched
    if (not f_stages  or r["stage"]       in f_stages)
    and (not f_country or r["country"]     in f_country)
    and (not f_type   or r["client_type"]  in f_type)
    and (not f_team   or r["source_team"]  in f_team)
]

if not filtered:
    st.info("No entries match the selected filters.")
    st.stop()

# ------------------------------------------------------------------
# Stage summary metrics
# ------------------------------------------------------------------

st.subheader("By Stage")
s_cols = st.columns(len(STAGES))
for col, stage in zip(s_cols, STAGES):
    s_rows = [r for r in filtered if r["stage"] == stage]
    total  = sum(r["budget_realistic"] for r in s_rows)
    col.metric(
        f"{STAGE_COLORS[stage]} {stage}",
        f"€{total:,.0f}",
        f"{len(s_rows)} entr{'y' if len(s_rows)==1 else 'ies'}",
    )

st.divider()

# ------------------------------------------------------------------
# Top-level summary metrics
# ------------------------------------------------------------------

_tot_real    = sum(r["budget_realistic"] for r in filtered)
_tot_tc      = sum(r["time_charges"]     for r in filtered)
_tot_inv     = sum(r["invoiced"]         for r in filtered)
_tot_paid    = sum(r["paid"]             for r in filtered)
_tot_rem_bgt = sum(r["rem_budget"]       for r in filtered)
_tot_rem_inv = sum(r["rem_to_invoice"]   for r in filtered)
_tot_rem_csh = sum(r["rem_cash"]         for r in filtered)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Budget Realistic (€)", f"€{_tot_real:,.0f}")
m2.metric("Time Charges (€)",     f"€{_tot_tc:,.0f}")
m3.metric("Invoiced (€)",         f"€{_tot_inv:,.0f}")
m4.metric("Paid (€)",             f"€{_tot_paid:,.0f}")

r1, r2, r3, _ = st.columns(4)
r1.metric("Remaining Budget (€)",    f"€{_tot_rem_bgt:,.0f}",
          help="Budget Realistic − Time Charges")
r2.metric("Remaining to Invoice (€)", f"€{_tot_rem_inv:,.0f}",
          help="Budget Realistic − Invoiced")
r3.metric("Remaining Cash (€)",      f"€{_tot_rem_csh:,.0f}",
          help="Budget Realistic − Paid")

st.divider()

# ------------------------------------------------------------------
# Grouping toggle
# ------------------------------------------------------------------

group_by = st.radio(
    "Group / view by",
    ["Detail (all entries)", "Client", "Country", "Source Team"],
    horizontal=True, key="pf_group",
)

# ------------------------------------------------------------------
# Detail table
# ------------------------------------------------------------------

_FMT_COLS = [
    "Budget if Conv. (€)", "Prob %", "Budget Realistic (€)",
    "Min Expected (€)", "Max Possible (€)",
    "Time Charges (€)", "Invoiced (€)", "Paid (€)",
    "Rem. Budget (€)", "Rem. to Invoice (€)", "Rem. Cash (€)",
]

if group_by == "Detail (all entries)":
    detail_rows = []
    for r in filtered:
        detail_rows.append({
            "Stage":               f"{STAGE_COLORS[r['stage']]} {r['stage']}",
            "Client":              r["client_name"],
            "Project / Opp.":      r["project_name"],
            "Country":             r["country"] or "—",
            "Source Team":         r["source_team"],
            "Budget if Conv. (€)": r["budget_if_conv"],
            "Prob %":              round(r["prob"] * 100, 0),
            "Budget Realistic (€)":r["budget_realistic"],
            "Min Expected (€)":    r["min_expected"],
            "Max Possible (€)":    r["max_possible"],
            "Time Charges (€)":    r["time_charges"],
            "Invoiced (€)":        r["invoiced"],
            "Paid (€)":            r["paid"],
            "Rem. Budget (€)":     r["rem_budget"],
            "Rem. to Invoice (€)": r["rem_to_invoice"],
            "Rem. Cash (€)":       r["rem_cash"],
        })
    df = pd.DataFrame(detail_rows)
    _num_fmt = {c: "{:,.0f}" for c in _FMT_COLS if c != "Prob %"}
    _num_fmt["Prob %"] = "{:.0f}"
    st.dataframe(
        df.style.format(_num_fmt),
        use_container_width=True, hide_index=True,
    )
    st.caption(f"{len(detail_rows)} entr{'y' if len(detail_rows)==1 else 'ies'}")

# ------------------------------------------------------------------
# Grouped views
# ------------------------------------------------------------------

else:
    group_key = {
        "Client":      "client_name",
        "Country":     "country",
        "Source Team": "source_team",
    }[group_by]

    _agg: dict = defaultdict(lambda: defaultdict(float))
    _counts: dict = defaultdict(int)
    for r in filtered:
        key = r[group_key] or "—"
        _counts[key] += 1
        for col in ["budget_if_conv", "budget_realistic", "min_expected", "max_possible",
                    "time_charges", "invoiced", "paid", "rem_budget", "rem_to_invoice", "rem_cash"]:
            _agg[key][col] += r[col]

    grp_rows = []
    for key in sorted(_agg.keys()):
        a = _agg[key]
        grp_rows.append({
            group_by:              key,
            "Entries":             _counts[key],
            "Budget if Conv. (€)": a["budget_if_conv"],
            "Budget Realistic (€)":a["budget_realistic"],
            "Min Expected (€)":    a["min_expected"],
            "Max Possible (€)":    a["max_possible"],
            "Time Charges (€)":    a["time_charges"],
            "Invoiced (€)":        a["invoiced"],
            "Paid (€)":            a["paid"],
            "Rem. Budget (€)":     a["rem_budget"],
            "Rem. to Invoice (€)": a["rem_to_invoice"],
            "Rem. Cash (€)":       a["rem_cash"],
        })

    _grp_num_cols = [c for c in _FMT_COLS if c != "Prob %"]
    df_grp = pd.DataFrame(grp_rows)
    _tot_grp = {c: df_grp[c].sum() if c in _grp_num_cols else ("TOTAL" if c == group_by else df_grp[c].sum())
                for c in df_grp.columns}
    _tot_grp[group_by] = "TOTAL"
    _tot_grp["Entries"] = df_grp["Entries"].sum()

    dataframe_with_total(df_grp, _tot_grp, {c: "{:,.0f}" for c in _grp_num_cols})

# ------------------------------------------------------------------
# Recurring Revenue Forecast
# ------------------------------------------------------------------

st.divider()
st.subheader("Recurring Revenue Forecast")
st.caption(
    "Future occurrences from active recurring fees on all project codes. "
    "Amounts are indexed where applicable. "
    "**We bill** = amounts we will invoice. "
    "**Third-party bills** = our share we expect to receive (split amount)."
)

horizon = st.slider("Forecast horizon (years)", min_value=1, max_value=5, value=3,
                    key="pf_horizon")

@st.cache_data(ttl=120)
def _forecast(h: int) -> list[dict]:
    return db.get_recurring_revenue_forecast(h)

forecast = _forecast(horizon)

if not forecast:
    st.info("No pending recurring fee occurrences found within the selected horizon.")
else:
    from datetime import date as _date
    current_year = _date.today().year
    all_years    = sorted({r["year"] for r in forecast})

    # Split by billing type
    we_bill_rows  = [r for r in forecast if r["billing_type"] == "we_bill"]
    recv_rows     = [r for r in forecast if r["billing_type"] == "third_party_bills"]

    # ---- Year-by-year summary metrics --------------------------------
    fy_cols = st.columns(len(all_years))
    for col, yr in zip(fy_cols, all_years):
        yr_we   = sum(r["fee_total"]   for r in we_bill_rows  if r["year"] == yr)
        yr_recv = sum(r["split_total"] for r in recv_rows     if r["year"] == yr)
        yr_tot  = yr_we + yr_recv
        label   = f"{yr} {'(current)' if yr == current_year else ''}"
        col.metric(label, f"€{yr_tot:,.0f}",
                   f"↑ €{yr_we:,.0f} billed · ↓ €{yr_recv:,.0f} received")

    st.divider()

    # ---- Helper: build pivot DataFrame --------------------------------
    def _pivot(rows: list[dict], amount_col: str) -> pd.DataFrame | None:
        if not rows:
            return None
        records = []
        for r in rows:
            records.append({
                "client_name":   r["client_name"],
                "project_name":  r["project_name"],
                "fee_description": r["fee_description"],
                "billing_arrangement": r["billing_arrangement"],
                "year":          r["year"],
                "amount":        r[amount_col],
            })
        df = pd.DataFrame(records)
        pivot = df.pivot_table(
            index=["client_name", "project_name", "fee_description", "billing_arrangement"],
            columns="year",
            values="amount",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        pivot.columns = [
            str(c) if isinstance(c, int) else c
            for c in pivot.columns
        ]
        yr_str_cols = [str(y) for y in all_years if str(y) in pivot.columns]
        pivot["Total (€)"] = pivot[yr_str_cols].sum(axis=1)
        pivot = pivot.rename(columns={
            "client_name":         "Client",
            "project_name":        "Project",
            "fee_description":     "Description",
            "billing_arrangement": "Arrangement",
        })
        yr_display = {str(y): f"{y} (€)" for y in all_years}
        pivot = pivot.rename(columns=yr_display)
        return pivot.sort_values("Total (€)", ascending=False)

    # ---- We-bill section --------------------------------------------
    if we_bill_rows:
        st.markdown("#### Amounts we will invoice")
        df_wb = _pivot(we_bill_rows, "fee_total")
        if df_wb is not None:
            num_cols_wb = [f"{y} (€)" for y in all_years if f"{y} (€)" in df_wb.columns]
            num_cols_wb.append("Total (€)")
            fmt_wb = {c: "{:,.0f}" for c in num_cols_wb}

            tot_wb = {c: df_wb[c].sum() if c in num_cols_wb
                      else ("TOTAL" if c == "Client" else "")
                      for c in df_wb.columns}
            dataframe_with_total(df_wb, tot_wb, fmt_wb)

    # ---- Third-party-bills section ----------------------------------
    if recv_rows:
        st.markdown("#### Amounts we expect to receive (our split)")
        df_rv = _pivot(recv_rows, "split_total")
        if df_rv is not None:
            num_cols_rv = [f"{y} (€)" for y in all_years if f"{y} (€)" in df_rv.columns]
            num_cols_rv.append("Total (€)")
            fmt_rv = {c: "{:,.0f}" for c in num_cols_rv}

            tot_rv = {c: df_rv[c].sum() if c in num_cols_rv
                      else ("TOTAL" if c == "Client" else "")
                      for c in df_rv.columns}
            dataframe_with_total(df_rv, tot_rv, fmt_rv)

    # ---- Combined total strip ---------------------------------------
    total_we_bill  = sum(r["fee_total"]   for r in we_bill_rows)
    total_recv     = sum(r["split_total"] for r in recv_rows)
    st.divider()
    ct1, ct2, ct3 = st.columns(3)
    ct1.metric(f"Total We Bill — {horizon}yr (€)",    f"€{total_we_bill:,.0f}")
    ct2.metric(f"Total We Receive — {horizon}yr (€)", f"€{total_recv:,.0f}")
    ct3.metric(f"Combined — {horizon}yr (€)",         f"€{total_we_bill + total_recv:,.0f}")
