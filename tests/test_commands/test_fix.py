"""Tests for commands/fix.py — CMD-08 scenarios."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db import run_migrations
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


def test_fix_sell_path(db_engine: Engine) -> None:
    """Price change on closed position recalculates realized_pnl; audit_log updated."""
    run_migrations(db_engine)

    with db_engine.connect() as conn:
        pos_result = conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=datetime(2026, 4, 1, tzinfo=UTC),
                entry_close=182.50,
                shares=50,
                initial_stop=169.725,
                highest_close=185.00,
                trailing_stop=138.75,
                scan_id=None,
                closed_at=datetime(2026, 5, 20, tzinfo=UTC),
                exit_price=178.20,
                realized_pnl=(178.20 - 182.50) * 50,
            )
        )
        pos_pk = pos_result.inserted_primary_key
        assert pos_pk is not None
        position_id: int = pos_pk[0]
        conn.execute(
            text(
                "UPDATE positions SET closed_reason='stop_trailing',"
                " closed_manual_reason=NULL WHERE id=:id"
            ),
            {"id": position_id},
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.fix.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.fix.create_backup"),
    ):
        # y = confirm fix target; Enter = keep Date; 180.00 = new price; y = confirm
        result = runner.invoke(app, ["fix", "AAPL"], input="y\n\n180.00\ny\n")

    assert result.exit_code == 0, f"Output:\n{result.output}"
    assert "Transaction corrected" in result.output

    with db_engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM positions WHERE id = :id"),
            {"id": position_id},
        ).fetchone()

    assert row is not None
    assert row.exit_price == pytest.approx(180.00)
    assert row.realized_pnl == pytest.approx((180.00 - 182.50) * 50)

    with db_engine.connect() as conn:
        log_rows = conn.execute(
            select(audit_log).where(
                (audit_log.c.event_type == "transaction_corrected")
                & (audit_log.c.symbol == "AAPL")
            )
        ).fetchall()

    assert len(log_rows) >= 1
    payload = json.loads(log_rows[0].payload)
    assert payload["after"]["exit_price"] == pytest.approx(180.00)
    assert payload["before"]["exit_price"] == pytest.approx(178.20)


def test_buy_path_price_zero_rejected(tmp_path: Path) -> None:
    """buy-path fix exits code 1 when user enters zero price; no DB write occurs."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

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
        # y = confirm target; Enter = keep Date; 0 = zero price → rejection
        result = runner.invoke(app, ["fix", "NVDA"], input="y\n\n0\n")

    assert result.exit_code == 1
    assert "Price must be greater than zero" in result.output
    assert mock_create_backup.called is False
    assert mock_log_event.called is False


def test_buy_path_shares_zero_rejected(tmp_path: Path) -> None:
    """buy-path fix exits code 1 when user enters zero shares."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

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
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        # y = confirm target; Enter = keep Date; valid price; 0 = zero shares
        result = runner.invoke(app, ["fix", "NVDA"], input="y\n\n432.75\n0\n")

    assert result.exit_code == 1
    assert "Shares must be greater than zero" in result.output


def test_sell_path_price_zero_rejected(tmp_path: Path) -> None:
    """sell-path fix exits code 1 when user enters zero price."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    mock_closed = MagicMock()
    mock_closed.id = 2
    mock_closed.entry_close = 182.50
    mock_closed.shares = 50
    mock_closed.closed_at = datetime(2026, 5, 20, tzinfo=UTC)
    mock_closed.exit_price = 178.20
    mock_closed.closed_reason = "stop_trailing"
    mock_closed.closed_manual_reason = None
    mock_closed.realized_pnl = (178.20 - 182.50) * 50

    mock_conn.execute.return_value.fetchone.side_effect = [
        None,         # open_row lookup → no open position
        mock_closed,  # closed_row lookup → closed position found
    ]

    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        # y = confirm target; Enter = keep Date; 0 = zero price → rejection
        result = runner.invoke(app, ["fix", "AAPL"], input="y\n\n0\n")

    assert result.exit_code == 1
    assert "Price must be greater than zero" in result.output


def _make_buy_mocks(tmp_path: Path) -> tuple[MagicMock, MagicMock]:
    """Return (mock_engine, mock_conn) with a standard open-position row."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_open_row = MagicMock()
    mock_open_row.id = 1
    mock_open_row.entry_date = datetime(2026, 5, 1, tzinfo=UTC)
    mock_open_row.entry_close = 432.50
    mock_open_row.shares = 23
    mock_open_row.initial_stop = 402.225
    mock_conn.execute.return_value.fetchone.return_value = mock_open_row
    return mock_engine, mock_conn


def _make_sell_mocks() -> tuple[MagicMock, MagicMock]:
    """Return (mock_engine, mock_conn) set up for a closed-position (sell-path) fix."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_closed = MagicMock()
    mock_closed.id = 2
    mock_closed.entry_close = 182.50
    mock_closed.shares = 50
    mock_closed.closed_at = datetime(2026, 5, 20, tzinfo=UTC)
    mock_closed.exit_price = 178.20
    mock_closed.closed_reason = "stop_trailing"
    mock_closed.closed_manual_reason = None
    mock_closed.realized_pnl = (178.20 - 182.50) * 50
    mock_conn.execute.return_value.fetchone.side_effect = [None, mock_closed]
    return mock_engine, mock_conn


