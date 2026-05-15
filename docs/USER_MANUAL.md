# InvoiceApp — User Manual

## What This App Is For

InvoiceApp is a personal billing management tool for Milliman Cyprus. It lets you:

- Generate professional invoices and credit notes from Word templates and download them as PDF or DOCX.
- Maintain a log of all invoices with sorting, filtering, partial-payment tracking, and Excel export.
- Manage clients, projects, and project codes (billing codes).
- Import monthly time-charge reports and see billable amounts per project/code.
- Track write-offs against projects with pro-rata or ad-hoc allocation.
- Manage the sales pipeline — track prospects from first contact through conversion to a live project.
- View a dashboard of key financial metrics.
- Run annual consultant reviews with bonus calculation and performance scoring.

---

## How To

Step-by-step guides for the most common tasks. Each guide lists the exact pages and actions in order.

---

### How to Issue an Invoice

1. Go to **1. Generate Invoice**.
2. Ensure **Document type** is set to **Invoice** (default).
3. Select the **client** — address and VAT number auto-fill.
4. Select the **project** — description, VAT %, and template auto-fill. Tick **Include completed projects** if the project is marked Completed.
5. Enter the **invoice date**, **net amount**, and confirm the auto-suggested **Invoice ID**.
6. *(Optional)* Expand **Project Code Allocation** to manually split the net amount across project codes, or leave at 0 for automatic pro-rata.
7. *(Optional)* Expand **Advanced** to choose PDF vs DOCX and add expense lines.
8. Click **Generate Invoice** — the file is saved to `exports/` and a Download button appears.

---

### How to Issue a Credit Note

1. Go to **1. Generate Invoice**.
2. Toggle **Document type** to **Credit Note**.
3. *(Optional)* Enter the **Invoice No being credited** (reference only — appears as a caption in the log).
4. Select client and project as normal.
5. Enter the **net amount as a positive number** — it is stored and displayed as negative automatically.
6. Click **Generate Invoice**.
7. The credit note appears in the Invoice Log with a 🔄 icon.

---

### How to Record a Payment on an Invoice

**Full payment:**
1. Go to **2. Invoice Log**.
2. Find the invoice and click **✓ Pay** — records a full payment for the remaining balance with today's date.

**Partial payment:**
1. Go to **2. Invoice Log**.
2. Find the invoice and click **± Part.** to open the inline payment form.
3. Enter the **amount received**, the **date**, and an optional **note**.
4. Click **Record Payment** — invoice status changes to Partial and the Balance updates.
5. Repeat for each subsequent receipt.

**To undo all payments:**
- Click **↩ Reset** — clears all payment records and reverts the invoice to Outstanding.

---

### How to Add a New Client and Project

**Option A — Add New Project page (recommended for new engagements):**
1. Go to **4. Add New Project**.
2. In **Section 1 — Client**, toggle to **Create new client** and fill in: name, billing name, client code, VAT number, client type, and country.
3. In **Section 2 — Project**, fill in: project name, description, VAT %, template, and status.
4. In **Section 3 — Project Codes**, enter at least one billing code row (suffix, budget, status). Click **+ Add row** for additional codes.
5. Click **Import to Database** — creates only missing records (safe to re-run).

**Option B — Clients & Projects page (for editing existing data):**
1. Go to **3. Clients & Projects**.
2. Use the **Clients tab** to add or edit client details.
3. Use the **Projects tab** to add or edit projects within a client.

---

### How to Add a Project Code to an Existing Project

1. Go to **5. Project Codes**.
2. Select the **client** and **project**.
3. Fill in the **suffix**, budget, optional date range, and status.
4. Click **Add Project Code**.

**To reuse a suffix that was used on a previous project:**
1. Create the new code with the same suffix.
2. Set **Date Start** (YYYY-MM-DD) to the first period this code should apply to.
3. Time entries on or after that date route to the new project automatically; earlier entries stay with the original.

---

### How to Add a Prospect to the Pipeline

1. Go to **6. Pipeline / CRM**.
2. Click **➕ Add Prospect** to expand the form.
3. Fill in: **Company name** (required), opportunity name, description, country, stage, budget min/est/max, and probability %.
4. Click **Add Prospect** — the entry appears in the pipeline table immediately.
5. Edit stage, budgets, probability, and notes at any time using the inline table and **Save changes**.

