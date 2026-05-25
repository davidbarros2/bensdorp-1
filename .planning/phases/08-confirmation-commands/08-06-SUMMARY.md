---
plan: 08-06
phase: 08-confirmation-commands
status: complete
started: 2026-05-25
completed: 2026-05-25
duration: ~5m
tasks_completed: 2
files_modified: 2
---

# Plan 08-06: CR-01 Input Validation and WR-01/WR-02 Fixes

## What Was Built

Added range guards to `fix.py` to reject zero/negative price and share values before any DB write (CR-01), fixed `fix.py`'s sell-path to always recompute `realized_pnl` unconditionally from `new_price` (WR-02), and replaced `sell.py`'s silent `_REASON_MAP` fallback with an explicit `typer.Exit(code=1)` error (WR-01).

## Key Files

### Modified
- `src/bensdorp1/commands/fix.py` — 3 guards added (buy price, buy shares, sell price) + unconditional realized_pnl recomputation
- `src/bensdorp1/commands/sell.py` — _REASON_MAP lookup now raises on unknown key

## Tasks Summary

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Add range guards to fix.py (CR-01 + WR-02) | ✓ complete | 5e80970 |
| 2 | Fix sell.py _REASON_MAP silent fallback (WR-01) | ✓ complete | 5e80970 |

## Verification

- `grep -c "new_price <= 0" fix.py` → 2 (buy + sell paths)
- `grep -c "new_shares <= 0" fix.py` → 1 (buy path)
- `realized_pnl` assignment is unconditional in sell path — no `if new_price != current_exit_price` guard
- `sell.py` contains "Unrecognised exit trigger reason" error; silent fallback removed
- `uv run ruff check` → 0 issues
- `uv run mypy --strict` → Success: no issues found
- `uv run pytest tests/test_commands/test_fix.py tests/test_commands/test_sell.py` → 6 passed

## Deviations

None. All edits matched the plan spec exactly.

## Self-Check: PASSED
