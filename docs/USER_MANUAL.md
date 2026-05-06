# InvoiceApp — User Manual

## What This App Is For

InvoiceApp is a personal billing management tool for Milliman Cyprus. It lets you:

- Generate professional invoices and credit notes from Word templates and download them as PDF or DOCX.
- Maintain a log of all invoices with sorting, filtering, partial-payment tracking, and Excel export.
- Manage clients, projects, and project codes (billing codes).
- Import monthly time-charge reports and see billable amounts per project/code.
- Track write-offs against projects with pro-rata or ad-hoc allocation.
- Manage the sales pipeline with stage tracking and forecasting.
- View a dashboard of key financial metrics.
- Run annual consultant reviews with bonus calculation and performance scoring.

---

## Pages

### Home (App.py)

The landing page after sign-in. Use the **left sidebar** to navigate between pages. All pages are listed in the sidebar at all times.

**Sign in:** Enter your username and password. Your browser's saved-password feature will auto-complete these once you save them the first time.

---

### Page 0 — Generate Invoice

**What it does:** Fills a Word template with invoice details, saves it to the `exports/` folder, and offers a download button. Also supports Credit Notes.

**Step-by-step:**

1. **Document type** — toggle between **Invoice** (default) and **Credit Note**. Credit notes store a negative amount and are used to negate or partially reverse a previous invoice.
2. *(Credit Notes only)* Optionally enter the original **Invoice No being credited** — this is a reference field only; it appears as a caption in the Invoice Log.
3. **Select a client** — address and VAT number auto-fill.
4. **Select a project** — description, VAT %, and template auto-fill. Tick **Include completed projects** to see Active, On Hold, and Completed projects.
5. Enter the **invoice date**, **amount (net, always positive)**, and confirm the **Invoice ID** (sequential counter, auto-suggested). The **Invoice No** shown on the document is formatted as `ID/YYYY` (e.g. `12/2026`).
6. *(Optional)* Expand **Project Code Allocation** to manually split the net amount across project codes. If you leave all at 0, the system allocates automatically using each code's budget as the weight (equal split if all budgets are zero).
7. *(Optional)* Expand **Advanced** to choose PDF vs DOCX, and add expense lines.
8. Click **Generate Invoice**.

**What happens when you click Generate Invoice:**
- The DB record is saved immediately (credit notes are stored with a negative amount).
- The filled DOCX (and PDF if selected) is written to `exports/` permanently (e.g. `exports/2026_12-2026_ClientName_Invoice.docx`).
- A **Download** button appears — this is a convenience copy. The file already exists in `exports/` even if you do not click Download.

**Tips:**
- The Invoice ID is auto-incremented per year and shared between invoices and credit notes. You can edit it if needed.
- If PDF conversion fails (requires Microsoft Word or LibreOffice to be installed), switch to DOCX in the Advanced section.

---

### Page 1 — Invoice Log

**What it does:** Shows all recorded invoices and credit notes with sorting, filters, payment tracking, and per-row file download. A second tab lets you bulk-upload historical invoices.

#### Log tab

**Sorting:** Use the **Sort by** selectbox (Date, Invoice ID, Amount, Client, Status, Type) and **Direction** radio (Ascending / Descending) above the table.

**Filters:**

| Filter | Behaviour |
|--------|-----------|
| Year | Shows only invoices from that year |
| Client | Shows only invoices for that client |
| Project | Shows only invoices for that project |
| Status | `outstanding` / `paid` / `partial` / All |
| Search | Matches invoice number or project name |

**Summary strip:** Shows count, net total, gross total, and **actual outstanding balance** (accounting for partial payments).

**Columns:** Date · Invoice ID · Inv No (`ID/YYYY`) · Type (📄 Invoice / 🔄 Credit Note) · Client · Project · Net € · VAT € · Status · Balance € · File · Action

