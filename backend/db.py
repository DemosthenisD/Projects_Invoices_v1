"""
SQLite data access layer for InvoiceApp.

All database interactions go through this module.
Tables are created on first run via init_db().
"""
import sqlite3
import sys
import os
import calendar as _calendar
from contextlib import contextmanager
from datetime import datetime, timezone, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
from shared.models import (
    Client, Address, Project, Invoice, InvoiceAllocation, Payment, PipelineEntry,
    ProjectCode, TimeEntry, WriteOff,
    ConsultantProfile, AnnualSalaryHistory, BillingBasis, ReviewScore,
    RecurringFee, RecurringFeeOccurrence, Receivable, ReceivablePayment,
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
                group_name TEXT NOT NULL DEFAULT 'Other',
                status     TEXT NOT NULL DEFAULT 'Active'
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
                UNIQUE(emp_nbr, year, source)
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

            CREATE TABLE IF NOT EXISTS review_locks (
                emp_nbr   TEXT    NOT NULL,
                year      INTEGER NOT NULL,
                locked_at TEXT    DEFAULT (datetime('now')),
                PRIMARY KEY (emp_nbr, year)
            );

            -- FK and filter columns not covered by UNIQUE constraints
            CREATE INDEX IF NOT EXISTS idx_te_project_id   ON time_entries(project_id);
            CREATE INDEX IF NOT EXISTS idx_te_consultant    ON time_entries(consultant);
            CREATE INDEX IF NOT EXISTS idx_te_emp_nbr      ON time_entries(emp_nbr);
            CREATE INDEX IF NOT EXISTS idx_inv_year        ON invoices(year);
            CREATE INDEX IF NOT EXISTS idx_inv_project_id  ON invoices(project_id);
            CREATE INDEX IF NOT EXISTS idx_inv_client_id   ON invoices(client_id);
            CREATE INDEX IF NOT EXISTS idx_pay_invoice_id  ON payments(invoice_id);
            CREATE INDEX IF NOT EXISTS idx_pc_project_id   ON project_codes(project_id);
            CREATE INDEX IF NOT EXISTS idx_wo_project_id   ON write_offs(project_id);
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

        # --- Migration: consultant_groups.status column ---
        try:
            conn.execute(
                "ALTER TABLE consultant_groups ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'"
            )
        except Exception:
            pass

        # --- Migration: pipeline.opportunity_country column ---
        try:
            conn.execute("ALTER TABLE pipeline ADD COLUMN opportunity_country TEXT DEFAULT ''")
        except Exception:
            pass

        # --- Migration: billing_basis.is_preferred column ---
        try:
            conn.execute(
                "ALTER TABLE billing_basis ADD COLUMN is_preferred INTEGER NOT NULL DEFAULT 0"
            )
            # Initialise based on priority rule: manual preferred; time_tracking preferred
            # only when no manual record exists for the same (emp_nbr, year).
            conn.execute("UPDATE billing_basis SET is_preferred=1 WHERE source='manual'")
            conn.execute("""
                UPDATE billing_basis SET is_preferred=1
                WHERE source='time_tracking'
                  AND NOT EXISTS (
                      SELECT 1 FROM billing_basis b2
                      WHERE b2.emp_nbr = billing_basis.emp_nbr
                        AND b2.year   = billing_basis.year
                        AND b2.source = 'manual'
                  )
            """)
        except Exception:
            pass

        # --- Migration: billing_basis.avg_annual_rate column ---
        try:
            conn.execute(
                "ALTER TABLE billing_basis ADD COLUMN avg_annual_rate REAL NOT NULL DEFAULT 0.0"
            )
        except Exception:
            pass

        # --- Migration: pipeline → prospect support (nullable project_id, new columns) ---
        _pl_schema_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='pipeline'"
        ).fetchone()
        _pl_schema_str = (_pl_schema_row[0] if _pl_schema_row else "") or ""
        _need_pl_migration = "is_prospect" not in _pl_schema_str

        # --- Migration: billing_basis UNIQUE(emp_nbr,year) → UNIQUE(emp_nbr,year,source) ---
        # SQLite requires a table recreation to change a UNIQUE constraint.
        # We do this outside the main connection (executescript issues its own COMMITs).
        _bb_schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='billing_basis'"
        ).fetchone()
        if _bb_schema and "UNIQUE(emp_nbr, year, source)" not in (_bb_schema["sql"] or ""):
            _need_bb_migration = True
        else:
            _need_bb_migration = False

    if _need_bb_migration:
        _mig_conn = sqlite3.connect(DB_PATH)
        _mig_conn.row_factory = sqlite3.Row
        try:
            _mig_conn.executescript("""
                PRAGMA foreign_keys=OFF;
                CREATE TABLE IF NOT EXISTS billing_basis_new (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    emp_nbr               TEXT    NOT NULL,
                    year                  INTEGER NOT NULL,
                    source                TEXT    DEFAULT 'manual',
                    billed                REAL    DEFAULT 0.0,
                    capped_paid_prebill   REAL    DEFAULT 0.0,
                    capped_unpaid_prebill REAL    DEFAULT 0.0,
                    charged_off           REAL    DEFAULT 0.0,
                    paid                  REAL    DEFAULT 0.0,
                    unbilled              REAL    DEFAULT 0.0,
                    hourly_rate           REAL    DEFAULT 0.0,
                    avg_annual_rate       REAL    DEFAULT 0.0,
                    notes                 TEXT    DEFAULT '',
                    created_at            TEXT    DEFAULT (datetime('now')),
                    UNIQUE(emp_nbr, year, source)
                );
                INSERT OR IGNORE INTO billing_basis_new
                    SELECT id, emp_nbr, year, source, billed, capped_paid_prebill,
                           capped_unpaid_prebill, charged_off, paid, unbilled,
                           hourly_rate, 0.0, notes, created_at
                    FROM billing_basis;
                DROP TABLE billing_basis;
                ALTER TABLE billing_basis_new RENAME TO billing_basis;
                PRAGMA foreign_keys=ON;
            """)
        finally:
            _mig_conn.close()

    if _need_pl_migration:
        _mig_conn = sqlite3.connect(DB_PATH)
        _mig_conn.row_factory = sqlite3.Row
        try:
            _mig_conn.executescript("""
                PRAGMA foreign_keys = OFF;
                CREATE TABLE pipeline_new (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id            INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                    is_prospect           INTEGER NOT NULL DEFAULT 0,
                    company_name          TEXT    DEFAULT '',
                    prospect_name         TEXT    DEFAULT '',
                    description           TEXT    DEFAULT '',
                    stage                 TEXT    DEFAULT 'Prospect',
                    value                 REAL    DEFAULT 0.0,
                    budget_min            REAL    DEFAULT 0.0,
                    budget_est            REAL    DEFAULT 0.0,
                    budget_max            REAL    DEFAULT 0.0,
                    probability           REAL    DEFAULT 0.5,
                    notes                 TEXT    DEFAULT '',
                    updated_at            TEXT    DEFAULT (datetime('now')),
                    date_entered_pipeline TEXT    DEFAULT '',
                    date_entered_stage    TEXT    DEFAULT '',
                    opportunity_country   TEXT    DEFAULT ''
                );
                INSERT INTO pipeline_new
                    (id, project_id, is_prospect, stage, value,
                     budget_min, budget_est, budget_max, probability, notes,
                     updated_at, date_entered_pipeline, date_entered_stage, opportunity_country)
                    SELECT id, project_id, 0, stage, value,
                           COALESCE(budget_min,  0.0), COALESCE(budget_est,  0.0),
                           COALESCE(budget_max,  0.0), COALESCE(probability, 0.5),
                           COALESCE(notes, ''),  COALESCE(updated_at, datetime('now')),
                           COALESCE(date_entered_pipeline, ''),
                           COALESCE(date_entered_stage,    ''),
                           COALESCE(opportunity_country,   '')
                    FROM pipeline;
                DROP TABLE pipeline;
                ALTER TABLE pipeline_new RENAME TO pipeline;
                CREATE UNIQUE INDEX IF NOT EXISTS uidx_pipeline_project
                    ON pipeline(project_id) WHERE project_id IS NOT NULL;
                PRAGMA foreign_keys = ON;
            """)
        finally:
            _mig_conn.close()

    # --- Bootstrap: give every existing project a pipeline entry (idempotent) ---
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO pipeline (project_id, is_prospect, stage,
                                  date_entered_pipeline, date_entered_stage, updated_at)
            SELECT p.id, 0,
                   CASE WHEN p.status IN ('Active','On Hold','Completed','Prospect')
                        THEN p.status ELSE 'Prospect' END,
                   date('now'), date('now'), datetime('now')
            FROM projects p
            LEFT JOIN pipeline pl ON pl.project_id = p.id
            WHERE pl.id IS NULL
        """)

    # --- Migration: pipeline activity log ---
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_activity_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_id INTEGER NOT NULL REFERENCES pipeline(id) ON DELETE CASCADE,
                note        TEXT    NOT NULL DEFAULT '',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

    # --- Migration: projects.billing_arrangement ---
    with get_connection() as conn:
        try:
            conn.execute(
                "ALTER TABLE projects ADD COLUMN billing_arrangement TEXT NOT NULL DEFAULT 'local'"
            )
            conn.execute("""
                UPDATE projects SET billing_arrangement = 'receivable'
                WHERE client_id IN (SELECT id FROM clients WHERE client_type = 'external')
            """)
            conn.execute("""
                UPDATE projects SET billing_arrangement = 'internal'
                WHERE client_id IN (SELECT id FROM clients WHERE client_type = 'internal')
            """)
        except Exception:
            pass  # column already exists

    # --- Recurring fees, receivables tables ---
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS recurring_fees (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                project_code_id INTEGER NOT NULL REFERENCES project_codes(id) ON DELETE CASCADE,
                description     TEXT    NOT NULL DEFAULT '',
                fee_amount      REAL    NOT NULL DEFAULT 0.0,
                fee_type        TEXT    NOT NULL DEFAULT 'fixed',
                index_rate      REAL    NOT NULL DEFAULT 0.0,
                frequency       TEXT    NOT NULL DEFAULT 'annual',
                coverage_start  TEXT    NOT NULL DEFAULT '',
                expected_end    TEXT    NOT NULL DEFAULT '',
                billing_type    TEXT    NOT NULL DEFAULT 'we_bill',
                split_party     TEXT    NOT NULL DEFAULT '',
                split_amount    REAL    NOT NULL DEFAULT 0.0,
                auto_invoice    INTEGER NOT NULL DEFAULT 0,
                status          TEXT    NOT NULL DEFAULT 'Active',
                cancelled_at    TEXT    NOT NULL DEFAULT '',
                notes           TEXT    NOT NULL DEFAULT '',
                created_at      TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recurring_fee_occurrences (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                recurring_fee_id INTEGER NOT NULL REFERENCES recurring_fees(id) ON DELETE CASCADE,
                due_date         TEXT    NOT NULL,
                amount           REAL    NOT NULL DEFAULT 0.0,
                split_amount     REAL    NOT NULL DEFAULT 0.0,
                invoice_id       INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
                status           TEXT    NOT NULL DEFAULT 'pending',
                notes            TEXT    NOT NULL DEFAULT '',
                created_at       TEXT    DEFAULT (datetime('now')),
                UNIQUE(recurring_fee_id, due_date)
            );

            CREATE TABLE IF NOT EXISTS receivables (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id       INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                project_code_id  INTEGER REFERENCES project_codes(id) ON DELETE SET NULL,
                occurrence_id    INTEGER REFERENCES recurring_fee_occurrences(id) ON DELETE SET NULL,
                description      TEXT    NOT NULL DEFAULT '',
                receivable_type  TEXT    NOT NULL DEFAULT 'capped',
                cap_amount       REAL    NOT NULL DEFAULT 0.0,
                expected_amount  REAL    NOT NULL DEFAULT 0.0,
                due_date         TEXT    NOT NULL DEFAULT '',
                notes            TEXT    NOT NULL DEFAULT '',
                created_at       TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS receivable_payments (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                receivable_id INTEGER NOT NULL REFERENCES receivables(id) ON DELETE CASCADE,
                amount        REAL    NOT NULL,
                date          TEXT    NOT NULL,
                notes         TEXT    NOT NULL DEFAULT '',
                created_at    TEXT    DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_rfo_fee_id
                ON recurring_fee_occurrences(recurring_fee_id);
            CREATE INDEX IF NOT EXISTS idx_rfo_due_date
                ON recurring_fee_occurrences(due_date);
            CREATE INDEX IF NOT EXISTS idx_rec_project_id
                ON receivables(project_id);
            CREATE INDEX IF NOT EXISTS idx_recpay_receivable_id
                ON receivable_payments(receivable_id);
        """)


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
    query = ("SELECT id, client_id, name, description, vat_pct, template, status, "
             "date_start, billing_arrangement FROM projects")
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
                status: str = "Active", date_start: str = "",
                billing_arrangement: str = "local") -> int:
    _PIPELINE_STAGES = {"Active", "On Hold", "Completed", "Prospect"}
    is_new = False
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO projects "
            "(client_id, name, description, vat_pct, template, status, date_start, billing_arrangement) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (client_id, name, description, vat_pct, template, status, date_start, billing_arrangement)
        )
        if cur.lastrowid:
            project_id = cur.lastrowid
            is_new = True
        else:
            row = conn.execute(
                "SELECT id FROM projects WHERE client_id=? AND name=?",
                (client_id, name)
            ).fetchone()
            project_id = row["id"]
    if is_new:
        upsert_pipeline(project_id, stage=status if status in _PIPELINE_STAGES else "Prospect")
    return project_id


