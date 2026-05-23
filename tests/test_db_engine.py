"""Tests for STATE-01: engine behavior — lazy caching, path resolution, migrations.

Uses the db_engine fixture from conftest.py for tests that need a live engine.
Direct function tests use tmp_path and monkeypatch without going through the fixture.
"""

from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

import bensdorp1.db.engine as engine_module
from bensdorp1.db.engine import run_migrations


def test_build_engine_returns_engine(tmp_path: Path) -> None:
    """_build_engine() returns an sqlalchemy Engine instance."""
    engine = engine_module._build_engine(tmp_path / "t.db")
    assert isinstance(engine, Engine)
    engine.dispose()


def test_resolve_db_path_uses_bensdorp1_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BENSDORP1_HOME env var changes the resolved DB path base directory."""
    engine_module._reset_engine_for_testing()
    monkeypatch.setenv("BENSDORP1_HOME", str(tmp_path))
    resolved = engine_module._resolve_db_path(None)
    assert resolved == tmp_path / "data" / "bensdorp1.db"


def test_resolve_db_path_override(tmp_path: Path) -> None:
    """An explicit override path is returned unchanged, ignoring env vars."""
    override = tmp_path / "custom.db"
    resolved = engine_module._resolve_db_path(override)
    assert resolved == override


def test_run_migrations_idempotent(db_engine: Engine) -> None:
    """run_migrations() can be called twice without raising (checkfirst=True)."""
    run_migrations(db_engine)
    run_migrations(db_engine)  # second call must not raise


def test_get_engine_returns_cached_singleton(tmp_path: Path) -> None:
    """get_engine() returns the same Engine object on repeated calls."""
    engine_module._reset_engine_for_testing()
    try:
        e1 = engine_module.get_engine(tmp_path / "a.db")
        e2 = engine_module.get_engine(tmp_path / "b.db")  # different path, ignored
        assert e1 is e2
    finally:
        engine_module._reset_engine_for_testing()


def test_get_engine_returns_engine_instance(tmp_path: Path) -> None:
    """get_engine() returns an Engine instance on first call."""
    engine_module._reset_engine_for_testing()
    try:
        e = engine_module.get_engine(tmp_path / "t.db")
        assert isinstance(e, Engine)
    finally:
        engine_module._reset_engine_for_testing()
