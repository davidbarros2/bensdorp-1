---
phase: 07-scan-command
plan: "01"
subsystem: db/schema + test-infrastructure
tags: [schema, ddl, scan, exit-triggers, wave-0, test-stubs]
dependency_graph:
  requires: []
  provides: [scan_exit_triggers table, Wave 0 test contract]
  affects: [src/bensdorp1/db/schema.py, tests/test_commands/test_scan.py]
tech_stack:
  added: []
  patterns: [SQLAlchemy Core Table + Index pattern, pytest.skip stub pattern]
key_files:
  created:
    - tests/test_commands/test_scan.py
  modified:
    - src/bensdorp1/db/schema.py
    - .planning/phases/07-scan-command/07-VALIDATION.md
decisions:
  - "pytest.skip() used for stubs (not pass) so Wave 2/3 executors can grep 'skipped' vs 'passed' to confirm stub replacement"
  - "noqa: F401 on app import — import is required by plan spec for Wave 2/3 integration tests; ruff would otherwise remove it"
metrics:
  duration: "4 minutes"
  completed_date: "2026-05-24"
  tasks: 2
  files: 3
---

# Phase 7 Plan 01: DB Schema Extension + Wave 0 Test Stubs Summary

scan_exit_triggers table added to schema.py (6 columns, 1 index, 2 FK constraints) and 10 Wave 0 test stubs created in test_scan.py to serve as target IDs for Plans 07-02 and 07-03.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add scan_exit_triggers table to schema.py | 789236e | src/bensdorp1/db/schema.py |
| 2 | Create test_scan.py with 10 Wave 0 stubs + update 07-VALIDATION.md | 21b1249 | tests/test_commands/test_scan.py, .planning/phases/07-scan-command/07-VALIDATION.md |

## Verification Results

```
uv run pytest tests/test_commands/test_scan.py -x
  → 10 skipped in 0.89s (exit 0)

uv run mypy src/bensdorp1/db/schema.py tests/test_commands/test_scan.py --strict
  → Success: no issues found in 2 source files (exit 0)

uv run ruff check src/bensdorp1/db/schema.py tests/test_commands/test_scan.py
  → All checks passed! (exit 0)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff F401 and E501 violations in test_scan.py initial draft**
- **Found during:** Task 2 verification
- **Issue:** `from bensdorp1.cli import app` flagged as unused (F401) because stubs use pytest.skip only; two docstrings exceeded 88-char line limit (E501)
- **Fix:** Added `# noqa: F401` comment explaining the import is used by Wave 2/3 tests; shortened the two offending docstrings
- **Files modified:** tests/test_commands/test_scan.py
- **Commit:** 21b1249 (fixed inline before commit)

## Known Stubs

All 10 functions in tests/test_commands/test_scan.py are intentional Wave 0 stubs. Each calls `pytest.skip("Wave 0 stub — implemented in Plan 07-03")`. This is by design — Plans 07-02 and 07-03 will replace each stub with a full implementation.

| Stub | File | Line | Reason |
|------|------|------|--------|
| test_schema_has_exit_triggers_table | tests/test_commands/test_scan.py | 20 | Wave 0 — Plan 07-03 implements |
| test_time_gate | tests/test_commands/test_scan.py | 25 | Wave 0 — Plan 07-03 implements |
| test_happy_path_bull | tests/test_commands/test_scan.py | 30 | Wave 0 — Plan 07-03 implements |
| test_bearish_regime | tests/test_commands/test_scan.py | 35 | Wave 0 — Plan 07-03 implements |
| test_idempotent_same_day | tests/test_commands/test_scan.py | 40 | Wave 0 — Plan 07-03 implements |
| test_force_reruns_scan | tests/test_commands/test_scan.py | 45 | Wave 0 — Plan 07-03 implements |
| test_non_trading_day | tests/test_commands/test_scan.py | 50 | Wave 0 — Plan 07-03 implements |
| test_catchup_stop_updates | tests/test_commands/test_scan.py | 55 | Wave 0 — Plan 07-03 implements |
| test_stop_freeze_after_trigger | tests/test_commands/test_scan.py | 60 | Wave 0 — Plan 07-03 implements |
| test_exit_trigger_on_missed_day | tests/test_commands/test_scan.py | 65 | Wave 0 — Plan 07-03 implements |

## Threat Flags

No new security-relevant surface introduced. The scan_exit_triggers Table definition is pure DDL (static Python objects); no user input reaches the DDL layer. Parameterized inserts will be enforced in Plans 07-02/03 per T-7-01.

## Self-Check: PASSED

- [x] src/bensdorp1/db/schema.py — scan_exit_triggers Table with 6 columns present
- [x] tests/test_commands/test_scan.py — 10 stubs, all skipped, exit 0
- [x] .planning/phases/07-scan-command/07-VALIDATION.md — wave_0_complete: true
- [x] Commit 789236e exists (Task 1)
- [x] Commit 21b1249 exists (Task 2)
