---
phase: 04-strategy-logic
reviewed: 2026-05-23T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/bensdorp1/strategy/__init__.py
  - src/bensdorp1/strategy/screening.py
  - src/bensdorp1/strategy/positions.py
  - src/bensdorp1/data/prices.py
  - tests/test_strategy/test_screening.py
  - tests/test_strategy/test_positions.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

The strategy subpackage (`screening.py`, `positions.py`) is structurally sound — pure functions with no I/O, clear docstrings, and good separation of concerns. The test coverage is above average and the Hypothesis invariants are well-chosen. However, three correctness bugs exist that will produce silent wrong results at runtime: two division-by-zero paths (one in the hot ranking loop, one in position sizing) and a silent loss of an entire persist batch when any DB write fails. An additional design defect — position-size logic duplicated verbatim across two modules — creates a drift hazard. Several test coverage gaps leave the most dangerous edge cases unexercised.

---

## Critical Issues

### CR-01: Division by zero in `rank_candidates` when `close_t200 == 0`

**File:** `src/bensdorp1/strategy/screening.py:158`

**Issue:** `roc_200` is computed as `(prev_close / close_t200) - 1.0`. The only guard is `len(df) < 200`, which ensures the row exists but does not guard against its *value* being zero. A split-adjusted historical price of 0.0 (or a corrupt yfinance row) produces a `ZeroDivisionError` that crashes the entire scan without any audit trail. The crash happens inside the loop, so any symbols processed before the bad one are silently dropped from `results` already.

**Fix:**
```python
if close_t200 == 0.0:
    # Skip uncomputable ROC rather than crashing the scan.
    continue
roc_200: float = (prev_close / close_t200) - 1.0
```

---

### CR-02: Division by zero in `compute_position_size` and `rank_candidates` when `prev_close == 0`

**File:** `src/bensdorp1/strategy/positions.py:16` and `src/bensdorp1/strategy/screening.py:159`

**Issue:** Both sites compute `math.floor((cash * 0.10) / prev_close)`. If `prev_close` is 0 (degenerate yfinance row, or any caller passing 0), Python raises `ZeroDivisionError`. The docstring for `compute_position_size` says "Returns 0 when result < 1" but does not document or guard the zero-denominator case. The caller in `rank_candidates` re-implements the same formula inline, so neither guard propagates to the other. No test covers `prev_close=0`.

**Fix in `positions.py`:**
```python
def compute_position_size(available_cash: float, prev_close: float) -> int:
    if prev_close <= 0.0:
        return 0
    return math.floor((available_cash * 0.10) / prev_close)
```

Apply the same guard at `screening.py:159`:
```python
shares: int = 0 if prev_close <= 0.0 else math.floor((available_cash * 0.10) / prev_close)
```

---

### CR-03: Persist failure silently discards all rows fetched in the same scan

**File:** `src/bensdorp1/data/prices.py:263-270`

**Issue:** The `try/except` around `_persist_price_rows` catches every `Exception`, logs an audit event, and then falls through — causing the function to return normally. Any transient or permanent DB write error means the entire batch of price rows (bulk download + all per-symbol retries) is silently discarded. The caller in `update_price_data` has no indication of failure, so subsequent coverage checks (`check_price_coverage`) will return stale counts without any warning visible to the user. Swallowing an exception after a log event is acceptable only if the exception is truly non-fatal; a failure to persist any prices at all is fatal for a scan.

**Fix:** Re-raise (or propagate a sentinel return value) after logging:
```python
try:
    _persist_price_rows(engine, rows)
except Exception as exc:
    log_event(
        engine,
        AuditEventType.DATA_FETCH_FAILED,
        payload={"source": "persist_price_rows", "error": str(exc)},
    )
    raise  # Do not silently discard the fetch failure
```

---

## Warnings

### WR-01: Position-size formula duplicated verbatim across two modules

**File:** `src/bensdorp1/strategy/screening.py:159` and `src/bensdorp1/strategy/positions.py:16`

**Issue:** The formula `math.floor((available_cash * 0.10) / prev_close)` is copy-pasted into `rank_candidates` rather than calling `compute_position_size`. `compute_position_size` is the authoritative function (exported in `__init__.py`). If the sizing constant (10%) ever changes, a maintainer will update one site and miss the other, and the bug will not be caught by tests because both implementations are exercised independently and the tests do not cross-verify them against each other.

**Fix:** Replace the inline computation at `screening.py:159` with a call to the canonical function:
```python
from bensdorp1.strategy.positions import compute_position_size
# ...
shares: int = compute_position_size(available_cash, prev_close)
```
Because `screening.py` already lives in the same subpackage, this is a sibling import with no circular-dependency risk.

---

### WR-02: `_download_with_retry` will raise `KeyError` if yfinance omits `Volume` column

**File:** `src/bensdorp1/data/prices.py:135`

