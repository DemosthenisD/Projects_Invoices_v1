"""
SQLite data access layer for InvoiceApp.

All database interactions go through this module.
Tables are created on first run via init_db().
"""
import sqlite3
import sys
import os
from contextlib import contextmanager
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.models import Client, Address, Project, Invoice, PipelineEntry
from shared.config import DB_PATH


@contextmanager
def get_connection():
    """Yield an open SQLite connection with row_factory set."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                name               TEXT    NOT NULL UNIQUE,
                name_for_invoices  TEXT    NOT NULL DEFAULT '',
                client_code        TEXT    DEFAULT '',
                vat_number         TEXT    DEFAULT '',
                created_at         TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS addresses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                address    TEXT    NOT NULL,
                UNIQUE(client_id, address)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                name        TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                vat_pct     REAL    DEFAULT 19.0,
                template    TEXT    DEFAULT 'template1_v3',
                status      TEXT    DEFAULT 'Active',
                UNIQUE(client_id, name)
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id       INTEGER NOT NULL REFERENCES clients(id),
                project_id      INTEGER REFERENCES projects(id),
                invoice_number  TEXT    NOT NULL,
                year            INTEGER NOT NULL,
                date            TEXT    NOT NULL,
                amount          REAL    NOT NULL,
                vat_amount      REAL    NOT NULL DEFAULT 0.0,
                vat_pct         REAL    DEFAULT 19.0,
                address         TEXT    DEFAULT '',
                project_name    TEXT    DEFAULT '',
                description     TEXT    DEFAULT '',
                template        TEXT    DEFAULT '',
                format          TEXT    DEFAULT 'PDF',
                file_path       TEXT    DEFAULT '',
                expenses_net    REAL    DEFAULT 0.0,
                expenses_vat    REAL    DEFAULT 0.0,
                created_at      TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS pipeline (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                stage       TEXT    DEFAULT 'Prospect',
                value       REAL    DEFAULT 0.0,
                notes       TEXT    DEFAULT '',
                updated_at  TEXT    DEFAULT (datetime('now')),
                UNIQUE(project_id)
            );
        """)


# ---------------------------------------------------------------------------
# Client CRUD
# ---------------------------------------------------------------------------

def get_clients() -> list[Client]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, name_for_invoices, client_code, vat_number, created_at "
            "FROM clients ORDER BY name"
        ).fetchall()
    return [Client(**dict(r)) for r in rows]


def get_client_by_name(name: str) -> Client | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, name_for_invoices, client_code, vat_number, created_at "
            "FROM clients WHERE name = ?", (name,)
        ).fetchone()
    return Client(**dict(row)) if row else None


def add_client(name: str, name_for_invoices: str = "", client_code: str = "",
               vat_number: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO clients (name, name_for_invoices, client_code, vat_number) "
            "VALUES (?, ?, ?, ?)",
            (name, name_for_invoices or name, client_code, vat_number)
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM clients WHERE name = ?", (name,)).fetchone()
        return row["id"]


def update_client(client_id: int, name_for_invoices: str, client_code: str,
                  vat_number: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE clients SET name_for_invoices=?, client_code=?, vat_number=? "
            "WHERE id=?",
            (name_for_invoices, client_code, vat_number, client_id)
        )


def delete_client(client_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM clients WHERE id=?", (client_id,))


# ---------------------------------------------------------------------------
# Address CRUD
# ---------------------------------------------------------------------------

def get_addresses(client_id: int) -> list[Address]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, client_id, address FROM addresses WHERE client_id=? ORDER BY address",
            (client_id,)
        ).fetchall()
    return [Address(**dict(r)) for r in rows]


def add_address(client_id: int, address: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO addresses (client_id, address) VALUES (?, ?)",
            (client_id, address)
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM addresses WHERE client_id=? AND address=?",
            (client_id, address)
        ).fetchone()
        return row["id"]


def delete_address(address_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM addresses WHERE id=?", (address_id,))


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

def get_projects(client_id: int | None = None, status: str | None = None) -> list[Project]:
    query = "SELECT id, client_id, name, description, vat_pct, template, status FROM projects"
    params: list = []
    filters = []
    if client_id is not None:
        filters.append("client_id = ?")
        params.append(client_id)
    if status is not None:
        filters.append("status = ?")
        params.append(status)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY name"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [Project(**dict(r)) for r in rows]


def add_project(client_id: int, name: str, description: str = "",
                vat_pct: float = 19.0, template: str = "template1_v3",
                status: str = "Active") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO projects "
            "(client_id, name, description, vat_pct, template, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (client_id, name, description, vat_pct, template, status)
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM projects WHERE client_id=? AND name=?",
            (client_id, name)
        ).fetchone()
        return row["id"]


def update_project(project_id: int, description: str, vat_pct: float,
                   template: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE projects SET description=?, vat_pct=?, template=?, status=? WHERE id=?",
            (description, vat_pct, template, status, project_id)
        )


def delete_project(project_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))


