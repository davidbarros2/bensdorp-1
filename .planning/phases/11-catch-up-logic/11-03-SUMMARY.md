---
phase: 11-catch-up-logic
plan: "03"
subsystem: catch-up-logic
tags: [catch-up-summary, rendering, audit, composite, template-7, tests]
dependency_graph:
  requires:
    - catch_up_events dict (11-02 _update_position_stops accumulator)
    - events.py render_* functions (11-01 Task 2)
    - _OpenPosition with entry_close/shares/delisted (11-01 Task 3)
    - _apply_splits() / _detect_delisted_positions() (11-02)
  provides:
    - _render_output() catch-up summary block (D-04 placement, D-01/D-02/D-03 rules)
    - CATCH_UP_PERFORMED audit event in run_scan()
    - Template 7 (D-09) zero-rows-across-ALL-missed-days threshold
    - All 18 test_catchup.py tests green (14 plan + 4 coverage)
    - Overall suite >= 90% coverage
  affects:
    - src/bensdorp1/commands/_scan_engine.py
    - src/bensdorp1/data/__init__.py
    - src/bensdorp1/data/prices.py
    - tests/test_commands/test_catchup.py
    - tests/test_commands/test_scan_engine.py
    - tests/test_commands/test_restore.py
    - tests/test_db_schema.py
tech_stack:
  added: []
  patterns:
    - catch_up_events dict sentinel key "_regime" for system-level events
    - Separate system_notes list to keep bear-market note out of catch-up summary
    - Template 7 D-09 threshold: all(_get_close_for_day(...) is None for d in missed_list)
    - CATCH_UP_PERFORMED guarded by len(missed_list) >= 1 (Pitfall 5 threshold)
key_files:
  created: []
  modified:
    - src/bensdorp1/commands/_scan_engine.py
    - src/bensdorp1/data/__init__.py
    - src/bensdorp1/data/prices.py
    - tests/test_commands/test_catchup.py
    - tests/test_commands/test_scan_engine.py
    - tests/test_commands/test_restore.py
    - tests/test_db_schema.py
decisions:
  - Bear-market system note kept in separate system_notes list inside _render_output()
    so it never leaks into the catch-up summary block (D-04 separation)
  - catch_up_notes removed from _run_preflight() return tuple entirely (replaced by
    full catch-up block in _render_output)
  - CATCH_UP_PERFORMED logged once per absence only when len(missed_list) >= 1
    (one missed day = two elapsed trading days, satisfying spec "N >= 2" threshold)
  - Template 7 threshold check placed in run_scan() after _update_position_stops(),
    iterating open_positions and checking _get_close_for_day across all missed_list
  - Retroactive triggers table built from today_triggers where triggered_date.date() < today
metrics:
  duration: "~17 minutes"
  completed_date: "2026-05-30"
  tasks_completed: 3
  files_changed: 7
---

# Phase 11 Plan 03: Output Rendering, Audit Event, Verification Gate

One-liner: Catch-up summary block rendered before regular scan output (spec §7.6) with composite collapse, Template 7 zero-rows threshold, CATCH_UP_PERFORMED audit event, stale DATA-06 comments removed, all 18 catch-up tests green, suite at 90% coverage.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Catch-up summary rendering + composite + Template 7 | 6838304 | _scan_engine.py, test_catchup.py, test_scan_engine.py |
| 2 | CATCH_UP_PERFORMED audit + stale comment cleanup | 6b783ff | _scan_engine.py, data/__init__.py, data/prices.py, events.py, test_restore.py |
| 3 | Full verification gate + coverage tests | 94ba0af | test_catchup.py, test_db_schema.py |

## What Was Built

### Task 1 — Catch-up summary rendering

