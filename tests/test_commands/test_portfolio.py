"""Tests for commands/portfolio.py — CMD-09 scenarios."""

from datetime import UTC, datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest
from sqlalchemy import insert, select  # noqa: F401
from sqlalchemy.engine import Engine  # noqa: F401
from typer.testing import CliRunner

from bensdorp1.cli import app  # noqa: F401

runner = CliRunner()


def test_portfolio_lists_open_positions_table(tmp_path: Path) -> None:
    """portfolio lists open positions table."""
    pytest.skip("Wave 0 stub — filled in by plan 09-07")


def test_portfolio_empty_state_shows_no_open_positions(tmp_path: Path) -> None:
    """portfolio empty state shows "No open positions."."""
    pytest.skip("Wave 0 stub — filled in by plan 09-07")


def test_portfolio_shows_na_when_price_daily_missing(tmp_path: Path) -> None:
    """portfolio shows N/A when price_daily missing."""
    pytest.skip("Wave 0 stub — filled in by plan 09-07")
