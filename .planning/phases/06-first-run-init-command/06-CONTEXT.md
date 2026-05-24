# Phase 6: First-Run Init Command - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the `init` command (`commands/init.py`) — the interactive first-run setup that creates the `~/bensdorp1/` directory tree, initializes the SQLite database via `run_migrations()`, fetches S&P 500 constituents, downloads 220 trading days of price history, and records the user's initial available cash. Follows spec section 7.1 exactly for all output.

Specifically delivers:
- `src/bensdorp1/commands/init.py` — replaces the stub; full interactive flow
- `tests/test_commands/test_init.py` — CLI + unit tests with mocked data layer
- No new subpackages; no changes to `ui/`, `db/`, `data/`, or `strategy/`

**Does NOT include:** catch-up logic (Phase 11), restore command (Phase 10), or any modifications to existing modules.

</domain>

<decisions>
## Implementation Decisions

### Guard Condition (already-initialized check)
- **D-01:** Guard condition is DB file existence: `(DATA_DIR / "data" / "bensdorp1.db").exists()`. No schema inspection. Fast, conservative, spec-correct.
- **D-02:** Guard error message uses `print_error()` and mentions BOTH recovery paths:
  1. "Delete the file and run `bensdorp1 init` again" — for partial/interrupted inits
  2. "Run `bensdorp1 restore PATH` to replace with a backup" — for users with an existing DB
  Guard fires before any prompts or I/O; command exits immediately.

### Cash Input Validation
- **D-03:** Minimum valid cash: `> 0`. Any positive float is accepted. Zero, negative numbers, and non-numeric input are all invalid.
- **D-04:** On invalid cash (≤ 0): re-prompt with `"Error: Cash must be greater than zero."` — user stays in the flow without aborting. `number_prompt()` already handles non-numeric re-prompting; Phase 6 adds a positive-value guard loop on top of `number_prompt()`.
- **D-05:** `number_prompt()` signature stays unchanged (returns `float`). The `init` command wraps the entire cash-entry block in `try/except KeyboardInterrupt`, prints `"Operation aborted. No changes were made."` via console, then exits with `raise typer.Exit()`.

### Abort and Partial Failure
- **D-06:** No cleanup on Ctrl+C or network failure during execution. If init fails mid-way (DB file created, price download incomplete), the partial DB stays. The guard error on re-run explains the recovery path (D-02). No file deletion logic in init.
- **D-07:** The spec's "Continue? [y/n]" at step 1 (before any DB writes) is the user's only escape hatch. No additional confirmation prompt is added before execution begins. After cash is confirmed, setup starts immediately.

### Test Coverage
- **D-08:** Phase 6 ships moderate test coverage using `CliRunner` (in-process) with mocked data layer. Tests are written to `tests/test_commands/test_init.py`. Required scenarios:
  1. Guard fires when DB file already exists — assert error exit + message contains both recovery paths
  2. Happy path — mock `get_constituents`, `update_price_data`, `run_migrations`, `log_event`, `create_backup`; simulate user inputs; assert DB created, `system_initialized` audit event written, cash stored in DB
  3. Cash validation — simulate invalid inputs (0, -100, "abc"); assert re-prompt behavior
  4. Ctrl+C during cash entry — simulate `KeyboardInterrupt`; assert abort message + clean exit (no DB written)

### Claude's Discretion
- The exact `tests/test_commands/` directory structure (create `__init__.py` or not, conftest placement) — follow whatever pattern matches the existing `tests/` layout.
- Whether to extract a private `_run_init()` helper function within `init.py` (for testability) or keep the command function flat — planner's call based on testability needs.
- The exact error message wording for the guard (beyond the two recovery paths) — sentence case, plain text, `print_error()` severity prefix as established in Phase 5.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary specification (authoritative)
- `.planning/Bensdorp_1.md` §7.1 — Complete first-run init flow: exact output layout for all 4 steps (welcome, cash declaration, multi-phase progress, completion summary). Canonical source.
- `.planning/Bensdorp_1.md` §6 — 31 UI/UX style guide rules (all output must comply)
- `.planning/Bensdorp_1.md` §3.1 — Rich mandated for output rendering
- `.planning/REQUIREMENTS.md` CMD-01 — `init` command requirement (one-line spec: create dirs, fetch, download, record cash; refuses if DB exists)

### Existing implementations to read before coding
- `src/bensdorp1/commands/init.py` — current stub (one-liner; replace entirely)
- `src/bensdorp1/config.py` — DATA_DIR, PROJECT_NAME, MARKET_TZ, USER_TZ constants
- `src/bensdorp1/db/engine.py` — `run_migrations(engine)`, `get_engine(path)`, `_reset_engine_for_testing()`
- `src/bensdorp1/db/audit.py` — `log_event(engine, AuditEventType.system_initialized, ...)`
- `src/bensdorp1/db/backup.py` — `create_backup(engine)` — called after successful init
- `src/bensdorp1/data/__init__.py` — `get_constituents()`, `refresh_constituents()`, `update_price_data()`, `check_price_coverage()`
- `src/bensdorp1/ui/progress.py` — `feedback.multi_step(total)` / `.step()` / `feedback.track()` API (D-03 from Phase 5)
- `src/bensdorp1/ui/prompts.py` — `confirm_prompt()`, `number_prompt()`, `text_prompt()` — do NOT modify signatures
- `src/bensdorp1/ui/messages.py` — `print_error()`, `print_success()`, `print_info()` — use for all output

