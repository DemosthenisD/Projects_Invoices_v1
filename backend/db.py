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
from shared.models import (
    Client, Address, Project, Invoice, InvoiceAllocation, Payment, PipelineEntry,
    ProjectCode, TimeEntry, WriteOff,
    ConsultantProfile, AnnualSalaryHistory, BillingBasis, ReviewScore,
)
from shared.config import DB_PATH, load_office_codes

# Loaded once at module import; reflects file state at server start.
# 0009 (NotBillable) is handled separately in code; not expected in this dict.
_OFFICE_CODES: dict[str, str] = load_office_codes()


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

            CREATE TABLE IF NOT EXISTS payments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                amount      REAL    NOT NULL,
                date        TEXT    NOT NULL,
                note        TEXT    DEFAULT '',
                created_at  TEXT    DEFAULT (datetime('now'))
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

            CREATE TABLE IF NOT EXISTS consultant_profiles (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_nbr          TEXT    NOT NULL UNIQUE,
                employment_date  TEXT    DEFAULT '',
                prior_exp_years  REAL    DEFAULT 0.0,
                milliman_status  TEXT    DEFAULT '',
                external_level   TEXT    DEFAULT '',
                languages        TEXT    DEFAULT '',
                tools            TEXT    DEFAULT '',
                current_role     TEXT    DEFAULT '',
                notes            TEXT    DEFAULT '',
                created_at       TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS annual_salary_history (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_nbr             TEXT    NOT NULL,
                year                INTEGER NOT NULL,
                starting_salary     REAL    DEFAULT 0.0,
                exams_passed        REAL    DEFAULT 0.0,
                exam_raise_per_exam REAL    DEFAULT 1000.0,
                other_raise         REAL    DEFAULT 0.0,
                effective_date      TEXT    DEFAULT '',
                objective_bonus_pct REAL    DEFAULT 0.0,
                bonus_paid          REAL    DEFAULT 0.0,
                proposed_rate       REAL    DEFAULT 0.0,
                notes               TEXT    DEFAULT '',
                UNIQUE(emp_nbr, year)
            );

            CREATE TABLE IF NOT EXISTS billing_basis (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_nbr              TEXT    NOT NULL,
                year                 INTEGER NOT NULL,
                source               TEXT    DEFAULT 'manual',
                billed               REAL    DEFAULT 0.0,
                capped_paid_prebill  REAL    DEFAULT 0.0,
                capped_unpaid_prebill REAL   DEFAULT 0.0,
                charged_off          REAL    DEFAULT 0.0,
                paid                 REAL    DEFAULT 0.0,
                unbilled             REAL    DEFAULT 0.0,
                hourly_rate          REAL    DEFAULT 0.0,
                notes                TEXT    DEFAULT '',
                created_at           TEXT    DEFAULT (datetime('now')),
                UNIQUE(emp_nbr, year)
            );

            CREATE TABLE IF NOT EXISTS review_scores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_nbr     TEXT    NOT NULL,
                year        INTEGER NOT NULL,
                score_group TEXT    NOT NULL,
                item_name   TEXT    NOT NULL,
                score       REAL    DEFAULT 0.0,
                UNIQUE(emp_nbr, year, score_group, item_name)
            );
            CREATE TABLE IF NOT EXISTS review_feedback (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_nbr           TEXT    NOT NULL,
                year              INTEGER NOT NULL,
                area              TEXT    NOT NULL,
                comments          TEXT    DEFAULT '',
                development_ideas TEXT    DEFAULT '',
                created_at        TEXT,
                UNIQUE(emp_nbr, year, area)
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

        # --- Migration: clients.country column ---
        for col, defval in [("client_type", "'managed'"), ("country", "''")]:
            try:
                conn.execute(f"ALTER TABLE clients ADD COLUMN {col} TEXT NOT NULL DEFAULT {defval}")
            except Exception:
                pass

        # --- Migration: invoices.status, paid_date, comment, type, related_invoice_number columns ---
        for col, defval in [
            ("status", "'outstanding'"),
            ("paid_date", "''"),
            ("comment", "''"),
            ("type", "'Invoice'"),
            ("related_invoice_number", "''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE invoices ADD COLUMN {col} TEXT NOT NULL DEFAULT {defval}")
            except Exception:
                pass

        # --- Migration: projects.date_start column ---
        try:
            conn.execute("ALTER TABLE projects ADD COLUMN date_start TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass

        # --- Migration: pipeline date tracking columns ---
        for col in ("date_entered_pipeline", "date_entered_stage"):
            try:
                conn.execute(f"ALTER TABLE pipeline ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        # Back-fill existing rows so dates are not blank
        conn.execute("""
            UPDATE pipeline SET date_entered_pipeline = date(updated_at)
            WHERE date_entered_pipeline = '' OR date_entered_pipeline IS NULL
        """)
        conn.execute("""
            UPDATE pipeline SET date_entered_stage = date(updated_at)
            WHERE date_entered_stage = '' OR date_entered_stage IS NULL
        """)

        # --- Data fix: invoices with corrupt year values ---
        # Rows where year is clearly wrong (not a plausible 4-digit year) are corrected
        # by extracting the year from the stored date string.
        conn.execute("""
            UPDATE invoices
            SET year = CAST(SUBSTR(date, 1, 4) AS INTEGER)
            WHERE (year < 2000 OR year > 2100)
              AND SUBSTR(date, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'
        """)

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

def get_clients(exclude_types: list[str] | None = None) -> list[Client]:
    """Return clients ordered by name.

    exclude_types — omit clients whose client_type is in this list.
                    e.g. ['internal'] hides 0009xxx overhead codes.
    """
    query = ("SELECT id, name, name_for_invoices, client_code, vat_number, "
             "client_type, country, created_at FROM clients")
    params: list = []
    if exclude_types:
        placeholders = ",".join("?" * len(exclude_types))
        query += f" WHERE client_type NOT IN ({placeholders})"
        params = list(exclude_types)
    query += " ORDER BY name"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [Client(**dict(r)) for r in rows]


def get_clients_with_counts(exclude_types: list[str] | None = None) -> list[dict]:
    """Return clients with project/code counts for the tabular overview."""
    base_query = """
        SELECT c.id, c.name, c.name_for_invoices, c.client_code, c.vat_number,
               c.client_type, c.country, c.created_at,
               COUNT(DISTINCT p.id)                                          AS total_projects,
               COUNT(DISTINCT CASE WHEN p.status='Active' THEN p.id END)    AS active_projects,
               COUNT(DISTINCT CASE WHEN pc.status='Active' THEN pc.id END)  AS active_codes
        FROM clients c
        LEFT JOIN projects p ON p.client_id = c.id
        LEFT JOIN project_codes pc ON pc.project_id = p.id
    """
    params: list = []
    if exclude_types:
        placeholders = ",".join("?" * len(exclude_types))
        base_query += f" WHERE c.client_type NOT IN ({placeholders})"
        params = list(exclude_types)
    base_query += " GROUP BY c.id ORDER BY c.name"
    with get_connection() as conn:
        rows = conn.execute(base_query, params).fetchall()
    return [dict(r) for r in rows]


def get_client_by_name(name: str) -> Client | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, name_for_invoices, client_code, vat_number, client_type, country, created_at "
            "FROM clients WHERE name = ?", (name,)
        ).fetchone()
    return Client(**dict(row)) if row else None


def add_client(name: str, name_for_invoices: str = "", client_code: str = "",
               vat_number: str = "", client_type: str = "managed",
               country: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO clients "
            "(name, name_for_invoices, client_code, vat_number, client_type, country) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, name_for_invoices or name, client_code, vat_number, client_type, country)
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM clients WHERE name = ?", (name,)).fetchone()
        return row["id"]


def update_client(client_id: int, name_for_invoices: str, client_code: str,
                  vat_number: str, client_type: str = "managed",
                  country: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE clients SET name_for_invoices=?, client_code=?, vat_number=?, "
            "client_type=?, country=? WHERE id=?",
            (name_for_invoices, client_code, vat_number, client_type, country, client_id)
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

def get_projects_with_summary(client_id: int | None = None) -> list[dict]:
    """Return projects with per-project financial summary columns.

    client_id=None returns all clients (adds client_name to each row).
    """
    where = "WHERE p.client_id = ?" if client_id is not None else ""
    params = (client_id,) if client_id is not None else ()
    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT
                p.id, p.name, p.status, p.date_start, p.vat_pct, p.template, p.description,
                c.name                         AS client_name,
                c.client_type                  AS client_type,
                c.country                      AS client_country,
                COALESCE(pc.code_count, 0)     AS code_count,
                COALESCE(pc.total_budget, 0)   AS total_budget,
                COALESCE(te.billable_charges, 0) AS billable_charges,
                COALESCE(wo.write_offs, 0)     AS write_offs,
                COALESCE(inv.invoiced, 0)      AS invoiced
            FROM projects p
            JOIN clients c ON c.id = p.client_id
            LEFT JOIN (SELECT project_id, COUNT(*) AS code_count, SUM(budget_amount) AS total_budget
                       FROM project_codes GROUP BY project_id) pc ON pc.project_id = p.id
            LEFT JOIN (SELECT project_id, SUM(non_z_charges) AS billable_charges
                       FROM time_entries GROUP BY project_id) te ON te.project_id = p.id
            LEFT JOIN (SELECT project_id, SUM(amount) AS write_offs
                       FROM write_offs WHERE reversed=0 GROUP BY project_id) wo ON wo.project_id = p.id
            LEFT JOIN (SELECT project_id, SUM(amount) AS invoiced
                       FROM invoices GROUP BY project_id) inv ON inv.project_id = p.id
            {where}
            ORDER BY c.name, p.name
        """, params).fetchall()
    return [dict(r) for r in rows]


def get_projects(client_id: int | None = None, status: str | None = None) -> list[Project]:
    query = ("SELECT id, client_id, name, description, vat_pct, template, status, date_start "
             "FROM projects")
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
                status: str = "Active", date_start: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO projects "
            "(client_id, name, description, vat_pct, template, status, date_start) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (client_id, name, description, vat_pct, template, status, date_start)
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM projects WHERE client_id=? AND name=?",
            (client_id, name)
        ).fetchone()
        return row["id"]


def update_project(project_id: int, description: str, vat_pct: float,
                   template: str, status: str, date_start: str = "") -> int:
    """Update project fields. Returns count of project codes auto-closed (0 if no auto-close)."""
    from datetime import date as _date
    closed_count = 0
    with get_connection() as conn:
        old = conn.execute("SELECT status FROM projects WHERE id=?", (project_id,)).fetchone()
        conn.execute(
            "UPDATE projects SET description=?, vat_pct=?, template=?, status=?, date_start=? "
            "WHERE id=?",
            (description, vat_pct, template, status, date_start, project_id)
        )
        if status == "Completed" and old and old["status"] != "Completed":
            today = _date.today().isoformat()
            cur = conn.execute(
                "UPDATE project_codes SET status='Completed', date_end=? "
                "WHERE project_id=? AND status='Active' AND date_end=''",
                (today, project_id)
            )
            closed_count = cur.rowcount
    return closed_count


def delete_project(project_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))


# ---------------------------------------------------------------------------
# Invoice CRUD
# ---------------------------------------------------------------------------

def get_invoices(
    client_id: int | None = None,
    year: int | None = None,
    project_id: int | None = None,
    project_name: str | None = None,
    search: str | None = None,
    status: str | None = None,
) -> list[Invoice]:
    base = (
        "SELECT i.id, i.client_id, i.project_id, i.invoice_number, i.year, i.date, i.amount, "
        "i.vat_amount, i.vat_pct, i.address, i.project_name, i.description, i.template_used, "
        "i.format, i.file_path, i.expenses_net, i.expenses_vat, i.status, i.paid_date, "
        "i.comment, i.type, i.related_invoice_number, i.created_at, "
        "COALESCE(py.total_paid, 0.0) AS total_paid "
        "FROM invoices i "
        "LEFT JOIN (SELECT invoice_id, SUM(amount) AS total_paid "
        "           FROM payments GROUP BY invoice_id) py ON py.invoice_id = i.id"
    )
    params: list = []
    filters = []
    if client_id is not None:
        filters.append("i.client_id = ?")
        params.append(client_id)
    if year is not None:
        filters.append("i.year = ?")
        params.append(year)
    if project_id is not None:
        filters.append("i.project_id = ?")
        params.append(project_id)
    if project_name:
        filters.append("i.project_name = ?")
        params.append(project_name)
    if search:
        filters.append("(i.invoice_number LIKE ? OR i.project_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        filters.append("i.status = ?")
        params.append(status)
    query = base + (" WHERE " + " AND ".join(filters) if filters else "")
    query += " ORDER BY i.year DESC, CAST(i.invoice_number AS INTEGER) DESC"
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
    comment: str = "",
    doc_type: str = "Invoice",
    related_invoice_number: str = "",
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
            "expenses_net, expenses_vat, comment, type, related_invoice_number) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (client_id, project_id or None, invoice_number, year, date, amount,
             vat_amount, vat_pct, address, project_name, description, template_used,
             fmt, file_path, expenses_net, expenses_vat, comment, doc_type, related_invoice_number)
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
    """Returns the next sequential invoice number for the given year.

    Uses MAX(CAST(invoice_number AS INTEGER)) scoped to year so the result is
    correct even when rows have been deleted or imported out of order.
    Numeric casting means non-numeric values (e.g. 'EXAMPLE-001') resolve to 0
    and do not affect the result.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(invoice_number AS INTEGER)) AS max_no "
            "FROM invoices WHERE year = ?",
            (year,)
        ).fetchone()
    return (row["max_no"] or 0) + 1


def update_invoice_status(invoice_id: int, status: str, paid_date: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE invoices SET status=?, paid_date=? WHERE id=?",
            (status, paid_date, invoice_id)
        )


def _recompute_invoice_status(invoice_id: int, conn) -> None:
    """Derive outstanding / partial / paid from payment records and update the invoice row."""
    inv = conn.execute(
        "SELECT amount, vat_amount, expenses_net, expenses_vat FROM invoices WHERE id=?",
        (invoice_id,)
    ).fetchone()
    if not inv:
        return
    gross = inv["amount"] + inv["vat_amount"] + inv["expenses_net"] + inv["expenses_vat"]
    if gross <= 0:
        return  # credit notes — payment tracking not applicable
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS paid, MAX(date) AS latest "
        "FROM payments WHERE invoice_id=?", (invoice_id,)
    ).fetchone()
    total_paid = row["paid"]
    latest_date = row["latest"] or ""
    if total_paid <= 0:
        status, paid_date = "outstanding", ""
    elif total_paid >= gross - 0.01:
        status, paid_date = "paid", latest_date
    else:
        status, paid_date = "partial", latest_date
    conn.execute(
        "UPDATE invoices SET status=?, paid_date=? WHERE id=?",
        (status, paid_date, invoice_id)
    )


def add_payment(invoice_id: int, amount: float, date: str, note: str = "") -> int:
    """Insert a payment record and recompute the invoice status."""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO payments (invoice_id, amount, date, note) VALUES (?,?,?,?)",
            (invoice_id, round(amount, 2), date, note)
        )
        _recompute_invoice_status(invoice_id, conn)
        return cur.lastrowid


def get_payments(invoice_id: int) -> list[Payment]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, invoice_id, amount, date, note, created_at "
            "FROM payments WHERE invoice_id=? ORDER BY date, id",
            (invoice_id,)
        ).fetchall()
    return [Payment(**dict(r)) for r in rows]


