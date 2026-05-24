"""Tests for bensdorp1.config constants and env-var resolution."""

import importlib
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

import bensdorp1.config as config_module
from bensdorp1.config import DATA_DIR, MARKET_TZ, PROJECT_NAME, USER_TZ


def test_import_succeeds() -> None:
    """All four constants import without error."""
    assert PROJECT_NAME is not None
    assert MARKET_TZ is not None
    assert USER_TZ is not None
    assert DATA_DIR is not None


def test_project_name() -> None:
    """PROJECT_NAME equals 'bensdorp1'."""
    assert PROJECT_NAME == "bensdorp1"


def test_market_tz_key() -> None:
    """MARKET_TZ.key == 'America/New_York'."""
    assert MARKET_TZ.key == "America/New_York"


def test_user_tz_default() -> None:
    """Default USER_TZ.key == 'Europe/Lisbon' when BENSDORP1_USER_TZ is unset."""
    os.environ.pop("BENSDORP1_USER_TZ", None)
    importlib.reload(config_module)
    assert config_module.USER_TZ.key == "Europe/Lisbon"


def test_user_tz_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """When BENSDORP1_USER_TZ=America/Chicago, USER_TZ.key == 'America/Chicago'."""
    monkeypatch.setenv("BENSDORP1_USER_TZ", "America/Chicago")
    importlib.reload(config_module)
    assert config_module.USER_TZ.key == "America/Chicago"
    # Restore default
    monkeypatch.delenv("BENSDORP1_USER_TZ", raising=False)
    importlib.reload(config_module)


def test_invalid_zone_raises() -> None:
    """ZoneInfo('invalid/zone') raises ZoneInfoNotFoundError."""
    with pytest.raises(ZoneInfoNotFoundError):
        ZoneInfo("invalid/zone")


def test_data_dir_default() -> None:
    """DATA_DIR is Path and equals Path.home() / 'bensdorp1' when unset."""
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
