"""Tests for commands/last.py — CMD-04 scenarios."""

from datetime import UTC, datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest
from sqlalchemy import insert, select  # noqa: F401
from sqlalchemy.engine import Engine  # noqa: F401
from typer.testing import CliRunner

from bensdorp1.cli import app  # noqa: F401

runner = CliRunner()


def test_last_shows_most_recent_scan_output(tmp_path: Path) -> None:
    """last shows raw_output of most recent scan."""
    pytest.skip("Wave 0 stub — filled in by plan 09-02")


def test_last_empty_state_no_scans(tmp_path: Path) -> None:
    """last prints info message when no scans exist."""
    pytest.skip("Wave 0 stub — filled in by plan 09-02")
