"""
Page 1 — Invoice Log.

Features:
  - Filter by year, client, project, status, free-text search
  - Status badges + Mark as Paid / Outstanding inline
  - Per-row file download (DOCX or PDF)
  - Export visible rows to Excel
  - Bulk upload via downloadable Excel template
"""
import sys
import os
import io
from datetime import date

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

tab_log, tab_upload = st.tabs(["Log", "Bulk Upload"])

# ------------------------------------------------------------------
# Load data (shared between tabs)
# ------------------------------------------------------------------

@st.cache_data(ttl=60)
def _load_invoices():
    return db.get_invoices()

@st.cache_data(ttl=300)
def _load_clients():
    return db.get_clients()

invoices = _load_invoices()
clients  = _load_clients()
client_map = {c.id: c.name for c in clients}

# ==================================================================
# TAB 1 — LOG
# ==================================================================

with tab_log:
    if not invoices:
        st.info("No invoices recorded yet.")
    else:
        # ---- Filter controls ----
        all_years = sorted({i.year for i in invoices}, reverse=True)
        STATUSES = ["All", "outstanding", "paid", "partial"]

        col1, col2, col3, col4, col5 = st.columns([1, 2, 2, 1, 2])

        with col1:
            year_filter = st.selectbox("Year", ["All"] + [str(y) for y in all_years])

        after_year = invoices if year_filter == "All" else [i for i in invoices if i.year == int(year_filter)]
        clients_in_year = sorted({client_map.get(i.client_id, "") for i in after_year})

        with col2:
            client_filter = st.selectbox("Client", ["All"] + clients_in_year)

        after_client = after_year if client_filter == "All" else [
            i for i in after_year if client_map.get(i.client_id, "") == client_filter
        ]
        projects_in_client = sorted({i.project_name for i in after_client if i.project_name})

        with col3:
            project_filter = st.selectbox("Project", ["All"] + projects_in_client)
        with col4:
            status_filter = st.selectbox("Status", STATUSES)
        with col5:
            search = st.text_input("Search (invoice # or project)", placeholder="Type to search…")

        # ---- Apply filters ----
        filtered = invoices
        if year_filter != "All":
            filtered = [i for i in filtered if i.year == int(year_filter)]
        if client_filter != "All":
            filtered = [i for i in filtered if client_map.get(i.client_id, "") == client_filter]
        if project_filter != "All":
            filtered = [i for i in filtered if i.project_name == project_filter]
        if status_filter != "All":
            filtered = [i for i in filtered if i.status == status_filter]
        if search:
            q = search.lower()
            filtered = [
                i for i in filtered
                if q in i.invoice_number.lower() or q in i.project_name.lower()
            ]

        # ---- Summary strip ----
        total_net   = sum(i.amount for i in filtered)
        total_vat   = sum(i.vat_amount for i in filtered)
        outstanding = sum(i.amount + i.vat_amount for i in filtered if i.status == "outstanding")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invoices", len(filtered))
        c2.metric("Net (€)", f"{total_net:,.2f}")
        c3.metric("Gross (€)", f"{total_net + total_vat:,.2f}")
        c4.metric("Outstanding (€)", f"{outstanding:,.2f}")

        st.divider()

        # ---- Table with per-row actions ----
        if not filtered:
            st.info("No invoices match the selected filters.")
        else:
            STATUS_BADGE = {"outstanding": "🔴", "paid": "🟢", "partial": "🟡"}

            st.caption(
                "PDF/DOCX buttons download the generated file from your local disk. "
                "Use **Mark Paid** / **Mark Outstanding** to update payment status."
            )

            _cols = [1.2, 1, 1.8, 2, 1, 1, 0.8, 1.2, 1]
            hdr = st.columns(_cols)
            for label, col in zip(
                ["Date", "Invoice #", "Client", "Project", "Net €", "VAT €", "Status", "File", "Action"],
                hdr,
            ):
                col.markdown(f"**{label}**")

            for inv in filtered:
                (col_date, col_num, col_client, col_proj,
                 col_net, col_vat, col_st, col_dl, col_act) = st.columns(_cols)

                col_date.write(inv.date)
                col_num.write(f"**#{inv.invoice_number}**")
                col_client.write(client_map.get(inv.client_id, "—"))
                col_proj.write(inv.project_name or "—")
                col_net.write(f"€{inv.amount:,.0f}")
                col_vat.write(f"€{inv.vat_amount:,.0f}")
                badge = STATUS_BADGE.get(inv.status, "")
                col_st.write(f"{badge} {inv.status}")

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

                if inv.status == "outstanding":
                    if col_act.button("Mark Paid", key=f"paid_{inv.id}", type="primary"):
                        db.update_invoice_status(inv.id, "paid", date.today().isoformat())
                        st.cache_data.clear()
                        st.rerun()
                else:
                    if col_act.button("Outstanding", key=f"unpaid_{inv.id}"):
                        db.update_invoice_status(inv.id, "outstanding", "")
                        st.cache_data.clear()
                        st.rerun()

            st.divider()

            # ---- Export to Excel ----
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
                        "Status":        i.status,
                        "Paid Date":     i.paid_date,
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

# ==================================================================
# TAB 2 — BULK UPLOAD
# ==================================================================

with tab_upload:
    st.subheader("Bulk Invoice Upload")
    st.write(
        "Download the template, fill in your invoices, then upload the completed file. "
        "Existing invoices (matched by Invoice No + Year) are skipped."
    )

    # ---- Build template ----
    def _build_template() -> bytes:
        client_list = db.get_clients(exclude_types=["internal"])
        client_ref = "\n".join(f"{c.id} — {c.name}" for c in client_list)

        template_cols = {
            "client_id": "int (see Reference sheet)",
            "project_id": "int or 0",
            "invoice_number": "e.g. 2024-001",
            "year": "e.g. 2024",
            "date": "YYYY-MM-DD",
            "amount": "net amount",
            "vat_amount": "",
            "vat_pct": "e.g. 19",
            "address": "",
            "project_name": "",
            "description": "",
            "template_used": "",
            "format": "PDF or DOCX",
            "file_path": "",
            "expenses_net": "0",
            "expenses_vat": "0",
            "status": "outstanding / paid / partial",
            "paid_date": "YYYY-MM-DD or blank",
        }

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            pd.DataFrame([{k: v for k, v in template_cols.items()}]).to_excel(
                writer, sheet_name="Invoices", index=False
            )
            pd.DataFrame(
                [{"client_id": c.id, "client_name": c.name, "client_code": c.client_code}
                 for c in client_list]
            ).to_excel(writer, sheet_name="Client Reference", index=False)
        return buf.getvalue()

    st.download_button(
        label="Download blank template",
        data=_build_template(),
        file_name="invoice_upload_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()

    uploaded = st.file_uploader("Upload completed template (.xlsx)", type=["xlsx"])
    if uploaded:
        try:
            df = pd.read_excel(uploaded, sheet_name="Invoices", dtype=str)
            df = df.dropna(how="all")
            records = df.to_dict("records")
            st.write(f"Found **{len(records)}** row(s) in uploaded file.")

            if st.button("Import invoices", type="primary"):
                result = db.bulk_import_invoices(records)
                st.success(f"Imported: {result['inserted']} | Skipped (duplicates): {result['skipped']}")
                if result["errors"]:
                    st.error("Errors on some rows:")
                    for err in result["errors"]:
                        st.write(f"- {err}")
                st.cache_data.clear()
        except Exception as exc:
            st.error(f"Could not read file: {exc}")