- `_render_output()` in `_scan_engine.py`: signature changed from `catch_up_notes: list[str]` to `catch_up_events: dict[str, list[str]]` + new keyword params `missed_days: list[date] | None`, `open_positions_count: int`, `split_notifications: list[str] | None`.
- Catch-up summary block (section 0) rendered BEFORE regular sections when `_missed` is non-empty (D-04):
  - SEPARATOR + "Catch-up summary" header
  - "You were absent for N trading days (START to END)."
  - "State has been updated for N open positions."
  - Per-position entries: silent if 0 events (D-01), direct string if 1 event, `render_composite()` if >= 2 events (D-02)
  - Regime events under sentinel key `"_regime"` shown after per-position entries
  - Retroactive pending-triggers table built from `today_triggers` where `triggered_date.date() < today`
  - "Confirm sells" closing line
- Bear-market note separated into `system_notes` list (not in catch-up summary)
- Composite collapse (D-02): `render_composite(symbol, events)` used for positions with >= 2 accumulated events
- Template 3 (D-03): single collapsed entry via Plan 02's `render_new_highest_close` with initial→final stops
- Template 7 (D-09): `if all(c is None for c in closes_on_missed)` check in `run_scan()` after `_update_position_stops`; `render_market_delist(pos.symbol, delist_date=None)` appended to `catch_up_events`
- `_run_preflight()` return tuple reduced from 5 to 4 elements (dropped `catch_up_notes`); all callers updated
- Updated `test_scan_engine.py`: all 8 `_render_output` call sites updated from `catch_up_notes=[]` to `catch_up_events={}`; `test_render_output_bear_regime` updated to check output text rather than mutated list; `test_render_output_catch_up_notes` updated to test catch-up summary block with `missed_days`
- 4 rendering stubs in `test_catchup.py` filled: `test_catchup_summary_rendering`, `test_composite_template`, `test_template3_initial_final_only`, `test_catch_up_audit_event`

### Task 2 — CATCH_UP_PERFORMED logging + stale comment cleanup

- `run_scan()` in `_scan_engine.py`: `log_event(engine, AuditEventType.CATCH_UP_PERFORMED, payload={...})` called when `len(missed_list) >= 1`, immediately before `SCAN_PERFORMED` audit event. Payload: `missed_days` (count), `start_date`, `end_date` (ISO format).
- `_update_position_stops()` signature: added `split_notifications: list[str] | None = None` keyword-only param. Internal local `split_notifications` variable renamed to `_split_notif`; caller-owned list used when provided.
- `run_scan()` passes the module-level `split_notifications: list[str] = []` into `_update_position_stops()` and to `_render_output()` separately.
- `test_split_in_catchup_template`: extended to also assert `render_output()` shows "Stock split" and "2:1" in the rendered catch-up summary.
- `data/__init__.py`: module docstring simplified — "DATA-06 ... OUT OF SCOPE for Phase 3" deferred text removed.
- `data/prices.py`: module docstring updated — "DATA-06: Split detection deferred to Phase 11" changed to "DATA-06: Split detection implemented in Phase 11 via _apply_splits()".

### Task 3 — Verification gate

- Added 4 targeted coverage tests to `test_catchup.py`:
  - `test_template7_delist_positive_case`: verifies `render_market_delist()` output and Template 7 behavior (uses events module directly)
  - `test_template7_partial_gap_no_delist`: verifies D-09 threshold logic — partial gap (some days have data) does NOT trigger Template 7
  - `test_regime_change_templates`: covers Templates 8-9 (`render_regime_bull_to_bear`, `render_regime_bear_to_bull`)
  - `test_system_event_templates`: covers Templates 10-12 (`render_constituents_updated`, `render_data_fetch_failed`, `render_trading_holidays`)
