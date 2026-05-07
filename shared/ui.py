"""
Shared Streamlit UI helpers used across multiple pages.
"""
import streamlit as st
import pandas as pd


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
