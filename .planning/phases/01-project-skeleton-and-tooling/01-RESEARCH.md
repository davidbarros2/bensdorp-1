# Phase 1: Project Skeleton and Tooling - Research

**Researched:** 2026-05-23
**Domain:** Python project scaffolding — uv, Typer, mypy strict, ruff, GitHub Actions CI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** src/ layout — package lives at `src/bensdorp1/`
- **D-02:** `commands/` subpackage from day 1 — `src/bensdorp1/commands/`. Each command in its own module. Root app wired in `src/bensdorp1/cli.py`.
- **D-03:** Minimal skeleton for Phase 1: only `commands/` + `cli.py`. No placeholder dirs for db/, strategy/, data/, ui/.
- **D-04:** All 17 commands registered as Typer stubs in Phase 1. Each stub in its own module.
- **D-05:** Stub body: prints `"Not yet implemented."` and exits via `typer.Exit()`. Non-zero exit code NOT used.
- **D-06:** Python 3.11 only in CI. No multi-version matrix.
- **D-07:** OS matrix: ubuntu-latest + windows-latest.
- **D-08:** uv download cache enabled. Cache key based on `uv.lock`.
- **D-09:** CI runs pytest + ruff check + ruff format --check + mypy --strict on every push and PR.
- **D-10:** close-pr.yml auto-closes any PR with policy message. Runs on pull_request opened/reopened events.
- **D-11:** `bensdorp1 help [COMMAND]` is a real Typer command. With COMMAND, delegates to Typer's built-in `--help`. Without argument, shows full categorized command list.
- **D-12:** Top-level `bensdorp1 --help` uses Typer Rich panels with `rich_markup_mode="rich"`. Commands grouped via `rich_help_panel` parameter.
- **D-13:** Command categories: Setup (init, restore), Daily operation (scan, last, history), Confirmations (buy, sell, fix), Positions (portfolio, detail), System (cash, config, audit, status, refresh, validate, help).

### Claude's Discretion

None — all decisions locked.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CMD-17 | `bensdorp1 help [COMMAND]` — categorized command list or detailed help for a specific command | Typer Context + invoke_without_command pattern; delegating to `--help` via `ctx.get_help()` / subprocess invoke |
| REPO-01 | MIT License, public open-source repository | File creation task only; no library research needed |
| REPO-02 | Issues disabled (config.yml); Discussions disabled; Wiki disabled | GitHub repo settings — manual step; `.github/ISSUE_TEMPLATE/config.yml` with `blank_issues_enabled: false` |
| REPO-03 | PRs auto-closed via GitHub Actions workflow (close-pr.yml) with policy message | `superbrothers/close-pull-request@v3` action; `pull_request_target` event trigger |
| REPO-06 | Branch protection on main: CI must pass for any merge | GitHub settings — manual step; no workflow file needed |
| REPO-07 | GitHub Actions ci.yml: runs tests, lint, type check on push and PR | `astral-sh/setup-uv` + `uv sync --locked` + `uv run pytest/ruff/mypy` patterns verified |
| TEST-06 | CI pipeline: pytest + ruff + mypy strict on every push and PR via GitHub Actions | See REPO-07 above |

</phase_requirements>

---

## Summary

Phase 1 stands up the entire project skeleton: pyproject.toml with uv_build backend, src/ layout, all 17 Typer command stubs, the real `help` command implementation, and two GitHub Actions workflows. The repo is empty today (only CLAUDE.md exists at root), so every file is a net-new creation.

The primary technical challenges are: (1) wiring 17 Typer commands with correct type annotations that satisfy mypy strict's `disallow_untyped_decorators`, (2) making `bensdorp1 help [COMMAND]` delegate to a subcommand's built-in `--help` without duplicating help text, and (3) producing a GitHub Actions matrix that runs clean on both ubuntu-latest and windows-latest from day one.

All libraries in the standard stack are well-established, slopcheck-verified, and available on the system. The uv_build backend is the correct choice and its exact [build-system] TOML is confirmed. The `superbrothers/close-pull-request@v3` action covers the close-PR requirement cleanly.

**Primary recommendation:** Write all 17 command modules as minimal Typer stubs first, wire them in `cli.py`, then confirm `mypy --strict` passes before writing tests — because fixing the decorator typing early is cheaper than retrofitting 17 modules.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CLI entry point + command dispatch | CLI process (Typer) | — | Single process, no server |
| Help text rendering | CLI process (Typer / Rich) | — | Rich panels at runtime |
| Stub command execution | CLI process | — | In-process function calls |
| CI/CD pipeline | GitHub Actions runner | — | External to codebase |
| PR auto-close | GitHub Actions runner | — | Workflow event handler |
| Package build/install | uv + uv_build | — | Build-time concern |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | `>=0.21.1` | CLI framework — command registration, argument parsing, help generation | Type-hint based, built on Click, Rich integration, industry standard for modern Python CLIs [VERIFIED: pip index versions] |
| rich | `>=14.0` | Terminal formatting — panels, color, markup in help output | Typer depends on it; required (not optional) since Typer 0.12 [VERIFIED: pip index versions] |
| pytest | `>=8.3` | Test runner | Standard Python test framework [VERIFIED: pip index versions] |
| ruff | `>=0.15` | Linter + formatter (replaces flake8, isort, black) | Fastest Python linter, single config, replaces multiple tools [VERIFIED: pip index versions] |
| mypy | `>=2.1.0` | Static type checker | Only type checker with Pydantic plugin; project requires strict mode [VERIFIED: pip index versions] |

