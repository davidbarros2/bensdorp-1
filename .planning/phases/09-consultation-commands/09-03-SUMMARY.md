---
phase: 09-consultation-commands
plan: "03"
subsystem: commands
tags: [config, read-only, kv-block, CMD-12]
dependency_graph:
  requires: [09-01]
  provides: [CMD-12]
  affects: []
tech_stack:
  added: []
  patterns: [SP-1 DB entry triad, SP-3 raise typer.Exit(), SP-8 config_table alias, render_kv_block, importlib.metadata]
key_files:
  created: []
  modified:
    - src/bensdorp1/commands/config.py
    - tests/test_commands/test_config.py
decisions:
  - "Cash key is available_cash (not cash) — confirmed from init.py line 74"
  - "config table imported as config_table alias per SP-8 to avoid shadowing bensdorp1.config module"
  - "Version sourced at runtime via importlib.metadata.version to avoid hard-coding"
metrics:
  duration: "~4 minutes"
  completed: "2026-05-25T21:21:53Z"
  tasks_completed: 1
  files_modified: 2
---

# Phase 9 Plan 3: Config Command (CMD-12) Summary

**One-liner:** config command reads available_cash from SQLite config table and displays Cash, Data directory, Timezone, and Version via render_kv_block.

## What Was Built

Replaced the 11-line stub in `src/bensdorp1/commands/config.py` with a full CMD-12 implementation that:

1. Uses the SP-1 DB entry triad (db_path, get_engine, run_migrations, Console)
2. Queries the config table with `key == "available_cash"` (verified correct key from init.py line 74)
3. Formats cash via `format_price(float(cash_row.value))` or shows `"Not configured"` when absent
4. Builds the display dict in spec order: Cash, Data directory, Timezone, Version
5. Renders via `render_kv_block(data, console)` — markup-safe per T-09-03-T2
6. Sources version at runtime via `pkg_version("bensdorp1")` from importlib.metadata

Filled in the Wave 0 test stub in `tests/test_commands/test_config.py` using the real SQLite db_engine fixture, seeding one config row with `key="available_cash"`, `value="45000.00"`, and asserting all four labeled key-value pairs appear in output.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement config.py + fill in 1 test stub | b4916ec | src/bensdorp1/commands/config.py, tests/test_commands/test_config.py |

## Verification Results

- `uv run pytest tests/test_commands/test_config.py -x -q` → 1 passed
- `uv run mypy --strict src/bensdorp1/commands/config.py` → Success: no issues found
- `uv run ruff check src/bensdorp1/commands/config.py tests/test_commands/test_config.py` → All checks passed

## Deviations from Plan

None — plan executed exactly as written. The critical note about `"available_cash"` vs `"cash"` was honored: the implementation uses `config_table.c.key == "available_cash"` as specified.

## Known Stubs

None. The command is fully implemented for both configured (cash row present) and unconfigured (no cash row) states.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced. The config table read is parameterized (T-09-03-T3 mitigated). render_kv_block uses markup=False internally (T-09-03-T2 accepted).

## Self-Check: PASSED

- [x] `src/bensdorp1/commands/config.py` exists and is modified
- [x] `tests/test_commands/test_config.py` exists and is modified
- [x] Commit b4916ec exists in git log
- [x] No `pytest.skip` calls in test_config.py
- [x] No "Not yet implemented" string in config.py
- [x] `from bensdorp1.db.schema import config as config_table` present
- [x] `config_table.c.key == "available_cash"` present (not "cash")
- [x] `pkg_version("bensdorp1")` present
- [x] `render_kv_block(` present
- [x] `USER_TZ.key.split("/")[-1]` present
