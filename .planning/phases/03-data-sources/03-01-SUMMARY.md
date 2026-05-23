---
phase: 03-data-sources
plan: 01
subsystem: data
tags:
  - data-layer
  - calendar
  - nyse
  - pyproject
dependency_graph:
  requires:
    - "Phase 2: db subpackage (engine, schema)"
  provides:
    - "bensdorp1.data subpackage marker (src/bensdorp1/data/__init__.py)"
    - "calendar.py: get_trading_days, is_trading_day, n_trading_days_ago"
    - "Stable test filenames for Plans 02 and 03"
    - "mypy overrides for yfinance, pandas_market_calendars"
    - "lxml-stubs and pandas-stubs in dev deps"
  affects:
    - "Plans 02 and 03 (unblocked — stable test paths and pyproject config)"
    - "Phase 4 (strategy logic calls calendar.py)"
tech_stack:
  added:
    - "pandas-market-calendars 5.3.2 (NYSE calendar; already installed, now used)"
    - "lxml-stubs 0.5.1 (mypy strict stubs for lxml)"
    - "pandas-stubs 3.0.0.260204 (mypy strict stubs; pandas 3.0.3 lacks py.typed)"
  patterns:
    - "Module-level singleton _NYSE = mcal.get_calendar('NYSE') — read-only, no lock"
    - "Fixed max-lookback cap (3650 days) for n_trading_days_ago to make ValueError reachable"
    - "Reference date excluded from n_trading_days_ago range — n=1 returns day before reference"
key_files:
  created:
    - path: "src/bensdorp1/data/__init__.py"
      lines: 4
      role: "Placeholder subpackage marker; Plan 04 adds full re-exports"
    - path: "src/bensdorp1/data/calendar.py"
      lines: 54
      role: "NYSE trading-day wrappers (DATA-07) — pure computation, no I/O"
    - path: "tests/test_data_calendar.py"
      lines: 73
      role: "9 unit tests covering DATA-07; all passing"
    - path: "tests/test_data_constituents.py"
      lines: 12
      role: "Test scaffold for Plan 02 (DATA-01/02/05); 1 SKIP placeholder"
    - path: "tests/test_data_prices.py"
      lines: 12
      role: "Test scaffold for Plan 03 (DATA-03/04/08/09/10); 1 SKIP placeholder"
  modified:
    - path: "pyproject.toml"
      change: "Added lxml-stubs>=0.5.1 and pandas-stubs to dev deps; added mypy overrides for yfinance and pandas_market_calendars"
decisions:
  - "Used 3650-day max lookback cap in n_trading_days_ago (not adaptive-only) — makes ValueError reachable for n=10000 test; also bounds memory consumption"
  - "Reference date excluded from n_trading_days_ago range — days[-1] would be reference itself if included; n=1 must return the day before reference"
  - "Added pandas-stubs (deviation from plan) — pandas 3.0.3 lacks py.typed; mypy strict raised import-untyped error; pandas-stubs resolves it cleanly"
metrics:
  duration: "5m 12s"
  completed_date: "2026-05-23"
  tasks_completed: 3
  files_created: 5
  files_modified: 2
---

# Phase 03 Plan 01: Data Foundations — Calendar, pyproject, and Test Scaffolds — Summary

**One-liner:** NYSE calendar wrappers (DATA-07) with pandas_market_calendars 5.3.2 + mypy strict plumbing for yfinance/pandas.

## What Was Built

Three tasks completed atomically:

**Task 1 — pyproject.toml updates:**
- Added `lxml-stubs>=0.5.1` to `[dependency-groups] dev` list (line 36, after mypy entry)
- Added two `[[tool.mypy.overrides]]` blocks after the existing `bensdorp1.commands.*` block:
  - `module = "yfinance"` with `ignore_missing_imports = true`
  - `module = "pandas_market_calendars"` with `ignore_missing_imports = true`
- `uv sync` installed lxml-stubs 0.5.1 and pandas-stubs 3.0.0.260204 (deviation — see below)
- `uv run mypy --strict -c "import yfinance"` and `import pandas_market_calendars` both exit 0

