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
        def _gross(inv):
            return inv.amount + inv.expenses_net + inv.vat_amount + inv.expenses_vat

        total_net   = sum(i.amount for i in filtered)
        total_vat   = sum(i.vat_amount for i in filtered)
        # Outstanding = gross minus any payments already received, for unpaid/partial rows
        outstanding = sum(
            _gross(i) - i.total_paid
            for i in filtered
            if i.status in ("outstanding", "partial")
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invoices", len(filtered))
        c2.metric("Net (€)", f"{total_net:,.2f}")
        c3.metric("Gross (€)", f"{total_net + total_vat:,.2f}")
        c4.metric("Outstanding (€)", f"{outstanding:,.2f}")

        st.divider()

        # ---- Sort controls ----
        sort_c1, sort_c2 = st.columns([3, 2])
        sort_by  = sort_c1.selectbox(
            "Sort by",
            ["Date", "Invoice ID", "Amount", "Client", "Status", "Type"],
            index=0, label_visibility="collapsed",
        )
        sort_dir = sort_c2.radio("Order", ["↓ Desc", "↑ Asc"], horizontal=True, index=0,
                                  label_visibility="collapsed")
        asc = sort_dir == "↑ Asc"

        _sort_key = {
            "Date":       lambda i: i.date,
            "Invoice ID": lambda i: int(i.invoice_number) if i.invoice_number.isdigit() else 0,
            "Amount":     lambda i: i.amount,
            "Client":     lambda i: client_map.get(i.client_id, ""),
            "Status":     lambda i: i.status,
            "Type":       lambda i: i.type,
        }
        filtered = sorted(filtered, key=_sort_key[sort_by], reverse=not asc)

        # ---- Table with per-row actions ----
        if not filtered:
            st.info("No invoices match the selected filters.")
        else:
            STATUS_BADGE = {"outstanding": "🔴", "paid": "🟢", "partial": "🟡"}
            TYPE_BADGE   = {"Invoice": "📄", "Credit Note": "🔄"}

            st.caption(
                "**✓ Pay** = record full payment · **± Part.** = record partial payment · "
                "**↩ Reset** = clear all payments · 🔄 = Credit Note"
            )

            _cols = [1.0, 0.6, 1.0, 0.7, 1.5, 1.8, 0.9, 0.9, 0.8, 1.0, 1.0, 1.2]
            hdr = st.columns(_cols)
            for label, col in zip(
                ["Date", "ID", "Inv No", "Type", "Client", "Project",
                 "Net €", "VAT €", "Status", "Balance €", "File", "Action"],
                hdr,
            ):
                col.markdown(f"**{label}**")

            def _fmt_date(d: str) -> str:
                try:
                    from datetime import datetime
                    return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    return str(d)

            st.session_state.setdefault("_pay_form", None)

            for inv in filtered:
                (col_date, col_id, col_ref, col_type, col_client, col_proj,
                 col_net, col_vat, col_st, col_bal, col_dl, col_act) = st.columns(_cols)

                inv_ref = f"{inv.invoice_number}/{inv.year}"
                gross   = _gross(inv)
                balance = gross - inv.total_paid

                t_badge = TYPE_BADGE.get(getattr(inv, "type", "Invoice"), "📄")
                col_date.write(_fmt_date(inv.date))
                col_id.write(f"**{inv.invoice_number}**")
                col_ref.write(f"**{inv_ref}**")
                col_type.write(t_badge)
                col_client.write(client_map.get(inv.client_id, "—"))
                col_proj.write(inv.project_name or "—")
                col_net.write(f"€{inv.amount:,.0f}")
                col_vat.write(f"€{inv.vat_amount:,.0f}")
                badge = STATUS_BADGE.get(inv.status, "")
                col_st.write(f"{badge} {inv.status}")

                # Balance: show remaining for unpaid/partial; "—" for fully paid
                if inv.status == "paid" and inv.total_paid == 0:
                    col_bal.write("—")   # legacy paid record with no payment rows
                elif inv.status == "paid":
                    col_bal.write("€0")
                else:
                    col_bal.write(f"€{balance:,.0f}")

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

                # Action buttons
                if inv.status == "paid":
                    if col_act.button("↩ Reset", key=f"reset_{inv.id}",
                                      help="Clear payments and mark outstanding"):
                        db.delete_payments(inv.id)
                        st.cache_data.clear()
                        st.rerun()
                else:
                    a1, a2 = col_act.columns(2)
                    remaining = max(balance, 0.0)
                    if a1.button("✓", key=f"pay_{inv.id}", type="primary",
                                 help="Record full payment"):
                        db.add_payment(inv.id, remaining, date.today().isoformat())
                        st.session_state["_pay_form"] = None
                        st.cache_data.clear()
                        st.rerun()
                    if a2.button("±", key=f"part_{inv.id}",
                                 help="Record partial payment"):
                        st.session_state["_pay_form"] = (
                            None if st.session_state["_pay_form"] == inv.id else inv.id
                        )
                        st.rerun()

                # Notes + payment history below the row
                if inv.comment:
                    st.caption(f"💬 {inv.comment}")
                related = getattr(inv, "related_invoice_number", "")
                if related:
                    st.caption(f"↩ Credits invoice {related}")

                # Payment history
                payments = db.get_payments(inv.id)
                if payments:
                    for p in payments:
                        st.caption(
                            f"💰 {_fmt_date(p.date)}: €{p.amount:,.2f}"
                            + (f" — {p.note}" if p.note else "")
                        )

                # Inline partial payment form
                if st.session_state.get("_pay_form") == inv.id:
                    with st.form(key=f"pform_{inv.id}", clear_on_submit=True):
                        fc1, fc2, fc3 = st.columns([2, 2, 3])
                        p_amt  = fc1.number_input("Amount (€)", min_value=0.01,
                                                   max_value=float(max(balance, 0.01)),
                                                   value=float(min(balance, max(balance, 0.01))),
                                                   step=100.0)
                        p_date = fc2.date_input("Date", value=date.today())
                        p_note = fc3.text_input("Note (optional)")
                        if st.form_submit_button("Save payment"):
                            db.add_payment(inv.id, p_amt, p_date.isoformat(), p_note)
                            st.session_state["_pay_form"] = None
                            st.cache_data.clear()
                            st.rerun()

            st.divider()

            # ---- Export to Excel ----
            def _build_excel(rows) -> bytes:
                data = [
                    {
                        "Year":                 i.year,
                        "Type":                 getattr(i, "type", "Invoice"),
                        "Invoice ID":           i.invoice_number,
                        "Invoice No":           f"{i.invoice_number}/{i.year}",
                        "Related Invoice No":   getattr(i, "related_invoice_number", ""),
                        "Date":                 i.date,
                        "Client":               client_map.get(i.client_id, ""),
                        "Project":              i.project_name,
                        "Description":          i.description,
                        "Address":              i.address,
                        "Net (€)":              i.amount,
                        "VAT %":                i.vat_pct,
                        "VAT (€)":              i.vat_amount,
                        "Gross (€)":            round(_gross(i), 2),
                        "Expenses Net":         i.expenses_net,
                        "Expenses VAT":         i.expenses_vat,
                        "Paid (€)":             i.total_paid,
                        "Balance (€)":          round(_gross(i) - i.total_paid, 2)
                                                if i.status != "paid" or i.total_paid > 0
                                                else 0.0,
                        "Status":               i.status,
                        "Paid Date":            i.paid_date,
                        "Comment":              i.comment,
                        "Format":               i.format,
                        "File":                 i.file_path,
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
        from openpyxl.worksheet.datavalidation import DataValidation
        from openpyxl.workbook.defined_name import DefinedName

        client_list = db.get_clients(exclude_types=["internal"])

        # Build per-client project map and flat project rows
        client_projects: dict[int, list] = {}
        proj_rows = []
        for c in client_list:
            projs = db.get_projects(client_id=c.id)
            client_projects[c.id] = projs
            for p in projs:
                proj_rows.append({
                    "project_id": p.id, "project_name": p.name,
                    "client_id": c.id, "client_name": c.name,
                    "vat_pct": p.vat_pct, "template_used": p.template,
                    "description": p.description or "",
                    "project_status": p.status,
                    "_key": f"{p.name}|{c.id}",
                })

        addr_rows = []
        for c in client_list:
            for a in db.get_addresses(c.id):
                addr_rows.append({"client_id": c.id, "client_name": c.name,
                                  "address": a.address})

        # ---- Styles ----
        GOLD      = PatternFill("solid", fgColor="FFD966")   # required user fill
        GREEN     = PatternFill("solid", fgColor="E2EFDA")   # optional user fill
        FILL_AUTO = PatternFill("solid", fgColor="DDEEFF")   # formula-driven
        FILL_EX   = PatternFill("solid", fgColor="F2F2F2")   # example row
        DARK      = PatternFill("solid", fgColor="404040")
        BOLD_W    = Font(bold=True, color="FFFFFF")
        BOLD_BLK  = Font(bold=True)
        HINT      = Font(italic=True, color="888888", size=8)
        AUTO_FNT  = Font(color="0070C0", italic=True, size=9)
        DATE_FMT  = "DD/MM/YYYY"

        NUM_DATA_ROWS = 100
        DATA_START    = 4   # bumped to 5 after legend row

        # ---- Column layout ----
        # USER cols A–I: fill these (gold=required, green=optional)
        # AUTO cols J–U: formula-driven, do not edit (blue)
        USER_COLS = [
            # (header, fill, hint)
            ("▶ Client Name",          GOLD,  "Select from dropdown"),
            ("▶ Project Name",         GOLD,  "Select from dropdown — filtered by client"),
            ("invoice_number",         GOLD,  "Required — sequential ID, e.g. 12"),
            ("date",                   GOLD,  "Required — enter as DD/MM/YYYY"),
            ("amount",                 GOLD,  "Required — net fee excluding VAT (positive; negative for credit notes)"),
            ("status",                 GOLD,  "outstanding / paid / partial"),
            ("type",                   GOLD,  "Invoice or Credit Note"),
            ("paid_date",              GREEN, "DD/MM/YYYY or leave blank"),
            ("description",            GREEN, "Invoice description — leave blank to use project default"),
            ("comment",                GREEN, "Internal note — not shown on invoice"),
            ("related_invoice_number", GREEN, "Credit Notes only: original Invoice No, e.g. 12/2026"),
        ]
        AUTO_COLS = [
            # (header, hint)
            ("year",          "auto: year from date"),
            ("client_id",     "auto: from Client Reference"),
            ("project_id",    "auto: from Project Reference"),
            ("vat_pct",       "auto: from Project Reference"),
            ("vat_amount",    "auto: amount x vat_pct / 100"),
            ("project_name",  "auto: from Project Name"),
            ("template_used", "auto: from Project Reference"),
            ("address",       "auto: first address for client"),
            ("format",        "auto: PDF"),
            ("expenses_net",  "auto: 0"),
            ("expenses_vat",  "auto: 0"),
            ("file_path",     "auto: blank"),
        ]
        N_USER     = len(USER_COLS)   # 9
        N_AUTO     = len(AUTO_COLS)   # 12
        TOTAL_COLS = N_USER + N_AUTO  # 21

        wb = Workbook()

        # ==== Hidden helper: one column per client listing their project names ====
        wh = wb.create_sheet("_ProjectsHelper")
        wh.sheet_state = "hidden"
        for ci, c in enumerate(client_list, 1):
            wh.cell(1, ci, c.name)
            projs_for_client = client_projects.get(c.id, [])
            for ri, p in enumerate(projs_for_client, 2):
                wh.cell(ri, ci, p.name)
            end_row = max(2, len(projs_for_client) + 1)
            col_ltr = get_column_letter(ci)
            ref = f"'_ProjectsHelper'!${col_ltr}$2:${col_ltr}${end_row}"
            rn = f"Proj_{c.id}"
            wb.defined_names[rn] = DefinedName(name=rn, attr_text=ref)
        wb.defined_names["Proj_none"] = DefinedName(
            name="Proj_none", attr_text="'_ProjectsHelper'!$A$1:$A$1")

        # ==== Sheet 1 — Invoices ====
        ws = wb.active
        ws.title = "Invoices"
        ws.freeze_panes = f"A{DATA_START}"

        # Row 1 — headers
        for ci, (hdr, fill, _) in enumerate(USER_COLS, 1):
            c = ws.cell(1, ci, hdr)
            c.fill = fill; c.font = BOLD_BLK
            c.alignment = Alignment(horizontal="center", wrap_text=True)
        for ci, (hdr, _) in enumerate(AUTO_COLS, N_USER + 1):
            c = ws.cell(1, ci, hdr)
            c.fill = FILL_AUTO; c.font = Font(bold=True, color="0070C0")
            c.alignment = Alignment(horizontal="center", wrap_text=True)

        # Row 2 — hints
        for ci, (_, _, hint) in enumerate(USER_COLS, 1):
            ws.cell(2, ci, hint).font = HINT
        for ci, (_, hint) in enumerate(AUTO_COLS, N_USER + 1):
            ws.cell(2, ci, hint).font = HINT

        # Row 3 — example (skipped on import)
        ex_client = client_list[0] if client_list else None
        ex_proj   = (client_projects.get(ex_client.id) or [None])[0] if ex_client else None
        ex_addr   = next((a["address"] for a in addr_rows
                          if ex_client and a["client_id"] == ex_client.id), "")
        from datetime import date as _today
        ex_vals = {
            "▶ Client Name":          ex_client.name if ex_client else "",
            "▶ Project Name":         ex_proj.name if ex_proj else "",
            "invoice_number":         "EXAMPLE-001",
            "date":                   "31/01/2025",
            "amount":                 10000.0,
            "status":                 "outstanding",
            "type":                   "Invoice",
            "paid_date":              "",
            "description":            ex_proj.description if ex_proj else "",
            "comment":                "",
            "related_invoice_number": "",
            "year":                   2025,
            "client_id":              ex_client.id if ex_client else "",
            "project_id":             ex_proj.id if ex_proj else "",
            "vat_pct":                ex_proj.vat_pct if ex_proj else 19.0,
            "vat_amount":             1900.0,
            "project_name":           ex_proj.name if ex_proj else "",
            "template_used":          ex_proj.template if ex_proj else "template1_v4",
            "address":                ex_addr,
            "format":                 "PDF", "expenses_net": 0, "expenses_vat": 0, "file_path": "",
        }
        all_hdrs = [h for h, _, _ in USER_COLS] + [h for h, _ in AUTO_COLS]
        for ci, hdr in enumerate(all_hdrs, 1):
            c = ws.cell(3, ci, ex_vals.get(hdr, ""))
            c.fill = FILL_EX

        # Row 4 — legend (spans all cols, data starts row 5)
        ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=TOTAL_COLS)
        ws.cell(4, 1,
            "🟡 Required   🟢 Optional   🔵 Auto-calculated — do not edit   "
            "Dates: DD/MM/YYYY format   Row 3 is an example and is skipped on import."
        ).font = Font(italic=True, size=9, color="444444")

        DATA_START = 5  # first real data row

        # ---- Data validations ----
        # USER_COLS layout (A-K, 11 cols):
        # A=Client, B=Project, C=invoice_number, D=date, E=amount, F=status,
        # G=type, H=paid_date, I=description, J=comment, K=related_invoice_number
        # AUTO_COLS start at L=12:
        # L=year, M=client_id, N=project_id, O=vat_pct, P=vat_amount,
        # Q=project_name, R=template_used, S=address, T=format,
        # U=expenses_net, V=expenses_vat, W=file_path
        n_clients = len(client_list)
        # Client dropdown (col A)
        client_dv = DataValidation(
            type="list",
            formula1=f"='Client Reference'!$B$2:$B${n_clients + 1}",
            allow_blank=True, showDropDown=False,
        )
        ws.add_data_validation(client_dv)
        client_dv.sqref = f"A{DATA_START}:A{DATA_START + NUM_DATA_ROWS - 1}"

        # Project dropdown (col B) — CONCATENATE used instead of & to avoid XML escaping issues
        proj_dv = DataValidation(
            type="list",
            formula1=(
                "=INDIRECT(CONCATENATE(\"Proj_\","
                f"IFERROR(INDEX('Client Reference'!$A:$A,"
                f"MATCH(A{DATA_START},'Client Reference'!$B:$B,0)),\"none\")))"
            ),
            allow_blank=True, showDropDown=False,
        )
        ws.add_data_validation(proj_dv)
        proj_dv.sqref = f"B{DATA_START}:B{DATA_START + NUM_DATA_ROWS - 1}"

        # Status dropdown (col F)
        status_dv = DataValidation(
            type="list", formula1='"outstanding,paid,partial"',
            allow_blank=True, showDropDown=False,
        )
        ws.add_data_validation(status_dv)
        status_dv.sqref = f"F{DATA_START}:F{DATA_START + NUM_DATA_ROWS - 1}"

        # Type dropdown (col G)
        type_dv = DataValidation(
            type="list", formula1='"Invoice,Credit Note"',
            allow_blank=True, showDropDown=False,
        )
        ws.add_data_validation(type_dv)
        type_dv.sqref = f"G{DATA_START}:G{DATA_START + NUM_DATA_ROWS - 1}"

        # ---- Format date columns as DD/MM/YYYY ----
        date_col   = 4   # col D = date
        pdate_col  = 8   # col H = paid_date (shifted by 2 due to type col at G)
        for r in range(DATA_START, DATA_START + NUM_DATA_ROWS):
            ws.cell(r, date_col).number_format  = DATE_FMT
            ws.cell(r, pdate_col).number_format = DATE_FMT

        # ---- Pre-fill AUTO formula rows ----
        PR = "'Project Reference'"
        CR = "'Client Reference'"
        AR = "'Address Reference'"

        for row in range(DATA_START, DATA_START + NUM_DATA_ROWS):
            # AUTO cols start at L=12 (N_USER+1=12)
            # key_match uses B (project name) + M (client_id)
            key_match = f'CONCATENATE(B{row},"|",M{row})'
            auto_vals = [
                # L: year — YEAR() works natively on Excel date serial; fallback for text
                f'=IF(D{row}="","",IFERROR(YEAR(D{row}),IFERROR(YEAR(DATEVALUE(D{row})),"")))' ,
                # M: client_id
                f'=IFERROR(INDEX({CR}!$A:$A,MATCH(A{row},{CR}!$B:$B,0)),"")',
                # N: project_id
                f'=IFERROR(INDEX({PR}!$A:$A,MATCH({key_match},{PR}!$I:$I,0)),"")',
                # O: vat_pct
                f'=IFERROR(INDEX({PR}!$E:$E,MATCH({key_match},{PR}!$I:$I,0)),"")',
                # P: vat_amount
                f'=IF(OR(E{row}="",O{row}=""),"",ROUND(E{row}*O{row}/100,2))',
                # Q: project_name
                f'=IF(B{row}="","",B{row})',
                # R: template_used
                f'=IFERROR(INDEX({PR}!$F:$F,MATCH({key_match},{PR}!$I:$I,0)),"")',
                # S: address
                f'=IFERROR(INDEX({AR}!$C:$C,MATCH(M{row},{AR}!$A:$A,0)),"")',
                # T: format
                "PDF",
                # U: expenses_net
                0,
                # V: expenses_vat
                0,
                # W: file_path
                "",
            ]
            for ci_offset, val in enumerate(auto_vals):
                cell = ws.cell(row, N_USER + 1 + ci_offset, val)
                cell.fill = FILL_AUTO
                cell.font = AUTO_FNT

        # Column widths — 11 user + 12 auto
        user_widths = [28, 32, 16, 14, 12, 14, 14, 14, 36, 28, 22]
        auto_widths = [6,  10,  10,  7,  10,  26,  18,  40, 7, 8, 8, 8]
        for i, w in enumerate(user_widths + auto_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[1].height = 30
        ws.row_dimensions[2].height = 32

        def _ref_hdr(sheet, headers):
            for i, h in enumerate(headers, 1):
                cell = sheet.cell(1, i, h)
                cell.fill = DARK; cell.font = BOLD_W
                cell.alignment = Alignment(horizontal="center")

        # ==== Sheet 2 — Client Reference ====
        wc = wb.create_sheet("Client Reference")
        _ref_hdr(wc, ["client_id", "client_name", "client_code", "vat_number", "country"])
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
                  "vat_pct", "template_used", "description", "project_status", "_key"]
        _ref_hdr(wp, p_hdrs)
        for ri, p in enumerate(proj_rows, 2):
            for ci, k in enumerate(p_hdrs, 1):
                wp.cell(ri, ci, p[k])
        for i, w in enumerate([10, 32, 10, 26, 7, 18, 40, 14, 0], 1):
            wp.column_dimensions[get_column_letter(i)].width = max(w, 4)
        wp.column_dimensions["I"].width = 0
        wp.freeze_panes = "A2"

        # ==== Sheet 4 — Address Reference ====
        wa = wb.create_sheet("Address Reference")
        _ref_hdr(wa, ["client_id", "client_name", "address"])
        for ri, a in enumerate(addr_rows, 2):
            wa.cell(ri, 1, a["client_id"]); wa.cell(ri, 2, a["client_name"])
            wa.cell(ri, 3, a["address"])
        wa.column_dimensions["A"].width = 10
        wa.column_dimensions["B"].width = 30
        wa.column_dimensions["C"].width = 65
        wa.freeze_panes = "A2"

        # ==== Sheet 5 — Project Codes Reference ====
        all_codes = db.get_all_project_codes_with_context()
        wpc = wb.create_sheet("Project Codes Reference")
        pc_hdrs = ["code_id", "code_label", "project_id", "project_name",
                   "client_id", "client_name", "budget_amount"]
        _ref_hdr(wpc, pc_hdrs)
        for ri, cd in enumerate(all_codes, 2):
            label = f"{cd['client_code']}-{cd['client_suffix']}"
            if cd["code_name"]:
                label += f" | {cd['code_name']}"
            wpc.cell(ri, 1, cd["id"]);       wpc.cell(ri, 2, label)
            wpc.cell(ri, 3, cd["project_id"]); wpc.cell(ri, 4, cd["project_name"])
            wpc.cell(ri, 5, cd["client_id"]); wpc.cell(ri, 6, cd["client_name"])
            wpc.cell(ri, 7, cd["budget_amount"])
        for i, w in enumerate([10, 30, 10, 32, 10, 26, 14], 1):
            wpc.column_dimensions[get_column_letter(i)].width = w
        wpc.freeze_panes = "A2"

        n_codes = len(all_codes)
        code_range_ref = f"'Project Codes Reference'!$B$2:$B${max(n_codes + 1, 3)}"
        wb.defined_names["All_Codes"] = DefinedName(name="All_Codes", attr_text=code_range_ref)

        # ==== Sheet 6 — Allocations ====
        wal = wb.create_sheet("Allocations")
        AL_HDRS  = ["invoice_number",
                    "code_1","amount_1","code_2","amount_2",
                    "code_3","amount_3","code_4","amount_4",
                    "code_1_id","code_2_id","code_3_id","code_4_id"]
        AL_HINTS = ["Must match invoice_number in Invoices sheet",
                    "Select code","Net amount","Select code (optional)","Net amount",
                    "Select code (optional)","Net amount","Select code (optional)","Net amount",
                    "auto","auto","auto","auto"]
        for ci, h in enumerate(AL_HDRS, 1):
            cell = wal.cell(1, ci, h)
            is_auto = h.endswith("_id") and h.startswith("code_")
            cell.fill = FILL_AUTO if is_auto else (GREEN if "amount" in h else GOLD)
            cell.font = Font(bold=True, color="0070C0") if is_auto else BOLD_BLK
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        for ci, hint in enumerate(AL_HINTS, 1):
            wal.cell(2, ci, hint).font = HINT

        AL_DATA_START = 3
        AL_NUM_ROWS   = 100
        PCR = "'Project Codes Reference'"
        for code_col_idx in [2, 4, 6, 8]:
            code_dv = DataValidation(
                type="list", formula1="=All_Codes",
                allow_blank=True, showDropDown=False,
            )
            wal.add_data_validation(code_dv)
            col_ltr = get_column_letter(code_col_idx)
            code_dv.sqref = f"{col_ltr}{AL_DATA_START}:{col_ltr}{AL_DATA_START + AL_NUM_ROWS - 1}"

        for row in range(AL_DATA_START, AL_DATA_START + AL_NUM_ROWS):
            for code_col, id_col in [(2,10),(4,11),(6,12),(8,13)]:
                cl = get_column_letter(code_col)
                formula = f'=IFERROR(INDEX({PCR}!$A:$A,MATCH({cl}{row},{PCR}!$B:$B,0)),"")'
                cell = wal.cell(row, id_col, formula)
                cell.fill = FILL_AUTO; cell.font = AUTO_FNT

        al_widths = [20, 30, 12, 30, 12, 30, 12, 30, 12, 10, 10, 10, 10]
        for i, w in enumerate(al_widths, 1):
            wal.column_dimensions[get_column_letter(i)].width = w
        wal.row_dimensions[1].height = 30
        wal.row_dimensions[2].height = 28
        wal.freeze_panes = f"A{AL_DATA_START}"

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
        "**How to fill:** Select a client in column A → select the project in column B "
        "(dropdown filters automatically) → enter invoice number, date (DD/MM/YYYY), amount, status. "
        "All other columns (blue) auto-calculate. Dates in columns D and G must be in DD/MM/YYYY format."
    )

    st.divider()

    uploaded = st.file_uploader("Upload completed template (.xlsx)", type=["xlsx"])
    if uploaded:
        try:
            # Row 1=headers, 2=hints (skip), 3=example (filtered), 4=legend (filtered), 5+=data
            xl = pd.ExcelFile(uploaded)
            df = pd.read_excel(xl, sheet_name="Invoices", dtype=str, skiprows=[1, 2, 3])
            df = df.dropna(how="all")
            df = df[~df.get("invoice_number", pd.Series(dtype=str))
                      .str.upper().str.startswith("EXAMPLE", na=False)]
            df = df.rename(columns={"▶ Client Name": "_client_sel",
                                    "▶ Project Name": "_project_sel"})
            records = df.to_dict("records")

            # Optional Allocations sheet
            alloc_records: list[dict] = []
            if "Allocations" in xl.sheet_names:
                dfa = pd.read_excel(xl, sheet_name="Allocations", dtype=str, skiprows=[1])
                dfa = dfa.dropna(subset=["invoice_number"], how="any")
                dfa = dfa[dfa["invoice_number"].str.strip() != ""]
                alloc_records = dfa.to_dict("records")

            st.write(f"Found **{len(records)}** invoice row(s) and "
                     f"**{len(alloc_records)}** allocation row(s) in uploaded file.")

            if st.button("Import invoices", type="primary"):
                result = db.bulk_import_invoices(records)
                st.success(
                    f"Imported: {result['inserted']} | "
                    f"Skipped (duplicates): {result['skipped']}"
                )
                if result["errors"]:
                    st.error("Errors on some rows:")
                    for err in result["errors"]:
                        st.write(f"- {err}")

                # Process allocations
                if alloc_records:
                    alloc_ok = alloc_skip = 0
                    alloc_errs = []
                    for row in alloc_records:
                        inv_no = str(row.get("invoice_number", "")).strip()
                        if not inv_no:
                            continue
                        inv = db.get_invoice_by_number(inv_no)
                        if not inv:
                            alloc_errs.append(f"{inv_no}: invoice not found in DB")
                            continue
                        pairs = []
                        for i in range(1, 5):
                            code_id_raw = str(row.get(f"code_{i}_id", "")).strip()
                            amt_raw     = str(row.get(f"amount_{i}", "")).strip()
                            if code_id_raw and code_id_raw not in ("", "nan") \
                                    and amt_raw and amt_raw not in ("", "nan"):
                                try:
                                    pairs.append({
                                        "project_code_id": int(float(code_id_raw)),
                                        "amount": float(amt_raw),
                                    })
                                except ValueError:
                                    alloc_errs.append(
                                        f"{inv_no} code_{i}: bad value ({code_id_raw}, {amt_raw})"
                                    )
                        if pairs:
                            db.upsert_invoice_allocations(inv["id"], pairs)
                            alloc_ok += 1
                        else:
                            alloc_skip += 1
                    st.success(f"Allocations — applied: {alloc_ok} | skipped (empty): {alloc_skip}")
                    if alloc_errs:
                        st.error("Allocation errors:")
                        for err in alloc_errs:
                            st.write(f"- {err}")

                st.cache_data.clear()
        except Exception as exc:
            st.error(f"Could not read file: {exc}")