---

### How to Convert a Prospect to a Project (When Won)

1. Go to **6. Pipeline / CRM**.
2. Scroll to **Prospect Actions** at the bottom.
3. Select the prospect from the dropdown.
4. Click **Convert to Project →** — the app navigates to **4. Add New Project** with the company name, opportunity name, and description pre-filled.
5. Complete the remaining fields: client code, VAT, client type, project codes, etc.
6. Click **Import to Database** — the pipeline entry is automatically linked to the new project and its stage advances to Active.

---

### How to Import Monthly Time Charges

1. Export the monthly time-charge report from the billing system as CSV.
2. Go to **9. Time Tracking → Import tab**.
3. Upload the CSV file — unmatched codes are shown for review before import.
4. Click **Confirm Import** to load entries. Duplicate rows (same period/employee/code) are skipped automatically.
5. Check the **Rollup tab** to verify the imported amounts per project and code.

---

### How to Prepare the Annual Billing Basis

**Auto (from imported time entries):**
1. Go to **11. Billing Basis**.
2. Select the **Financial Year** and filter by **Consultant Team** (defaults to Local).
3. Click **Load from Time Tracking** — preview table and monthly rate breakdown appear.
4. Review the **Avg Annual Rate** pre-filled from the weighted average of NonZ Rate across all periods. Edit if needed — this rate is used for the Productivity Bonus % calculation.
5. Enter a **Hourly Rate (reference)** if different from the avg rate.
6. Click **Save Auto Basis**.

**Manual entry:**
1. Go to **11. Billing Basis → Manual Entry tab**.
2. Fill in billing amounts for each consultant: Billed, Capped Paid Prebill, Capped Unpaid Prebill, Charged Off, Paid, Unbilled.
3. Enter **Avg Annual Rate €/hr** (from the Auto tab monthly breakdown, or from an external source) and **Hourly Rate (reference)**.
4. The computed summary updates live — verify Grand Total, Basis for Bonus, and Productivity Bonus %.
5. Click **Save Manual Basis**.

**If both sources are saved:**
1. Go to **Saved Basis tab** → scroll to the source selector at the bottom.
2. For each consultant with dual entries, choose which source to use and click **Save preferences**.
3. The ✓ indicator updates to confirm which source is Active for Review.

---

### How to Run the Annual Review for a Consultant

1. Complete the billing basis first (see above). The review reads from the saved basis automatically.
2. Go to **11. Billing Basis → Saved Basis tab** and confirm the correct source has ✓ for the consultant.
3. Go to **12. Consultant Profiles**. Select the consultant and confirm the profile is up to date (employment date, status, level, tools).
4. In the **Salary History tab**, add or edit the year record: starting salary (auto-carried from prior year), exams passed, discretionary raise, objective bonus %, proposed rate.
5. Go to **13. Annual Review**. Select the consultant and review year.
6. **Section 1 — Compensation**: review the auto-computed productivity bonus %, adjust inputs if needed, click **Save Compensation**.
7. **Section 2 — Performance Scores**: enter scores 1.0–4.0 for each item across the three groups. Click **Save All Scores**.
8. **Section 3 — Summary**: review the formatted summary card. Click **Export Review to Excel** if needed.

---

### How to Generate the ICEE Feedback Form

1. Complete Section 1 (Compensation) and Section 2 (Scores) for the consultant on **13. Annual Review** first.
2. Expand **Section 4 — Feedback Form Export**.
3. In **Sub-section A**, review the project breakdown auto-filled from time entries:
   - Adjust **Colleagues involved** and **Teams involved** fields if needed.
   - Set each project row to **Include**, **Aggregate**, or **Exclude**.
4. In **Sub-section B**, fill in Assessment Comments and Development Ideas for each performance area.
5. In **Sub-section C**, write any general narrative or additional comments.
6. Click **Save & Generate Feedback Form** — the Word document is saved to `exports/` and a Download button appears.

---

### How to Back Up Your Data

