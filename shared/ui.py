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


def faceted_filters(rows, facets, cols=None):
    """
    Render filter widgets whose options narrow each other (faceted search).

    Each facet's options are the distinct values found in the rows that pass
    every OTHER facet's current selection. Selections that are no longer
    available are dropped before the widgets are drawn.

    Args:
        rows:   iterable of dicts / objects / DataFrame records to filter.
        facets: list of dicts with keys
                  key     - unique session_state key
                  label   - widget label
                  get     - fn(row) -> value or list of values for this facet
                  single  - True for a selectbox with an "All" entry (default: multiselect)
                  default - initial multiselect selection (optional)
                  help    - optional help text
                  reverse - True to list options in descending order
                  extra   - values always offered even if no row has them
                            (e.g. a client with no projects yet)
        cols:   optional list of st containers (one per facet); defaults to
                st.columns(len(facets)).

    Returns:
        match(row) -> bool predicate applying all current selections.
    """
    rows = list(rows)

    def vals(f, r):
        v = f["get"](r)
        v = list(v) if isinstance(v, (list, set, tuple)) else [v]
        return [x for x in v if x not in (None, "")]

    def selected(f):
        v = st.session_state.get(f["key"], [] if not f.get("single") else "All")
        if f.get("single"):
            return [] if v == "All" else [v]
        return list(v)

    for f in facets:
        if f["key"] not in st.session_state and not f.get("single"):
            st.session_state[f["key"]] = list(f.get("default", []))

    def passes(r, skip=None):
        for g in facets:
            if g["key"] == skip:
                continue
            s = selected(g)
            if s and not any(v in s for v in vals(g, r)):
                return False
        return True

    options: dict[str, list] = {}
    for _ in range(2):  # pruning one facet can widen/narrow another
        for f in facets:
            opts = sorted({v for r in rows if passes(r, f["key"]) for v in vals(f, r)}
                          | set(f.get("extra", [])), reverse=bool(f.get("reverse")))
            options[f["key"]] = opts
            cur = st.session_state.get(f["key"])
            if f.get("single"):
                if cur not in (None, "All") and cur not in opts:
                    st.session_state[f["key"]] = "All"
            elif cur is not None:
                st.session_state[f["key"]] = [v for v in cur if v in opts]

    cols = cols or st.columns(len(facets))
    for f, c in zip(facets, cols):
        if f.get("single"):
            c.selectbox(f["label"], ["All"] + options[f["key"]], key=f["key"], help=f.get("help"))
        else:
            c.multiselect(f["label"], options[f["key"]], key=f["key"], help=f.get("help"))

    return lambda r: passes(r)


def go_invoice(project_id: int, occurrence_id: int | None = None) -> None:
    """Open Generate Invoice pre-filled for a project (and optionally a recurring-fee occurrence)."""
    st.session_state["gi_prefill"] = {"project_id": project_id, "occurrence_id": occurrence_id}
    st.switch_page("pages/0_generate_invoice.py")
