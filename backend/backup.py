"""One-click backup of the database (and generated files)."""
import os
import shutil
import sqlite3
from datetime import datetime

import backend.db as db
import shared.config as cfg


def _dir_size(path: str) -> int:
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(path) for f in fs)


def list_backups(backup_dir: str | None = None) -> list[dict]:
    """Existing backups, newest first: [{name, path, size}]."""
    root = backup_dir or cfg.BACKUP_DIR
    if not os.path.isdir(root):
        return []
    names = sorted((n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n))), reverse=True)
    return [{"name": n, "path": os.path.join(root, n), "size": _dir_size(os.path.join(root, n))} for n in names]


def create_backup(include_exports: bool = True, keep: int = 30, backup_dir: str | None = None) -> dict:
    """Copy the live database (consistent snapshot) and optionally exports/ into a new dated folder.

    The database is copied with SQLite's online backup API, so it is safe while the app is running.
    Keeps the newest `keep` backup folders and deletes older ones.
    Returns {path, db_bytes, exports_files, integrity, pruned}.
    """
    root = backup_dir or cfg.BACKUP_DIR
    dest = os.path.join(root, datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    os.makedirs(dest)

    src = sqlite3.connect(db.DB_PATH)
    dst = sqlite3.connect(os.path.join(dest, "invoiceapp.db"))
    try:
        src.backup(dst)
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        dst.close()
        src.close()

    n_files = 0
    if include_exports and os.path.isdir(cfg.EXPORTS_DIR):
        shutil.copytree(cfg.EXPORTS_DIR, os.path.join(dest, "exports"))
        n_files = sum(len(fs) for _, _, fs in os.walk(os.path.join(dest, "exports")))

    pruned = 0
    for old in list_backups(root)[keep:]:
        shutil.rmtree(old["path"], ignore_errors=True)
        pruned += 0 if os.path.exists(old["path"]) else 1

    return {
        "path": dest,
        "db_bytes": os.path.getsize(os.path.join(dest, "invoiceapp.db")),
        "exports_files": n_files,
        "integrity": integrity,
        "pruned": pruned,
    }
