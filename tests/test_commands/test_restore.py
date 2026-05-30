"""Tests for commands/restore.py — CMD-02 scenarios."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.audit import AuditEventType
from bensdorp1.db.schema import metadata

runner = CliRunner()


@pytest.fixture
def valid_backup_db(tmp_path: Path) -> Path:
    """Create a SQLite file with all 8 expected tables for restore happy-path tests."""
    from sqlalchemy.engine import URL, create_engine

    backup_path = tmp_path / "bensdorp1-test-backup.db"
    url = URL.create("sqlite+pysqlite", database=str(backup_path))
    engine = create_engine(url)
    try:
        metadata.create_all(engine)
    finally:
        engine.dispose()  # CRITICAL on Windows
    return backup_path


def test_restore_invalid_path(tmp_path: Path, db_engine: Engine) -> None:
    """restore with a non-existent path exits code 1 with 'not found' message."""
    missing = tmp_path / "does_not_exist.db"
    mock_log = MagicMock()

    with (
        patch("bensdorp1.commands.restore.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.restore.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.restore.run_migrations"),
        patch("bensdorp1.commands.restore.log_event", mock_log),
    ):
        result = runner.invoke(app, ["restore", str(missing)])

    assert result.exit_code == 1
    assert "not found" in result.output.lower() or "File not found" in result.output
    mock_log.assert_not_called()


def test_restore_schema_invalid(tmp_path: Path, db_engine: Engine) -> None:
    """restore with an empty/non-SQLite file exits code 1; schema validation error."""
    bogus = tmp_path / "empty.db"
    bogus.write_bytes(b"")
    mock_log = MagicMock()

    with (
        patch("bensdorp1.commands.restore.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.restore.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.restore.run_migrations"),
        patch("bensdorp1.commands.restore.log_event", mock_log),
    ):
        result = runner.invoke(app, ["restore", str(bogus)])

    assert result.exit_code == 1
    assert (
        "schema validation" in result.output.lower()
        or "failed schema" in result.output.lower()
    )
    # No prompt was shown — schema validation precedes prompts
    assert "Replace active database" not in result.output
    mock_log.assert_not_called()


def test_restore_first_confirm_no(
    valid_backup_db: Path, db_engine: Engine, tmp_path: Path
) -> None:
    """restore with 'n' at first prompt exits 0; no pre-restore backup or file copy."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "bensdorp1.db").write_bytes(b"placeholder")
    mock_log = MagicMock()

    with (
        patch("bensdorp1.commands.restore.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.restore.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.restore.run_migrations"),
        patch("bensdorp1.commands.restore.log_event", mock_log),
    ):
        result = runner.invoke(app, ["restore", str(valid_backup_db)], input="n\n")

    assert result.exit_code == 0
    mock_log.assert_not_called()
    # No pre-restore backup created
    backups_dir = tmp_path / "backups"
    assert (
        not backups_dir.exists()
        or len(list(backups_dir.glob("bensdorp1-pre-restore-*.db"))) == 0
    )
    # Active DB content is unchanged
    assert (tmp_path / "data" / "bensdorp1.db").read_bytes() == b"placeholder"


def test_restore_second_confirm_no(
    valid_backup_db: Path, db_engine: Engine, tmp_path: Path
) -> None:
    """restore with 'y' then 'n' at second prompt exits 0; no pre-restore backup."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "bensdorp1.db").write_bytes(b"placeholder")
    mock_log = MagicMock()

    with (
        patch("bensdorp1.commands.restore.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.restore.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.restore.run_migrations"),
        patch("bensdorp1.commands.restore.log_event", mock_log),
    ):
        result = runner.invoke(app, ["restore", str(valid_backup_db)], input="y\nn\n")

    assert result.exit_code == 0
    mock_log.assert_not_called()
    # No pre-restore backup created
    backups_dir = tmp_path / "backups"
    assert (
        not backups_dir.exists()
        or len(list(backups_dir.glob("bensdorp1-pre-restore-*.db"))) == 0
    )
    # Active DB content is unchanged
    assert (tmp_path / "data" / "bensdorp1.db").read_bytes() == b"placeholder"


def test_restore_full_flow(
    valid_backup_db: Path, db_engine: Engine, tmp_path: Path
) -> None:
    """restore full happy path: validates, two confirms, pre-restore backup created."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    active_db = tmp_path / "data" / "bensdorp1.db"
    active_db.write_bytes(b"placeholder active db content")
    mock_log = MagicMock()

    with (
        patch("bensdorp1.commands.restore.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.restore.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.restore.run_migrations"),
        patch("bensdorp1.commands.restore.log_event", mock_log),
    ):
        result = runner.invoke(app, ["restore", str(valid_backup_db)], input="y\ny\n")

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "Database restored." in result.output

    # Pre-restore backup was created
    # (create_backup names files bensdorp1-{timestamp}.db)
    backups_dir = tmp_path / "backups"
    pre_restore_files = [
        f for f in backups_dir.glob("bensdorp1-*.db") if f.name != "bensdorp1-latest.db"
    ]
    assert len(pre_restore_files) == 1

    # Active DB was overwritten with valid_backup_db content
    assert active_db.read_bytes() == valid_backup_db.read_bytes()

    # log_event called once with RESTORE_PERFORMED and correct payload
    mock_log.assert_called_once()
    call_args = mock_log.call_args
    # Second positional arg is event_type
    assert call_args.args[1] == AuditEventType.RESTORE_PERFORMED
    payload = call_args.kwargs.get("payload")
    assert payload is not None
    assert "restored_from" in payload
    assert "pre_restore_backup" in payload