Copy two locations to a safe place:
- `data/invoiceapp.db` — the complete database (all clients, projects, invoices, time entries, HR data).
- `exports/` folder — all generated invoice and feedback form files.

That is everything. No other data needs to be backed up.

---

### How to Fix a Data Error Directly

For corrections not covered by the UI (wrong invoice number, duplicate row, typo in a name):
1. Download **DB Browser for SQLite** from [sqlitebrowser.org](https://sqlitebrowser.org/dl/) — free Windows installer.
2. Go to **14. Data Tables** in the app and note the full database file path shown there.
3. Open the `.db` file in DB Browser → browse to the relevant table → double-click any cell to edit.
4. Click **Write Changes** when done. The app reflects the change immediately on next page load.

---

## Pages

### Home (App.py)

The landing page after sign-in. Use the **left sidebar** to navigate between pages. All pages are listed in the sidebar at all times, grouped by section.

**Sign in:** Enter your username and password. Your browser's saved-password feature will auto-complete these once you save them the first time.

---

### How to Use

A brief in-app orientation page with page summaries, a "Where to go for each edit" quick-reference table, and step-by-step How To guides for all major activities.

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

**When to use instead of Page 3:** Use Page 4 when you are setting up an entirely new engagement, or when converting a pipeline prospect to a live project. Use Page 3 when you need to edit an existing client or project's details.

---

### Page 5 — Project Codes

**What it does:** Manages billing codes (client suffix) for each project. Each code has its own budget, date range, and status.

The `client_code` portion (e.g. `0478EUR30`) is set automatically from the client record — you only need to enter the suffix (e.g. `07`). Together they form the full billing code (e.g. `0478EUR30-07`) used to match imported time entries.

**To add a code:** Select client → project → fill in suffix, budget, and status.

**Reusing a suffix across projects:** The same suffix can be used on a different project at a later time. Set **Date Start** (YYYY-MM-DD) on the new code to mark when this project takes over. Time entries are routed automatically: entries whose period falls before the Date Start belong to the original project; entries on or after belong to the new one. Leave Date End blank for open-ended codes.

**Per-code metrics shown:** budget, billable charges, write-offs, remaining budget.

---

### Page 6 — Pipeline / CRM

**What it does:** Tracks prospects and active business opportunities from first contact through to a live project. Prospects can be added with minimal information — no client record or project setup is required until the engagement is won.

#### Adding Prospects

Click **➕ Add Prospect** to expand the form at the top of the page. Fields:
- **Company name** (required)
- **Opportunity name** — the project or engagement name
- **Description** — free-text notes on the opportunity
- **Country**, **Stage** (Prospect / Active / On Hold / Completed)
- **Budget Min / Est / Max (€)** — range of expected contract value
- **Probability %** — likelihood of winning

Click **Add Prospect** — the entry appears in the pipeline table immediately and contributes to the probability-weighted forecast.

#### Summary and Forecast

**Summary strip:** Count and total value per stage (Prospect / Active / On Hold / Completed).

**Probability-weighted forecast** (shown when at least one entry has budget fields set):
- Weighted Min, Weighted Est, Weighted Max = budget × probability, summed across all filtered entries.

#### Inline Editing Table

All pipeline entries — both standalone prospects and linked project entries — appear in a single editable grid. You can edit directly:
- **Stage** (dropdown: Prospect / Active / On Hold / Completed)
- **Value (€)**, **Min (€)**, **Est (€)**, **Max (€)**
- **Prob %** (0–100)
- **Notes**, **Opp. Country**

Click **Save changes** to persist all edits in one go. Live subtotals for the filtered view are shown below the table.

**Filters:** Stage, Client / Company, Opportunity Country, Client Country, Client Type.

The **Prospect?** column (read-only checkbox) indicates whether a row is a standalone prospect (✓) or a project-linked entry.

#### Prospect Actions

When at least one standalone prospect exists, a **Prospect Actions** section appears at the bottom of the page.

**Convert to Project →**
1. Select the prospect from the dropdown.
2. Click **Convert to Project →** — the app navigates to **Page 4 — Add New Project** with the company name, opportunity name, and description pre-filled.
3. Complete the remaining details (client code, VAT, project codes, etc.) and click **Import to Database**.
4. The pipeline entry is automatically linked to the new project and its stage advances to Active if it was previously Prospect.

**🗑 Delete Prospect**
- Permanently removes the selected prospect entry. This only works for standalone prospects — linked project entries cannot be deleted here.

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

**Consultant Groups tab:** Assign each consultant to Local, ICEE, or Other. Manage Active / Inactive status for Local consultants.
- **Group radio** at the top selects which group to view (defaults to Local).
- Only the consultants in the selected group are shown, in alphabetically sorted expanders. The expander title shows the consultant's current status for Local consultants (e.g. `Savva, Konstantinos (Active)`).
- Each expander has three fields: **Group**, **emp_nbr**, and (for Local consultants) **Status** (Active / Inactive).
- Setting a Local consultant to **Inactive** hides them from the Annual Review consultant dropdown. They remain in all other pages and their historical data is unaffected.
- ICEE and Other consultants have no status concept — the Status column is not shown for them.

---

### Page 10 — Write-offs

**What it does:** Records write-offs against projects (reductions in billable amount).

**Create tab:**

- **Project-level:** Allocates the write-off amount pro-rata across all consultants on the project (by their billable charges). An allocation preview is shown before saving.
- **Ad-hoc:** Records a write-off for a specific consultant directly.

**Log tab:** Shows all write-offs with client/project filters. Reversed write-offs can be shown or hidden.

---

### Page 11 — Billing Basis

**What it does:** Annual billing summary per consultant, used as the basis for productivity-bonus calculation. Two independent sources can be stored per consultant per year — Auto (from imported time entries) and Manual (hand-entered). Only one source is used for the Annual Review; you choose which one explicitly.

**Selectors:** Financial Year and Group (Local / ICEE / Other / All — defaults to Local).

**Tabs:**

- **Auto (from Time Tracking):** Aggregates `non_z_charges` per consultant from imported time entries for the selected year. Write-offs are mapped to the Charged Off column. Click **Load from Time Tracking** to preview.

  The app also computes a **monthly rate breakdown** per consultant — for each billing period: NonZ Hours, NonZ Charges, and the implied NonZ Rate (non_z_charges ÷ non_z_hours). Expand **Monthly rate breakdown** to view this table. The weighted average across all periods gives the **Avg Annual Rate**, which is the fairest billing rate to use for the bonus calculation when a consultant's rate changed during the year.

  Below the preview table, a form lets you set:
  - **Avg Annual Rate €/hr** — pre-filled from the weighted average computed above. Edit if needed. This rate is used for the Productivity Bonus % calculation.
  - **Hourly Rate €/hr (reference)** — your proposed or current rate. Shown on the Rates by Year view but not used for the bonus calculation when Avg Annual Rate is set.

  Click **Save Auto Basis** to persist.

- **Manual Entry:** Spreadsheet-style table matching the bonus template's Sheet5 layout (Billed / Capped Paid Prebill / Capped Unpaid Prebill / Charged Off / Paid / Unbilled). Includes an **Avg Annual Rate €/hr** column — enter the weighted average rate here (obtain it from the Auto tab's monthly breakdown if time entries are available, or enter it manually). A computed summary below shows Grand Total, Basis for Bonus, Equivalent Hours, and Productivity Bonus % live as you type. Click **Save Manual Basis** to persist.

