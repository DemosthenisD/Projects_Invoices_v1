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

The landing page after sign-in. Use the **left sidebar** to navigate between pages. All pages are listed in the sidebar at all times, grouped by section.

**Sign in:** Enter your username and password. Your browser's saved-password feature will auto-complete these once you save them the first time.

---

### How to Use

A brief in-app orientation page. Always visible at the top of the sidebar (no number assigned).

---

### Page 1 — Generate Invoice

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

### Page 2 — Invoice Log

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

### Page 3 — Clients & Projects

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

### Page 4 — Add New Project

**What it does:** A single flat form that creates a client (if new), a project, and any number of project codes in one step.

**Sections:**

1. **Client** — select an existing client or toggle to **Create new client**. If creating new, fill in: name, billing name, client code, VAT number, **Client Type** (managed / external / internal), and Country. If a client with the same name already exists, the existing record is reused and no duplicate is created.
2. **Project** — name, description, VAT %, invoice template, and status.
3. **Project Codes** — a row-per-code table. Use **+ Add row** / **− Remove last row** to adjust. For each row: suffix, name, budget, Date Start, Date End, and status. Project codes are **optional for external and internal clients** (overhead / non-billable); at least one code is required for managed clients.

**Click Import to Database** — the app creates only what is missing. It is safe to run multiple times; no duplicates are created.

**When to use instead of Page 5:** Use Page 4 when you are setting up an entirely new engagement. Use Page 5 when you need to add a single code to an existing project or edit an existing code.

---

### Page 5 — Project Codes

**What it does:** Manages billing codes (client suffix) for each project. Each code has its own budget, date range, and status.

The `client_code` portion (e.g. `0478EUR30`) is set automatically from the client record — you only need to enter the suffix (e.g. `07`). Together they form the full billing code (e.g. `0478EUR30-07`) used to match imported time entries.

**To add a code:** Select client → project → fill in suffix, budget, and status.

**Reusing a suffix across projects:** The same suffix can be used on a different project at a later time. Set **Date Start** (YYYY-MM-DD) on the new code to mark when this project takes over. Time entries are routed automatically: entries whose period falls before the Date Start belong to the original project; entries on or after belong to the new one. Leave Date End blank for open-ended codes.

**Per-code metrics shown:** budget, billable charges, write-offs, remaining budget.

---

### Page 6 — Pipeline / CRM

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

### Page 7 — Dashboard

**What it does:** High-level financial overview.

Shows metrics for the current year: invoiced total, VAT, gross, and pipeline forecast (probability-weighted min/est/max).

---

### Page 8 — Project Overview

**What it does:** Full project-level financial summary across all clients.

**Columns:** Client | Type | Project | Source | Codes | Budget (€) | Billable (€) | Write-offs (€) | Net (€) | Invoiced (€) | Remaining (€) | Status

**Project Source** is derived from the client code prefix:
- `0478` → CY (Cyprus)
- `0009` → NotBillable
- Other → Other

**Filters (6 multiselects):**

| Filter | Behaviour |
|--------|-----------|
| Client | Show only selected clients |
| Status | Default: Active only; add On Hold / Completed as needed |
| Source / Office | Filter by derived source (CY / NotBillable / Other) |
| Type | Filter by client type (managed / external / internal) |
| Consultant Group | Show only projects where at least one consultant in the selected group has billed hours |
| Consultant | Show only projects where the selected consultant has billed hours |

**Sorting:** Click any column header. Amount columns sort numerically (not lexicographically) — billable totals sort correctly regardless of magnitude.

**Subtotals:** A **TOTAL** row is appended at the bottom of the main table and each sub-table, aggregating all visible amounts with comma thousands separators.

**Year-by-Year view:** Expands under each project to show per-code, per-year breakdown of billable hours, charges, and internal hours. Each of the three sub-tables (hours, charges, internal) has a TOTAL column and TOTAL row.

**Export to Excel:** Downloads all visible rows.

---

### Page 9 — Time Tracking

**What it does:** Imports monthly time-charge reports and provides rollup views.

**Import tab:**
1. Upload a CSV file in the standard format (see `sample_time_sheet.csv`). Files encoded in UTF-8, UTF-8-BOM, or Windows-1252 (common Excel export encoding) are all handled automatically.
2. Unmatched codes (combinations not in the project codes table) are shown before import.
3. Click **Confirm Import** to load entries. Duplicate rows (same period/employee/code) are skipped.