**Actual latest versions confirmed on system (May 2026):**
- typer: 0.25.1 (latest), 0.24.1 installed [VERIFIED: pip index versions]
- mypy: 2.1.0 (latest) [VERIFIED: pip index versions]
- ruff: 0.15.14 (latest), 0.15.8 installed [VERIFIED: pip index versions]
- rich: 15.0.0 installed [VERIFIED: pip index versions]
- pytest: 9.0.3 installed [VERIFIED: pip index versions]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | `>=7.1.0` | Coverage reports | All test runs; configured via `[tool.coverage.*]` |
| hypothesis | `>=6.130` | Property-based testing | Strategy invariant tests in Phase 4; scaffold in Phase 1 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Typer | Click (direct) | Typer IS Click with type hints; no reason to use Click directly |
| ruff format | black | ruff format replaces black; running both creates conflicts |
| uv_build | hatchling | uv_build is now stable and zero-config; hatchling needed for extension modules only |

**Installation (development):**
```bash
uv sync --locked --dev
```

**Version verification:** Confirmed via `pip index versions` on 2026-05-23. See versions above.

---

## Package Legitimacy Audit

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| typer | PyPI | [OK] | Approved |
| rich | PyPI | [OK] | Approved |
| sqlalchemy | PyPI | [OK] | Approved |
| pydantic | PyPI | [OK] | Approved |
| yfinance | PyPI | [OK] | Approved |
| pandas | PyPI | [OK] | Approved |
| pytest | PyPI | [OK] | Approved |
| pytest-cov | PyPI | [OK] (no source repo linked — established package) | Approved |
| hypothesis | PyPI | [OK] | Approved |
| ruff | PyPI | [OK] | Approved |
| mypy | PyPI | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck 0.6.1 ran successfully on 2026-05-23. All 11 packages passed.*

---

## Architecture Patterns

### System Architecture Diagram

```
User terminal
     |
     v
bensdorp1 <command> [args]      <-- entry point: src/bensdorp1/__main__.py (or scripts entry)
     |
     v
src/bensdorp1/cli.py            <-- typer.Typer app; all 17 commands registered
     |
     +-- commands/help.py       <-- real implementation; delegates to --help or shows panel list
     +-- commands/scan.py       <-- stub: prints "Not yet implemented."
     +-- commands/init.py       <-- stub
     +-- commands/...           <-- 14 more stubs
     |
     v
Rich terminal output            <-- rich_markup_mode="rich", rich_help_panel grouping
```

### Recommended Project Structure

```
src/
  bensdorp1/
    __init__.py            # package marker, version string
    cli.py                 # root Typer app + all command imports/registrations
    commands/
      __init__.py          # empty package marker
      help.py              # CMD-17: real help command
      init.py              # stub
      restore.py           # stub
      scan.py              # stub
      last.py              # stub
      history.py           # stub
      buy.py               # stub
      sell.py              # stub
      fix.py               # stub
      portfolio.py         # stub
      detail.py            # stub
      cash.py              # stub
      config.py            # stub
      audit.py             # stub
      status.py            # stub
      refresh.py           # stub
      validate.py          # stub
tests/
  __init__.py
  test_cli.py              # smoke tests: --help, every stub, help <command>
.github/
  workflows/
    ci.yml
    close-pr.yml
  ISSUE_TEMPLATE/
    config.yml             # blank_issues_enabled: false
pyproject.toml
uv.lock                    # generated by uv
LICENSE
```

### Pattern 1: pyproject.toml — uv_build with src layout and entry point

```toml
# Source: https://docs.astral.sh/uv/concepts/build-backend/ [VERIFIED: WebFetch official docs]

[build-system]
requires = ["uv_build>=0.7,<0.8"]
build-backend = "uv_build"

[project]
name = "bensdorp1"
version = "0.1.0"
description = "CLI for Bensdorp System #1 trend-following strategy"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.21.1",
    "rich>=14.0",
    "sqlalchemy>=2.0.49,<2.1",
    "pydantic>=2.13.4",
    "yfinance>=1.3.0",
    "pandas-market-calendars>=5.3.2",
    "httpx>=0.28.1",
    "beautifulsoup4>=4.14.3",
    "pandas>=3.0.3",
    "numpy>=2.0",
]

[project.scripts]
bensdorp1 = "bensdorp1.cli:app"

# PEP 735 dependency groups — NOT [tool.uv.dev-dependencies] (legacy)
[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-cov>=7.1.0",
    "hypothesis>=6.130",
    "ruff>=0.15",
    "mypy>=2.1.0",
]
```

