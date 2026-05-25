"""Tests for commands/portfolio.py — CMD-09 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import positions, price_daily

runner = CliRunner()


def test_portfolio_empty_state_shows_no_open_positions(tmp_path: Path) -> None:
    """portfolio empty state shows "No open positions."."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchall.return_value = []

    with (
        patch("bensdorp1.commands.portfolio.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.portfolio.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.portfolio.run_migrations"),
    ):
        result = runner.invoke(app, ["portfolio"])

    assert result.exit_code == 0
    assert "No open positions." in result.output


def test_portfolio_lists_open_positions_table(
    db_engine: Engine, tmp_path: Path
) -> None:
    """portfolio lists open positions table with price-derived columns."""
    # Seed one open position
    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=datetime(2026, 3, 15, tzinfo=UTC),
                entry_close=182.50,
                shares=50,
                initial_stop=169.73,
                highest_close=185.00,
                trailing_stop=138.75,
                scan_id=None,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        # Seed a price_daily row
        conn.execute(
            insert(price_daily).values(
                symbol="AAPL",
                trade_date=datetime(2026, 5, 20, tzinfo=UTC),
                close=178.20,
                volume=1000000,
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.portfolio.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.portfolio.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.portfolio.run_migrations"),
    ):
        result = runner.invoke(app, ["portfolio"])

    assert result.exit_code == 0
    # Symbol present
    assert "AAPL" in result.output
    # Shares column (short value — never truncated)
    assert "50" in result.output
    # Dist % positive: last_close (178.20) > effective_stop = max(169.73, 138.75)
    # format_pct produces "+4.8%" — short enough not to be truncated
    assert "+4.8%" in result.output
    # Unrealized P&L = (178.20 - 182.50) * 50 = -215.00
    # format_pnl produces "-$215.00"; "-$215" prefix is present even if truncated
    assert "-$215" in result.output
    # Stop $ column contains $169.73 (effective_stop = max(169.73, 138.75))
    assert "$169.73" in result.output


def test_portfolio_shows_na_when_price_daily_missing(
    db_engine: Engine, tmp_path: Path
) -> None:
    """portfolio shows N/A when price_daily missing."""
    # Seed one open position for NVDA but no price_daily row
    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="NVDA",
                entry_date=datetime(2026, 4, 1, tzinfo=UTC),
                entry_close=850.00,
                shares=12,
                initial_stop=790.50,
                highest_close=870.00,
                trailing_stop=652.50,
                scan_id=None,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.portfolio.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.portfolio.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.portfolio.run_migrations"),
    ):
        result = runner.invoke(app, ["portfolio"])

    assert result.exit_code == 0
    assert "NVDA" in result.output
    # Five N/A columns: Last $, High $, Stop $, Dist %, P&L
    assert result.output.count("N/A") >= 5
