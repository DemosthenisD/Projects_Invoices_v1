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
            "Add optional expense lines (in the Advanced section)",
            "Click **Generate Invoice** to create the DB record and save the file to `exports/`",
            "Download the file via the Download button (optional — file is already saved locally)",
        ],
        [
            "VAT amount and gross auto-calculated as you type",
            "Invoice number auto-suggested (max for the year + 1)",
            "Address and VAT number auto-filled from the client record",
            "Description and template auto-filled from the project record",
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
            "Add, edit, or delete billing codes (client_code + suffix) per project",
            "Set per-code budget and status",
        ],
        [
            "Per-code metrics: budget, billable charges, write-offs, remaining",
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
| Client name / VAT / billing name | Page 3 — Clients & Projects → expand client → Edit |
| Project description / VAT % / template / status | Page 3 — Clients & Projects → expand client → expand project → Edit |
| Project code budget | Page 6 — Project Codes → expand code → Edit |
| Pipeline stage / estimated value / probability | Page 4 — Pipeline / CRM → expand project → Save |
| Consultant group (Local / ICEE / Other) | Page 7 — Time Tracking → Consultant Groups tab → expand person → Save |
| Write-off reason / reversal | Page 8 — Write-offs → Log tab → Reverse button |
| Anything else (direct DB edit) | Page 9 — Data Tables → **Open in DB Browser for SQLite** |
""")

st.info(
    "**DB Browser for SQLite** is your escape hatch for anything not covered by the UI: "
    "rename a project, fix a wrong invoice number, delete a duplicate row, and so on. "
    "Open the table, double-click a cell, edit, then click **Write Changes**."
)
