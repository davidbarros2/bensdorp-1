"""Tests for commands/detail.py — CMD-10 scenarios."""

from datetime import UTC, datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest
from sqlalchemy import insert, select  # noqa: F401
from sqlalchemy.engine import Engine  # noqa: F401
from typer.testing import CliRunner

from bensdorp1.cli import app  # noqa: F401

runner = CliRunner()


def test_detail_shows_position_summary_and_stop_history(tmp_path: Path) -> None:
    """detail SYMBOL shows position summary + stop history table."""
    pytest.skip("Wave 0 stub — filled in by plan 09-08")


def test_detail_exits_code_1_when_no_open_position(tmp_path: Path) -> None:
    """detail SYMBOL exits code 1 when no open position."""
    pytest.skip("Wave 0 stub — filled in by plan 09-08")


def test_detail_stop_history_rows_use_correct_formulas(tmp_path: Path) -> None:
    """detail SYMBOL stop history rows use correct formulas."""
    pytest.skip("Wave 0 stub — filled in by plan 09-08")
