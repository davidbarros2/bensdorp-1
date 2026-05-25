"""Tests for commands/last.py — CMD-04 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import scans

runner = CliRunner()


def test_last_empty_state_no_scans(tmp_path: Path) -> None:
    """last prints info message when no scans exist."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = None

    with (
        patch("bensdorp1.commands.last.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.last.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.last.run_migrations"),
    ):
        result = runner.invoke(app, ["last"])

    assert result.exit_code == 0
    assert "No scans recorded yet" in result.output


def test_last_shows_most_recent_scan_output(db_engine: Engine, tmp_path: Path) -> None:
    """last shows raw_output of most recent scan."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(scans).values(
                scan_date=datetime(2026, 5, 21, tzinfo=UTC),
                regime_active=True,
                candidate_count=10,
                exit_trigger_count=0,
                raw_output="Scan for 2026-05-21\n=== regime: Bull ===",
                created_at=datetime(2026, 5, 21, tzinfo=UTC),
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.last.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.last.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.last.run_migrations"),
    ):
        result = runner.invoke(app, ["last"])

    assert result.exit_code == 0
    assert "Scan for 2026-05-21" in result.output
