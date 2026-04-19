"""
InvoiceApp — login entry point.

Run with:
    cd frontend
    streamlit run App.py
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

# ------------------------------------------------------------------
# Session state helpers
# ------------------------------------------------------------------

def _is_logged_in() -> bool:
    return st.session_state.get("authenticated", False)


def _logout() -> None:
    st.session_state["authenticated"] = False


# ------------------------------------------------------------------
# Login wall
# ------------------------------------------------------------------

if not _is_logged_in():
    # Hide the page list in the sidebar until the user is signed in
    st.markdown(
        "<style>[data-testid='stSidebarNav']{display:none}</style>",
        unsafe_allow_html=True,
    )
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
# Authenticated landing — redirect hint
# ------------------------------------------------------------------

st.sidebar.button("Sign out", on_click=_logout)

st.title("InvoiceApp")
st.write(f"Welcome, **{st.session_state.get('username', '')}**.")
st.info("Use the sidebar to navigate to a page.")
