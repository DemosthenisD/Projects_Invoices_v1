# InvoiceApp — Release Notes

---

## V1.2 — Pipeline prospect workflow + Avg Annual Rate for bonus calculation (May 2026)

> **Updates on 15 May 2026** — Two major features plus a comprehensive documentation overhaul.
>
> **(1) Pipeline prospect workflow:** Prospects can now be added directly to the Pipeline / CRM page with minimal information (company name, opportunity name, description, country, budgets, probability) — no client record, project, or billing codes required. A "Convert to Project →" action navigates to Add New Project with the prospect's details pre-filled, and links the pipeline entry back to the new project on save (stage advances to Active automatically). Standalone prospects can also be deleted from the Prospect Actions section. Previously, pipeline entries could only be created by setting up a full client → project → codes chain first.
>
> **(2) Avg Annual Rate for bonus calculation:** A new `avg_annual_rate` field on `billing_basis` stores the weighted average billing rate for the year, computed as `SUM(non_z_charges) / SUM(non_z_hours)` from time entries. This is more accurate than a single `hourly_rate` snapshot when a consultant's rate changed during the year (e.g. €100/hr for H1 and €120/hr for H2 → weighted avg ≈ €110/hr). The Billing Basis Auto tab now shows a monthly rate breakdown table per consultant and pre-fills the Avg Annual Rate input from the computed weighted average. The Manual Entry tab also includes an Avg Annual Rate column. The Productivity Bonus % calculation in both Billing Basis (Page 11) and Annual Review (Page 13) uses Avg Annual Rate when set, falling back to Hourly Rate otherwise.
>
> **(3) Documentation overhaul:** USER_MANUAL.md restructured with a new **How To** section containing step-by-step guides for all major activities (issue invoice, record payment, add prospect, convert prospect, import time charges, prepare billing basis, run annual review, generate feedback form, back up data, fix data errors). TECHNICAL.md updated with the revised pipeline and billing_basis table schemas and new DB function reference. The in-app How to Use page (Page — How to Use) updated with the same How To section and refreshed Page 6 and Page 11 descriptions.

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`pipeline`** — table recreated with: `project_id` changed from UNIQUE NOT NULL to nullable (NULL for standalone prospects); new columns `is_prospect INTEGER NOT NULL DEFAULT 0`, `company_name TEXT`, `prospect_name TEXT`, `description TEXT`, `budget_min REAL`, `budget_est REAL`, `budget_max REAL`, `probability REAL`, `opportunity_country TEXT`. Partial unique index `uidx_pipeline_project ON pipeline(project_id) WHERE project_id IS NOT NULL` replaces the old column-level UNIQUE constraint. Existing rows migrated with `is_prospect=0`.
- **`billing_basis`** — added `avg_annual_rate REAL NOT NULL DEFAULT 0.0` between `hourly_rate` and `notes`.

### New DB Functions

- `add_prospect(company_name, prospect_name, description, country, stage, value, budget_min, budget_est, budget_max, probability, notes)` — inserts a standalone prospect row; returns `lastrowid`.
- `update_prospect(pipeline_id, ...)` — updates a prospect row in-place (`WHERE id=? AND is_prospect=1`).
- `convert_prospect_to_project(pipeline_id, project_id)` — links a prospect to a real project; clears prospect fields; advances stage to Active if currently Prospect.
- `delete_prospect(pipeline_id)` — deletes `WHERE id=? AND is_prospect=1`.
- `get_monthly_billing_rate_breakdown(emp_nbr, year)` — per-period breakdown of `non_z_hours`, `non_z_charges`, and implied `avg_nonz_rate`. Used to compute the weighted Avg Annual Rate.

### Updated DB Functions

- `get_pipeline()` — LEFT JOIN instead of INNER JOIN; CASE expressions for `display_client`, `display_project`, `country` unified columns across prospect and linked-project rows; includes all new prospect columns.
- `upsert_pipeline()` — rewritten as explicit SELECT → then INSERT or UPDATE (avoids `ON CONFLICT` limitation with partial unique indexes). Now includes `opportunity_country` parameter.
- `upsert_billing_basis()` — now includes `avg_annual_rate` parameter; included in both INSERT and UPDATE.

### Model Changes

- **`PipelineEntry`** dataclass (`shared/models.py`) — added `is_prospect`, `company_name`, `prospect_name`, `description` fields.
- **`BillingBasis`** dataclass (`shared/models.py`) — added `avg_annual_rate: float = 0.0` between `hourly_rate` and `notes`.

### Page Changes

- **Page 6 — Pipeline / CRM:** Add Prospect expander at top (minimal fields — no client/project required). Bootstrap loop scoped to non-null `project_id` rows only. Inline editor: `_is_prospect` checkbox (read-only) discriminates row type; save logic branches to `update_prospect()` vs `upsert_pipeline()` accordingly. Prospect Actions section at bottom: Convert to Project (sets session state + `st.switch_page` to Page 4), Delete Prospect. Filters now use unified `display_client` and `country` columns.
- **Page 4 — Add New Project:** Reads `_convert_pipeline_id`, `_convert_company_name`, `_convert_description`, `_convert_prospect_name` from session state (set by Pipeline / CRM convert action). Pre-fills Client name, Project name, and Description fields. After successful import, calls `convert_prospect_to_project()` to link the pipeline entry. Conversion banner shown when arriving via the convert workflow.
- **Page 11 — Billing Basis:** Auto tab: `get_monthly_billing_rate_breakdown()` called per consultant; monthly breakdown shown in expander; Avg Annual Rate input pre-filled from weighted average; both Avg Annual Rate and Hourly Rate saved via `upsert_billing_basis()`. `_derive()` updated: uses `avg_annual_rate` when > 0, else falls back to `hourly_rate`; new output fields `Rate Used €/hr` and `Rate Source`. Manual Entry tab: `Avg Annual Rate €/hr` column added to editor and save. Saved Basis tab: `Avg Rate €/hr` and `Rate €/hr` columns added; `_derive()` called with both rates. Excel export: `avg_annual_rate`, Rate Used, Rate Source columns included.
- **Page 13 — Annual Review:** `_productivity_bonus()` updated to prefer `avg_annual_rate` over `hourly_rate`; guard condition updated to allow either rate being set. Summary display and Excel export show the effective rate used.

