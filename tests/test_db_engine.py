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


def test_run_migrations_adds_closed_reason_columns(db_engine: Engine) -> None:
    """run_migrations adds closed_reason and closed_manual_reason columns idempotently.

    The db_engine fixture already called metadata.create_all once (schema without the new
    columns). run_migrations is called a second time here to exercise the ALTER TABLE path.
    A third call verifies idempotency — OperationalError must NOT propagate.
    """
    from sqlalchemy import text

    # Second call: ALTER TABLE path (columns not yet present because schema.py has no them)
    run_migrations(db_engine)

    with db_engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(positions)")).fetchall()

    col_names = [row[1] for row in rows]
    assert "closed_reason" in col_names, f"closed_reason missing; columns: {col_names}"
    assert "closed_manual_reason" in col_names, (
        f"closed_manual_reason missing; columns: {col_names}"
    )

    # Third call: must be idempotent — no exception raised
    run_migrations(db_engine)
