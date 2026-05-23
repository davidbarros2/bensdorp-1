---
phase: 03-data-sources
verified: 2026-05-23T00:00:00Z
status: passed
score: 4/4 roadmap success criteria verified
overrides_applied: 0
deferred:
  - truth: "DATA-06: Split detection and automatic position adjustment"
    addressed_in: "Phase 11"
    evidence: "Phase 11 success criteria item 3: 'Split detection runs on every scan for all held positions; when a split is detected, shares, entry price, and stop levels are adjusted and a split_applied audit event is written'"
---

# Phase 3: Data Sources Verification Report

**Phase Goal:** Implement the data-sources layer — S&P 500 constituent fetcher, price downloader, NYSE calendar, and public API surface.
**Verified:** 2026-05-23
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Constituents fetched from Wikipedia + Slickcharts; discrepancy rules (0-3 silent, 4-10 warn, 11+ abort) enforced and logged | VERIFIED | `constituents.py` lines 41-51 implement `_classify_discrepancy`; symmetric diff `wiki_set ^ slickcharts_set` on line 185; all 3 audit events emitted; 8 tests covering silent/warn/abort branches pass |
| 2 | yfinance returns 220 trading days of adjusted-close history; all arithmetic uses NYSE trading days exclusively | VERIFIED | `prices.py`: `DEFAULT_LOOKBACK_DAYS=350`, `DEFAULT_REQUIRED_TRADING_DAYS=220`, `auto_adjust=True` in both `_download_bulk` and `_download_with_retry`; `calendar.py` uses `pandas_market_calendars` NYSE exclusively; 9 calendar tests + 17 prices tests pass |
| 3 | Tickers stored in period form (`BRK.B`); converted to hyphen form (`BRK-B`) only at yfinance call site; sole normalization location | VERIFIED | `prices.py` `_to_yfinance`/`_to_db` are the exclusive normalization site; `test_ticker_normalization_period_stored_in_db` and `test_yfinance_called_with_hyphen_form` pass |
| 4 | Failed download retries with backoff (1s, 2s, 4s); fewer than 95% constituents with price data aborts scan | VERIFIED | `prices.py` `BACKOFF_DELAYS: list[float] = [1.0, 2.0, 4.0]`; `check_price_coverage` returns `(covered, total)` tuple; `test_failed_ticker_retried_with_backoff`, `test_failed_ticker_exhausts_retries_emits_audit`, `test_check_price_coverage_pass`, `test_check_price_coverage_fail` all pass |

**Score:** 4/4 roadmap success criteria verified

### Deferred Items