---

## V1.1 — Billing Basis dual-source, Annual Review project breakdown fixes, Teams column (May 2026)

> **Updates on 13 May 2026** — Six targeted improvements across Billing Basis (Page 11) and Annual Review (Page 14).
>
> **(1) Billing Basis dual-source storage:** The `billing_basis` table now stores Auto (time_tracking) and Manual entries as two independent rows per consultant per year, keyed by `source`. Previously an upsert on `(emp_nbr, year)` would overwrite whichever source was saved first. The corrected constraint is `UNIQUE(emp_nbr, year, source)`, ensuring both sources coexist. The Manual Entry tab pre-populates only from existing `manual` rows (zeros for consultants with no manual entry).
>
> **(2) Explicit billing basis source selection for Annual Review:** A new `is_preferred` flag (`INTEGER DEFAULT 0`) on `billing_basis` lets you designate which source (Auto or Manual) the Annual Review uses for each consultant when both are saved. The Saved Basis tab shows a ✓ in the **Active for Review** column next to the active source. A radio-button form at the bottom of the Saved Basis tab lists every consultant with dual entries and lets you set the preferred source with a single click. All Annual Review queries now order by `is_preferred DESC` so the explicit choice always wins.
>
> **(3) Annual Review project breakdown — correct colleague filtering:** The colleagues list for each project in Section 4A was incorrectly showing all consultants billing to any suffix of the same client code. The join now uses `project_id` combined with a `project_codes` subquery validation (`te2.project_code_id IN (SELECT id FROM project_codes WHERE project_id = te.project_id)`), so only consultants billing to codes that actually belong to the specific project are included. Consultants billing to the same client code under a different project are excluded.
>
> **(4) Colleague names as "Firstname Lastname":** Names in the Colleagues involved column are now displayed as "Firstname Lastname" (e.g. "Konstantinos Savva") instead of "Lastname, Firstname". A `_flip_name()` helper converts the stored format at display time.
>
> **(5) Self-exclusion fix:** The reviewed consultant's own name is now reliably excluded from the colleagues list. The fix uses a ` | ` separator in `GROUP_CONCAT` (replacing `,`) so that "Lastname, Firstname" names are not fragmented when parsed, enabling exact-match exclusion.
>
> **(6) Teams involved column:** Each project row in Section 4A now shows a **Teams involved** field alongside Colleagues involved. Teams are derived by joining `consultant_groups` — if three ICEE consultants worked on a project, "ICEE" appears only once. The generated Word Feedback Form document uses the Teams column (not the individual colleagues list), giving a cleaner team-level view. Both columns are editable before generating.

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`billing_basis`** — unique constraint changed from `(emp_nbr, year)` to `(emp_nbr, year, source)`. New column `is_preferred INTEGER NOT NULL DEFAULT 0`. Existing rows migrated: if only one row exists for a consultant/year, it is set to `is_preferred=1` automatically.

### New DB Functions

- `set_billing_basis_preferred(emp_nbr, year, source)` — clears `is_preferred` for all rows matching `(emp_nbr, year)`, then sets `is_preferred=1` for the specified source.

### Updated DB Functions

- `upsert_billing_basis()` — ON CONFLICT clause updated to `(emp_nbr, year, source)`; `source` removed from UPDATE set (it is part of the key, not updatable).
- `get_billing_basis_year()` — uses `is_preferred DESC` ordering to return the active source for each consultant.
- `get_billing_basis()` — same ordering fix for single-consultant lookup.
- `get_consultant_project_hours(consultant, year)` — result dict now includes `"teams"` field (pipe-separated team names); colleague join revised to `project_id + project_codes` subquery validation; uses ` | ` separator in GROUP_CONCAT via a DISTINCT subquery to comply with SQLite restrictions.

### Model Changes

- **`BillingBasis`** dataclass (`shared/models.py`) — added `is_preferred: int = 0`.

### Page Changes

- **Page 11 — Billing Basis:** Manual Entry tab pre-populates from `manual` rows only; info banner clarifies source isolation. Saved Basis tab: shows both sources per consultant; Active for Review ✓ indicator; explicit source selection form for consultants with dual entries.
- **Page 14 — Annual Review:** `_flip_name()` helper converts display names to "Firstname Lastname". `_unique_colleagues()` helper splits on ` | ` and excludes the reviewed consultant. Project breakdown layout expanded to 7 columns to include the Teams involved field. Word export uses teams (not colleagues). Aggregate Other Projects row merges both colleague and team lists with deduplication.

---

## Sprint 16 — TOTAL row pinning, Section 4A project toggles, employee status & UX fixes (May 2026)

