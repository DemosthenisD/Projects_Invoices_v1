"""
One-time seed script: import clients, addresses, projects, and project codes
from the NocoDb CSV exports.

Run from the repo root:
    python scripts/seed_from_csv.py           # live run
    python scripts/seed_from_csv.py --dry-run # preview only
"""
import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.db import init_db, get_connection  # noqa: E402

# ---------------------------------------------------------------------------
# Source file paths
# ---------------------------------------------------------------------------

NOCODB_DIR = Path(r"C:\Milliman Dropbox\Demosthenis Demosthenous\_Mill_CY\1 (Admin)\_Time Charges and Billing\Planning and Pipeline\_PlanTasks\InvoiceCodes\NocoDb_App")
CLIENTS_CSV = NOCODB_DIR / "clients_Tbl.csv"
MAINS_CSV   = NOCODB_DIR / "Projects_List_Real_OnlyMains_Tbl.csv"
FULL_CSV    = NOCODB_DIR / "Projects_List_Real_Tbl.csv"

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

TEMPLATE_MAP = {
    "Template-1": "template1_v3",
    "Template-2": "template2_v3",
}

STATUS_MAP = {
    "Active":                  "Active",
    "Closed":                  "Completed",
    "Finishished - Nut Paid":  "Completed",
    "Finished - ToInvoice":    "Active",
    "Future":                  "On Hold",
    "":                        "Active",
}

