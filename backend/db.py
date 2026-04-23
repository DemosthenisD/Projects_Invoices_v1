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
import re
from shared.models import Client, Address, Project, Invoice, InvoiceAllocation, PipelineEntry, ProjectCode, TimeEntry, WriteOff
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
                template_used   TEXT    DEFAULT '',
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
                budget_min  REAL    DEFAULT 0.0,
                budget_est  REAL    DEFAULT 0.0,
                budget_max  REAL    DEFAULT 0.0,
                probability REAL    DEFAULT 0.5,
                notes       TEXT    DEFAULT '',
                updated_at  TEXT    DEFAULT (datetime('now')),
                UNIQUE(project_id)
            );

            -- Columns added in Sprint 8 (ALTER TABLE used for existing DBs below)
            -- budget_min, budget_est, budget_max, probability on pipeline

            CREATE TABLE IF NOT EXISTS project_codes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                client_code    TEXT    NOT NULL,
                client_suffix  TEXT    NOT NULL,
                name           TEXT    DEFAULT '',
                description    TEXT    DEFAULT '',
                budget_amount  REAL    DEFAULT 0.0,
                status         TEXT    DEFAULT 'Active',
                date_start     TEXT    NOT NULL DEFAULT '',
                date_end       TEXT    NOT NULL DEFAULT '',
                created_at     TEXT    DEFAULT (datetime('now')),
                UNIQUE(client_code, client_suffix, date_start)
            );

            CREATE TABLE IF NOT EXISTS invoice_allocations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id      INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                project_code_id INTEGER NOT NULL REFERENCES project_codes(id),
                amount          REAL    NOT NULL,
                created_at      TEXT    DEFAULT (datetime('now')),
                UNIQUE(invoice_id, project_code_id)
            );

            CREATE TABLE IF NOT EXISTS time_entries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                project_code_id INTEGER REFERENCES project_codes(id) ON DELETE SET NULL,
                project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                period          TEXT    NOT NULL,
                emp_nbr         TEXT    NOT NULL,
                consultant      TEXT    NOT NULL,
                client_code     TEXT    NOT NULL,
                client_suffix   TEXT    NOT NULL,
                total_hours     REAL    DEFAULT 0.0,
                non_z_hours     REAL    DEFAULT 0.0,
                z_hours         REAL    DEFAULT 0.0,
                total_charges   REAL    DEFAULT 0.0,
                non_z_charges   REAL    DEFAULT 0.0,
                z_charges       REAL    DEFAULT 0.0,
                description     TEXT    DEFAULT '',
                batch_ref       TEXT    DEFAULT '',
                created_at      TEXT    DEFAULT (datetime('now')),
                UNIQUE(period, emp_nbr, client_code, client_suffix)
            );

            CREATE TABLE IF NOT EXISTS consultant_groups (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_nbr    TEXT,
                consultant TEXT NOT NULL,
                group_name TEXT NOT NULL DEFAULT 'Other'
            );

            CREATE TABLE IF NOT EXISTS write_offs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                project_code_id INTEGER REFERENCES project_codes(id) ON DELETE SET NULL,
                emp_nbr         TEXT    DEFAULT '',
                consultant      TEXT    DEFAULT '',
                amount          REAL    NOT NULL,
                reason          TEXT    NOT NULL,
                notes           TEXT    DEFAULT '',
                allocation_type TEXT    DEFAULT 'project',
                reversed        INTEGER DEFAULT 0,
                reversed_reason TEXT    DEFAULT '',
                reversed_at     TEXT    DEFAULT '',
                created_at      TEXT    DEFAULT (datetime('now'))
            );
        """)
        # --- Migration: pipeline budget columns ---
        for col, defval in [
            ("budget_min",  "0.0"),
            ("budget_est",  "0.0"),
            ("budget_max",  "0.0"),
            ("probability", "0.5"),
        ]:
            try:
                conn.execute(f"ALTER TABLE pipeline ADD COLUMN {col} REAL DEFAULT {defval}")
            except Exception:
                pass

        # --- Migration: project_codes date columns ---
        for col in ("date_start", "date_end"):
            try:
                conn.execute(f"ALTER TABLE project_codes ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass

        # --- Migration: project_codes UNIQUE constraint (client_code, client_suffix) → add date_start ---
        _pc_schema = (conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='project_codes'"
        ).fetchone() or [None])[0] or ""
        if re.search(r"UNIQUE\s*\(\s*client_code\s*,\s*client_suffix\s*\)", _pc_schema):
            conn.executescript("""
                PRAGMA foreign_keys = OFF;
                CREATE TABLE project_codes_new (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    client_code    TEXT    NOT NULL,
                    client_suffix  TEXT    NOT NULL,
                    name           TEXT    DEFAULT '',
                    description    TEXT    DEFAULT '',
                    budget_amount  REAL    DEFAULT 0.0,
                    status         TEXT    DEFAULT 'Active',
                    date_start     TEXT    NOT NULL DEFAULT '',
                    date_end       TEXT    NOT NULL DEFAULT '',
                    created_at     TEXT    DEFAULT (datetime('now')),
                    UNIQUE(client_code, client_suffix, date_start)
                );
                INSERT INTO project_codes_new
                    (id, project_id, client_code, client_suffix, name, description,
                     budget_amount, status, date_start, date_end, created_at)
                    SELECT id, project_id, client_code, client_suffix, name, description,
                           budget_amount, status,
                           COALESCE(date_start, ''), COALESCE(date_end, ''), created_at
                    FROM project_codes;
                DROP TABLE project_codes;
                ALTER TABLE project_codes_new RENAME TO project_codes;
                PRAGMA foreign_keys = ON;
            """)

        # --- Migration: invoices.template → invoices.template_used ---
        _inv_schema = (conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='invoices'"
        ).fetchone() or [None])[0] or ""
        if "template_used" not in _inv_schema:
            try:
                conn.execute("ALTER TABLE invoices RENAME COLUMN template TO template_used")
            except Exception:
                pass

        # --- Migration: normalise stale template values in projects ---
        conn.execute(
            "UPDATE projects SET template = 'template1_v3' WHERE template IN ('Template-1', 'template1')"
        )
        conn.execute(
            "UPDATE projects SET template = 'template2_v3' WHERE template = 'Template-2'"
        )


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
        "vat_amount, vat_pct, address, project_name, description, template_used, format, "
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
    template_used: str = "",
    fmt: str = "PDF",
    file_path: str = "",
    expenses_net: float = 0.0,
    expenses_vat: float = 0.0,
    allocations: list[dict] | None = None,
) -> int:
    """Insert invoice and write allocation rows.

    allocations: list of {project_code_id, amount} (net amounts summing to invoice amount).
    If None and project_id is given, pro-rata allocation across project codes is computed automatically.
    """
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO invoices "
            "(client_id, project_id, invoice_number, year, date, amount, vat_amount, "
            "vat_pct, address, project_name, description, template_used, format, file_path, "
            "expenses_net, expenses_vat) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (client_id, project_id or None, invoice_number, year, date, amount,
             vat_amount, vat_pct, address, project_name, description, template_used,
             fmt, file_path, expenses_net, expenses_vat)
        )
        invoice_id = cur.lastrowid

    # Resolve allocations
    if project_id:
        if allocations is None:
            allocations = compute_prorata_allocations(project_id, amount)
        if allocations:
            upsert_invoice_allocations(invoice_id, allocations)

    return invoice_id


def get_next_invoice_number(year: int) -> int:
    """Returns the next sequential invoice number for the given year."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM invoices WHERE year = ?", (year,)
        ).fetchone()
    return (row["cnt"] or 0) + 1


