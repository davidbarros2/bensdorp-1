---
phase: 03-data-sources
plan: "04"
subsystem: data
tags:
  - data-layer
  - public-api
  - phase-gate
dependency_graph:
  requires:
    - 03-01
    - 03-02
    - 03-03
  provides:
    - bensdorp1.data public API surface
  affects:
    - Phase 06 (init command)
    - Phase 07 (scan command)
    - Phase 10 (refresh command)
tech_stack:
  added: []
  patterns:
    - Re-export __init__.py mirroring db/__init__.py convention
    - Sorted-alphabetic __all__ list
key_files:
  created: []
  modified:
    - src/bensdorp1/data/__init__.py
decisions:
  - "data/__init__.py uses 3-import-line structure (one per submodule) alphabetically ordered — mirrors db/__init__.py exactly"
  - "DATA-06 deferral documented in __init__.py module docstring and prices.py docstring (2 independent records in source); also in plan must_haves and threat model (4 total records)"
metrics:
  duration: "~3 minutes"
  completed: "2026-05-23"
  tasks: 2
  files_modified: 1
---

# Phase 03 Plan 04: Finalize data public API surface Summary

**One-liner:** Replaced Plan 01 placeholder with canonical 7-symbol re-export `__init__.py`; Phase 3 integration gate is green (128 tests passed, mypy strict on 30 files, ruff clean).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Finalize data/__init__.py public API surface | cb1239f | src/bensdorp1/data/__init__.py |
| 2 | Full-repo integration verification (Phase 3 gate) | (no-op — verification only) | .planning/phases/03-data-sources/03-04-pytest-output.log |

## Phase 3 Requirement Coverage

| Req | Status | Plan | Module |
|-----|--------|------|--------|
| DATA-01 | Implemented | 03-02 | constituents.py |
| DATA-02 | Implemented | 03-02 | constituents.py |
| DATA-03 | Implemented | 03-03 | prices.py |
| DATA-04 | Implemented | 03-03 | prices.py |
| DATA-05 | Implemented | 03-02 | constituents.py |
| DATA-06 | DEFERRED | Phase 11 | (Catch-Up Logic) |
| DATA-07 | Implemented | 03-01 | calendar.py |
| DATA-08 | Implemented | 03-03 | prices.py |
| DATA-09 | Implemented | 03-03 | prices.py |
| DATA-10 | Implemented | 03-03 | prices.py |

## Integration Verification Results

- **pytest:** PASS — 128 passed, 0 failed, 0 skipped, 0 errors; runtime 3.50s
  - Phase 1+2 baseline tests: no regression
  - calendar tests: 9 passed
  - constituents tests: 15 passed
  - prices tests: 17 passed
- **mypy strict:** PASS — `Success: no issues found in 30 source files`
- **ruff:** PASS — `All checks passed!` across src/ and tests/
- **Public API import smoke test:** PASS — all 7 imports ok
- **pytest log:** 139 lines at `.planning/phases/03-data-sources/03-04-pytest-output.log`
- **DATA-06 deferral:** CONFIRMED — 4 matches across `src/bensdorp1/data/__init__.py` (2 lines) and `src/bensdorp1/data/prices.py` (2 lines)

## Phase 3 Acceptance (from ROADMAP.md §Phase 3)

1. "Constituents are fetched from Wikipedia and cross-checked against Slickcharts; discrepancy rules (0-3 silent, 4-10 warn, 11+ abort buy candidates) are enforced and logged" — IMPLEMENTED via Plan 02; verified by `test_refresh_silent_when_discrepancy_le_3`, `test_refresh_warn_when_discrepancy_4_to_10`, `test_refresh_abort_when_discrepancy_ge_11`.

2. "yfinance returns 220 trading days of adjusted-close price history for a constituent symbol; all arithmetic uses NYSE trading days exclusively" — IMPLEMENTED via Plans 01 and 03; verified by `test_220_days_range_default` and `test_n_trading_days_ago_220_does_not_raise`.

3. "Tickers are stored in period form (BRK.B) and converted to hyphen form (BRK-B) only at the yfinance call site" — IMPLEMENTED via Plan 03; verified by `test_ticker_normalization_period_stored_in_db` and `test_yfinance_called_with_hyphen_form`.

4. "A failed download retries with exponential backoff (1s, 2s, 4s); if fewer than 95% of constituents have price data, the scan is aborted" — IMPLEMENTED via Plan 03; verified by `test_failed_ticker_retried_with_backoff`, `test_failed_ticker_exhausts_retries_emits_audit`, `test_check_price_coverage_pass`, `test_check_price_coverage_fail`.

## DATA-06 Deferral Record

Split detection and automatic position adjustment (DATA-06) is OUT OF SCOPE for Phase 3. It is owned by Phase 11 (Catch-Up Logic). This deferral is documented in:
1. `src/bensdorp1/data/__init__.py` module docstring (2 lines)
2. `src/bensdorp1/data/prices.py` module docstring + inline comment (2 lines)
3. This plan's `must_haves` section
4. This plan's threat model (T-03-API-04)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — no placeholder data or hardcoded empty values in files modified by this plan.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The `data/__init__.py` is a pure re-export shim with no I/O surface.

## Next Steps

- Run `/gsd-verify-work 03` to invoke the Phase 3 checker.
- Phase 4 (Strategy Logic) is unblocked and depends on Phase 3 outputs (price_daily + constituents_cache populated by Phase 6 init).

## Self-Check: PASSED

- `src/bensdorp1/data/__init__.py` exists with 19 lines (>= 13 required)
- Commit `cb1239f` exists in git log
- pytest log exists at `.planning/phases/03-data-sources/03-04-pytest-output.log` (139 lines)
- All 7 public symbols importable from `bensdorp1.data`
- `__all__` sorted alphabetically with exactly 7 entries
- DATA-06 deferral confirmed in 4 matches across 2 source files
