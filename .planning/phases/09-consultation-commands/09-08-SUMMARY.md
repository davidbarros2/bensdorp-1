---
phase: 09-consultation-commands
plan: "08"
subsystem: commands
tags:
  - cmd-10
  - detail
  - stop-history
  - trailing-stop

dependency_graph:
  requires:
    - 09-01  # Wave 0 stubs created test_detail.py
    - "Phase 4 strategy: trailing stop formulas (running_max * 0.75, max(initial, trailing))"
    - "Phase 6: init populates price_daily with 220-day history"
    - "Phase 7: scan updates price_daily on each scan run"
  provides:
    - CMD-10 detail command (full implementation)
    - per-day stop history walk from price_daily
  affects:
    - src/bensdorp1/commands/detail.py
    - tests/test_commands/test_detail.py

tech_stack:
  added: []
  patterns:
    - SP-1 DB entry triad (buy.py canonical)
    - SP-4 closed_at == None SQLAlchemy IS NULL idiom
    - SP-9 Text() wrapping for console.print() literals
    - D-01 per-day stop history walk from price_daily (no schema changes)
    - D-02 no splits section (deferred to Phase 11)
    - D-10 error message wording with audit --symbol hint

key_files:
  created: []
  modified:
    - src/bensdorp1/commands/detail.py
    - tests/test_commands/test_detail.py

decisions:
  - "D-01 honored: stop history reconstructed by walking NYSE trading days from entry_date+1 to last price_daily.trade_date; no schema changes required"
  - "D-02 honored: no splits section present; no placeholder text"
  - "D-10 honored: error message 'No open position for SYMBOL.' with actions hint 'bensdorp1 audit --symbol SYMBOL'"
  - "Added 4th test (test_detail_no_price_history) beyond the 3 Wave 0 stubs; covers the Scenario 3 MSFT edge case from the plan action block"
  - "Running max initialized to pos_row.entry_close (entry close is the base; day-after-entry data may or may not exceed it)"

metrics:
  duration: "~8 minutes"
  completed: "2026-05-25T21:25:03Z"
  tasks_completed: 1
  files_modified: 2
---

# Phase 09 Plan 08: detail Command (CMD-10) Summary

**One-liner:** Full `bensdorp1 detail SYMBOL` command with NYSE trading-day walk computing per-day running_max, trailing_stop, and effective_stop from price_daily data.

## What Was Built

Replaced the 11-line stub `detail.py` with a full CMD-10 implementation:

- **Open-position guard:** `select(positions).where(symbol == SYMBOL AND closed_at IS NULL)` → if None, `print_error` with `audit --symbol` hint + exit code 1
- **Position summary block:** 5-key `render_kv_block` (Symbol, Entry date, Entry price, Shares, Initial stop)
- **Section header:** `Text("Stop history")` + `Text("-" * 12)` per SP-9
- **Price fetch:** All `price_daily` rows for SYMBOL where `trade_date > entry_date`, ordered ascending; built into `close_map: dict[date, float]`
- **No-data guard:** If `close_map` empty → `print_info` + exit 0
- **NYSE day walk:** `get_trading_days(entry_date + 1 day, last_price_date)` → for each day: skip if gap, else accumulate `running_max`, compute `trailing_stop = running_max * 0.75`, `effective_stop = max(initial_stop, trailing_stop)`
- **5-column table:** Date, Close, Highest close, Trailing stop, Effective stop

Filled in the 3 Wave 0 test stubs and added a 4th no-price-history test:
1. `test_detail_exits_code_1_when_no_open_position` — mock engine, no pos for NVDA, exit 1, output contains "audit --symbol NVDA"
2. `test_detail_shows_position_summary_and_stop_history` — seeded DB with AAPL + 3 price rows, exit 0, all headers + dates + closes in output
3. `test_detail_stop_history_rows_use_correct_formulas` — same seed, verifies running_max progression, $138.75 trailing_stop, $185.00 appears ≥2 times
4. `test_detail_no_price_history` — MSFT open position, no price rows after entry, exit 0 with "No price history available"

## Commits

| Hash | Message |
|------|---------|
| 14ba312 | feat(09-08): implement detail command with per-day stop history walk |

## Deviations from Plan

### Auto-added functionality

**Extra test (no plan deviation — plan described 3 scenarios, I implemented all 3 + added 4th)**
- The plan's action block described Scenario 3 (MSFT, no price rows, exit 0) but the 3 Wave 0 stubs only covered 2 named scenarios + formulas. Added `test_detail_no_price_history` as the 4th test to cover Scenario 3 explicitly.
- This is strictly additive coverage; all plan must_haves still satisfied.

No bugs fixed. No architectural changes. No blocking issues.

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| No "Not yet implemented" in detail.py | PASS |
| signature accepts `symbol: str = typer.Argument(...)` | PASS |
| `print_error(` with `audit --symbol` actions hint | PASS |
| `raise typer.Exit(code=1)` on no-position branch | PASS |
| `positions.c.closed_at == None  # noqa: E711` | PASS |
| `running_max: float = pos_row.entry_close` (initialization) | PASS |
| `running_max * 0.75` for trailing_stop | PASS |
| `max(pos_row.initial_stop, trailing_stop)` for effective_stop | PASS |
| `get_trading_days(pos_row.entry_date.date() + timedelta(days=1)` | PASS |
| `Text("Stop history")` and `Text("-" * 12)` | PASS |
| No "split"/"splits" in user-visible strings | PASS |
| 5-column render_table: Date, Close, Highest close, Trailing stop, Effective stop | PASS |
| Zero `pytest.skip` calls remaining | PASS |
| `uv run pytest tests/test_commands/test_detail.py -x -q` exits 0 (4 passed) | PASS |
| `uv run mypy --strict src/bensdorp1/commands/detail.py` exits 0 | PASS |
| `uv run ruff check ...` exits 0 | PASS |

## Known Stubs

None. The command is fully wired to real SQLite data via price_daily.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. All SQL uses SQLAlchemy parameterized queries (T-09-08-T1 mitigated). All cell values formatted via format_price/format_date before reaching render_table (T-09-08-T2 mitigated). Price gaps handled by `close_map.get(day_date)` returning None → `continue` (T-09-08-V2 mitigated).

## Self-Check: PASSED

- `src/bensdorp1/commands/detail.py` exists and has 135 lines
- `tests/test_commands/test_detail.py` exists and has 169 lines
- Commit 14ba312 exists in git log
- 4 tests pass, 0 failures