def delete_payments(invoice_id: int) -> None:
    """Delete all payment records for an invoice and reset its status to outstanding."""
    with get_connection() as conn:
        conn.execute("DELETE FROM payments WHERE invoice_id=?", (invoice_id,))
        conn.execute(
            "UPDATE invoices SET status='outstanding', paid_date='' WHERE id=?",
            (invoice_id,)
        )


def _parse_date_str(val) -> str:
    """Normalise a date value from Excel to YYYY-MM-DD string.

    Handles: Python date/datetime objects, pandas Timestamps, and text strings
    in DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY formats.
    """
    from datetime import date as _date, datetime as _dt
    import pandas as _pd
    if val is None:
        return ""
    if isinstance(val, (_date, _dt)):
        return val.strftime("%Y-%m-%d")
    try:
        if isinstance(val, _pd.Timestamp):
            return val.strftime("%Y-%m-%d")
    except Exception:
        pass
    s = str(val).strip().split(".")[0].split(" ")[0]  # strip time part
    if not s or s.lower() in ("nan", "none", ""):
        return ""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            from datetime import datetime as _dtp
            return _dtp.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s  # fall back verbatim


def bulk_import_invoices(records: list[dict]) -> dict:
    """Insert invoices from an Excel template upload.

    Each record dict should contain the columns from the template.
    Returns {inserted, skipped, errors} counts.
    Duplicates (same invoice_number + year) are skipped.
    """
    inserted = skipped = 0
    errors = []
    for rec in records:
        try:
            inv_num = str(rec.get("invoice_number", "")).strip()
            # year: prefer the auto-computed year column; fall back to parsing the date
            year_raw = rec.get("year", 0)
            try:
                year = int(float(year_raw)) if str(year_raw).strip() not in ("", "nan") else 0
            except (ValueError, TypeError):
                year = 0
            if not year:
                date_str = _parse_date_str(rec.get("date", ""))
                try:
                    year = int(date_str[:4]) if date_str else 0
                except ValueError:
                    year = 0
            if not inv_num or not year:
                errors.append(f"Row missing invoice_number or year: {rec}")
                continue
            with get_connection() as conn:
                existing = conn.execute(
                    "SELECT id FROM invoices WHERE invoice_number=? AND year=?",
                    (inv_num, year)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT INTO invoices "
                    "(client_id, project_id, invoice_number, year, date, amount, vat_amount, "
                    "vat_pct, address, project_name, description, template_used, format, "
                    "file_path, expenses_net, expenses_vat, status, paid_date, comment, "
                    "type, related_invoice_number) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        int(float(rec.get("client_id", 0) or 0)),
                        int(float(rec.get("project_id", 0) or 0)) or None,
                        inv_num, year,
                        _parse_date_str(rec.get("date", "")),
                        float(rec.get("amount", 0) or 0),
                        float(rec.get("vat_amount", 0) or 0),
                        float(rec.get("vat_pct", 19.0) or 19.0),
                        str(rec.get("address", "") or ""),
                        str(rec.get("project_name", "") or ""),
                        str(rec.get("description", "") or ""),
                        str(rec.get("template_used", "") or ""),
                        str(rec.get("format", "PDF") or "PDF"),
                        str(rec.get("file_path", "") or ""),
                        float(rec.get("expenses_net", 0) or 0),
                        float(rec.get("expenses_vat", 0) or 0),
                        str(rec.get("status", "outstanding") or "outstanding"),
                        _parse_date_str(rec.get("paid_date", "")),
                        str(rec.get("comment", "") or ""),
                        str(rec.get("type", "Invoice") or "Invoice"),
                        str(rec.get("related_invoice_number", "") or ""),
                    )
                )
                inserted += 1
        except Exception as exc:
            errors.append(f"{rec.get('invoice_number', '?')}: {exc}")
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def sync_completed_project_budgets() -> dict:
    """For completed projects whose codes all have budget_amount=0, set each code's
    budget to an equal share of the total invoiced net amount for that project.

    Skips projects with no project codes (nowhere to store a budget).
    Returns {updated: list of project names, skipped_no_codes: list, skipped_has_budget: list}.
    """
    updated: list[str] = []
    skipped_no_codes: list[str] = []
    skipped_has_budget: list[str] = []

    with get_connection() as conn:
        # Find completed projects
        completed = conn.execute(
            "SELECT id, name FROM projects WHERE status = 'Completed'"
        ).fetchall()

        for proj in completed:
            proj_id, proj_name = proj["id"], proj["name"]

            # Sum invoiced net amount (credit notes already stored negative)
            inv_row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM invoices WHERE project_id = ?",
                (proj_id,)
            ).fetchone()
            total_invoiced = inv_row["total"]
            if total_invoiced <= 0:
                continue  # nothing invoiced, skip

            # Get codes
            codes = conn.execute(
                "SELECT id, budget_amount FROM project_codes WHERE project_id = ?",
                (proj_id,)
            ).fetchall()

            if not codes:
                skipped_no_codes.append(proj_name)
                continue

            # Check if any code already has a non-zero budget
            if any(c["budget_amount"] != 0 for c in codes):
                skipped_has_budget.append(proj_name)
                continue

            # Equal split across codes
            per_code = round(total_invoiced / len(codes), 2)
            for c in codes:
                conn.execute(
                    "UPDATE project_codes SET budget_amount = ? WHERE id = ?",
                    (per_code, c["id"])
                )
            updated.append(proj_name)

    return {
        "updated": updated,
        "skipped_no_codes": skipped_no_codes,
        "skipped_has_budget": skipped_has_budget,
    }


