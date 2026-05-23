"""SQLite backup primitive using sqlite3.Connection.backup().

Create a timestamped snapshot of the live database and update
bensdorp1-latest.db via shutil.copy2.

STATE-02: uses sqlite3.Connection.backup() (NOT shutil.copy on the live file).
STATE-03: bensdorp1-latest.db is updated via shutil.copy2 (NOT symlink — Windows
          requires admin for symlinks; [WinError 1314] confirmed on this machine).

Used by: every state-changing command (buy, sell, fix, cash) after each write.
"""

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine


def create_backup(engine: Engine, backups_dir: Path) -> Path:
    """Create a timestamped backup and update bensdorp1-latest.db.

    Uses sqlite3.Connection.backup() accessed via the SQLAlchemy engine's
    raw connection pool proxy.  This API takes a consistent snapshot even if
    a writer is active — file-level copy on a live database can corrupt.

    Args:
        engine:      SQLAlchemy Engine connected to the source database.
        backups_dir: Directory in which to write backup files.  Created
                     (including any missing parents) if it does not exist.

    Returns:
        Path to the newly created timestamped backup file.
    """
    backups_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    backup_path = backups_dir / f"bensdorp1-{ts}.db"
    latest_path = backups_dir / "bensdorp1-latest.db"

    # Unwrap pool proxy → underlying sqlite3.Connection
    raw_conn = engine.raw_connection()
    try:
        sqlite_conn = raw_conn.driver_connection
        if not isinstance(sqlite_conn, sqlite3.Connection):
            raise RuntimeError(
                f"Expected sqlite3.Connection from pool; got {type(sqlite_conn)!r}. "
                "Cannot create backup."
            )
        backup_sqlite_conn = sqlite3.connect(str(backup_path))
        try:
            sqlite_conn.backup(backup_sqlite_conn)
        finally:
            backup_sqlite_conn.close()
    finally:
        raw_conn.close()

    # Update latest.db via copy2 — NOT symlink (Windows requires admin for symlinks)
    shutil.copy2(backup_path, latest_path)

    return backup_path
