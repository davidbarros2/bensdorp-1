---
phase: 03-data-sources
plan: 02
subsystem: data
tags:
  - data-layer
  - constituents
  - wikipedia
  - slickcharts
  - cache
dependency_graph:
  requires:
    - "Phase 2: db subpackage (schema, audit, engine)"
    - "Phase 3 Plan 01: data/__init__.py subpackage marker, pyproject overrides"
  provides:
    - "bensdorp1.data.constituents: get_constituents, refresh_constituents"
    - "DATA-01 Wikipedia fetch + Slickcharts cross-check"
    - "DATA-02 discrepancy classification (0-3 silent, 4-10 warn, 11+ abort)"
    - "DATA-05 7-day cache TTL with stale-with-warning fallback"
  affects:
    - "Plan 03 (prices.py) — unblocked for Wave 3"
    - "Phase 6 (init command) — calls get_constituents on first run"
    - "Phase 7 (scan command) — calls get_constituents once per scan"
    - "Phase 10 (refresh command) — calls refresh_constituents directly"
tech_stack:
  added: []
  patterns:
    - "DELETE+INSERT atomic replacement in _persist_constituents — transaction-safe cache update"
    - "Symmetric difference (wiki_set ^ slickcharts_set) for DATA-02 discrepancy count"
    - "D-03: refresh returns silently on network failure; get_constituents falls back to stale cache"
    - "Ticker regex _TICKER_RE = r'^[A-Z.\\-\\^]{1,10}$' validated before every DB insert"
    - "Slickcharts table CSS class fallback: class_='table' then first <table> [ASSUMED per RESEARCH Open Q1]"
    - "Row[4] positional access for audit_log.payload in tests (avoids SQLAlchemy Row attr typing)"
key_files:
  created:
    - path: "src/bensdorp1/data/constituents.py"
      lines: 226
      role: "S&P 500 constituent fetcher with 7-day cache — DATA-01, DATA-02, DATA-05"
  modified:
    - path: "tests/test_data_constituents.py"
      lines: 390
      role: "Full test suite replacing Plan 01 scaffold — 14 test functions, 19 total (6 parametrized)"
decisions:
  - "Used Slickcharts CSS class fallback (class_='table' then first <table>) per RESEARCH.md Open Question 1 [ASSUMED] — table class not verifiable offline"
  - "Used row[4] positional access for audit_log.payload in tests — avoids unused-ignore mypy warnings from Row attribute access"
  - "19 tests total (14 plan-specified + 5 from parametrize expansion) — parametrize counts as 1 test function, 6 test cases"
metrics:
  duration: "6m 9s"
  completed_date: "2026-05-23"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
---

# Phase 03 Plan 02: S&P 500 Constituent Fetcher (DATA-01, DATA-02, DATA-05) — Summary

**One-liner:** Wikipedia + Slickcharts constituent scraping with symmetric-difference discrepancy gate and 7-day cache TTL using SQLAlchemy Core DELETE+INSERT.

## What Was Built

Two tasks completed atomically:

**Task 1 — `src/bensdorp1/data/constituents.py` (226 lines):**

- 2 public functions: `get_constituents(engine)`, `refresh_constituents(engine)`
- 8 private helpers:
  - `_validate_ticker(symbol)` — regex guard before every DB insert
  - `_ensure_utc(dt)` — normalizes naive SQLite datetimes to UTC-aware
  - `_classify_discrepancy(diff_count)` — returns "silent"/"warn"/"abort" at 0-3/4-10/11+ bounds
  - `_fetch_wikipedia(client)` — BeautifulSoup + lxml parse of wikitable; drops malformed tickers
  - `_fetch_slickcharts(client)` — Bootstrap table parse with class_ fallback; column 2 = Symbol
  - `_is_cache_stale(engine)` — `func.max(fetched_at)` query with 7-day TTL check
  - `_persist_constituents(engine, data)` — DELETE+INSERT in single transaction
  - `_read_cached_constituents(engine)` — reads current cache rows into dict
- All three audit events: `CONSTITUENTS_UPDATED`, `CONSTITUENTS_DISCREPANCY`, `DATA_FETCH_FAILED`
- Browser User-Agent `"Mozilla/5.0 (compatible; bensdorp1/0.1)"` on all HTTP calls
- Symmetric difference `wiki_set ^ slickcharts_set` drives discrepancy classification per DATA-02
- D-03: never hard-fails — network failures return silently with DATA_FETCH_FAILED audit event

**Task 2 — `tests/test_data_constituents.py` (390 lines, replaces Plan 01 scaffold):**