# Clients present in the project CSVs but absent from clients_Tbl.csv
EXTRA_CLIENTS = [
    {
        "name":              "Mikellidou",
        "client_code":       "0478MIK78",
        "name_for_invoices": "Mikellidou",
        "vat_number":        "",
        "vat_pct":           19.0,           # CY client (78 suffix pattern)
        "template":          "template1_v3",
        "address":           "",
    },
    {
        "name":              "Ethniki CY (ZET)",
        "client_code":       "0478ZET30",
        "name_for_invoices": "Ethniki Insurance",
        "vat_number":        "",
        "vat_pct":           19.0,           # CY entity of Ethniki
        "template":          "template1_v3",
        "address":           "",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float(val) -> float:
    """Parse a budget value; return 0.0 for blanks or '---'."""
    s = str(val).strip() if val is not None else ""
    if s in ("---", "", "None"):
        return 0.0
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return 0.0


def _status(val) -> str:
    return STATUS_MAP.get(str(val).strip(), "Active")


# ---------------------------------------------------------------------------
# CSV loaders
# ---------------------------------------------------------------------------

def load_clients() -> list[dict]:
    rows = []
    with open(CLIENTS_CSV, encoding="cp1252", newline="") as f:
        for r in csv.DictReader(f):
            name = str(r.get("Client", "")).strip()
            code = str(r.get("client_code", "")).strip()
            try:
                if not name or float(name) == 0 or not code:
                    continue
            except ValueError:
                pass
            if not name or not code:
                continue
            tmpl_raw = str(r.get("Invoice Template", "Template-1")).strip()
            vat_raw  = str(r.get("VAT %", "0")).strip()
            try:
                vat_pct = float(vat_raw) if vat_raw else 0.0
            except ValueError:
                vat_pct = 0.0
            if vat_pct == 2.0:  # Groupama test value → correct to 0
                vat_pct = 0.0
            rows.append({
                "name":              name,
                "client_code":       code,
                "name_for_invoices": str(r.get("Client Name (for Invoices)", "")).strip() or name,
                "vat_number":        str(r.get("VAT_No", "")).strip(),
                "vat_pct":           vat_pct,
                "template":          TEMPLATE_MAP.get(tmpl_raw, "template1_v3"),
                "address":           str(r.get("Address", "")).strip(),
            })
    return rows + EXTRA_CLIENTS


def load_projects() -> list[dict]:
    """Main projects only (Project Line = 1), skip ??? suffixes."""
    rows = []
    with open(MAINS_CSV, encoding="cp1252", newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("Project Line", "")).strip() != "1":
                continue
            suffix = str(r.get("client_suffix", "")).strip()
            if "?" in suffix:
                continue
            pname = str(r.get("Project", "")).strip()
            if not pname:
                continue
            rows.append({
                "client_name":  str(r.get("Client", "")).strip(),
                "client_code":  str(r.get("client_code", "")).strip(),
                "project_name": pname,
                "description":  str(r.get("description", "")).strip(),
                "status":       _status(r.get("Status", "")),
            })
    return rows


def load_project_codes() -> list[dict]:
    """All rows from the full CSV — includes sub-suffixes."""
    rows = []
    with open(FULL_CSV, encoding="cp1252", newline="") as f:
        for r in csv.DictReader(f):
            suffix = str(r.get("client_suffix", "")).strip()
            if "?" in suffix or not suffix:
                continue
            code = str(r.get("client_code", "")).strip()
            if not code:
                continue
            pname = str(r.get("Project", "")).strip()
            rows.append({
                "client_name":   str(r.get("Client", "")).strip(),
                "client_code":   code,
                "client_suffix": suffix,
                "project_name":  pname,
                "description":   str(r.get("description", "")).strip(),
                "budget_amount": _float(r.get("Suffix Budget", "")),
                "status":        _status(r.get("Status", "")),
            })
    return rows


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed(dry_run: bool = False) -> None:
    init_db()

    clients_data = load_clients()
    projects_data = load_projects()
    codes_data    = load_project_codes()

    # Runtime lookup maps
    code_to_client_id: dict[str, int] = {}    # client_code → clients.id
    proj_key_to_id:    dict[tuple, int] = {}  # (client_code, project_name) → projects.id
    client_meta:       dict[str, dict] = {c["client_code"]: c for c in clients_data}

    with get_connection() as conn:

        # ── 1. Clients ──────────────────────────────────────────────────
        print("\n=== CLIENTS ===")
        for c in clients_data:
            # Match by client_code first, then by name (handles pre-existing rows)
            row = conn.execute(
                "SELECT id FROM clients WHERE client_code = ?", (c["client_code"],)
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT id FROM clients WHERE name = ?", (c["name"],)
                ).fetchone()
            if row:
                if not dry_run:
                    conn.execute(
                        "UPDATE clients SET name=?, name_for_invoices=?, client_code=?, vat_number=? WHERE id=?",
                        (c["name"], c["name_for_invoices"], c["client_code"], c["vat_number"], row["id"])
                    )
                code_to_client_id[c["client_code"]] = row["id"]
                print(f"  UPDATED  {c['client_code']}  {c['name']}")
            else:
                if not dry_run:
                    cur = conn.execute(
                        "INSERT INTO clients (name, name_for_invoices, client_code, vat_number) "
                        "VALUES (?,?,?,?)",
                        (c["name"], c["name_for_invoices"], c["client_code"], c["vat_number"])
                    )
                    code_to_client_id[c["client_code"]] = cur.lastrowid
                else:
                    code_to_client_id[c["client_code"]] = -1  # placeholder for dry-run
                print(f"  INSERT   {c['client_code']}  {c['name']}")

            # Address (insert only if not already present)
            addr = c.get("address", "").strip()
            cid  = code_to_client_id.get(c["client_code"])
            if addr and cid and cid != -1 and not dry_run:
                conn.execute(
                    "INSERT OR IGNORE INTO addresses (client_id, address) VALUES (?,?)",
                    (cid, addr)
                )

        # ── 2. Projects ─────────────────────────────────────────────────
        print("\n=== PROJECTS ===")
        for p in projects_data:
            cid = code_to_client_id.get(p["client_code"])
            if not cid:
                row = conn.execute(
                    "SELECT id FROM clients WHERE client_code=?", (p["client_code"],)
                ).fetchone()
                if row:
                    cid = row["id"]
                    code_to_client_id[p["client_code"]] = cid
            if not cid:
                print(f"  SKIP (no client)  {p['client_code']}  {p['project_name']}")
                continue

            meta     = client_meta.get(p["client_code"], {})
            vat_pct  = meta.get("vat_pct", 0.0)
            template = meta.get("template", "template1_v3")
            status   = p["status"]

            row = conn.execute(
                "SELECT id FROM projects WHERE client_id=? AND name=?",
                (cid, p["project_name"])
            ).fetchone()
            if row:
                if not dry_run:
                    conn.execute(
                        "UPDATE projects SET description=?, vat_pct=?, template=?, status=? WHERE id=?",
                        (p["description"], vat_pct, template, status, row["id"])
                    )
                proj_key_to_id[(p["client_code"], p["project_name"])] = row["id"]
                print(f"  UPDATED  {p['client_code']}  {p['project_name']}")
            else:
                if not dry_run:
                    cur = conn.execute(
                        "INSERT INTO projects "
                        "(client_id, name, description, vat_pct, template, status) "
                        "VALUES (?,?,?,?,?,?)",
                        (cid, p["project_name"], p["description"], vat_pct, template, status)
                    )
                    proj_key_to_id[(p["client_code"], p["project_name"])] = cur.lastrowid
                else:
                    proj_key_to_id[(p["client_code"], p["project_name"])] = -1
                print(f"  INSERT   {p['client_code']}  {p['project_name']}")

        # ── 3. Project Codes ────────────────────────────────────────────
        print("\n=== PROJECT CODES ===")
        seen: set[tuple] = set()  # (client_code, client_suffix) — first-wins dedup

        for pc in codes_data:
            key = (pc["client_code"], pc["client_suffix"])
            if key in seen:
                print(f"  SKIP dup {pc['client_code']}-{pc['client_suffix']}  "
                      f"(already mapped; this suffix also appears in '{pc['project_name']}')")
                continue
            seen.add(key)

            # Resolve project_id
            proj_id = proj_key_to_id.get((pc["client_code"], pc["project_name"]))
            if not proj_id:
                cid = code_to_client_id.get(pc["client_code"])
                if not cid:
                    row = conn.execute(
                        "SELECT id FROM clients WHERE client_code=?", (pc["client_code"],)
                    ).fetchone()
                    cid = row["id"] if row else None
                if cid and pc["project_name"]:
                    row = conn.execute(
                        "SELECT id FROM projects WHERE client_id=? AND name=?",
                        (cid, pc["project_name"])
                    ).fetchone()
                    proj_id = row["id"] if row else None

            if not proj_id:
                print(f"  SKIP (no proj) {pc['client_code']}-{pc['client_suffix']}  {pc['project_name']}")
                continue

            row = conn.execute(
                "SELECT id FROM project_codes WHERE client_code=? AND client_suffix=? AND date_start=''",
                (pc["client_code"], pc["client_suffix"])
            ).fetchone()
            if row:
                print(f"  EXISTS   {pc['client_code']}-{pc['client_suffix']}")
            else:
                if not dry_run:
                    conn.execute(
                        "INSERT INTO project_codes "
                        "(project_id, client_code, client_suffix, name, description, budget_amount, status, date_start, date_end) "
                        "VALUES (?,?,?,?,?,?,?,'','')",
                        (proj_id, pc["client_code"], pc["client_suffix"],
                         pc["project_name"], pc["description"],
                         pc["budget_amount"], pc["status"])
                    )
                print(f"  INSERT   {pc['client_code']}-{pc['client_suffix']}  "
                      f"-> {pc['project_name']}  budget={pc['budget_amount']:.0f}")

    mode = "DRY RUN — no changes written" if dry_run else "Done"
    print(f"\n{mode}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed InvoiceApp DB from NocoDb CSV exports.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be inserted/updated without touching the DB.")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)
