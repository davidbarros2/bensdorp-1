---
phase: 02-database-and-migrations
plan: "02"
subsystem: db
tags: [sqlalchemy, engine, sqlite, pytest, fixtures, migrations]
dependency_graph:
  requires: [02-01]
  provides: [engine.py, conftest.py, test_db_schema.py, test_db_engine.py]
  affects: [02-03, 02-04, 02-05]
tech_stack:
  added: []
  patterns:
    - "Lazy-cached engine singleton with double-checked locking (threading.Lock)"
    - "URL.create('sqlite+pysqlite', database=str(path)) for Windows-safe SQLite URLs"
    - "pytest db_engine fixture with engine.dispose() in finally (WinError 32 prevention)"
    - "run_migrations() with metadata.create_all(checkfirst=True) for idempotent DDL"
key_files:
  created:
    - src/bensdorp1/db/engine.py
    - tests/conftest.py
    - tests/test_db_schema.py
    - tests/test_db_engine.py
  modified: []
decisions:
  - "Used X | None union syntax (UP045) instead of Optional[X] — ruff enforces this for Python 3.11 target"
  - "Generator imported from collections.abc not typing (UP035) — ruff enforces modern stdlib location"
  - "Removed @pytest.fixture() parentheses — ruff PT001 prefers @pytest.fixture (no-arg form)"
  - "run_migrations() imports metadata inside function body to avoid circular import risk at module load"
metrics:
  duration: "4m 30s"
  completed: "2026-05-23"
  tasks: 2
  files: 4
requirements: [STATE-01]
---

# Phase 02 Plan 02: Engine and Test Infrastructure Summary

One-liner: Lazy-cached SQLAlchemy Engine singleton with BENSDORP1_HOME resolution and file-based pytest db_engine fixture with Windows-safe teardown.

## What Was Built

### Task 1: engine.py — lazy-cached engine singleton

`src/bensdorp1/db/engine.py` implements the engine lifecycle for the `db/` subpackage:

- `_resolve_db_path(override)` — priority chain: explicit override > BENSDORP1_HOME env var > `~/bensdorp1/data/bensdorp1.db`
- `_build_engine(path)` — constructs engine via `URL.create("sqlite+pysqlite", database=str(path))`; never uses f-string URL (backslash safety on Windows)
- `get_engine(path=None)` — double-checked locking with `threading.Lock`; cached after first call
- `run_migrations(engine)` — calls `metadata.create_all(engine, checkfirst=True)`; local import of `metadata` inside function body to prevent circular import
- `_reset_engine_for_testing(replacement=None)` — disposes current engine before replacing; enables test isolation

### Task 2: conftest.py + STATE-01 test files

`tests/conftest.py` — `db_engine` fixture using `tmp_path`, with `engine.dispose()` in `finally` block (CRITICAL on Windows to prevent `[WinError 32]` during `tmp_path` cleanup).

`tests/test_db_schema.py` — 6 tests covering STATE-01:
- `test_all_tables_created` — exactly 7 tables via `sqlalchemy.inspect`
- `test_create_all_idempotent` — second `create_all()` call does not raise
- `test_partial_index_exists` — `ix_positions_open_symbol` present on `positions`
- `test_price_daily_unique_index_exists` — `ix_price_daily_symbol_date` present
- `test_audit_log_indexes_exist` — all 3 audit_log indexes present
- `test_positions_columns` — exactly 12 columns match expected set

`tests/test_db_engine.py` — 4 tests covering STATE-01 engine behavior:
- `test_build_engine_returns_engine` — `_build_engine()` returns `Engine` instance
- `test_resolve_db_path_uses_bensdorp1_home` — `monkeypatch.setenv` correctly changes resolution
- `test_resolve_db_path_override` — explicit override returned unchanged
- `test_run_migrations_idempotent` — `run_migrations()` called twice does not raise

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff UP045: Optional[X] replaced with X | None**
- **Found during:** Task 1 verification
- **Issue:** Ruff's UP045 rule enforces `X | None` union syntax over `Optional[X]` for Python 3.11 targets; plan specified `Optional` but ruff config selects `UP` rules
- **Fix:** Replaced all four `Optional[...]` annotations in engine.py with `X | None`; removed the now-unused `from typing import Optional` import
- **Files modified:** `src/bensdorp1/db/engine.py`
- **Commit:** d5529c0

**2. [Rule 1 - Bug] Ruff UP035: Generator import from typing replaced with collections.abc**
- **Found during:** Task 2 verification
- **Issue:** `from typing import Generator` triggers UP035; modern stdlib location is `collections.abc`
- **Fix:** Changed import to `from collections.abc import Generator` in conftest.py
- **Files modified:** `tests/conftest.py`
- **Commit:** 6364937

**3. [Rule 1 - Bug] Ruff PT001: @pytest.fixture() parentheses removed**
- **Found during:** Task 2 verification
- **Issue:** Ruff PT001 prefers `@pytest.fixture` over `@pytest.fixture()` (no-arg decorator form)
- **Fix:** Removed parentheses from fixture decorator
- **Files modified:** `tests/conftest.py`
- **Commit:** 6364937

**4. [Rule 1 - Bug] Ruff E501: Line too long in test files**
- **Found during:** Task 2 verification
- **Issue:** Three lines exceeded 88-char limit in docstring, comment, and set literal
- **Fix:** Shortened docstring, comment, and split set literal across multiple lines
- **Files modified:** `tests/test_db_engine.py`, `tests/conftest.py`, `tests/test_db_schema.py`
- **Commit:** 6364937

## Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_db_schema.py tests/test_db_engine.py -v` | 10/10 passed |
| `uv run pytest tests/ -x -q` | 51/51 passed (41 Phase 1 + 10 new) |
| `uv run ruff check src/bensdorp1/db/ tests/` | 0 errors |
| `uv run mypy src/bensdorp1/db/` | 0 errors (strict mode) |

## Known Stubs

None — engine.py is fully implemented and tested. No placeholder return values or TODO markers.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. The BENSDORP1_HOME path resolution was reviewed against T-2-04 (path traversal): single-user local CLI with no privilege boundary; `Path()` construction is safe.

## Self-Check

- [x] `src/bensdorp1/db/engine.py` exists
- [x] `tests/conftest.py` exists
- [x] `tests/test_db_schema.py` exists
- [x] `tests/test_db_engine.py` exists
- [x] Commit d5529c0 exists (engine.py)
- [x] Commit 6364937 exists (test files)

## Self-Check: PASSED