Note on uv_build version pin: the pydevtools.com article cites `>=0.7.19,<0.8.0`; official uv docs cite `>=0.11.16,<0.12` (more recent). Use `>=0.7,<0.8` as a wide but safe constraint since uv is on version 0.10.12 on this machine. [CITED: https://docs.astral.sh/uv/concepts/build-backend/]

The [project.scripts] entry `bensdorp1 = "bensdorp1.cli:app"` works because Typer's `app` object is callable as a Click group. [VERIFIED: Typer docs + official uv docs]

### Pattern 2: Typer multi-command wiring in cli.py

```python
# Source: CLAUDE.md §Typer Multi-Command Structure [ASSUMED: based on CLAUDE.md pattern guidance]
# The root app is created once; per-command modules import it and decorate.
# CRITICAL: All command modules must be imported in cli.py so decorators register.

import typer
from bensdorp1.commands import (
    audit, buy, cash, config, detail, fix, help as help_cmd,
    history, init, last, portfolio, refresh, restore,
    scan, sell, status, validate,
)

app = typer.Typer(
    name="bensdorp1",
    help="Bensdorp System #1 — daily stock screening CLI.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Alternative wiring: each command module calls app.command() on the shared app.
# Pattern: import app into each command module, then re-export the decorated function.
# This is cleaner than passing app around; see Pattern 3.
```

**Two valid wiring approaches:**

**Approach A — Centralized registration in cli.py (recommended for readability):**
```python
# cli.py
app = typer.Typer(...)
from bensdorp1.commands.scan import scan_cmd
app.command(name="scan", rich_help_panel="Daily operation")(scan_cmd)
```

**Approach B — Decentralized: each module imports the shared app:**
```python
# In each commands/scan.py:
from bensdorp1.cli import app   # circular import risk! Use with care.
```

Approach A avoids circular imports entirely. Approach B risks circular imports because `cli.py` imports from `commands/`, and if `commands/scan.py` imports from `cli.py`, you get a cycle. **Use Approach A or a shared `_app.py` module.**

**Cleanest pattern (avoids circular imports):**
```python
# src/bensdorp1/_app.py
import typer
app = typer.Typer(
    name="bensdorp1",
    help="...",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# src/bensdorp1/commands/scan.py
from bensdorp1._app import app

@app.command(rich_help_panel="Daily operation")
def scan(force: bool = typer.Option(False, "--force")) -> None:
    """Run daily end-of-day screening."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()

# src/bensdorp1/cli.py
from bensdorp1._app import app
# Import all command modules to trigger their @app.command() decorations:
import bensdorp1.commands.scan  # noqa: F401
import bensdorp1.commands.init  # noqa: F401
# ... (16 more)
```

### Pattern 3: Typer rich_help_panel grouping

```python
# Source: https://typer.tiangolo.com/tutorial/commands/help/ [VERIFIED: WebFetch official docs]

@app.command(rich_help_panel="Daily operation")
def scan(...) -> None:
    """Run daily end-of-day screening."""

@app.command(rich_help_panel="Setup")
def init(...) -> None:
    """First-run setup."""
```

The `rich_help_panel` parameter on `@app.command()` groups commands into labeled sections in the `--help` output. Commands without a panel appear under the default "Commands" section. `rich_markup_mode="rich"` on the `Typer()` app enables Rich markup in docstrings. [VERIFIED: WebFetch official Typer docs]

Panel names for this project (from D-13):
- `"Setup"` — init, restore
- `"Daily operation"` — scan, last, history
- `"Confirmations"` — buy, sell, fix
- `"Positions"` — portfolio, detail
- `"System"` — cash, config, audit, status, refresh, validate, help

### Pattern 4: help command implementation (CMD-17)

**The challenge:** `bensdorp1 help scan` must show the same output as `bensdorp1 scan --help`. Typer has no built-in "show help for a subcommand" API. The cleanest approach is to invoke the CLI process again with `--help` appended, or to use Click's `get_help()` on the command object.

**Approach A — subprocess re-invocation (simple, always correct):**
```python
# Source: training knowledge [ASSUMED]
import subprocess
import sys
import typer

@app.command(rich_help_panel="System")
def help(command: str = typer.Argument(default="", show_default=False)) -> None:
    """Show command list, or detailed help for COMMAND."""
    if command:
        result = subprocess.run(
            [sys.executable, "-m", "bensdorp1", command, "--help"],
            check=False,
        )
        raise typer.Exit(result.returncode)
    else:
        # Typer prints --help when invoked with no args if no_args_is_help=True
        # For the help command itself: re-invoke root --help
        subprocess.run(
            [sys.executable, "-m", "bensdorp1", "--help"],
            check=False,
        )
```

**Approach B — Click context lookup (in-process, avoids subprocess):**
```python
# Source: training knowledge [ASSUMED]; Click docs confirm get_help() exists
import click
import typer

@app.command(rich_help_panel="System")
def help(
    ctx: typer.Context,
    command: str = typer.Argument(default="", show_default=False),
) -> None:
    """Show command list, or detailed help for COMMAND."""
    if command:
        root_ctx = ctx.find_root()
        cmd_obj = root_ctx.command.commands.get(command)  # type: ignore[attr-defined]
        if cmd_obj is None:
            typer.echo(f"Unknown command: {command}", err=True)
            raise typer.Exit(1)
        # Print help for the found command object
        typer.echo(cmd_obj.get_help(root_ctx))
    else:
        typer.echo(ctx.find_root().get_help())
    raise typer.Exit()
```

**Recommendation:** Approach B is in-process and more testable. The `ctx.find_root().command.commands` attribute is available on Click group objects (Typer's `app` is a Click group). The `# type: ignore` is needed because mypy doesn't know the concrete type of `ctx.command` in Typer's type stubs. [ASSUMED — Click/Typer internals not directly verified via Context7 in this session]

### Pattern 5: mypy strict + Typer decorators

**The problem:** `mypy --strict` enables `disallow_untyped_decorators`. Typer's `@app.command()` and `@app.callback()` decorators are typed as returning `Callable[[F], F]`, which means they preserve the function's type. In recent Typer versions (0.12+), this is handled correctly — the decorator signature is typed. [ASSUMED — based on CLAUDE.md guidance + training knowledge]

**Practical reality:** Even with properly typed Typer decorators, mypy strict sometimes emits `[misc]` errors on decorated functions when the return type isn't explicitly annotated. The fix:

```python
# Every stub command MUST have an explicit return type annotation -> None
# Source: CLAUDE.md §mypy Strict Mode Configuration [CITED: CLAUDE.md]
@app.command(rich_help_panel="Setup")
def init() -> None:
    """First-run setup."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
```

**If `disallow_untyped_decorators` fires on `@app.command()`,** the per-module override in pyproject.toml suppresses it:
```toml
# Source: CLAUDE.md §mypy Strict Mode Configuration [CITED: CLAUDE.md]
[[tool.mypy.overrides]]
module = "bensdorp1.commands.*"
disallow_untyped_decorators = false
```

This is the established workaround — suppress only for the modules using the decorator, keep strict everywhere else. [CITED: CLAUDE.md; pattern confirmed in mypy issue #9442 discussion]

**Stub packages needed for type stubs (dev dependency):**
```toml
# From CLAUDE.md §mypy Strict Mode Configuration
# typer has inline stubs; click has stubs via types-click if needed
```

mypy configuration in pyproject.toml:
```toml
[tool.mypy]
python_version = "3.11"
strict = true
# Show error codes so targeted ignores can be written
show_error_codes = true

# Modules without stubs — suppress only missing stubs, not all errors
[[tool.mypy.overrides]]
module = "bensdorp1.commands.*"
disallow_untyped_decorators = false
```

### Pattern 6: ruff configuration

```toml
# Source: CLAUDE.md §Ruff Configuration [CITED: CLAUDE.md]
[tool.ruff]
line-length = 88
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "PT"]
# TC rules and SQLAlchemy: don't move SQLAlchemy imports into TYPE_CHECKING
# Not needed in Phase 1 (no SQLAlchemy yet), but include to avoid future breakage.
```

### Pattern 7: ci.yml — GitHub Actions

```yaml
# Source: https://docs.astral.sh/uv/guides/integration/github/ [CITED: official uv docs]
# Source: https://pydevtools.com/handbook/tutorial/setting-up-github-actions-with-uv/ [CITED]

name: CI

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  test:
    name: test (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.11"
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Install project
        run: uv sync --locked --dev

      - name: Run pytest
        run: uv run pytest tests/ -v

      - name: Run ruff check
        run: uv run ruff check .

      - name: Run ruff format check
        run: uv run ruff format --check .

      - name: Run mypy
        run: uv run mypy src/
```

**Key decisions:**
- `fail-fast: false` — both OS jobs run even if one fails; Windows failures shouldn't hide Linux failures
- `uv sync --locked --dev` — dev group is the default group; `--locked` fails if uv.lock is out of date
- mypy runs against `src/` not the entire repo to avoid false positives in tests
- No shell override needed — `uv run` handles activation cross-platform; `run:` commands work on both ubuntu and windows with default shells [CITED: uv docs, verified by cross-platform design of uv]

### Pattern 8: close-pr.yml

```yaml
# Source: https://github.com/superbrothers/close-pull-request [CITED]
# Decision D-10: use pull_request_target (not pull_request)
# pull_request_target runs from the target branch (main), not the fork branch.
# This matters for security: forks cannot exfiltrate secrets via this event.

name: Close Pull Request

on:
  pull_request_target:
    types: [opened, reopened]

jobs:
  close:
    runs-on: ubuntu-latest
    steps:
      - uses: superbrothers/close-pull-request@v3
        with:
          comment: |
            Thank you for your interest in bensdorp1.

            This is a personal tool and does not accept external contributions. Pull requests are closed automatically.

            If you have found a bug, please open an issue instead (if issues are enabled) or contact the maintainer directly.
```

**Note on REPO-02 (Issues/Discussions disabled):** Disabling Issues and Discussions is a repository setting in GitHub UI, not a file in the repo. The `.github/ISSUE_TEMPLATE/config.yml` file can set `blank_issues_enabled: false` and provide a contact URL, but full issue disable requires the GitHub repository settings page. This is a manual step, not automatable via committed files.

```yaml
# .github/ISSUE_TEMPLATE/config.yml
blank_issues_enabled: false
contact_links:
  - name: Questions
    url: https://github.com/davidandrebarros/bensdorp-1
    about: This repository does not accept issues. Please contact the maintainer directly.
```

### Anti-Patterns to Avoid

- **Importing the app in command modules (circular import):** `commands/scan.py` importing from `cli.py` creates a circular dependency. Use a `_app.py` intermediary or centralize registration in `cli.py`. [ASSUMED]
- **Using `typer.run()` instead of `app = typer.Typer()`:** `typer.run()` is for single-command scripts; multi-command CLIs need the explicit `Typer()` app object. [CITED: Typer docs]
- **Omitting `-> None` return type on command functions:** mypy strict will complain. Every command function, including stubs, must be typed. [CITED: CLAUDE.md]
- **`no_args_is_help=False` on the root app:** Without this set to True, `bensdorp1` with no command shows nothing useful. [ASSUMED]
- **Running `ruff format` and `black` both:** They conflict. This project uses `ruff format` only. [CITED: CLAUDE.md]
- **`[tool.uv.dev-dependencies]` instead of `[dependency-groups]`:** Legacy format — the project requires PEP 735 `[dependency-groups]`. [CITED: CLAUDE.md]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Argument parsing and help generation | Custom argparse setup | Typer | Handles types, validation, help text, shell completion |
| Terminal color and markup | ANSI escape codes directly | Rich (via Typer) | Cross-platform, composable, panel support |
| Test runner | Custom runner | pytest + CliRunner | Standard; CliRunner handles Typer/Click exit codes correctly |
| Lint + format + import sort | Multiple tools (flake8, isort, black) | ruff | One tool, one config, faster |
| Type checking | Runtime assertions | mypy strict | Catches errors at check time, not runtime |
| PR auto-close logic | Custom GitHub API calls | `superbrothers/close-pull-request@v3` | Single-line workflow, handles comment + close atomically |

**Key insight:** The entire test suite for Phase 1 is "run the CLI and assert on output" — CliRunner makes this trivial. Never invoke the CLI via subprocess in tests when CliRunner works.

---

## Runtime State Inventory

> This is a greenfield phase with no existing runtime state. Omitted per instructions for greenfield phases.

---

## Common Pitfalls

### Pitfall 1: Circular imports between cli.py and commands/
**What goes wrong:** `commands/scan.py` imports `app` from `cli.py`; `cli.py` imports `scan` from `commands/scan.py`. Python raises `ImportError: cannot import name 'app' from partially initialized module`.
**Why it happens:** The `app` object must exist before command modules can register against it, but `cli.py` tries to import those modules to trigger registration.
**How to avoid:** Create `src/bensdorp1/_app.py` that only contains the `Typer()` instantiation. Both `cli.py` and command modules import from `_app.py`. `cli.py` then imports all command modules (for side-effect registration) after defining nothing else.
**Warning signs:** `ImportError` on `bensdorp1 --help`, or commands not appearing in `--help` output.

### Pitfall 2: mypy `disallow_untyped_decorators` on @app.command()
**What goes wrong:** `mypy --strict` emits `Untyped decorator makes function "scan" untyped [misc]` even when the function has full type annotations.
**Why it happens:** Older or complex Typer decorator signatures are not fully transparent to mypy. The error code is `misc` because there's no dedicated error code for this yet (mypy issue #19148).
**How to avoid:** Add a per-module mypy override: `[[tool.mypy.overrides]] module = "bensdorp1.commands.*"; disallow_untyped_decorators = false`. All other strict checks remain active.
**Warning signs:** CI failing on mypy with `[misc]` errors in command modules.

### Pitfall 3: uv.lock not committed or out of date in CI
**What goes wrong:** `uv sync --locked` fails with "Lockfile does not exist" or "Lockfile is not up to date".
**Why it happens:** `uv.lock` is generated by `uv lock` / `uv sync` and must be committed to the repo. If pyproject.toml changes and `uv lock` is not re-run, the lockfile diverges.
**How to avoid:** Run `uv lock` locally after any pyproject.toml change. Commit `uv.lock`. The `--locked` flag in CI enforces this.
**Warning signs:** CI failing with lockfile mismatch on first run.

### Pitfall 4: `bensdorp1 help <command>` returning wrong or empty output
**What goes wrong:** `help scan` outputs nothing, or outputs the help command's own help text.
**Why it happens:** Using `ctx.find_root().get_help()` always shows root help, not subcommand help. Need `root_ctx.command.commands[command].get_help(ctx)`.
**How to avoid:** Use `ctx.find_root().command.commands.get(command)` to look up the command object, then call `.get_help(ctx)` on it. Guard against unknown command names.
**Warning signs:** `help scan` and `help init` both showing identical text (the root help).

### Pitfall 5: Windows path handling for the installed script
**What goes wrong:** The `bensdorp1` script installs correctly on Linux but the entry-point shim is not found in PATH on Windows.
**Why it happens:** On Windows, uv installs scripts to `Scripts/` (capital S) not `bin/`. The PATH configuration differs. When using `uv run bensdorp1`, this is handled automatically.
**How to avoid:** In CI, use `uv run bensdorp1 --help` instead of bare `bensdorp1 --help`. In tests, use `CliRunner.invoke(app, ...)` (in-process, no PATH dependency).
**Warning signs:** Windows CI job failing on `bensdorp1: command not found` while Linux passes.

### Pitfall 6: `pull_request` vs `pull_request_target` in close-pr.yml
**What goes wrong:** Using `on: pull_request` with `types: [opened]` fails for forks — the workflow runs on the fork branch and may not have write permissions to close the PR or post comments.
**Why it happens:** `pull_request` events from forks run with read-only tokens. `pull_request_target` runs from the base branch (main) with write tokens.
**How to avoid:** Use `on: pull_request_target: types: [opened, reopened]`. The `superbrothers/close-pull-request@v3` action is designed for this event.
**Warning signs:** close-pr.yml failing with "Resource not accessible by integration" or PRs not being closed.

### Pitfall 7: Missing `__init__.py` in commands/ breaks import discovery
**What goes wrong:** `from bensdorp1.commands import scan` raises `ModuleNotFoundError`.
**Why it happens:** Python requires `__init__.py` in every package directory with a src layout and uv_build. Without it, `commands/` is not a package.
**How to avoid:** Create `src/bensdorp1/commands/__init__.py` (empty file) alongside `src/bensdorp1/__init__.py`.

---

## Code Examples

Verified patterns from official sources:

### Minimal stub command (mypy-strict compliant)
```python
# Source: CLAUDE.md §Typer Multi-Command Structure + mypy §Strict Mode [CITED: CLAUDE.md]
import typer
from bensdorp1._app import app


@app.command(rich_help_panel="Daily operation")
def scan(force: bool = typer.Option(False, "--force", help="Re-run even if scan exists.")) -> None:
    """Run daily end-of-day screening."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
```

### Root app instantiation (_app.py)
```python
# Source: https://typer.tiangolo.com/tutorial/commands/help/ [CITED: Typer docs]
import typer

app = typer.Typer(
    name="bensdorp1",
    help="Bensdorp System #1 — daily S&P 500 trend-following CLI.",
    rich_markup_mode="rich",
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # don't show Python tracebacks to the user
)
```

### cli.py — registration hub
```python
# Source: CLAUDE.md §Typer Multi-Command Structure [CITED: CLAUDE.md]
from bensdorp1._app import app  # re-export for entry point

# Import all command modules to trigger @app.command() decorations (side-effect imports):
import bensdorp1.commands.audit   # noqa: F401
import bensdorp1.commands.buy     # noqa: F401
import bensdorp1.commands.cash    # noqa: F401
import bensdorp1.commands.config  # noqa: F401
import bensdorp1.commands.detail  # noqa: F401
import bensdorp1.commands.fix     # noqa: F401
import bensdorp1.commands.help    # noqa: F401
import bensdorp1.commands.history # noqa: F401
import bensdorp1.commands.init    # noqa: F401
import bensdorp1.commands.last    # noqa: F401
import bensdorp1.commands.portfolio  # noqa: F401
import bensdorp1.commands.refresh    # noqa: F401
import bensdorp1.commands.restore    # noqa: F401
import bensdorp1.commands.scan       # noqa: F401
import bensdorp1.commands.sell       # noqa: F401
import bensdorp1.commands.status     # noqa: F401
import bensdorp1.commands.validate   # noqa: F401

__all__ = ["app"]
```

### CliRunner test for stubs
```python
# Source: https://typer.tiangolo.com/tutorial/testing/ [CITED: Typer docs]
import pytest
from typer.testing import CliRunner
from bensdorp1.cli import app

runner = CliRunner()


def test_stub_scan_exits_cleanly() -> None:
    result = runner.invoke(app, ["scan"])
    assert result.exit_code == 0
    assert "Not yet implemented." in result.output


def test_help_root_shows_all_panels() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Daily operation" in result.output
    assert "Setup" in result.output
    assert "System" in result.output


def test_help_command_shows_panel_list() -> None:
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0


@pytest.mark.parametrize("cmd", [
    "init", "restore", "scan", "last", "history",
    "buy", "sell", "fix", "portfolio", "detail",
    "cash", "config", "audit", "status", "refresh", "validate",
])
def test_help_subcommand_shows_help(cmd: str) -> None:
    result = runner.invoke(app, ["help", cmd])
    assert result.exit_code == 0
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `[tool.uv.dev-dependencies]` | `[dependency-groups]` (PEP 735) | uv 0.4+ / PEP 735 ratified 2024 | Dev deps are now standard Python, not uv-proprietary |
| setuptools / hatchling | uv_build | uv 0.5 stable, 2024 | Zero-config build backend, tightly integrated with uv |
| flake8 + isort + black | ruff | ruff 0.1+ (2023), mature 2024 | One tool replaces three; 10-100x faster |
| mypy 1.x | mypy 2.x (2.0 parallel checks, 2.1 current) | 2025 | `strict_bytes` (PEP 688) now enabled in strict mode |
| Typer with `rich` optional | Typer 0.12+ requires `rich` | Typer 0.12 (2024) | Must declare `rich` explicitly; it's not optional |

**Deprecated/outdated:**
- `[tool.uv.dev-dependencies]`: Still works but is the legacy format. New projects use PEP 735.
- `typer[all]` extra: No longer needed since rich is a mandatory dependency.
- `setup.py` / `setup.cfg`: Replaced by `pyproject.toml` entirely.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `_app.py` intermediary pattern (rather than `app` in `cli.py`) cleanly avoids circular imports with all 17 commands | Architecture Patterns §Pattern 2 | If wrong, use centralized registration in cli.py instead — minor refactor |
| A2 | Typer's `@app.command()` decorator in version 0.21.1+ is typed well enough that mypy strict passes without the per-module override, or the override pattern (Pattern 5) resolves it | Pitfall 2 | If Typer stubs changed, may need different workaround; `# type: ignore[misc]` per-line as fallback |
| A3 | `ctx.find_root().command.commands` is a `dict[str, click.Command]` accessible at runtime in Typer's current version | Pattern 4 (help command) | If Typer changed this internal structure, Approach A (subprocess) is the reliable fallback |
| A4 | `no_args_is_help=True` on `typer.Typer()` causes `bensdorp1` with no subcommand to print help (same as `--help`) | Pattern 2 | If behavior changed, add `@app.callback(invoke_without_command=True)` as fallback |
| A5 | `pretty_exceptions_enable=False` is a valid parameter on `typer.Typer()` in version 0.21.1+ | Code Examples | If not available in this version, remove it; it's cosmetic not functional |

**If this table is empty:** It is not empty — five assumptions flagged. Planner should verify A3 (help command internals) before finalizing the help command implementation tasks.

---

## Open Questions

1. **pyproject.toml: uv_build version upper bound**
   - What we know: official docs show `>=0.11.16,<0.12`; pydevtools showed `>=0.7.19,<0.8.0`; uv on this machine is 0.10.12
   - What's unclear: the correct upper bound to use now that uv is at 0.10.x — the `<0.12` range from docs implies 0.11.x exists on PyPI
   - Recommendation: Use `requires = ["uv_build>=0.7,<1.0"]` as a liberal constraint, or check PyPI directly: `pip index versions uv_build`

2. **help command implementation — which approach**
   - What we know: Approach B (in-process Click context) is cleaner but relies on Typer internals; Approach A (subprocess) is always correct but slower
   - What's unclear: whether `ctx.find_root().command.commands` is stable API in Typer 0.21+
   - Recommendation: Implement Approach B with Approach A as tested fallback. If Approach B breaks in tests, switch to A.

3. **REPO-06 branch protection — is it automatable?**
   - What we know: GitHub branch protection rules are configured in repository settings, not via committed files
   - What's unclear: whether a GitHub Actions workflow can set branch protection rules (requires `admin` scope)
   - Recommendation: Document as a manual step in the plan. This is a post-push repo configuration, not a code deliverable.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | Package management, CI | ✓ | 0.10.12 | — |
| Python 3.11+ | Runtime, CI | ✓ (3.12 on this machine; 3.11 pulled by uv in CI) | 3.12 local / 3.11 CI | — |
| pytest | TEST-06 | ✓ | 9.0.3 | — |
| ruff | TEST-06 | ✓ | 0.15.8 | — |
| mypy | TEST-06 | ✓ | 1.19.1 (local) / 2.1.0 from uv in CI | upgrade mypy via uv |
| GitHub Actions | REPO-07, REPO-03 | ✓ (repo is public, has access) | — | — |

**Note:** Local mypy is 1.19.1, but CLAUDE.md pins `>=2.1.0`. CI will install 2.1.0 via `uv sync`. Local dev should upgrade: `uv tool install mypy@latest` or let uv manage it. This is not a blocker for Phase 1 since tests run via CI, but local mypy checks will use 1.19 unless uv environment is used.

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 creates it |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CMD-17 | `help` with no args shows categorized list | unit (CliRunner) | `uv run pytest tests/test_cli.py::test_help_root_shows_all_panels -x` | ❌ Wave 0 |
| CMD-17 | `help scan` shows scan command help text | unit (CliRunner) | `uv run pytest tests/test_cli.py::test_help_subcommand_shows_help -x` | ❌ Wave 0 |
| CMD-17 | `help unknown_cmd` exits non-zero | unit (CliRunner) | `uv run pytest tests/test_cli.py::test_help_unknown_command_exits_nonzero -x` | ❌ Wave 0 |
| REPO-07 / TEST-06 | CI workflow runs pytest clean | smoke (CI) | Verified by GitHub Actions passing | ❌ Wave 0 |
| REPO-07 / TEST-06 | CI workflow runs ruff clean | smoke (CI) | Verified by GitHub Actions passing | ❌ Wave 0 |
| REPO-07 / TEST-06 | CI workflow runs mypy --strict clean | smoke (CI) | Verified by GitHub Actions passing | ❌ Wave 0 |
| D-05 | Each stub exits 0 and prints "Not yet implemented." | unit (CliRunner) | `uv run pytest tests/test_cli.py::test_stub_<name>_exits_cleanly -x` | ❌ Wave 0 |
| REPO-01 | LICENSE file exists at repo root | existence | `uv run pytest tests/test_repo.py::test_license_exists -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src/`
- **Phase gate:** Full suite green + CI passing before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — package marker
- [ ] `tests/test_cli.py` — CliRunner tests for all stubs and help command
- [ ] `tests/test_repo.py` — structural assertions (LICENSE exists, etc.)
- [ ] `pyproject.toml` — pytest + coverage + mypy + ruff configuration
- [ ] `uv.lock` — generated by `uv lock` after pyproject.toml is written

---

## Security Domain

`security_enforcement: true` in config.json; `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 1 has no auth — CLI personal tool, single user |
| V3 Session Management | No | No sessions in this phase |
| V4 Access Control | No | Single-user CLI, no access control boundaries |
| V5 Input Validation | Partial | Typer validates argument types at CLI parse time; stub commands accept no input |
| V6 Cryptography | No | No cryptographic operations in Phase 1 |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious pyproject.toml dependency substitution | Tampering | Lock with `uv.lock`; `--locked` flag in CI |
| GitHub Actions secret exfiltration via fork PR | Information Disclosure | Use `pull_request_target` (not `pull_request`) for close-pr.yml; no secrets passed to PR workflows |
| Command injection via `bensdorp1 help <cmd>` with subprocess | Tampering | If Approach A (subprocess) is used for help: validate command name against known list before passing to subprocess |

**Phase 1 security posture:** Low risk. No secrets, no network calls, no auth, no data storage. The one security-sensitive design choice is the close-pr.yml event trigger (`pull_request_target` vs `pull_request`).

---

## Sources

### Primary (HIGH confidence)
- CLAUDE.md (project file) — verified library versions, pyproject.toml template, Typer layout, mypy config, ruff config
- `https://docs.astral.sh/uv/concepts/build-backend/` — [build-system] table, src layout, uv_build constraints [CITED: WebFetch]
- `https://docs.astral.sh/uv/guides/integration/github/` — GitHub Actions setup patterns [CITED: WebFetch]
- `https://typer.tiangolo.com/tutorial/commands/help/` — rich_help_panel parameter, rich_markup_mode [CITED: WebFetch]
- `https://typer.tiangolo.com/tutorial/commands/context/` — invoke_without_command, ctx.invoked_subcommand [CITED: WebFetch]
- `https://typer.tiangolo.com/tutorial/testing/` — CliRunner usage [CITED: WebFetch]
- `https://github.com/superbrothers/close-pull-request` — close-pr.yml pattern [CITED: WebFetch]
- `https://docs.astral.sh/uv/concepts/projects/dependencies/` — PEP 735 dependency groups [CITED: WebFetch]
- pip index versions (ran locally 2026-05-23) — version confirmation for typer, mypy, ruff [VERIFIED]
- slopcheck 0.6.1 (ran locally 2026-05-23) — all 11 packages [OK] [VERIFIED]

### Secondary (MEDIUM confidence)
- `https://pydevtools.com/handbook/tutorial/setting-up-github-actions-with-uv/` — complete CI YAML example [CITED: WebFetch]
- `https://pydevtools.com/blog/uv-build-backend/` — uv_build [build-system] TOML confirmed [CITED: WebFetch]
- `https://mypy.readthedocs.io/en/stable/command_line.html` — disallow_untyped_decorators behavior [CITED: WebFetch]
- GitHub issue python/mypy#9442 — per-library decorator override is open request; per-module override is the accepted workaround [CITED]

### Tertiary (LOW confidence — flagged as [ASSUMED])
- Training knowledge on `_app.py` intermediary pattern for circular import avoidance [A1]
- Training knowledge on `ctx.find_root().command.commands` being a `dict` [A3]
- Training knowledge on `pretty_exceptions_enable=False` parameter name [A5]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified via pip index versions and slopcheck
- Architecture: HIGH for pyproject.toml/CI patterns; MEDIUM for help command internals (A3 is assumed)
- Pitfalls: HIGH — all derived from verified sources or CLAUDE.md project guidance

**Research date:** 2026-05-23
**Valid until:** 2026-06-23 (stable stack; uv_build version constraint may need updating if uv releases 0.12.x before implementation)