**Issue:** After a successful single-ticker download, the code does `df[["Close", "Volume"]]`. The comment in `_download_bulk` notes that Volume may be absent for index instruments. The same caveat applies here: if `^GSPC` or another instrument is retried individually after the bulk pass fails, and yfinance returns a DataFrame without a `Volume` column, line 135 raises `KeyError: 'Volume'` unconditionally, swallowing the retry in the outer loop that calls `_download_with_retry`. The bulk path handles this correctly by computing `available = [c for c in ["Close", "Volume"] if c in stacked.columns]` (line 89), but the retry path does not.

**Fix:**
```python
available_cols = [c for c in ["Close", "Volume"] if c in df.columns]
result: pd.DataFrame = df[available_cols]
return result
```

---

### WR-03: `test_liquidity_filter_top_quartile` does not assert whether symbol `"C"` (avg vol 300) is included or excluded

**File:** `tests/test_strategy/test_screening.py:99-104`

**Issue:** pandas `quantile(0.75)` of `[100, 200, 300, 400]` using linear interpolation is 325.0 (confirmed). Symbol C has avg vol 300, which is below 325 — so it should be excluded. The test asserts `"D" in result`, `"A" not in result`, and `"B" not in result`, but never asserts `"C" not in result`. This is not a documentation issue; it is a test coverage gap that would allow a threshold-comparison regression (e.g., `>` instead of `>=`) to go undetected for C's boundary neighbourhood, and allows an off-by-one in the quantile implementation to silently include C.

**Fix:** Add the missing assertion:
```python
assert "C" not in result
```

---

### WR-04: `momentum_filter` minimum row check uses `< 200` but `iloc[-200]` accesses index position 0 for exactly 200 rows — misaligned with comment

**File:** `src/bensdorp1/strategy/screening.py:114-119`

**Issue:** The docstring (line 99) says `'200 trading days ago' = T-200 exclusive of today (iloc[-200])`. With exactly 200 rows, `iloc[-1]` is today (row 199) and `iloc[-200]` is row 0 — which means "close 199 trading days ago", not 200. The comment at D-03 says T-200 exclusive of today. The guard `len(df) < 200` allows exactly 200 rows, but in that case `iloc[-200]` returns the very first row (T+0 of the dataset), giving only a 199-day look-back, not 200. The same issue exists in `rank_candidates` at line 157 for the ROC computation.

To be consistent with the docstring ("200 trading days ago"), the minimum should be 201 rows (today + 200 historical rows), or the indexing should use `iloc[-201]` with the current 200-row minimum. As written, every caller is getting a 199-day momentum check silently.

**Fix (preferred — raise required rows by 1):**
```python
if len(df) < 201:
    raise ValueError(
        f"momentum_filter: {symbol} needs >= 201 rows; got {len(df)}"
    )
close_t200: float = float(df["close"].iloc[-201])
```
Apply the same correction to `rank_candidates` (`screening.py:152-157`) and to `regime_filter` (`screening.py:48-53`) where `iloc[-200:].mean()` includes today in the SMA 200 window — which may or may not be intentional (STRAT-01 says "last 200 closes including today", so `regime_filter` appears correct, but `momentum_filter` is inconsistent with it).

---

## Info

### IN-01: `_to_db` uses unconditional `.replace("-", ".")` which corrupts tickers that legitimately contain hyphens in DB form

**File:** `src/bensdorp1/data/prices.py:49-50`

**Issue:** The conversion assumes all hyphens are yfinance-introduced substitutes for periods. If any future ticker in the S&P 500 universe has a legitimate hyphen in its DB representation (uncommon but possible with certain preferred shares or ETFs named by the exchange with a hyphen), `_to_db` will silently corrupt the symbol stored in the DB. The current S&P 500 universe does not have such tickers, so this is a latent rather than active bug, but the assumption is undocumented and fragile. The comment at DATA-08 only documents the BRK.B case.

**Fix:** Document the assumption explicitly:
```python
def _to_db(symbol: str) -> str:
    """Convert yfinance hyphen form back to DB period form. BRK-B -> BRK.B.

    Assumption: ALL hyphens in yfinance ticker names represent periods in the
    exchange/DB canonical form. This holds for all current S&P 500 constituents.
    """
    return symbol.replace("-", ".")
```

---

### IN-02: `test_regime_off_when_close_le_sma200` Hypothesis test has a conditional assertion that silently passes when the invariant is not exercised

**File:** `tests/test_strategy/test_screening.py:295-299`

**Issue:** The test body constructs a series guaranteed to have `close <= sma200` (line 290), but then checks `if today_close <= sma200: assert result is False`. Because the series is always constructed to be bearish, the `if` guard is always true and the `assert` always runs — but this pattern means a future test refactor that accidentally removes the bearish construction would cause the `if` to be false and the test would pass vacuously without actually testing anything. The assertion should be unconditional given that the input is always constructed to be bearish:

```python
# The input is constructed to always be bearish; assert unconditionally.
assert result is False, (
    f"regime_filter returned True but {today_close} <= {sma200}"
)
```

---

_Reviewed: 2026-05-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
