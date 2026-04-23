# InvoiceApp — Architecture & Development Plan

## Overview

A personal invoice management and generation tool built with Streamlit (Python) and SQLite. Designed for a solo operator who needs reliable invoice generation, client/project tracking, a pipeline view, and revenue dashboards — with Excel export for ad-hoc analysis.

---

## Why This Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| UI framework | Streamlit | Familiar, Python-native, rapid iteration |
| Database | SQLite | Zero infrastructure, single `.db` file, ACID-compliant, no race conditions |
| Excel | Export-on-demand | Maintains compatibility for ad-hoc pivots without using Excel as a live DB |
| PDF generation | ConvertAPI | Existing integration, reliable DOCX→PDF |
| Document templates | python-docx | Placeholder substitution in `.docx` templates |

SQLite was chosen over NocoDB (previous attempt) because NocoDB requires a running server, adds network overhead, and its strengths (REST API, multi-user) are not needed for a solo local app.

---

## Directory Structure

```
InvoiceApp/
├── frontend/
│   ├── App.py                          # Login entry point
│   └── pages/
│       ├── 0_generate_invoice.py       # Invoice generation + project-code allocation
│       ├── 1_how_to_use.py             # Quick-reference guide
│       ├── 2_invoice_log.py            # Invoice log with filters & search
│       ├── 3_clients_projects.py       # CRUD: clients, projects, addresses
│       ├── 4_pipeline_crm.py           # Pipeline / CRM view
│       ├── 5_dashboard.py             # Revenue & billing charts
│       ├── 6_project_codes.py          # Billing codes (suffix + date ranges)
│       ├── 7_time_tracking.py          # Time-charge import & rollup
│       ├── 8_write_offs.py             # Write-off management
│       ├── 9_data_tables.py            # Direct table viewer
│       ├── 10_project_overview.py      # Project-level financial overview
│       └── 11_add_new_project.py       # Flat intake: client + project + codes
├── backend/
│   ├── db.py                           # SQLite connection + all CRUD queries
│   ├── invoice_gen.py                  # DOCX/PDF generation logic
│   └── excel_io.py                     # Import from Excel, export to Excel
├── shared/
│   ├── config.py                       # Loads secrets from .streamlit/secrets.toml
│   └── models.py                       # Dataclasses: Client, Address, Project, Invoice,
│                                       #   InvoiceAllocation, ProjectCode, TimeEntry, WriteOff
├── templates/                          # .docx invoice templates
├── data/                               # invoiceapp.db (SQLite, single file)
├── exports/                            # Generated invoice files (DOCX/PDF)
├── scripts/                            # Seed utilities (CSV import, consultant groups)
├── docs/                               # USER_MANUAL.md, TECHNICAL.md, RELEASE_NOTES.md
├── requirements.txt
└── .streamlit/
    ├── config.toml                     # Streamlit theme
    └── secrets.toml                    # Credentials & API keys (gitignored)
```

---

## SQLite Schema (current)

See `docs/TECHNICAL.md` for the full column-level reference. Key tables:

| Table | Purpose | Unique constraint |
|---|---|---|
| `clients` | Client master data | `name` |
| `addresses` | Billing addresses (multi per client) | `(client_id, address)` |
| `projects` | Engagements linked to a client | `(client_id, name)` |
| `invoices` | Invoice log; `template_used` records which template was actually used | — |
| `invoice_allocations` | Splits invoice net amount across project codes (auto pro-rata if not set) | `(invoice_id, project_code_id)` |
| `pipeline` | CRM stage + budget + probability per project | `project_id` |
| `project_codes` | Billing sub-lines per project; same suffix can be reused across projects via `date_start` | `(client_code, client_suffix, date_start)` |
| `time_entries` | Monthly time-charge rows; routed to a project code by period date + suffix | `(period, emp_nbr, client_code, client_suffix)` |
| `write_offs` | Write-offs at project or code/consultant level | — |
| `consultant_groups` | Group assignment (Local / ICEE / Other) per consultant | — |

---

## Key Modules

### `backend/db.py`
- `get_connection()` — returns SQLite connection with row_factory
- `init_db()` — creates all tables on first run
- CRUD functions per entity: `get_clients()`, `add_client()`, `get_projects(client_id)`, `add_invoice()`, etc.