> **Updates on 7–8 May 2026** — Six improvements across five pages.
>
> **(1) Pinned TOTAL rows (all tables):** All sortable data tables now show the TOTAL row permanently fixed at the bottom regardless of which column you sort by. Previously the TOTAL row would re-sort along with the data rows. Implemented via a shared `dataframe_with_total()` helper in `shared/ui.py` — renders data in one sortable `st.dataframe` and the TOTAL in a second fixed `st.dataframe` immediately below with blank column headers so it reads as a footer. Applied to every table in Pages 8 (Project Overview), 9 (Time Tracking — all five sub-tables), and 11 (Billing Basis — all seven view modes).
>
> **(2) Section 4A — Include / Aggregate / Exclude project toggles:** Each project row in the Feedback Form Export project breakdown now has a three-way action selector. *Include* — row appears as-is in the final document. *Exclude* — row is dropped entirely (e.g. non-billable or erroneous entries). *Aggregate* — row is merged with all other Aggregate rows into a single **Other Projects** line showing summed hours % and fees %. Default is Aggregate when the project represents < 2 % of the consultant's total fees for the year, Include otherwise. The row now also shows **Fees %** alongside Hours %. Decisions are persisted as JSON in the `review_feedback` table (area `_project_rows`) and reload on subsequent visits. The colleagues list on the Other Projects aggregate row is automatically deduplicated across all merged rows.
>
> **(3) Local consultant Active / Inactive status:** A new `status` column (Active / Inactive, default Active) is added to the `consultant_groups` table. Existing records migrate to Active automatically on startup. In the Consultant Groups tab (Page 9), Local consultants now show a Status selector in their expander; the expander title displays the current status for quick scanning. ICEE and Other consultants are unaffected. The Annual Review page now only shows Local + Active consultants in the consultant dropdown — Local/Inactive and all non-Local groups are excluded, replacing the previous Group radio.
>
> **(4) Bonus amount base corrected:** Bonus Amount is now calculated as **Starting Salary × Total Bonus %** (not Updated Salary, which incorrectly double-counted the raise). Fixed in the live preview, Section 3 summary card, and Excel export.
>
> **(5) Proposed Rate column renamed:** "Proposed Rate €/hr" → "Proposed Rate for following year €/hr" in both the Salary History table and the Billing Rates by Year table on the Consultant Profiles page, making clear that this rate applies to the next year not the current one.
>
> **(6) Billing Basis Auto tab group filter:** The Group radio at the top of the Billing Basis page (Page 11) now correctly filters the Auto tab — the time-tracking summary table, the rate entry inputs, and the Save operation all operate on the selected group only. Previously the filter was ignored by the Auto tab.
>
> **(7) Colleagues deduplication and self-exclusion:** The colleagues list in Section 4A is now deduplicated at the individual-name level before writing to the Word document. The reviewed consultant's own name is also removed from the list automatically. Both fixes apply to individual project rows and to the aggregated Other Projects row.

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`consultant_groups`** — added `status TEXT NOT NULL DEFAULT 'Active'`. Existing rows migrated to Active.

### New Shared Module

- **`shared/ui.py`** — new module. Contains `dataframe_with_total(df, total_dict, fmt, na_rep)`: renders a sortable data table followed by a pinned TOTAL footer row. Used by Pages 8, 9, and 11.

### DB Function Changes

- `get_consultant_groups()` — now includes `status` in the SELECT result.
- `upsert_consultant_group(consultant, group_name, emp_nbr, status)` — new `status` parameter (None = leave unchanged for existing rows).
- `get_consultant_project_hours(consultant, year)` — extended to return `fees` (total billable charges), `fees_pct` (share of total fees), and `hours_pct`. Now filters out internal clients (`client_type = 'internal'` and `client_code LIKE '0009%'`). Result ordered by fees descending (previously hours descending).

### Page Changes

- **Page 9 — Time Tracking (Consultant Groups tab):** Local consultants now show a Status (Active / Inactive) selector inside their expander, alongside Group and emp_nbr. Expander title shows current status in brackets.
- **Page 11 — Billing Basis (Auto tab):** Group filter now works correctly — filters display, rate inputs, and Save.
- **Page 12 — Consultant Profiles:** "Proposed Rate €/hr" renamed to "Proposed Rate for following year €/hr" in Salary History and Billing Rates by Year tables.
- **Page 13 — Annual Review:** Group radio removed. Consultant dropdown shows only Local + Active employees. Bonus Amount calculation corrected to use Starting Salary. Section 4A: Fees % column added; Include / Aggregate / Exclude toggle per row; decisions persisted; Other Projects aggregate row with deduplicated colleagues; reviewed consultant excluded from colleagues lists.

---

## Sprint 15 — Feedback Form Export (May 2026)

> **Updates on 7 May 2026** — New Section 4 added to Page 13 (Annual Review): generates a filled ICEE Feedback Form Word document per consultant per year. (1) **Project Breakdown (Table 2):** auto-filled from time entries — one row per project billed in the review year showing client, project name + description, colleagues (all other consultants who billed to the same project that year, editable before generating), and hours %. Row count is dynamic — one row per project worked on, not a fixed six. (2) **Assessment Comments (Table 3):** per-performance-area editable text fields for "Comments from Feedback Provider" and "Development ideas"; the computed group-average score (from Section 2) fills the Score column automatically. Comments are persisted in a new `review_feedback` DB table and reload on subsequent visits. (3) **Other Comments (Table 4):** free-text narrative persisted in the same table. (4) **Save & Generate button:** saves all comments to DB, fills the Word template (background info from Consultant Profiles, dynamic project table, assessment scores + comments, other narrative), writes to `exports/feedback_<Name>_<Year>.docx`, and offers a download button. (5) **Score scale:** Section 2 performance score inputs changed from 1–5 → 1–4 to match the template's legend (1=Significant underperformance … 4=Exceeds expectations). (6) **Docs:** USER_MANUAL.md updated with full Section 4 workflow documentation and four new FAQ entries.

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`review_feedback`** — new table: `id`, `emp_nbr`, `year`, `area` (Professionalism / Management / Social Skills / Other), `comments`, `development_ideas`, `created_at`. `UNIQUE(emp_nbr, year, area)`.

