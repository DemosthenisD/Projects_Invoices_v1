"""
Loads app configuration from .streamlit/secrets.toml (when running via Streamlit)
or from environment variables (standalone scripts / CI).
"""
import os


def _get(key: str, default: str = "") -> str:
    """
    Try st.secrets first, then os.environ, then default.
    Importing streamlit is deferred so this module works in standalone scripts.
    """
    try:
        import streamlit as st
        # st.secrets raises an exception if the key is missing
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)


CONVERT_API_KEY: str = _get("CONVERT_API_KEY", "")
LOGIN_USER: str = _get("username", "Demosthenis")
LOGIN_PASSWORD: str = _get("password", "")

# Paths relative to the repo root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "data", "invoiceapp.db")
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")
EXPORTS_DIR = os.path.join(REPO_ROOT, "exports")
LEGACY_EXCEL = os.path.join(
    REPO_ROOT,
    "Updated_Invoice_v2",
    "InvoiceLogTemplate_DD_28062024.xlsx",
)
