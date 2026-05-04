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
        import re
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
                    "_key": f"{p.name}|{c.id}",  # lookup key (col I)
                })

        # Build address rows (first address per client used for auto-fill)
        addr_rows = []
        for c in client_list:
            for a in db.get_addresses(c.id):
                addr_rows.append({"client_id": c.id, "client_name": c.name,
                                  "address": a.address})

        # ---- Styles ----
        GOLD  = PatternFill("solid", fgColor="FFD966")  # user must fill
        GREEN = PatternFill("solid", fgColor="E2EFDA")  # user optional
        FILL_AUTO = PatternFill("solid", fgColor="DDEEFF")  # auto-computed
        FILL_EX   = PatternFill("solid", fgColor="F2F2F2")  # example row
        DARK  = PatternFill("solid", fgColor="404040")
        BOLD_W   = Font(bold=True, color="FFFFFF")
        BOLD_BLK = Font(bold=True)
        HINT     = Font(italic=True, color="888888", size=8)
        AUTO_FNT = Font(color="0070C0", italic=True, size=9)

        NUM_DATA_ROWS = 100   # rows pre-filled with formulas
        DATA_START    = 4     # row index where data begins (1=hdr, 2=hint, 3=ex)

        # ---- Column layout ----
        # USER columns (A–G): orange/green = fill these
        # AUTO columns (H–T): blue italic = formula-driven, do not edit
        USER_COLS = [
            # (header, fill, hint)
            ("▶ Client Name",    GOLD,  "Select from dropdown — drives all other fields"),
            ("▶ Project Name",   GOLD,  "Select from dropdown — filtered by client above"),
            ("invoice_number",   GOLD,  "Required — unique per year, e.g. 2025-001"),
            ("date",             GOLD,  "Required — YYYY-MM-DD"),
            ("amount",           GOLD,  "Required — net fee excluding VAT"),
            ("status",           GOLD,  "outstanding / paid / partial"),
            ("paid_date",        GREEN, "YYYY-MM-DD or leave blank"),
        ]
        AUTO_COLS = [
            # (header, hint)
            ("year",          "=YEAR(date)"),
            ("client_id",     "=MATCH(Client Name → Client Reference)"),
            ("project_id",    "=MATCH(Project Name + client_id → Project Reference)"),
            ("vat_pct",       "=from Project Reference"),
            ("vat_amount",    "=amount × vat_pct ÷ 100"),
            ("project_name",  "=Project Name"),
            ("description",   "=from Project Reference"),
            ("template_used", "=from Project Reference"),
            ("address",       "=first address for client"),
            ("format",        '="PDF"'),
            ("expenses_net",  "=0"),
            ("expenses_vat",  "=0"),
            ("file_path",     '=""'),
        ]
        TOTAL_COLS = len(USER_COLS) + len(AUTO_COLS)  # 20

        wb = Workbook()

        # ==== Hidden helper sheet: one column per client = their project names ====
        # Named ranges Proj_<client_id> point here → used by cascading dropdown
        wh = wb.create_sheet("_ProjectsHelper")
        wh.sheet_state = "hidden"
        for ci, c in enumerate(client_list, 1):
            wh.cell(1, ci, c.name)  # header (not used in named range)
            projs_for_client = client_projects.get(c.id, [])
            for ri, p in enumerate(projs_for_client, 2):
                wh.cell(ri, ci, p.name)
            # Create named range Proj_<id> → column of project names
            end_row = max(2, len(projs_for_client) + 1)
            col_ltr = get_column_letter(ci)
            ref = f"'_ProjectsHelper'!${col_ltr}$2:${col_ltr}${end_row}"
            rn = f"Proj_{c.id}"
            wb.defined_names[rn] = DefinedName(name=rn, attr_text=ref)
        # Fallback named range for when no client is selected
        wb.defined_names["Proj_none"] = DefinedName(
            name="Proj_none",
            attr_text=f"'_ProjectsHelper'!$A$1:$A$1"
        )

        # ==== Sheet 1 — Invoices ====
        ws = wb.active
        ws.title = "Invoices"
        ws.freeze_panes = f"A{DATA_START}"

        # Row 1 — headers
        for ci, (hdr, fill, _) in enumerate(USER_COLS, 1):
            c = ws.cell(1, ci, hdr)
            c.fill = fill; c.font = BOLD_BLK
            c.alignment = Alignment(horizontal="center", wrap_text=True)
        for ci, (hdr, _) in enumerate(AUTO_COLS, len(USER_COLS) + 1):
            c = ws.cell(1, ci, hdr)
            c.fill = FILL_AUTO; c.font = Font(bold=True, color="0070C0")
            c.alignment = Alignment(horizontal="center", wrap_text=True)

        # Row 2 — hints
        for ci, (_, _, hint) in enumerate(USER_COLS, 1):
            c = ws.cell(2, ci, hint); c.font = HINT
        for ci, (_, hint) in enumerate(AUTO_COLS, len(USER_COLS) + 1):
            c = ws.cell(2, ci, hint); c.font = HINT

        # Row 3 — example row (pre-filled, skipped on import)
        ex_client = client_list[0] if client_list else None
        ex_proj   = (client_projects.get(ex_client.id) or [None])[0] if ex_client else None
        ex_addr   = next((a["address"] for a in addr_rows
                          if ex_client and a["client_id"] == ex_client.id), "")
        ex_vals = {
            "▶ Client Name": ex_client.name if ex_client else "",
            "▶ Project Name": ex_proj.name if ex_proj else "",
            "invoice_number": "EXAMPLE-001",
            "date": "2025-01-31",
            "amount": 10000.0,
            "status": "outstanding",
            "paid_date": "",
            # auto cols
            "year": 2025,
            "client_id": ex_client.id if ex_client else "",
            "project_id": ex_proj.id if ex_proj else "",
            "vat_pct": ex_proj.vat_pct if ex_proj else 19.0,
            "vat_amount": 1900.0,
            "project_name": ex_proj.name if ex_proj else "",
            "description": ex_proj.description if ex_proj else "",
            "template_used": ex_proj.template if ex_proj else "template1_v3",
            "address": ex_addr,
            "format": "PDF", "expenses_net": 0, "expenses_vat": 0, "file_path": "",
        }
        all_hdrs = [h for h, _, _ in USER_COLS] + [h for h, _ in AUTO_COLS]
        for ci, hdr in enumerate(all_hdrs, 1):
            c = ws.cell(3, ci, ex_vals.get(hdr, ""))
            c.fill = FILL_EX

        # Legend row
        leg = ws.cell(DATA_START - 1 + 1, 1,   # reuse row 4 slot (DATA_START=4)
            "🟡 Fill these columns   🔵 Auto-calculated — do not edit   "
            "Row 3 is an example and is skipped on import.")
        # Actually DATA_START=4 means row 4 is the first data row; insert legend at row 4?
        # No — shift: rows 1=hdr, 2=hint, 3=example, 4=legend, 5+ = data
        # Let's put the legend at row 4 and data starts at 5
        ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=TOTAL_COLS)
        ws.cell(4, 1,
            "🟡 Fill columns A–G   🔵 Columns H–T are auto-calculated — do not edit   "
            "Row 3 is a pre-filled example and is skipped on import."
        ).font = Font(italic=True, size=9, color="444444")

        DATA_START = 5  # actual first data row

        # ---- Data validation ----
        # Client dropdown (column A) — list from Client Reference
        n_clients = len(client_list)
        client_dv = DataValidation(
            type="list",
            formula1=f"='Client Reference'!$B$2:$B${n_clients + 1}",
            allow_blank=True, showDropDown=False,
        )
        ws.add_data_validation(client_dv)
        client_dv.sqref = f"A{DATA_START}:A{DATA_START + NUM_DATA_ROWS - 1}"

        # Project dropdown (column B) — cascading via INDIRECT + named range Proj_<client_id>
        proj_dv = DataValidation(
            type="list",
            formula1=(
                f'=INDIRECT("Proj_"&IFERROR('
                f"INDEX('Client Reference'!$A:$A,"
                f"MATCH(A{DATA_START},'Client Reference'!$B:$B,0))"
                f',"none"))'
            ),
            allow_blank=True, showDropDown=False,
        )
        ws.add_data_validation(proj_dv)
        proj_dv.sqref = f"B{DATA_START}:B{DATA_START + NUM_DATA_ROWS - 1}"

        # Status dropdown (column F)
        status_dv = DataValidation(
            type="list", formula1='"outstanding,paid,partial"',
            allow_blank=True, showDropDown=False,
        )
        ws.add_data_validation(status_dv)
        status_dv.sqref = f"F{DATA_START}:F{DATA_START + NUM_DATA_ROWS - 1}"

        # ---- Pre-fill formula rows ----
        for row in range(DATA_START, DATA_START + NUM_DATA_ROWS):
            A, B, E, H, I, J, K = (
                f"A{row}", f"B{row}", f"E{row}",
                f"H{row}", f"I{row}", f"J{row}", f"K{row}",
            )
            PR = "'Project Reference'"
            CR = "'Client Reference'"
            AR = "'Address Reference'"

            formulas = [
                # H: year
                f'=IF({A}="","",IFERROR(YEAR(DATEVALUE({A[0]}4)),IFERROR(INT(LEFT(D{row},4)),"")))',
                # H: year (correct reference)
                None,  # placeholder, will set below
                # I: client_id
                f'=IFERROR(INDEX({CR}!$A:$A,MATCH({A},{CR}!$B:$B,0)),"")',
                # J: project_id
                f'=IFERROR(INDEX({PR}!$A:$A,MATCH({B}&"|"&{I},{PR}!$I:$I,0)),"")',
                # K: vat_pct
                f'=IFERROR(INDEX({PR}!$E:$E,MATCH({B}&"|"&{I},{PR}!$I:$I,0)),"")',
                # L: vat_amount
                f'=IF(OR({E}="",{K}=""),"",ROUND({E}*{K}/100,2))',
                # M: project_name
                f'=IF({B}="","",{B})',
                # N: description
                f'=IFERROR(INDEX({PR}!$G:$G,MATCH({B}&"|"&{I},{PR}!$I:$I,0)),"")',
                # O: template_used
                f'=IFERROR(INDEX({PR}!$F:$F,MATCH({B}&"|"&{I},{PR}!$I:$I,0)),"")',
                # P: address
                f'=IFERROR(INDEX({AR}!$C:$C,MATCH({I},{AR}!$A:$A,0)),"")',
                # Q: format
                "PDF",
                # R: expenses_net
                0,
                # S: expenses_vat
                0,
                # T: file_path
                "",
            ]
            # H: year — correct formula
            year_f = (f'=IF(D{row}="","",IFERROR(YEAR(DATEVALUE(D{row})),'
                      f'IFERROR(INT(LEFT(D{row},4)),"")))')
            ci_id  = f'=IFERROR(INDEX({CR}!$A:$A,MATCH(A{row},{CR}!$B:$B,0)),"")'
            ci_pid = f'=IFERROR(INDEX({PR}!$A:$A,MATCH(B{row}&"|"&I{row},{PR}!$I:$I,0)),"")'
            ci_vat = f'=IFERROR(INDEX({PR}!$E:$E,MATCH(B{row}&"|"&I{row},{PR}!$I:$I,0)),"")'
            ci_vam = f'=IF(OR(E{row}="",K{row}=""),"",ROUND(E{row}*K{row}/100,2))'
            ci_pnm = f'=IF(B{row}="","",B{row})'
            ci_dsc = f'=IFERROR(INDEX({PR}!$G:$G,MATCH(B{row}&"|"&I{row},{PR}!$I:$I,0)),"")'
            ci_tpl = f'=IFERROR(INDEX({PR}!$F:$F,MATCH(B{row}&"|"&I{row},{PR}!$I:$I,0)),"")'
            ci_adr = f'=IFERROR(INDEX({AR}!$C:$C,MATCH(I{row},{AR}!$A:$A,0)),"")'

            auto_vals = [year_f, ci_id, ci_pid, ci_vat, ci_vam,
                         ci_pnm, ci_dsc, ci_tpl, ci_adr,
                         "PDF", 0, 0, ""]
            for ci_offset, val in enumerate(auto_vals):
                col = len(USER_COLS) + 1 + ci_offset
                cell = ws.cell(row, col, val)
                cell.fill = FILL_AUTO
                cell.font = AUTO_FNT

        # Column widths
        user_widths = [28, 32, 18, 14, 12, 14, 14]
        auto_widths = [6, 10, 10, 7, 10, 26, 32, 18, 40, 7, 10, 10, 10]
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

        # ==== Sheet 3 — Project Reference (with lookup key in col I) ====
        wp = wb.create_sheet("Project Reference")
        p_hdrs = ["project_id", "project_name", "client_id", "client_name",
                  "vat_pct", "template_used", "description", "project_status", "_key"]
        _ref_hdr(wp, p_hdrs)
        for ri, p in enumerate(proj_rows, 2):
            for ci, k in enumerate(p_hdrs, 1):
                wp.cell(ri, ci, p[k])
        for i, w in enumerate([10, 32, 10, 26, 7, 18, 40, 14, 0], 1):
            wp.column_dimensions[get_column_letter(i)].width = max(w, 4)
        wp.column_dimensions["I"].width = 0  # hide key column
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
            wpc.cell(ri, 1, cd["id"])
            wpc.cell(ri, 2, label)
            wpc.cell(ri, 3, cd["project_id"])
            wpc.cell(ri, 4, cd["project_name"])
            wpc.cell(ri, 5, cd["client_id"])
            wpc.cell(ri, 6, cd["client_name"])
            wpc.cell(ri, 7, cd["budget_amount"])
        for i, w in enumerate([10, 30, 10, 32, 10, 26, 14], 1):
            wpc.column_dimensions[get_column_letter(i)].width = w
        wpc.freeze_panes = "A2"

        # Named range for code dropdown
        n_codes = len(all_codes)
        code_range_ref = f"'Project Codes Reference'!$B$2:$B${max(n_codes + 1, 3)}"
        wb.defined_names["All_Codes"] = DefinedName(name="All_Codes", attr_text=code_range_ref)

        # ==== Sheet 6 — Allocations (optional) ====
        # One row per invoice_number; up to 4 (code, amount) pairs.
        # Columns: invoice_number | code_1 | amount_1 | code_2 | amount_2 |
        #          code_3 | amount_3 | code_4 | amount_4 |
        #          [hidden] code_1_id | code_2_id | code_3_id | code_4_id
        wal = wb.create_sheet("Allocations")
        AL_HDRS = [
            "invoice_number",
            "code_1", "amount_1",
            "code_2", "amount_2",
            "code_3", "amount_3",
            "code_4", "amount_4",
            "code_1_id", "code_2_id", "code_3_id", "code_4_id",
        ]
        AL_HINTS = [
            "Must match invoice_number in Invoices sheet",
            "Select code from dropdown", "Net amount for this code",
            "Select code from dropdown (optional)", "Net amount for this code",
            "Select code from dropdown (optional)", "Net amount for this code",
            "Select code from dropdown (optional)", "Net amount for this code",
            "auto", "auto", "auto", "auto",
        ]
        for ci, h in enumerate(AL_HDRS, 1):
            cell = wal.cell(1, ci, h)
            is_auto = h.startswith("code_") and h.endswith("_id")
            cell.fill = FILL_AUTO if is_auto else (GOLD if "amount" not in h else GREEN)
            cell.font = Font(bold=True, color="0070C0") if is_auto else BOLD_BLK
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        for ci, hint in enumerate(AL_HINTS, 1):
            wal.cell(2, ci, hint).font = HINT

        AL_DATA_START = 3
        AL_NUM_ROWS   = 100
        PCR = "'Project Codes Reference'"

        # Code dropdowns for columns B, D, F, H
        for code_col_idx in [2, 4, 6, 8]:
            code_dv = DataValidation(
                type="list", formula1="=All_Codes",
                allow_blank=True, showDropDown=False,
            )
            wal.add_data_validation(code_dv)
            col_ltr = get_column_letter(code_col_idx)
            code_dv.sqref = (f"{col_ltr}{AL_DATA_START}:"
                             f"{col_ltr}{AL_DATA_START + AL_NUM_ROWS - 1}")

        # Formula rows: code_id = INDEX(code_id col, MATCH(code_label, label col))
        for row in range(AL_DATA_START, AL_DATA_START + AL_NUM_ROWS):
            for pair_idx, (code_col, id_col) in enumerate(
                [(2, 10), (4, 11), (6, 12), (8, 13)], 1
            ):
                code_ltr = get_column_letter(code_col)
                id_ltr   = get_column_letter(id_col)
                formula  = (f'=IFERROR(INDEX({PCR}!$A:$A,'
                            f'MATCH({code_ltr}{row},{PCR}!$B:$B,0)),"")')
                cell = wal.cell(row, id_col, formula)
                cell.fill = FILL_AUTO; cell.font = AUTO_FNT

        # Widths
        al_widths = [20, 30, 12, 30, 12, 30, 12, 30, 12, 10, 10, 10, 10]
        for i, w in enumerate(al_widths, 1):
            wal.column_dimensions[get_column_letter(i)].width = w
        wal.row_dimensions[1].height = 30
        wal.row_dimensions[2].height = 28
        wal.freeze_panes = f"A{AL_DATA_START}"
        wal.sheet_state = "visible"

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
        "(dropdown filters automatically) → enter invoice number, date, amount, status. "
        "All other columns (blue) auto-calculate."
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