def update_project(project_id: int, description: str, vat_pct: float,
                   template: str, status: str, date_start: str = "",
                   billing_arrangement: str = "local") -> int:
    """Update project fields. Returns count of project codes auto-closed (0 if no auto-close)."""
    closed_count = 0
    with get_connection() as conn:
        old = conn.execute("SELECT status FROM projects WHERE id=?", (project_id,)).fetchone()
        conn.execute(
            "UPDATE projects SET description=?, vat_pct=?, template=?, status=?, "
            "date_start=?, billing_arrangement=? WHERE id=?",
            (description, vat_pct, template, status, date_start, billing_arrangement, project_id)
        )
        if status == "Completed" and old and old["status"] != "Completed":
            today = date.today().isoformat()
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
    import pandas as _pd
    if val is None:
        return ""
    if isinstance(val, (date, datetime)):
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
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
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
    """Returns all pipeline entries — both linked (project_id set) and standalone prospects."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT pl.id, pl.project_id, pl.is_prospect,
                   pl.company_name, pl.prospect_name, pl.description,
                   pl.stage, pl.value,
                   pl.budget_min, pl.budget_est, pl.budget_max, pl.probability,
                   pl.notes, pl.updated_at,
                   pl.date_entered_pipeline, pl.date_entered_stage,
                   pl.opportunity_country,
                   pr.name        AS project_name,
                   pr.status      AS project_status,
                   c.name         AS client_name,
                   c.client_type,
                   c.country      AS client_country,
                   CASE WHEN pl.is_prospect = 1
                        THEN pl.company_name
                        ELSE c.name END   AS display_client,
                   CASE WHEN pl.is_prospect = 1
                        THEN COALESCE(NULLIF(pl.prospect_name, ''), pl.company_name)
                        ELSE pr.name END  AS display_project,
                   CASE WHEN pl.is_prospect = 1
                        THEN pl.company_name
                        ELSE COALESCE(c.country, '') END AS country
            FROM pipeline pl
            LEFT JOIN projects pr ON pr.id = pl.project_id
            LEFT JOIN clients  c  ON c.id  = pr.client_id
            ORDER BY pl.stage, display_client
        """).fetchall()
    return [dict(r) for r in rows]