def get_all_project_codes_with_context() -> list[dict]:
    """Return all active project codes joined with project and client info.

    Used to populate the Project Codes Reference sheet in the bulk upload template.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT pc.id, pc.client_code, pc.client_suffix, pc.name AS code_name,
                   pc.budget_amount, pc.status,
                   p.id AS project_id, p.name AS project_name,
                   c.id AS client_id, c.name AS client_name
            FROM project_codes pc
            JOIN projects p ON p.id = pc.project_id
            JOIN clients c ON c.id = p.client_id
            WHERE pc.status = 'Active'
            ORDER BY c.name, p.name, pc.client_code, pc.client_suffix
        """).fetchall()
    return [dict(r) for r in rows]


def get_invoice_by_number(invoice_number: str) -> dict | None:
    """Return invoice row as dict by invoice_number, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM invoices WHERE invoice_number = ? LIMIT 1",
            (invoice_number,)
        ).fetchone()
    return dict(row) if row else None


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
                   pl.date_entered_pipeline, pl.date_entered_stage,
                   pr.name AS project_name, pr.status AS project_status,
                   c.name AS client_name, c.client_type, c.country
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
    today = datetime.now(timezone.utc).date().isoformat()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT stage FROM pipeline WHERE project_id = ?", (project_id,)
        ).fetchone()
        stage_changed = existing is None or existing["stage"] != stage
        conn.execute(
            "INSERT INTO pipeline "
            "(project_id, stage, value, budget_min, budget_est, budget_max, probability, notes, "
            " updated_at, date_entered_pipeline, date_entered_stage) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET "
            "stage=excluded.stage, value=excluded.value, "
            "budget_min=excluded.budget_min, budget_est=excluded.budget_est, "
            "budget_max=excluded.budget_max, probability=excluded.probability, "
            "notes=excluded.notes, updated_at=excluded.updated_at, "
            "date_entered_stage=CASE WHEN stage != excluded.stage THEN excluded.date_entered_stage "
            "                        ELSE pipeline.date_entered_stage END",
            (project_id, stage, value, budget_min, budget_est, budget_max, probability, notes,
             now, today, today)
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


def analyse_csv_gaps(pairs: list[tuple[str, str]]) -> dict:
    """Analyse (client_code, client_suffix) pairs from a CSV upload.

    Returns a dict with three keys:
      matched        — list of (cc, cs) already in project_codes
      missing_code   — list of dicts where client exists but project code absent
                       keys: client_code, client_suffix, client_name, existing_projects
      missing_client — list of dicts where client itself is not in DB
                       keys: client_code, client_suffix, is_internal
    """
    with get_connection() as conn:
        db_clients = {
            r["client_code"]: r["name"]
            for r in conn.execute("SELECT client_code, name FROM clients").fetchall()
        }
        db_pc = {
            (r["client_code"], r["client_suffix"])
            for r in conn.execute(
                "SELECT client_code, client_suffix FROM project_codes"
            ).fetchall()
        }

        matched, missing_code, missing_client = [], [], []
        for cc, cs in pairs:
            if (cc, cs) in db_pc:
                matched.append((cc, cs))
            elif cc in db_clients:
                projects = [
                    r["name"] for r in conn.execute(
                        "SELECT p.name FROM projects p "
                        "JOIN clients c ON c.id = p.client_id "
                        "WHERE c.client_code = ? ORDER BY p.name",
                        (cc,)
                    ).fetchall()
                ]
                missing_code.append({
                    "client_code": cc,
                    "client_suffix": cs,
                    "client_name": db_clients[cc],
                    "existing_projects": projects,
                })
            else:
                missing_client.append({
                    "client_code": cc,
                    "client_suffix": cs,
                    "is_internal": cc.startswith("0009"),
                })

    return {
        "matched": matched,
        "missing_code": missing_code,
        "missing_client": missing_client,
    }


def quick_setup_external_codes(items: list[dict]) -> dict:
    """Create placeholder client, project, and project code for unknown external codes.

    Each item must have: client_code (str), client_suffix (str).
    Naming:
      client  → '{client_code}_Default_Client'   (type = external)
      project → '{client_code}_Default_Project'
      code    → suffix = client_suffix, name = '{client_code}_{suffix}_Default_SuffixCode'

    Looks up client by client_code (not name) so a previously manually-created
    client with the right code is reused rather than duplicated.
    Returns {'created_clients', 'created_projects', 'created_codes'} counts.
    """
    from collections import defaultdict
    by_client: dict[str, list[str]] = defaultdict(list)
    for item in items:
        by_client[str(item["client_code"])].append(str(item["client_suffix"]))

    created_clients = created_projects = created_codes = 0

    for client_code, suffixes in by_client.items():
        client_name  = f"{client_code}_Default_Client"
        project_name = f"{client_code}_Default_Project"

        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM clients WHERE client_code = ?", (client_code,)
            ).fetchone()
        if row:
            client_id = row["id"]
        else:
            client_id = add_client(
                name=client_name,
                name_for_invoices=client_name,
                client_code=client_code,
                client_type="external",
            )
            created_clients += 1

        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM projects WHERE client_id = ? AND name = ?",
                (client_id, project_name)
            ).fetchone()
        if row:
            project_id = row["id"]
        else:
            project_id = add_project(
                client_id=client_id,
                name=project_name,
                description=f"Auto-created placeholder for client code {client_code}",
                vat_pct=0.0,
                status="Active",
            )
            created_projects += 1

        for suffix in suffixes:
            add_project_code(
                project_id=project_id,
                client_suffix=suffix,
                name=f"{client_code}_{suffix}_Default_SuffixCode",
            )
            created_codes += 1

    return {
        "created_clients": created_clients,
        "created_projects": created_projects,
        "created_codes": created_codes,
    }


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
    consultants: list[str] | None = None,
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
    if consultants:
        placeholders = ",".join("?" * len(consultants))
        filters.append(f"consultant IN ({placeholders})")
        params.extend(consultants)
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


def get_team_time_summary(
    period_from: str | None = None,
    period_to: str | None = None,
    group_names: list[str] | None = None,
) -> list[dict]:
    """Cross-client billable summary per consultant per period (YYYYMM).

    Returns list of dicts: consultant, emp_nbr, group_name, period,
    billable_hrs, billable_charges, internal_hrs, internal_charges, total_hrs.
    group_names — if provided, only returns rows matching those groups.
    """
    q = """
        SELECT
            te.consultant,
            te.emp_nbr,
            COALESCE(cg.group_name, 'Other') AS group_name,
            te.period,
            SUM(te.non_z_hours)   AS billable_hrs,
            SUM(te.non_z_charges) AS billable_charges,
            SUM(te.z_hours)       AS internal_hrs,
            SUM(te.z_charges)     AS internal_charges,
            SUM(te.total_hours)   AS total_hrs
        FROM time_entries te
        LEFT JOIN consultant_groups cg ON cg.consultant = te.consultant
    """
    params: list = []
    filters: list[str] = []
    if period_from:
        filters.append("te.period >= ?")
        params.append(period_from)
    if period_to:
        filters.append("te.period <= ?")
        params.append(period_to)
    if group_names:
        ph = ",".join("?" * len(group_names))
        filters.append(f"COALESCE(cg.group_name, 'Other') IN ({ph})")
        params.extend(group_names)
    if filters:
        q += " WHERE " + " AND ".join(filters)
    q += " GROUP BY te.consultant, cg.group_name, te.period ORDER BY te.consultant, te.period"
    with get_connection() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_team_time_summary_by_project(
    period_from: str | None = None,
    period_to: str | None = None,
    group_names: list[str] | None = None,
) -> list[dict]:
    """Cross-client billable per consultant per project.

    Returns: consultant, group_name, project, client, billable_hrs, billable_charges.
    Joined by consultant name (not emp_nbr) to handle multiple historical emp_nbrs.
    """
    q = """
        SELECT
            te.consultant,
            COALESCE(cg.group_name, 'Other') AS group_name,
            COALESCE(p.name, '(unknown project)') AS project,
            COALESCE(c.name, '(unknown client)')  AS client,
            SUM(te.non_z_hours)   AS billable_hrs,
            SUM(te.non_z_charges) AS billable_charges
        FROM time_entries te
        LEFT JOIN consultant_groups cg ON cg.consultant = te.consultant
        LEFT JOIN projects p ON p.id = te.project_id
        LEFT JOIN clients  c ON c.id = p.client_id
    """
    params: list = []
    filters: list[str] = []
    if period_from:
        filters.append("te.period >= ?"); params.append(period_from)
    if period_to:
        filters.append("te.period <= ?"); params.append(period_to)
    if group_names:
        ph = ",".join("?" * len(group_names))
        filters.append(f"COALESCE(cg.group_name,'Other') IN ({ph})")
        params.extend(group_names)
    if filters:
        q += " WHERE " + " AND ".join(filters)
    q += (" GROUP BY te.consultant, cg.group_name, te.project_id"
          " ORDER BY te.consultant, billable_charges DESC")
    with get_connection() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_time_summary_by_year(project_id: int) -> list[dict]:
    """Per-year, per-code billable hours and charges for a project (for Rollup year-by-year view)."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                SUBSTR(te.period, 1, 4) AS year,
                pc.client_code, pc.client_suffix, pc.name AS code_name,
                SUM(te.non_z_hours)   AS billable_hrs,
                SUM(te.non_z_charges) AS billable_charges,
                SUM(te.z_hours)       AS internal_hrs
            FROM time_entries te
            JOIN project_codes pc ON pc.id = te.project_code_id
            WHERE te.project_id = ?
            GROUP BY year, te.project_code_id
            ORDER BY year DESC, pc.client_code
        """, (project_id,)).fetchall()
    return [dict(r) for r in rows]


def get_billing_basis_summary(year: int) -> list[dict]:
    """Billing basis for a year joined with consultant name and group, for view-toggle modes.

    Returns: emp_nbr, consultant, group_name, project_id, project_name, client_name,
             non_z_charges (from time_entries for that year per project per consultant).
    Used for project-centric views in Billing Basis page.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                te.consultant,
                COALESCE(cg.group_name, 'Other') AS group_name,
                COALESCE(p.name, '(no project)') AS project_name,
                COALESCE(c.name, '(no client)')  AS client_name,
                SUM(te.non_z_charges) AS billable_charges,
                SUM(te.non_z_hours)   AS billable_hrs
            FROM time_entries te
            LEFT JOIN consultant_groups cg ON cg.consultant = te.consultant
            LEFT JOIN projects p ON p.id = te.project_id
            LEFT JOIN clients  c ON c.id = p.client_id
            WHERE te.period LIKE ?
            GROUP BY te.consultant, cg.group_name, te.project_id
            ORDER BY te.consultant, billable_charges DESC
        """, (f"{year}%",)).fetchall()
    return [dict(r) for r in rows]


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


def get_all_projects_overview(years: list[int] | None = None) -> list[dict]:
    """Rolled-up financials for every project, including year-by-year breakdown.

    years — list of calendar years to expand (default: current year + 3 prior).
    """
    from datetime import date as _date
    if years is None:
        cy = _date.today().year
        years = [cy - i for i in range(4)]

    # Build per-year subquery fragments
    sel, inv_j, te_j, wo_j = "", "", "", ""
    for yr in years:
        sel += (
            f", COALESCE(inv_{yr}.invoiced, 0) AS invoiced_{yr}"
            f", COALESCE(te_{yr}.charges,  0) AS charges_{yr}"
            f", COALESCE(wo_{yr}.write_offs,0) AS writeoffs_{yr}"
        )
        inv_j += (
            f" LEFT JOIN (SELECT project_id, SUM(amount) AS invoiced"
            f" FROM invoices WHERE year={yr} GROUP BY project_id)"
            f" inv_{yr} ON inv_{yr}.project_id = p.id"
        )
        te_j += (
            f" LEFT JOIN (SELECT project_id, SUM(non_z_charges) AS charges"
            f" FROM time_entries WHERE period LIKE '{yr}%' GROUP BY project_id)"
            f" te_{yr} ON te_{yr}.project_id = p.id"
        )
        wo_j += (
            f" LEFT JOIN (SELECT project_id, SUM(amount) AS write_offs"
            f" FROM write_offs WHERE reversed=0"
            f" AND strftime('%Y', created_at)='{yr}' GROUP BY project_id)"
            f" wo_{yr} ON wo_{yr}.project_id = p.id"
        )

    query = f"""
        SELECT
            p.id          AS project_id,
            c.name        AS client,
            c.client_code,
            c.client_type,
            c.country,
            p.name        AS project,
            p.status,
            COUNT(DISTINCT pc.id)                       AS code_count,
            COALESCE(SUM(DISTINCT pc.budget_amount), 0) AS budget,
            COALESCE(te_all.billable_charges, 0)        AS billable_charges,
            COALESCE(wo_all.write_offs,       0)        AS write_offs,
            COALESCE(inv_all.invoiced,        0)        AS invoiced
            {sel}
            , COALESCE(grp_info.groups_with_hours, '')       AS groups_with_hours
            , COALESCE(grp_info.consultants_with_hours, '')  AS consultants_with_hours
        FROM projects p
        JOIN clients c ON c.id = p.client_id
        LEFT JOIN project_codes pc ON pc.project_id = p.id
        LEFT JOIN (SELECT project_id, SUM(non_z_charges) AS billable_charges
                   FROM time_entries GROUP BY project_id) te_all ON te_all.project_id = p.id
        LEFT JOIN (SELECT project_id, SUM(amount) AS write_offs
                   FROM write_offs WHERE reversed=0 GROUP BY project_id) wo_all ON wo_all.project_id = p.id
        LEFT JOIN (SELECT project_id, SUM(amount) AS invoiced
                   FROM invoices GROUP BY project_id) inv_all ON inv_all.project_id = p.id
        LEFT JOIN (
            SELECT te.project_id,
                   GROUP_CONCAT(DISTINCT COALESCE(cg.group_name, 'Other')) AS groups_with_hours,
                   GROUP_CONCAT(DISTINCT te.consultant) AS consultants_with_hours
            FROM time_entries te
            LEFT JOIN consultant_groups cg ON cg.consultant = te.consultant
            GROUP BY te.project_id
        ) grp_info ON grp_info.project_id = p.id
        {inv_j} {te_j} {wo_j}
        GROUP BY p.id
        ORDER BY c.name, p.name
    """
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["net_charges"] = d["billable_charges"] - d["write_offs"]
        d["remaining"]   = d["budget"] - d["invoiced"]
        prefix = (d.get("client_code") or "")[:4]
        if prefix == "0009":
            d["project_source"] = "NotBillable"
        else:
            d["project_source"] = _OFFICE_CODES.get(prefix, "Ext")
        d["client_type"] = d.get("client_type") or "external"
        d["country"]     = d.get("country") or ""
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


# ---------------------------------------------------------------------------
# Consultant Profile CRUD (Sprint 10)
# ---------------------------------------------------------------------------

def get_consultant_profile(emp_nbr: str) -> ConsultantProfile | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, emp_nbr, employment_date, prior_exp_years, milliman_status, "
            "external_level, languages, tools, current_role, notes, created_at "
            "FROM consultant_profiles WHERE emp_nbr = ?", (emp_nbr,)
        ).fetchone()
    return ConsultantProfile(**dict(row)) if row else None


def upsert_consultant_profile(
    emp_nbr: str,
    employment_date: str = "",
    prior_exp_years: float = 0.0,
    milliman_status: str = "",
    external_level: str = "",
    languages: str = "",
    tools: str = "",
    current_role: str = "",
    notes: str = "",
) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM consultant_profiles WHERE emp_nbr = ?", (emp_nbr,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE consultant_profiles SET employment_date=?, prior_exp_years=?, "
                "milliman_status=?, external_level=?, languages=?, tools=?, "
                "current_role=?, notes=? WHERE emp_nbr=?",
                (employment_date, prior_exp_years, milliman_status, external_level,
                 languages, tools, current_role, notes, emp_nbr)
            )
            return row["id"]
        cur = conn.execute(
            "INSERT INTO consultant_profiles "
            "(emp_nbr, employment_date, prior_exp_years, milliman_status, external_level, "
            "languages, tools, current_role, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (emp_nbr, employment_date, prior_exp_years, milliman_status, external_level,
             languages, tools, current_role, notes)
        )
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Annual Salary History CRUD (Sprint 10)
# ---------------------------------------------------------------------------

def get_salary_history(emp_nbr: str) -> list[AnnualSalaryHistory]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, emp_nbr, year, starting_salary, exams_passed, exam_raise_per_exam, "
            "other_raise, effective_date, objective_bonus_pct, bonus_paid, proposed_rate, notes "
            "FROM annual_salary_history WHERE emp_nbr = ? ORDER BY year",
            (emp_nbr,)
        ).fetchall()
    return [AnnualSalaryHistory(**dict(r)) for r in rows]


def get_salary_record(emp_nbr: str, year: int) -> AnnualSalaryHistory | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, emp_nbr, year, starting_salary, exams_passed, exam_raise_per_exam, "
            "other_raise, effective_date, objective_bonus_pct, bonus_paid, proposed_rate, notes "
            "FROM annual_salary_history WHERE emp_nbr = ? AND year = ?",
            (emp_nbr, year)
        ).fetchone()
    return AnnualSalaryHistory(**dict(row)) if row else None


def upsert_salary_record(
    emp_nbr: str,
    year: int,
    starting_salary: float = 0.0,
    exams_passed: float = 0.0,
    exam_raise_per_exam: float = 1000.0,
    other_raise: float = 0.0,
    effective_date: str = "",
    objective_bonus_pct: float = 0.0,
    bonus_paid: float = 0.0,
    proposed_rate: float = 0.0,
    notes: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO annual_salary_history "
            "(emp_nbr, year, starting_salary, exams_passed, exam_raise_per_exam, "
            "other_raise, effective_date, objective_bonus_pct, bonus_paid, proposed_rate, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(emp_nbr, year) DO UPDATE SET "
            "starting_salary=excluded.starting_salary, "
            "exams_passed=excluded.exams_passed, "
            "exam_raise_per_exam=excluded.exam_raise_per_exam, "
            "other_raise=excluded.other_raise, "
            "effective_date=excluded.effective_date, "
            "objective_bonus_pct=excluded.objective_bonus_pct, "
            "bonus_paid=excluded.bonus_paid, "
            "proposed_rate=excluded.proposed_rate, "
            "notes=excluded.notes",
            (emp_nbr, year, starting_salary, exams_passed, exam_raise_per_exam,
             other_raise, effective_date, objective_bonus_pct, bonus_paid, proposed_rate, notes)
        )


def delete_salary_record(emp_nbr: str, year: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM annual_salary_history WHERE emp_nbr = ? AND year = ?",
            (emp_nbr, year)
        )


# ---------------------------------------------------------------------------
# Billing Basis CRUD (Sprint 10)
# ---------------------------------------------------------------------------

def get_billing_basis_year(year: int) -> list[BillingBasis]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, emp_nbr, year, source, billed, capped_paid_prebill, "
            "capped_unpaid_prebill, charged_off, paid, unbilled, hourly_rate, notes, created_at "
            "FROM billing_basis WHERE year = ? ORDER BY emp_nbr",
            (year,)
        ).fetchall()
    return [BillingBasis(**dict(r)) for r in rows]


def get_billing_basis(emp_nbr: str, year: int) -> BillingBasis | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, emp_nbr, year, source, billed, capped_paid_prebill, "
            "capped_unpaid_prebill, charged_off, paid, unbilled, hourly_rate, notes, created_at "
            "FROM billing_basis WHERE emp_nbr = ? AND year = ?",
            (emp_nbr, year)
        ).fetchone()
    return BillingBasis(**dict(row)) if row else None


def upsert_billing_basis(
    emp_nbr: str,
    year: int,
    source: str = "manual",
    billed: float = 0.0,
    capped_paid_prebill: float = 0.0,
    capped_unpaid_prebill: float = 0.0,
    charged_off: float = 0.0,
    paid: float = 0.0,
    unbilled: float = 0.0,
    hourly_rate: float = 0.0,
    notes: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO billing_basis "
            "(emp_nbr, year, source, billed, capped_paid_prebill, capped_unpaid_prebill, "
            "charged_off, paid, unbilled, hourly_rate, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(emp_nbr, year) DO UPDATE SET "
            "source=excluded.source, billed=excluded.billed, "
            "capped_paid_prebill=excluded.capped_paid_prebill, "
            "capped_unpaid_prebill=excluded.capped_unpaid_prebill, "
            "charged_off=excluded.charged_off, paid=excluded.paid, "
            "unbilled=excluded.unbilled, hourly_rate=excluded.hourly_rate, "
            "notes=excluded.notes",
            (emp_nbr, year, source, billed, capped_paid_prebill, capped_unpaid_prebill,
             charged_off, paid, unbilled, hourly_rate, notes)
        )


def get_billing_basis_from_time_entries(year: int) -> list[dict]:
    """Auto-aggregate time entries + write-offs for a given year into billing basis rows.

    Maps: non_z_charges → paid column; write-off amounts → charged_off.
    Other billing categories (billed, capped prebill, unbilled) are not tracked in
    time_entries and will be zero — fill manually if needed.
    """
    period_prefix = str(year)
    with get_connection() as conn:
        te_rows = conn.execute(
            "SELECT emp_nbr, consultant, "
            "SUM(non_z_charges) AS paid, "
            "SUM(total_charges) AS grand_total_raw "
            "FROM time_entries WHERE period LIKE ? "
            "GROUP BY emp_nbr ORDER BY consultant",
            (f"{period_prefix}%",)
        ).fetchall()
        wo_rows = conn.execute(
            "SELECT emp_nbr, SUM(amount) AS charged_off "
            "FROM write_offs "
            "WHERE reversed = 0 "
            "AND strftime('%Y', created_at) = ? "
            "AND emp_nbr != '' "
            "GROUP BY emp_nbr",
            (period_prefix,)
        ).fetchall()
    wo_map = {r["emp_nbr"]: r["charged_off"] for r in wo_rows}
    result = []
    for r in te_rows:
        paid = r["paid"] or 0.0
        charged_off = wo_map.get(r["emp_nbr"], 0.0)
        result.append({
            "emp_nbr": r["emp_nbr"],
            "consultant": r["consultant"],
            "billed": 0.0,
            "capped_paid_prebill": 0.0,
            "capped_unpaid_prebill": 0.0,
            "charged_off": round(charged_off, 2),
            "paid": round(paid, 2),
            "unbilled": 0.0,
            "grand_total": round(paid + charged_off, 2),
        })
    return result


# ---------------------------------------------------------------------------
# Review Scores CRUD (Sprint 10)
# ---------------------------------------------------------------------------

def get_review_scores(emp_nbr: str, year: int) -> dict[str, dict[str, float]]:
    """Returns {group: {item: score}} for the given consultant and year."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT score_group, item_name, score FROM review_scores "
            "WHERE emp_nbr = ? AND year = ?",
            (emp_nbr, year)
        ).fetchall()
    result: dict[str, dict[str, float]] = {}
    for r in rows:
        result.setdefault(r["score_group"], {})[r["item_name"]] = r["score"]
    return result


