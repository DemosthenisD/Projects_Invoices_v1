# InvoiceApp — Technical Reference

## Architecture Overview

```
frontend/
  App.py                    ← Streamlit entry point, login wall
  pages/
    0_generate_invoice.py   ← Invoice generation UI
    1_invoice_log.py        ← Invoice log + Excel export
    2_clients_projects.py   ← Client & project master data
    3_pipeline_crm.py       ← Pipeline / CRM
    4_dashboard.py          ← Financial dashboard
    5_project_codes.py      ← Billing codes management
    6_time_tracking.py      ← Time-charge import & rollup
    7_write_offs.py         ← Write-off management
    8_data_tables.py        ← Direct table viewer
    9_project_overview.py   ← Project-level financial overview

backend/
  db.py                     ← All SQLite access (CRUD functions)
  invoice_gen.py            ← DOCX template filling + PDF conversion

shared/
  config.py                 ← Paths, credentials (from .streamlit/secrets.toml)
  models.py                 ← Dataclass definitions (Client, Project, Invoice, …)

data/
  invoiceapp.db             ← SQLite database (single file)

templates/
  template1_v3.docx         ← Invoice template (Cyprus clients, 19% VAT)
  template2_v3.docx         ← Invoice template (Greece clients, 0% VAT)

exports/
  *.pdf / *.docx            ← Generated invoice files (permanent)

scripts/
  seed_from_csv.py          ← One-time import from NocoDb CSV exports
  seed_consultant_groups.py ← Pre-populate consultant_groups from ICEE Plan CY Excel
```

---

## Database

**Location:** `data/invoiceapp.db` relative to the repo root.

**Absolute path on this machine:**
`C:\Milliman Dropbox\Demosthenis Demosthenous\_Personal\GitProject\InvoiceApp\data\invoiceapp.db`

