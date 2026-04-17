# Task: Bug fixes — round 2
# Started: 2026-04-17
# Status: COMPLETE

## Main Steps

- [x] 1. Fix DOCX placeholders not being replaced
  - [x] 1.1 Root cause: data dict in 0_generate_invoice.py uses named keys (Client_Name_For_Invoice etc.) but templates use numbered keys ({{placeholder1}} etc.)
  - [x] 1.2 Fix: rewrite data dict to use correct placeholder numbers; add placeholder6 for v1/v2 template compatibility

- [x] 2. Fix PDF SSL in corporate proxy environment
  - [x] 2.1 Root cause: Milliman SSL inspection proxy presents a corporate CA cert not in certifi's bundle; env-var approach only works for non-intercepted connections
  - [x] 2.2 Fix: temporarily monkey-patch requests.Session to disable SSL verification only for the convertapi call

## Log
| Timestamp | Step | Action | Notes |
|-----------|------|---------|-------|
| 2026-04-17 | Start | Round 2 bug fixes planned | Placeholder mapping error + corporate SSL proxy |
| 2026-04-17 | 1.1–1.2 | Fixed placeholder mapping in 0_generate_invoice.py | Data dict now uses placeholder1–placeholder10 keys matching template format |
| 2026-04-17 | 2.1–2.2 | Fixed PDF SSL in invoice_gen.py | Monkey-patch requests.Session to disable SSL only for convertapi call; always restores original |

---

# Bug fixes — round 1 (COMPLETE 2026-04-17)

## Main Steps

- [x] 1. Fix false "already exists" on project/client/address add forms
  - [x] 1.1 Root cause: `st.rerun()` preserves form submit state in Streamlit 1.28 causing double-processing
  - [x] 1.2 Fix: use form key counter in session_state to force fresh form on rerun

- [x] 2. Fix PDF conversion SSL error
  - [x] 2.1 Root cause: Windows Python can't verify ConvertAPI SSL cert with its default CA bundle
  - [x] 2.2 Fix: point requests to certifi's CA bundle before calling convertapi
  - [x] 2.3 Also fix: set both `api_secret` and `api_credentials` to cover convertapi 1.5.x and 1.7+

## Log
| Timestamp | Step | Action | Notes |
|-----------|------|---------|-------|
| 2026-04-17 | Start | Bug fixes task created | Two bugs found during first test run |
| 2026-04-17 | 1.1–1.2 | Fixed double form submission in 2_clients_projects.py | Form key counter in session_state; success msgs via session_state |
| 2026-04-17 | 2.1–2.3 | Fixed PDF SSL error in invoice_gen.py | certifi CA bundle for requests; both api_secret and api_credentials set |

---

# Sprint 4 — Pipeline/CRM & Sprint 5 — Dashboard (COMPLETE 2026-04-17)

## Main Steps

- [x] 1. Create `frontend/pages/3_pipeline_crm.py`
  - [x] 1.1 Auth guard + page setup
  - [x] 1.2 Filter controls (stage, client)
  - [x] 1.3 Pipeline table with inline stage/value/notes editing
  - [x] 1.4 Summary by stage (project count + total value)

- [x] 2. Create `frontend/pages/4_dashboard.py`
  - [x] 2.1 Auth guard + page setup + year selector
  - [x] 2.2 Monthly revenue bar chart (net vs gross)
  - [x] 2.3 Revenue by client bar chart
  - [x] 2.4 VAT summary table (net + VAT + gross totals)
  - [x] 2.5 YTD vs prior year comparison metrics

## Log
| Timestamp | Step | Action | Notes |
|-----------|------|---------|-------|
| 2026-04-17 | Start | Sprint 4 & 5 plan added | Pipeline/CRM and Dashboard pages |
| 2026-04-17 | 1.1–1.4 | Created frontend/pages/3_pipeline_crm.py | Stage/client filters, inline editing, stage summary metrics |
| 2026-04-17 | 2.1–2.5 | Created frontend/pages/4_dashboard.py | Year selector, monthly chart, client chart, VAT table, YTD vs prior year |

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