### `backend/invoice_gen.py`
- `fill_placeholders(doc, data: dict)` — replaces `{{FIELD}}` in DOCX paragraphs & tables
- `generate_invoice(data: dict, fmt: str) -> str` — writes filled DOCX to `exports/`, returns path
- `convert_to_pdf(docx_path: str) -> str` — calls ConvertAPI, returns PDF path

### `backend/excel_io.py`
- `import_from_excel(path: str)` — one-time migration: reads `InvoiceLogTemplate_DD_28062024.xlsx` sheets (Project_List, Client_List, InvoiceLogTemplate) and populates SQLite
- `export_to_excel(path: str)` — writes all SQLite tables to multi-sheet `.xlsx`

### `shared/models.py`
- `@dataclass Client`, `Address`, `Project`, `Invoice` — typed data containers used across frontend and backend

### `shared/config.py`
- `get_secret(key)` — reads from `st.secrets` (Streamlit) or `.env` fallback
- Exposes: `CONVERT_API_KEY`, `LOGIN_USER`, `LOGIN_PASSWORD`

---

## Page Summaries

| Page | Purpose |
|------|---------|
| `App.py` | Login with session state. Redirects to invoice generation on success. |
| `0_generate_invoice.py` | Select client → auto-fill address/VAT. Select project → auto-fill description/template. Enter amount/date → auto-suggest invoice number. Optional allocation to project codes (pro-rata fallback). Generate DOCX/PDF. Save to DB. |
| `1_how_to_use.py` | Quick-reference guide: page summaries (Actions vs Views), edit map, DB Browser tip. |
| `2_invoice_log.py` | Filterable table of all invoices (date range, client, project). Download file per row. Export visible data to Excel. |
| `3_clients_projects.py` | Tabbed CRUD for Clients, Projects, Addresses. Duplicate detection. Edit/delete with confirmation. |
| `4_pipeline_crm.py` | Project table with inline stage editing (Prospect / Active / On Hold / Completed). Filter by stage/client. Summary by stage. |
| `5_dashboard.py` | Monthly revenue bar chart. Revenue by client. VAT summary (net + VAT + gross). YTD vs prior year. |
| `6_project_codes.py` | Billing codes (suffix) per project. client_code derived automatically. Date Start/End support suffix reuse across projects. Per-code budget/billable/remaining metrics. |
| `7_time_tracking.py` | CSV import of monthly time-charge reports. Date-range aware routing to project codes. Rollup by code and consultant group. |
| `8_write_offs.py` | Project-level (pro-rata) or ad-hoc write-offs. Reversal log. |
| `9_data_tables.py` | Read-only view of all DB tables. Open in DB Browser for SQLite. |
| `10_project_overview.py` | Full project-level financial summary. Filter by client/status/source. Export to Excel. |
| `11_add_new_project.py` | Flat intake form: select/create client, fill project details, add N project code rows, single import button. |

---

## Sprint Plan

### Sprint 1 — Foundation (DB + Data Layer)
- `backend/db.py` — SQLite setup + CRUD
- `shared/models.py` — dataclasses
- `shared/config.py` — secrets loader
- `backend/excel_io.py` — Excel import/export
- Initial data import from existing Excel

### Sprint 2 — Invoice Generation
- `frontend/App.py` — login
- `backend/invoice_gen.py` — DOCX/PDF logic
- `frontend/pages/0_generate_invoice.py` — main generation form

### Sprint 3 — Data Management
- `frontend/pages/1_invoice_log.py` — filterable log
- `frontend/pages/2_clients_projects.py` — CRUD

### Sprint 4 — Pipeline / CRM
- `frontend/pages/3_pipeline_crm.py`

### Sprint 5 — Dashboard
- `frontend/pages/4_dashboard.py`

### Sprint 6 — Polish
- Loading spinners, toast messages, Excel export buttons
- Trim requirements.txt
- Basic tests for `db.py` and `invoice_gen.py`

---

## Running the App

```bash
cd frontend
streamlit run App.py
```

## One-time Data Migration

```bash
cd backend
python excel_io.py  # imports from Updated_Invoice_v2/InvoiceLogTemplate_DD_28062024.xlsx
```

## Key Files (legacy reference)
- Original app: `Updated_Invoice_v2/pages/0_generate_invoice_DD.py`
- Original data: `Updated_Invoice_v2/InvoiceLogTemplate_DD_28062024.xlsx`
- Original templates: `Updated_Invoice_v2/template*.docx`
