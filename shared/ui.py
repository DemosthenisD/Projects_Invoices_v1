"""
Shared Streamlit UI helpers used across multiple pages.
"""
from datetime import datetime
import os
import streamlit as st
import pandas as pd

from shared.config import TEMPLATES_DIR


def require_auth() -> None:
    """Stop page execution if the user is not authenticated.

    Call once at the top of every page, immediately after imports.
    """
    if not st.session_state.get("authenticated", False):
        st.warning("Please sign in from the Home page.")
        st.stop()


@st.cache_data(ttl=300)
def list_templates() -> list[str]:
    """Return sorted template names available in the templates directory.

    Excludes filled/temp files that start with 'filled'. Result is cached
    for 5 minutes so repeated calls don't hit the filesystem every rerun.
    """
    return sorted(
        f.replace(".docx", "")
        for f in os.listdir(TEMPLATES_DIR)
        if f.endswith(".docx") and not f.startswith("filled")
    )


def fmt_date(d: str) -> str:
    """Convert an ISO date string (YYYY-MM-DD) to display format (DD/MM/YYYY).

    Returns the original string unchanged if parsing fails, so it is safe
    to call on empty strings or legacy values.
    """
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def fmt_eur(x, decimals: int = 0) -> str:
    """Format a number as a Euro amount: €1,234 (0 dp) or €1,234.56 (2 dp).

    Use decimals=0 for salaries/budgets, decimals=2 for invoice amounts/payments.
    """
    try:
        return f"€{float(x):,.{decimals}f}"
    except (TypeError, ValueError):
        return "€—"


def dataframe_with_total(
    df: pd.DataFrame,
    total_dict: dict,
    fmt: dict,
    na_rep: str = "—",
) -> None:
    """
    Render a sortable dataframe followed by a pinned TOTAL row.

    The data table is a normal st.dataframe (user can sort columns).
    The TOTAL row is displayed in a separate st.dataframe immediately
    below, with blank column headers so it reads as a footer row.

    Args:
        df:         Data rows only (no TOTAL row included).
        total_dict: Dict mapping column name → total value (same keys as df.columns).
        fmt:        Format dict for pandas Styler, e.g. {"Amount": "{:,.0f}"}.
        na_rep:     String to show for NaN values.
    """
    # Sortable data
    st.dataframe(
        df.style.format(fmt, na_rep=na_rep),
        use_container_width=True,
        hide_index=True,
    )

    # TOTAL row — pre-format all values as strings so no secondary formatting
    formatted: dict[str, str] = {}
    for col in df.columns:
        val = total_dict.get(col, "")
        if col in fmt and isinstance(val, (int, float)):
            formatted[col] = fmt[col].format(val)
        else:
            formatted[col] = str(val) if val != "" else ""

    total_df = pd.DataFrame([formatted])

    # Blank column labels to suppress the duplicate header row visually
    blank_cfg = {col: st.column_config.TextColumn(label="") for col in total_df.columns}

    st.dataframe(
        total_df.style.set_properties(**{"font-weight": "bold", "background-color": "#eef2ff"}),
        column_config=blank_cfg,
        use_container_width=True,
        hide_index=True,
    )
