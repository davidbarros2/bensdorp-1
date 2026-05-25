---
phase: 09-consultation-commands
plan: "01"
subsystem: tests
tags: [test-scaffolding, wave-0, consultation-commands]
dependency_graph:
  requires: []
  provides:
    - tests/test_commands/test_last.py (CMD-04 stubs)
    - tests/test_commands/test_history.py (CMD-05 stubs)
    - tests/test_commands/test_portfolio.py (CMD-09 stubs)
    - tests/test_commands/test_detail.py (CMD-10 stubs)
    - tests/test_commands/test_cash.py (CMD-11 stubs)
    - tests/test_commands/test_config.py (CMD-12 stubs)
    - tests/test_commands/test_audit.py (CMD-13 stubs)
  affects: []
tech_stack:
  added: []
  patterns:
    - Wave 0 stub test files with pytest.skip for all planned scenarios
    - Canonical import block matching test_buy.py (noqa: F401 for unused imports)
    - Module-level runner = CliRunner() pattern
key_files:
  created:
    - tests/test_commands/test_last.py
    - tests/test_commands/test_history.py
    - tests/test_commands/test_portfolio.py
    - tests/test_commands/test_detail.py
    - tests/test_commands/test_cash.py
    - tests/test_commands/test_config.py
    - tests/test_commands/test_audit.py
  modified: []
decisions:
  - Used noqa: F401 on app and all unused imports (datetime, UTC, MagicMock, patch, insert, select, Engine) to keep canonical import block intact for downstream fill-in without lint churn
  - runner = CliRunner() kept at module scope even in stubs so downstream plans can add invoke calls without restructuring
metrics:
  duration: "2m 14s"
  completed: "2026-05-25T21:18:09Z"
  tasks_completed: 1
  files_created: 7
  files_modified: 0
---

# Phase 09 Plan 01: Wave 0 Test Stubs Summary

**One-liner:** 24 pytest.skip stubs across 7 test files for CMD-04/05/09-13, collectible and mypy/ruff clean.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create 7 Wave 0 test stub files | 976c15d | 7 new test files |

## What Was Built

Seven new test files covering all 7 consultation commands planned for Phase 9. Each file:

- Has a module docstring referencing its CMD-NN requirement
- Imports the canonical test_buy.py import block (with `# noqa: F401` on unused symbols)
- Defines `runner = CliRunner()` at module scope
- Contains one stub test per planned scenario from RESEARCH.md "Phase Requirements → Test Map"
- Each stub body is exactly `pytest.skip("Wave 0 stub — filled in by plan 09-NN")`

Scenario counts match RESEARCH.md exactly:
- test_last.py: 2 stubs (CMD-04)
- test_history.py: 4 stubs (CMD-05)
- test_portfolio.py: 3 stubs (CMD-09)
- test_detail.py: 3 stubs (CMD-10)
- test_cash.py: 5 stubs (CMD-11)
- test_config.py: 1 stub (CMD-12)
- test_audit.py: 6 stubs (CMD-13)

Total: 24 stubs.

## Verification Results

- `uv run pytest tests/test_commands/ --collect-only -q`: 99 tests collected, no errors
- `uv run pytest tests/test_commands/test_{last,history,portfolio,detail,cash,config,audit}.py -v`: 24 SKIPPED, exit 0
- `uv run ruff check tests/test_commands/`: All checks passed
- `uv run mypy --strict tests/test_commands/test_{last,...}.py`: Success, no issues in 7 source files

## Deviations from Plan

None — plan executed exactly as written.

The `app` import from `bensdorp1.cli` needed `# noqa: F401` since stub functions only call `pytest.skip()` and do not invoke `runner.invoke(app, ...)`. This is the expected approach specified in the plan's action section.

## Known Stubs

All 24 test functions are stubs by design. These are intentional Wave 0 placeholders — each downstream implementation plan (09-02 through 09-08) will replace the `pytest.skip(...)` calls with real assertions alongside the command implementations.

| File | Stub count | Filled in by |
|------|-----------|--------------|
| test_last.py | 2 | plan 09-02 |
| test_config.py | 1 | plan 09-03 |
| test_history.py | 4 | plan 09-04 |
| test_audit.py | 6 | plan 09-05 |
| test_cash.py | 5 | plan 09-06 |
| test_portfolio.py | 3 | plan 09-07 |
| test_detail.py | 3 | plan 09-08 |

## Threat Flags

None — test stub files introduce no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- [x] tests/test_commands/test_last.py exists
- [x] tests/test_commands/test_history.py exists
- [x] tests/test_commands/test_portfolio.py exists
- [x] tests/test_commands/test_detail.py exists
- [x] tests/test_commands/test_cash.py exists
- [x] tests/test_commands/test_config.py exists
- [x] tests/test_commands/test_audit.py exists
- [x] Commit 976c15d verified in git log