def upsert_pipeline(project_id: int, stage: str = "Prospect",
                    value: float = 0.0, notes: str = "",
                    budget_min: float = 0.0, budget_est: float = 0.0,
                    budget_max: float = 0.0, probability: float = 0.5,
                    opportunity_country: str = "") -> None:
    """Insert or update a pipeline entry for an existing linked project (is_prospect=0)."""
    now   = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, stage, date_entered_stage FROM pipeline WHERE project_id = ?",
            (project_id,)
        ).fetchone()
        stage_changed = existing is None or existing["stage"] != stage
        stage_date = today if stage_changed else (existing["date_entered_stage"] if existing else today)
        if existing:
            conn.execute(
                "UPDATE pipeline SET stage=?, value=?, budget_min=?, budget_est=?, budget_max=?, "
                "probability=?, notes=?, updated_at=?, opportunity_country=?, date_entered_stage=? "
                "WHERE id=?",
                (stage, value, budget_min, budget_est, budget_max, probability, notes,
                 now, opportunity_country, stage_date, existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO pipeline (project_id, is_prospect, stage, value, budget_min, budget_est, "
                "budget_max, probability, notes, updated_at, date_entered_pipeline, "
                "date_entered_stage, opportunity_country) VALUES (?,0,?,?,?,?,?,?,?,?,?,?,?)",
                (project_id, stage, value, budget_min, budget_est, budget_max, probability, notes,
                 now, today, stage_date, opportunity_country)
            )


def add_prospect(company_name: str, prospect_name: str = "", description: str = "",
                 country: str = "", stage: str = "Prospect", value: float = 0.0,
                 budget_min: float = 0.0, budget_est: float = 0.0,
                 budget_max: float = 0.0, probability: float = 0.5,
                 notes: str = "") -> int:
    """Insert a standalone prospect row (project_id=NULL, is_prospect=1). Returns new id."""
    now   = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO pipeline (project_id, is_prospect, company_name, prospect_name, "
            "description, stage, value, budget_min, budget_est, budget_max, probability, "
            "notes, updated_at, date_entered_pipeline, date_entered_stage, opportunity_country) "
            "VALUES (NULL,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (company_name, prospect_name, description, stage, value,
             budget_min, budget_est, budget_max, probability, notes,
             now, today, today, "")
        )
        return cur.lastrowid


def update_prospect(pipeline_id: int, company_name: str, prospect_name: str = "",
                    description: str = "", stage: str = "Prospect", value: float = 0.0,
                    budget_min: float = 0.0, budget_est: float = 0.0,
                    budget_max: float = 0.0, probability: float = 0.5,
                    notes: str = "", opportunity_country: str = "") -> None:
    """Update an existing standalone prospect row."""
    now   = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    with get_connection() as conn:
        old = conn.execute(
            "SELECT stage, date_entered_stage FROM pipeline WHERE id=? AND is_prospect=1",
            (pipeline_id,)
        ).fetchone()
        if old is None:
            return
        stage_date = today if old["stage"] != stage else old["date_entered_stage"]
        conn.execute(
            "UPDATE pipeline SET company_name=?, prospect_name=?, description=?, stage=?, "
            "value=?, budget_min=?, budget_est=?, budget_max=?, probability=?, notes=?, "
            "updated_at=?, date_entered_stage=?, opportunity_country=? "
            "WHERE id=? AND is_prospect=1",
            (company_name, prospect_name, description, stage, value,
             budget_min, budget_est, budget_max, probability, notes,
             now, stage_date, opportunity_country, pipeline_id)
        )


def convert_prospect_to_project(pipeline_id: int, project_id: int) -> None:
    """Link a prospect row to a real project and clear prospect-only fields."""
    now   = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT stage FROM pipeline WHERE id=? AND is_prospect=1", (pipeline_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No prospect row found with id={pipeline_id}")
        new_stage = "Active" if row["stage"] == "Prospect" else row["stage"]
        conn.execute(
            "UPDATE pipeline SET project_id=?, is_prospect=0, "
            "company_name='', prospect_name='', description='', "
            "stage=?, updated_at=?, date_entered_stage=? WHERE id=?",
            (project_id, new_stage, now, today, pipeline_id)
        )


def delete_prospect(pipeline_id: int) -> None:
    """Delete a standalone prospect row. Will not delete linked rows."""
    with get_connection() as conn:
        conn.execute("DELETE FROM pipeline WHERE id=? AND is_prospect=1", (pipeline_id,))


def add_pipeline_note(pipeline_id: int, note: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO pipeline_activity_log (pipeline_id, note) VALUES (?, ?)",
            (pipeline_id, note.strip()),
        )


def get_pipeline_notes(pipeline_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, note, created_at FROM pipeline_activity_log "
            "WHERE pipeline_id=? ORDER BY created_at DESC",
            (pipeline_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Pipeline Financial Dashboard
# ---------------------------------------------------------------------------

def get_pipeline_financial_summary() -> list[dict]:
    """Return Prospect/Active/On Hold pipeline entries with financial aggregates."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                pl.id          AS pipeline_id,
                pl.project_id,
                pl.is_prospect,
                pl.stage,
                COALESCE(pl.probability, 0.5) AS probability,
                COALESCE(pl.budget_min,  0.0) AS budget_min,
                COALESCE(pl.budget_est,  0.0) AS budget_est,
                COALESCE(pl.budget_max,  0.0) AS budget_max,
                CASE WHEN pl.is_prospect THEN pl.company_name
                     ELSE COALESCE(c.name, '') END AS client_name,
                CASE WHEN pl.is_prospect THEN COALESCE(pl.opportunity_country, '')
                     ELSE COALESCE(c.country, '') END AS country,
                CASE WHEN pl.is_prospect
                          THEN COALESCE(NULLIF(pl.prospect_name,''), pl.company_name)
                     ELSE COALESCE(p.name, '') END AS project_name,
                COALESCE(c.client_type, '') AS client_type,
                COALESCE(pc_s.code_budget,      0.0) AS code_budget,
                COALESCE(te_s.time_charges,     0.0) AS time_charges,
                COALESCE(inv_s.invoiced_amount, 0.0) AS invoiced_amount,
                COALESCE(inv_s.paid_amount,     0.0) AS paid_amount
            FROM pipeline pl
            LEFT JOIN projects p  ON p.id  = pl.project_id
            LEFT JOIN clients  c  ON c.id  = p.client_id
            LEFT JOIN (
                SELECT project_id, SUM(budget_amount) AS code_budget
                FROM project_codes GROUP BY project_id
            ) pc_s  ON pc_s.project_id  = pl.project_id
            LEFT JOIN (
                SELECT project_id, SUM(non_z_charges) AS time_charges
                FROM time_entries GROUP BY project_id
            ) te_s  ON te_s.project_id  = pl.project_id
            LEFT JOIN (
                SELECT i.project_id,
                       SUM(i.amount)                  AS invoiced_amount,
                       SUM(COALESCE(py.total_paid,0)) AS paid_amount
                FROM invoices i
                LEFT JOIN (
                    SELECT invoice_id, SUM(amount) AS total_paid
                    FROM payments GROUP BY invoice_id
                ) py ON py.invoice_id = i.id
                GROUP BY i.project_id
            ) inv_s ON inv_s.project_id = pl.project_id
            WHERE pl.stage IN ('Prospect', 'Active', 'On Hold')
            ORDER BY
                CASE pl.stage WHEN 'Active' THEN 1
                              WHEN 'On Hold' THEN 2
                              ELSE 3 END,
                client_name, project_name
        """).fetchall()
    return [dict(r) for r in rows]


def get_pipeline_source_teams() -> dict[int, str]:
    """Return project_id → name of consultant team with most billable hours."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT te.project_id, cg.group_name, SUM(te.non_z_hours) AS hrs
            FROM time_entries te
            JOIN consultant_groups cg ON cg.emp_nbr = te.emp_nbr
            WHERE te.project_id IS NOT NULL
            GROUP BY te.project_id, cg.group_name
        """).fetchall()
    by_project: dict[int, dict[str, float]] = {}
    for r in rows:
        by_project.setdefault(r["project_id"], {})[r["group_name"]] = r["hrs"]
    return {pid: max(groups, key=groups.__getitem__) for pid, groups in by_project.items()}


