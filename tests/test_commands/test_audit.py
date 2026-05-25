"""Tests for commands/audit.py — CMD-13 scenarios."""

from datetime import UTC, datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest
from sqlalchemy import insert, select  # noqa: F401
from sqlalchemy.engine import Engine  # noqa: F401
from typer.testing import CliRunner

from bensdorp1.cli import app  # noqa: F401

runner = CliRunner()


def test_audit_no_filters_shows_50_most_recent_events(tmp_path: Path) -> None:
    """audit (no filters) shows 50 most recent events."""
    pytest.skip("Wave 0 stub — filled in by plan 09-05")


def test_audit_symbol_filter_shows_only_matching_events(tmp_path: Path) -> None:
    """audit --symbol NVDA filters to NVDA events only."""
    pytest.skip("Wave 0 stub — filled in by plan 09-05")


def test_audit_type_filter_shows_only_that_type(tmp_path: Path) -> None:
    """audit --type buy_confirmed shows only that type."""
    pytest.skip("Wave 0 stub — filled in by plan 09-05")


def test_audit_since_until_and_filters_correctly(tmp_path: Path) -> None:
    """audit --since DATE --until DATE AND-filters correctly."""
    pytest.skip("Wave 0 stub — filled in by plan 09-05")


def test_audit_limit_flag_returns_at_most_n_events(tmp_path: Path) -> None:
    """audit --limit 3 returns at most 3 events."""
    pytest.skip("Wave 0 stub — filled in by plan 09-05")


def test_audit_empty_state_when_no_events_match(tmp_path: Path) -> None:
    """audit empty state when no events match."""
    pytest.skip("Wave 0 stub — filled in by plan 09-05")
