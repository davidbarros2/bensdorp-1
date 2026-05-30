---
phase: 11-catch-up-logic
plan: "02"
subsystem: catch-up-logic
tags: [split-detection, delisting, missed-days-walk, catch-up-events, scan-engine]
dependency_graph:
  requires:
    - positions.delisted column (11-01 schema migration)
    - events.py render_* functions (11-01 Task 2)
    - _OpenPosition with entry_close/shares/delisted (11-01 Task 3)
  provides:
    - _apply_splits() — D-05 window, D-06 math, SPLIT_APPLIED audit, split notification
    - _detect_delisted_positions() — D-11 set-once flag, POSITION_DELISTED_FROM_INDEX audit
    - _run_preflight() extended to return last_scan_date (Pitfall 7)
    - _update_position_stops() extended with last_scan_date + catch_up_events accumulator
    - run_scan() threading of last_scan_date; _detect_delisted_positions call
  affects:
    - src/bensdorp1/commands/_scan_engine.py
    - tests/test_commands/test_catchup.py
tech_stack:
  added:
    - import yfinance as yf (in _scan_engine.py — previously only in prices.py)
  patterns:
    - D-05 window approach for split idempotency (no extra DB column needed)
    - catchup_split_events dict threaded through _apply_splits for Template 5 events
    - D-03 collapse: initial_ts_for_new_high / had_new_high / final_new_ts accumulators
    - _entry_date_as_date() helper for datetime/date union handling
    - Sentinel key "_regime" in catch_up_events for D-10 system-level regime events
key_files:
  created: []
  modified:
    - src/bensdorp1/commands/_scan_engine.py
    - tests/test_commands/test_catchup.py
decisions:
  - Reuse prices.py _to_yfinance() (DATA-08 sole normalization site) — imported in _scan_engine.py
  - catchup_split_events parameter on _apply_splits() passes Template 5 events directly (no brittle string parsing)
  - _entry_date_as_date() helper encapsulates datetime/date union (pos.entry_date is datetime from DB)
  - Sentinel key "_regime" in catch_up_events dict carries regime events for Plan 03 renderer
  - Dividend fetch guarded by `if missed_days and catch_up_events is not None` (D-08: no fetch on no-absence scans)
  - _update_position_stops() new params are keyword-only with default=None for backward compat
metrics:
  duration: "~35 minutes"
  completed_date: "2026-05-30"
  tasks_completed: 3
  files_changed: 2
---

# Phase 11 Plan 02: Engine Logic — Splits, Delisting, Catch-Up Walk

One-liner: Engine behavioral core — _apply_splits() with D-05 window idempotency + D-06 math + audit, _detect_delisted_positions() with D-11 set-once semantics, extended _run_preflight() returning last_scan_date, and _update_position_stops() accumulating per-position catch-up events (stop violations, collapsed Template 3, dividends, regime flips, split Template 5).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | _apply_splits() — D-05 window, D-06 math, audit + notification | 6dacde6 | _scan_engine.py, test_catchup.py |
| 2 | _detect_delisted_positions() + buy-candidate exclusion + _run_preflight extension | 6dacde6 | _scan_engine.py, test_catchup.py |
| 3 | Event-accumulating missed-days walk (stop, highest-close, dividend, regime) | 6dacde6 | _scan_engine.py, test_catchup.py |

## What Was Built

### Task 1 — _apply_splits()

- `_apply_splits(engine, open_positions, last_scan_date, today, split_notifications, catchup_split_events=None)` added to `_scan_engine.py`.
- D-05 window: `split_date > max(entry_date, last_scan_date)` and `split_date <= today`. Window self-advances with each scan so prior-scan splits fall outside the next scan's window (no re-application, no extra DB column).
- D-06 math: `shares = floor(shares * ratio)`; all price fields divided by ratio.
- T-11-04: `ratio <= 0` guard; `try/except` around `yf.Ticker(...).splits`.
- Logs `SPLIT_APPLIED` with before/after payload (T-11-07).
- Appends System-notes notification (§8.3 format) to `split_notifications`.
- When `catchup_split_events` is provided, also appends Template 5 (`render_stock_split`) per split for catch-up summary.
- Reuses `_to_yfinance()` from `prices.py` (DATA-08: sole normalization site; imported via `from bensdorp1.data.prices import _to_yfinance`).
- `_entry_date_as_date()` helper added to safely extract `date` from `pos.entry_date` (datetime in DB).
- Four split tests green: math, idempotency, audit event, outside-window ignored.

### Task 2 — _detect_delisted_positions() + _run_preflight extension

- `_detect_delisted_positions(engine, open_positions, constituents)` added: iterates open positions, skips any in constituent set or already `delisted==1`, sets `delisted=1`, logs `POSITION_DELISTED_FROM_INDEX` with position_id payload, appends `render_removed_from_sp500(symbol, removal_date=None)` to returned event list.
- D-11 set-once semantics: positions already `delisted==1` are entirely skipped (no re-log on subsequent scans).
- Buy-candidate exclusion: delisted symbols are absent from the current constituent set → not in `all_symbols` → not in `price_dfs` → naturally excluded from `_run_screening` screening universe. No additional filter needed.
- `_run_preflight()` return tuple extended from 4 to 5 elements: `(constituents, missed_days, catch_up_notes, freshness_days, last_scan_date)`. `last_scan_date: date | None` is the date of the most-recent prior scan (None if no prior scan).
- `run_scan()` unpacking updated to bind `last_scan_date`. `_detect_delisted_positions` called immediately after open positions query; returned events merged into `catch_up_events` dict.
- Four delisted tests green: flag set, event not repeated, excluded from candidates, Template 4 rendered.

