"""
Page — How to Use.

Quick reference: grouped page summaries (Actions vs Views), edit guide, DB tips.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

st.title("How to Use")

# ------------------------------------------------------------------
# Documentation links
# ------------------------------------------------------------------

_docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs")

with st.container():
    st.caption("Full documentation is available as downloadable files below.")
    _doc_cols = st.columns(3)

    _manual_path = os.path.join(_docs_dir, "USER_MANUAL.md")
    if os.path.exists(_manual_path):
        with open(_manual_path, "rb") as _f:
            _doc_cols[0].download_button(
                "📄 User Manual",
                data=_f.read(),
                file_name="USER_MANUAL.md",
                mime="text/markdown",
                use_container_width=True,
            )

    _rn_path = os.path.join(_docs_dir, "RELEASE_NOTES.md")
    if os.path.exists(_rn_path):
        with open(_rn_path, "rb") as _f:
            _doc_cols[1].download_button(
                "📋 Release Notes",
                data=_f.read(),
                file_name="RELEASE_NOTES.md",
                mime="text/markdown",
                use_container_width=True,
            )

    _tech_path = os.path.join(_docs_dir, "TECHNICAL.md")
    if os.path.exists(_tech_path):
        with open(_tech_path, "rb") as _f:
            _doc_cols[2].download_button(
                "⚙️ Technical Reference",
                data=_f.read(),
                file_name="TECHNICAL.md",
                mime="text/markdown",
                use_container_width=True,
            )

st.divider()

# ------------------------------------------------------------------
# Page summaries — grouped to match the sidebar
# ------------------------------------------------------------------

st.header("Page Overview")

groups = {
    "Invoices": [
        (
            "1. Generate Invoice",
            [
                "Toggle **Document type**: Invoice (default) or **Credit Note** — credit notes store a negative amount and negate a previously issued invoice",
                "For Credit Notes: optionally enter the original Invoice No being credited (reference only)",
                "Select client and project — use **Client → Project** or **Project → Client** mode",
                "Tick **Include completed projects** to see Active, On Hold, and Completed projects in the dropdown",
                "Enter amount, date, and confirm the auto-suggested **Invoice ID** (sequential counter for the year)",
                "**Invoice No** (shown on the document) is auto-formatted as `ID/YYYY` (e.g. `12/2026`)",
                "Optionally expand **Project Code Allocation** to split the net amount across project codes — leave at 0 for automatic pro-rata by budget",
                "Add optional expense lines in the **Advanced** section",
                "Click **Generate Invoice** — creates the DB record, saves the file to `exports/`, then offers a Download button",
            ],
            [
                "VAT amount and gross auto-calculated as you type",
                "Address and VAT number auto-filled from the client record",
                "Description and template auto-filled from the project record",
                "Allocation balance checker shows when manual allocations match the net amount",
            ],
        ),
        (
            "2. Invoice Log",
            [
                "**Sort** the table by Date, Invoice ID, Amount, Client, Status, or Type (asc / desc)",
                "Filter by Year, Client, Project, Status, and free-text search",
                "**✓ Pay** — record a full payment for the remaining balance (today's date)",
                "**± Part.** — open an inline form to record a partial payment with amount, date, and optional note",
                "**↩ Reset** — clear all payment records and revert the invoice to Outstanding",
                "Download individual invoice files (PDF or DOCX) per row",
                "Export the filtered view to Excel (includes Paid €, Balance €, Type, Related Invoice No, Comment columns)",
                "Bulk upload: download the Excel template, fill in invoices, upload to import in bulk — template includes Description, Comment, Type, and Related Invoice No columns",
            ],
            [
                "Columns: Date · Invoice ID · Inv No (ID/YYYY) · Type (📄 Invoice / 🔄 Credit Note) · Client · Project · Net € · VAT € · Status · Balance € · File · Action",
                "Balance € = gross − payments received; shows `—` for legacy paid records with no payment rows",
                "Payment history shown as captions below each row (date, amount, optional note)",
                "Internal comment shown as caption (💬) below the row — not visible on the invoice document",
                "Credit note rows show the referenced original invoice number (↩) below the row",
                "Summary strip: invoice count, net, gross, and **actual outstanding balance** (accounting for partial payments)",
            ],
        ),
    ],
    "Clients & Projects": [
        (
            "3. Clients & Projects",
            [
                "**Clients tab**: add, edit, or delete clients — name, billing name, VAT number, client type, country, addresses",
                "**Projects tab**: add, edit, or delete projects — description, VAT %, template, status, start date",
                "**Admin expander (Projects tab)**: run **Sync completed project budgets** — sets zero-budget project code amounts to an equal share of the total invoiced amount for each Completed project",
            ],
            [
                "Clients tab: filter by name search, client type (managed / external / internal), and country; badge legend shown",
                "Projects tab: filter by client, status, client type, and country; columns include Budget, Billable, Write-offs, Invoiced",
                "Projects tab totals bar: aggregate Budget, Billable, Write-offs, and Invoiced for the filtered view",
            ],
        ),
        (
            "4. Add New Project",
            [
                "Fill in client (select existing or **create new**), project details, and project code rows in a single form",
                "**Create new client** includes: name, billing name, client code, VAT number, **Client Type** (managed / external / internal), and **Country**",
                "Project codes are **optional** for external and internal clients; at least one is required for managed clients",
                "Click **Import to Database** — creates only missing records (safe to re-run)",
            ],
            [
                "Client matched by name — if found, existing record is reused, no duplicate created",
                "Project matched by name within the client — existing record reused if found",
                "Each project code row creates a billing sub-line with its own suffix, budget, and optional date range",
            ],
        ),
        (
            "5. Project Codes",
            [
                "Add a billing code (client_suffix) to a project — client_code derived from the client",
                "Set per-code budget, status, and optional Date Start / Date End for time-range scoping",
                "Edit or delete existing codes (deletion blocked if time entries exist)",
            ],
            [
                "Per-code metrics: budget, billable charges, write-offs, remaining",
                "Date range shown in label when a suffix is reused across projects",
            ],
        ),
    ],
    "Pipeline & Reporting": [
        (
            "6. Pipeline / CRM",
            [
                "Set or update stage, contracted value, min/est/max budget, probability, and notes per project",
            ],
            [
                "Filter by stage, client type, and country",
                "Columns include: Country, In Pipeline (date first entered), In Stage Since (auto-updated when stage changes)",
                "Probability-weighted forecast totals (weighted min / est / max)",
                "Stage summary metrics (count + total value per stage)",
            ],
        ),
        (
            "7. Dashboard",
            [],
            [
                "YTD revenue vs prior year (net, VAT, gross) with % change",
                "Monthly revenue bar chart (net vs gross)",
                "Revenue by client bar chart",
                "VAT summary table by month with totals row",
                "Pipeline forecast: probability-weighted min / est / max",
            ],
        ),
        (
            "8. Project Overview",
            [
                "Export the full project table to Excel",
            ],
            [
                "One row per project: Client, Project, Source, Codes, Budget, Billable, Write-offs, Net, Invoiced, Remaining, Status",
                "Multi-select filters: Client, Status, Source",
                "Summary totals: project count, budget, billable, invoiced",
            ],
        ),
    ],
    "Time & Billing": [
        (
            "9. Time Tracking",
            [
                "Import a monthly time-charge CSV (rows matched by client_code + suffix)",
                "Delete an entire import batch if needed",
                "Assign or change a consultant's group (Local / ICEE / Other) on the Consultant Groups tab",
                "Add new consultants manually on the Consultant Groups tab",
            ],
            [
                "Entries tab: raw time entries filterable by client, project, period, billable-only",
                "Rollup tab: project-level and per-code summary of billable hours, charges, write-offs, net",
                "Local / ICEE / Other breakdown by consultant group in the Rollup tab",
                "Consultant Groups tab: full list of consultants with group assignments",
            ],
        ),
        (
            "10. Write-offs",
            [
                "Record a project-level write-off (allocated pro-rata across consultants by billable charges)",
                "Record an ad-hoc write-off for a specific consultant",
                "Reverse an existing write-off with a reason",
            ],
            [
                "Allocation preview showing each consultant's share before saving",
                "Log tab: all write-offs filterable by client/project, with reversed entries optionally shown",
            ],
        ),
    ],
    "Annual Review": [
        (
            "11. Billing Basis",
            [
                "Select **Financial Year** and filter by **Group** (Local / ICEE / Other / All) — defaults to Local",
                "Auto-aggregate billing amounts from Time Tracking (non_z_charges per consultant for the year)",
                "Or enter billing amounts manually in the Sheet5-style table",
                "Enter each consultant's hourly billing rate to unlock equivalent-hours and productivity-bonus calculation",
                "Save the basis for use by page 13 — Annual Review",
            ],
            [
                "Per-consultant: Grand Total, Basis for Bonus (Grand Total − Charged Off), Equivalent Hours, Productivity Bonus %",
                "Saved Basis tab shows all stored rows for the selected year",
                "Productivity bonus formula: `(Equiv Hours − 800) / 40 × 1%`",
            ],
        ),
        (
            "12. Consultant Profiles",
            [
                "Filter by **Group** (Local / ICEE / Other / All) — defaults to Local",
                "Record employment start date, prior experience, Milliman status, external level, languages, and tools",
                "Add or edit year records in the Salary History tab: starting salary, exams passed, exam raise rate, other raise, objective bonus %, proposed billing rate",
            ],
            [
                "Profile tab: full employment profile for the selected consultant",
                "Salary History tab: year-by-year salary chain with bonus details; updated salary auto-carries to next year",
                "Rates tab: billing rates by year from salary history and billing basis",
                "Productivity bonus pulled from page 11 (Billing Basis) automatically",
            ],
        ),
        (
            "13. Annual Review",
            [
                "Select consultant + year; set assessor name and assessment date",
                "Section 1 — Compensation: enter exams passed, other raise, objective bonus %, proposed rate → computed fields update live",
                "Section 2 — Performance Scores: score each sub-item (1.0–5.0) across Professionalism, Management, Social Skills",
                "Save compensation and scores independently; export full review to Excel",
            ],
            [
                "Auto-pulls productivity bonus % from saved Billing Basis",
                "Shows salary chain and bonus calculation live",
                "Prior 3 years shown as reference; group averages calculated automatically",
                "Management scoring group always shown — set to 0 for non-manager consultants",
            ],
        ),
    ],
    "Admin": [
        (
            "14. Data Tables",
            [
                "Open the database directly in **DB Browser for SQLite** (for edits not covered by the UI)",
                "Open the database folder in File Explorer",
            ],
            [
                "Read-only view of every table: Clients, Projects, Project Codes, Invoices, Payments, Time Entries, Write-offs, Pipeline, Billing Basis, Salary History, Review Scores",
                "Configurable row limit per table; Show All option",
                "Full database file path displayed for reference",
            ],
        ),
    ],
}

for group_name, pages in groups.items():
    st.subheader(group_name)
    for title, actions, views in pages:
        with st.expander(f"**{title}**", expanded=False):
            if actions:
                st.markdown("**Actions**")
                for a in actions:
                    st.markdown(f"- {a}")
            if views:
                st.markdown("**Views / Available Information**")
                for v in views:
                    st.markdown(f"- {v}")

st.divider()

# ------------------------------------------------------------------
# Where to go for each edit
# ------------------------------------------------------------------

st.header("Where to Go for Each Edit")

st.markdown("""
| What you want to do | Where to go |
|---|---|
| Generate an invoice or credit note | **1. Generate Invoice** |
| See completed projects in the invoice form | **1. Generate Invoice** → tick *Include completed projects* |
| Record a full payment on an invoice | **2. Invoice Log** → **✓** button on the invoice row |
| Record a partial payment | **2. Invoice Log** → **±** button → enter amount, date, note |
| Clear payments and reset to Outstanding | **2. Invoice Log** → **↩ Reset** button |
| Add a completely new project with client and codes | **4. Add New Project** |
| Add a new external or internal client (no codes needed) | **4. Add New Project** → Create new client → set Client Type |
| Client name / VAT / billing name / type / country | **3. Clients & Projects** → Clients tab → Edit |
| Project description / VAT % / template / status | **3. Clients & Projects** → Projects tab → Edit |
| Project code budget / date range | **5. Project Codes** → expand code → Edit |
| Auto-set budgets for completed projects from invoiced amounts | **3. Clients & Projects** → Projects tab → *Admin: sync completed project budgets* expander |
| Invoice allocation to project codes | **1. Generate Invoice** → Project Code Allocation expander |
| Pipeline stage / estimated value / probability | **6. Pipeline / CRM** → edit row → Save |
| Consultant group (Local / ICEE / Other) | **9. Time Tracking** → Consultant Groups tab |
| Write-off reason / reversal | **10. Write-offs** → Log tab → Reverse button |
| Annual billing amounts for bonus calc | **11. Billing Basis** → Manual Entry or Auto tab (filter by Local first) |
| Consultant employment / experience / tools | **12. Consultant Profiles** → Profile tab (filter by Local first) |
| Salary record for a specific year | **12. Consultant Profiles** → Salary History tab → Add / Edit Year Record |
| Performance scores for a review year | **13. Annual Review** → Section 2 — Performance Scores |
| Anything else (direct DB edit) | **14. Data Tables** → Open in DB Browser for SQLite |
""")

st.info(
    "**DB Browser for SQLite** is your escape hatch for anything not covered by the UI: "
    "rename a project, fix a wrong invoice number, delete a duplicate row, and so on. "
    "Open the table, double-click a cell, edit, then click **Write Changes**. "
    "Note: editing the CSV files in `DB_Tbls_Structure/` has **no effect** on the live database — "
    "those are export snapshots only."
)

st.divider()

# ------------------------------------------------------------------
# Key concepts & terminology
# ------------------------------------------------------------------

st.header("Key Concepts")

st.markdown("""
| Term | Meaning |
|---|---|
| **Invoice ID** | Sequential log counter per year (e.g. `12`). Auto-suggested; can be overridden. |
| **Invoice No** | Business reference shown on the document: `ID/YYYY` (e.g. `12/2026`). |
| **Credit Note** | An invoice with a negative amount that negates or partially reverses a previous invoice. Shares the same sequential counter as invoices. |
| **Gross amount** | Net fee + expenses net + VAT on fees + VAT on expenses. This is the total the client owes. |
| **Balance** | Gross amount minus payments received. Zero once fully paid. |
| **Pro-rata allocation** | When no manual split is entered, the invoice net is distributed across project codes in proportion to their budgets. |
| **managed client** | Standard client with full project tracking, budgets, and invoices. |
| **external client** | Client outside normal managed scope — tracked at a basic level; project codes optional. |
| **internal client** | Non-billable overhead codes (e.g. internal projects, admin time). |
| **Local group** | The Cyprus local team. Default filter on Billing Basis and Consultant Profiles pages. |
""")
