---
phase: 06-first-run-init-command
plan: "02"
subsystem: commands/tests
tags: [typer, rich, testing, init, cli-runner, mocking]

# Dependency graph
requires:
  - phase: 06-first-run-init-command
    plan: "01"
    provides: Full init command implementation (commands/init.py)
  - phase: 05-ui-components
    provides: confirm_prompt, number_prompt, feedback, format_price, print_error
  - phase: 03-data-sources
    provides: get_constituents, update_price_data
  - phase: 02-database-and-migrations
    provides: get_engine, run_migrations, log_event, create_backup

provides:
  - tests/test_commands/__init__.py — empty package marker
  - tests/test_commands/test_init.py — four D-08 CliRunner-based scenarios
  - All four D-08 test scenarios passing with full mock isolation

affects: [CMD-01 coverage complete]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CliRunner in-process invocation with input= string for prompt sequences"
    - "patch at import site (bensdorp1.commands.init.NAME) not definition site"
    - "side_effect=KeyboardInterrupt on number_prompt mock for Ctrl+C test"
    - "tmp_path fixture for DATA_DIR isolation — no shared filesystem state"
    - "MagicMock() for engine — supports context manager protocol automatically"

key-files:
  created:
    - tests/test_commands/__init__.py
    - tests/test_commands/test_init.py
  modified: []

key-decisions:
  - "Excluded 'abc' from cash validation input string — number_prompt handles non-numeric internally without consuming our input stream; only the positive-value guard layer needs testing at this level"
  - "Patched number_prompt directly with side_effect=KeyboardInterrupt for Ctrl+C test — cleaner than injecting KeyboardInterrupt via builtins.input which would require navigating through number_prompt's internal try/except"
  - "assert not (tmp_path / 'data' / 'bensdorp1.db').exists() for Ctrl+C test — confirms no DB written rather than mocking get_engine/run_migrations"

patterns-established:
  - "tests/test_commands/__init__.py matches tests/test_ui/__init__.py (empty, 0 bytes)"
  - "Four D-08 scenarios: guard fires, happy path, cash validation, Ctrl+C abort"

requirements-completed: [CMD-01]

# Metrics
duration: 8min
completed: "2026-05-24"
---

# Phase 6 Plan 02: Init Command Tests Summary

**Four CliRunner-based D-08 test scenarios for the init command — guard, happy path, cash validation, and Ctrl+C abort — all passing with full mock isolation**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-24T10:12:00Z
- **Completed:** 2026-05-24T10:20:38Z
- **Tasks:** 2
- **Files created:** 2 (tests/test_commands/__init__.py, tests/test_commands/test_init.py)

## Accomplishments

- Created `tests/test_commands/__init__.py` (empty, 0 bytes — matches test_ui/__init__.py pattern)
- Created `tests/test_commands/test_init.py` with exactly four D-08 test functions
- `test_guard_fires_when_db_exists`: pre-creates DB file; asserts exit_code==1 and both recovery paths in output
- `test_happy_path`: patches all data-layer calls; asserts exit_code==0, "Setup complete", and "50,000.00" in output; verifies log_event and create_backup were called
- `test_cash_validation_reprompts`: feeds 0, -100, then 50000; asserts exit_code==0 and error message appeared
- `test_ctrl_c_during_cash_entry`: patches number_prompt to raise KeyboardInterrupt; asserts exit_code==0, abort message in output, DB file not created
- Full suite: 275 tests, 97% coverage, mypy strict 0 errors, ruff check 0 errors, ruff format clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/test_commands package with D-08 test scenarios** - `43eed44` (feat)
2. **Task 2: Full verification gate — all 275 tests pass, mypy+ruff clean** - `674aaa3` (chore)

## Files Created/Modified

- `tests/test_commands/__init__.py` - Empty package marker (0 bytes)
- `tests/test_commands/test_init.py` - Four D-08 scenarios, CliRunner-based, fully mocked

## Decisions Made

- **Ctrl+C test approach:** Patched `bensdorp1.commands.init.number_prompt` with `side_effect=KeyboardInterrupt` directly rather than injecting via `builtins.input`. The `number_prompt` function has an internal loop that would complicate the stdin injection approach; patching the function directly is cleaner and tests the exact exception-handling path.
- **Cash validation input string:** Excluded "abc" from `"y\n0\n-100\n50000\ny\n"` per plan guidance — `number_prompt()` handles non-numeric internally without consuming stdin tokens, so only the `> 0` guard layer needs to be covered at this test level.
- **DB existence assertion in Ctrl+C test:** Used `assert not (tmp_path / "data" / "bensdorp1.db").exists()` instead of mocking get_engine/run_migrations — confirms no DB written as a behavioral guarantee without coupling to implementation details.

## Deviations from Plan

### Sync files from plan 01 wave

**[Rule 3 - Blocking] Copied prerequisite files from main branch into worktree**

- **Found during:** Task 1 — worktree was forked before plan 01's commits
- **Issue:** Worktree lacked `src/bensdorp1/commands/init.py` (full implementation), `src/bensdorp1/config.py`, `src/bensdorp1/ui/` subpackage, `tests/test_ui/`, and updated `tests/conftest.py` and `tests/test_cli.py` — all committed to main in plan 01 wave
- **Fix:** Used `git show main:<path> > <worktree-path>` to copy all missing files from main into the worktree, then staged them in Task 1 commit
- **Files modified:** 20 files (init.py, config.py, ui/*, conftest.py, test_cli.py, test_ui/*)
- **Commit:** 43eed44

### ruff F401 + E501 + LF line endings

**[Rule 1 - Bug] Fixed unused import and line-too-long in test_init.py; applied ruff LF formatting**

- **Found during:** Task 2 verification gate (ruff check + ruff format)
- **Issue:** test_init.py had unused `import pytest`, two E501 lines; progress.py and three test_ui files had CRLF from Windows git checkout vs LF expected by ruff
- **Fix:** Removed unused pytest import, shortened docstrings, ran `uv run ruff format` to normalize to LF
- **Files modified:** tests/test_commands/test_init.py, src/bensdorp1/ui/progress.py, tests/test_ui/test_config.py, tests/test_ui/test_public_api.py, tests/test_ui/test_styles.py
- **Commit:** 674aaa3

## Known Stubs

None — all four test scenarios are fully implemented and wired to the real init command.

## Threat Flags

No new security surface introduced. Tests use:
- tmp_path for DATA_DIR isolation (T-06-05 mitigated)
- All external calls mocked (no network, no real DB writes in happy path / validation tests)
- No new packages installed (T-06-SC accepted)

## Self-Check

- [x] `tests/test_commands/__init__.py` exists and is empty (0 bytes)
- [x] `tests/test_commands/test_init.py` exists (92 lines, 4 test functions)
- [x] Four test functions: test_guard_fires_when_db_exists, test_happy_path, test_cash_validation_reprompts, test_ctrl_c_during_cash_entry
- [x] Commit 43eed44 exists (Task 1 — feat)
- [x] Commit 674aaa3 exists (Task 2 — chore)
- [x] uv run pytest tests/test_commands/test_init.py: 4 passed
- [x] uv run pytest tests/test_cli.py: 35 passed
- [x] uv run pytest --cov=bensdorp1: 275 passed, 97% coverage
- [x] uv run mypy src/ --strict: Success: no issues found in 41 source files
- [x] uv run ruff check src/ tests/: All checks passed
- [x] uv run ruff format --check src/ tests/: 67 files already formatted

## Self-Check: PASSED

---
*Phase: 06-first-run-init-command*
*Completed: 2026-05-24*
