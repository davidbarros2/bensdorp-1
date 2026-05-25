"""Tests for commands/cash.py — CMD-11 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.audit import AuditEventType
from bensdorp1.db.schema import config as config_table

runner = CliRunner()


def test_cash_no_args_shows_no_cash_configured(tmp_path: Path) -> None:
    """cash (no args) with no config row shows 'No cash configured' and exits 0."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = None

    with (
        patch("bensdorp1.commands.cash.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.cash.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.cash.run_migrations"),
    ):
        result = runner.invoke(app, ["cash"])

    assert result.exit_code == 0
    assert "No cash configured" in result.output


def test_cash_no_args_shows_current_cash_and_last_updated(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    """cash (no args) with a config row shows cash amount and Last updated."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(config_table).values(
                key="available_cash",
                value="45000.00",
                updated_at=datetime(2026, 5, 25, 14, 30, tzinfo=UTC),
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.cash.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.cash.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.cash.run_migrations"),
    ):
        result = runner.invoke(app, ["cash"])

    assert result.exit_code == 0
    assert "$45,000.00" in result.output
    assert "Last updated" in result.output


def test_cash_amount_updates_after_confirmation_and_writes_audit_event(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    """cash AMOUNT y-confirm updates row, creates backup, and logs CASH_UPDATED."""
    # Seed current cash row
    with db_engine.connect() as conn:
        conn.execute(
            insert(config_table).values(
                key="available_cash",
                value="45000.00",
                updated_at=datetime(2026, 5, 25, 14, 30, tzinfo=UTC),
            )
        )
        conn.commit()

    mock_backup = MagicMock()
    mock_log = MagicMock()

    with (
        patch("bensdorp1.commands.cash.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.cash.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.cash.run_migrations"),
        patch("bensdorp1.commands.cash.create_backup", mock_backup),
        patch("bensdorp1.commands.cash.log_event", mock_log),
    ):
        result = runner.invoke(app, ["cash", "50000.0"], input="y\n")

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "Cash updated" in result.output

    # Verify backup was called once
    mock_backup.assert_called_once()

    # Verify log_event was called with CASH_UPDATED and correct payload
    mock_log.assert_called_once()
    _, log_kwargs = mock_log.call_args
    assert log_kwargs.get("payload") == {
        "old": 45000.0,
        "new": 50000.0,
        "note": None,
    }
    # Also verify via positional args
    log_pos_args = mock_log.call_args.args
    assert log_pos_args[1] == AuditEventType.CASH_UPDATED

    # Verify DB row was updated
    with db_engine.connect() as conn:
        row = conn.execute(
            select(config_table.c.value).where(config_table.c.key == "available_cash")
        ).fetchone()
    assert row is not None
    assert row.value == "50000.00"


def test_cash_amount_n_answer_aborts_without_state_change(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    """cash AMOUNT n-answer exits 0 without changing DB, backup, or audit log."""
    # Seed current cash row
    with db_engine.connect() as conn:
        conn.execute(
            insert(config_table).values(
                key="available_cash",
                value="45000.00",
                updated_at=datetime(2026, 5, 25, 14, 30, tzinfo=UTC),
            )
        )
        conn.commit()

    mock_backup = MagicMock()
    mock_log = MagicMock()

    with (
        patch("bensdorp1.commands.cash.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.cash.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.cash.run_migrations"),
        patch("bensdorp1.commands.cash.create_backup", mock_backup),
        patch("bensdorp1.commands.cash.log_event", mock_log),
    ):
        result = runner.invoke(app, ["cash", "50000.0"], input="n\n")

    assert result.exit_code == 0
    mock_backup.assert_not_called()
    mock_log.assert_not_called()

    # Verify DB row is unchanged
    with db_engine.connect() as conn:
        row = conn.execute(
            select(config_table.c.value).where(config_table.c.key == "available_cash")
        ).fetchone()
    assert row is not None
    assert row.value == "45000.00"


def test_cash_negative_amount_exits_code_1(tmp_path: Path) -> None:
    """cash -- -1.0 exits code 1 (non-negative validation); create_backup not called.

    Note: negative float literals starting with '-' are treated as option flags by
    Typer/Click, so the test uses '--' to signal end-of-options before the negative
    value. This correctly exercises the application-level validator (amount < 0.0).
    """
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = None

    mock_backup = MagicMock()

    with (
        patch("bensdorp1.commands.cash.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.cash.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.cash.run_migrations"),
        patch("bensdorp1.commands.cash.create_backup", mock_backup),
    ):
        result = runner.invoke(app, ["cash", "--", "-1.0"])

    assert result.exit_code == 1
    assert "non-negative" in result.output
    mock_backup.assert_not_called()
