"""
Page 8 — Data Tables.

Direct view of all underlying database tables for inspection.
Includes an "Open DB folder" button and DB Browser for SQLite recommendation.
"""
import sys
import os
import subprocess
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from shared.config import DB_PATH

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

st.title("Data Tables")

# ------------------------------------------------------------------
# DB location + open button
# ------------------------------------------------------------------

st.subheader("Database Location")
st.code(DB_PATH)
st.caption(
    "Edit the database directly in **DB Browser for SQLite** "
    "([download here](https://sqlitebrowser.org/dl/) if not installed). "
    "The button below opens the file directly in DB Browser."
)

btn1, btn2 = st.columns(2)

with btn1:
    if st.button("Open in DB Browser for SQLite"):
        exe_candidates = [
            r"C:\Program Files\DB Browser for SQLite\DB Browser for SQLite.exe",
            r"C:\Program Files (x86)\DB Browser for SQLite\DB Browser for SQLite.exe",
        ]
        exe = next((p for p in exe_candidates if os.path.exists(p)), None)
        if exe:
            try:
                subprocess.Popen([exe, DB_PATH])
                st.success("Opening DB Browser…")
            except Exception as e:
                st.error(f"Could not launch DB Browser: {e}")
        else:
            st.error("DB Browser for SQLite not found. Download it from https://sqlitebrowser.org/dl/")

with btn2:
    if st.button("Open DB folder in File Explorer"):
        folder = os.path.dirname(DB_PATH)
        try:
            subprocess.Popen(["explorer", folder])
            st.success(f"Opened: {folder}")
        except Exception as e:
            st.error(f"Could not open folder: {e}")

st.divider()

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _query(sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def _show_table(df: pd.DataFrame, key: str) -> None:
    n_total = len(df)
    show_all = st.checkbox("Show all rows", key=f"showall_{key}")
    limit = st.slider("Rows to show", 10, 200, 50, key=f"limit_{key}") if not show_all else n_total
    st.dataframe(df.head(limit), use_container_width=True)
    st.caption(f"Showing {min(limit, n_total)} of {n_total} rows. "
               "Edit directly in DB Browser for SQLite (link above).")


# ------------------------------------------------------------------
# Tabs
# ------------------------------------------------------------------

tabs = st.tabs(["Clients", "Projects", "Project Codes", "Invoices",
                "Time Entries", "Write-offs", "Pipeline"])

with tabs[0]:
    st.subheader("Clients")
    df = _query("SELECT id, name, name_for_invoices, client_code, vat_number, created_at "
                "FROM clients ORDER BY name")
    _show_table(df, "clients")

with tabs[1]:
    st.subheader("Projects")
    df = _query("""
        SELECT p.id, c.name AS client, p.name, p.description, p.vat_pct, p.template, p.status
        FROM projects p JOIN clients c ON c.id = p.client_id
        ORDER BY c.name, p.name
    """)
    _show_table(df, "projects")

with tabs[2]:
    st.subheader("Project Codes")
    df = _query("""
        SELECT pc.id, c.name AS client, p.name AS project,
               pc.client_code, pc.client_suffix, pc.budget_amount, pc.status
        FROM project_codes pc
        JOIN projects p ON p.id = pc.project_id
        JOIN clients c ON c.id = p.client_id
        ORDER BY c.name, pc.client_code, pc.client_suffix
    """)
    _show_table(df, "project_codes")

with tabs[3]:
    st.subheader("Invoices")
    df = _query("""
        SELECT i.id, i.year, i.date, i.invoice_number, c.name AS client, i.project_name,
               i.amount, i.vat_pct, i.vat_amount, i.expenses_net, i.expenses_vat,
               i.format, i.file_path
        FROM invoices i JOIN clients c ON c.id = i.client_id
        ORDER BY i.year DESC, i.invoice_number DESC
    """)
    _show_table(df, "invoices")

with tabs[4]:
    st.subheader("Time Entries")
    df = _query("""
        SELECT te.id, te.period, te.emp_nbr, te.consultant,
               te.client_code, te.client_suffix,
               te.non_z_hours AS billable_hrs, te.non_z_charges AS billable_chg,
               te.z_hours AS internal_hrs, te.z_charges AS internal_chg,
               te.batch_ref
        FROM time_entries te
        ORDER BY te.period DESC, te.consultant
    """)
    _show_table(df, "time_entries")

with tabs[5]:
    st.subheader("Write-offs")
    df = _query("""
        SELECT wo.id, c.name AS client, p.name AS project,
               wo.consultant, wo.amount, wo.reason, wo.allocation_type,
               wo.reversed, wo.reversed_reason, wo.created_at
        FROM write_offs wo
        JOIN projects p ON p.id = wo.project_id
        JOIN clients c ON c.id = p.client_id
        ORDER BY wo.created_at DESC
    """)
    _show_table(df, "write_offs")

with tabs[6]:
    st.subheader("Pipeline")
    df = _query("""
        SELECT pl.id, c.name AS client, p.name AS project,
               pl.stage, pl.value, pl.notes, pl.updated_at
        FROM pipeline pl
        JOIN projects p ON p.id = pl.project_id
        JOIN clients c ON c.id = p.client_id
        ORDER BY pl.stage, c.name
    """)
    _show_table(df, "pipeline")
