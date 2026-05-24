"""Tests for bensdorp1.config constants and env-var resolution."""

import importlib
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

import bensdorp1.config as config_module


def test_import_succeeds() -> None:
    """from bensdorp1.config import PROJECT_NAME, MARKET_TZ, USER_TZ, DATA_DIR resolves."""
    from bensdorp1.config import DATA_DIR, MARKET_TZ, PROJECT_NAME, USER_TZ  # noqa: F401


def test_project_name() -> None:
    """PROJECT_NAME equals 'bensdorp1'."""
    from bensdorp1.config import PROJECT_NAME

    assert PROJECT_NAME == "bensdorp1"


def test_market_tz_key() -> None:
    """MARKET_TZ.key == 'America/New_York'."""
    from bensdorp1.config import MARKET_TZ

    assert MARKET_TZ.key == "America/New_York"


def test_user_tz_default() -> None:
    """Default USER_TZ.key == 'Europe/Lisbon' when BENSDORP1_USER_TZ is unset."""
    # Ensure env var is not set before reload
    os.environ.pop("BENSDORP1_USER_TZ", None)
    importlib.reload(config_module)
    assert config_module.USER_TZ.key == "Europe/Lisbon"


def test_user_tz_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """When BENSDORP1_USER_TZ=America/Chicago, USER_TZ.key == 'America/Chicago' after reload."""
    monkeypatch.setenv("BENSDORP1_USER_TZ", "America/Chicago")
    importlib.reload(config_module)
    assert config_module.USER_TZ.key == "America/Chicago"
    # Restore default
    monkeypatch.delenv("BENSDORP1_USER_TZ", raising=False)
    importlib.reload(config_module)


def test_invalid_zone_raises() -> None:
    """ZoneInfo('invalid/zone') raises ZoneInfoNotFoundError — error path config.py would hit."""
    with pytest.raises(ZoneInfoNotFoundError):
        ZoneInfo("invalid/zone")


def test_data_dir_default() -> None:
    """DATA_DIR is a Path instance and equals Path.home() / 'bensdorp1' when BENSDORP1_HOME unset."""
    os.environ.pop("BENSDORP1_HOME", None)
    importlib.reload(config_module)
    assert isinstance(config_module.DATA_DIR, Path)
    assert config_module.DATA_DIR == Path.home() / "bensdorp1"


def test_data_dir_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When BENSDORP1_HOME=<tmp_path>, DATA_DIR == Path(tmp_path) after reload."""
    monkeypatch.setenv("BENSDORP1_HOME", str(tmp_path))
    importlib.reload(config_module)
    assert config_module.DATA_DIR == tmp_path
    # Restore default
    monkeypatch.delenv("BENSDORP1_HOME", raising=False)
    importlib.reload(config_module)
