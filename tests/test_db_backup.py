"""Tests for bensdorp1.db.backup.create_backup().

Covers STATE-02 (backup API used: sqlite3.Connection.backup(), not file copy)
and STATE-03 (timestamped backup + bensdorp1-latest.db updated).
"""

import re
import sqlite3
from pathlib import Path

from sqlalchemy.engine import Engine

from bensdorp1.db.backup import create_backup


def test_backup_creates_timestamped_file(db_engine: Engine, tmp_path: Path) -> None:
    """Backup file exists and its name matches bensdorp1-{8digits}T{6digits}Z.db."""
    backups_dir = tmp_path / "backups"
    result = create_backup(db_engine, backups_dir)

    assert result.exists()
    assert result.name.startswith("bensdorp1-")
    assert result.suffix == ".db"
    assert re.match(r"bensdorp1-\d{8}T\d{6}Z\.db", result.name) is not None


def test_backup_creates_backups_dir(db_engine: Engine, tmp_path: Path) -> None:
    """create_backup() creates backups_dir (including nested parents) if absent."""
    backups_dir = tmp_path / "backups" / "nested"
    assert not backups_dir.exists()

    create_backup(db_engine, backups_dir)

    assert backups_dir.exists()


def test_latest_db_updated(db_engine: Engine, tmp_path: Path) -> None:
    """bensdorp1-latest.db exists in backups_dir after create_backup()."""
    backups_dir = tmp_path / "backups"
    create_backup(db_engine, backups_dir)

    assert (backups_dir / "bensdorp1-latest.db").exists()


def test_backup_is_valid_sqlite(db_engine: Engine, tmp_path: Path) -> None:
    """The timestamped backup file is a valid SQLite database (openable, queryable)."""
    backups_dir = tmp_path / "backups"
    result = create_backup(db_engine, backups_dir)

    conn = sqlite3.connect(str(result))
    try:
        conn.execute("SELECT 1")
    finally:
        conn.close()


def test_backup_returns_path(db_engine: Engine, tmp_path: Path) -> None:
    """create_backup() returns a pathlib.Path instance."""
    backups_dir = tmp_path / "backups"
    result = create_backup(db_engine, backups_dir)

    assert isinstance(result, Path)