# ---------------------------------------------------------------------------
# Cross-project rollup (for Time Tracking "All Clients" view)
# ---------------------------------------------------------------------------

def get_cross_project_time_summary() -> list[dict]:
    """Return one row per project with aggregated billing, write-off and invoice totals."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                c.name        AS client_name,
                c.client_type AS client_type,
                p.name        AS project_name,
                p.id          AS project_id,
                COALESCE(pc_s.budget_amount,    0.0) AS budget_amount,
                COALESCE(te_s.billable_charges, 0.0) AS billable_charges,
                COALESCE(wo_s.write_off_amount, 0.0) AS write_off_amount,
                COALESCE(te_s.billable_charges, 0.0) -
                    COALESCE(wo_s.write_off_amount, 0.0) AS net_charges,
                COALESCE(inv_s.invoiced_amount,  0.0) AS invoiced_amount
            FROM projects p
            JOIN clients c ON c.id = p.client_id
            LEFT JOIN (
                SELECT project_id, SUM(budget_amount) AS budget_amount
                FROM project_codes GROUP BY project_id
            ) pc_s  ON pc_s.project_id  = p.id
            LEFT JOIN (
                SELECT project_id, SUM(non_z_charges) AS billable_charges
                FROM time_entries GROUP BY project_id
            ) te_s  ON te_s.project_id  = p.id
            LEFT JOIN (
                SELECT project_id, SUM(amount) AS write_off_amount
                FROM write_offs GROUP BY project_id
            ) wo_s  ON wo_s.project_id  = p.id
            LEFT JOIN (
                SELECT project_id, SUM(amount) AS invoiced_amount
                FROM invoices GROUP BY project_id
            ) inv_s ON inv_s.project_id = p.id
            WHERE COALESCE(te_s.billable_charges, 0) > 0
               OR COALESCE(pc_s.budget_amount,    0) > 0
               OR COALESCE(inv_s.invoiced_amount,  0) > 0
            ORDER BY c.name, p.name
        """).fetchall()
    return [dict(r) for r in rows]


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


def get_invoices_detailed(year: int | None = None) -> list[dict]:
    """Return one row per invoice with client metadata for dashboard filtering."""
    query = """
        SELECT i.id, i.date, i.year,
               strftime('%Y-%m', i.date) AS month,
               i.amount AS net, i.vat_amount AS vat,
               i.amount + i.vat_amount AS gross,
               c.name AS client, c.client_type, c.country
        FROM invoices i
        JOIN clients c ON c.id = i.client_id
    """
    params = []
    if year:
        query += " WHERE i.year = ?"
        params.append(year)
    query += " ORDER BY i.date"
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
    Adds: has_recurring flag, recurring_cy_budget (current-year occurrence totals),
    paid (total payments received), paid_{yr} and rec_budget_{yr} per year.
    """
    if years is None:
        cy = date.today().year
        years = [cy - i for i in range(4)]

    years = [int(y) for y in years]
    cy = date.today().year

    sel, inv_j, te_j, wo_j, rec_j, pay_j = "", "", "", "", "", ""
    for yr in years:
        sel += (
            f", COALESCE(inv_{yr}.invoiced,    0) AS invoiced_{yr}"
            f", COALESCE(te_{yr}.charges,      0) AS charges_{yr}"
            f", COALESCE(wo_{yr}.write_offs,   0) AS writeoffs_{yr}"
            f", COALESCE(rec_{yr}.rec_budget,  0) AS rec_budget_{yr}"
            f", COALESCE(pay_{yr}.paid,        0) AS paid_{yr}"
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
        rec_j += (
            f" LEFT JOIN ("
            f"SELECT pc2.project_id, SUM(rfo.amount) AS rec_budget"
            f" FROM recurring_fee_occurrences rfo"
            f" JOIN recurring_fees rf2 ON rf2.id = rfo.recurring_fee_id"
            f" JOIN project_codes pc2 ON pc2.id = rf2.project_code_id"
            f" WHERE SUBSTR(rfo.due_date,1,4)='{yr}'"
            f" GROUP BY pc2.project_id"
            f") rec_{yr} ON rec_{yr}.project_id = p.id"
        )
        pay_j += (
            f" LEFT JOIN ("
            f"SELECT i2.project_id, SUM(pay2.amount) AS paid"
            f" FROM payments pay2 JOIN invoices i2 ON i2.id = pay2.invoice_id"
            f" WHERE SUBSTR(pay2.date,1,4)='{yr}'"
            f" GROUP BY i2.project_id"
            f") pay_{yr} ON pay_{yr}.project_id = p.id"
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
            COALESCE(SUM(DISTINCT pc.budget_amount), 0) AS budget_code,
            COALESCE(te_all.billable_charges, 0)        AS billable_charges,
            COALESCE(wo_all.write_offs,       0)        AS write_offs,
            COALESCE(inv_all.invoiced,        0)        AS invoiced,
            COALESCE(pay_all.paid,            0)        AS paid,
            COALESCE(rf_flag.has_recurring,   0)        AS has_recurring,
            COALESCE(rec_cy.rec_budget,       0)        AS recurring_cy_budget
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
        LEFT JOIN (SELECT i2.project_id, SUM(pay2.amount) AS paid
                   FROM payments pay2 JOIN invoices i2 ON i2.id = pay2.invoice_id
                   GROUP BY i2.project_id) pay_all ON pay_all.project_id = p.id
        LEFT JOIN (SELECT pc2.project_id, 1 AS has_recurring
                   FROM recurring_fees rf2
                   JOIN project_codes pc2 ON pc2.id = rf2.project_code_id
                   WHERE rf2.status = 'Active'
                   GROUP BY pc2.project_id) rf_flag ON rf_flag.project_id = p.id
        LEFT JOIN (SELECT pc2.project_id, SUM(rfo.amount) AS rec_budget
                   FROM recurring_fee_occurrences rfo
                   JOIN recurring_fees rf2 ON rf2.id = rfo.recurring_fee_id
                   JOIN project_codes pc2 ON pc2.id = rf2.project_code_id
                   WHERE SUBSTR(rfo.due_date,1,4)='{cy}'
                   GROUP BY pc2.project_id) rec_cy ON rec_cy.project_id = p.id
        LEFT JOIN (
            SELECT te.project_id,
                   GROUP_CONCAT(DISTINCT COALESCE(cg.group_name, 'Other')) AS groups_with_hours,
                   GROUP_CONCAT(DISTINCT te.consultant) AS consultants_with_hours
            FROM time_entries te
            LEFT JOIN consultant_groups cg ON cg.consultant = te.consultant
            GROUP BY te.project_id
        ) grp_info ON grp_info.project_id = p.id
        {inv_j} {te_j} {wo_j} {rec_j} {pay_j}
        GROUP BY p.id
        ORDER BY c.name, p.name
    """
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["has_recurring"] = bool(d.get("has_recurring", 0))
        # Budget: use current-year recurring total for recurring projects,
        # else fall back to the sum of project-code budgets.
        d["budget"] = d["recurring_cy_budget"] if d["has_recurring"] else d["budget_code"]
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
            "SELECT id, emp_nbr, consultant, group_name, status FROM consultant_groups ORDER BY consultant"
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_consultant_group(consultant: str, group_name: str,
                            emp_nbr: str | None = None,
                            status: str | None = None) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM consultant_groups WHERE consultant = ?", (consultant,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE consultant_groups SET group_name=?, emp_nbr=COALESCE(?,emp_nbr), "
                "status=COALESCE(?,status) WHERE id=?",
                (group_name, emp_nbr, status, row["id"])
            )
        else:
            conn.execute(
                "INSERT INTO consultant_groups (consultant, group_name, emp_nbr, status) VALUES (?,?,?,?)",
                (consultant, group_name, emp_nbr, status or "Active")
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
    """Return the active record per consultant.

    Priority: is_preferred=1 first; if neither record has is_preferred set,
    manual beats time_tracking (legacy default).
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT b.id, b.emp_nbr, b.year, b.source, b.is_preferred,
                      b.billed, b.capped_paid_prebill, b.capped_unpaid_prebill,
                      b.charged_off, b.paid, b.unbilled,
                      b.hourly_rate, b.avg_annual_rate, b.notes, b.created_at
               FROM billing_basis b
               WHERE b.year = ?
                 AND b.id = (
                     SELECT id FROM billing_basis
                     WHERE emp_nbr = b.emp_nbr AND year = ?
                     ORDER BY is_preferred DESC,
                              CASE source WHEN 'manual' THEN 0 ELSE 1 END
                     LIMIT 1
                 )
               ORDER BY b.emp_nbr""",
            (year, year)
        ).fetchall()
    return [BillingBasis(**dict(r)) for r in rows]


