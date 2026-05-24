---
phase: 07-scan-command
fixed_at: 2026-05-24T20:50:00Z
review_path: .planning/phases/07-scan-command/07-REVIEW.md
iteration: 1
findings_in_scope: 12
fixed: 12
skipped: 0
status: all_fixed
---

# Phase 07: Code Review Fix Report

**Fixed at:** 2026-05-24T20:50:00Z
**Source review:** .planning/phases/07-scan-command/07-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 12
- Fixed: 12
- Skipped: 0

## Fixed Issues

### CR-01: Non-trading-day branch queries DB without running migrations

**Files modified:** `src/bensdorp1/commands/scan.py`
**Commit:** `901bb2c`
**Applied fix:** Added `run_migrations(engine)` call immediately after `get_engine(db_path)` in the non-trading-day branch (line 42), before the `engine.connect()` block that queries the `scans` table. This ensures the schema is created on first run even when the user invokes `scan` on a non-trading day.

---

### CR-02: `_detect_exit_triggers` records wrong `triggered_date` and `close_at_trigger` for catch-up triggers

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `1d4052e`
**Applied fix:** Changed `triggered_position_ids` from `set[int]` to `dict[int, tuple[date, float, float]]`. In `_update_position_stops`, when a trigger is detected, the code now stores `triggered_position_ids[pos.id] = (day, close, eff_stop)` instead of `.add(pos.id)`. In `_detect_exit_triggers`, the code now unpacks `trigger_day, close_at_trigger, eff_stop = triggered_position_ids[pos.id]` and uses `trigger_day` (not `today`) for `triggered_date_utc`. This implements D-09 correctly: `triggered_date` now stores the actual day the stop was hit.

Note: WR-04 is resolved as part of this same commit — `eff_stop` (the value that actually caused the trigger) is now stored in the dict and used in the INSERT, rather than recomputing from the stale `pos.trailing_stop`.

---

### CR-03: `_detect_exit_triggers` queries all rows from `scan_exit_triggers` without filtering

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `88b02c2`
**Applied fix:** Two changes:
1. In `_detect_exit_triggers`, scoped the `existing_rows` query to exclude rows where `scan_id == current scan_id` (using `.where(scan_exit_triggers.c.scan_id != scan_id)`), so a `--force` re-run correctly sees positions as re-triggerable.
2. In `_persist_scan`, added a block that deletes prior `scan_exit_triggers` rows for the current `scan_id` when `force=True`, so re-triggered positions get fresh rows on forced re-runs.

---

### CR-04: `_run_screening` raises uncaught `ValueError` from strategy filters

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `d7ca5d2`
**Applied fix:** Wrapped the `regime_filter` call and all subsequent strategy filter calls in a `try/except ValueError as exc: raise RuntimeError(str(exc)) from exc` block. This converts any `ValueError` from insufficient data into a `RuntimeError`, which is already caught by `run_scan`'s outer `except RuntimeError` handler, producing a user-friendly error message instead of a raw traceback.

---

### WR-01: `scan.py` idempotency check does not guard against `existing.raw_output is None`

**Files modified:** `src/bensdorp1/commands/scan.py`
**Commit:** `a5557e6`
**Applied fix:** Added an `else` branch to the `if existing.raw_output is not None` check that calls `print_info()` with a descriptive message ("A scan record exists for today but has no output (the prior scan may have failed). Re-run with --force to retry."), so the user is informed rather than receiving a silent exit.

---

### WR-02: `_run_screening` computes `spx_sma_200` differently from `regime_filter`

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `21424d1`
**Applied fix:** Moved `spx_closes: pd.Series[float] = spx_df["close"].astype(float)` to before the `spx_close` and `spx_sma_200` computations. Both `spx_close` and `spx_sma_200` now derive from the same `astype(float)` cast series, ensuring consistency with the value passed to `regime_filter`.

---

### WR-03: `_get_close_for_day` uses `df.iterrows()` — O(n) linear scan per call

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `9baf177`
**Applied fix:** Replaced the `for _, row in df.iterrows()` loop with a vectorized approach: `dates = df["trade_date"].apply(lambda td: td.date() if hasattr(td, "date") else date(...))`, then `mask = dates == target_date`, then `df.loc[mask, "close"]`. Same semantics (returns first match), no Python-level loop.