**Task 2 — data subpackage + calendar.py + tests:**
- `src/bensdorp1/data/__init__.py`: 4-line placeholder docstring only; Plan 04 adds re-exports
- `src/bensdorp1/data/calendar.py`: 54 lines implementing DATA-07
  - Module-level singleton: `_NYSE = mcal.get_calendar("NYSE")`
  - `get_trading_days(start, end)` → `pd.DatetimeIndex` (UTC)
  - `is_trading_day(dt)` → `bool`
  - `n_trading_days_ago(n, reference=None)` → `date` with 3650-day max lookback cap
- `tests/test_data_calendar.py`: 73 lines, 9 unit tests — all pass

**Task 3 — test scaffolds:**
- `tests/test_data_constituents.py`: 12 lines, 1 SKIP placeholder for Plan 02
- `tests/test_data_prices.py`: 12 lines, 1 SKIP placeholder for Plan 03
- Full suite: 92 passed, 2 skipped; mypy strict clean; ruff clean

## Test Results

| Suite | Result |
|-------|--------|
| `uv run pytest tests/test_data_calendar.py -x -q` | 9 passed |
| `uv run pytest tests/test_data_constituents.py tests/test_data_prices.py -q` | 2 skipped |
| `uv run pytest tests/ -q` (full suite) | 92 passed, 2 skipped |
| `uv run mypy src/` | 0 errors (28 files) |
| `uv run ruff check src/ tests/` | 0 errors |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed n_trading_days_ago returning reference day instead of day before**
- **Found during:** Task 2, first test run (test_n_trading_days_ago_one_step failed)
- **Issue:** `days[-n]` with `get_trading_days(start, ref)` returned `ref` itself when `ref` is a trading day — `days[-1]` = reference date, not the preceding day
- **Fix:** Changed `end = ref` to `end = ref - timedelta(days=1)` to exclude the reference from the range
- **Files modified:** `src/bensdorp1/data/calendar.py`
- **Commit:** included in f30cf5a

**2. [Rule 1 - Bug] Fixed ValueError not raised for n=10000**
- **Found during:** Task 2, second test run (test_n_trading_days_ago_raises_when_buffer_insufficient failed)
- **Issue:** The adaptive buffer `int(n * 1.5) + 30 = 15030` days for n=10000 covers ~41 years of NYSE history — enough trading days exist, so no error was raised
- **Fix:** Added `_MAX_LOOKBACK_DAYS = 3650` cap (`min(adaptive_buffer, 3650)`) — 3650 calendar days ≈ 2500 trading days, which is less than 10000
- **Files modified:** `src/bensdorp1/data/calendar.py`
- **Commit:** included in f30cf5a

**3. [Rule 2 - Missing Critical Functionality] Added pandas-stubs dev dependency**
- **Found during:** Task 2, first mypy run
- **Issue:** `pandas 3.0.3` does not ship `py.typed` or `.pyi` stubs. mypy strict raised `Library stubs not installed for "pandas" [import-untyped]`. The CLAUDE.md note "pandas and numpy ship their own stubs — no override needed" appears outdated for pandas 3.0.x.
- **Fix:** Ran `uv add --dev "pandas-stubs"` — installed `pandas-stubs==3.0.0.260204`. Also removed now-unnecessary `# type: ignore[import-untyped]` comment on the `pandas_market_calendars` import (the mypy override added in Task 1 covered it).
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Commit:** included in f30cf5a

## Known Stubs

None. `data/__init__.py` is a docstring-only placeholder; Plan 04 fills in the re-exports. The test scaffolds use `pytest.skip()` intentionally — they show as SKIPPED, not failures.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. `calendar.py` is pure computation (no I/O). pyproject.toml changes are additive dev-tooling only.

## Self-Check

Files exist:
- [x] `src/bensdorp1/data/__init__.py`
- [x] `src/bensdorp1/data/calendar.py`
- [x] `tests/test_data_calendar.py`
- [x] `tests/test_data_constituents.py`
- [x] `tests/test_data_prices.py`

Commits:
- [x] `9747419` — chore(03-01): pyproject.toml lxml-stubs + mypy overrides
- [x] `f30cf5a` — feat(03-01): data subpackage, calendar.py, calendar tests
- [x] `e69580b` — feat(03-01): test scaffolds for Plans 02/03

## Self-Check: PASSED
