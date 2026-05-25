"""Tests for commands/history.py — CMD-05 scenarios."""

from datetime import UTC, datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest
from sqlalchemy import insert, select  # noqa: F401
from sqlalchemy.engine import Engine  # noqa: F401
from typer.testing import CliRunner

from bensdorp1.cli import app  # noqa: F401

runner = CliRunner()


def test_history_shows_compact_table_ordered_by_date_desc(tmp_path: Path) -> None:
    """history shows compact table ordered by date desc."""
    pytest.skip("Wave 0 stub — filled in by plan 09-04")


def test_history_limit_flag_returns_only_n_rows(tmp_path: Path) -> None:
    """history --limit 2 returns only 2 rows."""
    pytest.skip("Wave 0 stub — filled in by plan 09-04")


def test_history_since_flag_filters_correctly(tmp_path: Path) -> None:
    """history --since DATE filters correctly."""
    pytest.skip("Wave 0 stub — filled in by plan 09-04")


def test_history_empty_state_when_no_scans(tmp_path: Path) -> None:
    """history empty state when no scans."""
    pytest.skip("Wave 0 stub — filled in by plan 09-04")
