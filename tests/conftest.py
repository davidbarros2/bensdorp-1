"""Shared pytest fixtures for the bensdorp1 test suite.

The db_engine fixture provides a fresh file-based SQLite engine per test,
using tmp_path to avoid cross-test interference.  engine.dispose() is called
inside _reset_engine_for_testing() — this is CRITICAL on Windows to release
file handles before pytest attempts to clean up tmp_path (prevents [WinError 32]).

The record_console fixture provides a fresh Console(record=True, width=80) per
test for the UI test suite; callers use export_text() to assert output content.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from rich.console import Console
from sqlalchemy.engine import Engine

import bensdorp1.db.engine as engine_module
from bensdorp1.db.schema import metadata


@pytest.fixture
def record_console() -> Console:
    """Fresh Console(record=True, width=80) per test.

    UI suite uses this for export_text() assertions.
    """
    return Console(record=True, width=80)


@pytest.fixture
def db_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    """Fresh file-based SQLite engine per test.

    Resets the module-level engine cache so each test starts clean.
    Calls metadata.create_all so the schema is ready before yield.
    Disposes the engine in teardown so Windows can delete tmp_path files.
    """
    db_path = tmp_path / "test.db"
    engine = engine_module._build_engine(db_path)
    engine_module._reset_engine_for_testing(engine)
    metadata.create_all(engine, checkfirst=True)
    try:
        yield engine
    finally:
        # _reset_engine_for_testing() calls engine.dispose() internally;
        # no second dispose() call needed.
        engine_module._reset_engine_for_testing()
