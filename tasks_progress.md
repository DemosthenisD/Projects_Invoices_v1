# Task: Sprint 4 — Pipeline/CRM & Sprint 5 — Dashboard
# Started: 2026-04-17
# Status: IN PROGRESS

## Main Steps

- [x] 1. Create `frontend/pages/3_pipeline_crm.py`
  - [x] 1.1 Auth guard + page setup
  - [x] 1.2 Filter controls (stage, client)
  - [x] 1.3 Pipeline table with inline stage/value/notes editing
  - [x] 1.4 Summary by stage (project count + total value)

- [ ] 2. Create `frontend/pages/4_dashboard.py`
  - [ ] 2.1 Auth guard + page setup + year selector
  - [ ] 2.2 Monthly revenue bar chart (net vs gross)
  - [ ] 2.3 Revenue by client bar chart
  - [ ] 2.4 VAT summary table (net + VAT + gross totals)
  - [ ] 2.5 YTD vs prior year comparison metrics

## Log
| Timestamp | Step | Action | Notes |
|-----------|------|---------|-------|
| 2026-04-17 | Start | Sprint 4 & 5 plan added | Pipeline/CRM and Dashboard pages |
| 2026-04-17 | 1.1–1.4 | Created frontend/pages/3_pipeline_crm.py | Stage/client filters, inline editing, stage summary metrics |

---

## Completed Tasks

### Sprint 3 — Data Management (2026-04-17)
| Step | Action | Notes |
|------|---------|-------|
| 1.1–1.4 | Created frontend/pages/1_invoice_log.py | Filters, summary strip, per-row download, Excel export |
| 2.1–2.4 | Created frontend/pages/2_clients_projects.py | Tabbed CRUD: clients, projects, addresses — add/edit/delete with guards |

### Sprint 2 — Invoice Generation (2026-04-17)
| Step | Action | Notes |
|------|---------|-------|
| 1.1–1.4 | Requirements & config files created | requirements.txt, .streamlit/config.toml, secrets.toml template, .gitignore |
| 2.1–2.3 | Created backend/invoice_gen.py | fill_placeholders, generate_invoice, convert_to_pdf via ConvertAPI |
| 3.1–3.2 | Created frontend/App.py | Login form, session state guard, sign-out button, init_db() on startup |
| 4.1–4.4 | Created frontend/pages/0_generate_invoice.py | Full form: client/project auto-fill, invoice number suggestion, DOCX/PDF generation, DB save, download |