**Entries tab:** Browse imported time entries by client, project, and period. Delete an entire import batch if needed.

**Rollup tab:** Project-level and per-code summary of billable hours, charges, write-offs, and net.

*Filters (6 controls):*

| Control | Description |
|---------|-------------|
| Client Type | Filter by managed / external / internal |
| Country | Filter by client country |
| Client | Filter by specific client (multiselect) |
| Project | Filter by specific project (multiselect) |
| Period From | Earliest period to include (e.g. `202401`) |
| Period To | Latest period to include (e.g. `202412`) |

*View toggle:*
- **By Code (current):** Standard per-code table for the selected project with a TOTAL row.
- **Year-by-Year:** Pivot showing each code as a row and each calendar year as a column, so you can compare across years at a glance. TOTAL column and TOTAL row included.

*Breakdown sections (below the main table, filtered by the same period):*
- **Breakdown by Group:** Billable hours and charges per consultant group (Local / ICEE / Other), with TOTAL row.
- **Breakdown by Consultant:** Group radio at top to filter the list; per-consultant billable hours and charges table with TOTAL row.

**Team Summary tab:** Shows aggregate hours and charges across all projects and periods.

*Three sub-sections:*
- **By Consultant:** Each consultant's total billable hours and charges, grouped by consultant group, with a TOTAL row. Group radio at top to pre-filter.
- **By Consultant & Project:** Same as By Consultant but drills one level deeper — each consultant row expands to show the individual projects they billed on, with hours and charges per project. TOTAL row per consultant and overall.
- **Period pivot:** Consultant × period matrix showing billable hours and charges broken down by month.

**Consultant Groups tab:** Assign each consultant to Local, ICEE, or Other.
- **Group radio** at the top selects which group to view (defaults to Local).
- Only the consultants in the selected group are shown, in alphabetically sorted expanders.
- Pre-populated from the ICEE Plan CY Excel on first seed.

---

### Page 10 — Write-offs

**What it does:** Records write-offs against projects (reductions in billable amount).

**Create tab:**

- **Project-level:** Allocates the write-off amount pro-rata across all consultants on the project (by their billable charges). An allocation preview is shown before saving.
- **Ad-hoc:** Records a write-off for a specific consultant directly.

**Log tab:** Shows all write-offs with client/project filters. Reversed write-offs can be shown or hidden.

---

### Page 11 — Billing Basis

**What it does:** Annual billing summary per consultant, used as the basis for productivity-bonus calculation.

**Selectors:** Financial Year and Group (Local / ICEE / Other / All — defaults to Local).

**Tabs:**

- **Auto (from Time Tracking):** Aggregates `non_z_charges` per consultant from imported time entries for the selected year. Write-offs are mapped to the Charged Off column. Click **Load from Time Tracking** to preview, then enter hourly rates and click **Save Auto Basis**.
- **Manual Entry:** Spreadsheet-style table matching the bonus template's Sheet5 layout (Billed / Capped Paid Prebill / Capped Unpaid Prebill / Charged Off / Paid / Unbilled). A computed summary below shows Grand Total, Basis for Bonus, Equivalent Hours, and Productivity Bonus % live as you type. Click **Save Manual Basis** to persist.
- **Saved Basis:** Read-only view of all saved rows for the year.

  *Group filter:* Radio above the table restricts the display to the selected group (Local / ICEE / Other / All).

  *Re-arrange to Show By:* A selectbox with 7 view modes:

  | Mode | Description |
  |------|-------------|
  | By Consultant | Default view — one row per consultant with all billing columns and derived metrics |
  | By Group | Aggregated per consultant group (Local / ICEE / Other) |
  | By Consultant → Project | Per consultant, broken down by project; uses time-entry amounts |
  | By Project | Aggregated per project across all consultants; uses time-entry amounts |
  | By Project → Group | Per project, broken down by consultant group |
  | By Project → Consultant | Per project, broken down by individual consultant |
  | By Project → Group → Consultant | Full three-level drill-down: project → group → consultant |

  All views include a TOTAL row and comma-separated thousands in all amount columns. Export to Excel available.

**Derived values (computed, not stored):**
- **Grand Total** = sum of all six billing columns.
- **Basis for Bonus** = Grand Total − Charged Off.
- **Equivalent Hours** = Basis for Bonus ÷ Hourly Rate.
- **Productivity Bonus %** = `max(Equiv Hrs − 800, 0) / 40 × 1%`.

---

### Page 12 — Consultant Profiles

**What it does:** Extended master data and salary history per consultant.

