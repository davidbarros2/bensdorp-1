---
phase: 03-data-sources
reviewed: 2026-05-23T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - pyproject.toml
  - src/bensdorp1/data/__init__.py
  - src/bensdorp1/data/calendar.py
  - src/bensdorp1/data/constituents.py
  - src/bensdorp1/data/prices.py
  - tests/test_data_calendar.py
  - tests/test_data_constituents.py
  - tests/test_data_prices.py
findings:
  critical: 2
  warning: 3
  info: 3
  total: 8
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

The data-sources layer is structurally sound. The calendar wrappers, constituent-fetching pipeline, and price download machinery follow the architecture correctly, and the test suite covers the major paths including retry backoff, cache TTL, discrepancy classification, and coverage gating.

Two blockers were found: one is a genuine runtime crash path (AttributeError in `_fetch_wikipedia` when a tbody element is absent), and one is a behavioral divergence from the DATA-09 spec (the 4s backoff delay constant is declared but never applied). Three warnings address silent input-discarding behavior, a latent KeyError in bulk download column selection, and unhandled DB errors that bypass the D-03 "never hard-fails" invariant. Three info items cover the misleading constant, overly broad ticker regex, and a test coverage gap on the "abort" semantic.

---

## Critical Issues

### CR-01: `_fetch_wikipedia` crashes with AttributeError when `<tbody>` is absent

**File:** `src/bensdorp1/data/constituents.py:67`
**Issue:** `table.find("tbody")` returns `None` when BeautifulSoup/lxml does not find a `<tbody>` element inside the wikitable. The subsequent `.find_all("tr")` call is made directly on that `None`, raising `AttributeError: 'NoneType' object has no attribute 'find_all'`. The `# type: ignore[union-attr]` comment acknowledges the mypy diagnostic but does not prevent the runtime crash.

By contrast, `_fetch_slickcharts` (lines 93-94) correctly guards against this:
```python
tbody = table.find("tbody")
rows = tbody.find_all("tr") if tbody is not None else []
```

The crash is unhandled and propagates out of `_fetch_wikipedia` as an `AttributeError` rather than the documented `ValueError`. Because `refresh_constituents` only catches `(httpx.HTTPError, ValueError)` at line 163, an `AttributeError` would escape those guards, propagate through `get_constituents`, and crash the caller — breaking the D-03 "never hard-fails" invariant.

**Fix:** Apply the same guard used in `_fetch_slickcharts`:
```python
# Before (line 67):
for row in table.find("tbody").find_all("tr"):  # type: ignore[union-attr]

# After:
tbody = table.find("tbody")
rows = tbody.find_all("tr") if tbody is not None else []
for row in rows:
```

Alternatively, if an empty tbody is considered a malformed page, raise `ValueError` explicitly:
```python
tbody = table.find("tbody")
if tbody is None:
    raise ValueError("Wikipedia S&P 500 wikitable has no tbody")
for row in tbody.find_all("tr"):
```

The second form is preferred: it keeps the error type consistent with what `refresh_constituents` catches, and makes the failure path auditable.

---

### CR-02: Third backoff delay (4s) is dead code; DATA-09 retry spec is not fully implemented

**File:** `src/bensdorp1/data/prices.py:36` and `src/bensdorp1/data/prices.py:117-131`
**Issue:** `BACKOFF_DELAYS: list[float] = [1.0, 2.0, 4.0]` declares three delay values. The module docstring and DATA-09 spec both say "delays 1s, 2s, 4s". However, `_download_with_retry` only ever applies the first two:

```python
delays = BACKOFF_DELAYS[:retries]          # [1.0, 2.0, 4.0] for retries=3
for attempt, delay in enumerate(delays):
    df = yf.download(...)
    if not df.empty and not df["Close"].isna().all():
        return result
    if attempt < len(delays) - 1:          # True for attempt 0, 1; False for attempt 2
        time.sleep(delay)                  # sleeps 1.0 then 2.0; 4.0 is never reached
return pd.DataFrame()
```

After three failures the function sleeps 1s then 2s — the 4s delay in the constant is dead. The test `test_failed_ticker_exhausts_retries_emits_audit` confirms this: `assert mock_sleep.call_args_list == [call(1.0), call(2.0)]`. The constant `BACKOFF_DELAYS` is actively misleading to future maintainers and auditors who read "delays 1s, 2s, 4s" and expect three sleeps.