def get_invoice_allocations(invoice_id: int) -> list[InvoiceAllocation]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, invoice_id, project_code_id, amount, created_at "
            "FROM invoice_allocations WHERE invoice_id = ? ORDER BY project_code_id",
            (invoice_id,)
        ).fetchall()
    return [InvoiceAllocation(**dict(r)) for r in rows]


def upsert_invoice_allocations(invoice_id: int, allocations: list[dict]) -> None:
    """Replace all allocation rows for this invoice with the given list.

    Each dict must have keys: project_code_id (int), amount (float).
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM invoice_allocations WHERE invoice_id = ?", (invoice_id,))
        for a in allocations:
            conn.execute(
                "INSERT INTO invoice_allocations (invoice_id, project_code_id, amount) VALUES (?,?,?)",
                (invoice_id, a["project_code_id"], round(float(a["amount"]), 2))
            )


def compute_prorata_allocations(project_id: int, net_amount: float) -> list[dict]:
    """Return pro-rata allocation list based on each project code's budget_amount.

    Falls back to equal split if all budgets are zero.
    Only Active project codes are included.
    """
    with get_connection() as conn:
        codes = conn.execute(
            "SELECT id, budget_amount FROM project_codes WHERE project_id = ? AND status = 'Active'",
            (project_id,)
        ).fetchall()
    if not codes:
        return []
    total_budget = sum(c["budget_amount"] for c in codes)
    n = len(codes)
    result = []
    remaining = round(net_amount, 2)
    for i, c in enumerate(codes):
        if i == n - 1:
            alloc = remaining  # absorb rounding residual on last row
        elif total_budget > 0:
            alloc = round(net_amount * c["budget_amount"] / total_budget, 2)
        else:
            alloc = round(net_amount / n, 2)
        remaining = round(remaining - alloc, 2)
        result.append({"project_code_id": c["id"], "amount": alloc})
    return result


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------

def get_pipeline() -> list[dict]:
    """Returns pipeline entries joined with project and client names."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT pl.id, pl.project_id, pl.stage, pl.value,
                   pl.budget_min, pl.budget_est, pl.budget_max, pl.probability,
                   pl.notes, pl.updated_at,
                   pr.name AS project_name, pr.status AS project_status,
                   c.name AS client_name
            FROM pipeline pl
            JOIN projects pr ON pr.id = pl.project_id
            JOIN clients c ON c.id = pr.client_id
            ORDER BY pl.stage, c.name
        """).fetchall()
    return [dict(r) for r in rows]


def upsert_pipeline(project_id: int, stage: str = "Prospect",
                    value: float = 0.0, notes: str = "",
                    budget_min: float = 0.0, budget_est: float = 0.0,
                    budget_max: float = 0.0, probability: float = 0.5) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO pipeline "
            "(project_id, stage, value, budget_min, budget_est, budget_max, probability, notes, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET "
            "stage=excluded.stage, value=excluded.value, "
            "budget_min=excluded.budget_min, budget_est=excluded.budget_est, "
            "budget_max=excluded.budget_max, probability=excluded.probability, "
            "notes=excluded.notes, updated_at=excluded.updated_at",
            (project_id, stage, value, budget_min, budget_est, budget_max, probability, notes, now)
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


# ---------------------------------------------------------------------------
# Project Code CRUD
# ---------------------------------------------------------------------------

def get_project_codes(project_id: int | None = None, status: str | None = None) -> list[ProjectCode]:
    query = (
        "SELECT id, project_id, client_code, client_suffix, name, description, "
        "budget_amount, status, date_start, date_end, created_at FROM project_codes"
    )
    params: list = []
    filters = []
    if project_id is not None:
        filters.append("project_id = ?")
        params.append(project_id)
    if status is not None:
        filters.append("status = ?")
        params.append(status)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY client_code, client_suffix, date_start"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [ProjectCode(**dict(r)) for r in rows]


def get_project_code_by_keys(client_code: str, client_suffix: str,
                              period: str | None = None) -> ProjectCode | None:
    """Lookup a project code by client_code + client_suffix.

    When period (YYYYMM) is given, uses date-range matching to find the correct
    code when the same suffix has been reused across multiple projects over time.
    Without period, returns the open-ended code (date_start = '').
    """
    _SELECT = (
        "SELECT id, project_id, client_code, client_suffix, name, description, "
        "budget_amount, status, date_start, date_end, created_at FROM project_codes "
    )
    with get_connection() as conn:
        if period:
            period_date = f"{period[:4]}-{period[4:]}-01"
            row = conn.execute(
                _SELECT +
                "WHERE client_code = ? AND client_suffix = ? "
                "AND (date_start = '' OR date_start <= ?) "
                "AND (date_end   = '' OR date_end   >= ?) "
                "ORDER BY date_start DESC LIMIT 1",
                (client_code, client_suffix, period_date, period_date)
            ).fetchone()
        else:
            row = conn.execute(
                _SELECT + "WHERE client_code = ? AND client_suffix = ? AND date_start = ''",
                (client_code, client_suffix)
            ).fetchone()
    return ProjectCode(**dict(row)) if row else None


def add_project_code(project_id: int, client_suffix: str,
                     name: str = "", description: str = "",
                     budget_amount: float = 0.0, status: str = "Active",
                     date_start: str = "", date_end: str = "") -> int:
    """Add a project code. client_code is derived from the project's parent client."""
    with get_connection() as conn:
        client_row = conn.execute(
            "SELECT c.client_code FROM projects p JOIN clients c ON c.id = p.client_id WHERE p.id = ?",
            (project_id,)
        ).fetchone()
        if not client_row:
            raise ValueError(f"Project {project_id} not found.")
        client_code = client_row["client_code"]
        cur = conn.execute(
            "INSERT OR IGNORE INTO project_codes "
            "(project_id, client_code, client_suffix, name, description, budget_amount, status, date_start, date_end) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, client_code, client_suffix, name, description, budget_amount, status, date_start, date_end)
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM project_codes WHERE client_code = ? AND client_suffix = ? AND date_start = ?",
            (client_code, client_suffix, date_start)
        ).fetchone()
        return row["id"]


