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
OFFICE_CODES_PATH = os.path.join(REPO_ROOT, "data", "OfficeCodes.txt")
LEGACY_EXCEL = os.path.join(
    REPO_ROOT,
    "Updated_Invoice_v2",
    "InvoiceLogTemplate_DD_28062024.xlsx",
)


def load_office_codes() -> dict[str, str]:
    """Return {4-digit prefix: office name} from data/OfficeCodes.txt.

    File format (tab-separated, first row is a header):
        first 4 digits code<TAB>OFFICE
        0478<TAB>Cyprus
        ...

    Returns an empty dict if the file is missing or unreadable.
    Hard-coded reserved codes (0009 → NotBillable) are NOT included here;
    callers handle those separately.
    """
    mapping: dict[str, str] = {}
    if not os.path.exists(OFFICE_CODES_PATH):
        return mapping
    try:
        with open(OFFICE_CODES_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    parts = line.split()   # fallback: any whitespace
                if len(parts) < 2:
                    continue
                prefix, office = parts[0].strip(), parts[1].strip()
                if prefix.isdigit() and len(prefix) == 4:
                    mapping[prefix] = office
    except Exception:
        pass
    return mapping