def get_billing_basis_year_by_source(year: int, source: str) -> list[BillingBasis]:
    """Return all records for a year filtered by source ('manual' or 'time_tracking')."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, emp_nbr, year, source, is_preferred, billed, capped_paid_prebill, "
            "capped_unpaid_prebill, charged_off, paid, unbilled, hourly_rate, avg_annual_rate, notes, created_at "
            "FROM billing_basis WHERE year = ? AND source = ? ORDER BY emp_nbr",
            (year, source)
        ).fetchall()
    return [BillingBasis(**dict(r)) for r in rows]


def get_billing_basis(emp_nbr: str, year: int) -> BillingBasis | None:
    """Return the active record for a consultant.

    Priority: is_preferred=1 first; falls back to manual > time_tracking.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, emp_nbr, year, source, is_preferred, billed, capped_paid_prebill, "
            "capped_unpaid_prebill, charged_off, paid, unbilled, hourly_rate, avg_annual_rate, notes, created_at "
            "FROM billing_basis WHERE emp_nbr = ? AND year = ? "
            "ORDER BY is_preferred DESC, CASE source WHEN 'manual' THEN 0 ELSE 1 END LIMIT 1",
            (emp_nbr, year)
        ).fetchone()
    return BillingBasis(**dict(row)) if row else None


def get_billing_basis_by_source(emp_nbr: str, year: int, source: str) -> BillingBasis | None:
    """Return the record for a specific source, or None if not saved yet."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, emp_nbr, year, source, is_preferred, billed, capped_paid_prebill, "
            "capped_unpaid_prebill, charged_off, paid, unbilled, hourly_rate, avg_annual_rate, notes, created_at "
            "FROM billing_basis WHERE emp_nbr = ? AND year = ? AND source = ?",
            (emp_nbr, year, source)
        ).fetchone()
    return BillingBasis(**dict(row)) if row else None


def set_billing_basis_preferred(emp_nbr: str, year: int, source: str) -> None:
    """Explicitly mark one source as preferred for Annual Review calculations.

    Clears any existing preference for the same (emp_nbr, year) first.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE billing_basis SET is_preferred=0 WHERE emp_nbr=? AND year=?",
            (emp_nbr, year)
        )
        conn.execute(
            "UPDATE billing_basis SET is_preferred=1 WHERE emp_nbr=? AND year=? AND source=?",
            (emp_nbr, year, source)
        )


def get_monthly_billing_rate_breakdown(emp_nbr: str, year: int) -> list[dict]:
    """Per-period hours/charges/implied rate for one consultant in a given year.

    Used to compute the weighted average annual rate for the bonus calculation:
      avg_annual_rate = SUM(non_z_charges) / SUM(non_z_hours) across all periods.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT period,
                   SUM(non_z_hours)   AS non_z_hours,
                   SUM(non_z_charges) AS non_z_charges,
                   CASE WHEN SUM(non_z_hours) > 0
                        THEN ROUND(SUM(non_z_charges) / SUM(non_z_hours), 1)
                        ELSE 0.0 END  AS avg_nonz_rate,
                   SUM(total_hours)   AS total_hours,
                   SUM(total_charges) AS total_charges,
                   CASE WHEN SUM(total_hours) > 0
                        THEN ROUND(SUM(total_charges) / SUM(total_hours), 1)
                        ELSE 0.0 END  AS avg_total_rate
            FROM time_entries
            WHERE emp_nbr = ? AND SUBSTR(period, 1, 4) = ?
            GROUP BY period
            ORDER BY period
        """, (emp_nbr, str(year))).fetchall()
    return [dict(r) for r in rows]


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
    avg_annual_rate: float = 0.0,
    notes: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO billing_basis "
            "(emp_nbr, year, source, billed, capped_paid_prebill, capped_unpaid_prebill, "
            "charged_off, paid, unbilled, hourly_rate, avg_annual_rate, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(emp_nbr, year, source) DO UPDATE SET "
            "billed=excluded.billed, "
            "capped_paid_prebill=excluded.capped_paid_prebill, "
            "capped_unpaid_prebill=excluded.capped_unpaid_prebill, "
            "charged_off=excluded.charged_off, paid=excluded.paid, "
            "unbilled=excluded.unbilled, hourly_rate=excluded.hourly_rate, "
            "avg_annual_rate=excluded.avg_annual_rate, notes=excluded.notes",
            (emp_nbr, year, source, billed, capped_paid_prebill, capped_unpaid_prebill,
             charged_off, paid, unbilled, hourly_rate, avg_annual_rate, notes)
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
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO review_feedback (emp_nbr, year, area, comments, development_ideas, created_at) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(emp_nbr, year, area) DO UPDATE SET "
            "comments=excluded.comments, development_ideas=excluded.development_ideas",
            (emp_nbr, year, area, comments, development_ideas, now),
        )


def is_review_locked(emp_nbr: str, year: int) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM review_locks WHERE emp_nbr=? AND year=?", (emp_nbr, year)
        ).fetchone() is not None


def lock_review(emp_nbr: str, year: int) -> None:
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO review_locks (emp_nbr, year) VALUES (?,?)", (emp_nbr, year))


