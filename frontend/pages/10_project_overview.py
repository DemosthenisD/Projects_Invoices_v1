"""
Page 8 — Project Overview.

Full project-level financial summary across all clients with multi-select filters,
year-by-year breakdown, and Excel export.
"""
import sys
import os
import io
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import backend.db as db
from shared.ui import dataframe_with_total, require_auth

require_auth()

st.title("Project Overview")

# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load():
    return db.get_all_projects_overview()

rows = _load()

if not rows:
    st.info("No projects found.")
    st.stop()

df = pd.DataFrame(rows)
cy = date.today().year
years: list[int] = [cy - i for i in range(4)]

# ------------------------------------------------------------------
# Filters — row 1: Client, Status, Source
# ------------------------------------------------------------------

all_clients  = sorted(df["client"].unique())
all_statuses = sorted(df["status"].unique())
all_sources  = sorted(df["project_source"].unique())
all_types    = sorted(df["client_type"].unique())
all_groups   = sorted({g for cell in df["groups_with_hours"] for g in cell.split(",") if g})
all_consults = sorted({c for cell in df["consultants_with_hours"] for c in cell.split(",") if c})

col1, col2, col3 = st.columns(3)
with col1:
    client_sel = st.multiselect("Client", all_clients)
with col2:
    status_sel = st.multiselect("Status", all_statuses, default=["Active"])
with col3:
    source_sel = st.multiselect("Milliman Office", all_sources)

col4, col5, col6 = st.columns(3)
with col4:
    type_sel = st.multiselect("Client Type", all_types)
with col5:
    group_sel = st.multiselect("Consultant Team", all_groups)
with col6:
    consult_sel = st.multiselect("Consultant", all_consults)

filtered = df.copy()
if client_sel:
    filtered = filtered[filtered["client"].isin(client_sel)]
if status_sel:
    filtered = filtered[filtered["status"].isin(status_sel)]
if source_sel:
    filtered = filtered[filtered["project_source"].isin(source_sel)]
if type_sel:
    filtered = filtered[filtered["client_type"].isin(type_sel)]
if group_sel:
    filtered = filtered[filtered["groups_with_hours"].apply(
        lambda v: any(g in v.split(",") for g in group_sel)
    )]
if consult_sel:
    filtered = filtered[filtered["consultants_with_hours"].apply(
        lambda v: any(c in v.split(",") for c in consult_sel)
    )]

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Projects",     len(filtered))
c2.metric("Budget (€)",   f"{filtered['budget'].sum():,.0f}")
c3.metric("Billable (€)", f"{filtered['billable_charges'].sum():,.0f}")
c4.metric("Invoiced (€)", f"{filtered['invoiced'].sum():,.0f}")

st.divider()

# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

_MONEY_FMT = "{:,.0f}"
_MONEY2_FMT = "{:,.2f}"

def _style_money(df_in: pd.DataFrame, cols: list[str], dec: int = 0) -> "pd.io.formats.style.Styler":
    fmt = _MONEY_FMT if dec == 0 else _MONEY2_FMT
    return df_in.style.format({c: fmt for c in cols if c in df_in.columns}, na_rep="—")

def _totals_row(display: pd.DataFrame, label_col: str, label: str, num_cols: list[str]) -> pd.DataFrame:
    row = {c: display[c].sum() if c in num_cols else ("" if c != label_col else label)
           for c in display.columns}
    return pd.concat([display, pd.DataFrame([row])], ignore_index=True)

# ------------------------------------------------------------------
# View toggle
# ------------------------------------------------------------------

view = st.radio("View", ["Summary", "Year-by-Year"], horizontal=True, label_visibility="collapsed")

_NUM_COLS = ["Budget (€)", "Billable (€)", "Write-offs (€)", "Net (€)", "Invoiced (€)", "Remaining (€)"]

if view == "Summary":
    display = filtered[[
        "client", "project", "project_source", "client_type", "code_count",
        "budget", "billable_charges", "write_offs", "net_charges", "invoiced", "remaining", "status",
    ]].rename(columns={
        "client":           "Client",
        "project":          "Project",
        "project_source":   "Office",
        "client_type":      "Type",
        "code_count":       "Codes",
        "budget":           "Budget (€)",
        "billable_charges": "Billable (€)",
        "write_offs":       "Write-offs (€)",
        "net_charges":      "Net (€)",
        "invoiced":         "Invoiced (€)",
        "remaining":        "Remaining (€)",
        "status":           "Status",
    })

    _num_fmt = {c: "{:,.0f}" for c in _NUM_COLS}
    _tot = {c: display[c].sum() if c in _NUM_COLS else ("TOTAL" if c == "Client" else "")
            for c in display.columns}
    dataframe_with_total(display, _tot, _num_fmt)

