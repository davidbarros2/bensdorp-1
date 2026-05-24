---
phase: 06-first-run-init-command
plan: "01"
subsystem: commands
tags: [typer, rich, sqlalchemy, init, setup, interactive]

# Dependency graph
requires:
  - phase: 05-ui-components
    provides: feedback, MultiStepContext, TrackContext, confirm_prompt, number_prompt, format_price, print_error, _render_kv_block
  - phase: 03-data-sources
    provides: get_constituents, update_price_data
  - phase: 02-database-and-migrations
    provides: get_engine, run_migrations, log_event, create_backup, AuditEventType

provides:
  - Full init command replacing the stub with the complete §7.1 interactive flow
  - Guard check refusing re-initialization when DB file already exists
  - Cash declaration loop with positive-value validation and Ctrl+C abort handling
  - Three-phase multi_step progress: fetch constituents, verify, per-symbol download
  - _store_cash writes to config table, log_event writes SYSTEM_INITIALIZED audit event
  - Completion summary with tilde-form paths and formatted elapsed time

affects: [07-scan-command, 10-restore-command, 11-catch-up-logic, 12-remaining-commands]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Guard via db_path.exists() before any prompts or I/O"
    - "try/except KeyboardInterrupt wrapping cash entry block, raise typer.Exit() from None"
    - "Detail lines printed after with ms.step() block exits, not inside it"
    - "TrackContext type annotation via type: ignore[assignment] on SpinnerContext | TrackContext union"
    - "_tilde_path() replaces home prefix with ~/ for display without exposing full paths"
    - "_store_cash uses sqlite_insert.on_conflict_do_update with f-string for deterministic precision"
    - "Private helper _render_kv_block imported once with inline comment explaining why"

key-files:
  created: []
  modified:
    - src/bensdorp1/commands/init.py
    - tests/test_cli.py

key-decisions:
  - "TrackContext resolved with type: ignore[assignment] — ms.step() yields SpinnerContext | TrackContext union; mypy cannot narrow without cast"
  - "raise typer.Exit() from None inside except KeyboardInterrupt — B904 (ruff) requires chaining or explicit None; None chosen since no causal exception to chain"
  - "Private _render_kv_block import retained as planned — no public equivalent for column-aligned kv pairs"

patterns-established:
  - "Guard pattern: check db_path.exists() before any prompts; print_error with actions list; raise typer.Exit(1)"
  - "Cash entry: try/except KeyboardInterrupt at block level; while True with number_prompt + positive guard + confirm_prompt"
  - "Completion summary: _render_kv_block with dict of string keys/values; tilde-form paths; _format_elapsed for time"

requirements-completed: [CMD-01]

# Metrics
duration: 3min
completed: "2026-05-24"
---

# Phase 6 Plan 01: Init Command Summary

**Interactive first-run setup command using Rich multi-step progress, Typer exit patterns, and SQLAlchemy upsert for cash persistence — full §7.1 spec compliance**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-24T10:08:43Z
- **Completed:** 2026-05-24T10:11:29Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Replaced the one-liner stub with the full 237-line interactive first-run setup flow
- Guard fires on re-init with exact error message and both recovery paths (delete+reinit, restore from backup)
- Cash declaration loop validates > 0, handles Ctrl+C with abort message, confirms before proceeding
- Three-phase multi_step progress drives real constituent fetch and per-symbol price download
- mypy strict, ruff check, and ruff format all exit 0; 35 CLI tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement init.py — full interactive flow** - `c34f070` (feat)
2. **Task 2: Update test_cli.py — remove init from stub parametrize list** - `7351077` (chore)

## Files Created/Modified

- `src/bensdorp1/commands/init.py` - Full init command (237 lines) replacing 10-line stub
- `tests/test_cli.py` - Removed "init" from test_stub_exits_cleanly parametrize list only

## Decisions Made

- **TrackContext type annotation:** Used `track: TrackContext = _track  # type: ignore[assignment]` to satisfy mypy strict on the `SpinnerContext | TrackContext` union returned by `ms.step()`. The plan explicitly allowed this approach.
- **`raise typer.Exit() from None`:** ruff B904 requires chaining inside `except` blocks. Used `from None` since the KeyboardInterrupt has no causal exception to chain to the Exit.
- **Private `_render_kv_block` import:** Retained as specified by the plan. No public equivalent exists for column-aligned kv output.

## Deviations from Plan

None — plan executed exactly as written. The `type: ignore[assignment]` and `from None` patterns were both explicitly anticipated in the plan's mypy compliance section.

## Issues Encountered

- **ruff E501 (line too long):** Initial write had several lines over 88 chars. Fixed by wrapping long import lists with parentheses and splitting long string literals. Minor formatting issue, resolved before commit.
- **ruff B904:** `raise typer.Exit()` inside `except KeyboardInterrupt` triggered "raise from err or None" rule. Fixed with `raise typer.Exit() from None`.

## Known Stubs

None — init.py is fully implemented. The _store_cash, log_event, and create_backup calls are wired to real implementations.

## Threat Flags

No new security-relevant surface beyond what was specified in the plan's threat model. All T-06-0x threats handled per plan dispositions:
- T-06-01 (cash display): format_price + _render_kv_block with markup=False
- T-06-02 (path display): _tilde_path only replaces home prefix; no user path strings in file ops

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- init command is complete and integrated; the database, constituents, and price history will be populated correctly on first run
- test_stub_exits_cleanly no longer covers init; test_commands/test_init.py (integration tests) can be added in a future plan if needed
- All other stub commands remain in test_stub_exits_cleanly unchanged

## Self-Check

- [x] `src/bensdorp1/commands/init.py` exists (237 lines, min_lines=80 satisfied)
- [x] `tests/test_cli.py` updated — "init" removed from test_stub_exits_cleanly
- [x] Commit c34f070 exists (Task 1)
- [x] Commit 7351077 exists (Task 2)
- [x] mypy strict: 0 errors
- [x] ruff check: 0 errors
- [x] ruff format: already formatted
- [x] pytest tests/test_cli.py: 35 passed

## Self-Check: PASSED

---
*Phase: 06-first-run-init-command*
*Completed: 2026-05-24*