def unlock_review(emp_nbr: str, year: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM review_locks WHERE emp_nbr=? AND year=?", (emp_nbr, year))


def get_consultant_project_hours(consultant: str, year: int) -> list[dict]:
    """
    Per-project billable breakdown for a consultant in a given year.

    Excludes internal clients (client_type='internal' or client_code LIKE '0009%').
    Returns list of dicts ordered by fees (charges) descending:
        client, project_name, description, hours, fees,
        hours_pct, fees_pct, colleagues
    Colleagues = ' | '-separated names of other consultants with billable hours
    on the same project in the same year (subject consultant excluded).
    Keyed internally by project_id to avoid collisions when projects share a name.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                te.project_id,
                c.name                AS client,
                p.name                AS project_name,
                p.description         AS description,
                SUM(te.non_z_hours)   AS hours,
                SUM(te.non_z_charges) AS fees
            FROM time_entries te
            JOIN projects p ON p.id = te.project_id
            JOIN clients  c ON c.id = p.client_id
            WHERE te.consultant = ?
              AND SUBSTR(te.period, 1, 4) = ?
              AND c.client_type != 'internal'
              AND c.client_code NOT LIKE '0009%'
            GROUP BY te.project_id
            ORDER BY fees DESC
            """,
            (consultant, str(year)),
        ).fetchall()

        # Totals for this consultant that year (billable only, excl. internal)
        totals_row = conn.execute(
            """
            SELECT COALESCE(SUM(te.non_z_hours), 0)   AS total_hrs,
                   COALESCE(SUM(te.non_z_charges), 0) AS total_fees
            FROM time_entries te
            JOIN projects p ON p.id = te.project_id
            JOIN clients  c ON c.id = p.client_id
            WHERE te.consultant = ?
              AND SUBSTR(te.period, 1, 4) = ?
              AND c.client_type != 'internal'
              AND c.client_code NOT LIKE '0009%'
            """,
            (consultant, str(year)),
        ).fetchone()
        total_hrs  = totals_row["total_hrs"]  if totals_row else 0.0
        total_fees = totals_row["total_fees"] if totals_row else 0.0

        def _flip(name: str) -> str:
            """'Lastname, Firstname' → 'Firstname Lastname'; unchanged if no comma."""
            if ", " in name:
                last, first = name.split(", ", 1)
                return f"{first} {last}"
            return name

        # ------------------------------------------------------------------
        # Colleagues per project.
        # Join strategy: te2.project_id = te.project_id (same project) AND
        # te2.project_code_id must belong to that project (validated via the
        # project_codes table).  This means:
        #   • Different codes within the same project share colleagues (correct
        #     for multi-code real projects).
        #   • Suffixes of the same client_code that are assigned to DIFFERENT
        #     projects are excluded (e.g., a reassigned auto-created code no
        #     longer belongs to the default project).
        #   • Time entries whose project_code has been moved away from a project
        #     are excluded (project_codes.project_id is the authoritative source).
        # GROUP_CONCAT(DISTINCT x, sep) is illegal in SQLite — deduplicate in
        # a subquery and apply the separator in the outer query.
        # ------------------------------------------------------------------
        project_colleagues: dict[int, str] = {}
        coll_rows = conn.execute(
            """
            SELECT project_id,
                   GROUP_CONCAT(colleague, ' | ') AS others
            FROM (
                SELECT DISTINCT te.project_id, te2.consultant AS colleague
                FROM time_entries te
                JOIN projects p ON p.id = te.project_id
                JOIN clients  c ON c.id = p.client_id
                JOIN time_entries te2
                     ON te2.project_id = te.project_id
                    AND te2.project_code_id IN (
                        SELECT id FROM project_codes
                        WHERE project_id = te.project_id
                    )
                    AND SUBSTR(te2.period, 1, 4) = ?
                    AND te2.consultant != te.consultant
                    AND te2.non_z_hours > 0
                WHERE te.consultant = ?
                  AND SUBSTR(te.period, 1, 4) = ?
                  AND c.client_type != 'internal'
                  AND c.client_code NOT LIKE '0009%'
            )
            GROUP BY project_id
            """,
            (str(year), consultant, str(year)),
        ).fetchall()
        for cr in coll_rows:
            if cr["others"]:
                flipped = " | ".join(
                    _flip(n.strip()) for n in cr["others"].split(" | ") if n.strip()
                )
                project_colleagues[cr["project_id"]] = flipped
            else:
                project_colleagues[cr["project_id"]] = ""

        # ------------------------------------------------------------------
        # Teams per project — distinct consultant_groups.group_name values
        # for the same colleague population (same join as above).
        # ------------------------------------------------------------------
        project_teams: dict[int, str] = {}
        team_rows = conn.execute(
            """
            SELECT project_id,
                   GROUP_CONCAT(team, ' | ') AS teams
            FROM (
                SELECT DISTINCT te.project_id,
                       COALESCE(cg.group_name, 'Other') AS team
                FROM time_entries te
                JOIN projects p ON p.id = te.project_id
                JOIN clients  c ON c.id = p.client_id
                JOIN time_entries te2
                     ON te2.project_id = te.project_id
                    AND te2.project_code_id IN (
                        SELECT id FROM project_codes
                        WHERE project_id = te.project_id
                    )
                    AND SUBSTR(te2.period, 1, 4) = ?
                    AND te2.consultant != te.consultant
                    AND te2.non_z_hours > 0
                LEFT JOIN consultant_groups cg ON cg.consultant = te2.consultant
                WHERE te.consultant = ?
                  AND SUBSTR(te.period, 1, 4) = ?
                  AND c.client_type != 'internal'
                  AND c.client_code NOT LIKE '0009%'
            )
            GROUP BY project_id
            """,
            (str(year), consultant, str(year)),
        ).fetchall()
        for tr in team_rows:
            project_teams[tr["project_id"]] = tr["teams"] or ""

    result = []
    for r in rows:
        hrs_pct  = (r["hours"] / total_hrs  * 100) if total_hrs  > 0 else 0.0
        fees_pct = (r["fees"]  / total_fees * 100) if total_fees > 0 else 0.0
        result.append({
            "client":       r["client"],
            "project_name": r["project_name"],
            "description":  r["description"] or "",
            "hours":        round(r["hours"], 1),
            "fees":         round(r["fees"], 2),
            "hours_pct":    round(hrs_pct, 1),
            "fees_pct":     round(fees_pct, 1),
            "colleagues":   project_colleagues.get(r["project_id"], ""),
            "teams":        project_teams.get(r["project_id"], ""),
        })
    return result


# ---------------------------------------------------------------------------
# Recurring fees — helpers
# ---------------------------------------------------------------------------

def _add_months(d: date, months: int) -> date:
    """Return d + months months, clamping day to month-end as needed."""
    month = d.month - 1 + months
    year  = d.year + month // 12
    month = month % 12 + 1
    day   = min(d.day, _calendar.monthrange(year, month)[1])
    return date(year, month, day)


_FREQ_MONTHS = {"monthly": 1, "quarterly": 3, "semi-annual": 6, "annual": 12}


def _ensure_occurrences(conn, fee_id: int, horizon_years: int = 3) -> None:
    """Generate or extend occurrences for one recurring fee.

    - Stops at expected_end if set (never extends past it).
    - Otherwise extends to today + horizon_years.
    - Skips dates already present (UNIQUE constraint on fee_id + due_date).
    - Amounts are indexed annually from coverage_start year.
    """
    row = conn.execute("SELECT * FROM recurring_fees WHERE id = ?", (fee_id,)).fetchone()
    if not row or row["status"] == "Cancelled" or not row["coverage_start"]:
        return

    today        = date.today()
    horizon_end  = date(today.year + horizon_years, today.month, today.day)
    if row["expected_end"]:
        end = min(date.fromisoformat(row["expected_end"]), horizon_end)
    else:
        end = horizon_end

    freq_months  = _FREQ_MONTHS.get(row["frequency"], 12)
    start        = date.fromisoformat(row["coverage_start"])
    start_year   = start.year
    base_amount  = float(row["fee_amount"])
    base_split   = float(row["split_amount"])
    index_rate   = float(row["index_rate"]) if row["fee_type"] == "indexed" else 0.0

    last_row = conn.execute(
        "SELECT MAX(due_date) AS last FROM recurring_fee_occurrences WHERE recurring_fee_id = ?",
        (fee_id,)
    ).fetchone()
    last_date = date.fromisoformat(last_row["last"]) if last_row["last"] else None
    next_date  = _add_months(last_date, freq_months) if last_date else start

    if next_date > end:
        return  # already fully generated

    occurrences = []
    current = next_date
    while current <= end:
        years_elapsed = current.year - start_year
        factor  = (1 + index_rate) ** years_elapsed
        amount  = round(base_amount * factor, 2)
        split   = round(base_split  * factor, 2)
        occurrences.append((fee_id, current.isoformat(), amount, split))
        current = _add_months(current, freq_months)

    conn.executemany(
        "INSERT OR IGNORE INTO recurring_fee_occurrences "
        "(recurring_fee_id, due_date, amount, split_amount) VALUES (?, ?, ?, ?)",
        occurrences,
    )