- **Type** — 📄 for invoices, 🔄 for credit notes. Credit note rows show a caption with the referenced original invoice number.
- **Status** — colour-coded badge: 🔴 outstanding · 🟢 paid · 🟡 partial.
- **Balance €** — gross amount minus payments received. Shows `—` for legacy paid records with no individual payment rows; `€0` for fully paid invoices with payment records.
- **Payment history** — individual payment receipts shown as captions below each row (date, amount, optional note).
- **Action buttons:**
  - **✓ Pay** — record a full payment for the remaining balance (today's date, no note).
  - **± Part.** — toggle an inline form to record a partial payment with amount, date, and optional note. Multiple partial payments can be recorded; each appears in the history.
  - **↩ Reset** — shown for paid/partial invoices. Clears all payment records and reverts the invoice to Outstanding.
- **File column** — click the PDF/DOCX button to download from your local disk. Shows "—" if the file was moved.

**Export to Excel:** Downloads all visible rows including Type, Related Invoice No, Paid (€), Balance (€), Status, and Paid Date columns.

#### Bulk Upload tab

Use this when you need to load several historical invoices at once.

1. Click **Download blank template** to get a pre-filled Excel file with all columns and reference sheets.
2. Fill in the `Invoices` sheet (one row per invoice). `client_id` must match the Client Reference sheet. The template includes **Type** (Invoice / Credit Note) and **Related Invoice No** columns.
3. Upload the completed file — the app shows a preview row count.
4. Click **Import invoices**. Duplicates (same Invoice No + Year) are skipped automatically.

---

### Page 2 — Clients & Projects

**What it does:** Manages client and project master data.

**Client section (Clients tab):**
- A summary table shows all clients with columns: Name, Code, Type (🟢 managed / 🔵 external / ⚪ internal), Country, Name for invoices, total projects, active projects, and active codes.
- Filters: name search, client type (managed / external / internal), country.
- **Add new client** expander: name, billing name, client code, country, VAT number, client type.
- **Edit / delete a client** expander: select a client from a dropdown then edit its fields. Deletion is blocked if invoices are linked.

**Project section (Projects tab):**
- Filter by client, status, client type, and country.
- Totals bar shows aggregate Budget, Billable, Write-offs, and Invoiced for the filtered view.
- Each project expander shows: description, VAT %, template, status, start date, budget breakdown by project code (including date ranges), and a billing summary (billable charges, invoiced, write-offs).
- **Setting a project to Completed** automatically closes all its active project codes (sets status = Completed, date_end = today) and shows a confirmation message with the count of codes closed.
- **Admin: sync completed project budgets** expander — click to auto-set zero-budget codes for Completed projects. The invoiced total for each completed project is divided equally across its codes. Useful when project codes were created without budgets and you want the budget to reflect actual invoiced amounts.

---

### Page 3 — Pipeline / CRM

**What it does:** Tracks prospective and in-progress business opportunities with inline editing.

**Summary strip:** Count and total value per stage (Prospect / Active / On Hold / Completed).

**Probability-weighted forecast** (shown when at least one project has budget fields set):
- Weighted Min, Weighted Est, Weighted Max = budget × probability for each project.

**Inline editing table:** All pipeline rows are displayed in a single editable grid. You can directly edit:
- Stage (dropdown: Prospect / Active / On Hold / Completed)
- Value (€), Min (€), Est (€), Max (€)
- Prob % (0–100)
- Notes

Click **Save changes** to persist all edits in one go.

Filters (Stage, Client) apply before the table is rendered. Changes outside the filter are not affected.

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

1. **Client** — select an existing client or toggle to **Create new client**. If creating new, fill in: name, billing name, client code, VAT number, **Client Type** (managed / external / internal), and Country. If a client with the same name already exists, the existing record is reused and no duplicate is created.
2. **Project** — name, description, VAT %, invoice template, and status.
3. **Project Codes** — a row-per-code table. Use **+ Add row** / **− Remove last row** to adjust. For each row: suffix, name, budget, Date Start, Date End, and status. Project codes are **optional for external and internal clients** (overhead / non-billable); at least one code is required for managed clients.

**Click Import to Database** — the app creates only what is missing. It is safe to run multiple times; no duplicates are created.

**When to use instead of Page 5:** Use Page 11 when you are setting up an entirely new engagement. Use Page 5 when you need to add a single code to an existing project or edit an existing code.

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

### Page 12 — Billing Basis

**What it does:** Annual billing summary per consultant, used as the basis for productivity-bonus calculation.

**Selectors:** Financial Year and Group (Local / ICEE / Other / All — defaults to Local).

**Tabs:**

- **Auto (from Time Tracking):** Aggregates `non_z_charges` per consultant from imported time entries for the selected year. Write-offs are mapped to the Charged Off column. Click **Load from Time Tracking** to preview, then enter hourly rates and click **Save Auto Basis**.
- **Manual Entry:** Spreadsheet-style table matching the bonus template's Sheet5 layout (Billed / Capped Paid Prebill / Capped Unpaid Prebill / Charged Off / Paid / Unbilled). A computed summary below shows Grand Total, Basis for Bonus, Equivalent Hours, and Productivity Bonus % live as you type. Click **Save Manual Basis** to persist.
- **Saved Basis:** Read-only view of all saved rows for the year. Export to Excel available.

**Derived values (computed, not stored):**
- **Grand Total** = sum of all six billing columns.
- **Basis for Bonus** = Grand Total − Charged Off.
- **Equivalent Hours** = Basis for Bonus ÷ Hourly Rate.
- **Productivity Bonus %** = `max(Equiv Hrs − 800, 0) / 40 × 1%`.

---

### Page 13 — Consultant Profiles

**What it does:** Extended master data and salary history per consultant.

**Selector:** Group radio (Local / ICEE / Other / All — defaults to Local), then individual consultant selectbox.

**Tabs:**

- **Profile:** Employment start date, prior experience (years before Milliman), Milliman professional status, external level, current role, languages, tools, and notes. Years at Milliman and total experience computed and shown automatically.
- **Salary History:** Year-by-year salary chain. Add or edit year records with: starting salary (auto-carried from prior year's updated salary), exams passed, raise per exam, other/discretionary raise, effective date, objective bonus %, bonus paid (historical), and proposed billing rate. A live preview shows Exam Raise, Total Raise, and Updated Salary as you type. Productivity Bonus % is pulled automatically from the saved Billing Basis for that year.
- **Rates by Year:** Side-by-side view of Proposed Rate (from Salary History) and Billing Basis Rate (from Billing Basis) per year.

---

## Frequently Asked Questions

**Where are generated invoice files stored?**
In the `exports/` subfolder of the repo, e.g. `C:\...\InvoiceApp\exports\`. Files are named `YEAR_ID-YYYY_CLIENTNAME_Invoice.docx` (e.g. `2026_12-2026_ERGO_Invoice.docx`). Note: the `/` in the Invoice No is replaced with `-` in the filename to avoid OS path separator issues.

**Where is the database?**
At `data/invoiceapp.db` relative to the repo root. See TECHNICAL.md for details on how to open and edit it directly.

**PDF generation fails — what do I do?**
PDF conversion requires Microsoft Word (via the `docx2pdf` library) or LibreOffice installed on the machine. If neither is available, select DOCX format in the Advanced section on the Generate Invoice page.

**How do I back up my data?**
Copy `data/invoiceapp.db` and the `exports/` folder to a safe location. That is the complete data set.

**Can I reuse a client suffix for a new project?**
Yes — set a **Date Start** on the new project code (YYYY-MM-DD). Time entries whose period falls on or after that date are automatically routed to the new project; earlier entries stay with the original. Leave Date End blank on both codes unless you want an explicit end date. Only one code per suffix may have a blank Date Start (the original first use).

**How do I record a partial payment on an invoice?**
In the Invoice Log, click the **± Part.** button on the invoice row to open an inline form. Enter the amount received, the date, and an optional note. Click **Record Payment**. The invoice status changes to Partial, and the Balance € column updates to show the remaining amount. Repeat for subsequent receipts. Click **↩ Reset** to clear all payment records and revert to Outstanding.

**How do I issue a Credit Note?**
On the Generate Invoice page, toggle **Document type** to Credit Note. Enter the net amount as a positive number (it is stored as negative automatically). Optionally enter the original Invoice No being credited. Click Generate. The credit note appears in the Invoice Log with a 🔄 icon and the referenced invoice number shown as a caption.

**What do the client types mean?**
- **managed** — standard consulting clients with full project tracking, budgets, and invoices.
- **external** — clients outside the normal managed scope; tracked at a basic level; project codes optional.
- **internal** — non-billable overhead codes (e.g. internal projects, admin time). Project codes optional.

**Why can't I see a consultant in the Billing Basis or Consultant Profiles page?**
These pages default to the Local group filter. Use the Group radio at the top to switch to ICEE, Other, or All.