### Prior phase context
- `.planning/phases/05-ui-components/05-CONTEXT.md` — D-01 through D-08: all UI primitive decisions; D-06 console ownership pattern; D-07 severity prefix API
- `.planning/phases/01-project-skeleton-and-tooling/01-CONTEXT.md` — `CliRunner` test pattern, `_app.py` Typer app structure

### Technology
- `CLAUDE.md` §Verified Library Versions — `typer >=0.21.1`, `rich >=14.0`
- `CLAUDE.md` §mypy Strict Mode Configuration — init.py must pass mypy strict
- `CLAUDE.md` §Ruff Configuration — formatter and linter apply

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `db/engine.py`: `run_migrations(engine)` — idempotent, `checkfirst=True`; `get_engine(path=None)` — lazy singleton; `_reset_engine_for_testing()` — test teardown helper.
- `db/audit.py`: `log_event(engine, AuditEventType.system_initialized, metadata={...})` — call at successful completion.
- `db/backup.py`: `create_backup(engine)` — call after `run_migrations()` (per STATE-02: backup after every state-changing operation).
- `data/__init__.py`: `get_constituents(engine)` returns list of symbols + metadata; `update_price_data(engine, symbols)` downloads 220-day history.
- `ui/progress.py`: `feedback.multi_step(3)` for the 3-phase setup. Step 3 (price download) uses `ms.step("Downloading price history", total=len(symbols))` to get a `TrackContext`; call `.advance(symbol)` per symbol. Extra detail lines (e.g., "Stocks found: 503") are printed by the command after the step context exits.
- `config.py`: `DATA_DIR` — base directory; `DATA_DIR / "data" / "bensdorp1.db"` is the DB path; `DATA_DIR / "backups"` is the backups path.

### Established Patterns
- `_app.py`: `app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)`. All commands use `-> None` return type. `raise typer.Exit()` for early exits (not `sys.exit()`).
- Console ownership: all UI functions accept `console: Console | None = None`; tests pass `Console(record=True)` explicitly.
- `CliRunner` from `typer.testing` (in-process) for all CLI tests — no subprocess, no PATH dependency.
- `number_prompt()` returns `float`; already handles non-numeric re-prompt. Phase 6 adds positive-value guard on top.

### Integration Points
- `commands/init.py` imports from: `bensdorp1._app` (app), `bensdorp1.config` (DATA_DIR), `bensdorp1.db` (get_engine, run_migrations, log_event, create_backup, AuditEventType), `bensdorp1.data` (get_constituents, update_price_data), `bensdorp1.ui` (feedback, confirm_prompt, number_prompt, print_error, print_success, print_info).
- `tests/test_commands/test_init.py` — follows `tests/test_db/`, `tests/test_data/` directory pattern; uses shared `conftest.py` fixtures.

</code_context>

<specifics>
## Specific Ideas

### Path display: tilde form (from spec §7.1 completion summary)
The completion summary must show paths as `~/bensdorp1/data/bensdorp1.db`, not the expanded absolute path. The command must replace the home directory prefix with `~` when displaying:
```python
def _tilde_path(p: Path) -> str:
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)
```

### Multi-step detail lines (from spec §7.1 Step 3)
After each `ms.step()` context exits, the command prints indented detail lines:
```
[1/3] Fetching S&P 500 constituents... done.
      Source: Wikipedia
      Stocks found: 503
```
The `MultiStepContext.step()` prints the `done.` line automatically. The extra info lines (`Source: Wikipedia`, `Stocks found: 503`) are printed by the command immediately after `with ms.step(...):` exits. Use `console.print("      Source: Wikipedia")` (8-space indent per the spec layout).

### 3-phase setup structure
Spec §7.1 shows exactly 3 phases in `multi_step(3)`:
1. `[1/3] Fetching S&P 500 constituents...` — SpinnerContext (no total, unknown duration)
2. `[2/3] Verifying against secondary source...` — SpinnerContext
3. `[3/3] Downloading price history...` — TrackContext (total = len(constituents))

Phase 3 uses the rule 6.21 progress bar layout (already implemented in `TrackContext._build_progress_block()`).

### Section header format (from spec §7.1)
- Welcome screen title: `===` spanning content width — use `ui/messages.py` or print directly with `"=" * 64`
- "Available cash" subsection: `---` spanning only the section header text width — `"Available cash"` (14 chars) + `"\n" + "-" * 14`
- "Setup complete" title: same `===` pattern as welcome screen

### Cash confirmation format
After numeric input, display:
```
Available cash: $50,000.00

Confirm? [y/n]: _
```
Use `format_price(amount)` from `ui/` (already implemented) for the formatted display.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-First-Run Init Command*
*Context gathered: 2026-05-24*
