---
phase: 04-strategy-logic
fixed_at: 2026-05-23T19:10:00Z
review_path: .planning/phases/04-strategy-logic/04-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-05-23T19:10:00Z
**Source review:** .planning/phases/04-strategy-logic/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: Division by zero in `rank_candidates` when `close_t200 == 0`

**Files modified:** `src/bensdorp1/strategy/screening.py`
**Commit:** 833d1eb
**Applied fix:** Added `if close_t200 == 0.0: continue` guard before ROC computation in `rank_candidates`, skipping symbols with uncomputable ROC rather than crashing the scan.

---

### CR-02: Division by zero in `compute_position_size` and `rank_candidates` when `prev_close == 0`

**Files modified:** `src/bensdorp1/strategy/positions.py`, `src/bensdorp1/strategy/screening.py`
**Commits:** 20824cf (positions.py), 833d1eb (screening.py)
**Applied fix:** Added `if prev_close <= 0.0: return 0` guard in `compute_position_size`. The inline formula in `rank_candidates` was replaced by a call to `compute_position_size` (WR-01 fix), which automatically picks up this guard.

---

### CR-03: Persist failure silently discards all rows fetched in the same scan

**Files modified:** `src/bensdorp1/data/prices.py`
**Commit:** 270a02a
**Applied fix:** Added `raise` after the `log_event` call in the `except` block of `update_price_data`. The exception is now re-raised after being logged so callers receive the failure signal rather than returning normally with stale data.

---

### WR-01: Position-size formula duplicated verbatim across two modules

**Files modified:** `src/bensdorp1/strategy/screening.py`
**Commit:** 833d1eb
**Applied fix:** Removed `import math` from screening.py and added `from bensdorp1.strategy.positions import compute_position_size`. Replaced the inline `math.floor((available_cash * 0.10) / prev_close)` in `rank_candidates` with a call to `compute_position_size(available_cash, prev_close)`. No circular dependency risk since both modules are siblings in the same subpackage.

---

### WR-02: `_download_with_retry` will raise `KeyError` if yfinance omits `Volume` column

**Files modified:** `src/bensdorp1/data/prices.py`
**Commit:** 270a02a
**Applied fix:** Replaced `df[["Close", "Volume"]]` with `available_cols = [c for c in ["Close", "Volume"] if c in df.columns]; df[available_cols]` — consistent with the pattern already used in `_download_bulk`.

---

### WR-03: `test_liquidity_filter_top_quartile` does not assert symbol `"C"` is excluded

**Files modified:** `tests/test_strategy/test_screening.py`
**Commit:** 833d1eb
**Applied fix:** Added `assert "C" not in result` after the existing assertions in `test_liquidity_filter_top_quartile`. Symbol C has avg volume 300, which is below the 75th percentile threshold of 325.0 and must be excluded.

---

### WR-04: `momentum_filter` and `rank_candidates` minimum row check misaligned with 200-day look-back

**Files modified:** `src/bensdorp1/strategy/screening.py`, `tests/test_strategy/test_screening.py`
**Commit:** 833d1eb
**Applied fix:** Changed minimum row requirement from 200 to 201 in both `momentum_filter` and `rank_candidates`. Updated `iloc[-200]` to `iloc[-201]` so that with 201 rows, `iloc[-1]` is today and `iloc[-201]` is exactly 200 trading days ago (true T-200 exclusive look-back). Updated all affected unit tests (pass/reject/boundary/insufficient/zero_position_size) and the Hypothesis property test to supply 201-row DataFrames. Updated error messages to say `>= 201`. `regime_filter` was left unchanged — it uses `iloc[-200:].mean()` which includes today per STRAT-01 ("last 200 closes including today") and is intentionally correct.

---

## Skipped Issues

None — all findings were fixed.

---

_Fixed: 2026-05-23T19:10:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