DATA-06 (split detection and automatic position adjustment) is explicitly deferred. This is documented in 4 independent locations: `data/__init__.py` module docstring (2 lines), `prices.py` module docstring + inline comment (2 lines), Plan 04 must_haves, and Plan 04 threat model T-03-API-04. Phase 11 (Catch-Up Logic) owns this requirement per ROADMAP.md.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | DATA-06: Split detection, position adjustment on split events | Phase 11 | Phase 11 SC3: "Split detection runs on every scan for held positions; split_applied audit event is written" |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/bensdorp1/data/__init__.py` | Public API re-export, 7 symbols, sorted `__all__` | VERIFIED | 19 lines; exports all 7 symbols; `__all__` sorted alphabetically; DATA-06 deferral in docstring |
| `src/bensdorp1/data/calendar.py` | `get_trading_days`, `is_trading_day`, `n_trading_days_ago` | VERIFIED | 54 lines; all 3 functions present; `_NYSE = mcal.get_calendar("NYSE")` singleton; no pytz |
| `src/bensdorp1/data/constituents.py` | `get_constituents`, `refresh_constituents`, 8 private helpers | VERIFIED | 226 lines (>120 min); both public functions; all 8 private helpers; all 3 audit event types referenced |
| `src/bensdorp1/data/prices.py` | `update_price_data`, `check_price_coverage`, 10 private helpers | VERIFIED | 282 lines (>150 min); both public functions; all 10 private helpers present |
| `tests/test_data_calendar.py` | 9+ tests covering DATA-07 | VERIFIED | 71 lines; 9 test functions; all pass |
| `tests/test_data_constituents.py` | 14+ tests covering DATA-01/02/05 | VERIFIED | 390 lines (>80 min); 14 test functions (19 cases with parametrize); all pass |
| `tests/test_data_prices.py` | 17+ tests covering DATA-03/04/08/09/10 | VERIFIED | 400 lines (>120 min); 17 test functions; all pass in 1.74s (sleep mocked) |
| `pyproject.toml` | lxml-stubs dev dep + mypy overrides for yfinance and pandas_market_calendars | VERIFIED | `lxml-stubs>=0.5.1` present; `pandas-stubs` present (deviation — needed for pandas 3.0.3); both mypy overrides confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `data/__init__.py` | `data/calendar.py` | `from bensdorp1.data.calendar import get_trading_days, is_trading_day, n_trading_days_ago` | WIRED | Exact import line confirmed in file; all 3 symbols in `__all__` |
| `data/__init__.py` | `data/constituents.py` | `from bensdorp1.data.constituents import get_constituents, refresh_constituents` | WIRED | Exact import line confirmed; both symbols in `__all__` |
| `data/__init__.py` | `data/prices.py` | `from bensdorp1.data.prices import check_price_coverage, update_price_data` | WIRED | Exact import line confirmed; both symbols in `__all__` |
| `calendar.py` | `pandas_market_calendars` | `_NYSE = mcal.get_calendar("NYSE")` module-level singleton | WIRED | Line 14: `_NYSE = mcal.get_calendar("NYSE")` confirmed |
| `constituents.py` | `db/schema.py:constituents_cache` | `insert(constituents_cache)`, `select(constituents_cache)`, `constituents_cache.delete()` | WIRED | DELETE on line 133, INSERT on line 135; SELECT on line 143 |
| `constituents.py` | `db/audit.py:log_event` | `log_event(engine, AuditEventType.CONSTITUENTS_UPDATED|CONSTITUENTS_DISCREPANCY|DATA_FETCH_FAILED, ...)` | WIRED | All 3 event types used; confirmed in source lines 163-168, 189-197, 207-214 |
| `prices.py` | `db/schema.py:price_daily` | `sqlite_insert(price_daily).values(rows).on_conflict_do_nothing(index_elements=["symbol","trade_date"])` | WIRED | Lines 202-204 confirmed |
| `prices.py` | `yfinance` | `yf.download(..., auto_adjust=True, ...)` — both bulk and retry call sites | WIRED | `auto_adjust=True` appears twice: line 77 (`_download_bulk`) and line 121 (`_download_with_retry`) |
| `tests/test_data_constituents.py` | `unittest.mock.patch` | `patch("httpx.Client.get")` and related | WIRED | File imports `MagicMock, patch`; no real HTTP calls |
| `tests/test_data_prices.py` | `unittest.mock.patch("yfinance.download")` + `patch("bensdorp1.data.prices.time.sleep")` | Mock prevents network/sleep | WIRED | All yfinance calls mocked; 17 tests run in 1.74s (sleep not real) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `constituents.py:get_constituents` | return dict | `_read_cached_constituents` → SQLAlchemy `select(constituents_cache)` | Yes — DB rows from prior `_persist_constituents` | FLOWING |
| `constituents.py:refresh_constituents` | `wiki_data` | `_fetch_wikipedia(client)` → httpx + BeautifulSoup parse | Yes — live HTML scrape | FLOWING |
| `prices.py:update_price_data` | `rows` | `_download_bulk` → `yf.download` → `df.stack` → `_stacked_to_rows` | Yes — yfinance returns real OHLCV DataFrames | FLOWING |
| `prices.py:check_price_coverage` | `(covered, total)` | Two SQLAlchemy Core queries with JOIN on `constituents_cache` | Yes — DB aggregate queries | FLOWING |
| `calendar.py:get_trading_days` | `pd.DatetimeIndex` | `_NYSE.valid_days(...)` from `pandas_market_calendars` | Yes — internal NYSE holiday calendar (no network) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 7 public symbols importable | `uv run python -c "from bensdorp1.data import ...; assert len(__all__)==7"` | Prints "public API ok, __all__: [...]" | PASS |
| All Phase 3 tests pass | `uv run pytest tests/test_data_calendar.py tests/test_data_constituents.py tests/test_data_prices.py -q` | 45 passed in 1.74s | PASS |
| Full test suite (no regressions) | `uv run pytest tests/ -q` | 128 passed in 3.30s | PASS |
| mypy strict full src/ | `uv run mypy src/` | `Success: no issues found in 30 source files` | PASS |
| ruff full src/ + tests/ | `uv run ruff check src/ tests/` | `All checks passed!` | PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files exist in this project; no probes declared in any plan.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DATA-01 | 03-02 | S&P 500 constituents from Wikipedia + Slickcharts | SATISFIED | `constituents.py` `_fetch_wikipedia` + `_fetch_slickcharts`; 4 tests covering fetch branches |
| DATA-02 | 03-02 | 0-3 silent, 4-10 warn, 11+ abort discrepancy | SATISFIED | `_classify_discrepancy` with exact bounds; `test_classify_discrepancy_bounds` parametrized at 0/3/4/10/11/500 |
| DATA-03 | 03-03 | `auto_adjust=True` in all yfinance calls | SATISFIED | `auto_adjust=True` in both `_download_bulk` (line 77) and `_download_with_retry` (line 121) |
| DATA-04 | 03-03 | 220 trading days history | SATISFIED | `DEFAULT_LOOKBACK_DAYS=350` calendar days covers 220+ trading days; `test_220_days_range_default` passes |
| DATA-05 | 03-02 | 7-day cache TTL | SATISFIED | `CACHE_TTL_DAYS=7`; `_is_cache_stale` uses `timedelta(days=CACHE_TTL_DAYS)`; fresh/stale tests pass |
| DATA-06 | 03-04 (deferred) | Split detection and position adjustment | DEFERRED | Explicitly deferred to Phase 11; documented in `__init__.py` and `prices.py`; Phase 11 SC3 covers it |
| DATA-07 | 03-01 | NYSE calendar for all trading-day arithmetic | SATISFIED | `calendar.py` uses `pandas_market_calendars` exclusively; `_NYSE` singleton; 9 tests pass |
| DATA-08 | 03-03 | Period form in DB; hyphen form at yfinance call site only | SATISFIED | `_to_yfinance`/`_to_db` in `prices.py` exclusively; `test_yfinance_called_with_hyphen_form` + `test_ticker_normalization_period_stored_in_db` pass |
| DATA-09 | 03-03 | 3 retries at 1s, 2s, 4s backoff | SATISFIED | `BACKOFF_DELAYS: list[float] = [1.0, 2.0, 4.0]`; retry loop uses `BACKOFF_DELAYS[:retries]`; retry + exhaustion tests pass |
| DATA-10 | 03-03 | Abort scan if <95% constituents have price data | SATISFIED | `check_price_coverage` returns `(covered, total)`; coverage check excludes `^GSPC` via JOIN; pass/fail/GSPC-excluded tests all pass |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None | — | — | No stub placeholders, TBD/FIXME/XXX markers, hardcoded empty returns, or placeholder stubs found in any Phase 3 source file. Test scaffolds from Plan 01 were fully replaced by Plans 02/03. |

Scan notes:
- No `TBD`, `FIXME`, or `XXX` markers found in any data-layer source file
- No `return null`, `return {}`, or `return []` stubs in public function bodies
- `data/__init__.py` placeholder from Plan 01 was correctly replaced by Plan 04
- `test_data_constituents.py` and `test_data_prices.py` Plan 01 scaffolds were correctly overwritten by Plan 02 and Plan 03
- One deviation from Plan 01: `pandas-stubs` was added (not listed in plan) — required because pandas 3.0.3 lacks `py.typed`; this is a necessary addition, not a stub

### Human Verification Required

None. All must-haves are verifiable programmatically. No visual UI, real-time behavior, or external service integration requires human judgment at this phase (yfinance/Wikipedia/Slickcharts calls are all mocked in tests).

### Gaps Summary

No gaps. All 4 roadmap success criteria are verified against the actual codebase:

1. Constituent fetching with discrepancy classification — implementation confirmed substantive and wired.
2. 220-day adjusted-close price history with NYSE calendar — implementation confirmed substantive and wired.
3. Sole-site ticker normalization period/hyphen — implementation confirmed exclusively in `prices.py`.
4. Retry backoff and 95% coverage gate — implementation confirmed with correct constant values and tuple return.

DATA-06 is a known deferred item, not a gap. It is explicitly assigned to Phase 11 in ROADMAP.md and documented in 4 independent locations in source and planning artifacts.

---

_Verified: 2026-05-23_
_Verifier: Claude (gsd-verifier)_
