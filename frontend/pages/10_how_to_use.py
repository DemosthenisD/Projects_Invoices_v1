"""
Page 10 — How to Use.

Quick reference: page summaries, where to go for each edit, and DB tips.
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
    ("Generate Invoice",   "0",  "Fill a Word template with client / project / amount details and export as PDF or DOCX. The file is saved permanently to the `exports/` folder; the Download button is optional."),
    ("Invoice Log",        "1",  "Browse all recorded invoices. Filter by year, client, or project (filters cascade). Each row shows net, VAT, and expenses amounts plus a download button for the generated file. Export the filtered view to Excel."),
    ("Clients & Projects", "2",  "Manage client master data (name, VAT number, billing name, address) and projects (description, VAT %, invoice template, status). Each project card shows a billing summary: billable charges, invoiced, write-offs, and remaining."),
    ("Pipeline / CRM",     "3",  "Track business opportunities by stage (Prospect → Active → On Hold → Completed). Set contracted value, min/est/max budget, and probability for each project. A probability-weighted forecast is shown at the top."),
    ("Dashboard",          "4",  "High-level financial overview: YTD revenue vs prior year, monthly bar chart, revenue by client, VAT summary table, and pipeline forecast (probability-weighted min/est/max)."),
    ("Project Codes",      "5",  "Manage billing codes (client_code + suffix) per project. Each code has its own budget. Per-code metrics show budget, billable charges, write-offs, and remaining."),
    ("Time Tracking",      "6",  "Import monthly time-charge CSV reports. Browse entries by client/project/period. The Rollup tab shows project and per-code summaries plus a Local/ICEE/Other breakdown. Manage consultant group assignments on the Consultant Groups tab."),
    ("Write-offs",         "7",  "Record write-offs against projects. Project-level write-offs are allocated pro-rata across consultants by their billable charges. Ad-hoc write-offs target a specific consultant. The Log tab shows all write-offs with the option to reverse them."),
    ("Data Tables",        "8",  "Direct read-only view of every database table (Clients, Projects, Project Codes, Invoices, Time Entries, Write-offs, Pipeline). Use the **Open in DB Browser for SQLite** button to edit data directly."),
    ("Project Overview",   "9",  "Full project-level financial summary across all clients. Columns: Client, Project, Source (CY/NotBillable/Other), Codes, Budget, Billable, Write-offs, Net, Invoiced, Remaining, Status. Filter by client, status, or source. Export to Excel."),
    ("How to Use",         "10", "This page — quick reference for page functionality and where to go for each type of edit."),
]

for name, num, desc in pages:
    st.markdown(f"**Page {num} — {name}**")
    st.write(desc)
    st.divider()

# ------------------------------------------------------------------
# Where to go for each edit
# ------------------------------------------------------------------

st.header("Where to Go for Each Edit")

st.markdown("""
| What you want to edit | Where to go |
|---|---|
| Client name / VAT / billing name | Page 2 — Clients & Projects → expand client → Edit |
| Project description / VAT % / template / status | Page 2 — Clients & Projects → expand client → expand project → Edit |
| Project code budget | Page 5 — Project Codes → expand code → Edit |
| Pipeline stage / estimated value / probability | Page 3 — Pipeline / CRM → expand project → Save |
| Consultant group (Local / ICEE / Other) | Page 6 — Time Tracking → Consultant Groups tab → expand person → Save |
| Write-off reason / reversal | Page 7 — Write-offs → Log tab → Reverse button |
| Anything else (direct DB edit) | Page 8 — Data Tables → **Open in DB Browser for SQLite** |
""")

st.info(
    "**DB Browser for SQLite** is your escape hatch for anything not covered by the UI: "
    "rename a project, fix a wrong invoice number, delete a duplicate row, and so on. "
    "Open the table, double-click a cell, edit, then click **Write Changes**."
)
