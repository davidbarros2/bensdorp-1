---
phase: 08-confirmation-commands
plan: "03"
subsystem: commands
tags: [sell, cmd-07, confirmation, pnl, exit-trigger, audit]
dependency_graph:
  requires:
    - 08-01 (schema migrations, stub test skeletons)
  provides:
    - sell command (CMD-07) fully implemented
    - 3/3 sell test scenarios passing
  affects:
    - tests/test_cli.py (removed sell from stub parametrize list)
tech_stack:
  added: []
  patterns:
    - two-step UPDATE for ALTER TABLE columns not in SQLAlchemy Table object
    - parameterized text() for extra columns alongside update() for known columns
    - run_migrations() called in test setup to ensure ALTER TABLE columns exist
key_files:
  created: []
  modified:
    - src/bensdorp1/commands/sell.py
    - tests/test_commands/test_sell.py
    - tests/test_cli.py
decisions:
  - Two-step UPDATE: update() for core columns + text() for closed_reason/closed_manual_reason (ALTER TABLE cols not declared in schema.py Table object)
  - run_migrations() called at test setup to add ALTER TABLE columns before seeding
  - test_no_exit_trigger keeps tmp_path signature (per Plan 01) and uses MagicMock engine
  - Removed sell from test_stub_exits_cleanly (Rule 1 auto-fix — sell is now a full command)
metrics:
  duration: 7m
  completed: "2026-05-25"
  tasks_completed: 2
  files_modified: 3
---

# Phase 8 Plan 03: Sell Command (CMD-07) Summary

Full implementation of `bensdorp1 sell SYMBOL PRICE [--date DATE] [--manual REASON]` replacing the stub. All 3 CMD-07 test scenarios pass; mypy strict and ruff clean.

## What Was Built

### sell.py — CMD-07 implementation
Replaces the one-liner stub with a complete flow:
- Resolves sell date (defaults to today ET)
- Validates: open position exists, price > 0, sell date >= entry date
- Exit trigger lookup: `SELECT reason FROM scan_exit_triggers WHERE position_id = ? ORDER BY id ASC LIMIT 1` (earliest trigger per D-12)
- `_REASON_MAP` converts `"Trailing stop"` → `"stop_trailing"`, `"Initial stop"` → `"stop_initial"`
- `--manual REASON` bypasses trigger lookup: `closed_reason = "manual"`, `event_type = SELL_MANUAL`
- P&L: `realized_pnl = (price - entry_close) * shares`; `realized_pnl_pct = (price / entry_close - 1) * 100.0`
- Days held: `len(get_trading_days(entry_date.date(), sell_date))` — NYSE calendar, pitfall 4 (.date() on datetime)
- Confirmation preview rendered via `render_kv_block`; SEPARATOR, header, all spec §7.4 fields
- State write: `update(positions)` for core columns + parameterized `text()` for ALTER TABLE columns
- `create_backup` + `log_event(SELL_CONFIRMED or SELL_MANUAL)` + `print_success`

### test_sell.py — 3 CMD-07 scenarios
All 3 skipped stubs replaced with real implementations:

1. **test_no_exit_trigger** — mocked engine with `fetchone.side_effect = [position_row, None]`; verifies exit code 1 and error message
2. **test_happy_path_normal** — real SQLite DB via `db_engine` fixture; seeds position + trigger (reason="Trailing stop"); asserts exit 0, `closed_reason="stop_trailing"`, P&L correct, audit event "sell_confirmed"
3. **test_manual_sell** — real SQLite DB, no trigger row (verifies bypass); `--manual "Stop tightened ahead of earnings"`; asserts `closed_reason="manual"`, `closed_manual_reason` set, audit event "sell_manual"

P&L assertions use `pytest.approx` for float precision.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two-step UPDATE for ALTER TABLE columns**
- **Found during:** Task 2 (test run)
- **Issue:** SQLAlchemy 2.0.48 raises `CompileError('Unconsumed column names: closed_reason, closed_manual_reason')` when `update(positions).values(closed_reason=..., closed_manual_reason=...)` is called — the `positions` Table object does not declare these ALTER TABLE columns. PATTERNS.md incorrectly claimed "SQLAlchemy does not validate kwargs against `Table.columns`".
- **Fix:** Split the UPDATE into two statements — `update(positions).values(closed_at=..., exit_price=..., realized_pnl=...)` for the schema-declared columns, followed by a parameterized `text("UPDATE positions SET closed_reason = :r, closed_manual_reason = :m WHERE id = :id")` for the ALTER TABLE columns. Both are fully parameterized; no f-string SQL.
- **Files modified:** `src/bensdorp1/commands/sell.py`
- **Commit:** 9f526aa

**2. [Rule 1 - Bug] run_migrations() needed in test setup**
- **Found during:** Task 2 (test run)
- **Issue:** `db_engine` fixture runs `metadata.create_all` which creates the table without `closed_reason` / `closed_manual_reason` (not in schema.py). The two-step UPDATE requires those columns to physically exist.
- **Fix:** Added `run_migrations(db_engine)` at the top of each real-DB test to apply the ALTER TABLE migrations before seeding data.
- **Files modified:** `tests/test_commands/test_sell.py`
- **Commit:** 9f526aa

**3. [Rule 1 - Bug] Remove sell from test_stub_exits_cleanly**
- **Found during:** Full test suite run
- **Issue:** `test_cli.py::test_stub_exits_cleanly[sell]` expected exit code 0 and "Not yet implemented." — both now fail because sell requires SYMBOL and PRICE arguments.
- **Fix:** Removed `"sell"` from the parametrize list; updated comment to note sell is a full implementation.
- **Files modified:** `tests/test_cli.py`
- **Commit:** 9f526aa

## P&L Float Precision Approach

All float assertions use `pytest.approx` with default relative tolerance (1e-6). Example:
```python
assert row.realized_pnl == pytest.approx((178.20 - 182.50) * 50)  # -$215.00
```
This covers the SQLite float round-trip (64-bit IEEE 754) without hardcoded tolerance.

## Trigger Lookup Ordering

The test uses a single `scan_exit_triggers` row (`reason="Trailing stop"`). The explicit `.order_by(scan_exit_triggers.c.id.asc()).limit(1)` in the query is verified as correct structure. For multi-trigger scenarios, the ASC ordering ensures the earliest (original) trigger is used per D-12.

## Success Criteria Verification

- `uv run pytest tests/test_commands/test_sell.py -v` → 3 PASSED, 0 SKIPPED
- `uv run mypy src/bensdorp1/commands/sell.py tests/test_commands/test_sell.py --strict` → 0 errors
- `uv run ruff check src/bensdorp1/commands/sell.py tests/test_commands/test_sell.py` → all checks passed
- `uv run pytest -x` → 319 passed, 8 skipped (pre-existing buy/fix skips)
- `grep -c "text(f\""` on sell.py → 0 (no f-string SQL injection)

## Self-Check: PASSED

Files verified:
- `src/bensdorp1/commands/sell.py` — present (229 lines + 12-line two-step UPDATE addition)
- `tests/test_commands/test_sell.py` — present, 3 tests passing
- `tests/test_cli.py` — present, sell removed from stub list

Commits verified:
- `2efa018` (feat: sell.py implementation)
- `9f526aa` (feat: test_sell.py + sell.py two-step UPDATE fix)
