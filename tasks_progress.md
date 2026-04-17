# Task: Sprint 3 — Data Management
# Started: 2026-04-17
# Status: COMPLETE

## Main Steps

- [x] 1. Create `frontend/pages/1_invoice_log.py`
  - [x] 1.1 Auth guard + page setup
  - [x] 1.2 Filter controls (year, client, project, free-text search)
  - [x] 1.3 Filterable invoice table with per-row file download
  - [x] 1.4 Export visible data to Excel button

- [x] 2. Create `frontend/pages/2_clients_projects.py`
  - [x] 2.1 Auth guard + tabbed layout (Clients / Projects / Addresses)
  - [x] 2.2 Clients tab: list, add (duplicate detection), edit, delete
  - [x] 2.3 Projects tab: list by client, add, edit (description/VAT/template/status), delete
  - [x] 2.4 Addresses tab: list by client, add, delete

## Log
| Timestamp | Step | Action | Notes |
|-----------|------|---------|-------|
| 2026-04-17 | Start | Sprint 3 plan added to tasks_progress.md | Data Management pages |
| 2026-04-17 | 1.1–1.4 | Created frontend/pages/1_invoice_log.py | Filters, summary strip, per-row download, Excel export |
| 2026-04-17 | 2.1–2.4 | Created frontend/pages/2_clients_projects.py | Tabbed CRUD: clients, projects, addresses — add/edit/delete with guards |

---

## Completed Tasks

### Sprint 2 — Invoice Generation (2026-04-17)
| Step | Action | Notes |
|------|---------|-------|
| 1.1–1.4 | Requirements & config files created | requirements.txt, .streamlit/config.toml, secrets.toml template, .gitignore |
| 2.1–2.3 | Created backend/invoice_gen.py | fill_placeholders, generate_invoice, convert_to_pdf via ConvertAPI |
| 3.1–3.2 | Created frontend/App.py | Login form, session state guard, sign-out button, init_db() on startup |
| 4.1–4.4 | Created frontend/pages/0_generate_invoice.py | Full form: client/project auto-fill, invoice number suggestion, DOCX/PDF generation, DB save, download |
