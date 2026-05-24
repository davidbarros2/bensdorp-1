"""Tests for commands/init.py — D-08 scenarios for the init command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app

runner = CliRunner()


def test_guard_fires_when_db_exists(tmp_path: Path) -> None:
    """Guard fires with exit code 1 when DB file already exists."""
    db_dir = tmp_path / "data"
    db_dir.mkdir(parents=True)
    (db_dir / "bensdorp1.db").touch()

    with patch("bensdorp1.commands.init.DATA_DIR", tmp_path):
        result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "Delete the file" in result.output
    assert "bensdorp1 restore" in result.output


def test_happy_path(tmp_path: Path) -> None:
    """Happy path: all data-layer calls mocked, exits 0 with setup complete summary."""
    mock_engine = MagicMock()

    with (
        patch("bensdorp1.commands.init.DATA_DIR", tmp_path),
        patch(
            "bensdorp1.commands.init.get_constituents",
            return_value={"AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation"},
        ),
        patch("bensdorp1.commands.init.update_price_data"),
        patch("bensdorp1.commands.init.run_migrations"),
        patch(
            "bensdorp1.commands.init.get_engine", return_value=mock_engine
        ) as mock_get_engine,
        patch("bensdorp1.commands.init.create_backup") as mock_create_backup,
        patch("bensdorp1.commands.init.log_event") as mock_log_event,
    ):
        result = runner.invoke(app, ["init"], input="y\n50000\ny\n")

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert "Setup complete" in result.output
    assert "50,000.00" in result.output
    assert mock_log_event.called
    assert mock_create_backup.called
    mock_get_engine.assert_called_once()


def test_cash_validation_reprompts(tmp_path: Path) -> None:
    """Cash validation re-prompts on 0 and negative; accepts first positive amount."""
    mock_engine = MagicMock()

    with (
        patch("bensdorp1.commands.init.DATA_DIR", tmp_path),
        patch(
            "bensdorp1.commands.init.get_constituents",
            return_value={"AAPL": "Apple Inc."},
        ),
        patch("bensdorp1.commands.init.update_price_data"),
        patch("bensdorp1.commands.init.run_migrations"),
        patch("bensdorp1.commands.init.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.init.create_backup"),
        patch("bensdorp1.commands.init.log_event"),
    ):
        # Continue=y; 0 and -100 rejected; 50000 accepted; Confirm=y
        result = runner.invoke(app, ["init"], input="y\n0\n-100\n50000\ny\n")

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert result.output.count("Error: Cash must be greater than zero.") == 2


def test_store_cash_writes_to_config(db_engine: Engine) -> None:
    """_store_cash upserts the correct value into the config table."""
    from sqlalchemy import select

    from bensdorp1.commands.init import _store_cash
    from bensdorp1.db.schema import config as config_table

    _store_cash(db_engine, 75_000.0)

    with db_engine.connect() as conn:
        row = conn.execute(
            select(config_table).where(config_table.c.key == "available_cash")
        ).one()
    assert row.value == "75000.00"


def test_ctrl_c_during_cash_entry(tmp_path: Path) -> None:
    """Ctrl+C during cash entry prints abort message and exits cleanly (code 0)."""
    with (
        patch("bensdorp1.commands.init.DATA_DIR", tmp_path),
        patch(
            "bensdorp1.commands.init.number_prompt",
            side_effect=KeyboardInterrupt,
        ),
    ):
        # "y" for the Continue? prompt; then number_prompt raises KeyboardInterrupt
        result = runner.invoke(app, ["init"], input="y\n")

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert "Operation aborted. No changes were made." in result.output
    assert not (tmp_path / "data" / "bensdorp1.db").exists()