### New DB Functions

- `get_review_feedback(emp_nbr, year)` — returns a dict keyed by area with `ReviewFeedback` objects.
- `upsert_review_feedback(emp_nbr, year, area, comments, development_ideas)` — insert or overwrite a feedback record for one area.
- `get_consultant_project_hours(consultant, year)` — returns a list of dicts (one per project billed by the consultant in that year): `client`, `project_name`, `description`, `hours`, `hours_pct`, `colleagues` (comma-separated names of other consultants on the same project).

### New Model

- **`ReviewFeedback`** dataclass added to `shared/models.py`.

### Page Changes

- **Page 13 — Annual Review:** Section 4 added (Feedback Form Export). Score inputs in Section 2 capped at 4.0. Three new imports: `get_review_feedback`, `upsert_review_feedback`, `get_consultant_project_hours`. Helper `_generate_feedback_docx()` added — opens `template_other/Feedback Form_2025 DRAFT Example.docx`, fills all five tables, returns bytes + filename.

---

## Sprint 14 — Filters, Year-by-Year Views, Billing Basis View Modes & UX Polish (May 2026)

> **Updates on 7 May 2026** — Major analysis and reporting improvements across five pages. (1) **Page 8 — Project Overview:** six filter controls (Client, Status, Source, Type, Consultant Group, Consultant); sorting on amount columns fixed (values kept numeric, displayed with comma thousands separator via pandas Styler); TOTAL row on all tables; Year-by-Year sub-table includes TOTAL column and TOTAL row. (2) **Page 9 — Time Tracking:** Rollup gains Client Type and Country filters; Year-by-Year toggle pivots codes × years with subtotals; Breakdown by Consultant section with Group radio filter; Team Summary adds "By Consultant & Project" drill-down table; Consultant Groups tab gains Group radio so only the selected group's consultants are shown. (3) **Page 11 — Billing Basis:** Saved Basis tab gains Group filter radio and a "Re-arrange to Show By" selector with 7 view modes (By Consultant, By Group, By Consultant → Project, By Project, By Project → Group, By Project → Consultant, By Project → Group → Consultant). (4) **Page 12 — Consultant Profiles:** Delete a Year Record section added to Salary History tab. (5) **Page 13 — Annual Review:** Group radio added before the consultant selector (defaults to Local). (6) **General:** comma thousands separator applied consistently across all amount columns in all tables; TOTAL subtotal rows on all amount tables. (7) **CSV Import:** encoding fallback chain (UTF-8-BOM → UTF-8 → Windows-1252 → Latin-1) fixes import failures for Excel-exported files containing special characters (e.g. en-dashes). (8) **Bug fix:** Team Summary "By Consultant" was incorrectly placing consultants with multiple historical employee numbers under "Other" — fixed by joining `consultant_groups` on consultant name instead of employee number. (9) **Docs:** USER_MANUAL.md fully rewritten with correct sidebar page numbers 1–14 and all new features documented.

### DB Function Changes

- `get_all_projects_overview()` — extended to return `client_type`, `country`, `groups_with_hours` (comma-separated list of consultant groups with billed hours), and `consultants_with_hours` (comma-separated list of consultant names) per project. Uses `GROUP_CONCAT(DISTINCT ...)` aggregation in a LEFT JOIN subquery.
- `get_team_time_summary()` — JOIN to `consultant_groups` changed from `cg.emp_nbr = te.emp_nbr` to `cg.consultant = te.consultant`; `te.emp_nbr` removed from GROUP BY. Fixes incorrect group assignment for consultants with multiple historical employee numbers.
- New `get_team_time_summary_by_project(period_from, period_to, group_names)` — consultant × project breakdown; joins by consultant name; orders by consultant then billable charges descending.
- New `get_time_summary_by_year(project_id)` — per-code per-year pivot data for the Year-by-Year Rollup view.
- New `get_billing_basis_summary(year)` — per consultant per project time charges for the project-centric Billing Basis view modes; joins by consultant name.

### Page Changes

- **Page 8 — Project Overview:** Filters expanded from 3 to 6 (added Type, Consultant Group, Consultant multiselects). Amount columns use `pandas Styler.format("{:,.0f}")` so sorting is correct and display uses comma thousands separator. TOTAL row on main table and Year-by-Year sub-tables. "Type" column added to summary view.
- **Page 9 — Time Tracking:** Rollup — 6-control filter row (Client Type, Country, Client, Project, Period From, Period To); By Code vs Year-by-Year view toggle; Breakdown by Consultant section with Group radio. Team Summary — By Consultant & Project table added; all tables have TOTAL rows and comma-formatted amounts. Consultant Groups — Group radio added at top; consultants shown within selected group only.
- **Page 11 — Billing Basis:** Saved Basis tab — Group filter radio; "Re-arrange to Show By" selectbox (7 modes); all views have TOTAL rows and comma-formatted amounts; project-centric views use time-entry amounts (noted in UI). Helper `_sv_fmt()` applies consistent Styler formatting; helper `_totals_sv()` builds TOTAL rows.
- **Page 12 — Consultant Profiles:** "Delete a Year Record" section added below the Add/Edit form in the Salary History tab.
- **Page 13 — Annual Review:** Group radio added above the consultant selectbox; filters the consultant list to the selected group (defaults to Local).
- **Page 14 — Data Tables:** No functional change; page number updated in docstring to match sidebar (was referenced as Page 8 in earlier sprints).
- **All pages:** Page number in module docstrings aligned to sidebar numbering (1–14).

