"""Tests for commands/cash.py — CMD-11 scenarios."""

from datetime import UTC, datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest
from sqlalchemy import insert, select  # noqa: F401
from sqlalchemy.engine import Engine  # noqa: F401
from typer.testing import CliRunner

from bensdorp1.cli import app  # noqa: F401

runner = CliRunner()


def test_cash_no_args_shows_current_cash_and_last_updated(tmp_path: Path) -> None:
    """cash (no args) shows current cash + last updated."""
    pytest.skip("Wave 0 stub — filled in by plan 09-06")


def test_cash_amount_updates_after_confirmation_and_writes_audit_event(
    tmp_path: Path,
) -> None:
    """cash AMOUNT updates after confirmation + writes audit event."""
    pytest.skip("Wave 0 stub — filled in by plan 09-06")


def test_cash_negative_amount_exits_code_1(tmp_path: Path) -> None:
    """cash -1.0 exits code 1 (non-negative validation)."""
    pytest.skip("Wave 0 stub — filled in by plan 09-06")


def test_cash_zero_amount_succeeds(tmp_path: Path) -> None:
    """cash 0.0 succeeds (zero is valid)."""
    pytest.skip("Wave 0 stub — filled in by plan 09-06")


def test_cash_amount_n_answer_aborts_without_state_change(tmp_path: Path) -> None:
    """cash AMOUNT n-answer aborts without state change."""
    pytest.skip("Wave 0 stub — filled in by plan 09-06")