# ---------------------------------------------------------------------------
# Recurring fees — CRUD
# ---------------------------------------------------------------------------

def get_recurring_fees(project_code_id: int, ensure_occurrences: bool = True) -> list[dict]:
    with get_connection() as conn:
        if ensure_occurrences:
            for fee in conn.execute(
                "SELECT id FROM recurring_fees WHERE project_code_id = ? AND status = 'Active'",
                (project_code_id,)
            ).fetchall():
                _ensure_occurrences(conn, fee["id"])
        rows = conn.execute(
            "SELECT * FROM recurring_fees WHERE project_code_id = ? ORDER BY coverage_start",
            (project_code_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_recurring_fees_for_project(project_id: int, ensure_occurrences: bool = True) -> list[dict]:
    """All recurring fees across all codes of a project."""
    with get_connection() as conn:
        fee_ids = conn.execute(
            "SELECT rf.id FROM recurring_fees rf "
            "JOIN project_codes pc ON pc.id = rf.project_code_id "
            "WHERE pc.project_id = ? AND rf.status = 'Active'",
            (project_id,)
        ).fetchall()
        if ensure_occurrences:
            for fid in fee_ids:
                _ensure_occurrences(conn, fid["id"])
        rows = conn.execute("""
            SELECT rf.*, pc.client_code, pc.client_suffix, pc.name AS code_name
            FROM recurring_fees rf
            JOIN project_codes pc ON pc.id = rf.project_code_id
            WHERE pc.project_id = ?
            ORDER BY rf.coverage_start
        """, (project_id,)).fetchall()
    return [dict(r) for r in rows]


def add_recurring_fee(project_code_id: int, description: str, fee_amount: float,
                      frequency: str, coverage_start: str, billing_type: str = "we_bill",
                      fee_type: str = "fixed", index_rate: float = 0.0,
                      expected_end: str = "", split_party: str = "",
                      split_amount: float = 0.0, auto_invoice: int = 0,
                      notes: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO recurring_fees "
            "(project_code_id, description, fee_amount, fee_type, index_rate, frequency, "
            "coverage_start, expected_end, billing_type, split_party, split_amount, "
            "auto_invoice, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_code_id, description, fee_amount, fee_type, index_rate, frequency,
             coverage_start, expected_end, billing_type, split_party, split_amount,
             auto_invoice, notes)
        )
        fee_id = cur.lastrowid
        _ensure_occurrences(conn, fee_id)
    return fee_id


def update_recurring_fee(fee_id: int, description: str, fee_amount: float,
                         fee_type: str, index_rate: float, frequency: str,
                         coverage_start: str, expected_end: str, billing_type: str,
                         split_party: str, split_amount: float,
                         auto_invoice: int, notes: str) -> None:
    """Update fee definition. Pending occurrences are regenerated from today forward."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE recurring_fees
            SET description=?, fee_amount=?, fee_type=?, index_rate=?, frequency=?,
                coverage_start=?, expected_end=?, billing_type=?, split_party=?,
                split_amount=?, auto_invoice=?, notes=?
            WHERE id=?
        """, (description, fee_amount, fee_type, index_rate, frequency,
              coverage_start, expected_end, billing_type, split_party,
              split_amount, auto_invoice, notes, fee_id))
        # Drop ALL pending occurrences (including past ones) so every occurrence
        # is regenerated with the updated amount/frequency from coverage_start.
        conn.execute("""
            DELETE FROM recurring_fee_occurrences
            WHERE recurring_fee_id = ? AND status = 'pending'
        """, (fee_id,))
        _ensure_occurrences(conn, fee_id)


def cancel_recurring_fee(fee_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE recurring_fees SET status='Cancelled', cancelled_at=date('now') WHERE id=?",
            (fee_id,)
        )
        conn.execute(
            "DELETE FROM recurring_fee_occurrences WHERE recurring_fee_id=? AND status='pending'",
            (fee_id,)
        )


# ---------------------------------------------------------------------------
# Occurrences — queries and status transitions
# ---------------------------------------------------------------------------