def update_project_code(code_id: int, name: str, description: str,
                        budget_amount: float, status: str,
                        date_start: str = "", date_end: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE project_codes SET name=?, description=?, budget_amount=?, status=?, "
            "date_start=?, date_end=? WHERE id=?",
            (name, description, budget_amount, status, date_start, date_end, code_id)
        )


def delete_project_code(code_id: int) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM time_entries WHERE project_code_id = ?", (code_id,)
        ).fetchone()
        if row["cnt"] > 0:
            raise ValueError("Cannot delete project code with existing time entries.")
        conn.execute("DELETE FROM project_codes WHERE id=?", (code_id,))


# ---------------------------------------------------------------------------
# Time Entry CRUD
# ---------------------------------------------------------------------------

def add_time_entries_bulk(entries: list[dict]) -> dict:
    """Insert time entries from a parsed CSV import.

    Returns {inserted, skipped, unmatched} counts.
    Unmatched rows (no project_code found) are not stored.
    Duplicate rows (same period+emp_nbr+client_code+client_suffix) are skipped.
    """
    inserted = skipped = unmatched = 0
    with get_connection() as conn:
        for e in entries:
            cc, cs = e["client_code"], e["client_suffix"]
            period = str(e.get("period", ""))
            period_date = f"{period[:4]}-{period[4:]}-01" if len(period) == 6 else ""
            pc_row = conn.execute(
                "SELECT id, project_id FROM project_codes "
                "WHERE client_code=? AND client_suffix=? "
                "AND (date_start = '' OR date_start <= ?) "
                "AND (date_end   = '' OR date_end   >= ?) "
                "ORDER BY date_start DESC LIMIT 1",
                (cc, cs, period_date, period_date)
            ).fetchone()
            if pc_row is None:
                unmatched += 1
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO time_entries "
                "(project_code_id, project_id, period, emp_nbr, consultant, "
                "client_code, client_suffix, total_hours, non_z_hours, z_hours, "
                "total_charges, non_z_charges, z_charges, description, batch_ref) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    pc_row["id"], pc_row["project_id"],
                    str(e["period"]), str(e["emp_nbr"]), e.get("consultant", ""),
                    cc, cs,
                    float(e.get("total_hours", 0)),
                    float(e.get("non_z_hours", 0)),
                    float(e.get("z_hours", 0)),
                    float(e.get("total_charges", 0)),
                    float(e.get("non_z_charges", 0)),
                    float(e.get("z_charges", 0)),
                    e.get("description", ""),
                    e.get("batch_ref", ""),
                )
            )
            if cur.lastrowid:
                inserted += 1
            else:
                skipped += 1
    return {"inserted": inserted, "skipped": skipped, "unmatched": unmatched}