def get_review_scores_multi_year(emp_nbr: str, years: list[int]) -> dict[int, dict[str, dict[str, float]]]:
    """Returns {year: {group: {item: score}}} for historical comparison."""
    if not years:
        return {}
    placeholders = ",".join("?" * len(years))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT year, score_group, item_name, score FROM review_scores "
            f"WHERE emp_nbr = ? AND year IN ({placeholders}) ORDER BY year",
            [emp_nbr] + list(years)
        ).fetchall()
    result: dict[int, dict[str, dict[str, float]]] = {}
    for r in rows:
        result.setdefault(r["year"], {}).setdefault(r["score_group"], {})[r["item_name"]] = r["score"]
    return result


def upsert_review_scores(emp_nbr: str, year: int, scores: dict[str, dict[str, float]]) -> None:
    """Upsert performance scores. scores = {group: {item: score}}."""
    with get_connection() as conn:
        for group, items in scores.items():
            for item, score in items.items():
                conn.execute(
                    "INSERT INTO review_scores (emp_nbr, year, score_group, item_name, score) "
                    "VALUES (?,?,?,?,?) "
                    "ON CONFLICT(emp_nbr, year, score_group, item_name) DO UPDATE SET score=excluded.score",
                    (emp_nbr, year, group, item, score)
                )