- **Saved Basis:** Read-only view of all saved rows for the year — both sources are shown for consultants who have entries from both.

  *Active for Review indicator:* The **Active for Review** column shows ✓ next to the source that will be used by the Annual Review for each consultant. For consultants with only one saved source, that source is used automatically. For consultants with **both** sources saved, the active source is whichever was last explicitly selected (or defaults to Manual if no explicit choice has been made).

  *Explicit source selection:* At the bottom of the Saved Basis tab, consultants who have both sources saved are listed with a radio button to choose which source to use for the Annual Review. Click **Save preferences** to confirm — the ✓ indicator updates immediately.

  *Group filter:* Radio above the table restricts the display to the selected group.

  *Re-arrange to Show By:* A selectbox with 7 view modes:

  | Mode | Description |
  |------|-------------|
  | By Consultant | Default view — one row per consultant (active source) with all billing columns and derived metrics |
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
- **Effective Rate** = Avg Annual Rate if set (> 0), otherwise Hourly Rate.
- **Equivalent Hours** = Basis for Bonus ÷ Effective Rate.
- **Productivity Bonus %** = `max(Equiv Hrs − 800, 0) / 40 × 1%`.

Using the Avg Annual Rate instead of a fixed Hourly Rate accounts for mid-year billing rate changes and gives a fairer equivalent hours figure — for example, a consultant billed at €100/hr for the first half of the year and €120/hr for the second half would have a weighted Avg Annual Rate of ~€110/hr rather than whichever rate happens to be stored on their profile.