def get_time_entries(
    project_id: int | None = None,
    project_code_id: int | None = None,
    period_from: str | None = None,
    period_to: str | None = None,
    emp_nbr: str | None = None,
    include_internal: bool = True,
) -> list[TimeEntry]:
    query = (
        "SELECT id, project_code_id, project_id, period, emp_nbr, consultant, "
        "client_code, client_suffix, total_hours, non_z_hours, z_hours, "
        "total_charges, non_z_charges, z_charges, description, batch_ref, created_at "
        "FROM time_entries"
    )
    params: list = []
    filters = []
    if project_id is not None:
        filters.append("project_id = ?")
        params.append(project_id)
    if project_code_id is not None:
        filters.append("project_code_id = ?")
        params.append(project_code_id)
    if period_from:
        filters.append("period >= ?")
        params.append(period_from)
    if period_to:
        filters.append("period <= ?")
        params.append(period_to)
    if emp_nbr:
        filters.append("emp_nbr = ?")
        params.append(emp_nbr)
    if not include_internal:
        filters.append("non_z_charges > 0")
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY period DESC, client_code, client_suffix, consultant"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [TimeEntry(**{k: (v or 0 if k in (
        "project_code_id", "project_id", "total_hours", "non_z_hours", "z_hours",
        "total_charges", "non_z_charges", "z_charges"
    ) else v) for k, v in dict(r).items()}) for r in rows]


