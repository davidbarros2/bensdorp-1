"""Tests for commands/config.py — CMD-12 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import config as config_table

runner = CliRunner()


def test_config_shows_cash_directory_timezone_version(
    db_engine: Engine, tmp_path: Path
) -> None:
    """config shows cash, directory, timezone, version."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(config_table).values(
                key="available_cash",
                value="45000.00",
                updated_at=datetime.now(UTC),
            )
        )
        conn.commit()

    with (
        patch("bensdorp1.commands.config.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.config.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.config.run_migrations"),
    ):
        result = runner.invoke(app, ["config"])

    assert result.exit_code == 0
    assert "Cash:" in result.output
    assert "$45,000.00" in result.output
    assert "Data directory:" in result.output
    assert "Timezone:" in result.output
    assert "BENSDORP1_USER_TZ" in result.output
    assert "Version:" in result.output
