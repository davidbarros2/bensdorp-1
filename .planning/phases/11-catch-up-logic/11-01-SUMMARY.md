---
phase: 11-catch-up-logic
plan: "01"
subsystem: catch-up-logic
tags: [schema, migration, events, templates, scan-engine, tests]
dependency_graph:
  requires: []
  provides:
    - positions.delisted column (schema + idempotent migration)
    - events.py — 13 catch-up event templates + split notification renderer
    - _OpenPosition extended with entry_close/shares/delisted
    - test_catchup.py scaffold with 14 failing stubs
  affects:
    - src/bensdorp1/db/schema.py
    - src/bensdorp1/db/engine.py
    - src/bensdorp1/commands/_scan_engine.py
    - tests/test_commands/test_scan.py
    - tests/test_commands/test_scan_engine.py
tech_stack:
  added: []
  patterns:
    - server_default=text("0") for SQLAlchemy Core NOT NULL column with default
    - run_migrations() ALTER TABLE idempotent pattern (try/except OperationalError)
    - Pure formatter module (events.py) — no I/O, no DB, no Rich markup in returns
    - NamedTuple field extension with two construction site updates
key_files:
  created:
    - src/bensdorp1/commands/events.py
    - tests/test_commands/test_catchup.py
  modified:
    - src/bensdorp1/db/schema.py
    - src/bensdorp1/db/engine.py
    - src/bensdorp1/commands/_scan_engine.py
    - tests/test_commands/test_scan.py
    - tests/test_commands/test_scan_engine.py
decisions:
  - server_default=text("0") used in schema.py (not default=0) so Core inserts omitting the column respect NOT NULL without ORM layer
  - Lazy imports of _apply_splits/_detect_delisted_positions inside test bodies so test_catchup.py is importable before Plan 02 lands
  - render_market_delist uses symbol-specific sell hint (not generic SYMBOL) to match CONTEXT.md §specifics verbatim
metrics:
  duration: "~15 minutes"
  completed_date: "2026-05-30"
  tasks_completed: 3
  files_changed: 7
---

# Phase 11 Plan 01: Foundation — Schema, Events, _OpenPosition, Test Scaffold

One-liner: Phase 11 foundation — positions.delisted column via ALTER TABLE migration, 13 verbatim §8.9 catch-up event templates in events.py, extended _OpenPosition NamedTuple with entry_close/shares/delisted, and 14 NotImplementedError stubs in test_catchup.py.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add positions.delisted column (schema + migration) | e092f20 | schema.py, engine.py |
| 2 | Create events.py — 13 catch-up templates + split notification | 71287b0 | events.py (new) |
| 3 | Extend _OpenPosition + _query_open_positions; scaffold test_catchup.py | d674932 | _scan_engine.py, test_catchup.py (new), test_scan.py, test_scan_engine.py |

## What Was Built

### Task 1 — positions.delisted column

- `src/bensdorp1/db/schema.py`: added `Column("delisted", Integer, nullable=False, server_default=text("0"))` as the final column of the `positions` Table; added `text` to the `from sqlalchemy import (...)` block.
- `src/bensdorp1/db/engine.py`: appended `"ALTER TABLE positions ADD COLUMN delisted INTEGER NOT NULL DEFAULT 0"` to the `run_migrations()` ALTER TABLE list; wrapped in the existing try/except OperationalError idempotency pattern.
- Fresh DBs via `metadata.create_all()` include the column; existing DBs get it via migration; double-run is idempotent.

### Task 2 — events.py

- `src/bensdorp1/commands/events.py`: 14 functions total.
  - 13 `render_*` functions implementing spec §8.9 templates 1-13 with verbatim wording.
  - 1 `render_split_notification()` for the spec §8.3 System-notes variant.
  - All dollar values go through `format_price()` from `bensdorp1.ui` — zero inline dollar-sign f-strings.
  - `render_removed_from_sp500` and `render_market_delist` accept `date | None`; when None, the " on {DATE}" clause is omitted (Open Question 2 resolution).
  - Unicode arrow `→` used in split templates per spec verbatim.
  - Pure formatter: no I/O, no DB, no Rich markup.

### Task 3 — _OpenPosition extension and test scaffold

- `src/bensdorp1/commands/_scan_engine.py`:
  - Added `entry_close: float`, `shares: int`, `delisted: int` to `_OpenPosition` NamedTuple (after `trailing_stop`).
  - Extended `_query_open_positions()` SELECT to include `positions.c.entry_close`, `positions.c.shares`, `positions.c.delisted`.
  - Updated in-memory snapshot replacement in `_update_position_stops` to carry the three new fields unchanged.
- `tests/test_commands/test_catchup.py`: 14 named test stubs raising `NotImplementedError`, organized by requirement (DATA-06: 8 stubs; STATE-05: 6 stubs; STATE-07: 4 stubs overlapping with DATA-06).
  - Lazy imports of `_apply_splits`/`_detect_delisted_positions` (Plans 02+03) inside test bodies.
  - Module-top imports of `events.py` functions (implemented in Task 2) are safe.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 5 pre-existing test _OpenPosition constructions**
- **Found during:** Task 3 verification (existing scan tests failed with TypeError)
- **Issue:** `test_scan.py` (3 sites) and `test_scan_engine.py` (2 sites) directly constructed `_OpenPosition` with the old 6-field signature — missing `entry_close`, `shares`, `delisted`.
- **Fix:** Added `entry_close=<appropriate_value>`, `shares=<appropriate_value>`, `delisted=0` to each construction site, using values consistent with the surrounding test insert statements.
- **Files modified:** `tests/test_commands/test_scan.py`, `tests/test_commands/test_scan_engine.py`
- **Commit:** d674932

## Known Stubs

- All 14 tests in `tests/test_commands/test_catchup.py` are stubs (raise NotImplementedError). This is intentional — Plans 02 and 03 implement `_apply_splits()`, `_detect_delisted_positions()`, and the full catch-up rendering, then fill in the stubs.

## Threat Flags

None. All files created/modified are internal (schema extension, pure formatters, test scaffold). No new network endpoints, auth paths, or trust-boundary crossings introduced.

## Self-Check: PASSED

- `src/bensdorp1/commands/events.py` — found, 14 render_* functions verified
- `tests/test_commands/test_catchup.py` — found, 14 tests collected by pytest
- `e092f20` — verified in git log (schema/migration commit)
- `71287b0` — verified in git log (events.py commit)
- `d674932` — verified in git log (scan_engine + test_catchup commit)
- `uv run mypy src/bensdorp1` — Success: no issues found in 43 source files
- `uv run pytest tests/test_commands/test_scan.py tests/test_commands/test_scan_engine.py -q` — 41 passed
- `uv run pytest tests/test_commands/test_catchup.py --collect-only -q` — 14 tests collected
