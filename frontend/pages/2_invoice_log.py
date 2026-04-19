"""
Page 1 — Invoice Log.

Features:
  - Filter by year, client, project, free-text search
  - Per-row file download (DOCX or PDF)
  - Export visible rows to Excel
"""
import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd

import backend.db as db
from shared.config import EXPORTS_DIR

# ------------------------------------------------------------------
# Auth guard
# ------------------------------------------------------------------

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

# ------------------------------------------------------------------
# Page setup
# ------------------------------------------------------------------

st.title("Invoice Log")

# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load_invoices():
    return db.get_invoices()

@st.cache_data(ttl=300)
def _load_clients():
    return db.get_clients()

invoices = _load_invoices()
clients  = _load_clients()

if not invoices:
    st.info("No invoices recorded yet.")
    st.stop()

client_map = {c.id: c.name for c in clients}

# ------------------------------------------------------------------
# Filter controls
# ------------------------------------------------------------------

all_years = sorted({i.year for i in invoices}, reverse=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    year_filter = st.selectbox("Year", ["All"] + [str(y) for y in all_years])

# Cascade: after year, restrict client options
after_year = invoices if year_filter == "All" else [i for i in invoices if i.year == int(year_filter)]
clients_in_year = sorted({client_map.get(i.client_id, "") for i in after_year})

with col2:
    client_filter = st.selectbox("Client", ["All"] + clients_in_year)

# Cascade: after client, restrict project options
after_client = after_year if client_filter == "All" else [
    i for i in after_year if client_map.get(i.client_id, "") == client_filter
]
projects_in_client = sorted({i.project_name for i in after_client if i.project_name})

with col3:
    project_filter = st.selectbox("Project", ["All"] + projects_in_client)
with col4:
    search = st.text_input("Search (invoice # or project)", placeholder="Type to search…")

# ------------------------------------------------------------------
# Apply filters
# ------------------------------------------------------------------

filtered = invoices

if year_filter != "All":
    filtered = [i for i in filtered if i.year == int(year_filter)]
if client_filter != "All":
    filtered = [i for i in filtered if client_map.get(i.client_id, "") == client_filter]
if project_filter != "All":
    filtered = [i for i in filtered if i.project_name == project_filter]
if search:
    q = search.lower()
    filtered = [
        i for i in filtered
        if q in i.invoice_number.lower() or q in i.project_name.lower()
    ]

# ------------------------------------------------------------------
# Summary strip
# ------------------------------------------------------------------

total_net   = sum(i.amount for i in filtered)
total_vat   = sum(i.vat_amount for i in filtered)
total_gross = total_net + total_vat

c1, c2, c3, c4 = st.columns(4)
c1.metric("Invoices", len(filtered))
c2.metric("Net (€)", f"{total_net:,.2f}")
c3.metric("VAT (€)", f"{total_vat:,.2f}")
c4.metric("Gross (€)", f"{total_gross:,.2f}")

st.divider()

# ------------------------------------------------------------------
# Table with per-row download
# ------------------------------------------------------------------

if not filtered:
    st.info("No invoices match the selected filters.")
    st.stop()

st.caption(
    "PDF/DOCX buttons download the generated file from your local disk. "
    "If the file has been moved or deleted the button will not appear (shown as —)."
)

# Header row
_cols = [1.2, 1, 1.8, 2, 1, 1, 1, 1]
hdr = st.columns(_cols)
for label, col in zip(
    ["Date", "Invoice #", "Client", "Project", "Net €", "VAT €", "Expenses €", "File"],
    hdr,
):
    col.markdown(f"**{label}**")

for inv in filtered:
    col_date, col_num, col_client, col_proj, col_net, col_vat, col_exp, col_dl = st.columns(_cols)
    col_date.write(inv.date)
    col_num.write(f"**#{inv.invoice_number}**")
    col_client.write(client_map.get(inv.client_id, "—"))
    col_proj.write(inv.project_name or "—")
    col_net.write(f"€{inv.amount:,.0f}")
    col_vat.write(f"€{inv.vat_amount:,.0f}")
    col_exp.write(f"€{inv.expenses_net:,.0f}" if inv.expenses_net else "—")

    # Download button if file exists
    if inv.file_path and os.path.exists(inv.file_path):
        ext  = os.path.splitext(inv.file_path)[1].lower()
        mime = "application/pdf" if ext == ".pdf" else (
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with open(inv.file_path, "rb") as f:
            col_dl.download_button(
                label=ext.lstrip(".").upper(),
                data=f.read(),
                file_name=os.path.basename(inv.file_path),
                mime=mime,
                key=f"dl_{inv.id}",
            )
    else:
        col_dl.write("—")

st.divider()

# ------------------------------------------------------------------
# Export to Excel
# ------------------------------------------------------------------

def _build_excel(rows) -> bytes:
    data = [
        {
            "Year":          i.year,
            "Invoice No":    i.invoice_number,
            "Date":          i.date,
            "Client":        client_map.get(i.client_id, ""),
            "Project":       i.project_name,
            "Description":   i.description,
            "Address":       i.address,
            "Net (€)":       i.amount,
            "VAT %":         i.vat_pct,
            "VAT (€)":       i.vat_amount,
            "Gross (€)":     round(i.amount + i.vat_amount, 2),
            "Expenses Net":  i.expenses_net,
            "Expenses VAT":  i.expenses_vat,
            "Format":        i.format,
            "File":          i.file_path,
        }
        for i in rows
    ]
    buf = io.BytesIO()
    pd.DataFrame(data).to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()

st.download_button(
    label="Export to Excel",
    data=_build_excel(filtered),
    file_name="invoice_export.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
