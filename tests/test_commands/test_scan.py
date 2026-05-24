"""Tests for commands/scan.py — Wave 0 stubs for all scan test scenarios.

All test functions are stubs that will be implemented in Plans 07-02 and 07-03.
Each stub uses pytest.skip() so the test is collected and skipped (not failed),
giving Wave 2 and Wave 3 executors target test IDs to implement against.
"""

from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app  # noqa: F401  # used by Wave 2/3 integration tests

runner = CliRunner()


def test_schema_has_exit_triggers_table() -> None:
    """scan_exit_triggers table exists with correct columns and FK constraints."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_time_gate(tmp_path: Path) -> None:
    """scan refuses with exit code 1 when invoked before 16:30 ET."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_happy_path_bull(tmp_path: Path) -> None:
    """Happy path: bull regime, exit triggers + buy candidates rendered correctly."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_bearish_regime(tmp_path: Path) -> None:
    """Bearish regime: buy candidates section suppressed; exit triggers still shown."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_idempotent_same_day(tmp_path: Path) -> None:
    """Same-day re-run without --force shows cached raw_output."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_force_reruns_scan(tmp_path: Path) -> None:
    """--force flag causes scan to re-fetch data and overwrite same-day result."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_non_trading_day(tmp_path: Path) -> None:
    """Non-trading day: Info message printed and last raw_output shown."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_catchup_stop_updates(db_engine: Engine) -> None:
    """Catch-up logic: trailing stop updated for each missed trading day in sequence."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_stop_freeze_after_trigger(db_engine: Engine) -> None:
    """Triggered position: effective_stop is frozen; position not double-triggered."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")


def test_exit_trigger_on_missed_day(db_engine: Engine) -> None:
    """Catch-up: exit trigger recorded with triggered_date of the missed trading day."""
    pytest.skip("Wave 0 stub — implemented in Plan 07-03")