- 14 test functions (19 test cases including parametrize expansion)
- DATA-01 coverage: `test_fetch_wikipedia_parses_symbols_and_names`, `test_fetch_wikipedia_drops_malformed_tickers`, `test_fetch_wikipedia_raises_when_table_missing`, `test_fetch_slickcharts_parses_symbol_column`
- DATA-02 coverage: `test_classify_discrepancy_bounds` (parametrized at 0/3/4/10/11/500), `test_refresh_silent_when_discrepancy_le_3`, `test_refresh_warn_when_discrepancy_4_to_10`, `test_refresh_abort_when_discrepancy_ge_11`
- DATA-05 coverage: `test_get_constituents_skips_fetch_when_cache_fresh`, `test_get_constituents_refreshes_when_cache_stale`, `test_get_constituents_returns_stale_cache_when_refresh_fails`
- D-03 coverage: `test_refresh_emits_data_fetch_failed_when_wikipedia_unreachable`, `test_refresh_continues_when_slickcharts_unreachable_but_wikipedia_succeeds`
- Security: `test_validate_ticker_accepts_period_form` — BRK.B, ^GSPC accepted; lowercase/space/long/injection rejected

## Test Results

| Suite | Result |
|-------|--------|
| `uv run pytest tests/test_data_constituents.py -x -q` | 19 passed |
| `uv run pytest tests/ -q` (full suite) | 111 passed, 1 skipped |
| `uv run mypy src/` | 0 errors (29 source files) |
| `uv run ruff check src/ tests/` | 0 errors |

## Discrepancy Classification — Verified at Boundaries

| diff_count | Expected | Actual |
|------------|----------|--------|
| 0 | silent | silent |
| 3 | silent | silent |
| 4 | warn | warn |
| 10 | warn | warn |
| 11 | abort | abort |
| 500 | abort | abort |

All 6 boundary values pass via `test_classify_discrepancy_bounds` parametrize.

## Stale-Cache Fallback — Verified

- `test_get_constituents_returns_stale_cache_when_refresh_fails`: Pre-populate 8-day-old cache with 2 rows. Mock `_fetch_wikipedia` to raise HTTPError. Call `get_constituents`. Result contains both stale rows. `audit_log` has 1 DATA_FETCH_FAILED event. No exception raised.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `# type: ignore[union-attr]` from test file**
- **Found during:** Task 2, mypy run
- **Issue:** `row.payload` on SQLAlchemy `Row` returns `Any`, not `Any | None`, so `type: ignore[union-attr]` was flagged as `unused-ignore` by mypy 2.1
- **Fix:** Changed payload access from `row.payload` to `row[4]` (positional column index) to avoid the attribute typing issue entirely — no `type: ignore` needed
- **Files modified:** `tests/test_data_constituents.py`
- **Commit:** d3534d3

**2. [Rule 1 - Bug] Fixed several E501 (line too long) violations in docstrings**
- **Found during:** Task 1 and Task 2, ruff check
- **Issue:** Module docstring and function docstrings exceeded 88-character limit
- **Fix:** Wrapped long docstring lines to fit within 88 chars
- **Files modified:** `src/bensdorp1/data/constituents.py`, `tests/test_data_constituents.py`
- **Commits:** 840d0cd, d3534d3

### Documented Assumptions

**[ASSUMED] Slickcharts table CSS class:** RESEARCH.md Open Question 1 notes that the Slickcharts table CSS class cannot be verified offline. Implementation uses `class_="table"` (Bootstrap class) with fallback to first `<table>` tag per plan instructions. The plan explicitly documents this as `[ASSUMED]`. If Slickcharts changes its HTML structure, `_fetch_slickcharts` will raise `ValueError("Slickcharts ticker table not found")` → DATA_FETCH_FAILED audit event → stale-cache fallback (D-03).

## Known Stubs

None. All functions and tests are fully implemented. The Plan 01 SKIP placeholder in `test_data_constituents.py` is replaced by the full 14-function test suite.

## Threat Surface Scan

New HTTP endpoints introduced:
- `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies` — public read-only Wikipedia page
- `https://www.slickcharts.com/sp500` — public read-only Slickcharts page

These are covered by the threat model in the plan:
- T-03-CONST-01: SQL injection via ticker — mitigated by `_validate_ticker` regex + SQLAlchemy parameterized queries
- T-03-CONST-02: XSS via company_name — mitigated by BeautifulSoup `get_text(strip=True)`
- T-03-CONST-03: DoS via 403/503 — mitigated by `raise_for_status()` + DATA_FETCH_FAILED + stale-cache fallback
- T-03-CONST-04: User-Agent disclosure — accepted (required for Cloudflare bypass per Pitfall 6)
- T-03-CONST-06: Adversarial large table — mitigated by `_validate_ticker` regex length bound + SQLite UNIQUE index

No additional threat surface beyond what was modeled in the plan.

## Self-Check

Files exist:
- [x] `src/bensdorp1/data/constituents.py` (226 lines)
- [x] `tests/test_data_constituents.py` (390 lines, 14 test functions)
- [x] `.planning/phases/03-data-sources/03-02-SUMMARY.md`

Commits:
- [x] `840d0cd` — feat(03-02): implement constituents.py with DATA-01/02/05
- [x] `d3534d3` — feat(03-02): 14-test suite for DATA-01/02/05 constituents module

## Self-Check: PASSED