### Docs

- **USER_MANUAL.md** — fully rewritten: corrected page numbers throughout (sidebar 1–14); added Page 13 Annual Review section (was missing); documented all new features for Pages 8, 9, 11, 12, 13; added FAQ entries for CSV encoding, sorting fix, and Billing Basis project-view data source.

---

## Sprint 13 — Credit Notes, Partial Payments, Sorting & Group Filters (May 2026)

> **Updates on 6 May 2026** — Eight improvements across five pages: (1) Generate Invoice now supports **Credit Notes** — a toggle switches document type; credit notes store a negative amount and share the same sequential counter as invoices; an optional "Credits invoice" reference field links to the original. (2) Invoice Log now has **sortable columns** (Date, Invoice ID, Amount, Client, Status, Type) with ascending/descending toggle. (3) Invoice Log gains a **Balance €** column showing gross minus payments received; legacy paid rows without payment records show `—`. (4) **Partial payments** supported — a `payments` table tracks each receipt; the log shows `✓ Pay` (full), `± Part.` (partial), and `↩ Reset` buttons; payment history shown as captions below each row. (5) Invoice filename fix — `/` in Invoice No (e.g. `1/2026`) was causing a `FileNotFoundError`; replaced with `-` in the generated filename. (6) Budget aggregation bug fixed — `SUM(DISTINCT)` on project codes with equal budgets was undercounting; replaced with a subquery aggregate. (7) **Sync completed project budgets** admin action added to Clients & Projects → Projects tab — auto-distributes total invoiced amount equally across any zero-budget codes for Completed projects. (8) **Add New Project** "Create new client" now includes Client Type and Country fields; project codes are optional for external and internal clients.

> **Group filter for Annual Review pages (6 May 2026):** Billing Basis and Consultant Profiles now have a Group radio (Local / ICEE / Other / All) defaulting to Local, so the annual review workflow stays focused on the local team.

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`invoices`** — added `type TEXT DEFAULT 'Invoice'` and `related_invoice_number TEXT DEFAULT ''`.
- **`payments`** — new table: `id`, `invoice_id`, `amount REAL`, `date TEXT`, `note TEXT DEFAULT ''`, `created_at TEXT`. Tracks individual payment receipts per invoice.

### New / Updated DB Functions

- `add_invoice()` — new `doc_type` and `related_invoice_number` parameters; stores `type` and `related_invoice_number` in `invoices`.
- `bulk_import_invoices()` — extended to read `type` and `related_invoice_number` columns from the upload template.
- `get_invoices()` — now JOINs a `payments` aggregate subquery to populate `total_paid` on each Invoice object; returns `type` and `related_invoice_number`.
- `add_payment(invoice_id, amount, date, note)` — new; inserts a payment row and calls `_recompute_invoice_status()`.
- `get_payments(invoice_id)` — new; returns all payment rows for an invoice.
- `delete_payments(invoice_id)` — new; removes all payment rows and resets invoice status to `outstanding`.
- `_recompute_invoice_status(invoice_id, conn)` — internal helper; derives `outstanding / partial / paid` from gross vs `SUM(payments.amount)` and writes back `status` and `paid_date`.
- `get_projects_with_summary()` — fixed `SUM(DISTINCT pc.budget_amount)` bug; now uses a subquery aggregate so codes with equal budgets are not collapsed.
- `sync_completed_project_budgets()` — new; finds Completed projects whose codes all have zero budget but a positive invoiced amount; sets each code's budget to `invoiced ÷ code count`.

### Page Changes

- **Page 0 — Generate Invoice:** Document type toggle (Invoice / Credit Note) added in the header row. Credit Note mode: positive amount entered by user; stored as negative. Optional "Credits invoice No" text input (reference only, not validated). Invoice No format `ID/YYYY`; filename uses `ID-YYYY` to avoid OS path separator issue.
- **Page 2 — Invoice Log:** Sort controls (selectbox + radio) above the table. New columns: Type (📄 / 🔄), Inv No (`ID/YYYY`), Balance €. Action column split into `✓` (full pay) and `±` (partial toggle) buttons; `↩ Reset` button for paid/partial invoices. Inline partial-payment form (amount, date, note) toggled per row via session state. Payment history shown as captions below each row. Related invoice caption for credit notes. Excel export extended with Type, Related Invoice No, Paid (€), Balance (€) columns. Bulk upload template extended with `type` (dropdown) and `related_invoice_number` columns.
- **Page 3 — Clients & Projects — Projects tab:** "Admin: sync completed project budgets" expander added below the totals bar; one-click button shows count of codes updated.
- **Page 11 — Add New Project:** "Create new client" mode now includes Client Type (managed / external / internal) and Country fields. Validation: project codes required only when client type is managed.
- **Page 12 — Billing Basis:** Group radio (All / Local / ICEE / Other) defaults to Local; Manual Entry tab filters consultant list by selected group.
- **Page 13 — Consultant Profiles:** Group radio (All / Local / ICEE / Other) defaults to Local; consultant selectbox filters to the chosen group.

