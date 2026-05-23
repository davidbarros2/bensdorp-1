---
status: complete
phase: 03-data-sources
source: 03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md
started: 2026-05-23T00:00:00Z
updated: 2026-05-23T12:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Full test suite passes clean
expected: Run `uv run pytest tests/ -q` — see 128 passed, 0 failed, 0 errors in under 5s. No regressions in Phase 1 or Phase 2 baseline tests.
result: pass
note: "1 failure found (WR-04) and fixed inline — retry loop made 2 attempts not 3; audit payload recorded 2 not 3. Fixed in commit 98bf75e."

### 2. Public API: all 7 symbols importable
expected: Run `uv run python -c "from bensdorp1.data import get_trading_days, is_trading_day, n_trading_days_ago, get_constituents, refresh_constituents, update_price_data, check_price_coverage; print('ok')"` — prints "ok" with no ImportError or AttributeError.
result: pass

### 3. Calendar: trading day detection
expected: Run `uv run python -c "from bensdorp1.data import is_trading_day; from datetime import date; print(is_trading_day(date(2024,1,1)), is_trading_day(date(2024,1,2)), is_trading_day(date(2024,1,6)))"` — should print "False True False" (Jan 1 = New Year's Day holiday, Jan 2 = first 2024 trading day, Jan 6 = Saturday).
result: pass

### 4. Calendar: n_trading_days_ago returns prior day
expected: Run `uv run python -c "from bensdorp1.data import n_trading_days_ago; from datetime import date; d = n_trading_days_ago(1, reference=date(2024,1,3)); print(d)"` — should print 2024-01-02 (the trading day immediately before Jan 3, 2024). n=1 must never return the reference date itself.
result: pass

### 5. Discrepancy gate boundaries work correctly
expected: Run `uv run python -c "from bensdorp1.data.constituents import _classify_discrepancy; print(_classify_discrepancy(3), _classify_discrepancy(4), _classify_discrepancy(10), _classify_discrepancy(11))"` — should print "silent warn warn abort". Boundaries: 0-3=silent, 4-10=warn, 11+=abort.
result: pass

### 6. Ticker normalization is correctly isolated
expected: Run `uv run python -c "from bensdorp1.data.prices import _to_yfinance, _to_db; print(_to_yfinance('BRK.B'), _to_db('BRK-B'), _to_yfinance('^GSPC'), _to_db('^GSPC'))"` — should print "BRK-B BRK.B ^GSPC ^GSPC". Period->hyphen for yfinance call site; hyphen->period for DB storage; ^GSPC unchanged in both directions.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "DATA-09: _download_with_retry makes exactly 3 attempts; audit payload records retries=3"
  status: fixed
  reason: "Loop iterated over BACKOFF_DELAYS (2 elements) instead of range(retries); audit recorded len(BACKOFF_DELAYS)=2"
  severity: major
  test: 1
  root_cause: "Loop used `for attempt, delay in enumerate(delays)` — only 2 iterations. Audit payload used len(BACKOFF_DELAYS) instead of retries."
  fix: "Changed loop to `for attempt in range(retries)`, sleep to BACKOFF_DELAYS[attempt], audit to retries=3. Removed 2 stale type: ignore comments. Commit 98bf75e."
