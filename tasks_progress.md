# Task: Sprint 2 — Invoice Generation
# Started: 2026-04-17
# Status: IN PROGRESS

## Main Steps

- [x] 1. Requirements & Config setup
  - [x] 1.1 Create `requirements.txt` in repo root
  - [x] 1.2 Create `.streamlit/config.toml` (theme)
  - [x] 1.3 Create `.streamlit/secrets.toml` template
  - [x] 1.4 Update `.gitignore` to protect secrets

- [ ] 2. Create `backend/invoice_gen.py`
  - [ ] 2.1 `fill_placeholders(doc, data)` — replace tokens in paragraphs & tables
  - [ ] 2.2 `generate_invoice(data, fmt)` — fill template, save DOCX to exports/
  - [ ] 2.3 `convert_to_pdf(docx_path)` — call ConvertAPI, return PDF path

- [ ] 3. Create `frontend/App.py` (login entry point)
  - [ ] 3.1 Login form with username/password from secrets
  - [ ] 3.2 Session state guard; redirect to invoice page on success

- [ ] 4. Create `frontend/pages/0_generate_invoice.py`
  - [ ] 4.1 Client selector with address & VAT auto-fill from DB
  - [ ] 4.2 Project selector with description & template auto-fill from DB
  - [ ] 4.3 Amount, date, auto-suggested invoice number
  - [ ] 4.4 Generate DOCX/PDF → save to DB → show download button

## Log
| Timestamp | Step | Action | Notes |
|-----------|------|---------|-------|
| 2026-04-17 | Start | Created tasks_progress.md | Sprint 2 plan documented |
| 2026-04-17 | 1.1–1.4 | Requirements & config files created | requirements.txt, .streamlit/config.toml, secrets.toml template, .gitignore |
