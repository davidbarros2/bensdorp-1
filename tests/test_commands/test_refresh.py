"""Tests for commands/refresh.py — CMD-15 scenarios."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import constituents_cache

runner = CliRunner()


def test_refresh_no_changes(db_engine: Engine, tmp_path: Path) -> None:
    """refresh with no-op mock shows 'Constituents up to date.' and exits 0."""
    # Seed constituents_cache with 3 rows
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                [
                    {
                        "symbol": "AAA",
                        "company_name": "AlphaCo",
                        "fetched_at": datetime.now(UTC),
                    },
                    {
                        "symbol": "BBB",
                        "company_name": "BetaCo",
                        "fetched_at": datetime.now(UTC),
                    },
                    {
                        "symbol": "CCC",
                        "company_name": "GammaCo",
                        "fetched_at": datetime.now(UTC),
                    },
                ]
            )
        )
        conn.commit()

    mock_refresh = MagicMock()  # no side effect — cache stays the same

    with (
        patch("bensdorp1.commands.refresh.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.refresh.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.refresh.run_migrations"),
        patch("bensdorp1.commands.refresh.refresh_constituents", new=mock_refresh),
    ):
        result = runner.invoke(app, ["refresh"])

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "Constituents up to date." in result.output
    assert "no changes." in result.output
    assert "3 tickers" in result.output
    mock_refresh.assert_called_once()
    assert mock_refresh.call_args.args[0] is db_engine


def test_refresh_with_changes(db_engine: Engine, tmp_path: Path) -> None:
    """refresh with mock that mutates DB shows Added/Removed table and exits 0."""
    # Seed constituents_cache with AAA, BBB, CCC
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                [
                    {
                        "symbol": "AAA",
                        "company_name": "AlphaCo",
                        "fetched_at": datetime.now(UTC),
                    },
                    {
                        "symbol": "BBB",
                        "company_name": "BetaCo",
                        "fetched_at": datetime.now(UTC),
                    },
                    {
                        "symbol": "CCC",
                        "company_name": "GammaCo",
                        "fetched_at": datetime.now(UTC),
                    },
                ]
            )
        )
        conn.commit()

    def _mutate(engine_arg: Engine) -> None:
        with engine_arg.connect() as conn:
            conn.execute(
                constituents_cache.delete().where(constituents_cache.c.symbol == "BBB")
            )
            conn.execute(
                insert(constituents_cache).values(
                    symbol="DDD",
                    company_name="DeltaCo",
                    fetched_at=datetime.now(UTC),
                )
            )
            conn.commit()

    mock_refresh = MagicMock(side_effect=_mutate)

    with (
        patch("bensdorp1.commands.refresh.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.refresh.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.refresh.run_migrations"),
        patch("bensdorp1.commands.refresh.refresh_constituents", new=mock_refresh),
    ):
        result = runner.invoke(app, ["refresh"])

    assert result.exit_code == 0, f"Unexpected exit.\nOutput:\n{result.output}"
    assert "Added: 1 tickers" in result.output
    assert "Removed: 1 ticker(s)" in result.output
    assert "DDD" in result.output
    assert "BBB" in result.output
    assert "Added" in result.output
    assert "Removed" in result.output
