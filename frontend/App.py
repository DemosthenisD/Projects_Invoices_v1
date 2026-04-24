"""
InvoiceApp — entry point.

Run with:
    streamlit run frontend/App.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from shared.config import LOGIN_USER, LOGIN_PASSWORD
import backend.db as db

st.set_page_config(page_title="InvoiceApp", page_icon="🧾", layout="wide",
                   initial_sidebar_state="expanded")

db.init_db()


def _is_logged_in() -> bool:
    return st.session_state.get("authenticated", False)


def _logout() -> None:
    st.session_state["authenticated"] = False


# ------------------------------------------------------------------
# Login wall — navigation is not set up until authenticated
# ------------------------------------------------------------------
if not _is_logged_in():
    st.title("InvoiceApp")
    st.subheader("Sign in")

    with st.form("login_form"):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if username == LOGIN_USER and password == LOGIN_PASSWORD:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()


# ------------------------------------------------------------------
# Authenticated — grouped sidebar navigation
# ------------------------------------------------------------------
st.sidebar.button("Sign out", on_click=_logout, use_container_width=True)

pg = st.navigation(
    {
        "": [
            st.Page("pages/1_how_to_use.py",           title="How to Use",             icon="📖"),
        ],
        "Invoices": [
            st.Page("pages/0_generate_invoice.py",     title="1. Generate Invoice",    icon="📄"),
            st.Page("pages/2_invoice_log.py",           title="2. Invoice Log",         icon="📋"),
        ],
        "Clients & Projects": [
            st.Page("pages/3_clients_projects.py",     title="3. Clients & Projects",  icon="🏢"),
            st.Page("pages/11_add_new_project.py",     title="4. Add New Project",     icon="➕"),
            st.Page("pages/6_project_codes.py",        title="5. Project Codes",       icon="🔑"),
        ],
        "Pipeline & Reporting": [
            st.Page("pages/4_pipeline_crm.py",         title="6. Pipeline / CRM",      icon="📊"),
            st.Page("pages/5_dashboard.py",             title="7. Dashboard",           icon="📈"),
            st.Page("pages/10_project_overview.py",    title="8. Project Overview",    icon="🗂️"),
        ],
        "Time & Billing": [
            st.Page("pages/7_time_tracking.py",        title="9. Time Tracking",       icon="⏱️"),
            st.Page("pages/8_write_offs.py",            title="10. Write-offs",         icon="✂️"),
        ],
        "Annual Review": [
            st.Page("pages/12_billing_basis.py",       title="11. Billing Basis",      icon="💶"),
            st.Page("pages/13_consultant_profiles.py", title="12. Consultant Profiles",icon="👤"),
            st.Page("pages/14_annual_review.py",       title="13. Annual Review",      icon="📝"),
        ],
        "Admin": [
            st.Page("pages/9_data_tables.py",          title="14. Data Tables",        icon="🗄️"),
        ],
    }
)
pg.run()