**Selector:** Group radio (Local / ICEE / Other / All — defaults to Local), then individual consultant selectbox.

**Tabs:**

- **Profile:** Employment start date, prior experience (years before Milliman), Milliman professional status, external level, current role, languages, tools, and notes. Years at Milliman and total experience computed and shown automatically.
- **Salary History:** Year-by-year salary chain. Add or edit year records with: starting salary (auto-carried from prior year's updated salary), exams passed, raise per exam, other/discretionary raise, effective date, objective bonus %, bonus paid (historical), and proposed billing rate. A live preview shows Exam Raise, Total Raise, and Updated Salary as you type. Productivity Bonus % is pulled automatically from the saved Billing Basis for that year.

  **Delete a Year Record:** A separate section below the Add/Edit form lets you select a year from a dropdown and permanently delete that salary record. A warning is shown before deletion.

- **Rates by Year:** Side-by-side view of Proposed Rate (from Salary History) and Billing Basis Rate (from Billing Basis) per year.

---

### Page 13 — Annual Review

**What it does:** Per-consultant annual assessment form combining compensation, performance scores, and a formatted review summary.

**Selector:** Group radio (Local / ICEE / Other / All — defaults to Local), then individual consultant selectbox filtered to the chosen group.

**Sections:**

1. **Compensation:** Auto-pulls productivity bonus % from the saved Billing Basis. Salary chain computed live (starting salary → exam raise → other raise → updated salary → bonus amount). Proposed billing rate compared to the Billing Basis hourly rate.

2. **Performance Scores:** Three groups with a configurable number of scored items:
   - *Professionalism* (7 items)
   - *Management* (6 items — shown for all consultants; set to 0 for non-managers)
   - *Social Skills* (5 items)

   Historical comparison against 3 prior years is shown alongside the current year's scores.

3. **Summary:** Formatted review card showing the consultant's full compensation and performance summary. **Export to Excel** downloads a workbook with a Summary sheet and a Performance Scores sheet.

---

### Page 14 — Data Tables

**What it does:** Direct view of all underlying database tables for inspection and editing.

Use the tabs to switch between tables. The **"Open DB"** button shows the full path of the database file and opens the containing folder in File Explorer. To edit the DB directly, download [DB Browser for SQLite](https://sqlitebrowser.org/dl/) — it provides a spreadsheet-style interface with no coding required.

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
In the Invoice Log (Page 2), click the **± Part.** button on the invoice row to open an inline form. Enter the amount received, the date, and an optional note. Click **Record Payment**. The invoice status changes to Partial, and the Balance € column updates to show the remaining amount. Repeat for subsequent receipts. Click **↩ Reset** to clear all payment records and revert to Outstanding.

**How do I issue a Credit Note?**
On Page 1 — Generate Invoice, toggle **Document type** to Credit Note. Enter the net amount as a positive number (it is stored as negative automatically). Optionally enter the original Invoice No being credited. Click Generate. The credit note appears in the Invoice Log with a 🔄 icon and the referenced invoice number shown as a caption.

**What do the client types mean?**
- **managed** — standard consulting clients with full project tracking, budgets, and invoices.
- **external** — clients outside the normal managed scope; tracked at a basic level; project codes optional.
- **internal** — non-billable overhead codes (e.g. internal projects, admin time). Project codes optional.

**Why can't I see a consultant in the Billing Basis or Consultant Profiles page?**
These pages default to the Local group filter. Use the Group radio at the top to switch to ICEE, Other, or All.

**Time-charge CSV import fails with a Unicode error — what do I do?**
The importer automatically tries UTF-8, UTF-8-BOM, Windows-1252, and Latin-1 encodings in sequence. If your file was exported from Excel on Windows (common for files containing special characters such as en-dashes), it is likely Windows-1252 and will be handled automatically. If the import still fails, open the file in Excel and re-save it as CSV UTF-8.

**The Project Overview sort on amount columns doesn't seem to work correctly — is that fixed?**
Yes. Amount columns are stored as numbers internally and displayed with comma thousands separators. Clicking a column header sorts numerically (e.g. 86,541 → 70,000 → 3,168), not lexicographically.

**Where do the Billing Basis "By Project" view amounts come from?**
The `billing_basis` table stores amounts at the consultant level, not per project. For all project-centric view modes (By Project and below), the app uses time-entry charges aggregated per project. This is noted in the UI. The consultant-level modes (By Consultant, By Group) use the saved Billing Basis amounts.