---

## Sprint 12 — Filters, Pipeline Dates, Completed-Project Invoicing, Bulk Allocations (May 2026)

> **Updates on 4 May 2026** — Six improvements across four pages: (1) Generate Invoice now has an "Include completed projects" checkbox so invoices can be raised against completed projects (e.g. ERGO / IFRS17-P1). (2) Clients tab gains name / type / country filter row and a labelled "Status" column header with badge legend. (3) Projects tab gains a Country column, client-type filter, and a totals bar (Budget / Billable / Write-offs / Invoiced) for the filtered selection. (4) Pipeline/CRM adds Country and Client type filter controls, plus two new read-only date columns: "In Pipeline" (date first added) and "In Stage Since" (auto-updated when stage changes on Save). (5) Bulk Upload template extended with a "Project Codes Reference" sheet and an "Allocations" sheet — up to 4 project-code / amount pairs per invoice with cascading dropdown and auto-computed code IDs. (6) Import logic reads the Allocations sheet and writes to `invoice_allocations` after each invoice is inserted.

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`pipeline`** — added `date_entered_pipeline TEXT DEFAULT ''` and `date_entered_stage TEXT DEFAULT ''`. Existing rows back-filled from `updated_at`.

### New / Updated DB Functions

- `get_pipeline()` — now includes `country`, `client_type`, `date_entered_pipeline`, `date_entered_stage`.
- `upsert_pipeline()` — sets `date_entered_pipeline` on first INSERT; updates `date_entered_stage` only when `stage` changes.
- `get_projects_with_summary()` — now includes `client_type` and `client_country`.
- `get_all_project_codes_with_context()` — new; returns all active project codes joined with project and client info (used for bulk upload template).
- `get_invoice_by_number(invoice_number)` — new; looks up a single invoice by number (used by allocation import).

### Page Changes

- **Page 0 — Generate Invoice:** "Include completed projects" checkbox (default off) placed beside the mode toggle. When checked, Active + On Hold + Completed projects are shown.
- **Page 2 — Clients & Projects — Clients tab:** Unnamed circle column renamed to "Status"; badge legend caption added. Filter row (name search, Type multiselect, Country multiselect) added above the table.
- **Page 2 — Clients & Projects — Projects tab:** Country column added. "Status" replaces unnamed circle column. Client type multiselect filter added. Totals bar (4 metrics) shown below filtered table.
- **Page 3 — Pipeline / CRM:** Filter bar expanded to 4 controls: Stage, Client, Country (multiselect), Client type (multiselect). Table adds read-only Country, "In Pipeline", "In Stage Since" columns.
- **Page 1 — Invoice Log — Bulk Upload:** Template now has 6 sheets — Invoices, Client Reference, Project Reference, Address Reference, **Project Codes Reference** (all active codes), **Allocations** (up to 4 code/amount pairs per invoice). Import processes Allocations sheet automatically after inserting invoices.

---

## Sprint 11 — Status Tracking, Tabular Clients, Pipeline Inline Edit (April 2026)

> **Updates on 30 Apr 2026** — Four UX improvements delivered: (1) Clients tab now shows a tabular summary with Country, Name for invoices, project/code counts — a selectbox-based edit panel replaces accordion expanders. (2) Invoice Log gains Status filter, Mark Paid / Outstanding action buttons, and a Bulk Upload tab with a downloadable Excel template. (3) Pipeline / CRM replaced per-project expanders with a single inline `st.data_editor` grid — edit Stage, Value, budget fields, Probability, and Notes for all projects at once, then save in one click. (4) Completing a project now auto-closes all its active project codes (sets status = Completed, date_end = today) with a confirmation count.

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`clients`** — added `client_type TEXT DEFAULT 'managed'` and `country TEXT DEFAULT ''`.
- **`invoices`** — added `status TEXT DEFAULT 'outstanding'` and `paid_date TEXT DEFAULT ''`.
- **`projects`** — added `date_start TEXT DEFAULT ''`.

### New / Updated DB Functions

- `get_clients()` — now includes `country` in SELECT.
- `get_clients_with_counts()` — new; returns client rows joined with total_projects, active_projects, active_codes counts for the tabular overview.
- `add_client()` / `update_client()` — new `country` parameter.
- `get_invoices()` — now includes `status`, `paid_date`; new `status` filter parameter.
- `update_invoice_status(invoice_id, status, paid_date)` — new; used by Mark Paid / Outstanding buttons.
- `bulk_import_invoices(records)` — new; inserts from upload template, skips duplicates, returns `{inserted, skipped, errors}`.
- `update_project()` — now auto-closes active project codes when status changes to Completed; returns count of codes closed.

### Page Changes

- **Page 1 — Invoice Log:** Status filter, status badge column, Mark Paid / Outstanding per row, Outstanding summary metric, Bulk Upload tab (template download + file uploader + import button). Excel export now includes Status and Paid Date columns.
- **Page 2 — Clients & Projects:** Clients tab replaced accordion expanders with `st.dataframe` summary table (Name, Code, Type badge, Country, Name for invoices, Projects, Active projects, Active codes); "Edit / delete a client" selectbox panel added below. Project cards now also show date range (From / To) per project code row.
- **Page 3 — Pipeline / CRM:** Replaced per-project expander forms with a single `st.data_editor` table; summary metrics retained; probability-weighted forecast shown when budget fields are populated; one Save button persists all changes at once.

### .gitignore

