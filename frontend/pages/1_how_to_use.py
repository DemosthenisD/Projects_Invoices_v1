"""
Page 1 — How to Use.

Quick reference: page summaries split by Actions vs Views, edit reference table, and DB tips.
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
# Page summaries
# ------------------------------------------------------------------

st.header("Page Overview")

pages = [
    (
        "0 — Generate Invoice",
        [
            "Select client, project, amount, date, and format (PDF or DOCX)",
            "Optionally expand **Project Code Allocation** to split the invoice net amount across project codes — leave at 0 to apply automatic pro-rata by budget",
            "Add optional expense lines (in the Advanced section)",
            "Click **Generate Invoice** to create the DB record and save the file to `exports/`",
            "Download the file via the Download button (optional — file is already saved locally)",
        ],
        [
            "VAT amount and gross auto-calculated as you type",
            "Invoice number auto-suggested (max for the year + 1)",
            "Address and VAT number auto-filled from the client record",
            "Description and template auto-filled from the project record",
            "Allocation balance checker shows when manual allocations match the net amount",
        ],
    ),
    (
        "2 — Invoice Log",
        [
            "Download individual invoice files (PDF or DOCX) per row",
            "Export the filtered view to Excel",
        ],
        [
            "All recorded invoices: date, invoice #, client, project, net, VAT, expenses",
            "Filters: Year → Client → Project (cascading) + free-text search",
            "Summary totals (invoice count, net, VAT, gross) for the filtered view",
        ],
    ),
    (
        "3 — Clients & Projects",
        [
            "Add, edit, or delete clients (name, billing name, VAT number, address)",
            "Add, edit, or delete projects (description, VAT %, template, status)",
        ],
        [
            "All clients listed alphabetically with expandable project cards",
            "Per-project billing summary: billable charges, invoiced, write-offs, remaining",
        ],
    ),
    (
        "4 — Pipeline / CRM",
        [
            "Set or update stage, contracted value, min/est/max budget, probability, and notes per project",
        ],
        [
            "Tabular summary of all pipeline entries filterable by stage and client",
            "Probability-weighted forecast totals (weighted min / est / max)",
            "Stage summary metrics (count + total value per stage)",
        ],
    ),
    (
        "5 — Dashboard",
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
        "6 — Project Codes",
        [
            "Add a billing code (client_suffix) to a project — client_code is derived automatically from the client",
            "Set per-code budget, status, and optional Date Start / Date End for time-range scoping",
            "Edit or delete existing codes (deletion blocked if time entries exist)",
        ],
        [
            "Per-code metrics: budget, billable charges, write-offs, remaining",
            "Date range shown in label when a suffix is reused across projects",
        ],
    ),
    (
        "7 — Time Tracking",
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
            "Consultant Groups tab: full list of consultants with their group assignments",
        ],
    ),
    (
        "8 — Write-offs",
        [
            "Record a project-level write-off (allocated pro-rata across consultants by their billable charges)",
            "Record an ad-hoc write-off for a specific consultant",
            "Reverse an existing write-off with a reason",
        ],
        [
            "Allocation preview showing each consultant's share before saving",
            "Log tab: all write-offs filterable by client/project, with reversed entries optionally shown",
        ],
    ),
    (
        "9 — Data Tables",
        [
            "Open the database directly in **DB Browser for SQLite** (for edits not covered by the UI)",
            "Open the database folder in File Explorer",
        ],
        [
            "Read-only view of every table: Clients, Projects, Project Codes, Invoices, Time Entries, Write-offs, Pipeline",
            "Configurable row limit per table; Show All option",
            "Full database file path displayed for reference",
        ],
    ),
    (
        "10 — Project Overview",
        [
            "Export the full project table to Excel",
        ],
        [
            "One row per project: Client, Project, Source (CY / NotBillable / Other), Codes, Budget, Billable, Write-offs, Net, Invoiced, Remaining, Status",
            "Multi-select filters: Client, Status, Source",
            "Summary totals: project count, budget, billable, invoiced",
        ],
    ),
    (
        "11 — Add New Project",
        [
            "Fill in client (select existing or create new), project details, and one or more project code rows in a single form",
            "Click **Import to Database** — the app creates only the records that don't already exist (safe to re-run)",
        ],
        [
            "Client is matched by name; if found, existing record is reused (no duplicate created)",
            "Project is matched by name within the client; if found, existing record is reused",
            "Each project code row creates a new billing sub-line with its own suffix, budget, and optional date range",
        ],
    ),
    (
        "12 — Billing Basis",
        [
            "Auto-aggregate billing amounts from Time Tracking (non_z_charges per consultant for the year)",
            "Or enter billing amounts manually in the Sheet5-style table (Billed / Capped Prebill / Charged Off / Paid / Unbilled)",
            "Enter each consultant's hourly billing rate to unlock the equivalent-hours and productivity-bonus calculation",
            "Save the basis for use by the Annual Review page",
        ],
        [
            "Per-consultant: Grand Total, Basis for Bonus (Grand Total − Charged Off), Equivalent Hours, Productivity Bonus %",
            "Saved Basis tab shows all stored rows for the selected year with an Export to Excel button",
            "Basis for Bonus formula: `(Equiv Hours − 800) / 40 × 1%`",
        ],
    ),
    (
        "13 — Consultant Profiles",
        [
            "Record employment start date, prior experience, Milliman status, external level, languages, and tools",
            "Add or edit year records in the Salary History tab: starting salary, exams passed, exam raise rate, other raise, objective bonus %, proposed billing rate",
        ],
        [
            "Profile tab: full employment profile for the selected consultant",
            "Salary History tab: year-by-year table showing salary chain, bonus %, bonus amount — auto-carries forward updated salary to the next year",
            "Rates tab: billing rates by year from salary history and billing basis",
            "Productivity bonus is pulled from Page 12 (Billing Basis) automatically when shown",
        ],
    ),
    (
        "14 — Annual Review",
        [
            "Select consultant + year; set assessor name and assessment date",
            "Section 1 — Compensation: enter exams passed, other raise, objective bonus %, proposed rate → computed fields update live",
            "Section 2 — Performance Scores: score each sub-item (1.0–5.0) across three groups: Professionalism, Management, Social Skills",
            "Save compensation and scores independently; export the full review to Excel",
        ],
        [
            "Compensation section: auto-pulls productivity bonus % from saved Billing Basis; shows salary chain (start → raises → updated salary) and bonus calculation",
            "Performance section: historical scores for the prior 3 years shown alongside current-year inputs; group averages calculated automatically",
            "Summary section: formatted review card with all compensation and score data",
            "Management scoring group is always shown — set scores to 0 for non-manager consultants",
        ],
    ),
]

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
| What you want to edit | Where to go |
|---|---|
| Add a completely new project with client and codes | Page 11 — Add New Project |
| Client name / VAT / billing name | Page 3 — Clients & Projects → expand client → Edit |
| Project description / VAT % / template / status | Page 3 — Clients & Projects → expand client → expand project → Edit |
| Project code budget / date range | Page 6 — Project Codes → expand code → Edit |
| Invoice allocation to project codes | Page 0 — Generate Invoice → Project Code Allocation (before generating) |
| Pipeline stage / estimated value / probability | Page 4 — Pipeline / CRM → expand project → Save |
| Consultant group (Local / ICEE / Other) | Page 7 — Time Tracking → Consultant Groups tab → expand person → Save |
| Write-off reason / reversal | Page 8 — Write-offs → Log tab → Reverse button |
| Anything else (direct DB edit) | Page 9 — Data Tables → **Open in DB Browser for SQLite** |
| Consultant employment / experience / tools | Page 13 — Consultant Profiles → Profile tab |
| Salary record for a specific year | Page 13 — Consultant Profiles → Salary History tab → Add / Edit Year Record |
| Billing amounts for bonus calculation | Page 12 — Billing Basis → Manual Entry or Auto tab |
| Performance scores for a review year | Page 14 — Annual Review → Section 2 — Performance Scores |
""")

st.info(
    "**DB Browser for SQLite** is your escape hatch for anything not covered by the UI: "
    "rename a project, fix a wrong invoice number, delete a duplicate row, and so on. "
    "Open the table, double-click a cell, edit, then click **Write Changes**."
)
