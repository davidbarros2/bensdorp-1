---
phase: 04-strategy-logic
plan: "01"
subsystem: strategy/screening
tags: [python, pandas, mypy-strict, hypothesis, pure-functions, screening]
dependency_graph:
  requires: []
  provides:
    - bensdorp1.strategy.screening (Candidate, regime_filter, liquidity_filter, momentum_filter, rank_candidates)
    - bensdorp1.strategy (re-export public API via __init__.py)
  affects:
    - Phase 7 (scan command) — consumes rank_candidates output
    - Plan 04-02 — positions.py exports added to same __init__.py
tech_stack:
  added: []
  patterns:
    - from __future__ import annotations for pd.Series[float] runtime compatibility
    - TypedDict for mypy-strict-clean heterogeneous record type (Candidate)
    - math.floor for financial position sizing (not int truncation)
    - Hypothesis st.lists + st.from_regex for property-based max-10 invariant
key_files:
  created:
    - src/bensdorp1/strategy/__init__.py
    - src/bensdorp1/strategy/screening.py
    - tests/test_strategy/__init__.py
    - tests/test_strategy/test_screening.py
  modified: []
decisions:
  - "Added from __future__ import annotations to screening.py — pd.Series[float] is not subscriptable at runtime in pandas 3.0.3; __future__ annotations makes all annotations lazy strings, preserving mypy strict compliance"
  - "Fixed volume list length in Hypothesis test — close=200 rows, volume=200 rows (not 221 as in research example which was for a different context)"
metrics:
  duration: "~4m 30s"
  completed: "2026-05-23"
  tasks: 2
  files: 4
---

# Phase 4 Plan 01: Strategy Screening Subpackage Summary

Pure filter math subpackage with four screening functions (regime_filter, liquidity_filter, momentum_filter, rank_candidates) plus Candidate TypedDict — 100% line coverage, mypy strict clean, ruff clean.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create strategy/ subpackage — screening.py + __init__.py | 327a0fc | src/bensdorp1/strategy/__init__.py, src/bensdorp1/strategy/screening.py |
| 2 | Create tests/test_strategy/ — test_screening.py with full unit + Hypothesis coverage | de4756c | tests/test_strategy/__init__.py, tests/test_strategy/test_screening.py |

## What Was Built

**src/bensdorp1/strategy/screening.py** — Pure filter math with four functions:
- `regime_filter(spx_closes: pd.Series[float]) -> bool` — True when SPX close > SMA 200 (STRAT-01)
- `liquidity_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]` — top 25% by 20-day avg volume, T-1 through T-20 (STRAT-02)
- `momentum_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]` — close today > close 200 rows ago (STRAT-03)
- `rank_candidates(price_dfs: dict[str, pd.DataFrame], available_cash: float) -> list[Candidate]` — descending ROC 200, max 10 (STRAT-04/05)

**src/bensdorp1/strategy/__init__.py** — Re-exports Candidate + 4 functions via `__all__` (mirrors db/ pattern).

**tests/test_strategy/test_screening.py** — 19 tests: 17 unit tests covering all branches + 2 Hypothesis property invariants.

## Verification Results

| Gate | Result |
|------|--------|
| `uv run pytest tests/test_strategy/ -x -q` | 19 passed |
| `uv run mypy src/bensdorp1/strategy/screening.py src/bensdorp1/strategy/__init__.py` | Success: no issues found |
| `uv run ruff check src/bensdorp1/strategy/` | All checks passed |
| `coverage report --include="src/bensdorp1/strategy/screening.py"` | 100% (50 stmts, 0 missed) |
| `uv run mypy tests/test_strategy/test_screening.py` | Success: no issues found |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pd.Series[float] not subscriptable at runtime**
- **Found during:** Task 2 (first pytest run)
- **Issue:** pandas 3.0.3 `pd.Series` is not subscriptable at runtime — `pd.Series[float]` raises `TypeError: type 'Series' is not subscriptable` during module import. The research confirmed it works for mypy but did not note the runtime incompatibility.
- **Fix:** Added `from __future__ import annotations` to screening.py. This makes all annotations lazy string literals at runtime, preserving mypy strict compliance while eliminating the runtime error.
- **Files modified:** `src/bensdorp1/strategy/screening.py`
- **Commit:** de4756c (included in Task 2 commit as part of the task-related fix)

**2. [Rule 1 - Bug] Hypothesis test DataFrame column length mismatch**
- **Found during:** Task 2 (Hypothesis invariant 3 execution)
- **Issue:** RESEARCH.md example used `"volume": [1_000_000] * 221` but `"close": [100.0 + i for i in range(200)]` — 221 vs 200 rows. pandas raises `ValueError: All arrays must be of the same length`.
- **Fix:** Changed volume list to `[1_000_000] * 200` to match close column length.
- **Files modified:** `tests/test_strategy/test_screening.py`
- **Commit:** de4756c

## Known Stubs

None — all four functions are fully implemented with correct behavior verified by tests.

## Threat Flags

No new security-relevant surface introduced. All functions are pure math with no I/O, no network calls, no DB access. Threat model from plan is satisfied (T-04-01 through T-04-SC all accepted).

## Self-Check: PASSED

- FOUND: src/bensdorp1/strategy/__init__.py
- FOUND: src/bensdorp1/strategy/screening.py
- FOUND: tests/test_strategy/__init__.py
- FOUND: tests/test_strategy/test_screening.py
- FOUND commit: 327a0fc (Task 1)
- FOUND commit: de4756c (Task 2)
- Coverage: 100% on screening.py
- All tests: 19 passed, 0 failed
