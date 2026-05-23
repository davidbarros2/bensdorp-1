---
phase: 04-strategy-logic
plan: "02"
subsystem: strategy/positions
tags: [python, mypy-strict, hypothesis, pure-functions, positions, stop-calculation]
dependency_graph:
  requires:
    - bensdorp1.strategy (from 04-01 — __init__.py and tests/test_strategy/ package)
  provides:
    - bensdorp1.strategy.positions (compute_position_size, compute_initial_stop, update_highest_close, compute_trailing_stop, compute_effective_stop, is_exit_triggered)
    - bensdorp1.strategy (all 11 public names now exported via __init__.py)
  affects:
    - Phase 7 (scan command) — consumes is_exit_triggered, update_highest_close, compute_trailing_stop, compute_effective_stop
    - Phase 8 (buy command) — consumes compute_position_size, compute_initial_stop
tech_stack:
  added: []
  patterns:
    - stdlib math only in positions.py — no pandas, no numpy (D-02)
    - Multi-line docstrings for functions whose one-liner exceeded 88 chars (ruff E501)
    - Hypothesis st.lists for monotonicity invariant (Invariant 2)
    - import ordering: positions before screening alphabetically (ruff I001)
key_files:
  created:
    - src/bensdorp1/strategy/positions.py
    - tests/test_strategy/test_positions.py
  modified:
    - src/bensdorp1/strategy/__init__.py
decisions:
  - "Multi-line docstrings used for 4 of 6 functions — single-line docstrings exceeded ruff E501 (88 char limit); split into summary + details lines"
  - "Import ordering in __init__.py: positions import block placed before screening (alphabetical order per ruff I001)"
metrics:
  duration: "~3m 22s"
  completed: "2026-05-23"
  tasks: 2
  files: 3
---

# Phase 4 Plan 02: Position Sizing and Stop Calculation Summary

Six pure stop-arithmetic functions in positions.py with 100% line coverage, mypy strict clean, ruff clean — all STRAT-06 through STRAT-09 requirements satisfied and both Hypothesis invariants verified with 500 examples each.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create positions.py — six pure stop-arithmetic functions | 938526a | src/bensdorp1/strategy/positions.py |
| 2 | Create test_positions.py with full unit + Hypothesis coverage and wire __init__.py | cfee8d5 | tests/test_strategy/test_positions.py, src/bensdorp1/strategy/__init__.py |

## What Was Built

**src/bensdorp1/strategy/positions.py** — Six pure arithmetic functions, stdlib math only:
- `compute_position_size(available_cash, prev_close) -> int` — `math.floor((cash * 0.10) / prev_close)`; returns 0 when result < 1 (D-06, STRAT-06)
- `compute_initial_stop(entry_close) -> float` — `entry_close * 0.93`; immutable (STRAT-07)
- `update_highest_close(current, new_close) -> float` — `max(current, new_close)`; stateless (D-08)
- `compute_trailing_stop(highest_close) -> float` — `highest_close * 0.75`; stateless (D-08, STRAT-08)
- `compute_effective_stop(initial_stop, trailing_stop) -> float` — `max(initial, trailing)` (STRAT-09)
- `is_exit_triggered(close, effective_stop) -> bool` — `close <= effective_stop`; boundary-inclusive (STRAT-09)

**tests/test_strategy/test_positions.py** — 18 tests:
- 15 unit tests covering all 6 functions, all branches (D-06 zero case, boundary=1, equal cases for update_highest_close and is_exit_triggered)
- 2 Hypothesis property invariants (500 examples each):
  - Invariant 1: `compute_effective_stop(i, t) >= i` always
  - Invariant 2: trailing stop sequence is monotonically non-decreasing

**src/bensdorp1/strategy/__init__.py** — Updated to export all 11 public names:
- 5 from screening: `Candidate`, `liquidity_filter`, `momentum_filter`, `rank_candidates`, `regime_filter`
- 6 from positions: `compute_effective_stop`, `compute_initial_stop`, `compute_position_size`, `compute_trailing_stop`, `is_exit_triggered`, `update_highest_close`

## Verification Results

| Gate | Result |
|------|--------|
| `uv run pytest tests/test_strategy/test_positions.py -x -q` | 18 passed |
| `uv run pytest tests/test_strategy/ -x -q` | 37 passed (screening + positions) |
| `uv run mypy src/bensdorp1/strategy/` | Success: no issues found in 3 source files |
| `uv run ruff check src/bensdorp1/strategy/` | All checks passed |
| `uv run mypy tests/test_strategy/test_positions.py` | Success: no issues found |
| Coverage: positions.py | 100% (13 stmts, 0 missed) |
| Coverage: screening.py | 100% (50 stmts, 0 missed) |
| Coverage: __init__.py | 100% (3 stmts, 0 missed) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ruff E501 line-too-long on single-line docstrings**
- **Found during:** Task 1 (first ruff check)
- **Issue:** 5 of the 6 single-line docstrings specified in the plan exceeded ruff's 88-char line limit, causing ruff to exit non-zero.
- **Fix:** Converted affected docstrings to multi-line format (summary line + blank line + details line). Plan specified "single-line docstring pattern" but the exact wording from the plan itself was too long for ruff's limit. The pattern was preserved for the one function that fit (compute_effective_stop).
- **Files modified:** `src/bensdorp1/strategy/positions.py`
- **Commit:** 938526a

**2. [Rule 3 - Blocking] ruff I001 import order in __init__.py**
- **Found during:** Task 2 (first ruff check after editing __init__.py)
- **Issue:** Plan instructed adding positions imports after the screening imports, but ruff I001 requires alphabetical ordering of import blocks. `positions` sorts before `screening` alphabetically.
- **Fix:** Placed `from bensdorp1.strategy.positions import (...)` before `from bensdorp1.strategy.screening import (...)`.
- **Files modified:** `src/bensdorp1/strategy/__init__.py`
- **Commit:** cfee8d5

## Known Stubs

None — all six functions are fully implemented. No placeholder data, no hardcoded returns.

## Threat Flags

No new security-relevant surface introduced. All functions accept float/int scalars only. No I/O, no DB access, no network calls. Threat model from plan satisfied (T-04-04 through T-04-SC all accepted).

## Self-Check: PASSED

- FOUND: src/bensdorp1/strategy/positions.py
- FOUND: tests/test_strategy/test_positions.py
- FOUND: src/bensdorp1/strategy/__init__.py (modified)
- FOUND commit: 938526a (Task 1)
- FOUND commit: cfee8d5 (Task 2)
- Coverage: 100% on all three strategy/ files
- All tests: 37 passed (19 screening + 18 positions), 0 failed
- __init__.py __all__ contains 11 names (verified)