---

### Page 12 — Consultant Profiles

**What it does:** Extended master data and salary history per consultant.

**Selector:** Group radio (Local / ICEE / Other / All — defaults to Local), then individual consultant selectbox.

**Tabs:**

- **Profile:** Employment start date, prior experience (years before Milliman), Milliman professional status, external level, current role, languages, tools, and notes. Years at Milliman and total experience computed and shown automatically.
- **Salary History:** Year-by-year salary chain. Add or edit year records with: starting salary (auto-carried from prior year's updated salary), exams passed, raise per exam, other/discretionary raise, effective date, objective bonus %, bonus paid (historical), and proposed billing rate. A live preview shows Exam Raise, Total Raise, and Updated Salary as you type. Productivity Bonus % is pulled automatically from the saved Billing Basis for that year.

  **Delete a Year Record:** A separate section below the Add/Edit form lets you select a year from a dropdown and permanently delete that salary record. A warning is shown before deletion.

- **Rates by Year:** Side-by-side view of two rates per year:
  - **Proposed Rate for following year (€/hr)** — the rate entered in Salary History, intended as the proposed billing rate for the *next* year.
  - **Billing Basis Rate (€/hr)** — the hourly rate saved on the Billing Basis record for that year (used to convert billing amounts into Equivalent Hours). This is populated when you save a billing basis entry on Page 11.

---

### Page 13 — Annual Review

**What it does:** Per-consultant annual assessment form combining compensation, performance scores, and a formatted review summary.

**Scope:** This page is restricted to **Local + Active** consultants only. To make a consultant visible here, ensure they are in the Local group and have Status = Active in the Consultant Groups tab (Page 9). Inactive Local consultants and all non-Local consultants are excluded.

**Selector:** Consultant selectbox showing all active Local employees.

**Sections:**

1. **Compensation:** Auto-pulls productivity bonus % from the saved Billing Basis. The bonus uses the **Effective Rate** (Avg Annual Rate if set, otherwise Hourly Rate) to convert the billing basis into equivalent hours, ensuring mid-year rate changes are accounted for. Salary chain computed live (starting salary → exam raise → other raise → updated salary). **Bonus Amount = Starting Salary × Total Bonus %** (the bonus is applied to the pre-raise base salary, not the updated salary after the raise). Proposed billing rate compared to the Billing Basis rate.

2. **Performance Scores:** Three groups scored on a **1–4 scale** (1 = Significant underperformance · 2 = Does not meet expectations · 3 = Meets expectations · 4 = Exceeds expectations):
   - *Professionalism* (7 items: Deliverance assignments, Modelling skills, Problem solving, Reporting skills, Presentations skills, Project management, Innovation)
   - *Management* (6 items — shown for all consultants; set to 0 for non-managers)
   - *Social Skills* (5 items: Managing expectations, Client satisfaction, Teamwork, Developing people, Communication)

   Historical comparison against 3 prior years is shown alongside the current year's scores. Group averages are computed automatically.

3. **Summary:** Formatted review card showing the consultant's full compensation and performance summary. **Export to Excel** downloads a workbook with a Summary sheet and a Performance Scores sheet.

4. **Feedback Form Export:** Generates the ICEE Feedback Form Word document (`.docx`) for the selected consultant and year, saved to `exports/feedback_<Name>_<Year>.docx`.

   **Sub-section A — Project Breakdown:** Auto-filled from time entries for the review year. Internal projects (`0009*` codes and internal client type) are excluded automatically. Each row shows: Client, Project name + description, editable **Colleagues involved** field, editable **Teams involved** field, Hours %, Fees %, and an **Action** selector.

   - **Colleagues involved** — other consultants who billed to the same project in the same year, shown as "Firstname Lastname" names separated by ` | `. Only consultants billing to project codes that belong to the specific project are included. The reviewed consultant's own name is removed automatically.
   - **Teams involved** — the consultant teams (Local / ICEE / Other) corresponding to the colleagues on the project. If multiple colleagues belong to the same team, the team name appears only once. This field is used in the generated Word document instead of individual names, giving a cleaner team-level view.

   Both fields are editable before generating the document.

   *Action selector per row:*
   | Action | Effect in the generated document |
   |--------|----------------------------------|
   | **Include** | Row appears as-is |
   | **Exclude** | Row is dropped entirely (use for non-billable or erroneous entries) |
   | **Aggregate** | Row is merged with all other Aggregate rows into a single **Other Projects** line showing the combined hours % and fees % |

   The default action is **Aggregate** for any project representing less than 2 % of the consultant's total fees for the year, and **Include** for all others. You can override any row manually.

   Decisions are saved to the database and reloaded on subsequent visits.

   **Sub-section B — Assessment Comments & Development Ideas:** One block per performance area showing the computed average score. Two editable text fields per area:
   - *Comments from Feedback Provider* — narrative on performance during the year
   - *Development ideas* — suggested areas for growth

   These are saved to the database and pre-loaded on subsequent visits.

   **Sub-section C — Other Comments:** Free-text narrative for the "Other comments" section of the template (general year summary and expectations for the following year).

   Click **Save & Generate Feedback Form** to persist all comments and decisions and produce the Word document. A download button appears immediately after generation.

---

### Page 14 — Data Tables

**What it does:** Direct view of all underlying database tables for inspection and editing.

Use the tabs to switch between tables. The **"Open DB"** button shows the full path of the database file and opens the containing folder in File Explorer. To edit the DB directly, download [DB Browser for SQLite](https://sqlitebrowser.org/dl/) — it provides a spreadsheet-style interface with no coding required.

---

### Page 15 — Field Definitions

**What it does:** In-app reference page listing all field names and their meanings across every section of the app.

Organised by topic area (Invoices, Projects, Time Tracking, Billing Basis, Annual Review, etc.). Use this page when you encounter an unfamiliar field name or want to confirm the exact meaning of a billing column. No actions available — read-only reference.

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

**How do I add a prospect to the pipeline without creating a client or project first?**
Go to **6. Pipeline / CRM** and click **➕ Add Prospect** at the top of the page. Fill in company name (required), opportunity name, description, country, stage, budgets, and probability. No client record, project, or billing codes are needed — these are created later when the prospect converts to a live engagement.

**How do I convert a pipeline prospect to a live project?**
In the **Prospect Actions** section at the bottom of Page 6, select the prospect and click **Convert to Project →**. The app navigates to Page 4 — Add New Project with the company name, opportunity name, and description pre-filled. Complete the remaining fields and click **Import to Database** — the pipeline entry links back to the new project automatically and advances to Active stage.

**Why can't I see a consultant in the Billing Basis or Consultant Profiles page?**
These pages default to the Local group filter. Use the Group radio at the top to switch to ICEE, Other, or All.

**Why is a consultant missing from the Annual Review page?**
The Annual Review only shows **Local + Active** consultants. Check two things: (1) the consultant is in the **Local** group, and (2) their **Status** is **Active**. Both are set in Page 9 — Time Tracking → Consultant Groups tab. Open the consultant's expander and confirm Group = Local and Status = Active, then Save.

**How do I mark a consultant as inactive without losing their data?**
In Page 9 — Time Tracking → Consultant Groups tab, select the Local view, open the consultant's expander, change Status to **Inactive**, and click Save. Their data, time entries, billing history, and scores are fully preserved — they simply no longer appear in the Annual Review consultant dropdown.

**Time-charge CSV import fails with a Unicode error — what do I do?**
The importer automatically tries UTF-8, UTF-8-BOM, Windows-1252, and Latin-1 encodings in sequence. If your file was exported from Excel on Windows (common for files containing special characters such as en-dashes), it is likely Windows-1252 and will be handled automatically. If the import still fails, open the file in Excel and re-save it as CSV UTF-8.

**What is the Avg Annual Rate and how is it different from Hourly Rate?**
The **Avg Annual Rate** is the weighted average billing rate across all periods in the year, computed as `SUM(non_z_charges) / SUM(non_z_hours)` from time entries. It accurately reflects the true effective rate when a consultant's billing rate changed mid-year. The **Hourly Rate** is a single reference figure — usually the current or proposed rate — stored for display on the Rates by Year view. The Productivity Bonus % calculation uses the Avg Annual Rate when it is set (> 0), falling back to Hourly Rate otherwise.

**The Project Overview sort on amount columns doesn't seem to work correctly — is that fixed?**
Yes. Amount columns are stored as numbers internally and displayed with comma thousands separators. Clicking a column header sorts numerically (e.g. 86,541 → 70,000 → 3,168), not lexicographically.

**Where do the Billing Basis "By Project" view amounts come from?**
The `billing_basis` table stores amounts at the consultant level, not per project. For all project-centric view modes (By Project and below), the app uses time-entry charges aggregated per project. This is noted in the UI. The consultant-level modes (By Consultant, By Group) use the saved Billing Basis amounts.

**How does the Feedback Form Export work, and where is the file saved?**
Section 4 on Page 13 (Annual Review) fills the ICEE Feedback Form Word template with data from the app: profile details, time entries for the year (for the project breakdown), saved performance scores (group averages), and the comments/development ideas you enter. The file is saved permanently to `exports/feedback_<Name>_<Year>.docx` and a download button is offered immediately. Comments and development ideas are also persisted in the database so they reload on the next visit.

**The Colleagues column in the Feedback Form shows too many names — can I edit it?**
Yes. Section 4A shows all other consultants who billed to the same project in the same year. The app filters strictly: only consultants billing to project codes that actually belong to the specific project are included — consultants billing to the same client code under a different project are excluded. Names are shown as "Firstname Lastname", deduplicated, and the reviewed consultant's own name is removed automatically. The field is still editable before you click Save & Generate — trim or rewrite it as needed.

**What is the "Teams involved" column in Section 4A?**
Alongside the Colleagues involved column, each project row also shows the consultant teams (Local / ICEE / Other) of the colleagues on that project. If three ICEE consultants worked on the project, "ICEE" appears only once. This field is what gets written into the generated Word document — the Feedback Form template shows teams rather than individual names, which is cleaner and more appropriate for the document. The Teams field is editable before generating.

**Which billing basis source does the Annual Review use — Auto or Manual?**
For consultants with only one saved source, that source is used automatically. For consultants with both sources saved, the Annual Review uses whichever source is marked **Active for Review** (shown with a ✓ in the Saved Basis tab). You set this explicitly at the bottom of the Saved Basis tab using the source radio buttons for each consultant with dual entries. Without an explicit selection, Manual is preferred over Auto. Always check the ✓ indicator before running an Annual Review for a consultant.

**What is the difference between "Include", "Aggregate", and "Exclude" in Section 4A?**
These control how each project row appears in the generated Feedback Form document. **Include** keeps the row as-is. **Exclude** drops it entirely (use for internal overhead or data errors). **Aggregate** merges the row with all other Aggregate rows into a single "Other Projects" line, which is useful for grouping small-contribution projects into one summary entry. The default is Aggregate for projects under 2 % of total fees, and Include for the rest. Decisions are saved and reload on future visits.

**How is the Bonus Amount calculated?**
Bonus Amount = **Starting Salary × Total Bonus %**, where Total Bonus % = Productivity Bonus % + Objective Bonus %. The bonus is applied to the consultant's salary *before* the year's raise, not to the post-raise updated salary.

**The performance score scale changed — what happened to existing scores above 4.0?**
Section 2 inputs are now capped at 4.0 (matching the 1–4 scale on the Feedback Form template). Any previously saved scores above 4.0 will display at 4.0 in the input field. If you have historical scores entered on the old 1–5 scale, review and re-enter them on the 1–4 scale for consistency.
