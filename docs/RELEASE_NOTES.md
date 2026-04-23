# InvoiceApp — Release Notes

---

> **Updates on 23 Apr 2026** — Sprint 9 delivered: project-code date-range routing (suffix reuse across projects), `invoice_allocations` table with optional pro-rata split on invoice generation, `template_used` column rename for clarity, `client_code` integrity enforced at write time, and a new flat "Add New Project" intake page (page 11). All schema changes migrate automatically on startup; documentation fully refreshed.

---

## Sprint 9 — Schema Integrity & Project Intake (April 2026)

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`project_codes`** — added `date_start TEXT DEFAULT ''` and `date_end TEXT DEFAULT ''`. Unique constraint changed from `(client_code, client_suffix)` to `(client_code, client_suffix, date_start)`, allowing the same suffix to be reused for a later project by setting a start date on the new code.
- **`invoices`** — column `template` renamed to `template_used` to make clear it records which template was actually used at generation time (historical record), distinct from `projects.template` which is the default for future invoices.
- **`invoice_allocations`** — new table: splits an invoice's net amount across project codes. Created automatically using pro-rata by budget if no manual allocation is provided.
- **`projects.template`** — stale legacy values (`Template-1`, `Template-2`, `template1`) normalised to current filenames (`template1_v3`, `template2_v3`) in all existing rows.

### New Features

- **Project Code date-range routing:** Time entries are now routed to the correct project code based on their period date when a suffix has been reused. Entries before a code's `date_start` stay with the original project; entries on or after route to the new one.
- **client_code integrity enforced:** `add_project_code()` now derives `client_code` from the project's parent client at write time. It is no longer a free-text user input, closing the data-integrity gap where the stored code could differ from the actual client code.
- **Invoice allocation to project codes:** When generating an invoice, an optional "Project Code Allocation" section lets you split the net amount across the project's active codes. If left blank, the system computes pro-rata weights from each code's budget (equal split if all budgets are zero). Allocations are stored in `invoice_allocations` and can be updated after the fact.
- **Page 11 — Add New Project:** New flat intake page. Fill in client, project, and any number of project code rows in a single form. A single "Import to Database" button creates only missing records — safe to re-run.

### UI Updates

- **Page 6 — Project Codes:** `client_code` input removed (shown as read-only info); Date Start and Date End fields added to add and edit forms; code label shows date range when set.
- **Page 0 — Generate Invoice:** "Project Code Allocation" expander added between the amount section and the Advanced section; shows pro-rata hints per code and validates that manual allocations balance to the invoice net amount.
- **Page 1 — How to Use:** Updated to reflect all new pages, fields, and workflows.

---

## Sprint 8 — Quick Wins & Bug Fixes (April 2026)

### Bug Fixes
- **BUG 1:** `get_invoices()` now accepts an optional `project_id` filter parameter (previously caused an error when called from the Time Tracking page).
- **BUG 2:** Write-off allocation preview no longer references an unset session state key; proportions are shown correctly without a broken amount preview.

### Improvements
- **SP 1:** Sidebar is now expanded by default on load — all pages are visible without needing to click.
- **SP 2:** Login form inputs now carry `autocomplete` attributes so browsers can offer saved credentials.
- **SP 3b:** Generate Invoice page now shows a caption clarifying that clicking the button saves the file to the `exports/` folder permanently; the Download button is optional.
- **SP 4b:** Invoice Log now displays a header row (Date | Invoice # | Client | Project | Net € | VAT € | Expenses € | File).
- **SP 4c:** Invoice Log now includes an **Expenses €** column.
- **SP 4d:** Invoice Log now shows a caption explaining that the PDF/DOCX button downloads from the local disk and may be unavailable if the file was moved.

---

## Sprint 7 — Project Codes, Time Tracking & Write-offs (April 2026)

### New Features
- **Page 5 — Project Codes:** Manage billing codes (`client_code` + `client_suffix`) per project. Per-code metrics: budget, billable charges, write-offs, remaining.
- **Page 6 — Time Tracking:** Import monthly time-charge CSV reports. View entries by batch, filter, and delete. Rollup tab shows project and per-code summaries.
- **Page 7 — Write-offs:** Record project-level (pro-rata) or ad-hoc write-offs. Log with reversal support.
- **Billing summary** added to each project card on Clients & Projects page (billable charges, invoiced, write-offs, remaining).

### Infrastructure
- `project_codes`, `time_entries`, and `write_offs` tables added to DB schema.
- `backend/db.py` extended with full CRUD for new tables, bulk import, and rollup queries.
- `shared/models.py` extended with `ProjectCode`, `TimeEntry`, and `WriteOff` dataclasses.
- `scripts/seed_from_csv.py`: one-time import of clients, projects, and project codes from NocoDb CSV exports.
- 19 new tests (29 total passing).

### PDF Fix
- Replaced ConvertAPI (cloud, requires network) with **docx2pdf** (local, drives Microsoft Word) + **LibreOffice headless** fallback. No network calls required.

---

## Sprint 6 — Polish & Tests (March 2026)

### Improvements
- Replaced `datetime.utcnow()` (deprecated) with `datetime.now(timezone.utc)`.
- Added comprehensive test suite: 10 tests covering clients, addresses, projects, invoices, and pipeline CRUD.
- Requirements file pinned with minimum versions.
- README updated with setup instructions.

---

## Sprint 5 — Pipeline / CRM (March 2026)

### New Features
- **Page 3 — Pipeline / CRM:** Track pipeline projects by stage (Prospect → Won/Lost) with value and notes.
- **Page 4 — Dashboard:** High-level metrics for invoiced total, VAT, and gross by year.

---

## Sprint 4 — Clients & Projects (February 2026)

### New Features
- **Page 2 — Clients & Projects:** Full client and project management with cascading expanders, add/edit/delete, and VAT/template assignment per project.
- Projects linked to addresses; multiple addresses per client supported.

---

## Sprint 3 — Invoice Log (February 2026)

### New Features
- **Page 1 — Invoice Log:** Filterable list of all invoices with per-row download and Excel export.
- Filters: Year, Client, Project, free-text search.

---

## Sprint 2 — Generate Invoice (January 2026)

### New Features
- **Page 0 — Generate Invoice:** Full invoice generation flow — client → project → amount/date → DOCX/PDF output.
- Template placeholder filling (handles tokens split across runs).
- Invoice number auto-suggestion (max per year + 1).
- Expenses section (net + VAT).

---

## Sprint 1 — Foundation (January 2026)

### Initial Setup
- Streamlit multi-page app structure (`frontend/App.py` + `pages/`).
- SQLite backend (`data/invoiceapp.db`) with `clients`, `addresses`, `projects`, `invoices`, and `pipeline` tables.
- Login wall with session state.
- Shared config via `.streamlit/secrets.toml`.
- Two invoice templates: `template1_v3.docx` (CY, 19% VAT) and `template2_v3.docx` (GR, 0% VAT).

---

## Upcoming

- **Sprint 9:** Documentation suite (this file, USER_MANUAL.md, TECHNICAL.md).
- **Sprint 10:** Invoice Log cascading filters; Generate Invoice project-first selection; Data Tables viewer page; Project Overview page; Pipeline tabular summary.
- **Sprint 11:** Pipeline min/max/est budget + probability forecasting; Consultant grouping (Local / ICEE / Other) with time-charge breakdown.