def test_no_confirm_aborts(tmp_path: Path) -> None:
    """User says n to 'Is this the transaction to fix?' → exits 0 with no write."""
    mock_engine, _ = _make_buy_mocks(tmp_path)
    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup") as mock_backup,
        patch("bensdorp1.commands.fix.log_event") as mock_log,
    ):
        result = runner.invoke(app, ["fix", "NVDA"], input="n\n")
    assert result.exit_code == 0
    assert mock_backup.called is False
    assert mock_log.called is False


def test_buy_path_date_invalid(tmp_path: Path) -> None:
    """buy-path fix exits code 1 for an unparseable date string."""
    mock_engine, _ = _make_buy_mocks(tmp_path)
    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        result = runner.invoke(app, ["fix", "NVDA"], input="y\nbad-date\n")
    assert result.exit_code == 1
    assert "Expected YYYY-MM-DD" in result.output


def test_buy_path_price_nonnumeric(tmp_path: Path) -> None:
    """buy-path fix exits code 1 when price input is non-numeric."""
    mock_engine, _ = _make_buy_mocks(tmp_path)
    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        result = runner.invoke(app, ["fix", "NVDA"], input="y\n\nabc\n")
    assert result.exit_code == 1
    assert "Expected a numeric price" in result.output


def test_buy_path_shares_nonnumeric(tmp_path: Path) -> None:
    """buy-path fix exits code 1 when shares input is non-integer."""
    mock_engine, _ = _make_buy_mocks(tmp_path)
    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        result = runner.invoke(app, ["fix", "NVDA"], input="y\n\n432.75\nabc\n")
    assert result.exit_code == 1
    assert "Expected an integer" in result.output


def test_sell_path_date_invalid(tmp_path: Path) -> None:
    """sell-path fix exits code 1 for an unparseable date string."""
    mock_engine, _ = _make_sell_mocks()
    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        result = runner.invoke(app, ["fix", "AAPL"], input="y\nbad-date\n")
    assert result.exit_code == 1
    assert "Expected YYYY-MM-DD" in result.output


def test_sell_path_no_changes(tmp_path: Path) -> None:
    """sell-path fix exits 0 with 'No changes detected' when all fields kept."""
    mock_engine, _ = _make_sell_mocks()
    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup") as mock_backup,
        patch("bensdorp1.commands.fix.log_event") as mock_log,
    ):
        result = runner.invoke(app, ["fix", "AAPL"], input="y\n\n\n")
    assert result.exit_code == 0
    assert "No changes detected" in result.output
    assert mock_backup.called is False
    assert mock_log.called is False


def test_sell_path_manual_reason_display(tmp_path: Path) -> None:
    """Sell path with closed_reason='manual' shows Manual reason in kv_data."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_closed = MagicMock()
    mock_closed.id = 3
    mock_closed.entry_close = 182.50
    mock_closed.shares = 50
    mock_closed.closed_at = datetime(2026, 5, 20, tzinfo=UTC)
    mock_closed.exit_price = 178.20
    mock_closed.closed_reason = "manual"
    mock_closed.closed_manual_reason = "Stop tightened"
    mock_closed.realized_pnl = (178.20 - 182.50) * 50
    mock_conn.execute.return_value.fetchone.side_effect = [None, mock_closed]
    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        result = runner.invoke(app, ["fix", "AAPL"], input="n\n")
    assert result.exit_code == 0
    assert "Manual reason" in result.output


def test_buy_path_shares_only_change(tmp_path: Path) -> None:
    """Changing only shares covers the price-unchanged else branch and diff row."""
    mock_engine, _ = _make_buy_mocks(tmp_path)
    with (
        patch("bensdorp1.commands.fix.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.fix.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.fix.run_migrations"),
        patch("bensdorp1.commands.fix.create_backup"),
        patch("bensdorp1.commands.fix.log_event"),
    ):
        # y = confirm; \n = keep Date; \n = keep Price; 25 = new Shares; y = confirm
        result = runner.invoke(app, ["fix", "NVDA"], input="y\n\n\n25\ny\n")
    assert result.exit_code == 0
    assert "Transaction corrected" in result.output
