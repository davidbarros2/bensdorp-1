"""Tests for commands/fix.py — CMD-08 scenarios."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import audit_log, positions

runner = CliRunner()


def test_no_transaction(tmp_path: Path) -> None:
    """No open AND no closed position for symbol → exit code 1, error message."""
    mock_engine = MagicMock()
    # Each call to engine.connect() returns a context manager that yields a
    # mock conn. Both open-position and closed-position fetchone return None.
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_conn)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_engine.connect.return_value = mock_cm

    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        result = runner.invoke(app, ["fix", "ZZZ"])

    assert result.exit_code == 1
    assert "No transaction found for" in result.output


def test_no_changes(tmp_path: Path) -> None:
    """User presses Enter at every field → No changes message; no DB write."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    # Open position fetchone returns a valid row; closed position lookup never called
    mock_open_row = MagicMock()
    mock_open_row.id = 1
    mock_open_row.entry_date = datetime(2026, 5, 1, tzinfo=UTC)
    mock_open_row.entry_close = 432.50
    mock_open_row.shares = 23
    mock_open_row.initial_stop = 402.225
    mock_conn.execute.return_value.fetchone.return_value = mock_open_row

    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup") as mock_create_backup,
        patch("bensdorp1.commands.fix.log_event") as mock_log_event,
    ):
        # y to identify; three empty Enter for Date, Price, Shares
        result = runner.invoke(app, ["fix", "NVDA"], input="y\n\n\n\n")

    assert result.exit_code == 0, f"Output:\n{result.output}"
    assert "No changes detected" in result.output
    assert mock_create_backup.called is False
    assert mock_log_event.called is False


def test_price_change_updates_stop(db_engine: Engine) -> None:
    """Price change on open position recalculates initial_stop; stops unchanged."""
    # Seed an open position
    with db_engine.connect() as conn:
        insert_result = conn.execute(
            insert(positions).values(
                symbol="NVDA",
                entry_date=datetime(2026, 5, 20, tzinfo=UTC),
                entry_close=432.50,
                shares=23,
                initial_stop=402.225,
                highest_close=440.00,
                trailing_stop=330.00,
                scan_id=None,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        conn.commit()
        position_id: int = int(insert_result.inserted_primary_key[0])  # type: ignore[index]

    with (
        patch("bensdorp1.commands.fix.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.fix.create_backup"),
    ):
        # y to identify, Enter to keep Date, "432.75" for Price, Enter to keep Shares,
        # y to confirm correction
        invoke_result = runner.invoke(app, ["fix", "NVDA"], input="y\n\n432.75\n\ny\n")

    assert invoke_result.exit_code == 0, f"Output:\n{invoke_result.output}"
    assert "Transaction corrected" in invoke_result.output

    # Verify positions row updated correctly
    with db_engine.connect() as conn:
        row = conn.execute(
            select(positions).where(positions.c.id == position_id)
        ).fetchone()

    assert row is not None
    assert row.entry_close == pytest.approx(432.75)
    assert row.initial_stop == pytest.approx(432.75 * 0.93)
    assert row.highest_close == pytest.approx(440.00)  # UNCHANGED (D-22)
    assert row.trailing_stop == pytest.approx(330.00)  # UNCHANGED (D-22)
    assert row.shares == 23

    # Verify audit log has transaction_corrected event with before/after payload
    with db_engine.connect() as conn:
        log_rows = conn.execute(
            select(audit_log).where(
                (audit_log.c.event_type == "transaction_corrected")
                & (audit_log.c.symbol == "NVDA")
            )
        ).fetchall()

    assert len(log_rows) >= 1
    payload = json.loads(log_rows[0].payload)
    assert payload["before"]["entry_close"] == pytest.approx(432.50)
    assert payload["after"]["entry_close"] == pytest.approx(432.75)
    assert payload["after"]["initial_stop"] == pytest.approx(432.75 * 0.93)
