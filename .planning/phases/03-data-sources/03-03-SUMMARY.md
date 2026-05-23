---
phase: 03-data-sources
plan: 03
subsystem: data
tags:
  - data-layer
  - prices
  - yfinance
  - retry
  - coverage
dependency_graph:
  requires:
    - "Phase 2: db subpackage (schema price_daily, constituents_cache, audit)"
    - "Phase 3 Plan 01: pyproject.toml mypy overrides for yfinance"
    - "Phase 3 Plan 02: constituents.py (constituents_cache table populated)"
  provides:
    - "bensdorp1.data.prices: update_price_data, check_price_coverage"
    - "DATA-03: yfinance.download always called with auto_adjust=True"
    - "DATA-04: 220-day history via 350 calendar-day default lookback"
    - "DATA-08: period<->hyphen ticker normalization exclusively in prices.py"
    - "DATA-09: 3-retry exponential backoff [1s, 2s, 4s] + DATA_FETCH_FAILED audit"
    - "DATA-10: check_price_coverage returns (covered, total) tuple"
  affects:
    - "Plan 04 (data/__init__.py public API) — unblocked for Wave 4"
    - "Phase 6 (init command) — calls update_price_data to pre-load 220 trading days"
    - "Phase 7 (scan command) — calls update_price_data daily + check_price_coverage before scan"
tech_stack:
  added: []
  patterns:
    - "df.stack(level=1, future_stack=True) — correct MultiIndex flatten for multi-ticker bulk"
    - "JOIN constituents_cache in coverage subquery — ^GSPC excluded from covered count"
    - "BACKOFF_DELAYS literal [1.0, 2.0, 4.0] — not computed inline, patchable in tests"
    - "py.typed marker added to bensdorp1 package — mypy strict works on test files standalone"
key_files:
  created:
    - path: "src/bensdorp1/data/prices.py"
      lines: 275
      role: "yfinance bulk download + per-symbol retry + price_daily persistence + 95% coverage"
    - path: "src/bensdorp1/py.typed"
      lines: 0
      role: "PEP 561 marker enabling mypy strict on test files (Rule 2 addition)"
  modified:
    - path: "tests/test_data_prices.py"
      lines: 400
      role: "Full test suite replacing Plan 01 scaffold — 17 test functions, all passing"
decisions:
  - "check_price_coverage JOINs constituents_cache to exclude ^GSPC from covered count — pure price_daily subquery would count ^GSPC since it is always downloaded (DATA-10 constituent-only requirement)"
  - "Added py.typed to bensdorp1 package — mypy strict emitted import-untyped errors for bensdorp1 subpackages when test files run standalone; py.typed resolves it for the whole project"
  - "BACKOFF_DELAYS kept as literal [1.0, 2.0, 4.0] per plan — not computed as list comprehension — so tests can inspect and tests can patch without recomputing"
metrics:
  duration: "~12m"
  completed_date: "2026-05-23"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 03 Plan 03: yfinance Price Downloader (DATA-03, DATA-04, DATA-08, DATA-09, DATA-10) — Summary

**One-liner:** yfinance bulk+retry price downloader with period/hyphen normalization, ON CONFLICT idempotency, and constituent-aware 95% coverage check using SQLAlchemy Core JOIN.

## What Was Built

Two tasks completed atomically:

**Task 1 — `src/bensdorp1/data/prices.py` (275 lines):**

- 2 public functions: `update_price_data(engine, symbols, start, end)`, `check_price_coverage(engine, required_days)`
- 10 private helpers:
  - `_to_yfinance(symbol)` — period to hyphen (BRK.B -> BRK-B); ^GSPC no-op
  - `_to_db(symbol)` — hyphen to period (BRK-B -> BRK.B); ^GSPC no-op
  - `_ensure_utc(dt)` — normalizes naive SQLite datetimes to UTC-aware
  - `_default_date_range()` — today minus 350 calendar days through today
  - `_download_bulk(tickers, start, end)` — bulk yfinance call with auto_adjust=True; flattens via df.stack(level=1, future_stack=True)
  - `_find_failed_tickers(stacked, expected)` — detects all-NaN Close per ticker + absent tickers
  - `_download_with_retry(ticker, start, end, retries=3)` — single-ticker retry with BACKOFF_DELAYS[:retries]; multi_level_index=False safe for single ticker
  - `_stacked_to_rows(stacked)` — converts (Date, Ticker) MultiIndex rows to dicts with explicit float/int casts
  - `_per_symbol_to_rows(ticker_db, df)` — converts single-ticker flat DataFrame to dicts
  - `_persist_price_rows(engine, rows)` — ON CONFLICT DO NOTHING via sqlite_insert; idempotent
- DATA-06 (split detection) documented as deferred to Phase 11 in module docstring and inline comment
- mypy strict clean (0 errors), ruff clean (0 errors)

**Task 2 — `tests/test_data_prices.py` (400 lines, replaces Plan 01 scaffold):**

- 17 test functions, all passing in 1.07 seconds (time.sleep fully mocked)
- DATA-08: `test_to_yfinance_period_to_hyphen`, `test_to_yfinance_gspc_is_no_op`, `test_to_yfinance_plain_ticker_unchanged`, `test_to_db_hyphen_to_period`, `test_to_db_gspc_is_no_op`, `test_ticker_normalization_period_stored_in_db`, `test_yfinance_called_with_hyphen_form`
- DATA-03: `test_download_called_with_auto_adjust_true`
- D-04: `test_download_includes_gspc`
- DATA-04: `test_220_days_range_default`
- DATA-09: `test_failed_ticker_retried_with_backoff`, `test_failed_ticker_exhausts_retries_emits_audit`
- DATA-10: `test_check_price_coverage_pass`, `test_check_price_coverage_fail`, `test_check_price_coverage_excludes_gspc_from_constituent_total`
- Persistence: `test_price_rows_persisted_in_db`, `test_rerun_idempotent_no_duplicates`

