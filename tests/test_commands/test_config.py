"""Tests for commands/config.py — CMD-12 scenarios."""

from datetime import UTC, datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest
from sqlalchemy import insert, select  # noqa: F401
from sqlalchemy.engine import Engine  # noqa: F401
from typer.testing import CliRunner

from bensdorp1.cli import app  # noqa: F401

runner = CliRunner()


def test_config_shows_cash_directory_timezone_version(tmp_path: Path) -> None:
    """config shows cash, directory, timezone, version."""
    pytest.skip("Wave 0 stub — filled in by plan 09-03")