**How to open:** Download [DB Browser for SQLite](https://sqlitebrowser.org/dl/) — free, open-source Windows installer. It provides a spreadsheet-style viewer and editor with no SQL knowledge required. Open the `.db` file directly from File Explorer.

**How to back up:** Copy `data/invoiceapp.db` to any safe location. All app data lives in this single file.

---

## Tables

### `clients`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | TEXT UNIQUE | Display name |
| name_for_invoices | TEXT | Printed on invoices |
| client_code | TEXT | e.g. `0478EUR30` |
| vat_number | TEXT | Printed on invoices |
| created_at | TEXT | ISO datetime |

### `addresses`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| client_id | INTEGER FK→clients | Cascade delete |
| address | TEXT | Multi-line billing address |

Unique on `(client_id, address)`.

### `projects`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| client_id | INTEGER FK→clients | Cascade delete |
| name | TEXT | Project name |
| description | TEXT | Default invoice description |
| vat_pct | REAL | e.g. 19.0 or 0.0 |
| template | TEXT | Template filename (no .docx) |
| status | TEXT | Active / Completed / On Hold |

Unique on `(client_id, name)`.

### `invoices`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| client_id | INTEGER FK→clients | |
| project_id | INTEGER FK→projects | Nullable |
| invoice_number | TEXT | e.g. `42` |
| year | INTEGER | |
| date | TEXT | ISO date |
| amount | REAL | Net fee |
| vat_amount | REAL | |
| vat_pct | REAL | |
| address | TEXT | Snapshot at invoice time |
| project_name | TEXT | Snapshot |
| description | TEXT | Snapshot |
| template | TEXT | Template used |
| format | TEXT | PDF or DOCX |
| file_path | TEXT | Absolute path of generated file |
| expenses_net | REAL | |
| expenses_vat | REAL | |
| created_at | TEXT | |

### `pipeline`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| project_id | INTEGER FK→projects UNIQUE | One pipeline entry per project |
| stage | TEXT | Prospect / Proposal / Negotiation / Won / Lost |
| value | REAL | Contracted value |
| budget_min | REAL | For forecasting |
| budget_est | REAL | For forecasting |
| budget_max | REAL | For forecasting |
| probability | REAL | 0.0–1.0 |
| notes | TEXT | |
| updated_at | TEXT | |

### `project_codes`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| project_id | INTEGER FK→projects | Cascade delete |
| client_code | TEXT | e.g. `0478EUR30` |
| client_suffix | TEXT | e.g. `07` |
| name | TEXT | |
| description | TEXT | |
| budget_amount | REAL | Per-suffix budget |
| status | TEXT | Active / Completed |

Unique on `(client_code, client_suffix)`. Together these form the billing code used in time reports.

### `time_entries`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| project_code_id | INTEGER FK→project_codes | SET NULL on delete |
| project_id | INTEGER FK→projects | Cascade delete |
| period | TEXT | e.g. `2024-11` |
| emp_nbr | TEXT | Employee number from time report |
| consultant | TEXT | Full name |
| client_code | TEXT | |
| client_suffix | TEXT | |
| total_hours | REAL | |
| non_z_hours | REAL | Billable hours |
| z_hours | REAL | Internal/non-billable |
| total_charges | REAL | |
| non_z_charges | REAL | Billable charges (£/€) |
| z_charges | REAL | Internal charges |
| description | TEXT | |
| batch_ref | TEXT | Import batch identifier |

Unique on `(period, emp_nbr, client_code, client_suffix)`.

### `write_offs`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| project_id | INTEGER FK→projects | Cascade delete |
| project_code_id | INTEGER FK→project_codes | Nullable |
| emp_nbr | TEXT | Blank for project-level |
| consultant | TEXT | |
| amount | REAL | Write-off amount |
| reason | TEXT | |
| notes | TEXT | |
| allocation_type | TEXT | `project` or `adhoc` |
| reversed | INTEGER | 0 or 1 |
| reversed_reason | TEXT | |
| reversed_at | TEXT | |

### `consultant_groups`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| emp_nbr | TEXT | Nullable until first time entry seen |
| consultant | TEXT NOT NULL | Name as in time reports |
| group_name | TEXT | `Local` / `ICEE` / `Other` |

---

## File Locations

| Location | Contents |
|----------|---------|
| `data/invoiceapp.db` | All app data |
| `templates/*.docx` | Invoice Word templates |
| `exports/` | Generated invoice files (PDF/DOCX) |
| `scripts/` | Seed and utility scripts |

**Invoice file naming:** `YEAR_INVOICENO_CLIENTNAME_Invoice.pdf`

---

## Invoice Templates

Templates use `{{placeholderN}}` tokens:

| Token | Content |
|-------|---------|
| `{{placeholder1}}` | Client name (for invoices) |
| `{{placeholder2}}` | Billing address |
| `{{placeholder3}}` | Client VAT number |
| `{{placeholder4}}` | Invoice date (dd/mm/yyyy) |
| `{{placeholder5}}` | Invoice number |
| `{{placeholder6}}` | Year |
| `{{placeholder7}}` | Description |
| `{{placeholder8}}` | Net fee |
| `{{placeholder9}}` | VAT fee |
| `{{placeholder8_Exp}}` | Expenses net |
| `{{placeholder9_Exp}}` | Expenses VAT |
| `{{placeholder8_Tot}}` | Total net (fee + expenses) |
| `{{placeholder9_Tot}}` | Total VAT |
| `{{placeholder10}}` | Invoice total (gross) |

Template 1 (`template1_v3`) is used for Cyprus clients (19% VAT).
Template 2 (`template2_v3`) is used for Greece clients (0% VAT).

---

## PDF Conversion

The app tries two methods in order:

1. **docx2pdf** — drives Microsoft Word via COM (Windows only, requires Word installed).
2. **LibreOffice headless** — uses `soffice.exe --headless --convert-to pdf` (cross-platform fallback).

If neither is available, DOCX is still saved. Select DOCX format in the Advanced section to bypass conversion entirely.

---

## Configuration

Settings are read from `.streamlit/secrets.toml` (not committed to git):

```toml
LOGIN_USER = "your_username"
LOGIN_PASSWORD = "your_password"
DB_PATH = "data/invoiceapp.db"       # relative to repo root
TEMPLATES_DIR = "templates"
EXPORTS_DIR = "exports"
```

---

## Running the App

```bash
cd frontend
streamlit run App.py
```

Or from repo root:
```bash
streamlit run frontend/App.py
```

---

## Seeding Data

**From NocoDb CSV exports:**
```bash
python scripts/seed_from_csv.py           # live run
python scripts/seed_from_csv.py --dry-run # preview only
```

**Consultant groups from ICEE Plan CY Excel:**
```bash
python scripts/seed_consultant_groups.py
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

All 29+ tests cover DB CRUD, bulk import, write-off allocation, and time summaries.