### Task 3 — Event-accumulating missed-days walk

- `_update_position_stops()` signature extended with two keyword-only parameters: `last_scan_date: date | None = None` and `catch_up_events: dict[str, list[str]] | None = None`. Default None preserves backward compatibility; existing call sites without these params continue to work.
- At function start, `_apply_splits()` is called with `catchup_split_ev` accumulator (populated only when `catch_up_events is not None and missed_days`). Template 5 events merged into `catch_up_events` immediately after `_apply_splits` returns.
- D-03 collapse: `initial_ts_for_new_high`, `had_new_high`, `final_new_high_date`, `final_new_high_close`, `final_new_ts` accumulators track per-position new-high state. After the walk, a single `render_new_highest_close` call emits initial→final stop values (not one per day).
- Stop violations (missed days only): `render_trailing_stop_violated` or `render_initial_stop_violated` appended to `catch_up_events[symbol]` based on which stop is binding.
- D-08 dividends: `yf.Ticker(symbol).dividends` fetched once per position at function start, only when `missed_days` is non-empty. Filtered to `div_date > last_scan_date and div_date in missed_days`. `render_dividend` appended per dividend in window.
- D-10 regime: SPX closes from `price_dfs["^GSPC"]` used to compute SMA-200 regime per missed day. Flip between consecutive days emits `render_regime_bull_to_bear` or `render_regime_bear_to_bull` stored under sentinel key `"_regime"` in `catch_up_events`.
- Two walk tests green: stop reconstruction across 3 missed days, split Template 5 in catch-up events.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced brittle split-notification string parsing with direct Template 5 accumulation**
- **Found during:** Task 3 implementation
- **Issue:** Initial approach parsed split notification strings in `_update_position_stops` to extract ratio/date/shares for `render_stock_split`. Brittle, hard to maintain, and triggered ruff E501 line-length violations.
- **Fix:** Added `catchup_split_events: dict[str, list[str]] | None = None` parameter to `_apply_splits()`. When provided, `_apply_splits` appends Template 5 events directly using already-available values (no parsing needed).
- **Files modified:** `src/bensdorp1/commands/_scan_engine.py`
- **Commit:** 6dacde6

**2. [Rule 2 - Type Safety] Used `Any` type annotations for yfinance Series return values**
- **Found during:** Task 1 mypy check
- **Issue:** `yf.Ticker(symbol).splits` and `.dividends` return `pd.Series` but yfinance stubs don't provide precise types; `type: ignore[assignment]` annotations were "unused-ignore" under mypy strict.
- **Fix:** Annotated as `Any` with explicit `pd.Timestamp(ts).date()` conversion for DatetimeIndex iteration. Removed unused `type: ignore` comments.
- **Files modified:** `src/bensdorp1/commands/_scan_engine.py`
- **Commit:** 6dacde6

## Known Stubs

- 4 Plan-03 rendering tests in `tests/test_commands/test_catchup.py` remain as `NotImplementedError` stubs: `test_catchup_summary_rendering`, `test_composite_template`, `test_template3_initial_final_only`, `test_catch_up_audit_event`. Intentional — Plan 03 will implement `_render_output()` catch-up summary block.

## Threat Flags

None. All files modified are internal engine logic. No new network endpoints, auth paths, or trust-boundary crossings introduced beyond what the threat model already covers (yfinance call sites use parameterized queries; ratio guard implemented per T-11-04).

## Self-Check: PASSED

- `src/bensdorp1/commands/_scan_engine.py` contains `def _apply_splits(` — verified
- `src/bensdorp1/commands/_scan_engine.py` contains `import yfinance as yf` — verified
- `src/bensdorp1/commands/_scan_engine.py` contains `ratio <= 0` guard — verified
- `src/bensdorp1/commands/_scan_engine.py` contains `try/except` around `yf.Ticker` — verified
- `src/bensdorp1/commands/_scan_engine.py` contains `def _detect_delisted_positions(` — verified
- `_run_preflight` return signature includes `date | None` as last element — verified
- `run_scan()` unpacks `last_scan_date` from `_run_preflight` — verified
- `6dacde6` — verified in git log (implementation commit)
- `uv run mypy src/bensdorp1` — Success: no issues found in 43 source files
- `uv run ruff check src/bensdorp1/commands/_scan_engine.py` — All checks passed
- `uv run pytest tests/test_commands/test_catchup.py` — 10 passed, 4 NotImplementedError (Plan-03 stubs)
- `uv run pytest tests/test_commands/test_scan.py tests/test_commands/test_scan_engine.py` — 41 passed
- No new normalization function in _scan_engine.py (grep confirms 0 matches for `def _to_yfinance|def .*normalize`)
