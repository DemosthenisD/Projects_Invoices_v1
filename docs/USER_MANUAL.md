# InvoiceApp — User Manual

## What This App Is For

InvoiceApp is a personal billing management tool for Milliman Cyprus. It lets you:

- Generate professional invoices from Word templates and download them as PDF or DOCX.
- Maintain a log of all invoices with filtering and Excel export.
- Manage clients, projects, and project codes (billing codes).
- Import monthly time-charge reports and see billable amounts per project/code.
- Track write-offs against projects with pro-rata or ad-hoc allocation.
- Manage the sales pipeline with stage tracking and forecasting.
- View a dashboard of key financial metrics.

---

## Pages

### Home (App.py)

The landing page after sign-in. Use the **left sidebar** to navigate between pages. All pages are listed in the sidebar at all times.

**Sign in:** Enter your username and password. Your browser's saved-password feature will auto-complete these once you save them the first time.

---

### Page 0 — Generate Invoice

**What it does:** Fills a Word template with invoice details, saves it to the `exports/` folder, and offers a download button.

**Step-by-step:**

1. **Select a client** — address and VAT number auto-fill.
2. **Select a project** — description, VAT %, and template auto-fill.
3. Enter the **invoice date**, **amount (net)**, and confirm the **invoice number** (auto-suggested).
4. *(Optional)* Expand **Project Code Allocation** to manually split the net amount across project codes. Enter amounts per code; the page shows the pro-rata hint for each. If you leave all at 0, the system allocates automatically using each code's budget as the weight (equal split if all budgets are zero).
5. *(Optional)* Expand **Advanced** to choose PDF vs DOCX, and add expense lines.
6. Click **Generate Invoice**.

**What happens when you click Generate Invoice:**
- The DB record is saved immediately.
- The filled DOCX (and PDF if selected) is written to `exports/` permanently (e.g. `exports/2025_42_ClientName_Invoice.pdf`).
- A **Download** button appears — this is a convenience copy. The file already exists in `exports/` even if you do not click Download.

**Tips:**
- The invoice number is auto-incremented per year. You can edit it if needed.
- If PDF conversion fails (requires Microsoft Word or LibreOffice to be installed), switch to DOCX in the Advanced section.

---

### Page 1 — Invoice Log

**What it does:** Shows all recorded invoices with filters and per-row file download.

**Filters:**

| Filter | Behaviour |
|--------|-----------|
| Year | Shows only invoices from that year |
| Client | Shows only invoices for that client |
| Project | Shows only invoices for that project |
| Search | Matches invoice number or project name |

**Columns:** Date | Invoice # | Client | Project | Net € | VAT € | Expenses € | File

**File column:** Click the PDF/DOCX button to download the file from your local disk. If the file has been moved or deleted, the button shows "—".

**Export to Excel:** Downloads all visible (filtered) rows as an `.xlsx` file.

---

### Page 2 — Clients & Projects

**What it does:** Manages client and project master data.

**Client section:**
- Add a new client with name, billing name, client code, VAT number, and VAT %.
- Edit or delete existing clients (deletion is blocked if projects exist).

**Project section:**
- For each client, view their projects in expandable cards.
- Each card shows: description, VAT %, template, status, and a billing summary (billable charges, invoiced, write-offs, remaining).
- Add, edit, or delete projects.

---

### Page 3 — Pipeline / CRM

**What it does:** Tracks prospective and in-progress business opportunities.

**Summary table:** Shows all pipeline entries with stage, value, and notes at a glance. Filter by stage.

**Per-project detail:** Expand a project to edit its pipeline stage, estimated value, probability, and notes. Budget fields (Min/Est/Max) are used for forecasting.

**Dashboard integration:** The Dashboard page shows probability-weighted pipeline forecasts derived from these fields.

---

### Page 4 — Dashboard

**What it does:** High-level financial overview.

Shows metrics for the current year: invoiced total, VAT, gross, and pipeline forecast (probability-weighted min/est/max).

---

### Page 5 — Project Codes

**What it does:** Manages billing codes (client suffix) for each project. Each code has its own budget, date range, and status.

The `client_code` portion (e.g. `0478EUR30`) is set automatically from the client record — you only need to enter the suffix (e.g. `07`). Together they form the full billing code (e.g. `0478EUR30-07`) used to match imported time entries.