- `test_db_schema.py::test_positions_columns`: fixed to expect 15 columns (added `delisted` from Phase 11 Plan 01).
- `test_restore.py`: fixed pre-existing E501 comment line (out-of-scope but blocked ruff gate).
- Full verification gate results:
  - `pytest tests/test_commands/test_catchup.py -q`: 18 passed, 0 skipped (14 plan + 4 coverage)
  - `pytest --cov=src/bensdorp1 --cov-report=term-missing -q`: 393 passed, 90% overall coverage
  - `mypy src/bensdorp1`: Success: no issues found in 43 source files
  - `ruff check src/bensdorp1 tests`: All checks passed
  - `ruff format --check src/bensdorp1 tests`: 85 files already formatted
  - `bensdorp1 scan --help`: exits 0 with no traceback

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_positions_columns to include positions.delisted column**
- **Found during:** Task 3 full suite run
- **Issue:** `test_db_schema.py::test_positions_columns` expected 14 columns but schema now has 15 (Phase 11 Plan 01 added `positions.delisted`). This test failure pre-existed in the worktree base commit.
- **Fix:** Added `"delisted"` to the expected column set; updated docstring from 14 to 15 columns.
- **Files modified:** `tests/test_db_schema.py`
- **Commit:** 94ba0af

**2. [Rule 2 - Missing Critical Functionality] Added 4 coverage tests to reach 90% gate**
- **Found during:** Task 3 coverage measurement (initial run: 89%)
- **Issue:** events.py Templates 7, 8-9, 10-12 uncovered; overall coverage was 89% (1% below TEST-02 gate)
- **Fix:** Added targeted tests for `render_market_delist`, `render_regime_*`, `render_constituents_updated`, `render_data_fetch_failed`, `render_trading_holidays`. Also verified D-09 threshold logic (positive and negative cases).
- **Files modified:** `tests/test_commands/test_catchup.py`
- **Commit:** 94ba0af

**3. [Rule 1 - Bug] Pre-existing ruff E501 in test_restore.py (blocked verification gate)**
- **Found during:** Task 1 ruff check
- **Issue:** Comment line 150 in `test_restore.py` was 89 chars (> 88 limit). Pre-existing from a prior phase.
- **Fix:** Split comment onto two lines.
- **Files modified:** `tests/test_commands/test_restore.py`
- **Commit:** 6b783ff

**4. [Rule 1 - Bug] Pre-existing ruff E501/F841 in test_catchup.py from Plan 02 commits**
- **Found during:** Task 1 ruff check
- **Issue:** Plan 02 introduced long lines in DataFrame dict literals and unused `pos_id` assignments that exceeded the 88-char ruff limit.
- **Fix:** Reformatted dict literals with `"volume"` on continuation line; removed `pos_id = ` prefix where return value was unused.
- **Files modified:** `tests/test_commands/test_catchup.py`
- **Commit:** 6838304

## Known Stubs

None — all 18 tests in `test_catchup.py` are implemented.

## Threat Flags

None. All files modified are internal output rendering and audit logging. No new network endpoints, auth paths, or trust-boundary crossings introduced.

T-11-08: All `capture.print()` arguments wrapped in `Text()` — verified throughout `_render_output()`.
T-11-09: D-09 zero-rows threshold implemented; partial gaps route to normal events — verified via `test_template7_partial_gap_no_delist`.
T-11-10: CATCH_UP_PERFORMED audit event with missed_days/start/end payload — verified via `test_catch_up_audit_event`.

## Self-Check: PASSED

- `src/bensdorp1/commands/_scan_engine.py` contains "Catch-up summary" literal — verified
- `src/bensdorp1/commands/_scan_engine.py` contains `CATCH_UP_PERFORMED` log call guarded by `len(missed_list) >= 1` — verified
- `src/bensdorp1/data/__init__.py` no longer contains "DATA-06 ... OUT OF SCOPE" — verified
- `src/bensdorp1/data/prices.py` no longer contains "deferred to Phase 11" — verified
- `6838304` — verified in git log (Task 1 commit)
- `6b783ff` — verified in git log (Task 2 commit)
- `94ba0af` — verified in git log (Task 3 commit)
- `pytest tests/test_commands/test_catchup.py -q`: 18 passed, 0 skipped — verified
- `pytest --cov=src/bensdorp1 -q`: 393 passed, 90% — verified
- `mypy src/bensdorp1`: Success: no issues found in 43 source files — verified
- `ruff check src/bensdorp1 tests`: All checks passed — verified
- `ruff format --check src/bensdorp1 tests`: 85 files already formatted — verified
- `bensdorp1 scan --help`: exits 0 — verified
