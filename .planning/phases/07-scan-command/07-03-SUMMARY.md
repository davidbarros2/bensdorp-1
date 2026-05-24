---
phase: 07-scan-command
plan: "03"
subsystem: commands/scan
tags: [scan, typer, cli, time-gate, idempotency, tests, wave-3]
dependency_graph:
  requires: ["07-01", "07-02"]
  provides: [scan Typer command, 10 passing tests]
  affects:
    - src/bensdorp1/commands/scan.py
    - tests/test_commands/test_scan.py
tech_stack:
  added: []
  patterns:
    - time-gate guard before DB access
    - idempotency replay from scans.raw_output
    - module-level patch targets for CliRunner tests
    - inserted_primary_key None-guard pattern (SQLAlchemy mypy)
key_files:
  created: []
  modified:
    - src/bensdorp1/commands/scan.py
    - tests/test_commands/test_scan.py
decisions:
  - "Console created after idempotency check on trading-day path; single engine instance reused for both idempotency SELECT and run_scan call"
  - "Non-trading day path creates its own engine (not shared with trading-day path) to avoid get_engine being called before the is_trading_day check"
  - "test_exit_trigger_on_missed_day asserts triggered_date == today (scan date), not missed_day — matching _detect_exit_triggers current D-09 behavior"
  - "Ruff auto-fix applied for I001 import order in test_exit_trigger_on_missed_day (sorted alphabetically by name)"
metrics:
  duration: "6 minutes"
  completed_date: "2026-05-24"
  tasks: 2
  files: 2
---

# Phase 7 Plan 03: scan.py Typer Command + Test Implementation Summary

Full Typer scan command with time gate, non-trading-day replay, idempotency, --force flag, and engine delegation; all 10 test stubs replaced with passing implementations covering CliRunner integration scenarios and private engine unit tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement scan.py Typer command | 102e155 | src/bensdorp1/commands/scan.py |
| 2 | Implement all 10 tests in test_scan.py | 07f4e58 | tests/test_commands/test_scan.py |

## Verification Results

```
uv run pytest tests/test_commands/test_scan.py -x -v
  → 10 passed in 0.90s (exit 0, 0 skipped)

uv run mypy src/bensdorp1/commands/scan.py tests/test_commands/test_scan.py --strict
  → Success: no issues found in 2 source files (exit 0)

uv run ruff check src/bensdorp1/commands/scan.py tests/test_commands/test_scan.py
  → All checks passed! (exit 0)

uv run ruff format --check src/bensdorp1/commands/scan.py tests/test_commands/test_scan.py
  → 2 files already formatted (exit 0)
```

### Acceptance criteria:

- [x] uv run pytest tests/test_commands/test_scan.py -x -v exits 0
- [x] All 10 tests pass (0 skipped)
- [x] test_time_gate: exit_code == 1 and "16:30 ET" in output
- [x] test_idempotent_same_day: mock_run_scan.assert_not_called() passes
- [x] test_force_reruns_scan: mock_run_scan.assert_called_once() passes
- [x] test_schema_has_exit_triggers_table: "scan_exit_triggers" confirmed in metadata.tables
- [x] test_exit_trigger_on_missed_day: triggered_date == today (D-09 scan date semantics)
- [x] grep -c "pytest.skip" returns 0 (no remaining stubs)
- [x] uv run mypy tests/test_commands/test_scan.py --strict exits 0
- [x] uv run ruff check tests/test_commands/test_scan.py exits 0
- [x] scan.py contains: raise typer.Exit(code=1) (time gate failure path)
- [x] scan.py contains: 2x raise typer.Exit() clean exits (non-trading day + idempotent)
- [x] scan.py contains: from bensdorp1.commands._scan_engine import run_scan
- [x] scan.py does NOT contain: typer.echo("Not yet implemented.")

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] E501 line length violations in scan.py initial draft**
- **Found during:** Task 1 verification (ruff check)
- **Issue:** `typer.Option(False, "--force", help=...)` and two `print_info(...)` calls exceeded 88-char line limit
- **Fix:** Wrapped option definition across 3 lines; used string concatenation and line breaks for print_info calls
- **Files modified:** src/bensdorp1/commands/scan.py
- **Commit:** 102e155 (fixed inline before commit)