# ---------------------------------------------------------------------------
# Review Feedback
# ---------------------------------------------------------------------------

def get_review_feedback(emp_nbr: str, year: int) -> dict[str, "ReviewFeedback"]:
    """Return saved feedback keyed by area for a consultant/year."""
    from shared.models import ReviewFeedback
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, emp_nbr, year, area, comments, development_ideas, created_at "
            "FROM review_feedback WHERE emp_nbr = ? AND year = ?",
            (emp_nbr, year),
        ).fetchall()
    return {
        r["area"]: ReviewFeedback(
            id=r["id"], emp_nbr=r["emp_nbr"], year=r["year"], area=r["area"],
            comments=r["comments"] or "", development_ideas=r["development_ideas"] or "",
            created_at=r["created_at"] or "",
        )
        for r in rows
    }


def upsert_review_feedback(
    emp_nbr: str, year: int, area: str,
    comments: str = "", development_ideas: str = "",
) -> None:
    """Insert or update a feedback record for one area."""
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO review_feedback (emp_nbr, year, area, comments, development_ideas, created_at) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(emp_nbr, year, area) DO UPDATE SET "
            "comments=excluded.comments, development_ideas=excluded.development_ideas",
            (emp_nbr, year, area, comments, development_ideas, now),
        )


def get_consultant_project_hours(consultant: str, year: int) -> list[dict]:
    """
    Per-project hours breakdown for a consultant in a given year.

    Returns list of dicts (ordered by hours desc):
        client, project_name, description, hours, hours_pct, colleagues
    Colleagues = comma-separated names of other consultants who also billed
    to the same project in the same year.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.name          AS client,
                p.name          AS project_name,
                p.description   AS description,
                SUM(te.non_z_hours) AS hours
            FROM time_entries te
            JOIN projects p ON p.id = te.project_id
            JOIN clients  c ON c.id = p.client_id
            WHERE te.consultant = ?
              AND SUBSTR(te.period, 1, 4) = ?
            GROUP BY te.project_id
            ORDER BY hours DESC
            """,
            (consultant, str(year)),
        ).fetchall()

        # Total hours for this consultant that year (for % calculation)
        total_row = conn.execute(
            """
            SELECT COALESCE(SUM(non_z_hours), 0) AS total
            FROM time_entries
            WHERE consultant = ? AND SUBSTR(period, 1, 4) = ?
            """,
            (consultant, str(year)),
        ).fetchone()
        total_hrs = total_row["total"] if total_row else 0.0

        # Colleagues per project
        project_colleagues: dict[str, str] = {}
        coll_rows = conn.execute(
            """
            SELECT p.name AS project_name,
                   GROUP_CONCAT(DISTINCT te2.consultant) AS others
            FROM time_entries te
            JOIN projects p ON p.id = te.project_id
            JOIN time_entries te2
                 ON te2.project_id = te.project_id
                AND SUBSTR(te2.period, 1, 4) = ?
                AND te2.consultant != te.consultant
            WHERE te.consultant = ?
              AND SUBSTR(te.period, 1, 4) = ?
            GROUP BY te.project_id
            """,
            (str(year), consultant, str(year)),
        ).fetchall()
        for cr in coll_rows:
            project_colleagues[cr["project_name"]] = cr["others"] or ""

    result = []
    for r in rows:
        pct = (r["hours"] / total_hrs * 100) if total_hrs > 0 else 0.0
        result.append({
            "client":       r["client"],
            "project_name": r["project_name"],
            "description":  r["description"] or "",
            "hours":        round(r["hours"], 1),
            "hours_pct":    round(pct, 1),
            "colleagues":   project_colleagues.get(r["project_name"], ""),
        })
    return result


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at: {DB_PATH}")
