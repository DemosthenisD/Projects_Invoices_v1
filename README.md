# InvoiceApp — V1.0

Personal invoice and project billing management tool built with **Streamlit** and **SQLite**.

---

## Setup

```bash
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml`:

```toml
username = "Demosthenis"
password = "your-password"
```

## Running the App

```bash
streamlit run frontend/App.py
```

Opens at http://localhost:8501. Sign in with the credentials above.

## Running Tests

```bash
python -m pytest tests/ -v
```

29 tests covering DB CRUD, bulk import, write-off allocation, and invoice generation.

---

## Pages

| # | Page | Description |
|---|------|-------------|
| 0 | Generate Invoice | Fill client/project details, generate DOCX or PDF; optional project-code allocation; file saved permanently to `exports/` |
| 1 | How to Use | Quick reference: page summaries (Actions vs Views), edit guide, DB Browser tip |
| 2 | Invoice Log | Browse, filter (cascading), and download past invoices; export to Excel |
| 3 | Clients & Projects | Manage clients, projects, addresses; per-project billing summary |
| 4 | Pipeline / CRM | Track pipeline by stage; set min/est/max budget + probability; probability-weighted forecast |
| 5 | Dashboard | YTD revenue, monthly chart, revenue by client, VAT summary, pipeline forecast |
| 6 | Project Codes | Manage billing codes (suffix + date range); client_code auto-derived; per-code budget vs billable vs remaining |
| 7 | Time Tracking | Import monthly time-charge CSVs; date-range aware routing; rollup with Local/ICEE/Other breakdown |
| 8 | Write-offs | Record project-level (pro-rata) or ad-hoc write-offs; reversal log |
| 9 | Data Tables | Direct view of all DB tables; open in DB Browser for SQLite |
| 10 | Project Overview | Full project-level financial summary; filter by client/status/source; export to Excel |
| 11 | Add New Project | Flat intake form: client + project + codes in one step; import creates only missing records |
| 12 | Billing Basis | Annual billing summary per consultant (auto from time entries or manual entry); computes productivity bonus % |
| 13 | Consultant Profiles | Employment details, Milliman status/level, salary history year-by-year, billing rates |
| 14 | Annual Review | Per-consultant annual assessment: salary chain, bonus calculation, performance scores (3 groups), Excel export |

---

## Architecture

```
frontend/           Streamlit pages
backend/db.py       All SQLite access (CRUD + analytics queries)
backend/invoice_gen.py  DOCX template filling + PDF conversion
shared/config.py    Paths and credentials (from secrets.toml)
shared/models.py    Dataclasses: Client, Project, Invoice, ProjectCode, TimeEntry, WriteOff, …
data/invoiceapp.db  SQLite database (single file, excluded from git)
templates/          Word invoice templates (template1_v3, template2_v3)
exports/            Generated invoice files — PDF and DOCX (excluded from git)
scripts/            Seed utilities (CSV import, consultant groups)
docs/               User manual, technical reference, release notes
```

## Database

All data lives in a single SQLite file: `data/invoiceapp.db`.

**Tables:** `clients`, `addresses`, `projects`, `invoices`, `invoice_allocations`, `pipeline`, `project_codes`, `time_entries`, `write_offs`, `consultant_groups`, `consultant_profiles`, `annual_salary_history`, `billing_basis`, `review_scores`

To inspect or edit the database directly, use [DB Browser for SQLite](https://sqlitebrowser.org/dl/) (free, Windows). The app's **Data Tables** page (page 9) has a button that opens the file directly.

## PDF Conversion

PDF generation uses **docx2pdf** (drives Microsoft Word locally) with **LibreOffice headless** as a fallback. No cloud API or network calls required. If neither is installed, select DOCX format in the Advanced section on the Generate Invoice page.

## Seeding Data

```bash
# Import clients, projects, and project codes from NocoDb CSV exports
python scripts/seed_from_csv.py

# Pre-populate consultant groups from CONSULTANTS.csv
python scripts/seed_consultant_groups.py
```

## Documentation

Full documentation is in the `docs/` folder:

- [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) — step-by-step guide for each page
- [`docs/TECHNICAL.md`](docs/TECHNICAL.md) — architecture, DB schema, file locations
- [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) — version history by sprint
