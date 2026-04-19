"""
Seed consultant_groups from the Settings sheet of the ICEE Plan CY Excel file.

Column C (index 2) = consultant name (Last, First format)
Column D (index 3) = team ('CY' or 'Other')

Mapping: CY → 'Local', Other → 'Other'
ICEE group is left empty and must be assigned via the Time Tracking UI.

Run from the repo root:
    python scripts/seed_consultant_groups.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.db import init_db, upsert_consultant_group  # noqa: E402

EXCEL_PATH = Path(
    r"C:\Milliman Dropbox\Demosthenis Demosthenous\_Mill_CY\1 (Admin)"
    r"\_Time Charges and Billing\Planning and Pipeline"
    r"\ICEE Plan CY_v5 2024 (Chrgs_1124 - Invoices_191124 - Plan_311222) 02_05_2025.xlsm"
)

TEAM_MAP = {
    "CY":    "Local",
    "Other": "Other",
}


def load_consultants() -> list[tuple[str, str]]:
    """Returns list of (name, group_name) from Settings sheet."""
    import openpyxl
    wb = openpyxl.load_workbook(str(EXCEL_PATH), read_only=True, data_only=True, keep_links=False)
    ws = wb["Settings"]
    consultants = []
    for row in ws.iter_rows(min_row=1, max_row=200, values_only=True):
        name = row[2] if len(row) > 2 else None   # column C
        team = row[3] if len(row) > 3 else None   # column D
        if not name or not isinstance(name, str):
            continue
        name = name.strip()
        team = str(team).strip() if team else "Other"
        # skip header row
        if name.lower() in ("name_fam_last_first", "name", "consultant"):
            continue
        group = TEAM_MAP.get(team, "Other")
        consultants.append((name, group))
    return consultants


def seed() -> None:
    init_db()
    consultants = load_consultants()
    print(f"Loaded {len(consultants)} consultants from Settings sheet.")
    for name, group in consultants:
        upsert_consultant_group(consultant=name, group_name=group)
        print(f"  {group:8s}  {name}")
    print("\nDone.")


if __name__ == "__main__":
    seed()
