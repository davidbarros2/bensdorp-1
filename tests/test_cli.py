import pytest
from typer.testing import CliRunner

from bensdorp1.cli import app

runner = CliRunner()


def test_root_help_exits_cleanly() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_root_help_shows_all_panels() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Daily operation" in result.output
    assert "Setup" in result.output
    assert "Confirmations" in result.output
    assert "Positions" in result.output
    assert "System" in result.output


def test_help_command_no_args_exits_cleanly() -> None:
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0


def test_help_unknown_command_exits_nonzero() -> None:
    result = runner.invoke(app, ["help", "nonexistent"])
    assert result.exit_code != 0


# init, scan, buy, sell, fix are intentionally absent — full implementations, not stubs
@pytest.mark.parametrize(
    "cmd",
    [
        "restore",
        "last",
        "history",
        "portfolio",
        "detail",
        "cash",
        "config",
        "audit",
        "status",
        "refresh",
        "validate",
    ],
)
def test_stub_exits_cleanly(cmd: str) -> None:
    result = runner.invoke(app, [cmd])
    assert result.exit_code == 0
    assert "Not yet implemented." in result.output


@pytest.mark.parametrize(
    "cmd",
    [
        "init",
        "restore",
        "scan",
        "last",
        "history",
        "buy",
        "sell",
        "fix",
        "portfolio",
        "detail",
        "cash",
        "config",
        "audit",
        "status",
        "refresh",
        "validate",
    ],
)
def test_help_subcommand_shows_help(cmd: str) -> None:
    result = runner.invoke(app, ["help", cmd])
    assert result.exit_code == 0