---

### WR-04: `_detect_exit_triggers` recomputes `eff_stop` from stale `pos.trailing_stop`

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `1d4052e` (same commit as CR-02)
**Applied fix:** The `triggered_position_ids` dict now stores a 3-tuple `(trigger_day, close_at_trigger, eff_stop)`, where `eff_stop` is the actual effective stop that caused the trigger (computed from `new_ts`, not the stale `pos.trailing_stop`). `_detect_exit_triggers` unpacks this tuple and uses the stored `eff_stop` for both the DB INSERT and the returned `_TriggerRow`.

---

### WR-05: `liquidity_filter` raises `ValueError` for symbols with fewer than 21 rows

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `44231fb`
**Applied fix:** Added pre-filtering in `_run_screening` before calling strategy filters:
- Before `liquidity_filter`: filters `constituent_dfs` to only include symbols with `len(df) >= 21`
- Before `momentum_filter`: filters `liquid_dfs` to only include symbols with `len(df) >= 201`
This prevents `ValueError` from new S&P 500 constituents with insufficient history.

---

### IN-01: Docstring for `_detect_exit_triggers` contradicts implementation on D-09

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `1d4052e` (resolved as side effect of CR-02 fix)
**Applied fix:** The CR-02 fix changed the implementation to match the docstring — `triggered_date` now stores the actual day the stop was hit. The docstring ("D-09: triggered_date stores the actual day the stop was hit") is now accurate. No separate docstring change was needed.

---

### IN-02: `test_non_trading_day` does not test real DB crash

**Files modified:** `tests/test_commands/test_scan.py`
**Commit:** `eed6c8b`
**Applied fix:** Added a new test function `test_non_trading_day_fresh_db` that does NOT mock `get_engine`, letting the real SQLite path run against a fresh empty database. Added `create_engine` to imports. The test verifies that the non-trading-day branch exits cleanly (exit code 0) with a fresh DB, proving the CR-01 `run_migrations` fix works. Before CR-01, this test would have failed with `OperationalError: no such table: scans`.

---

### IN-03: Magic number `rows_needed=221` not explained

**Files modified:** `src/bensdorp1/commands/_scan_engine.py`
**Commit:** `15e8479`
**Applied fix:** Defined `_PRICE_ROWS_NEEDED: int = 221` as a module-level constant with a comment explaining the derivation (201 rows for momentum_filter's T-200 return + 20 for the liquidity window + 1 "today" row excluded from rolling averages). Updated the `_load_price_dfs(engine, all_symbols)` call in `run_scan` to use `rows_needed=_PRICE_ROWS_NEEDED`. Also repaired a UTF-8 encoding corruption introduced in the WR-03 commit (em dash character encoded as Windows-1252 0x97 instead of UTF-8 e2 80 94).

---

### Test Suite Updates

**Files modified:** `tests/test_commands/test_scan.py`, `tests/test_commands/test_scan_engine.py`
**Commit:** `2b0c3c8`
**Applied fix:** Updated all test functions that pass `triggered_ids` to `_update_position_stops` or `_detect_exit_triggers`:
- `test_catchup_stop_updates`: changed `set[int] = set()` to `dict[int, tuple[date, float, float]] = {}`
- `test_stop_freeze_after_trigger`: changed `set[int] = {int(pos_id)}` to `dict[int, tuple[date, float, float]] = {int(pos_id): (today, 90.0, 100.0)}`
- `test_exit_trigger_on_missed_day`: changed `set[int] = set()` to dict; updated `triggered_date` assertion from `== today` to `== missed_day` (reflecting the correct D-09 behavior after CR-02)
- `test_detect_exit_triggers_already_existing` (test_scan_engine.py): changed `{pos_id}` set literal to `{pos_id: (today, 90.0, 100.0)}` dict; inserted the pre-existing trigger row with a prior scan_id (not the current scan_id) so the CR-03 scoped query correctly sees it as already triggered

---

_Fixed: 2026-05-24T20:50:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