def delete_time_batch(batch_ref: str) -> int:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM time_entries WHERE batch_ref = ?", (batch_ref,))
        return cur.rowcount


def get_time_summary(project_id: int) -> list[dict]:
    """Per project-code rollup: budget, billable hours/charges, write-offs, net."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                pc.id              AS project_code_id,
                pc.client_code,
                pc.client_suffix,
                pc.name,
                pc.budget_amount,
                COALESCE(SUM(te.total_hours), 0)    AS total_hours,
                COALESCE(SUM(te.non_z_hours), 0)    AS non_z_hours,
                COALESCE(SUM(te.non_z_charges), 0)  AS non_z_charges,
                COALESCE(SUM(CASE WHEN wo.reversed=0 THEN wo.amount ELSE 0 END), 0) AS write_off_amount
            FROM project_codes pc
            LEFT JOIN time_entries te ON te.project_code_id = pc.id
            LEFT JOIN write_offs wo   ON wo.project_code_id = pc.id
            WHERE pc.project_id = ?
            GROUP BY pc.id
            ORDER BY pc.client_code, pc.client_suffix
        """, (project_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["net_charges"] = d["non_z_charges"] - d["write_off_amount"]
        result.append(d)
    return result


def get_project_time_totals(project_id: int) -> dict:
    """Project-level rollup of time charges, invoiced amounts, and write-offs."""
    with get_connection() as conn:
        te = conn.execute(
            "SELECT COALESCE(SUM(non_z_charges), 0) AS billable, "
            "COALESCE(SUM(total_charges), 0) AS total "
            "FROM time_entries WHERE project_id = ?", (project_id,)
        ).fetchone()
        wo = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS write_offs "
            "FROM write_offs WHERE project_id = ? AND reversed = 0", (project_id,)
        ).fetchone()
        inv = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS invoiced "
            "FROM invoices WHERE project_id = ?", (project_id,)
        ).fetchone()
    billable = te["billable"]
    write_offs = wo["write_offs"]
    return {
        "billable_charges": billable,
        "write_offs": write_offs,
        "net_charges": billable - write_offs,
        "invoiced": inv["invoiced"],
    }


def get_all_projects_overview() -> list[dict]:
    """Single query returning rolled-up financials for every project."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                p.id              AS project_id,
                c.name            AS client,
                c.client_code,
                p.name            AS project,
                p.status,
                COUNT(DISTINCT pc.id)                                              AS code_count,
                COALESCE(SUM(DISTINCT pc.budget_amount), 0)                        AS budget,
                COALESCE(te_sum.billable_charges, 0)                               AS billable_charges,
                COALESCE(wo_sum.write_offs, 0)                                     AS write_offs,
                COALESCE(inv_sum.invoiced, 0)                                      AS invoiced
            FROM projects p
            JOIN clients c ON c.id = p.client_id
            LEFT JOIN project_codes pc ON pc.project_id = p.id
            LEFT JOIN (
                SELECT project_id, SUM(non_z_charges) AS billable_charges
                FROM time_entries GROUP BY project_id
            ) te_sum ON te_sum.project_id = p.id
            LEFT JOIN (
                SELECT project_id, SUM(amount) AS write_offs
                FROM write_offs WHERE reversed = 0 GROUP BY project_id
            ) wo_sum ON wo_sum.project_id = p.id
            LEFT JOIN (
                SELECT project_id, SUM(amount) AS invoiced
                FROM invoices GROUP BY project_id
            ) inv_sum ON inv_sum.project_id = p.id
            GROUP BY p.id
            ORDER BY c.name, p.name
        """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["net_charges"] = d["billable_charges"] - d["write_offs"]
        d["remaining"] = d["budget"] - d["invoiced"]
        prefix = (d.get("client_code") or "")[:4]
        if prefix == "0478":
            d["project_source"] = "CY"
        elif prefix == "0009":
            d["project_source"] = "NotBillable"
        else:
            d["project_source"] = "Other"
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Write-off CRUD
# ---------------------------------------------------------------------------

