---
phase: 01-project-skeleton-and-tooling
plan: 02
subsystem: command-stubs
tags: [typer, commands, help, stubs, mypy-strict, ruff]
dependency_graph:
  requires: [bensdorp1-package, entry-point, typer-app-singleton]
  provides: [all-17-commands, CMD-17, command-panel-layout]
  affects: [all-subsequent-command-implementation-plans]
tech_stack:
  added: []
  patterns: [stub-command-pattern, side-effect-import-pattern, approach-b-help-command, ruff-per-file-ignores]
key_files:
  created:
    - src/bensdorp1/commands/init.py
    - src/bensdorp1/commands/restore.py
    - src/bensdorp1/commands/scan.py
    - src/bensdorp1/commands/last.py
    - src/bensdorp1/commands/history.py
    - src/bensdorp1/commands/buy.py
    - src/bensdorp1/commands/sell.py
    - src/bensdorp1/commands/fix.py
    - src/bensdorp1/commands/portfolio.py
    - src/bensdorp1/commands/detail.py
    - src/bensdorp1/commands/cash.py
    - src/bensdorp1/commands/config.py
    - src/bensdorp1/commands/audit.py
    - src/bensdorp1/commands/status.py
    - src/bensdorp1/commands/refresh.py
    - src/bensdorp1/commands/validate.py
    - src/bensdorp1/commands/help.py
  modified:
    - src/bensdorp1/cli.py
    - pyproject.toml
decisions:
  - "Used ruff per-file-ignores for cli.py I001 — intentional import ordering (from before import) is required for side-effect registration pattern; suppressing isort rule is correct here"
  - "Approach B (in-process Click context) for help command — no subprocess invocation; dict key lookup only; type: ignore[attr-defined] required for mypy but attribute exists at runtime"
metrics:
  duration: "2m 40s"
  completed_date: "2026-05-23"
  tasks_completed: 2
  tasks_total: 2
  files_created: 17
  files_modified: 2
---

# Phase 1 Plan 2: Command Stubs Summary

**One-liner:** 16 stub commands (exit 0 + "Not yet implemented.") plus real help command (CMD-17, Approach B in-process Click context) with 5 Rich panels and full mypy-strict compliance.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create all 16 stub command modules | d7dc72b | src/bensdorp1/commands/{init,restore,scan,last,history,buy,sell,fix,portfolio,detail,cash,config,audit,status,refresh,validate}.py |
| 2 | Create help.py (CMD-17) and update cli.py with all 17 side-effect imports | 4c674de | src/bensdorp1/commands/help.py, src/bensdorp1/cli.py, pyproject.toml |

## Verification Results

1. `uv run bensdorp1 --help` — exits 0, shows all 5 panels: Setup, Daily operation, Confirmations, Positions, System
2. `uv run bensdorp1 help scan` — exits 0, output contains "Run daily end-of-day screening"
3. `uv run bensdorp1 help nonexistent` — exits 1, prints "Unknown command: nonexistent" to stderr
4. `uv run bensdorp1 scan` — exits 0, prints "Not yet implemented."
5. `uv run mypy src/` — exits 0, "Success: no issues found in 21 source files"
6. `uv run ruff check .` — exits 0, "All checks passed!"
7. `uv run ruff format --check .` — exits 0, "21 files already formatted"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff I001 import ordering conflict in cli.py**
- **Found during:** Task 2 verification
- **Issue:** ruff's isort rule (I001) flagged cli.py for having `from bensdorp1._app import app` before the `import bensdorp1.commands.*` lines, since isort convention places `import` before `from` in the same section. The auto-fix reordered imports, moving `from` to the end — which is semantically wrong for the entry point re-export.
- **Fix:** Added `[tool.ruff.lint.per-file-ignores]` in pyproject.toml to suppress I001 for `src/bensdorp1/cli.py`. The intentional ordering (`from` first to establish app, then side-effect `import` lines) is a structural requirement of the registration hub pattern.
- **Files modified:** pyproject.toml
- **Commit:** 4c674de

**2. [Rule 1 - Bug] ruff E501 line too long in cli.py comment**
- **Found during:** Task 2 verification (same run as above)
- **Issue:** The comment "# Import all command modules to trigger @app.command() decorations (side-effect imports):" was 89 chars, exceeding the 88-char limit.
- **Fix:** Shortened comment to "# Import all command modules to trigger @app.command() decorations:" (68 chars).
- **Files modified:** src/bensdorp1/cli.py
- **Commit:** 4c674de

## Known Stubs

16 stub commands intentionally print "Not yet implemented." and exit 0. This is per-spec (D-05) — stubs are expected placeholders for future implementation phases. Not tracked as defects.

## Threat Flags

No new threat surface beyond the plan's threat model (T-02-01 through T-02-SC). The help command uses dict key lookup only — no subprocess invocation; user input cannot escape to shell.

## Self-Check: PASSED

- src/bensdorp1/commands/help.py: FOUND
- src/bensdorp1/commands/scan.py: FOUND
- src/bensdorp1/commands/init.py: FOUND
- src/bensdorp1/commands/validate.py: FOUND
- src/bensdorp1/cli.py: FOUND (17 side-effect imports)
- pyproject.toml: FOUND (per-file-ignores added)
- commit d7dc72b: FOUND (feat(01-02): create 16 stub command modules)
- commit 4c674de: FOUND (feat(01-02): add help command (CMD-17) and wire all 17 imports in cli.py)
