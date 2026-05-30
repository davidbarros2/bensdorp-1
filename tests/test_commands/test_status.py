"""Tests for commands/status.py — CMD-14 scenarios."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import constituents_cache, scans

runner = CliRunner()


def test_status_shows_four_sections(db_engine: Engine, tmp_path: Path) -> None:
    """status shows all 4 section headers when DB has fresh data."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="AAPL",
                company_name="Apple Inc.",
                fetched_at=datetime.now(UTC),
            )
        )
        conn.execute(
            insert(scans).values(
                scan_date=datetime.now(UTC),
                regime_active=True,
                candidate_count=5,
                exit_trigger_count=0,
                created_at=datetime.now(UTC),
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.status.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.status.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.status.run_migrations"),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "Data status" in result.output
    assert "Backup status" in result.output
    assert "Database status" in result.output
    assert "Operational status" in result.output


def test_status_ok_constituents(db_engine: Engine, tmp_path: Path) -> None:
    """status shows [OK] when constituents were fetched within the last 7 days."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="AAPL",
                company_name="Apple Inc.",
                fetched_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.status.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.status.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.status.run_migrations"),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "[OK]" in result.output


def test_status_stale_constituents(db_engine: Engine, tmp_path: Path) -> None:
    """status shows [STALE] when constituents were fetched 10 days ago (>7 days)."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="AAPL",
                company_name="Apple Inc.",
                fetched_at=datetime.now(UTC) - timedelta(days=10),
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.status.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.status.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.status.run_migrations"),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "[STALE]" in result.output


def test_status_integrity_failed(db_engine: Engine, tmp_path: Path) -> None:
    """status shows FAILED when PRAGMA integrity_check returns multiple rows.

    Uses a real in-memory engine for all sections and patches only
    _database_section to return a failed integrity result, avoiding the
    fragile scalar call-order dependency of a fully hand-rolled mock.
    """
    failed_db_section = {
        "File size": "1.0 KB",
        "Integrity check": "FAILED",
    }

    with (
        patch("bensdorp1.commands.status.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.status.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.status.run_migrations"),
        patch(
            "bensdorp1.commands.status._database_section",
            return_value=failed_db_section,
        ),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "FAILED" in result.output


def test_status_no_backups_does_not_crash(db_engine: Engine, tmp_path: Path) -> None:
    """status exits 0 and shows 'No backups found' when backups directory is absent."""
    # Do NOT create tmp_path / "backups" — test the missing-directory guard
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="AAPL",
                company_name="Apple Inc.",
                fetched_at=datetime.now(UTC),
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.status.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.status.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.status.run_migrations"),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "No backups found" in result.output
    assert "Traceback" not in result.output
