"""Tests for commands/buy.py — CMD-06 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import (
    audit_log,
    constituents_cache,
    positions,
    scan_candidates,
    scans,
)

runner = CliRunner()


def test_invalid_constituent(tmp_path: Path) -> None:
    """buy exits code 1 when symbol is not in constituents_cache."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    # constituent lookup returns None
    mock_conn.execute.return_value.fetchone.return_value = None

    with (
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup"),
        patch("bensdorp1.commands.buy.log_event"),
    ):
        result = runner.invoke(app, ["buy", "ZZZ", "100.0", "5"])

    assert result.exit_code == 1
    assert "not a valid S&P 500 constituent" in result.output


def test_duplicate_open_position(db_engine: Engine, tmp_path: Path) -> None:
    """buy exits code 1 when an open position for the symbol already exists."""
    # Insert constituent row
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="NVDA",
                company_name="NVIDIA Corporation",
                fetched_at=datetime.now(UTC),
            )
        )
        # Insert an open position for NVDA
        conn.execute(
            insert(positions).values(
                symbol="NVDA",
                entry_date=datetime.now(UTC),
                entry_close=400.0,
                shares=10,
                initial_stop=372.0,
                highest_close=400.0,
                trailing_stop=300.0,
                scan_id=None,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.buy.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup"),
        patch("bensdorp1.commands.buy.log_event"),
    ):
        result = runner.invoke(app, ["buy", "NVDA", "432.50", "23"], input="")

    assert result.exit_code == 1
    assert "already exists" in result.output

    # Ensure no second position was inserted
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(positions).where(positions.c.symbol == "NVDA")
        ).fetchall()
    assert len(rows) == 1


def test_off_signal_warning(tmp_path: Path) -> None:
    """buy shows off-signal warning when symbol is not in top-10 candidates."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value

    # fetchone side_effect:
    # 1st call: constituent lookup → row found
    # 2nd call: no-open-position check → None (no open position)
    # 3rd call: on-signal scan lookup → scan row found
    # 4th call: scan_candidates lookup → None (not in top 10)
    constituent_mock = MagicMock()
    constituent_mock.symbol = "NVDA"
    scan_mock = MagicMock()
    scan_mock.id = 1
    scan_mock.scan_date = MagicMock()
    scan_mock.scan_date.date.return_value = datetime(2026, 5, 21).date()

    mock_conn.execute.return_value.fetchone.side_effect = [
        constituent_mock,  # 1. constituent check passes
        None,  # 2. no open position
        scan_mock,  # 3. most recent scan found
        None,  # 4. symbol NOT in scan_candidates top 10
    ]

    with (
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup"),
        patch("bensdorp1.commands.buy.log_event"),
    ):
        result = runner.invoke(app, ["buy", "NVDA", "432.50", "23"], input="y\ny\n")

    assert result.exit_code == 0
    assert "was not in the top 10 buy candidates" in result.output
    assert "Confirm buy?" in result.output


def test_happy_path_on_signal(db_engine: Engine, tmp_path: Path) -> None:
    """Happy path: on-signal buy creates position, audit event, and exits 0."""
    # Use a past scan date so it is <= today 00:00 UTC (buy_date_utc)
    past_scan_date = datetime(2026, 5, 21, 0, 0, 0, tzinfo=UTC)

    # Seed constituents_cache
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="NVDA",
                company_name="NVIDIA Corporation",
                fetched_at=datetime.now(UTC),
            )
        )
        # Insert a scan row with a past date so it is <= buy_date_utc
        conn.execute(
            insert(scans).values(
                scan_date=past_scan_date,
                regime_active=True,
                candidate_count=10,
                exit_trigger_count=0,
                raw_output=None,
                created_at=past_scan_date,
            )
        )
        conn.commit()

    # Get the scan id
    with db_engine.connect() as conn:
        scan_row = conn.execute(select(scans.c.id)).fetchone()
    assert scan_row is not None
    scan_id = scan_row.id

    # Insert scan_candidates row
    with db_engine.connect() as conn:
        conn.execute(
            insert(scan_candidates).values(
                scan_id=scan_id,
                symbol="NVDA",
                rank=1,
                roc200=0.5,
                close=430.0,
                suggested_shares=23,
            )
        )
        conn.commit()

    mock_backup = MagicMock()

    with (
        patch("bensdorp1.commands.buy.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup", mock_backup),
    ):
        result = runner.invoke(app, ["buy", "NVDA", "432.50", "23"], input="y\n")

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert "Buy recorded" in result.output

    # Verify the position was inserted correctly
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(positions).where(positions.c.symbol == "NVDA")
        ).fetchall()
    assert len(rows) == 1
    pos = rows[0]
    assert pos.entry_close == pytest.approx(432.50)
    assert pos.shares == 23
    assert pos.initial_stop == pytest.approx(432.50 * 0.93)
    assert pos.trailing_stop == pytest.approx(432.50 * 0.75)
    assert pos.highest_close == pytest.approx(432.50)
    assert pos.scan_id is not None
    assert pos.closed_at is None

    # Verify audit log
    with db_engine.connect() as conn:
        audit_rows = conn.execute(
            select(audit_log).where(
                (audit_log.c.event_type == "buy_confirmed")
                & (audit_log.c.symbol == "NVDA")
            )
        ).fetchall()
    assert len(audit_rows) >= 1

    # Verify backup was called
    mock_backup.assert_called_once()


def test_off_signal_abort(tmp_path: Path) -> None:
    """buy exits 0 without inserting when user answers n to Continue? prompt."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value

    constituent_mock = MagicMock()
    constituent_mock.symbol = "NVDA"
    scan_mock = MagicMock()
    scan_mock.id = 1
    scan_mock.scan_date = MagicMock()
    scan_mock.scan_date.date.return_value = datetime(2026, 5, 21).date()

    mock_conn.execute.return_value.fetchone.side_effect = [
        constituent_mock,  # 1. constituent check passes
        None,  # 2. no open position
        scan_mock,  # 3. most recent scan found
        None,  # 4. symbol NOT in scan_candidates top 10
    ]

    mock_create_backup = MagicMock()
    mock_log_event = MagicMock()

    with (
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup", mock_create_backup),
        patch("bensdorp1.commands.buy.log_event", mock_log_event),
    ):
        result = runner.invoke(app, ["buy", "NVDA", "432.50", "23"], input="n\n")

    assert result.exit_code == 0
    mock_create_backup.assert_not_called()
    mock_log_event.assert_not_called()


def test_invalid_date(tmp_path: Path) -> None:
    """buy exits code 1 when --date value cannot be parsed as YYYY-MM-DD."""
    mock_engine = MagicMock()

    with (
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup"),
        patch("bensdorp1.commands.buy.log_event"),
    ):
        result = runner.invoke(
            app, ["buy", "NVDA", "432.50", "23", "--date", "not-a-date"]
        )

    assert result.exit_code == 1
    assert "Invalid --date value" in result.output


def test_price_zero_rejected(tmp_path: Path) -> None:
    """buy exits code 1 when price is zero; no DB insert or backup occurs."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value

    mock_conn.execute.return_value.fetchone.side_effect = [
        MagicMock(symbol="NVDA"),  # C.1 constituent check passes
        None,  # C.2 no open position found
    ]

    with (
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup") as mock_create_backup,
        patch("bensdorp1.commands.buy.log_event"),
    ):
        result = runner.invoke(app, ["buy", "NVDA", "0.0", "23"])

    assert result.exit_code == 1
    assert "Price and shares must be greater than zero" in result.output
    assert mock_create_backup.called is False
