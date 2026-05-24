---
phase: 06-first-run-init-command
verified: 2026-05-24T13:00:00Z
status: human_needed
score: 11/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `bensdorp1 init` on a clean machine or BENSDORP1_HOME-isolated path (not just in a test runner)"
    expected: "Welcome screen prints, cash prompt appears, multi-step progress bar runs with per-symbol TrackContext advancement, completion summary renders with tilde-form paths and elapsed time"
    why_human: "CliRunner tests mock all data-layer calls; real yfinance network calls and Rich progress rendering in a live terminal cannot be verified programmatically"
  - test: "Verify TrackContext actually advances the progress bar per-symbol (not just calls advance())"
    expected: "Step [3/3] shows a progress bar that visually advances for each S&P 500 symbol during a real download"
    why_human: "TrackContext.advance() is called in a loop in the implementation, but whether the progress bar renders correctly to a real terminal requires manual observation"
---

# Phase 6: First-Run Init Command Verification Report

**Phase Goal:** A developer can run `bensdorp1 init` on a clean machine, complete the interactive setup, and end with a populated database ready for daily scanning
**Verified:** 2026-05-24T13:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Running `bensdorp1 init` on a clean system produces a populated database with constituents, price history, and cash | VERIFIED | init.py lines 165-208: `get_engine(db_path)`, `run_migrations(engine)`, `get_constituents(engine)`, per-symbol `update_price_data(engine, [symbol])`, `_store_cash(engine, cash)` all called in sequence; test_happy_path confirms exit_code==0 with mocks |
| 2  | Re-running `bensdorp1 init` when DB file already exists prints an error mentioning both recovery paths and exits with code 1 | VERIFIED | init.py lines 99-108: guard checks `db_path.exists()`, calls `print_error("System already initialized.", actions=["Delete the file and run `bensdorp1 init` again.", "Run `bensdorp1 restore PATH` to replace with a backup."])`, then `raise typer.Exit(1)`; test_guard_fires_when_db_exists: exit_code==1, "Delete the file" in output, "bensdorp1 restore" in output — PASSES |
| 3  | Pressing Ctrl+C during cash entry prints 'Operation aborted. No changes were made.' and exits cleanly | VERIFIED | init.py lines 137-160: entire cash block in `try/except KeyboardInterrupt`; abort message exact match; `raise typer.Exit() from None`; test_ctrl_c_during_cash_entry: exit_code==0, message in output, DB not created — PASSES |
| 4  | Cash <= 0 triggers a re-prompt without aborting; only a positive float accepted | VERIFIED | init.py lines 148-150: `if cash <= 0: console.print(Text("Error: Cash must be greater than zero.")); continue`; test_cash_validation_reprompts feeds 0, -100, then 50000 — exit_code==0, error message in output — PASSES |
| 5  | The system_initialized audit event is written with constituent_count, cash, and history_days=220 in the payload | VERIFIED | init.py lines 199-207: `log_event(engine, AuditEventType.SYSTEM_INITIALIZED, payload={"constituent_count": len(constituents), "cash": cash, "history_days": 220})`; test_happy_path: `mock_log_event.called` asserted True |
| 6  | The completion summary displays tilde-form paths, formatted cash, and total elapsed time | VERIFIED | init.py lines 216-226: `_render_kv_block` called with `_tilde_path(db_path)`, `format_price(cash)`, `_format_elapsed(elapsed)`; test_happy_path: "50,000.00" in output — PASSES |
| 7  | Guard scenario: exit code 1 and output contains both recovery path strings | VERIFIED | See Truth #2 above; test passes against actual code |
| 8  | Happy path scenario: exit code 0 with all data-layer calls mocked | VERIFIED | test_happy_path: exit_code==0, "Setup complete" in output, "50,000.00" in output — PASSES |
| 9  | Cash validation scenario: inputs 0, -100 each trigger re-prompt; only positive float accepted | VERIFIED | See Truth #4; test_cash_validation_reprompts passes |
| 10 | Ctrl+C scenario: abort message in output and clean exit | VERIFIED | See Truth #3; test_ctrl_c_during_cash_entry passes |
| 11 | Full test suite stays green after adding new tests | VERIFIED | `uv run pytest --cov=bensdorp1`: 275 passed, 97% coverage; confirmed by direct execution |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/bensdorp1/commands/init.py` | Full interactive init command replacing stub; min_lines=80 | VERIFIED | 237 lines; full implementation; `min_lines=80` far exceeded |
| `tests/test_cli.py` | "init" removed from test_stub_exits_cleanly only | VERIFIED | "init" absent from stub parametrize list (lines 36-53); present in test_help_subcommand_shows_help (line 63) only |
| `tests/test_commands/__init__.py` | Empty package marker (0 bytes) | VERIFIED | Exists; `wc -c` = 0 |
| `tests/test_commands/test_init.py` | Four D-08 scenarios, CliRunner-based, fully mocked | VERIFIED | 93 lines; exactly four test functions — all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `commands/init.py` | `bensdorp1.db` | `from bensdorp1.db import AuditEventType, create_backup, get_engine, log_event, run_migrations` | WIRED | Lines 16-22; all symbols actively called in the command body |
| `commands/init.py` | `bensdorp1.data` | `from bensdorp1.data import get_constituents, update_price_data` | WIRED | Line 15; `get_constituents(engine)` line 174; `update_price_data(engine, [symbol])` line 192 |
| `commands/init.py` | `bensdorp1.ui` | `from bensdorp1.ui import TrackContext, confirm_prompt, feedback, format_price, number_prompt, print_error` | WIRED | Lines 24-31; all used in command body |
| `commands/init.py` | `bensdorp1.ui.styles` | `from bensdorp1.ui.styles import _render_kv_block` (private, one allowed) | WIRED | Line 35; `_render_kv_block(...)` called at line 216 |
| `commands/init.py` | `bensdorp1.db.schema` | `from bensdorp1.db.schema import config as config_table` | WIRED | Line 23; used in `_store_cash` `sqlite_insert(config_table)` at line 74 |
| `tests/test_commands/test_init.py` | `bensdorp1.commands.init` | `patch("bensdorp1.commands.init.DATA_DIR" / get_constituents / etc.)` | WIRED | All patches target import site correctly |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `commands/init.py` | `constituents` (dict[str, str]) | `get_constituents(engine)` → bensdorp1.data (Wikipedia/Slickcharts fetch) | Yes — real network call with DB cache | FLOWING |
| `commands/init.py` | `cash` (float) | `number_prompt()` → user stdin | Yes — user-supplied live input with validation loop | FLOWING |
| `commands/init.py` | price history | `update_price_data(engine, [symbol])` per symbol → yfinance | Yes — real yfinance download | FLOWING |
| `commands/init.py` | `elapsed` (float) | `time.monotonic()` difference | Yes — real wall-clock time | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Module imports cleanly | `uv run python -c "from bensdorp1.commands.init import init; print('import ok')"` | `import ok` | PASS |
| All 4 D-08 tests pass | `uv run pytest tests/test_commands/test_init.py -x -v` | 4 passed in 0.76s | PASS |
| CLI stub tests pass (init not in stub list) | `uv run pytest tests/test_cli.py -x -q` | 35 passed in 0.89s | PASS |
| Full suite green | `uv run pytest --cov=bensdorp1 -q` | 275 passed, 97% coverage | PASS |
| mypy strict on init.py | `uv run mypy src/bensdorp1/commands/init.py --strict` | Success: no issues found in 1 source file | PASS |
| mypy strict on full src/ | `uv run mypy src/ --strict` | Success: no issues found in 41 source files | PASS |
| ruff lint | `uv run ruff check src/ tests/` | All checks passed | PASS |
| ruff format | `uv run ruff format --check src/bensdorp1/commands/init.py` | 1 file already formatted | PASS |
| init --help shows Setup panel | `uv run bensdorp1 --help` | "Setup" panel contains "init" with correct docstring | PASS |

### Probe Execution

Step 7c: SKIPPED — no probe scripts declared in PLAN files or found under `scripts/*/tests/probe-*.sh`. Phase ships application code and tests, not standalone probes.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CMD-01 | 06-01-PLAN.md, 06-02-PLAN.md | `bensdorp1 init` — interactive first-run setup: creates dirs, SQLite DB, fetches constituents, downloads 220-day price history, records initial cash; refuses if DB already exists | SATISFIED | Full implementation in init.py (237 lines); four D-08 test scenarios pass; guard fires on re-run; audit event written; cash persisted in config table |

CMD-01 is the only requirement ID declared across both plans for this phase. No orphaned requirement IDs found.

**Note on REQUIREMENTS.md status column:** CMD-01 is still marked `[ ]` (Pending) and `Pending` in the traceability table. This is a documentation artifact — the implementation is complete. The traceability table was not updated after phase completion. This is informational only; it does not block the phase goal.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TBD, FIXME, XXX, TODO, HACK, PLACEHOLDER markers found in any file modified by this phase. No empty return stubs. No hardcoded empty data passed to rendering paths.

### Human Verification Required

#### 1. Live Terminal Rendering — Full Init Flow

**Test:** Set `BENSDORP1_HOME` to a fresh temp directory and run `bensdorp1 init` interactively in a real terminal (not `CliRunner`). Walk through the prompts: accept Continue, enter a cash amount, confirm, let the download run.

**Expected:** Welcome screen prints with `=` * 64 separator. Cash prompt re-prompts on zero/negative. Multi-step progress shows `[1/3]`, `[2/3]`, `[3/3]` with a progress bar that advances per S&P 500 symbol. Completion summary shows tilde-form paths (e.g., `~/tmp-dir/data/bensdorp1.db`), formatted cash (`$XX,XXX.00`), and elapsed time.

**Why human:** CliRunner tests mock all network and data-layer calls and capture stdout as plain text. Rich's progress bar, spinner animation, and ANSI color rendering in a real terminal cannot be verified programmatically. Step [3/3] TrackContext.advance() is called in a loop but whether the bar visually advances is only observable live.

#### 2. DB State After Real Init

**Test:** After completing the live init above, run `sqlite3 $BENSDORP1_HOME/data/bensdorp1.db ".tables"` and verify table contents.

**Expected:** Tables `prices`, `constituents`, `audit_events`, `config` exist and contain data. `config` table has `key='available_cash'` with the entered value. `audit_events` has a `system_initialized` row with `constituent_count`, `cash`, and `history_days=220` in the JSON payload. `prices` table has rows covering ~220 trading days for S&P 500 symbols.

**Why human:** Tests mock `get_constituents`, `update_price_data`, `log_event`, and `_store_cash` calls. Real DB state after a live run cannot be verified without an actual network download.

### Gaps Summary

No gaps. All must-have truths are verified against the actual codebase. The phase goal is achieved — the `bensdorp1 init` command is fully implemented, all four D-08 test scenarios pass, mypy strict and ruff are clean, and the test suite is green at 275/275 with 97% coverage.

Two human verification items remain because real-terminal rendering and live DB state after a genuine yfinance download cannot be confirmed programmatically.

---

_Verified: 2026-05-24T13:00:00Z_
_Verifier: Claude (gsd-verifier)_
