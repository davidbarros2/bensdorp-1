---
phase: 08-confirmation-commands
plan: "04"
subsystem: commands
tags: [typer, sqlalchemy, sqlite, fix, correction, audit-log]

requires:
  - phase: 08-01
    provides: "test skeleton for test_fix.py with 3 named tests (pytest.skip)"

provides:
  - "Full CMD-08 fix command implementation replacing stub"
  - "3/3 fix integration tests passing"
  - "closed_reason and closed_manual_reason columns added to schema.py Table definition"

affects:
  - 08-02
  - 08-03
  - 09-portfolio

tech-stack:
  added: []
  patterns:
    - "Field-by-field input with raw input() for default-bearing prompts (fix prompt format differs from text_prompt/number_prompt)"
    - "before/after audit payload with TRANSACTION_CORRECTED event for correction traceability"
    - "update(positions).where(id==).values() pattern for in-place DB correction"

key-files:
  created: []
  modified:
    - src/bensdorp1/commands/fix.py
    - src/bensdorp1/db/schema.py
    - tests/test_commands/test_fix.py
    - tests/test_cli.py
    - tests/test_db_schema.py

key-decisions:
  - "--date parameter accepted but unused (Open Question 1 resolved: no date-filtering semantics in Phase 8 per spec §7.5)"
  - "Sell closing-reason display label is sell.py's concern; fix.py only edits closed_at/exit_price/closed_manual_reason for closed positions"
  - "closed_reason and closed_manual_reason added to schema.py Table definition alongside run_migrations ALTER TABLE (required for positions.c.* access)"
  - "Invalid date/price input caught with try/except ValueError; prints Error message and raises typer.Exit(code=1)"

patterns-established:
  - "Fix command: field-by-field input via raw input() with format 'Field   [current]:  '"
  - "No-changes path: print_info + raise typer.Exit() with no DB write (D-23)"
  - "Price change on buy recalculates initial_stop = new_price * 0.93; trailing_stop/highest_close never mutated (D-22)"

requirements-completed:
  - CMD-08

duration: 25min
completed: 2026-05-25
---

# Phase 8 Plan 04: Fix Command Summary

**Interactive fix command with field-by-field prompts, before/after diff table, stop recalculation, and TRANSACTION_CORRECTED audit payload replacing the fix stub**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-25
- **Completed:** 2026-05-25
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Replaced `fix` stub with full CMD-08 implementation per spec §7.5 and decisions D-19–D-24
- All 3 CMD-08 scenarios pass: no-transaction error, no-changes early exit, price-change with stop recalculation
- trailing_stop and highest_close confirmed never mutated by any UPDATE in fix.py (D-22)
- Closed positions fix path handles closed_at/exit_price/closed_manual_reason with realized_pnl recalculation

## Task Commits

1. **Task 1: Implement fix.py — full CMD-08 flow** - `6636e02` (feat)
2. **Task 2: Implement test_fix.py — fill all 3 skeleton tests** - `b52c203` (feat)

## Files Created/Modified

- `src/bensdorp1/commands/fix.py` — Full fix command replacing stub (456 lines)
- `src/bensdorp1/db/schema.py` — Added closed_reason and closed_manual_reason columns to positions Table definition
- `tests/test_commands/test_fix.py` — 3 integration tests, 0 skips
- `tests/test_cli.py` — Removed fix from stub test list (fix is now a real implementation)
- `tests/test_db_schema.py` — Updated positions column count test from 12 to 14 columns

## Decisions Made

**Open Question 1 — `--date DATE` semantics for fix:**
Resolved by treating `--date` as accepted but unused in Phase 8. The parameter is accepted in the command signature (`date: str | None = typer.Option(...)`) and immediately bound to `_unused = date`. This matches the spec §7.5 which does not reference `--date` in the fix flow.

**Open Question 2 — Sell "Closing reason" display label:**
Resolved by noting that fix.py does NOT display the closing reason label at all. The fix command for closed positions shows date/price/manual_reason (if applicable). The closing-reason display label is exclusively sell.py's concern (render_kv_block in the sell confirmation). fix.py reads `closed_reason` only to determine whether `closed_manual_reason` is editable (only when `closed_reason == "manual"`).

**Invalid date/price input handling:**
`datetime.date.fromisoformat()` and `float()` are both wrapped in `try/except ValueError`. On invalid input, `print_error("Expected YYYY-MM-DD.", ...)` or `print_error("Expected a numeric price.", ...)` is printed and `raise typer.Exit(code=1)` exits cleanly. No re-prompt loop was added (acceptable per plan spec: "single re-prompt OK; or print Error and accept current").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added closed_reason and closed_manual_reason to schema.py Table definition**
- **Found during:** Task 2 (test_fix.py implementation)
- **Issue:** `positions.c.closed_reason` raised `AttributeError: closed_reason` at SQLAlchemy query construction time. The columns exist in the DB (added by `run_migrations` via ALTER TABLE) but were absent from the SQLAlchemy `Table` object in `schema.py`. Using `positions.c.closed_reason` in a `select()` call requires the Column to exist in the Python Table definition.
- **Fix:** Added `Column("closed_reason", Text, nullable=True)` and `Column("closed_manual_reason", Text, nullable=True)` to the `positions` Table in `schema.py`.
- **Files modified:** `src/bensdorp1/db/schema.py`, `tests/test_db_schema.py` (updated column count)
- **Verification:** `uv run pytest -x` passes 319 tests, 0 failures
- **Committed in:** `b52c203` (Task 2 commit)

**2. [Rule 1 - Bug] Removed fix from test_stub_exits_cleanly parametrize list**
- **Found during:** Task 2 verification (`uv run pytest -x`)
- **Issue:** `tests/test_cli.py::test_stub_exits_cleanly[fix]` invokes `runner.invoke(app, ["fix"])` with no arguments and expects exit 0 + "Not yet implemented." This test was written when fix was a stub. Now fix requires a SYMBOL argument; missing it causes exit code 2.
- **Fix:** Removed `"fix"` from the parametrize list. Updated the comment from "init and scan are intentionally absent" to "init, scan, and fix are intentionally absent".
- **Files modified:** `tests/test_cli.py`
- **Verification:** `uv run pytest tests/test_cli.py -v` passes all
- **Committed in:** `b52c203` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. Schema fix was required for the command to function at all. Stub test fix was required for the full suite to stay green. No scope creep.

## Issues Encountered

None beyond the deviations documented above.

## Known Stubs

None — fix.py fully replaces the stub. All behavior described in CMD-08 and spec §7.5 is implemented.

## Next Phase Readiness

- fix command is fully operational; can be used to correct buy or sell transactions
- Schema now has closed_reason and closed_manual_reason columns — sell.py (plans 02/03) can reference these via `positions.c.closed_reason`
- Full suite green at 319 tests passing

---
*Phase: 08-confirmation-commands*
*Completed: 2026-05-25*