- `DB_Tbls_Structure/*.csv` and `DB_Tbls_Structure/*.xlsx` — all data exports from the DB_Tbls_Structure folder are now excluded. The `data_dependencies.md` structure file is still committed.

---

## Numbered Pages — Launch shortcut → ready to test!

> **Updates on 24 Apr 2026 (UX)** — Sidebar now grouped into 6 sections (Invoices, Clients & Projects, Pipeline & Reporting, Time & Billing, Annual Review, Admin) with pages numbered 1–14. How to Use stays pinned at the top ungrouped. One-click `launch_app.bat` added — double-click to start the app and auto-open the browser. Currency fixed to € across all Annual Review pages.

---

## Annual Review features built

> **Updates on 24 Apr 2026** — Sprint 10 delivered: annual consultant review and bonus-calculation module (pages 12–14). New billing basis page aggregates time-charge data per consultant and computes productivity bonus %; new consultant profiles page stores employment details and salary history year-by-year; new annual review page combines billing basis, salary chain, and performance scoring (3 groups, 19 items) with Excel export. Four new DB tables added. Sensitive HR and billing files excluded from git; `SENSITIVE_FILES.md` added as a local navigation guide.

> **Updates on 23 Apr 2026** — Sprint 9 delivered: project-code date-range routing (suffix reuse across projects), `invoice_allocations` table with optional pro-rata split on invoice generation, `template_used` column rename for clarity, `client_code` integrity enforced at write time, and a new flat "Add New Project" intake page (page 11). All schema changes migrate automatically on startup; documentation fully refreshed.

---

## Sprint 10 — Bonus Calculation & Annual Review (April 2026)

### New Pages