else:
    if f"invoiced_{years[0]}" not in filtered.columns:
        st.warning(
            "Year-by-year columns not available — restart the Streamlit server and revisit this page."
        )
        st.stop()

    base_cols   = ["client", "project", "status"]
    base_rename = {"client": "Client", "project": "Project", "status": "Status"}

    for prefix, total_col, label in [
        ("invoiced",  "invoiced",         "Invoiced (€)"),
        ("charges",   "billable_charges", "Time Charges (€)"),
        ("writeoffs", "write_offs",       "Write-offs (€)"),
    ]:
        yr_cols = {f"{prefix}_{yr}": str(yr) for yr in years}
        tbl = filtered[base_cols + [total_col] + list(yr_cols)].copy().rename(columns={
            **base_rename,
            total_col: f"Total",
            **yr_cols,
        })
        num_cols = ["Total"] + [str(yr) for yr in years]
        _tot = {c: tbl[c].sum() if c in num_cols else ("TOTAL" if c == "Client" else "")
                for c in tbl.columns}
        st.subheader(label)
        dataframe_with_total(tbl, _tot, {c: "{:,.0f}" for c in num_cols})
        st.divider()

# ------------------------------------------------------------------
# Export to Excel
# ------------------------------------------------------------------

def _build_excel(data: pd.DataFrame, yrs: list[int]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_cols = {
            "client": "Client", "project": "Project", "project_source": "Source",
            "client_type": "Type", "code_count": "Codes", "budget": "Budget (€)",
            "billable_charges": "Billable (€)", "write_offs": "Write-offs (€)",
            "net_charges": "Net (€)", "invoiced": "Invoiced (€)",
            "remaining": "Remaining (€)", "status": "Status",
        }
        data[list(summary_cols)].rename(columns=summary_cols).to_excel(
            writer, sheet_name="Summary", index=False
        )
        yby_cols = {"client": "Client", "project": "Project", "status": "Status"}
        for yr in yrs:
            yby_cols[f"invoiced_{yr}"]  = f"Invoiced {yr}"
            yby_cols[f"charges_{yr}"]   = f"Charges {yr}"
            yby_cols[f"writeoffs_{yr}"] = f"Write-offs {yr}"
        data[[c for c in yby_cols if c in data.columns]].rename(columns=yby_cols).to_excel(
            writer, sheet_name="Year-by-Year", index=False
        )
    return buf.getvalue()

st.download_button(
    label="Export to Excel",
    data=_build_excel(filtered, years),
    file_name="project_overview.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# ------------------------------------------------------------------
# Recurring Fees management
# ------------------------------------------------------------------

st.divider()
st.subheader("Recurring Fees")
st.caption(
    "Manage scheduled recurring billing obligations at project-code level. "
    "Select a project to view, add, or edit its recurring fees."
)

_FREQ_LABELS = {
    "monthly":    "Monthly",
    "quarterly":  "Quarterly",
    "semi-annual":"Semi-annual",
    "annual":     "Annual",
}
_BT_LABELS = {
    "we_bill":          "We invoice the client",
    "third_party_bills":"Third party invoices client — we receive our portion",
}

# Project selector — all non-internal projects from the full (unfiltered) dataset
non_internal_rows = [r for r in rows if r.get("client_type") != "internal"]
proj_labels = {
    r["project_id"]: f"{r['client']} — {r['project']}"
    for r in non_internal_rows
}
proj_labels = dict(sorted(proj_labels.items(), key=lambda x: x[1]))

rf_proj_id = st.selectbox(
    "Select project",
    options=[None] + list(proj_labels.keys()),
    format_func=lambda x: "— choose a project —" if x is None else proj_labels[x],
    key="rf_proj_sel",
)

if rf_proj_id is not None:
    codes = db.get_project_codes(project_id=rf_proj_id)
    fees  = db.get_recurring_fees_for_project(rf_proj_id, ensure_occurrences=True)

    # ---- Existing fees -----------------------------------------------
    if fees:
        for fee in fees:
            occ_all      = db.get_occurrences(fee["id"])
            occ_pending  = [o for o in occ_all if o["status"] == "pending"]
            occ_invoiced = [o for o in occ_all if o["status"] == "invoiced"]

            code_label  = f"{fee['client_code']}{fee['client_suffix']}"
            status_icon = "🟢" if fee["status"] == "Active" else "🔴"
            freq_label  = _FREQ_LABELS.get(fee["frequency"], fee["frequency"])
            exp_title   = (
                f"{status_icon} **{code_label}** — {fee['description']} "
                f"| {freq_label} | €{fee['fee_amount']:,.0f}"
            )

            with st.expander(exp_title, expanded=False):
                mi1, mi2, mi3, mi4 = st.columns(4)
                mi1.metric("Billing",        _BT_LABELS.get(fee["billing_type"], "")[:22])
                mi2.metric("Coverage start", fee["coverage_start"] or "—")
                mi3.metric("Expected end",   fee["expected_end"]   or "Open-ended")
                mi4.metric("Occurrences",    f"{len(occ_invoiced)} invoiced · {len(occ_pending)} pending")

                if fee["split_amount"] > 0:
                    direction = "we owe" if fee["billing_type"] == "we_bill" else "we receive"
                    st.info(
                        f"**Split** — {fee['split_party'] or 'Other party'}: "
                        f"€{fee['split_amount']:,.2f} per occurrence ({direction})"
                    )

                # Next occurrences preview
                if occ_pending:
                    st.markdown("**Next occurrences:**")
                    next3 = occ_pending[:3]
                    df_occ = pd.DataFrame(next3)[["due_date", "amount", "split_amount", "status"]]
                    df_occ.columns = ["Due Date", "Amount (€)", "Split (€)", "Status"]
                    st.dataframe(
                        df_occ.style.format({"Amount (€)": "{:,.2f}", "Split (€)": "{:,.2f}"}),
                        use_container_width=True, hide_index=True,
                    )

                if fee["status"] == "Active":
                    tab_edit, tab_cancel = st.tabs(["Edit", "Cancel Fee"])

                    with tab_edit:
                        with st.form(key=f"edit_rf_{fee['id']}"):
                            ea1, ea2 = st.columns(2)
                            e_desc   = ea1.text_input("Description", value=fee["description"])
                            e_freq   = ea2.selectbox(
                                "Frequency", options=list(_FREQ_LABELS.keys()),
                                index=list(_FREQ_LABELS.keys()).index(fee["frequency"]),
                                format_func=lambda x: _FREQ_LABELS[x],
                            )
                            eb1, eb2, eb3 = st.columns(3)
                            e_amt    = eb1.number_input("Fee amount (€)", value=float(fee["fee_amount"]),
                                                        min_value=0.01, step=100.0)
                            e_ftype  = eb2.selectbox("Fee type", ["fixed", "indexed"],
                                                     index=0 if fee["fee_type"] == "fixed" else 1,
                                                     format_func=lambda x: "Fixed" if x == "fixed" else "Indexed")
                            e_irate  = eb3.number_input("Index rate %",
                                                        value=float(fee["index_rate"]) * 100,
                                                        min_value=0.0, max_value=20.0, step=0.1)
                            ec1, ec2 = st.columns(2)
                            e_start_raw = date.fromisoformat(fee["coverage_start"]) if fee["coverage_start"] else date.today()
                            e_start  = ec1.date_input("Coverage start", value=e_start_raw, key=f"es_{fee['id']}")
                            e_end_raw = date.fromisoformat(fee["expected_end"]) if fee["expected_end"] else None
                            e_end    = ec2.date_input("Expected end (blank = open-ended)",
                                                      value=e_end_raw, key=f"ee_{fee['id']}")
                            ed1, ed2, ed3 = st.columns(3)
                            e_bt     = ed1.selectbox("Billing type",
                                                     options=list(_BT_LABELS.keys()),
                                                     index=0 if fee["billing_type"] == "we_bill" else 1,
                                                     format_func=lambda x: _BT_LABELS[x])
                            e_sparty = ed2.text_input("Split party", value=fee["split_party"])
                            e_samt   = ed3.number_input("Split amount (€)", value=float(fee["split_amount"]),
                                                        min_value=0.0, step=100.0)
                            e_notes  = st.text_area("Notes", value=fee["notes"], height=80)

                            if st.form_submit_button("Save Changes", type="primary"):
                                db.update_recurring_fee(
                                    fee["id"], e_desc.strip(), e_amt,
                                    e_ftype, e_irate / 100 if e_ftype == "indexed" else 0.0,
                                    e_freq,
                                    e_start.isoformat(),
                                    e_end.isoformat() if e_end else "",
                                    e_bt, e_sparty, e_samt,
                                    fee["auto_invoice"], e_notes,
                                )
                                st.success("Recurring fee updated — future pending occurrences recalculated.")
                                st.cache_data.clear()
                                st.rerun()

                    with tab_cancel:
                        st.warning(
                            f"Cancelling will delete all **{len(occ_pending)} pending** occurrences. "
                            "Invoiced occurrences are preserved as a historical record."
                        )
                        if st.button("Confirm — Cancel This Fee", key=f"cancel_rf_{fee['id']}",
                                     type="primary"):
                            db.cancel_recurring_fee(fee["id"])
                            st.success("Recurring fee cancelled.")
                            st.cache_data.clear()
                            st.rerun()

    else:
        st.info("No recurring fees defined for this project yet.")

    # ---- Add new fee -------------------------------------------------
    st.markdown("---")
    with st.expander("➕ Add Recurring Fee", expanded=len(fees) == 0):
        if not codes:
            st.warning("No project codes found for this project — add codes first.")
        else:
            code_opts = {
                pc.id: f"{pc.client_code}{pc.client_suffix}"
                       + (f" — {pc.name}" if pc.name else "")
                for pc in codes
            }

            with st.form("add_rf_form"):
                fa1, fa2 = st.columns(2)
                new_code_id = fa1.selectbox(
                    "Project code*", options=list(code_opts.keys()),
                    format_func=lambda x: code_opts[x],
                )
                new_desc = fa2.text_input("Description*",
                                          placeholder="e.g. Annual platform support fee")

                fb1, fb2, fb3 = st.columns(3)
                new_amt   = fb1.number_input("Fee amount (€)*", min_value=0.01,
                                             step=100.0, value=1000.0)
                new_ftype = fb2.selectbox("Fee type", ["fixed", "indexed"],
                                          format_func=lambda x: "Fixed" if x == "fixed"
                                                                 else "Indexed (annual %)")
                new_irate = fb3.number_input("Index rate %", min_value=0.0, max_value=20.0,
                                             step=0.1, value=3.0)

                fc1, fc2, fc3 = st.columns(3)
                new_freq  = fc1.selectbox("Frequency", options=list(_FREQ_LABELS.keys()),
                                          format_func=lambda x: _FREQ_LABELS[x])
                new_start = fc2.date_input("Coverage start*", value=date.today())
                new_end   = fc3.date_input("Expected end (optional)", value=None)

                fd1, fd2, fd3 = st.columns(3)
                new_bt     = fd1.selectbox("Billing type", options=list(_BT_LABELS.keys()),
                                           format_func=lambda x: _BT_LABELS[x])
                new_sparty = fd2.text_input("Split party",
                                            placeholder="e.g. Global actuarial team")
                new_samt   = fd3.number_input(
                    "Split amount (€)",
                    min_value=0.0, step=100.0,
                    help="Amount we owe them (if we bill) or expect from them (if they bill)",
                )
                new_notes = st.text_area("Notes", height=80)

                if st.form_submit_button("Add Recurring Fee", type="primary"):
                    if not new_desc.strip():
                        st.error("Description is required.")
                    else:
                        db.add_recurring_fee(
                            project_code_id=new_code_id,
                            description=new_desc.strip(),
                            fee_amount=new_amt,
                            frequency=new_freq,
                            coverage_start=new_start.isoformat(),
                            billing_type=new_bt,
                            fee_type=new_ftype,
                            index_rate=new_irate / 100 if new_ftype == "indexed" else 0.0,
                            expected_end=new_end.isoformat() if new_end else "",
                            split_party=new_sparty,
                            split_amount=new_samt,
                            notes=new_notes,
                        )
                        st.success("Recurring fee added — occurrences generated.")
                        st.cache_data.clear()
                        st.rerun()
