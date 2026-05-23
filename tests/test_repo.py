from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_license_exists() -> None:
    assert (REPO_ROOT / "LICENSE").exists()


def test_pyproject_toml_exists() -> None:
    assert (REPO_ROOT / "pyproject.toml").exists()


def test_commands_init_exists() -> None:
    assert (REPO_ROOT / "src" / "bensdorp1" / "commands" / "__init__.py").exists()


def test_app_module_exists() -> None:
    assert (REPO_ROOT / "src" / "bensdorp1" / "_app.py").exists()


def test_all_command_modules_exist() -> None:
    for cmd in [
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
        "help",
    ]:
        assert (REPO_ROOT / "src" / "bensdorp1" / "commands" / f"{cmd}.py").exists(), (
            f"Missing: commands/{cmd}.py"
        )
