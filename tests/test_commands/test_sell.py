"""Tests for commands/sell.py — CMD-07 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db import run_migrations
from bensdorp1.db.schema import audit_log, positions, scan_exit_triggers, scans

runner = CliRunner()


def _data_dir(db_engine: Engine) -> Path:
    """Derive DATA_DIR from db_engine URL (test.db lives under <tmp>/data/test.db)."""
    db_path: str = db_engine.url.database or ""
    return Path(db_path).parent.parent


def test_no_exit_trigger(tmp_path: Path) -> None:
    """sell exits code 1 with error when no scan_exit_triggers row exists."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    # First fetchone: open position found; second fetchone: no trigger
    mock_conn.execute.return_value.fetchone.side_effect = [
        MagicMock(
            id=1,
            entry_close=182.50,
            shares=50,
            entry_date=datetime(2026, 4, 1, tzinfo=UTC),
        ),
        None,
    ]

    with (
        patch("bensdorp1.commands.sell.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.sell.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.sell.run_migrations"),
    ):
        result = runner.invoke(app, ["sell", "AAPL", "178.20"])

    assert result.exit_code == 1
    assert "No exit trigger on record" in result.output


def test_happy_path_normal(db_engine: Engine) -> None:
    """Happy path: open position + trigger → sell confirmed, position closed."""
    # Apply migrations so closed_reason / closed_manual_reason columns exist
    run_migrations(db_engine)

    with db_engine.connect() as conn:
        # Insert a scans row (FK requirement for scan_exit_triggers.scan_id)
        scan_result = conn.execute(
            insert(scans).values(
                scan_date=datetime(2026, 5, 20, tzinfo=UTC),
                regime_active=True,
                candidate_count=10,
                exit_trigger_count=1,
                created_at=datetime.now(UTC),
            )
        )
        scan_pk = scan_result.inserted_primary_key
        assert scan_pk is not None
        scan_id: int = scan_pk[0]

        # Insert open position
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
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        pos_pk = pos_result.inserted_primary_key
        assert pos_pk is not None
        position_id: int = pos_pk[0]

        # Insert exit trigger
        conn.execute(
            insert(scan_exit_triggers).values(
                scan_id=scan_id,
                position_id=position_id,
                reason="Trailing stop",
                effective_stop=170.0,
                triggered_date=datetime(2026, 5, 20, tzinfo=UTC),
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.sell.DATA_DIR", _data_dir(db_engine)),
        patch("bensdorp1.commands.sell.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.sell.run_migrations"),
        patch("bensdorp1.commands.sell.create_backup"),
    ):
        result = runner.invoke(app, ["sell", "AAPL", "178.20"], input="y\n")

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert "Sell recorded" in result.output

    # Verify position closed correctly — use text() to access ALTER TABLE columns
    with db_engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM positions WHERE id = :id"),
            {"id": position_id},
        ).fetchone()

    assert row is not None
    assert row.closed_at is not None
    assert row.exit_price == pytest.approx(178.20)
    assert row.realized_pnl == pytest.approx((178.20 - 182.50) * 50)
    assert row.closed_reason == "stop_trailing"
    assert row.closed_manual_reason is None

    # Verify audit log
    with db_engine.connect() as conn:
        audit_row = conn.execute(
            select(audit_log).where(
                (audit_log.c.event_type == "sell_confirmed")
                & (audit_log.c.symbol == "AAPL")
            )
        ).fetchone()

    assert audit_row is not None


def test_manual_sell(db_engine: Engine) -> None:
    """Manual sell bypasses trigger lookup; sets closed_reason='manual'."""
    # Apply migrations so closed_reason / closed_manual_reason columns exist
    run_migrations(db_engine)

    # Insert open position — no scan_exit_triggers row (verifies --manual bypass)
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
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        pos_pk = pos_result.inserted_primary_key
        assert pos_pk is not None
        position_id: int = pos_pk[0]
        conn.commit()

    with (
        patch("bensdorp1.commands.sell.DATA_DIR", _data_dir(db_engine)),
        patch("bensdorp1.commands.sell.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.sell.run_migrations"),
        patch("bensdorp1.commands.sell.create_backup"),
    ):
        result = runner.invoke(
            app,
            [
                "sell",
                "AAPL",
                "178.20",
                "--manual",
                "Stop tightened ahead of earnings",
            ],
            input="y\n",
        )

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"

    # Verify position closed with manual reason — use text() to access ALTER TABLE cols
    with db_engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM positions WHERE id = :id"),
            {"id": position_id},
        ).fetchone()

    assert row is not None
    assert row.closed_reason == "manual"
    assert row.closed_manual_reason == "Stop tightened ahead of earnings"

    # Verify audit event
    with db_engine.connect() as conn:
        audit_row = conn.execute(
            select(audit_log).where(
                (audit_log.c.event_type == "sell_manual")
                & (audit_log.c.symbol == "AAPL")
            )
        ).fetchone()

    assert audit_row is not None


def test_no_open_position(tmp_path: Path) -> None:
    """sell exits code 1 with error when no open position exists for the symbol."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = None

    with (
        patch("bensdorp1.commands.sell.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.sell.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.sell.run_migrations"),
    ):
        result = runner.invoke(app, ["sell", "AAPL", "178.20"])

    assert result.exit_code == 1
    assert "No open position for" in result.output


def _open_pos_conn(entry_date: datetime) -> MagicMock:
    """Return a mock conn whose first fetchone returns a valid open position row."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = MagicMock(
        id=1,
        entry_close=182.50,
        shares=50,
        entry_date=entry_date,
    )
    return mock_conn


def test_sell_price_zero_rejected(tmp_path: Path) -> None:
    """sell exits code 1 when price is zero after open position is found."""
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = _open_pos_conn(
        datetime(2026, 4, 1, tzinfo=UTC)
    )
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch("bensdorp1.commands.sell.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.sell.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.sell.run_migrations"),
    ):
        result = runner.invoke(app, ["sell", "AAPL", "0.0"])

    assert result.exit_code == 1
    assert "Sell price must be greater than zero" in result.output


def test_sell_unrecognised_trigger_reason(tmp_path: Path) -> None:
    """sell exits code 1 for an unrecognised exit trigger reason (WR-01 fix)."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    mock_conn.execute.return_value.fetchone.side_effect = [
        MagicMock(
            id=1,
            entry_close=182.50,
            shares=50,
            entry_date=datetime(2026, 4, 1, tzinfo=UTC),
        ),
        MagicMock(reason="unknown_weird_reason"),
    ]

    with (
        patch("bensdorp1.commands.sell.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.sell.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.sell.run_migrations"),
    ):
        result = runner.invoke(app, ["sell", "AAPL", "178.20"])

    assert result.exit_code == 1
    assert "Unrecognised exit trigger reason" in result.output


def test_sell_date_before_entry(tmp_path: Path) -> None:
    """sell exits code 1 when --date is earlier than the position entry date."""
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = _open_pos_conn(
        datetime(2026, 4, 1, tzinfo=UTC)
    )
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch("bensdorp1.commands.sell.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.sell.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.sell.run_migrations"),
    ):
        result = runner.invoke(app, ["sell", "AAPL", "178.20", "--date", "2026-03-01"])

    assert result.exit_code == 1
    assert "2026-03-01" in result.output

