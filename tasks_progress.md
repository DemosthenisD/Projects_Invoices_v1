# Task: Sprint 2 — Invoice Generation
# Started: 2026-04-17
# Status: COMPLETE

## Main Steps

- [x] 1. Requirements & Config setup
  - [x] 1.1 Create `requirements.txt` in repo root
  - [x] 1.2 Create `.streamlit/config.toml` (theme)
  - [x] 1.3 Create `.streamlit/secrets.toml` template
  - [x] 1.4 Update `.gitignore` to protect secrets

- [x] 2. Create `backend/invoice_gen.py`
  - [x] 2.1 `fill_placeholders(doc, data)` — replace tokens in paragraphs & tables
  - [x] 2.2 `generate_invoice(data, fmt)` — fill template, save DOCX to exports/
  - [x] 2.3 `convert_to_pdf(docx_path)` — call ConvertAPI, return PDF path

- [x] 3. Create `frontend/App.py` (login entry point)
  - [x] 3.1 Login form with username/password from secrets
  - [x] 3.2 Session state guard; redirect to invoice page on success

- [x] 4. Create `frontend/pages/0_generate_invoice.py`
  - [x] 4.1 Client selector with address & VAT auto-fill from DB
  - [x] 4.2 Project selector with description & template auto-fill from DB
  - [x] 4.3 Amount, date, auto-suggested invoice number
  - [x] 4.4 Generate DOCX/PDF → save to DB → show download button

## Log
| Timestamp | Step | Action | Notes |
|-----------|------|---------|-------|
| 2026-04-17 | Start | Created tasks_progress.md | Sprint 2 plan documented |
| 2026-04-17 | 1.1–1.4 | Requirements & config files created | requirements.txt, .streamlit/config.toml, secrets.toml template, .gitignore |
| 2026-04-17 | 2.1–2.3 | Created backend/invoice_gen.py | fill_placeholders, generate_invoice, convert_to_pdf via ConvertAPI |
| 2026-04-17 | 3.1–3.2 | Created frontend/App.py | Login form, session state guard, sign-out button, init_db() on startup |
| 2026-04-17 | 4.1–4.4 | Created frontend/pages/0_generate_invoice.py | Full form: client/project auto-fill, invoice number suggestion, DOCX/PDF generation, DB save, download |