## Test Results

| Suite | Result |
|-------|--------|
| `uv run pytest tests/test_data_prices.py -x -q` | 17 passed, 1.07s |
| `uv run pytest tests/ -q` (full suite) | 128 passed |
| `uv run mypy src/` | 0 errors (30 source files) |
| `uv run mypy tests/test_data_prices.py` | 0 errors |
| `uv run ruff check src/ tests/` | 0 errors |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed check_price_coverage counting ^GSPC in covered count**
- **Found during:** Task 2, test_check_price_coverage_excludes_gspc_from_constituent_total
- **Issue:** The coverage subquery `SELECT symbol FROM price_daily GROUP BY symbol HAVING COUNT(id) >= required_days` counted ALL symbols including ^GSPC. Since ^GSPC is always downloaded, it always had >= required_days rows and was included in covered count.
- **Fix:** Added JOIN to constituents_cache: `SELECT price_daily.symbol FROM price_daily JOIN constituents_cache ON price_daily.symbol == constituents_cache.symbol GROUP BY price_daily.symbol HAVING COUNT(price_daily.id) >= required_days`. This naturally excludes ^GSPC since it is never in constituents_cache.
- **Files modified:** `src/bensdorp1/data/prices.py`
- **Commit:** 87e02da

**2. [Rule 2 - Missing Critical Functionality] Added py.typed marker to bensdorp1 package**
- **Found during:** Task 2, mypy verification on test file
- **Issue:** `uv run mypy tests/test_data_prices.py` emitted `import-untyped` errors for `bensdorp1.data`, `bensdorp1.data.prices`, `bensdorp1.db.schema` — the package lacked a PEP 561 `py.typed` marker. Same issue existed in test_data_constituents.py from Plan 02 (accepted at the time). Fixing it cleanly here affects all test files positively.
- **Fix:** Created `src/bensdorp1/py.typed` (empty file). mypy strict now passes on all test files standalone.
- **Files modified:** `src/bensdorp1/py.typed` (new)
- **Commit:** 87e02da

**3. [Rule 1 - Bug] test_failed_ticker_retried_with_backoff test assertion corrected**
- **Found during:** Task 2, first pytest run
- **Issue:** Test expected `mock_sleep.call_args_list == [call(1.0)]` for "first retry succeeds". But when the first single-ticker attempt succeeds (attempt=0), no sleep is called at all — sleep only occurs between a FAILED attempt and the next attempt. The test was asserting wrong behavior.
- **Fix:** Changed the test to simulate: bulk fails, first single-ticker attempt fails (triggers sleep(1.0)), second single-ticker attempt succeeds. This correctly verifies the backoff sequence with `mock_sleep.call_args_list == [call(1.0)]`.
- **Files modified:** `tests/test_data_prices.py`
- **Commit:** 87e02da

## DATA-06 Deferral

Split detection (DATA-06) is explicitly NOT implemented. Documented in two places:
1. Module docstring line: `DATA-06: Split detection deferred to Phase 11 (Catch-Up Logic).`
2. Inline comment: `# DATA-06: Split detection deferred to Phase 11 (Catch-Up Logic)`

Phase 11 (Catch-Up Logic) owns `split_applied` audit event and share/price adjustment.

## Key Technical Decisions

- **df.stack(level=1, future_stack=True):** Used for multi-ticker bulk download flattening. `multi_level_index=False` does NOT flatten multi-ticker results (RESEARCH Pitfall 3). `multi_level_index=False` is used only in `_download_with_retry` for the single-ticker path (safe there).
- **BACKOFF_DELAYS as literal:** `[1.0, 2.0, 4.0]` kept as a module-level literal constant (not computed inline as `[1.0 * (2**i) for i in range(3)]`) so tests can reference it directly and patches can target the module-level name.
- **JOIN in coverage check:** Ensures ^GSPC (always in price_daily, never in constituents_cache) cannot inflate the covered count. The behavior spec requires constituent-only coverage counting.

## Known Stubs

None. All functions and tests are fully implemented. The Plan 01 SKIP placeholder in `test_data_prices.py` is replaced by the full 17-function test suite.

## Threat Surface Scan

No new network endpoints or auth paths. `prices.py` calls yfinance externally but only in production (all yfinance calls mocked in tests). The threat model in the plan covers:
- T-03-PRC-01 (SQL injection via symbol): mitigated — SQLAlchemy Core parameterized queries throughout
- T-03-PRC-02 (bogus numeric data from yfinance): mitigated — explicit float()/int() casts + pd.notna() guard
- T-03-PRC-04 (adversarial backoff timing): mitigated — BACKOFF_DELAYS literal [1.0, 2.0, 4.0] caps total sleep at 7s per ticker

No additional threat surface beyond what was modeled.

## Self-Check

Files exist:
- [x] `src/bensdorp1/data/prices.py` (275 lines)
- [x] `src/bensdorp1/py.typed` (new, 0 lines)
- [x] `tests/test_data_prices.py` (400 lines, 17 test functions)

Commits:
- [x] `9e8cdb3` — feat(03-03): implement prices.py with DATA-03/04/08/09/10
- [x] `87e02da` — feat(03-03): 17-test suite for DATA-03/04/08/09/10 prices module

## Self-Check: PASSED
