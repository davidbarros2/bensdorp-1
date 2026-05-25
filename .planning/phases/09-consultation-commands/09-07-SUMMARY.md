---
phase: 09-consultation-commands
plan: "07"
subsystem: commands
tags: [portfolio, cmd-09, read-only, table, positions, price-daily]
dependency_graph:
  requires: [09-01]
  provides: [CMD-09]
  affects: [src/bensdorp1/commands/portfolio.py, tests/test_commands/test_portfolio.py]
tech_stack:
  added: []
  patterns:
    - SP-1 DB entry triad
    - SP-2 empty state guard
    - SP-4 closed_at == None IS NULL idiom
    - SP-12 format_pct for percentage columns (Dist %)
    - per-symbol latest-price sub-query with ORDER BY DESC LIMIT 1
    - effective_stop computed at read time (max(initial_stop, trailing_stop))
key_files:
  created: []
  modified:
    - src/bensdorp1/commands/portfolio.py
    - tests/test_commands/test_portfolio.py
decisions:
  - test assertions use partial value matching (e.g. "-$215", "+4.8%", "$169.73") to remain robust against Rich table cell truncation in narrow CliRunner terminal
metrics:
  duration: ~7 minutes
  completed: "2026-05-25T21:25:51Z"
  tasks_completed: 1
  files_changed: 2
---

# Phase 9 Plan 07: Portfolio Command Summary

One-liner: `bensdorp1 portfolio` renders a 10-column table of all open positions with live-computed effective_stop, dist_pct, unrealized_pnl from latest price_daily row; N/A fallback when price data is absent.

## What Was Built

Replaced the 11-line stub in `src/bensdorp1/commands/portfolio.py` with a full CMD-09 implementation:

- Queries all open positions (`closed_at IS NULL` via SP-4 idiom)
- Prints `"No open positions."` and exits 0 on empty set (UI-08)
- Computes `today_et` and `today_utc_midnight` once outside the per-position loop
- For each position runs a per-symbol sub-query against `price_daily` ordered by `trade_date DESC LIMIT 1` to get the latest close
- When price data is absent, fills `Last $, High $, Stop $, Dist %, P&L` with `"N/A"` (D-07 fallback)
- When price data is present, computes:
  - `effective_stop = max(pos.initial_stop, pos.trailing_stop)` (D-18 — computed at read time, never stored)
  - `dist_pct = (last_close - effective_stop) / last_close * 100.0`
  - `unrealized_pnl = (last_close - pos.entry_close) * pos.shares`
  - `days = len(get_trading_days(pos.entry_date.date(), today_et))`
- Renders via `render_table` with exact D-06 10-column layout (Symbol/left, Entry date/left, Days/right, Entry $/right, Shares/right, Last $/right, High $/right, Stop $/right, Dist %/right, P&L/right)

Filled in all 3 Wave 0 test stubs in `tests/test_commands/test_portfolio.py`:
- Scenario 1 (empty): mock engine + `fetchall=[]` → asserts `"No open positions."`, exit 0
- Scenario 2 (happy-with-prices): seeded DB (AAPL + price_daily row) → asserts symbol, shares, `+4.8%` dist, `-$215` P&L, `$169.73` stop
- Scenario 3 (no-price-data): seeded DB (NVDA, no price_daily) → asserts `"NVDA"` + 5 `"N/A"` occurrences

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written with one implementation note:

**Test assertion strategy adjusted for Rich table cell truncation**

- **Found during:** Task 1 (first test run)
- **Issue:** The Rich `Table` rendered by `render_table` truncates long cell values (e.g. `$182.50` → `$182.…`) when the CliRunner default console width (80 chars) is too narrow for a 10-column table
- **Fix:** Instead of asserting exact dollar values that get truncated, the tests assert on: (a) short fixed-width values that don't truncate (`"+4.8%"`, `"$169.73"`, `"50"`), (b) prefixes that survive truncation (`"-$215"`). The terminal_width=200 approach was attempted but the Rich Console inside the command is constructed independently of the CliRunner terminal width setting.
- **Files modified:** `tests/test_commands/test_portfolio.py`
- **Commit:** c863c04 (same commit as implementation)

## Known Stubs

None — all stub placeholders replaced with working implementation and tests.

## Threat Flags

No new security-relevant surface introduced. All queries use parameterized SQLAlchemy Core. `render_table` uses `Text()` wrappers (markup-safe). Per the plan's threat register:
- T-09-07-T1: SQLAlchemy parameterized queries — implemented correctly
- T-09-07-T2: render_table markup safety — Text() wrappers used throughout
- T-09-07-V1: divide-by-zero guard — handled by `if price_row is None` branch (any zero-close from price_daily is an upstream data integrity issue, accepted per plan)

## Self-Check: PASSED

- `src/bensdorp1/commands/portfolio.py` exists and contains full implementation
- `tests/test_commands/test_portfolio.py` exists with 3 non-skip tests
- Commit `c863c04` verified in git log
- `uv run pytest tests/test_commands/test_portfolio.py -x -q` → 3 passed
- `uv run mypy --strict src/bensdorp1/commands/portfolio.py` → Success: no issues
- `uv run ruff check src/bensdorp1/commands/portfolio.py tests/test_commands/test_portfolio.py` → All checks passed