**To add a code:** Select client → project → fill in suffix, budget, and status.

**Reusing a suffix across projects:** The same suffix can be used on a different project at a later time. Set **Date Start** (YYYY-MM-DD) on the new code to mark when this project takes over. Time entries are routed automatically: entries whose period falls before the Date Start belong to the original project; entries on or after belong to the new one. Leave Date End blank for open-ended codes.

**Per-code metrics shown:** budget, billable charges, write-offs, remaining budget.

---

### Page 6 — Time Tracking

**What it does:** Imports monthly time-charge reports and provides rollup views.

**Import tab:**
1. Upload a CSV file in the standard format (see `sample_time_sheet.csv`).
2. Unmatched codes (combinations not in the project codes table) are shown before import.
3. Click **Confirm Import** to load entries. Duplicate rows (same period/employee/code) are skipped.

**Entries tab:** Browse imported time entries by client, project, and period. Delete an entire import batch if needed.

**Rollup tab:** Project-level and per-code summary of billable hours, charges, write-offs, and net. Also shows a Local / ICEE / Other breakdown by consultant group.

**Consultant Groups tab:** Assign each consultant to Local, ICEE, or Other. Pre-populated from the ICEE Plan CY Excel on first seed.

---

### Page 7 — Write-offs

**What it does:** Records write-offs against projects (reductions in billable amount).

**Create tab:**

- **Project-level:** Allocates the write-off amount pro-rata across all consultants on the project (by their billable charges). An allocation preview is shown before saving.
- **Ad-hoc:** Records a write-off for a specific consultant directly.

**Log tab:** Shows all write-offs with client/project filters. Reversed write-offs can be shown or hidden.

---

### Page 8 — Data Tables

**What it does:** Direct view of all underlying database tables for inspection and editing.

Use the tabs to switch between tables. The **"Open DB"** button shows the full path of the database file and opens the containing folder in File Explorer. To edit the DB directly, download [DB Browser for SQLite](https://sqlitebrowser.org/dl/) — it provides a spreadsheet-style interface with no coding required.

---

### Page 11 — Add New Project

**What it does:** A single flat form that creates a client (if new), a project, and any number of project codes in one step.

**Sections:**

1. **Client** — select an existing client or fill in details for a new one. If a client with the same name already exists, the existing record is used and no duplicate is created.
2. **Project** — name, description, VAT %, invoice template, and status.
3. **Project Codes** — a row-per-code table. Use **+ Add row** / **− Remove last row** to adjust. For each row: suffix, name, budget, Date Start, Date End, and status.

**Click Import to Database** — the app creates only what is missing. It is safe to run multiple times; no duplicates are created.

**When to use instead of Page 6:** Use Page 11 when you are setting up an entirely new engagement. Use Page 6 when you need to add a single code to an existing project or edit an existing code.

---

### Page 9 — Project Overview

**What it does:** Full project-level financial summary across all clients.

Columns: Client | Project | Source | Codes | Budget (€) | Billable (€) | Write-offs (€) | Net (€) | Invoiced (€) | Remaining (€) | Status

**Project_Source** is derived from the client code prefix:
- `0478` → CY (Cyprus)
- `0009` → NotBillable
- Other → Other

Filters: Client, Status, Source (multi-select). Export to Excel available.

---

## Frequently Asked Questions

**Where are generated invoice files stored?**
In the `exports/` subfolder of the repo, e.g. `C:\...\InvoiceApp\exports\`. Files are named `YEAR_INVOICENO_CLIENTNAME_Invoice.pdf`.

**Where is the database?**
At `data/invoiceapp.db` relative to the repo root. See TECHNICAL.md for details on how to open and edit it directly.

**PDF generation fails — what do I do?**
PDF conversion requires Microsoft Word (via the `docx2pdf` library) or LibreOffice installed on the machine. If neither is available, select DOCX format in the Advanced section on the Generate Invoice page.

**How do I back up my data?**
Copy `data/invoiceapp.db` and the `exports/` folder to a safe location. That is the complete data set.

**Can I reuse a client suffix for a new project?**
Yes — set a **Date Start** on the new project code (YYYY-MM-DD). Time entries whose period falls on or after that date are automatically routed to the new project; earlier entries stay with the original. Leave Date End blank on both codes unless you want an explicit end date. Only one code per suffix may have a blank Date Start (the original first use).
