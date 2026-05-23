---
phase: 02-database-and-migrations
plan: "05"
subsystem: db
tags: [db, package-init, re-exports, positions, partial-index, STATE-06]
dependency_graph:
  requires: [02-03, 02-04]
  provides: [db-public-surface, STATE-06-verified]
  affects: [all-future-phases-importing-from-bensdorp1.db]
tech_stack:
  added: []
  patterns: [re-export __all__, partial-unique-index, pytest-raises-IntegrityError]
key_files:
  created:
    - tests/test_db_positions.py
  modified:
    - src/bensdorp1/db/__init__.py
decisions:
  - "Used from-import style (not bare module import) in __init__.py — no noqa: F401 needed"
  - "Used datetime.UTC alias (UP017 compliant) in test_db_positions.py instead of timezone.utc"
  - "__all__ declared with multi-line list to respect 88-character line limit"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-23"
  tasks: 2
  files: 4
---

# Phase 02 Plan 05: db Package Public Interface Summary

Wired the `db/` package public surface by completing `db/__init__.py` with real re-exports from Waves 2-4, then confirmed STATE-06 partial index enforcement with three targeted integration tests.

## What Was Built

**Task 1: Complete db/__init__.py with real re-exports**

Replaced the Wave 1 placeholder in `src/bensdorp1/db/__init__.py` with the complete public interface of the db subpackage. Three import lines expose five names to all callers:

- `from bensdorp1.db.audit import AuditEventType, log_event`
- `from bensdorp1.db.backup import create_backup`
- `from bensdorp1.db.engine import get_engine, run_migrations`

The `__all__` list is declared with all five names (alphabetically ordered). The `from-import` style avoids `# noqa: F401` suppressions that would be needed with bare `import` statements.

**Task 2: Create test_db_positions.py confirming STATE-06 enforcement**

Created `tests/test_db_positions.py` with three integration tests that confirm the `ix_positions_open_symbol` partial unique index works end-to-end at the SQLite level:

1. `test_duplicate_open_position_rejected` — second `INSERT` with `closed_at=None` for the same symbol raises `sqlalchemy.exc.IntegrityError`
2. `test_sequential_positions_allowed` — close a position (set `closed_at`) then re-enter the same symbol succeeds without error
3. `test_different_symbols_can_both_be_open` — AAPL and GOOG can both have `closed_at=None` simultaneously

All three tests use the `db_engine` fixture from `conftest.py` and SQLAlchemy parameterized `insert().values()` / `update().values()` (no string-format SQL).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing ruff E501 in test_db_audit.py**
- **Found during:** Task 2 overall verification (plan requires `ruff check . exits 0`)
- **Issue:** `test_all_event_types_insertable` function signature was 91 characters, exceeding the 88-character limit
- **Fix:** Split the function signature onto two lines with the parameters on a continuation line
- **Files modified:** `tests/test_db_audit.py`
- **Commit:** afd2ac9

**2. [Rule 1 - Bug] Fixed pre-existing ruff F401 in test_db_backup.py**
- **Found during:** Task 2 overall verification (plan requires `ruff check . exits 0`)
- **Issue:** `import pytest` was declared but never used in `test_db_backup.py` (all 5 test functions use no pytest fixtures or marks directly)
- **Fix:** Removed the unused `import pytest` line
- **Files modified:** `tests/test_db_backup.py`
- **Commit:** afd2ac9

**3. [Rule 1 - Bug] Fixed ruff UP017 in test_db_positions.py**
- **Found during:** Task 2 ruff check of new file
- **Issue:** Used `timezone.utc` instead of `datetime.UTC` alias (UP017 rule)
- **Fix:** Changed import to `from datetime import UTC, datetime` and used `datetime.now(UTC)`; ruff `--fix` applied automatically
- **Files modified:** `tests/test_db_positions.py`
- **Commit:** afd2ac9

## Verification Results

| Check | Result |
|-------|--------|
| `from bensdorp1.db import get_engine, run_migrations, create_backup, log_event, AuditEventType` | PASS |
| `uv run pytest tests/test_db_positions.py -v` (3 tests) | PASS |
| `uv run pytest tests/ -x -q` (81 tests total) | PASS |
| `uv run ruff check .` | PASS |
| `uv run mypy src/` (26 source files) | PASS |
| `uv run ruff format --check .` (35 files formatted) | PASS |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 925704b | feat(02-05): complete db/__init__.py with real re-exports |
| Task 2 | afd2ac9 | test(02-05): add STATE-06 position tests confirming partial index enforcement |

## Self-Check: PASSED

- `src/bensdorp1/db/__init__.py` exists with 5 re-exports and correct `__all__`
- `tests/test_db_positions.py` exists with 3 test functions
- Commits 925704b and afd2ac9 exist in git log
- All 81 tests pass; ruff and mypy clean on full project