# ---------------------------------------------------------------------------
# Invoice CRUD
# ---------------------------------------------------------------------------

def get_invoices(
    client_id: int | None = None,
    year: int | None = None,
    project_name: str | None = None,
    search: str | None = None,
) -> list[Invoice]:
    query = (
        "SELECT id, client_id, project_id, invoice_number, year, date, amount, "
        "vat_amount, vat_pct, address, project_name, description, template, format, "
        "file_path, expenses_net, expenses_vat, created_at FROM invoices"
    )
    params: list = []
    filters = []
    if client_id is not None:
        filters.append("client_id = ?")
        params.append(client_id)
    if year is not None:
        filters.append("year = ?")
        params.append(year)
    if project_name:
        filters.append("project_name = ?")
        params.append(project_name)
    if search:
        filters.append("(invoice_number LIKE ? OR project_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY year DESC, invoice_number DESC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [Invoice(**dict(r)) for r in rows]


def add_invoice(
    client_id: int,
    invoice_number: str,
    year: int,
    date: str,
    amount: float,
    vat_amount: float,
    vat_pct: float = 19.0,
    project_id: int = 0,
    address: str = "",
    project_name: str = "",
    description: str = "",
    template: str = "",
    fmt: str = "PDF",
    file_path: str = "",
    expenses_net: float = 0.0,
    expenses_vat: float = 0.0,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO invoices "
            "(client_id, project_id, invoice_number, year, date, amount, vat_amount, "
            "vat_pct, address, project_name, description, template, format, file_path, "
            "expenses_net, expenses_vat) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (client_id, project_id or None, invoice_number, year, date, amount,
             vat_amount, vat_pct, address, project_name, description, template,
             fmt, file_path, expenses_net, expenses_vat)
        )
        return cur.lastrowid


def get_next_invoice_number(year: int) -> int:
    """Returns the next sequential invoice number for the given year."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM invoices WHERE year = ?", (year,)
        ).fetchone()
    return (row["cnt"] or 0) + 1


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------

def get_pipeline() -> list[dict]:
    """Returns pipeline entries joined with project and client names."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT pl.id, pl.project_id, pl.stage, pl.value, pl.notes, pl.updated_at,
                   pr.name AS project_name, pr.status AS project_status,
                   c.name AS client_name
            FROM pipeline pl
            JOIN projects pr ON pr.id = pl.project_id
            JOIN clients c ON c.id = pr.client_id
            ORDER BY pl.stage, c.name
        """).fetchall()
    return [dict(r) for r in rows]


def upsert_pipeline(project_id: int, stage: str = "Prospect",
                    value: float = 0.0, notes: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO pipeline (project_id, stage, value, notes, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET "
            "stage=excluded.stage, value=excluded.value, "
            "notes=excluded.notes, updated_at=excluded.updated_at",
            (project_id, stage, value, notes, now)
        )


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def get_monthly_revenue(year: int | None = None) -> list[dict]:
    query = """
        SELECT strftime('%Y-%m', date) AS month,
               SUM(amount) AS net,
               SUM(vat_amount) AS vat,
               SUM(amount + vat_amount) AS gross
        FROM invoices
    """
    params = []
    if year:
        query += " WHERE year = ?"
        params.append(year)
    query += " GROUP BY month ORDER BY month"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_revenue_by_client(year: int | None = None) -> list[dict]:
    query = """
        SELECT c.name AS client, SUM(i.amount) AS net, SUM(i.vat_amount) AS vat
        FROM invoices i
        JOIN clients c ON c.id = i.client_id
    """
    params = []
    if year:
        query += " WHERE i.year = ?"
        params.append(year)
    query += " GROUP BY c.name ORDER BY net DESC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at: {DB_PATH}")