def add_write_off_project(project_id: int, amount: float,
                          reason: str, notes: str = "") -> list[int]:
    """Allocate a project-level write-off pro-rata across (project_code, consultant) pairs."""
    with get_connection() as conn:
        groups = conn.execute(
            "SELECT project_code_id, emp_nbr, consultant, SUM(non_z_charges) AS charges "
            "FROM time_entries WHERE project_id = ? AND non_z_charges > 0 "
            "GROUP BY project_code_id, emp_nbr, consultant",
            (project_id,)
        ).fetchall()

    if not groups:
        raise ValueError("No billable time entries found for this project — cannot allocate pro-rata.")

    total_charges = sum(g["charges"] for g in groups)
    ids = []
    with get_connection() as conn:
        for g in groups:
            share = round(amount * g["charges"] / total_charges, 2)
            cur = conn.execute(
                "INSERT INTO write_offs "
                "(project_id, project_code_id, emp_nbr, consultant, amount, reason, notes, allocation_type) "
                "VALUES (?,?,?,?,?,?,?,'project')",
                (project_id, g["project_code_id"], g["emp_nbr"], g["consultant"],
                 share, reason, notes)
            )
            ids.append(cur.lastrowid)
    return ids


def add_write_off_adhoc(project_id: int, project_code_id: int,
                        emp_nbr: str, consultant: str,
                        amount: float, reason: str, notes: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO write_offs "
            "(project_id, project_code_id, emp_nbr, consultant, amount, reason, notes, allocation_type) "
            "VALUES (?,?,?,?,?,?,?,'adhoc')",
            (project_id, project_code_id, emp_nbr, consultant, amount, reason, notes)
        )
        return cur.lastrowid


def get_write_offs(project_id: int | None = None, include_reversed: bool = False) -> list[WriteOff]:
    query = (
        "SELECT id, project_id, project_code_id, emp_nbr, consultant, amount, reason, notes, "
        "allocation_type, reversed, reversed_reason, reversed_at, created_at FROM write_offs"
    )
    params: list = []
    filters = []
    if project_id is not None:
        filters.append("project_id = ?")
        params.append(project_id)
    if not include_reversed:
        filters.append("reversed = 0")
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [WriteOff(**{k: (v or 0 if k in ("project_code_id",) else v)
                        for k, v in dict(r).items()}) for r in rows]


def reverse_write_off(write_off_id: int, reason: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE write_offs SET reversed=1, reversed_reason=?, reversed_at=? WHERE id=?",
            (reason, now, write_off_id)
        )


# ---------------------------------------------------------------------------
# Consultant Groups CRUD
# ---------------------------------------------------------------------------

def get_consultant_groups() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, emp_nbr, consultant, group_name FROM consultant_groups ORDER BY consultant"
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_consultant_group(consultant: str, group_name: str,
                            emp_nbr: str | None = None) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM consultant_groups WHERE consultant = ?", (consultant,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE consultant_groups SET group_name=?, emp_nbr=COALESCE(?,emp_nbr) WHERE id=?",
                (group_name, emp_nbr, row["id"])
            )
        else:
            conn.execute(
                "INSERT INTO consultant_groups (consultant, group_name, emp_nbr) VALUES (?,?,?)",
                (consultant, group_name, emp_nbr)
            )


def ensure_consultant_group(emp_nbr: str, consultant: str) -> None:
    """Called on time-entry import to create a group row if not already present."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM consultant_groups WHERE consultant = ?", (consultant,)
        ).fetchone()
        if row:
            # Update emp_nbr if not yet set
            conn.execute(
                "UPDATE consultant_groups SET emp_nbr=? WHERE id=? AND emp_nbr IS NULL",
                (emp_nbr, row["id"])
            )
        else:
            conn.execute(
                "INSERT INTO consultant_groups (consultant, group_name, emp_nbr) VALUES (?,?,?)",
                (consultant, "Other", emp_nbr)
            )


def get_time_summary_by_group(project_id: int) -> list[dict]:
    """Billable charges grouped by Local/ICEE/Other for a project."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                COALESCE(cg.group_name, 'Other') AS group_name,
                SUM(te.non_z_hours)   AS billable_hrs,
                SUM(te.non_z_charges) AS billable_chg
            FROM time_entries te
            LEFT JOIN consultant_groups cg ON cg.consultant = te.consultant
            WHERE te.project_id = ?
            GROUP BY group_name
            ORDER BY group_name
        """, (project_id,)).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at: {DB_PATH}")
