"""Tests for commands/history.py — CMD-05 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import scan_candidates, scans

runner = CliRunner()


def test_history_empty_state_when_no_scans(tmp_path: Path) -> None:
    """history shows info message when the scans table is empty."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchall.return_value = []

    with (
        patch("bensdorp1.commands.history.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.history.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.history.run_migrations"),
    ):
        result = runner.invoke(app, ["history"])

    assert result.exit_code == 0
    assert "No scans recorded yet" in result.output


def test_history_shows_compact_table_ordered_by_date_desc(
    db_engine: Engine, tmp_path: Path
) -> None:
    """history shows compact table ordered by scan_date DESC with top-3 candidates."""
    with db_engine.connect() as conn:
        # Insert 3 scans in ascending date order
        conn.execute(
            insert(scans).values(
                scan_date=datetime(2026, 5, 19, tzinfo=UTC),
                regime_active=True,
                candidate_count=10,
                exit_trigger_count=0,
                raw_output=None,
                created_at=datetime(2026, 5, 19, 20, 0, tzinfo=UTC),
            )
        )

        r2 = conn.execute(
            insert(scans).values(
                scan_date=datetime(2026, 5, 20, tzinfo=UTC),
                regime_active=True,
                candidate_count=8,
                exit_trigger_count=1,
                raw_output=None,
                created_at=datetime(2026, 5, 20, 20, 0, tzinfo=UTC),
            )
        )
        scan2_id = r2.inserted_primary_key[0]

        conn.execute(
            insert(scans).values(
                scan_date=datetime(2026, 5, 21, tzinfo=UTC),
                regime_active=False,
                candidate_count=0,
                exit_trigger_count=2,
                raw_output=None,
                created_at=datetime(2026, 5, 21, 20, 0, tzinfo=UTC),
            )
        )

        # Add top-3 candidates for scan2 (middle scan)
        conn.execute(
            insert(scan_candidates).values(
                scan_id=scan2_id,
                symbol="NVDA",
                rank=1,
                roc200=0.45,
                close=900.0,
                suggested_shares=5,
            )
        )
        conn.execute(
            insert(scan_candidates).values(
                scan_id=scan2_id,
                symbol="AAPL",
                rank=2,
                roc200=0.38,
                close=180.0,
                suggested_shares=25,
            )
        )
        conn.execute(
            insert(scan_candidates).values(
                scan_id=scan2_id,
                symbol="MSFT",
                rank=3,
                roc200=0.32,
                close=400.0,
                suggested_shares=12,
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.history.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.history.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.history.run_migrations"),
    ):
        result = runner.invoke(app, ["history"])

    assert result.exit_code == 0
    # All three scan dates present
    assert "2026-05-19" in result.output
    assert "2026-05-20" in result.output
    assert "2026-05-21" in result.output
    # Top-3 candidates for scan2 should appear comma-separated
    assert "NVDA, AAPL, MSFT" in result.output
    # Bear day (scan3, 2026-05-21) has no candidates → em dash
    assert "—" in result.output


def test_history_limit_flag_returns_only_n_rows(
    db_engine: Engine, tmp_path: Path
) -> None:
    """history --limit 2 returns only the 2 most recent rows."""
    with db_engine.connect() as conn:
        for day in (19, 20, 21):
            conn.execute(
                insert(scans).values(
                    scan_date=datetime(2026, 5, day, tzinfo=UTC),
                    regime_active=True,
                    candidate_count=5,
                    exit_trigger_count=0,
                    raw_output=None,
                    created_at=datetime(2026, 5, day, 20, 0, tzinfo=UTC),
                )
            )
        conn.commit()

    with (
        patch("bensdorp1.commands.history.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.history.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.history.run_migrations"),
    ):
        result = runner.invoke(app, ["history", "--limit", "2"])

    assert result.exit_code == 0
    # Only the 2 most recent dates (DESC order: 21, 20)
    assert "2026-05-21" in result.output
    assert "2026-05-20" in result.output
    # The oldest date (19) should NOT appear
    assert "2026-05-19" not in result.output


def test_history_invalid_since_exits_code_1(tmp_path: Path) -> None:
    """history --since with invalid date exits code 1 with error message."""
    mock_engine = MagicMock()

    with (
        patch("bensdorp1.commands.history.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.history.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.history.run_migrations"),
    ):
        result = runner.invoke(app, ["history", "--since", "not-a-date"])

    assert result.exit_code == 1
    assert "Invalid --since" in result.output