**2. [Rule 1 - Bug] Incorrect mock_dt.now.return_value.date.return_value usage in tests**
- **Found during:** Task 2 first test run
- **Issue:** Setting `.date.return_value` on a real `datetime` object (not a Mock) raises `AttributeError: 'builtin_function_or_method' object has no attribute 'return_value'`. The real datetime's `.date()` method works correctly without this override.
- **Fix:** Removed the incorrect line; `mock_dt.now.return_value = datetime(2026, 5, 21, 17, 0, tzinfo=MARKET_TZ)` is sufficient — `.date()` returns the correct `date` object from the real datetime.
- **Files modified:** tests/test_commands/test_scan.py
- **Commit:** 07f4e58 (fixed inline before commit)

**3. [Rule 1 - Bug] test_non_trading_day time was 10:00 ET (before time gate)**
- **Found during:** Task 2 first test run
- **Issue:** The non-trading day test used `datetime(2026, 5, 23, 10, 0, ...)` — before 16:30 ET — which hit the time gate and caused exit code 1 instead of 0.
- **Fix:** Changed to `datetime(2026, 5, 23, 17, 0, ...)` (Saturday at 17:00 ET, after market gate, non-trading day).
- **Files modified:** tests/test_commands/test_scan.py
- **Commit:** 07f4e58 (fixed inline before commit)

**4. [Rule 1 - Bug] mypy: inserted_primary_key[0] indexing on Any | None**
- **Found during:** Task 2 mypy strict check
- **Issue:** `result.inserted_primary_key[0]` — SQLAlchemy stubs type `inserted_primary_key` as `Any | None`; direct indexing fails mypy strict (`[index]` error). Occurred at 4 sites in test_scan.py.
- **Fix:** Used the pattern from _scan_engine.py: `pk = result.inserted_primary_key; assert pk is not None; pos_id: int = int(pk[0])`
- **Files modified:** tests/test_commands/test_scan.py
- **Commit:** 07f4e58 (fixed inline before commit)

**5. [Rule 1 - Bug] ruff E501 + B905 + I001 violations in test_scan.py**
- **Found during:** Task 2 ruff check
- **Issue:** Comments exceeded 88 chars (E501); `zip()` lacked `strict=True` (B905); local import block was unsorted (I001)
- **Fix:** Shortened comments; added `strict=True` to all zip() calls; ran `ruff check --fix` for I001 auto-fix; broke long datetime lines with line continuation
- **Files modified:** tests/test_commands/test_scan.py
- **Commit:** 07f4e58 (fixed inline before commit)

## Known Stubs

None. All 10 test stubs replaced with full implementations.

## Threat Flags

No new security-relevant surface introduced beyond the plan's threat model:
- T-7-01 (SQL injection): `select(scans.c.raw_output).where(scans.c.scan_date == scan_date_utc)` uses bound parameters — no string interpolation.
- T-7-02 (Rich markup injection): All `console.print(raw_output, markup=False, highlight=False)` calls include `markup=False`.
- T-7-03 (Path traversal): `DATA_DIR / "data" / "bensdorp1.db"` uses Path join.

## Self-Check: PASSED

- [x] src/bensdorp1/commands/scan.py — 84 lines, full implementation (no stub text)
- [x] tests/test_commands/test_scan.py — 492 lines, 10 test functions, 0 pytest.skip
- [x] Commit 102e155 exists (Task 1)
- [x] Commit 07f4e58 exists (Task 2)
- [x] 10 tests pass, 0 skipped (verified above)
- [x] mypy strict: Success (0 errors)
- [x] ruff check: All checks passed
- [x] ruff format: Already formatted
