"""
Page 14 — Data Field Definitions.

Reference table listing every data field used across the application:
its standardised display name, where it appears, and its definition.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

st.title("Data Field Definitions")
st.caption(
    "Reference guide for every data field used in the application. "
    "Use this page to understand what each field means, where it is stored, and where it appears."
)

FIELDS = [
    {
        "Field Name": "Country",
        "DB Field / Source": "clients.country",
        "Pages / Tabs": "3-Clients (Clients tab, filter + table)\n3-Clients (Projects tab, table)\n6-Pipeline (Client Country filter + table)",
        "Definition": (
            "The country of registration or domicile of the client. "
            "Free text, entered by the user on the client record. "
            "Distinct from Milliman Office (which is derived from the billing code prefix)."
        ),
    },
    {
        "Field Name": "Milliman Office",
        "DB Field / Source": "Computed: first 4 digits of client_code → OfficeCodes.txt lookup",
        "Pages / Tabs": "8-Project Overview (filter + table column 'Office')",
        "Definition": (
            "The Milliman office that owns the client's billing code prefix "
            "(e.g. 0478 → Cyprus, 0011 → Seattle, 0403 → London). "
            "Derived automatically from the client code — not stored in the database. "
            "Distinct from the client's Country field."
        ),
    },
    {
        "Field Name": "Opportunity Country",
        "DB Field / Source": "pipeline.opportunity_country",
        "Pages / Tabs": "6-Pipeline (Opportunity Country filter + editable table column)",
        "Definition": (
            "The country where the work opportunity will be delivered, as opposed to the "
            "client's registration country. Editable directly in the Pipeline table. "
            "Separate from Client Country."
        ),
    },
    {
        "Field Name": "Client Type",
        "DB Field / Source": "clients.client_type",
        "Pages / Tabs": (
            "3-Clients (filter + table)\n3-Projects (filter)\n"
            "5-Project Codes (filter)\n6-Pipeline (filter)\n"
            "8-Project Overview (filter + table)"
        ),
        "Definition": (
            "Billing classification of the client. "
            "managed = full project management (Cyprus office clients); "
            "external = time tracking only (ICEE or other external engagements); "
            "internal = non-billable overhead (0009xxx codes)."
        ),
    },
    {
        "Field Name": "Project Status",
        "DB Field / Source": "projects.status",
        "Pages / Tabs": "3-Projects (filter + table)\n8-Project Overview (filter + table)",
        "Definition": (
            "Lifecycle stage of a project: Active, On Hold, Completed, or Prospect. "
            "Setting to Completed automatically closes all linked project codes."
        ),
    },
    {
        "Field Name": "Pipeline Stage",
        "DB Field / Source": "pipeline.stage",
        "Pages / Tabs": "6-Pipeline (filter + editable table)",
        "Definition": (
            "Sales / CRM stage of the opportunity: Prospect, Active, On Hold, or Completed. "
            "Stored separately from Project Status and editable in the Pipeline table. "
            "Auto-created for all projects when the Pipeline page is first opened."
        ),
    },
    {
        "Field Name": "Code Status",
        "DB Field / Source": "project_codes.status",
        "Pages / Tabs": "5-Project Codes (table + edit form)",
        "Definition": (
            "Lifecycle stage of an individual project code: Active, On Hold, or Completed. "
            "Separate from the parent project's status."
        ),
    },
    {
        "Field Name": "Employment Status",
        "DB Field / Source": "consultant_groups.status",
        "Pages / Tabs": (
            "9-Time Tracking / Consultant Teams tab (Employment Status selector, Local consultants only)\n"
            "12-Consultant Profiles (Employment Status filter)\n"
            "13-Annual Review (only Local + Active consultants appear in the dropdown)"
        ),
        "Definition": (
            "Whether a Local consultant is currently Active or Inactive. "
            "Default is Active. Only applies to consultants in the Local team. "
            "Inactive consultants are hidden from the Annual Review dropdown."
        ),
    },
    {
        "Field Name": "Consultant Team",
        "DB Field / Source": "consultant_groups.group_name",
        "Pages / Tabs": (
            "9-Time Tracking / Entries tab (filter)\n"
            "9-Time Tracking / Team Summary (filter)\n"
            "9-Time Tracking / Consultant Teams tab (managed here)\n"
            "8-Project Overview (filter)\n"
            "11-Billing Basis (filter)\n"
            "12-Consultant Profiles (filter)\n"
            "13-Annual Review (only Local team shown)"
        ),
        "Definition": (
            "The team or group a consultant belongs to: Local, ICEE, or Other. "
            "Assigned in the Consultant Teams tab on Time Tracking. "
            "New consultants are automatically added as 'Other' on time entry import."
        ),
    },
    {
        "Field Name": "Employee Number (emp_nbr)",
        "DB Field / Source": "consultant_groups.emp_nbr, time_entries.emp_nbr",
        "Pages / Tabs": (
            "9-Time Tracking / Consultant Teams tab (editable)\n"
            "12-Consultant Profiles (used to look up salary and billing records)\n"
            "13-Annual Review (required to load billing basis and salary data)"
        ),
        "Definition": (
            "Unique numeric identifier for a consultant, as used in the timesheet system. "
            "Imported automatically from the time entry CSV. "
            "Must be set correctly for Annual Review and billing basis lookups to work."
        ),
    },
    {
        "Field Name": "Period",
        "DB Field / Source": "time_entries.period",
        "Pages / Tabs": "9-Time Tracking / Entries and Rollup tabs (filter + table)",
        "Definition": (
            "The billing period a time entry belongs to, in YYYYMM format "
            "(e.g. 202401 = January 2024). Used to filter and aggregate time entries."
        ),
    },
    {
        "Field Name": "Billing Basis Rate",
        "DB Field / Source": "billing_basis.hourly_rate",
        "Pages / Tabs": "12-Consultant Profiles / Rates by Year tab",
        "Definition": (
            "The actual hourly billing rate used in a given year, "
            "sourced from the billing_basis table (populated via Auto-import or manual entry on "
            "Page 11 - Billing Basis). Used in productivity bonus calculations."
        ),
    },
    {
        "Field Name": "Proposed Rate for following year",
        "DB Field / Source": "salary_history.proposed_rate",
        "Pages / Tabs": (
            "12-Consultant Profiles / Salary History tab (column + edit form)\n"
            "12-Consultant Profiles / Rates by Year tab\n"
            "13-Annual Review (shown as context in the billing basis warning)"
        ),
        "Definition": (
            "The hourly billing rate proposed for the consultant in the following year. "
            "Stored in the salary history record for a given year. "
            "Does not automatically update the Billing Basis Rate — that must be entered separately."
        ),
    },
    {
        "Field Name": "Starting Salary",
        "DB Field / Source": "salary_history.starting_salary",
        "Pages / Tabs": "12-Consultant Profiles / Salary History tab\n13-Annual Review (Salary & Bonus section)",
        "Definition": (
            "The base salary at the start of the review year, before any raises. "
            "Used as the basis for bonus calculations (Productivity Bonus % × Starting Salary)."
        ),
    },
    {
        "Field Name": "Updated Salary",
        "DB Field / Source": "Computed: starting_salary + exam_raise + other_raise",
        "Pages / Tabs": "12-Consultant Profiles / Salary History tab\n13-Annual Review (Salary & Bonus section)",
        "Definition": (
            "The salary after all raises in the review year are applied. "
            "Computed as Starting Salary + (Exams Passed × Raise per Exam) + Other Raise. "
            "Used as the salary for the following year's Starting Salary."
        ),
    },
    {
        "Field Name": "Billing Basis Source",
        "DB Field / Source": "billing_basis.source",
        "Pages / Tabs": "11-Billing Basis (table)\n12-Consultant Profiles / Rates by Year tab",
        "Definition": (
            "How the billing basis record was populated: "
            "'auto' = imported from time entries and write-offs; "
            "'manual' = entered directly by the user."
        ),
    },
]

df = pd.DataFrame(FIELDS)
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Field Name":        st.column_config.TextColumn("Field Name",        width="medium"),
        "DB Field / Source": st.column_config.TextColumn("DB Field / Source", width="large"),
        "Pages / Tabs":      st.column_config.TextColumn("Pages / Tabs",      width="large"),
        "Definition":        st.column_config.TextColumn("Definition",         width="large"),
    },
)

st.divider()
st.caption(
    "Fields listed above are consistent across all pages as of the current version. "
    "If you notice a discrepancy in labelling, report it via the GitHub Issues page."
)
