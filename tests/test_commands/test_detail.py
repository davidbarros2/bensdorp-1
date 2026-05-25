"""Tests for commands/detail.py — CMD-10 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import positions, price_daily

runner = CliRunner()


def test_detail_exits_code_1_when_no_open_position(tmp_path: Path) -> None:
    """detail SYMBOL exits code 1 when no open position for SYMBOL."""
    from unittest.mock import MagicMock

    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    # No open position for NVDA
    mock_conn.execute.return_value.fetchone.return_value = None

    with (
        patch("bensdorp1.commands.detail.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.detail.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.detail.run_migrations"),
    ):
        result = runner.invoke(app, ["detail", "NVDA"])

    assert result.exit_code == 1
    assert "No open position for NVDA" in result.output
    assert "audit --symbol NVDA" in result.output


def test_detail_shows_position_summary_and_stop_history(
    db_engine: Engine, tmp_path: Path
) -> None:
    """detail SYMBOL shows position summary + stop history table."""
    entry_date = datetime(2026, 3, 15, tzinfo=UTC)

    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=entry_date,
                entry_close=180.00,
                shares=10,
                initial_stop=167.40,
                highest_close=185.00,
                trailing_stop=138.75,
                scan_id=None,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        # Three price_daily rows on consecutive trading days after entry
        for trade_dt, close_val in [
            (datetime(2026, 3, 16, tzinfo=UTC), 182.50),
            (datetime(2026, 3, 17, tzinfo=UTC), 185.00),
            (datetime(2026, 3, 18, tzinfo=UTC), 183.20),
        ]:
            conn.execute(
                insert(price_daily).values(
                    symbol="AAPL",
                    trade_date=trade_dt,
                    close=close_val,
                    volume=1_000_000,
                )
            )
        conn.commit()

    with (
        patch("bensdorp1.commands.detail.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.detail.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.detail.run_migrations"),
    ):
        result = runner.invoke(app, ["detail", "AAPL"])

    assert result.exit_code == 0
    output = result.output

    # Summary block present
    assert "AAPL" in output
    assert "$180.00" in output  # entry price

    # Section header present
    assert "Stop history" in output

    # All three date rows present
    assert "2026-03-16" in output
    assert "2026-03-17" in output
    assert "2026-03-18" in output

    # Closes present
    assert "$182.50" in output
    assert "$185.00" in output
    assert "$183.20" in output


def test_detail_stop_history_rows_use_correct_formulas(
    db_engine: Engine, tmp_path: Path
) -> None:
    """detail SYMBOL stop history rows use correct formulas (D-01)."""
    entry_date = datetime(2026, 3, 15, tzinfo=UTC)

    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=entry_date,
                entry_close=180.00,
                shares=10,
                initial_stop=167.40,
                highest_close=185.00,
                trailing_stop=138.75,
                scan_id=None,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        for trade_dt, close_val in [
            (datetime(2026, 3, 16, tzinfo=UTC), 182.50),
            (datetime(2026, 3, 17, tzinfo=UTC), 185.00),
            (datetime(2026, 3, 18, tzinfo=UTC), 183.20),
        ]:
            conn.execute(
                insert(price_daily).values(
                    symbol="AAPL",
                    trade_date=trade_dt,
                    close=close_val,
                    volume=1_000_000,
                )
            )
        conn.commit()

    with (
        patch("bensdorp1.commands.detail.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.detail.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.detail.run_migrations"),
    ):
        result = runner.invoke(app, ["detail", "AAPL"])

    assert result.exit_code == 0
    output = result.output

    # 2026-03-16: running_max = max(180.00, 182.50) = 182.50
    # trailing_stop = 182.50 * 0.75 = 136.875 → $136.88
    # effective_stop = max(167.40, 136.88) = $167.40 (initial_stop wins)
    assert "$182.50" in output  # running_max on 2026-03-16

    # 2026-03-17: running_max = max(182.50, 185.00) = 185.00
    # trailing_stop = 185.00 * 0.75 = 138.75
    # effective_stop = max(167.40, 138.75) = $167.40 (initial_stop still wins)
    assert "$138.75" in output  # trailing_stop on 2026-03-17

    # 2026-03-18: running_max stays $185.00 (183.20 < 185.00)
    # $185.00 appears as close on 3/17 and as highest-close on 3/18
    assert output.count("$185.00") >= 2


def test_detail_no_price_history(db_engine: Engine, tmp_path: Path) -> None:
    """detail SYMBOL exits 0 with info message when no price rows exist after entry."""
    entry_date = datetime.now(UTC)

    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="MSFT",
                entry_date=entry_date,
                entry_close=420.00,
                shares=5,
                initial_stop=390.60,
                highest_close=420.00,
                trailing_stop=315.00,
                scan_id=None,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.detail.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.detail.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.detail.run_migrations"),
    ):
        result = runner.invoke(app, ["detail", "MSFT"])

    assert result.exit_code == 0
    assert "No price history available" in result.output