def get_occurrences(recurring_fee_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM recurring_fee_occurrences WHERE recurring_fee_id=? ORDER BY due_date",
            (recurring_fee_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_pending_occurrences(project_id: int | None = None,
                            billing_arrangement: str | None = None,
                            days_ahead: int = 90) -> list[dict]:
    """Pending occurrences due within days_ahead days.

    billing_arrangement filters by project.billing_arrangement (e.g. 'local').
    """
    cutoff = _add_months(date.today(), 0)  # today
    cutoff_str = date(
        date.today().year, date.today().month, date.today().day
    ).isoformat()
    ahead_str = date(
        date.today().year + (days_ahead // 365),
        date.today().month,
        min(date.today().day, _calendar.monthrange(
            date.today().year + (days_ahead // 365), date.today().month)[1])
    ).isoformat()
    # Simpler: use SQL date arithmetic
    params: list = []
    where  = ["rfo.status = 'pending'",
              "rfo.due_date <= date('now', ? || ' days')",
              "rf.status = 'Active'"]
    params.append(str(days_ahead))

    if project_id is not None:
        where.append("pc.project_id = ?")
        params.append(project_id)
    if billing_arrangement:
        where.append("p.billing_arrangement = ?")
        params.append(billing_arrangement)

    sql = f"""
        SELECT rfo.*, rf.description AS fee_description, rf.billing_type, rf.frequency,
               rf.split_party, pc.client_code, pc.client_suffix, pc.project_id,
               p.name AS project_name, c.name AS client_name,
               p.billing_arrangement
        FROM recurring_fee_occurrences rfo
        JOIN recurring_fees rf ON rf.id = rfo.recurring_fee_id
        JOIN project_codes  pc ON pc.id = rf.project_code_id
        JOIN projects        p ON p.id  = pc.project_id
        JOIN clients         c ON c.id  = p.client_id
        WHERE {' AND '.join(where)}
        ORDER BY rfo.due_date
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def invoice_occurrence(occurrence_id: int, invoice_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE recurring_fee_occurrences SET status='invoiced', invoice_id=? WHERE id=?",
            (invoice_id, occurrence_id)
        )


def update_occurrence_amount(occurrence_id: int, amount: float,
                             split_amount: float, notes: str = "") -> None:
    """Override the amount on a single pending occurrence."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE recurring_fee_occurrences "
            "SET amount=?, split_amount=?, notes=? WHERE id=? AND status='pending'",
            (round(amount, 2), round(split_amount, 2), notes, occurrence_id)
        )


def skip_occurrence(occurrence_id: int, note: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE recurring_fee_occurrences SET status='skipped', notes=? WHERE id=?",
            (note, occurrence_id)
        )


# ---------------------------------------------------------------------------
# Receivables — CRUD
# ---------------------------------------------------------------------------

def get_receivables(project_id: int | None = None,
                    outstanding_only: bool = False) -> list[dict]:
    """Return receivables with total_paid and outstanding_amount computed."""
    where  = []
    params: list = []
    if project_id is not None:
        where.append("r.project_id = ?")
        params.append(project_id)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = []
    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT r.*,
                   COALESCE(SUM(rp.amount), 0)                   AS total_paid,
                   r.expected_amount - COALESCE(SUM(rp.amount), 0) AS outstanding,
                   p.name  AS project_name,
                   c.name  AS client_name,
                   p.billing_arrangement
            FROM receivables r
            JOIN projects p ON p.id = r.project_id
            JOIN clients  c ON c.id = p.client_id
            LEFT JOIN receivable_payments rp ON rp.receivable_id = r.id
            {where_sql}
            GROUP BY r.id
            ORDER BY r.due_date
        """, params).fetchall()

    result = [dict(r) for r in rows]
    if outstanding_only:
        result = [r for r in result if r["outstanding"] > 0.001]
    return result


def add_receivable(project_id: int, description: str, expected_amount: float,
                   due_date: str, receivable_type: str = "capped",
                   cap_amount: float = 0.0, project_code_id: int | None = None,
                   occurrence_id: int | None = None, notes: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO receivables "
            "(project_id, project_code_id, occurrence_id, description, receivable_type, "
            "cap_amount, expected_amount, due_date, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, project_code_id, occurrence_id, description, receivable_type,
             cap_amount, expected_amount, due_date, notes)
        )
    return cur.lastrowid


def update_receivable(receivable_id: int, description: str, expected_amount: float,
                      due_date: str, receivable_type: str, cap_amount: float,
                      notes: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE receivables SET description=?, expected_amount=?, due_date=?, "
            "receivable_type=?, cap_amount=?, notes=? WHERE id=?",
            (description, expected_amount, due_date, receivable_type, cap_amount,
             notes, receivable_id)
        )


def add_receivable_payment(receivable_id: int, amount: float,
                           payment_date: str, notes: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO receivable_payments (receivable_id, amount, date, notes) "
            "VALUES (?, ?, ?, ?)",
            (receivable_id, amount, payment_date, notes)
        )
    return cur.lastrowid


def get_receivable_payments(receivable_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM receivable_payments WHERE receivable_id=? ORDER BY date",
            (receivable_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_outstanding_receivables_summary() -> list[dict]:
    """Cross-project receivables summary for dashboard widgets."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT r.id, r.project_id, r.description, r.expected_amount, r.due_date,
                   r.receivable_type,
                   COALESCE(SUM(rp.amount), 0)                    AS total_paid,
                   r.expected_amount - COALESCE(SUM(rp.amount), 0) AS outstanding,
                   p.name  AS project_name, p.billing_arrangement,
                   c.name  AS client_name
            FROM receivables r
            JOIN projects p ON p.id = r.project_id
            JOIN clients  c ON c.id = p.client_id
            LEFT JOIN receivable_payments rp ON rp.receivable_id = r.id
            GROUP BY r.id
            HAVING outstanding > 0.001
            ORDER BY r.due_date
        """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Recurring revenue forecast (for Pipeline Financial dashboard)
# ---------------------------------------------------------------------------

def get_interoffice_charges(year: int) -> list[dict]:
    """Time charges on receivable-arrangement projects for a given year.

    Used by the Revenue Dashboard to show inter-office revenue separately
    from locally invoiced revenue.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT c.name  AS client_name,
                   p.name  AS project_name,
                   p.id    AS project_id,
                   ROUND(SUM(te.non_z_hours),   1) AS billable_hours,
                   ROUND(SUM(te.non_z_charges), 2) AS billable_charges,
                   ROUND(SUM(te.z_hours),       1) AS overhead_hours
            FROM time_entries te
            JOIN projects p ON p.id = te.project_id
            JOIN clients  c ON c.id = p.client_id
            WHERE p.billing_arrangement = 'receivable'
              AND te.period LIKE ?
            GROUP BY p.id
            HAVING billable_charges > 0
            ORDER BY billable_charges DESC
        """, (f"{year}%",)).fetchall()
    return [dict(r) for r in rows]


def get_all_recurring_fees(status: str = "Active", ensure_occurrences: bool = True) -> list[dict]:
    """All recurring fees across all projects, joined with project / client info and next due date."""
    with get_connection() as conn:
        if ensure_occurrences:
            fee_ids = conn.execute(
                "SELECT id FROM recurring_fees WHERE status = ?", (status,)
            ).fetchall()
            for fid in fee_ids:
                _ensure_occurrences(conn, fid["id"])
        rows = conn.execute("""
            SELECT rf.*,
                   pc.client_code, pc.client_suffix, pc.name AS code_name,
                   pc.project_id,
                   p.name  AS project_name,
                   p.billing_arrangement,
                   c.name  AS client_name,
                   (SELECT MIN(rfo.due_date)
                    FROM recurring_fee_occurrences rfo
                    WHERE rfo.recurring_fee_id = rf.id AND rfo.status = 'pending'
                   ) AS next_due,
                   (SELECT rfo.amount
                    FROM recurring_fee_occurrences rfo
                    WHERE rfo.recurring_fee_id = rf.id AND rfo.status = 'pending'
                    ORDER BY rfo.due_date LIMIT 1
                   ) AS next_amount,
                   (SELECT rfo.split_amount
                    FROM recurring_fee_occurrences rfo
                    WHERE rfo.recurring_fee_id = rf.id AND rfo.status = 'pending'
                    ORDER BY rfo.due_date LIMIT 1
                   ) AS next_split_amount,
                   (SELECT COUNT(*) FROM recurring_fee_occurrences rfo
                    WHERE rfo.recurring_fee_id = rf.id AND rfo.status = 'invoiced'
                   ) AS invoiced_count,
                   (SELECT COUNT(*) FROM recurring_fee_occurrences rfo
                    WHERE rfo.recurring_fee_id = rf.id AND rfo.status = 'pending'
                   ) AS pending_count
            FROM recurring_fees rf
            JOIN project_codes pc ON pc.id = rf.project_code_id
            JOIN projects       p  ON p.id  = pc.project_id
            JOIN clients        c  ON c.id  = p.client_id
            WHERE rf.status = ?
            ORDER BY c.name, p.name, rf.coverage_start
        """, (status,)).fetchall()
    return [dict(r) for r in rows]


def get_recurring_revenue_forecast(horizon_years: int = 3) -> list[dict]:
    """Return pending occurrences bucketed by year for the pipeline forecast.

    Returns one row per (project_id, recurring_fee_id, year) with summed amounts.
    Only includes active recurring fees on local and receivable projects.
    """
    # Ensure occurrences are fresh before querying
    with get_connection() as conn:
        fee_ids = conn.execute(
            "SELECT id FROM recurring_fees WHERE status = 'Active'"
        ).fetchall()
    with get_connection() as conn:
        for fid in fee_ids:
            _ensure_occurrences(conn, fid["id"], horizon_years)

    cutoff_year = date.today().year + horizon_years
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT CAST(SUBSTR(rfo.due_date, 1, 4) AS INTEGER) AS year,
                   pc.project_id,
                   p.name  AS project_name,
                   p.billing_arrangement,
                   c.name  AS client_name,
                   rf.id   AS fee_id,
                   rf.description AS fee_description,
                   rf.billing_type,
                   rf.split_party,
                   SUM(rfo.amount)       AS fee_total,
                   SUM(rfo.split_amount) AS split_total
            FROM recurring_fee_occurrences rfo
            JOIN recurring_fees rf ON rf.id = rfo.recurring_fee_id
            JOIN project_codes  pc ON pc.id = rf.project_code_id
            JOIN projects        p ON p.id  = pc.project_id
            JOIN clients         c ON c.id  = p.client_id
            WHERE rfo.status = 'pending'
              AND CAST(SUBSTR(rfo.due_date, 1, 4) AS INTEGER) BETWEEN ? AND ?
              AND p.billing_arrangement IN ('local', 'receivable')
            GROUP BY year, rf.id
            ORDER BY year, p.name, rf.description
        """, (date.today().year, cutoff_year)).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at: {DB_PATH}")
