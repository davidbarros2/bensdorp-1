---
phase: 08-confirmation-commands
plan: "01"
subsystem: db/migrations + test-scaffolding
tags: [migrations, schema, test-skeleton, idempotency]
dependency_graph:
  requires: []
  provides:
    - "positions.closed_reason TEXT column (via run_migrations ALTER TABLE)"
    - "positions.closed_manual_reason TEXT column (via run_migrations ALTER TABLE)"
    - "tests/test_commands/test_buy.py — 5 named CMD-06 skeleton tests"
    - "tests/test_commands/test_sell.py — 3 named CMD-07 skeleton tests"
    - "tests/test_commands/test_fix.py — 3 named CMD-08 skeleton tests"
  affects:
    - "src/bensdorp1/db/engine.py (run_migrations extended)"
tech_stack:
  added: []
  patterns:
    - "ALTER TABLE ... ADD COLUMN wrapped in try/except OperationalError for idempotency"
    - "TDD RED/GREEN: failing test committed before implementation"
key_files:
  created:
    - tests/test_commands/test_buy.py
    - tests/test_commands/test_sell.py
    - tests/test_commands/test_fix.py
  modified:
    - src/bensdorp1/db/engine.py
    - tests/test_db_engine.py
decisions:
  - "ALTER TABLE migrations go in run_migrations() in engine.py, not schema.py (D-01)"
  - "Each ALTER TABLE wrapped in separate try/except to allow first column success if second fails mid-run"
  - "test file location: tests/test_db_engine.py (not tests/test_db/ subdirectory — matches existing project layout)"
metrics:
  duration: "~2m 12s"
  completed: "2026-05-25"
  tasks_completed: 2
  files_changed: 4
---

# Phase 8 Plan 01: Schema Migration + Test Scaffolding Summary

Schema migrations for `closed_reason` and `closed_manual_reason` columns added to `positions` table via idempotent ALTER TABLE in `run_migrations`; 11 named skeleton tests created for Plans 02-04.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 (RED) | Failing test for run_migrations ALTER TABLE | b905b1f | tests/test_db_engine.py |
| 1 (GREEN) | Idempotent ALTER TABLE migrations in engine.py | 47048ee | src/bensdorp1/db/engine.py |
| 2 | Create 11 named skeleton tests (buy/sell/fix) | 618cf8a | tests/test_commands/test_buy.py, test_sell.py, test_fix.py |

## Verification Results

- `uv run pytest tests/test_db_engine.py -x` — 7 passed (including new migration test)
- `uv run pytest tests/test_commands/test_buy.py -v` — 5 tests, all SKIPPED
- `uv run pytest tests/test_commands/test_sell.py -v` — 3 tests, all SKIPPED
- `uv run pytest tests/test_commands/test_fix.py -v` — 3 tests, all SKIPPED
- `uv run pytest -x` — 317 passed, 11 skipped (full suite green)
- `uv run mypy src/bensdorp1/db/engine.py --strict` — 0 issues
- `uv run ruff check src/bensdorp1/db/engine.py tests/test_commands/test_buy.py tests/test_commands/test_sell.py tests/test_commands/test_fix.py` — all checks passed

## Schema Migration Details

Both ALTER TABLE statements are confirmed in `src/bensdorp1/db/engine.py`:

```
ALTER TABLE positions ADD COLUMN closed_reason TEXT
ALTER TABLE positions ADD COLUMN closed_manual_reason TEXT
```

Idempotency pattern: `try/except OperationalError: pass` per statement. On Python 3.12 with SQLite, the OperationalError message is `table positions already has a column named closed_reason` — swallowed cleanly.

## Skeleton Test Files

`tests/test_commands/test_buy.py` (5 functions for CMD-06, all skip with "Implementation pending in Plan 02"):
- `test_invalid_constituent(tmp_path: Path)`
- `test_duplicate_open_position(db_engine: Engine)`
- `test_off_signal_warning(tmp_path: Path)`
- `test_happy_path_on_signal(tmp_path: Path)`
- `test_off_signal_abort(tmp_path: Path)`

`tests/test_commands/test_sell.py` (3 functions for CMD-07, all skip with "Implementation pending in Plan 03"):
- `test_no_exit_trigger(tmp_path: Path)`
- `test_happy_path_normal(tmp_path: Path)`
- `test_manual_sell(tmp_path: Path)`

`tests/test_commands/test_fix.py` (3 functions for CMD-08, all skip with "Implementation pending in Plan 04"):
- `test_no_transaction(tmp_path: Path)`
- `test_no_changes(tmp_path: Path)`
- `test_price_change_updates_stop(db_engine: Engine)`

## Notes for Plans 02-04

1. **SQLite OperationalError message text on Python 3.12**: `"table positions already has a column named <col>"` — this is the exact string swallowed in run_migrations idempotency.
2. **test file location**: Tests in `tests/test_commands/` alongside existing `test_init.py` and `test_scan.py` — NOT in a `tests/test_db/` subdirectory (that subdirectory does not exist in this project layout).
3. **db_engine fixture**: Calls `metadata.create_all` without `run_migrations`. Plan 02/03/04 tests that need the new columns must call `run_migrations(db_engine)` explicitly to trigger the ALTER TABLE path (the test for `test_duplicate_open_position` and `test_price_change_updates_stop` take the `db_engine` fixture — they should call `run_migrations` at the start of each test body).
4. **All imports with noqa: F401**: `MagicMock`, `patch`, `Engine`, `app` are imported but unused in stubs. Plans 02-04 implementers should remove the `# noqa: F401` comment from any import they actively use.

## Deviations from Plan

None — plan executed exactly as written.

The only deviation from the plan's literal `<verify>` path was the test file location: the plan's `<verify>` section referenced `tests/test_db/test_db_engine.py` but the project has no `tests/test_db/` subdirectory — the existing file is `tests/test_db_engine.py`. The new test was added to the correct existing file. This is a documentation discrepancy in the plan only; the implementation follows the actual project layout.

## Self-Check: PASSED

All required files exist:
- FOUND: src/bensdorp1/db/engine.py
- FOUND: tests/test_commands/test_buy.py
- FOUND: tests/test_commands/test_sell.py
- FOUND: tests/test_commands/test_fix.py

All commits exist:
- b905b1f: test(08-01): add failing test for run_migrations closed_reason columns
- 47048ee: feat(08-01): add idempotent ALTER TABLE migrations for closed_reason columns
- 618cf8a: feat(08-01): create test skeleton files for buy, sell, fix commands
