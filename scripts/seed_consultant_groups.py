"""
Seed consultant_groups from CONSULTANTS.csv in the repo root.

Columns: name_fam_last_first, Team, Reg Rate, Local Rate
Team values: CY → 'Local', ICEE → 'ICEE', Other → 'Other'

Run from the repo root:
    python scripts/seed_consultant_groups.py
"""
import sys
import csv
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.db import init_db, upsert_consultant_group  # noqa: E402

CSV_PATH = REPO_ROOT / "CONSULTANTS.csv"

TEAM_MAP = {
    "CY":    "Local",
    "ICEE":  "ICEE",
    "Other": "Other",
}


def load_consultants() -> list[tuple[str, str]]:
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = str(r.get("name_fam_last_first", "")).strip()
            team = str(r.get("Team", "")).strip()
            if not name:
                continue
            group = TEAM_MAP.get(team, "Other")
            rows.append((name, group))
    return rows


def seed() -> None:
    init_db()
    consultants = load_consultants()
    print(f"Loaded {len(consultants)} consultants from {CSV_PATH.name}")
    for name, group in consultants:
        upsert_consultant_group(consultant=name, group_name=group)
        print(f"  {group:8s}  {name}")
    print("\nDone.")


if __name__ == "__main__":
    seed()