- **Page 12 — Billing Basis:** Annual billing summary per consultant used as the basis for productivity-bonus calculation. Two input modes: Auto (aggregates from `time_entries` + `write_offs` for the year) or Manual (spreadsheet-style table matching the bonus template's Sheet5 layout: Billed / Capped Paid Prebill / Capped Unpaid Prebill / Charged Off / Paid / Unbilled). Derived columns computed on the fly: Grand Total, Basis for Bonus (Grand Total − Charged Off), Equivalent Hours (Basis ÷ Hourly Rate), Productivity Bonus % (`(Hrs − 800) / 40 × 1%`). Save persists to `billing_basis` table.
- **Page 13 — Consultant Profiles:** Extended master data per consultant. Profile tab: employment date, prior experience, Milliman professional status, external level, languages, tools. Salary History tab: year-by-year salary chain — starting salary carried forward from prior year's updated salary, exams passed, exam raise per exam (resettable per year), other/discretionary raise, effective date, objective bonus %, bonus paid (historical), proposed billing rate. Rates tab: billing rates by year.
- **Page 14 — Annual Review:** Per-consultant annual assessment form. Section 1 (Compensation): auto-pulls productivity bonus % from billing basis, computes salary chain and bonus amount live. Section 2 (Performance Scores): three groups — Professionalism (7 items), Management (6 items, shown for all but set to 0 for non-managers), Social Skills (5 items) — with historical comparison against 3 prior years. Section 3 (Summary): formatted review card + Excel export (Summary sheet + Performance Scores sheet).

### New DB Tables (created automatically on startup)

- **`consultant_profiles`** — employment date, prior experience, Milliman status, external level, languages, tools. Linked to `consultant_groups` by `emp_nbr`.
- **`annual_salary_history`** — one row per consultant per year: starting salary, exams, exam raise per exam, other raise, effective date, objective bonus %, bonus paid, proposed rate.
- **`billing_basis`** — one row per consultant per year: six billing-category amounts, hourly rate; source (`time_tracking` or `manual`).
- **`review_scores`** — one row per consultant per year per group per item: score value. Unique on `(emp_nbr, year, score_group, item_name)`.

### Sensitive Data Handling

- `Review/`, `data/*.csv`, `data/*.xlsx`, `data/*.xlsm` added to `.gitignore` — HR compensation data, bonus templates, and time-charge CSVs are excluded from git.
- `SENSITIVE_FILES.md` added at repo root: committed navigation guide listing local machine paths to all excluded data files.

---

## Sprint 9 — Schema Integrity & Project Intake (April 2026)

### DB Schema Changes (non-breaking, migrated automatically on startup)

- **`project_codes`** — added `date_start TEXT DEFAULT ''` and `date_end TEXT DEFAULT ''`. Unique constraint changed from `(client_code, client_suffix)` to `(client_code, client_suffix, date_start)`, allowing the same suffix to be reused for a later project by setting a start date on the new code.
- **`invoices`** — column `template` renamed to `template_used` to make clear it records which template was actually used at generation time (historical record), distinct from `projects.template` which is the default for future invoices.
- **`invoice_allocations`** — new table: splits an invoice's net amount across project codes. Created automatically using pro-rata by budget if no manual allocation is provided.
- **`projects.template`** — stale legacy values (`Template-1`, `Template-2`, `template1`) normalised to current filenames (`template1_v3`, `template2_v3`) in all existing rows.

### New Features

- **Project Code date-range routing:** Time entries are now routed to the correct project code based on their period date when a suffix has been reused. Entries before a code's `date_start` stay with the original project; entries on or after route to the new one.
- **client_code integrity enforced:** `add_project_code()` now derives `client_code` from the project's parent client at write time. It is no longer a free-text user input, closing the data-integrity gap where the stored code could differ from the actual client code.
- **Invoice allocation to project codes:** When generating an invoice, an optional "Project Code Allocation" section lets you split the net amount across the project's active codes. If left blank, the system computes pro-rata weights from each code's budget (equal split if all budgets are zero). Allocations are stored in `invoice_allocations` and can be updated after the fact.
- **Page 11 — Add New Project:** New flat intake page. Fill in client, project, and any number of project code rows in a single form. A single "Import to Database" button creates only missing records — safe to re-run.

### UI Updates

- **Page 6 — Project Codes:** `client_code` input removed (shown as read-only info); Date Start and Date End fields added to add and edit forms; code label shows date range when set.
- **Page 0 — Generate Invoice:** "Project Code Allocation" expander added between the amount section and the Advanced section; shows pro-rata hints per code and validates that manual allocations balance to the invoice net amount.
- **Page 1 — How to Use:** Updated to reflect all new pages, fields, and workflows.

---

## Sprint 8 — Quick Wins & Bug Fixes (April 2026)

### Bug Fixes
- **BUG 1:** `get_invoices()` now accepts an optional `project_id` filter parameter (previously caused an error when called from the Time Tracking page).
- **BUG 2:** Write-off allocation preview no longer references an unset session state key; proportions are shown correctly without a broken amount preview.

### Improvements
- **SP 1:** Sidebar is now expanded by default on load — all pages are visible without needing to click.
- **SP 2:** Login form inputs now carry `autocomplete` attributes so browsers can offer saved credentials.
- **SP 3b:** Generate Invoice page now shows a caption clarifying that clicking the button saves the file to the `exports/` folder permanently; the Download button is optional.
- **SP 4b:** Invoice Log now displays a header row (Date | Invoice # | Client | Project | Net € | VAT € | Expenses € | File).
- **SP 4c:** Invoice Log now includes an **Expenses €** column.
- **SP 4d:** Invoice Log now shows a caption explaining that the PDF/DOCX button downloads from the local disk and may be unavailable if the file was moved.

---

## Sprint 7 — Project Codes, Time Tracking & Write-offs (April 2026)

### New Features
- **Page 5 — Project Codes:** Manage billing codes (`client_code` + `client_suffix`) per project. Per-code metrics: budget, billable charges, write-offs, remaining.
- **Page 6 — Time Tracking:** Import monthly time-charge CSV reports. View entries by batch, filter, and delete. Rollup tab shows project and per-code summaries.
- **Page 7 — Write-offs:** Record project-level (pro-rata) or ad-hoc write-offs. Log with reversal support.
- **Billing summary** added to each project card on Clients & Projects page (billable charges, invoiced, write-offs, remaining).

### Infrastructure
- `project_codes`, `time_entries`, and `write_offs` tables added to DB schema.
- `backend/db.py` extended with full CRUD for new tables, bulk import, and rollup queries.
- `shared/models.py` extended with `ProjectCode`, `TimeEntry`, and `WriteOff` dataclasses.
- `scripts/seed_from_csv.py`: one-time import of clients, projects, and project codes from NocoDb CSV exports.
- 19 new tests (29 total passing).

### PDF Fix
- Replaced ConvertAPI (cloud, requires network) with **docx2pdf** (local, drives Microsoft Word) + **LibreOffice headless** fallback. No network calls required.

---

## Sprint 6 — Polish & Tests (March 2026)

### Improvements
- Replaced `datetime.utcnow()` (deprecated) with `datetime.now(timezone.utc)`.
- Added comprehensive test suite: 10 tests covering clients, addresses, projects, invoices, and pipeline CRUD.
- Requirements file pinned with minimum versions.
- README updated with setup instructions.

---

## Sprint 5 — Pipeline / CRM (March 2026)

### New Features
- **Page 3 — Pipeline / CRM:** Track pipeline projects by stage (Prospect → Won/Lost) with value and notes.
- **Page 4 — Dashboard:** High-level metrics for invoiced total, VAT, and gross by year.

---

## Sprint 4 — Clients & Projects (February 2026)

### New Features
- **Page 2 — Clients & Projects:** Full client and project management with cascading expanders, add/edit/delete, and VAT/template assignment per project.
- Projects linked to addresses; multiple addresses per client supported.

---

## Sprint 3 — Invoice Log (February 2026)

### New Features
- **Page 1 — Invoice Log:** Filterable list of all invoices with per-row download and Excel export.
- Filters: Year, Client, Project, free-text search.

---

## Sprint 2 — Generate Invoice (January 2026)

### New Features
- **Page 0 — Generate Invoice:** Full invoice generation flow — client → project → amount/date → DOCX/PDF output.
- Template placeholder filling (handles tokens split across runs).
- Invoice number auto-suggestion (max per year + 1).
- Expenses section (net + VAT).

---

## Sprint 1 — Foundation (January 2026)

### Initial Setup
- Streamlit multi-page app structure (`frontend/App.py` + `pages/`).
- SQLite backend (`data/invoiceapp.db`) with `clients`, `addresses`, `projects`, `invoices`, and `pipeline` tables.
- Login wall with session state.
- Shared config via `.streamlit/secrets.toml`.
- Two invoice templates: `template1_v3.docx` (CY, 19% VAT) and `template2_v3.docx` (GR, 0% VAT).

---

## Upcoming

- **Sprint 9:** Documentation suite (this file, USER_MANUAL.md, TECHNICAL.md).
- **Sprint 10:** Invoice Log cascading filters; Generate Invoice project-first selection; Data Tables viewer page; Project Overview page; Pipeline tabular summary.
- **Sprint 11:** Pipeline min/max/est budget + probability forecasting; Consultant grouping (Local / ICEE / Other) with time-charge breakdown.