The root cause is that the loop sleeps BEFORE moving to the next attempt (using the current attempt's delay), so the last delay is always skipped. This is a correct "sleep between attempts, not after the last" pattern — but then the constant should only contain two values, not three.

**Fix (option A — trim the constant to match actual behavior):**
```python
BACKOFF_DELAYS: list[float] = [1.0, 2.0]  # sleep between attempt 0→1, 1→2
```
Update DATA-09 docstring accordingly: "delays 1s, 2s between attempts; 3 total attempts."

**Fix (option B — apply all three delays, one after each failed attempt including the last):**
```python
for attempt, delay in enumerate(delays):
    df = yf.download(...)
    if not df.empty and not df["Close"].isna().all():
        return result
    time.sleep(delay)   # sleep after every failure, including the last
return pd.DataFrame()
```
This matches the literal "delays 1s, 2s, 4s" spec but sleeps unnecessarily after the final failure. Option A is cleaner.

---

## Warnings

### WR-01: `update_price_data` silently discards a caller-supplied `start` when `end` is omitted

**File:** `src/bensdorp1/data/prices.py:222-223`
**Issue:** The function signature is `update_price_data(engine, symbols, start=None, end=None)`. The guard is:
```python
if start is None or end is None:
    start, end = _default_date_range()
```
If a caller provides `start` but not `end`, the supplied `start` is silently discarded and both values default. No exception, no warning — the caller's intent is quietly ignored. A future call from `commands/init.py` or `commands/scan.py` that passes only `start` will get the wrong date range with no indication of the problem.

**Fix:** Either require both or neither, or use the provided boundary when only one is supplied:
```python
if start is None and end is None:
    start, end = _default_date_range()
elif start is None or end is None:
    raise ValueError(
        "update_price_data requires both start and end, or neither."
    )
```

---

### WR-02: `_download_bulk` raises `KeyError` if yfinance omits the "Volume" column

**File:** `src/bensdorp1/data/prices.py:84`
**Issue:** After stacking, the function returns `stacked[["Close", "Volume"]]`. If yfinance's response does not include a "Volume" field — possible for certain index instruments or after a library API change — this raises `KeyError: "['Volume'] not in index"`. The per-row guard in `_stacked_to_rows` (line 159) that handles NaN Volume never executes because the column selection fails first. `^GSPC` historically returns volume data, but this is a fragility that would produce an unhandled exception from `update_price_data`.

**Fix:** Check column presence before slicing:
```python
available = [c for c in ["Close", "Volume"] if c in stacked.columns]
if "Close" not in available:
    return pd.DataFrame()
return stacked[available]
```
And update `_stacked_to_rows` to guard for a missing "Volume" key (it already handles NaN volume via `pd.notna`, but should also handle the key-absent case).

---

### WR-03: DB errors in `_persist_constituents` and `_persist_price_rows` bypass D-03

**File:** `src/bensdorp1/data/constituents.py:122-136`, `src/bensdorp1/data/prices.py:193-206`
**Issue:** Both `refresh_constituents` (line 204) and `update_price_data` (line 249) call their persistence helpers without any exception handling. The D-03 invariant ("Never hard-fails: on network errors, emits DATA_FETCH_FAILED and returns") is only enforced for `httpx.HTTPError` and `ValueError`. A SQLite `OperationalError` (disk full, DB locked by another process) propagating from `_persist_constituents` or `_persist_price_rows` would bypass D-03 and crash the calling command.

This is particularly relevant for `get_constituents`, which calls `refresh_constituents` directly:
```python
def get_constituents(engine):
    if _is_cache_stale(engine):
        refresh_constituents(engine)   # DB error propagates to caller
    return _read_cached_constituents(engine)
```

**Fix:** Wrap persistence calls in a try/except and emit `DATA_FETCH_FAILED`:
```python
# In refresh_constituents, around line 204:
try:
    _persist_constituents(engine, wiki_data)
except Exception as exc:
    log_event(
        engine,
        AuditEventType.DATA_FETCH_FAILED,
        payload={"source": "persist_constituents", "error": str(exc)},
    )
    return
```
Apply the same pattern in `update_price_data` around `_persist_price_rows`.

---

## Info

### IN-01: `BACKOFF_DELAYS` constant name and value imply behavior that does not occur

**File:** `src/bensdorp1/data/prices.py:36`
**Issue:** Even if CR-02 is resolved by trimming the constant, the name `BACKOFF_DELAYS` does not distinguish whether these are "delays before each retry" or "delays after each failure." A module-level comment clarifying the semantics would prevent future regressions.

**Fix:** Add an inline comment:
```python
# Sleep durations between successive attempts: applied BEFORE attempts 2 and 3.
# A 3-attempt retry loop consumes len(BACKOFF_DELAYS) = N-1 values when N=retries.
BACKOFF_DELAYS: list[float] = [1.0, 2.0]
```

---

### IN-02: Ticker regex `_TICKER_RE` is broader than real S&P 500 ticker patterns

**File:** `src/bensdorp1/data/constituents.py:28`
**Issue:** `_TICKER_RE = re.compile(r"^[A-Z.\-\^]{1,10}$")` accepts strings composed entirely of hyphens, dots, or carets (e.g., `"----"`, `"...."`). While no S&P 500 ticker looks like this, the regex passes silently for degenerate strings scraped from a malformed or adversarial page, and such strings would be stored in `constituents_cache` and passed to yfinance without further validation.

**Fix:** A more precise pattern that matches the actual S&P 500 ticker structure:
```python
# Matches: AAPL, BRK.B, BF.B, ^GSPC, BRK-B
_TICKER_RE = re.compile(r"^\^?[A-Z]{1,5}([.\-][A-Z]{1,5})?$")
```
This requires at least one letter block, limits the separator (`.` or `-`) to a single occurrence, and prevents all-punctuation strings.

---

### IN-03: "abort" discrepancy severity is audited but its enforcement is untested

**File:** `tests/test_data_constituents.py:198-217`
**Issue:** `test_refresh_abort_when_discrepancy_ge_11` verifies that a `CONSTITUENTS_DISCREPANCY` event with `severity=abort` is emitted, but does not verify the downstream behavior: the audit log contains `severity=abort`, but `refresh_constituents` continues to persist and emit `CONSTITUENTS_UPDATED`. No test verifies that a caller reading `severity=abort` from the audit log would refuse to proceed with a scan. The "abort" label is semantically important but its enforcement point is entirely untested.

**Fix:** Add a test (in the future scan-command phase) that calls `get_constituents`, reads the most recent `CONSTITUENTS_DISCREPANCY` event, finds `severity=abort`, and asserts that the scan command refuses to produce buy candidates. Alternatively, add a helper function `get_discrepancy_severity(engine) -> str | None` to `constituents.py` so the abort check has a clear, testable surface.

---

_Reviewed: 2026-05-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
