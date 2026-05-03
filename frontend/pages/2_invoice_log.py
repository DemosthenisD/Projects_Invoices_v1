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
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment
        from openpyxl.utils import get_column_letter

        client_list = db.get_clients(exclude_types=["internal"])

        # Build project rows (all clients)
        proj_rows = []
        for c in client_list:
            for p in db.get_projects(client_id=c.id):
                proj_rows.append({
                    "project_id":     p.id,
                    "project_name":   p.name,
                    "client_id":      c.id,
                    "client_name":    c.name,
                    "vat_pct":        p.vat_pct,
                    "template_used":  p.template,
                    "description":    p.description,
                    "project_status": p.status,
                })

        # Build address rows
        addr_rows = []
        for c in client_list:
            for a in db.get_addresses(c.id):
                addr_rows.append({
                    "client_id":   c.id,
                    "client_name": c.name,
                    "address":     a.address,
                })

        # ---- Styles ----
        GOLD  = PatternFill("solid", fgColor="FFD966")   # required
        BLUE  = PatternFill("solid", fgColor="BDD7EE")   # look up from reference
        GREEN = PatternFill("solid", fgColor="E2EFDA")   # optional
        GREY  = PatternFill("solid", fgColor="F2F2F2")   # example row
        DARK  = PatternFill("solid", fgColor="404040")   # reference sheet headers
        BOLD_W   = Font(bold=True, color="FFFFFF")
        BOLD_BLK = Font(bold=True)
        HINT     = Font(italic=True, color="888888", size=8)

        # ---- Invoice sheet column definitions ----
        # (field_name, fill, hint)
        COLS = [
            ("client_id",      GOLD,  "Required — copy ID from Client Reference tab"),
            ("project_id",     BLUE,  "Copy from Project Reference tab (0 if none)"),
            ("invoice_number", GOLD,  "Required — unique per year, e.g. 2025-001"),
            ("year",           GOLD,  "Required — 4-digit year, e.g. 2025"),
            ("date",           GOLD,  "Required — YYYY-MM-DD"),
            ("amount",         GOLD,  "Required — net fee excluding VAT"),
            ("vat_amount",     GOLD,  "Required — amount × vat_pct ÷ 100"),
            ("vat_pct",        BLUE,  "Copy from Project Reference tab, e.g. 19"),
            ("address",        BLUE,  "Copy from Address Reference tab"),
            ("project_name",   BLUE,  "Copy from Project Reference tab"),
            ("description",    BLUE,  "Copy from Project Reference tab (editable)"),
            ("template_used",  BLUE,  "Copy from Project Reference tab"),
            ("format",         GREEN, "PDF or DOCX (default: PDF)"),
            ("expenses_net",   GREEN, "0 if no expenses"),
            ("expenses_vat",   GREEN, "0 if no expenses"),
            ("status",         GOLD,  "outstanding / paid / partial"),
            ("paid_date",      GREEN, "YYYY-MM-DD or leave blank"),
            ("file_path",      GREEN, "Leave blank for bulk upload"),
        ]

        # Build pre-filled example from first project/address in DB
        ex = {f: "" for f, _, _ in COLS}
        ex.update({"invoice_number": "EXAMPLE-001", "year": 2025,
                   "date": "2025-01-31", "amount": 10000.0, "vat_amount": 1900.0,
                   "format": "PDF", "expenses_net": 0, "expenses_vat": 0,
                   "status": "outstanding", "paid_date": "", "file_path": ""})
        if proj_rows:
            p0 = proj_rows[0]
            ex.update({"client_id": p0["client_id"], "project_id": p0["project_id"],
                       "vat_pct": p0["vat_pct"], "project_name": p0["project_name"],
                       "description": p0["description"] or "",
                       "template_used": p0["template_used"]})
        if addr_rows:
            ex["address"] = addr_rows[0]["address"]

        wb = Workbook()

        # ==== Sheet 1 — Invoices ====
        ws = wb.active
        ws.title = "Invoices"
        ws.freeze_panes = "A3"

        # Row 1 — colour-coded field headers
        for ci, (field, fill, _) in enumerate(COLS, 1):
            cell = ws.cell(row=1, column=ci, value=field)
            cell.fill = fill
            cell.font = BOLD_BLK
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        # Row 2 — hints (small italic, not imported)
        for ci, (_, _, hint) in enumerate(COLS, 1):
            cell = ws.cell(row=2, column=ci, value=hint)
            cell.font = HINT
            cell.alignment = Alignment(wrap_text=True)

        # Row 3 — pre-filled example (clearly labelled, filtered out on import)
        for ci, (field, _, _) in enumerate(COLS, 1):
            cell = ws.cell(row=3, column=ci, value=ex.get(field, ""))
            cell.fill = GREY

        # Column widths
        widths = [12, 12, 18, 8, 14, 12, 12, 8, 40, 28, 35, 18, 8, 12, 12, 14, 14, 20]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[1].height = 28
        ws.row_dimensions[2].height = 36

        # Legend caption in a merged cell below the hint row
        leg = ws.cell(row=4, column=1,
                      value="🟡 Required   🔵 Copy from reference tabs   🟢 Optional   "
                            "Row 3 is an example — delete or leave it (it is skipped on import).")
        leg.font = Font(italic=True, size=9, color="444444")
        ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=len(COLS))

        def _ref_header(sheet, headers):
            for i, h in enumerate(headers, 1):
                cell = sheet.cell(row=1, column=i, value=h)
                cell.fill = DARK
                cell.font = BOLD_W
                cell.alignment = Alignment(horizontal="center")

        # ==== Sheet 2 — Client Reference ====
        wc = wb.create_sheet("Client Reference")
        c_hdrs = ["client_id", "client_name", "client_code", "vat_number", "country"]
        _ref_header(wc, c_hdrs)
        for ri, c in enumerate(client_list, 2):
            wc.cell(ri, 1, c.id);   wc.cell(ri, 2, c.name)
            wc.cell(ri, 3, c.client_code); wc.cell(ri, 4, c.vat_number)
            wc.cell(ri, 5, c.country)
        for i, w in enumerate([10, 30, 15, 18, 15], 1):
            wc.column_dimensions[get_column_letter(i)].width = w
        wc.freeze_panes = "A2"

        # ==== Sheet 3 — Project Reference ====
        wp = wb.create_sheet("Project Reference")
        p_hdrs = ["project_id", "project_name", "client_id", "client_name",
                  "vat_pct", "template_used", "description", "project_status"]
        _ref_header(wp, p_hdrs)
        for ri, p in enumerate(proj_rows, 2):
            for ci, k in enumerate(p_hdrs, 1):
                wp.cell(ri, ci, p[k])
        for i, w in enumerate([12, 32, 10, 26, 8, 18, 42, 14], 1):
            wp.column_dimensions[get_column_letter(i)].width = w
        wp.freeze_panes = "A2"

        # ==== Sheet 4 — Address Reference ====
        wa = wb.create_sheet("Address Reference")
        _ref_header(wa, ["client_id", "client_name", "address"])
        for ri, a in enumerate(addr_rows, 2):
            wa.cell(ri, 1, a["client_id"]); wa.cell(ri, 2, a["client_name"])
            wa.cell(ri, 3, a["address"])
        wa.column_dimensions["A"].width = 10
        wa.column_dimensions["B"].width = 30
        wa.column_dimensions["C"].width = 60
        wa.freeze_panes = "A2"

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    st.download_button(
        label="Download template",
        data=_build_template(),
        file_name="invoice_upload_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.caption(
        "🟡 Gold columns = required · "
        "🔵 Blue columns = copy from reference tabs · "
        "🟢 Green columns = optional"
    )

    st.divider()

    uploaded = st.file_uploader("Upload completed template (.xlsx)", type=["xlsx"])
    if uploaded:
        try:
            # Row 1 = headers, row 2 = hints (skipped), row 3 = example (filtered below)
            df = pd.read_excel(uploaded, sheet_name="Invoices", dtype=str, skiprows=[1])
            df = df.dropna(how="all")
            # Drop the pre-filled example row
            df = df[~df["invoice_number"].str.upper().str.startswith("EXAMPLE", na=False)]
            records = df.to_dict("records")
            st.write(f"Found **{len(records)}** data row(s) in uploaded file.")

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
