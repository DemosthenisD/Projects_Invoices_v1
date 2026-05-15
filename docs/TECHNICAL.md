# InvoiceApp — Technical Reference

## Architecture Overview

```
frontend/
  App.py                    ← Streamlit entry point, login wall
  pages/
    0_generate_invoice.py   ← Invoice generation UI + optional project-code allocation
    1_how_to_use.py         ← Quick-reference guide (Actions / Views / edit map)
    2_invoice_log.py        ← Invoice log + Excel export
    3_clients_projects.py   ← Client & project master data
    4_pipeline_crm.py       ← Pipeline / CRM
    5_dashboard.py          ← Financial dashboard
    6_project_codes.py      ← Billing codes management (suffix + date ranges)
    7_time_tracking.py      ← Time-charge import & rollup
    8_write_offs.py         ← Write-off management
    9_data_tables.py        ← Direct table viewer
    10_project_overview.py  ← Project-level financial overview
    11_add_new_project.py   ← Flat intake form: client + project + codes in one step
    12_billing_basis.py     ← Annual billing summary — Auto (time entries) + Manual sources; is_preferred selection
    13_consultant_profiles.py ← Employment details, salary history, billing rates
    14_annual_review.py     ← Annual assessment: compensation, scores, Feedback Form Word export
    15_data_field_definitions.py ← Field reference guide

backend/
  db.py                     ← All SQLite access (CRUD functions)
  invoice_gen.py            ← DOCX template filling + PDF conversion

shared/
  config.py                 ← Paths, credentials (from .streamlit/secrets.toml)
  models.py                 ← Dataclass definitions (Client, Project, Invoice, …)
  ui.py                     ← Shared UI helpers (dataframe_with_total pinned footer)

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
| client_type | TEXT | `managed` / `external` / `internal` |
| country | TEXT | e.g. `Cyprus` |
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
| status | TEXT | Active / Completed / On Hold / Prospect |
| date_start | TEXT | YYYY-MM-DD; when the project started |

Unique on `(client_id, name)`.

Setting `status = 'Completed'` via the UI automatically sets all active project codes to `Completed` with `date_end = today`.

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
| template_used | TEXT | Template actually used when generating (historical record) |
| format | TEXT | PDF or DOCX |
| file_path | TEXT | Absolute path of generated file |
| expenses_net | REAL | |
| expenses_vat | REAL | |
| status | TEXT | `outstanding` / `paid` / `partial` |
| paid_date | TEXT | ISO date; blank if not yet paid |
| created_at | TEXT | |

### `invoice_allocations`

Splits an invoice's net amount across project codes. Created automatically (pro-rata by budget) if no manual allocation is provided at invoice generation time.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| invoice_id | INTEGER FK→invoices | Cascade delete |
| project_code_id | INTEGER FK→project_codes | |
| amount | REAL | Net amount allocated to this code |
| created_at | TEXT | |

Unique on `(invoice_id, project_code_id)`.

### `pipeline`

Tracks both standalone prospects (no project required) and entries linked to live projects.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| project_id | INTEGER FK→projects NULLABLE | NULL for standalone prospects |
| is_prospect | INTEGER | 1 = standalone prospect; 0 = linked to a project |
| company_name | TEXT | Prospect-only: free-text company name |
| prospect_name | TEXT | Prospect-only: opportunity / engagement name |
| description | TEXT | Prospect-only: free-text notes |
| stage | TEXT | Prospect / Active / On Hold / Completed |
| value | REAL | Contracted value |
| budget_min | REAL | For forecasting |
| budget_est | REAL | For forecasting |
| budget_max | REAL | For forecasting |
| probability | REAL | 0.0–1.0 |
| notes | TEXT | |
| updated_at | TEXT | |
| date_entered_pipeline | TEXT | ISO date — set on first INSERT |
| date_entered_stage | TEXT | ISO date — updated when stage changes |
| opportunity_country | TEXT | Country of the opportunity (editable in grid) |

A partial unique index enforces uniqueness on `project_id` only for non-NULL values (`WHERE project_id IS NOT NULL`), allowing multiple NULL `project_id` rows (standalone prospects) while ensuring each live project has at most one pipeline entry.

### `project_codes`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| project_id | INTEGER FK→projects | Cascade delete |
| client_code | TEXT | Derived from parent client — never entered directly |
| client_suffix | TEXT | e.g. `07` |
| name | TEXT | |
| description | TEXT | |
| budget_amount | REAL | Per-suffix budget |
| status | TEXT | Active / On Hold / Completed |
| date_start | TEXT | YYYY-MM-DD; `''` means no lower bound (first use of this suffix) |
| date_end | TEXT | YYYY-MM-DD; `''` means open-ended |
| created_at | TEXT | |

Unique on `(client_code, client_suffix, date_start)`.

The same suffix can be reused for a later project by creating a new row with a non-empty `date_start`. Time entries are routed to whichever code's date range contains the entry's period. `client_code` is always derived from `project → client` at write time — it is never a free-text user input, ensuring it always matches the parent client.

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
| status | TEXT | `Active` / `Inactive`; Local consultants only; determines Annual Review visibility |

### `consultant_profiles`

One row per consultant — extended HR details.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| emp_nbr | TEXT | |
| employment_date | TEXT | YYYY-MM-DD |
| prior_exp_years | REAL | Years of experience before joining Milliman |
| milliman_status | TEXT | e.g. `Approved Professional` |
| external_level | TEXT | e.g. `Senior Consultant` |
| languages | TEXT | Free text |
| tools | TEXT | Free text |
| current_role | TEXT | |
| notes | TEXT | |

### `annual_salary_history`

One row per consultant per year.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| emp_nbr | TEXT | |
| year | INTEGER | |
| starting_salary | REAL | Carried from prior year's updated_salary |
| exams_passed | REAL | Can be fractional (e.g. 1.5) |
| exam_raise_per_exam | REAL | €/exam |
| other_raise | REAL | Discretionary raise |
| effective_date | TEXT | YYYY-MM-DD |
| objective_bonus_pct | REAL | e.g. 0.07 for 7% |
| bonus_paid | REAL | Actual bonus paid (historical record) |
| proposed_rate | REAL | Proposed hourly billing rate for the following year |
| notes | TEXT | |

### `billing_basis`

One or two rows per consultant per year (one per source).

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| emp_nbr | TEXT | |
| year | INTEGER | |
| source | TEXT | `time_tracking` or `manual` |
| is_preferred | INTEGER | `1` = explicitly chosen for Annual Review calc; `0` otherwise |
| billed | REAL | |
| capped_paid_prebill | REAL | |
| capped_unpaid_prebill | REAL | |
| charged_off | REAL | |
| paid | REAL | |
| unbilled | REAL | |
| avg_annual_rate | REAL | Weighted avg rate from time entries: SUM(non_z_charges)/SUM(non_z_hours). Used for Productivity Bonus % when > 0; falls back to hourly_rate otherwise. |
| hourly_rate | REAL | Reference/proposed billing rate — shown on Rates by Year view |
| notes | TEXT | |

Unique on `(emp_nbr, year, source)`. Both sources can coexist per year; `is_preferred=1` marks the one used by the Annual Review.

**Rate precedence for bonus calculation:** `avg_annual_rate` (when > 0) → `hourly_rate`. This ensures a mid-year rate change is properly weighted rather than using a single snapshot rate.

### `review_scores`

One row per consultant per year per score group per item.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| emp_nbr | TEXT | |
| year | INTEGER | |
| score_group | TEXT | `Professionalism` / `Management` / `Social Skills` |
| item_name | TEXT | e.g. `Modelling skills` |
| score | REAL | 1.0–4.0 |

Unique on `(emp_nbr, year, score_group, item_name)`.

### `review_feedback`

Narrative text per consultant per year per area.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| emp_nbr | TEXT | |
| year | INTEGER | |
| area | TEXT | `Professionalism` / `Management` / `Social Skills` / `Other` / `_project_rows` |
| comments | TEXT | Narrative from feedback provider |
| development_ideas | TEXT | Suggested areas for growth |

Unique on `(emp_nbr, year, area)`. The special area `_project_rows` stores JSON for Section 4A project action decisions.

---

## Key DB Functions (Pipeline & Billing Basis)

### Pipeline

| Function | Description |
|----------|-------------|
| `get_pipeline()` | Returns all pipeline rows (prospects + linked projects) as `list[dict]`. Uses LEFT JOIN to projects and clients; computes `display_client`, `display_project`, and `country` unified columns via CASE. |
| `upsert_pipeline(project_id, stage, ...)` | Explicit SELECT → INSERT/UPDATE (no ON CONFLICT, as SQLite partial unique indexes do not support that clause). Sets `date_entered_pipeline` on first insert; updates `date_entered_stage` only when stage changes. |
| `add_prospect(company_name, ...)` | Inserts a standalone prospect row (`project_id=NULL`, `is_prospect=1`). Returns `lastrowid`. |
| `update_prospect(pipeline_id, ...)` | Updates a prospect row in-place. Only operates on rows where `is_prospect=1`. |
| `convert_prospect_to_project(pipeline_id, project_id)` | Links a prospect to a real project: sets `project_id`, clears `is_prospect=0`, advances stage to Active if currently Prospect, clears prospect-only fields. |
| `delete_prospect(pipeline_id)` | Deletes a row WHERE `id=? AND is_prospect=1`. |

### Billing Basis

| Function | Description |
|----------|-------------|
| `get_monthly_billing_rate_breakdown(emp_nbr, year)` | Returns a `list[dict]` — one row per period. Fields: `period`, `non_z_hours`, `non_z_charges`, `avg_nonz_rate` (non_z_charges/non_z_hours), `total_hours`, `total_charges`, `avg_total_rate`. Used to compute the weighted Avg Annual Rate. |
| `upsert_billing_basis(..., avg_annual_rate=0.0)` | INSERT OR REPLACE on `(emp_nbr, year, source)`. Now includes `avg_annual_rate` in both INSERT and UPDATE. |

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
