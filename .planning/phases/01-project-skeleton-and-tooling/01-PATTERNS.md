# Phase 1: Project Skeleton and Tooling - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 26 new files (all net-new creations)
**Analogs found:** 0 / 26 — greenfield project; no existing source files

---

## Greenfield Notice

The repository contains only `CLAUDE.md` and `.planning/` at the start of Phase 1. There are no existing Python files, workflows, or config files to use as analogs. The canonical patterns for this project are therefore drawn from:

1. RESEARCH.md — verified code examples from official Typer, uv, ruff, mypy, and GitHub Actions documentation
2. CLAUDE.md — project-specific conventions locked before Phase 1

These patterns become the baseline that all subsequent phases will reference as analogs.

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `pyproject.toml` | config | — | None — greenfield | no analog |
| `LICENSE` | config | — | None — greenfield | no analog |
| `src/bensdorp1/__init__.py` | config | — | None — greenfield | no analog |
| `src/bensdorp1/_app.py` | config | — | None — greenfield | no analog |
| `src/bensdorp1/cli.py` | config | — | None — greenfield | no analog |
| `src/bensdorp1/commands/__init__.py` | config | — | None — greenfield | no analog |
| `src/bensdorp1/commands/help.py` | command | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/init.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/restore.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/scan.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/last.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/history.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/buy.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/sell.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/fix.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/portfolio.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/detail.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/cash.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/config.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/audit.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/status.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/refresh.py` | command (stub) | request-response | None — greenfield | no analog |
| `src/bensdorp1/commands/validate.py` | command (stub) | request-response | None — greenfield | no analog |
| `tests/__init__.py` | config | — | None — greenfield | no analog |
| `tests/test_cli.py` | test | request-response | None — greenfield | no analog |
| `.github/workflows/ci.yml` | config | — | None — greenfield | no analog |
| `.github/workflows/close-pr.yml` | config | — | None — greenfield | no analog |
| `.github/ISSUE_TEMPLATE/config.yml` | config | — | None — greenfield | no analog |

---

## Pattern Assignments

Because this is a greenfield project, the patterns below ARE the canonical patterns — extracted from RESEARCH.md verified examples. The planner MUST use these patterns directly; there is no codebase analog to read instead.

---

### `pyproject.toml` (config)

**Source:** RESEARCH.md Pattern 1 + CLAUDE.md §pyproject.toml Structure for uv

**Full pattern:**
```toml
[build-system]
requires = ["uv_build>=0.7,<1.0"]
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

[tool.ruff]
line-length = 88
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "PT"]

[tool.mypy]
python_version = "3.11"
strict = true
show_error_codes = true

[[tool.mypy.overrides]]
module = "bensdorp1.commands.*"
disallow_untyped_decorators = false

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Key rules:**
- `[dependency-groups]` NOT `[tool.uv.dev-dependencies]` — PEP 735 is mandatory per CLAUDE.md
- `uv_build` NOT `hatchling` — uv_build is zero-config and stable since uv 0.5
- Entry point: `bensdorp1 = "bensdorp1.cli:app"` — `app` is re-exported from `cli.py`
- Phase 1 does NOT include SQLAlchemy in pyproject.toml yet (added when db/ subpackage is created), but the dependency IS listed because `pyproject.toml` is written once for all v1 dependencies

---

### `src/bensdorp1/_app.py` (config — Typer app singleton)

**Source:** RESEARCH.md Pattern 2 + Code Examples "Root app instantiation"

**Full pattern:**
```python
import typer

app = typer.Typer(
    name="bensdorp1",
    help="Bensdorp System #1 — daily S&P 500 trend-following CLI.",
    rich_markup_mode="rich",
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # don't show Python tracebacks to the user
)
```

**Why `_app.py` exists (not inline in `cli.py`):** Prevents circular imports. `cli.py` imports all command modules to trigger `@app.command()` decoration. If `app` were defined in `cli.py` and command modules imported from `cli.py`, Python would raise `ImportError` on partially initialized module. The `_app.py` intermediary breaks this cycle — both `cli.py` and every command module import `app` from `_app.py`, which has no imports from the package.

---

### `src/bensdorp1/cli.py` (config — registration hub)

**Source:** RESEARCH.md Code Examples "cli.py — registration hub"

**Full pattern:**
```python
from bensdorp1._app import app  # re-export for entry point

# Import all command modules to trigger @app.command() decorations (side-effect imports):
import bensdorp1.commands.audit    # noqa: F401
import bensdorp1.commands.buy      # noqa: F401
import bensdorp1.commands.cash     # noqa: F401
import bensdorp1.commands.config   # noqa: F401
import bensdorp1.commands.detail   # noqa: F401
import bensdorp1.commands.fix      # noqa: F401
import bensdorp1.commands.help     # noqa: F401
import bensdorp1.commands.history  # noqa: F401
import bensdorp1.commands.init     # noqa: F401
import bensdorp1.commands.last     # noqa: F401
import bensdorp1.commands.portfolio   # noqa: F401
import bensdorp1.commands.refresh     # noqa: F401
import bensdorp1.commands.restore     # noqa: F401
import bensdorp1.commands.scan        # noqa: F401
import bensdorp1.commands.sell        # noqa: F401
import bensdorp1.commands.status      # noqa: F401
import bensdorp1.commands.validate    # noqa: F401

__all__ = ["app"]
```

**Key rules:**
- `cli.py` contains NO business logic — it is purely a registration hub
- Every import is a side-effect import — the module is imported only so its `@app.command()` decorators run
- `# noqa: F401` suppresses ruff's "imported but unused" warning on each side-effect import
- `__all__ = ["app"]` makes `app` importable as `from bensdorp1.cli import app` (the entry point)

---

### `src/bensdorp1/commands/scan.py` and all 15 other stubs (command, request-response)

**Source:** RESEARCH.md Code Examples "Minimal stub command (mypy-strict compliant)"

**Canonical stub pattern (copy for each of the 16 stub commands):**
```python
import typer

from bensdorp1._app import app


@app.command(rich_help_panel="<PANEL_NAME>")
def <function_name>() -> None:
    """<One-line docstring describing the command.>"""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
```

**Panel assignments (from D-13):**

| Command module | Function name | `rich_help_panel` value |
|---------------|---------------|------------------------|
| `commands/init.py` | `init` | `"Setup"` |
| `commands/restore.py` | `restore` | `"Setup"` |
| `commands/scan.py` | `scan` | `"Daily operation"` |
| `commands/last.py` | `last` | `"Daily operation"` |
| `commands/history.py` | `history` | `"Daily operation"` |
| `commands/buy.py` | `buy` | `"Confirmations"` |
| `commands/sell.py` | `sell` | `"Confirmations"` |
| `commands/fix.py` | `fix` | `"Confirmations"` |
| `commands/portfolio.py` | `portfolio` | `"Positions"` |
| `commands/detail.py` | `detail` | `"Positions"` |
| `commands/cash.py` | `cash` | `"System"` |
| `commands/config.py` | `config` | `"System"` |
| `commands/audit.py` | `audit` | `"System"` |
| `commands/status.py` | `status` | `"System"` |
| `commands/refresh.py` | `refresh` | `"System"` |
| `commands/validate.py` | `validate` | `"System"` |

**mypy strict rules for stubs:**
- Every command function MUST have `-> None` return type annotation
- `@app.command()` decorator is exempt from `disallow_untyped_decorators` via the pyproject.toml override for `bensdorp1.commands.*`
- `raise typer.Exit()` (not `return`) — Typer convention for clean exit; non-zero code NOT used for stubs (D-05)

---

### `src/bensdorp1/commands/help.py` (command, request-response — real implementation)

**Source:** RESEARCH.md Pattern 4 "help command implementation (CMD-17)", Approach B

**Full pattern (Approach B — in-process Click context):**
```python
import typer

from bensdorp1._app import app


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
        typer.echo(cmd_obj.get_help(root_ctx))
    else:
        typer.echo(ctx.find_root().get_help())
    raise typer.Exit()
```

**Key notes:**
- `# type: ignore[attr-defined]` is required — mypy does not know that `ctx.command` has a `.commands` dict at this call site; the attribute exists at runtime on Click group objects
- The `ctx` parameter must be typed as `typer.Context` (not `click.Context`) for mypy strict compatibility
- `show_default=False` on the `command` argument suppresses the unhelpful `[default: ]` in help text
- Assumption A3 from RESEARCH.md: if `ctx.find_root().command.commands` is not accessible at runtime, fall back to Approach A (subprocess re-invocation with `[sys.executable, "-m", "bensdorp1", command, "--help"]`)

---

### `src/bensdorp1/__init__.py` (config — package marker)

**Full pattern:**
```python
"""bensdorp1 — Bensdorp System #1 trend-following CLI."""

__version__ = "0.1.0"
```

**Key rule:** Version string must match `pyproject.toml` `[project] version`.

---

### `src/bensdorp1/commands/__init__.py` (config — package marker)

**Full pattern:** Empty file. Must exist for `from bensdorp1.commands import scan` to work with src layout and uv_build.

---

### `tests/__init__.py` (config — package marker)

**Full pattern:** Empty file. Required so pytest discovers the `tests/` package correctly.

---

### `tests/test_cli.py` (test, request-response)

**Source:** RESEARCH.md Code Examples "CliRunner test for stubs"

**Full pattern:**
```python
import pytest
from typer.testing import CliRunner

from bensdorp1.cli import app

runner = CliRunner()


def test_root_help_exits_cleanly() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_root_help_shows_all_panels() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Daily operation" in result.output
    assert "Setup" in result.output
    assert "Confirmations" in result.output
    assert "Positions" in result.output
    assert "System" in result.output


def test_help_command_no_args_exits_cleanly() -> None:
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0


def test_help_unknown_command_exits_nonzero() -> None:
    result = runner.invoke(app, ["help", "nonexistent"])
    assert result.exit_code != 0


@pytest.mark.parametrize("cmd", [
    "init", "restore", "scan", "last", "history",
    "buy", "sell", "fix", "portfolio", "detail",
    "cash", "config", "audit", "status", "refresh", "validate",
])
def test_stub_exits_cleanly(cmd: str) -> None:
    result = runner.invoke(app, [cmd])
    assert result.exit_code == 0
    assert "Not yet implemented." in result.output


@pytest.mark.parametrize("cmd", [
    "init", "restore", "scan", "last", "history",
    "buy", "sell", "fix", "portfolio", "detail",
    "cash", "config", "audit", "status", "refresh", "validate",
])
def test_help_subcommand_shows_help(cmd: str) -> None:
    result = runner.invoke(app, ["help", cmd])
    assert result.exit_code == 0
```

**Key rules:**
- NEVER invoke the CLI via subprocess in tests — `CliRunner.invoke(app, [...])` is in-process and handles Typer/Click exit codes correctly
- All test functions MUST have `-> None` return type for mypy strict
- `runner = CliRunner()` is module-level — one instance shared across all tests in the module
- Import path: `from bensdorp1.cli import app` (NOT `from bensdorp1._app import app`) — `cli.py` triggers all side-effect imports; `_app.py` alone has no commands registered

---

### `.github/workflows/ci.yml` (config — GitHub Actions)

**Source:** RESEARCH.md Pattern 7

**Full pattern:**
```yaml
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

**Key rules:**
- `fail-fast: false` — both OS jobs run even if one fails
- `uv sync --locked --dev` — `--locked` enforces lockfile is committed and up to date
- `astral-sh/setup-uv@v6` — current stable version of the uv setup action
- mypy runs against `src/` not repo root — avoids false positives in `tests/`
- `uv run` handles cross-platform activation — no shell override needed

---

### `.github/workflows/close-pr.yml` (config — GitHub Actions)

**Source:** RESEARCH.md Pattern 8

**Full pattern:**
```yaml
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

            If you have found a bug or have a suggestion, please contact the maintainer directly.
```

**Critical rule:** Use `pull_request_target` NOT `pull_request`. The `pull_request` event from forks runs with read-only tokens and cannot close PRs or post comments. `pull_request_target` runs from the base branch (main) with write tokens.

---

### `.github/ISSUE_TEMPLATE/config.yml` (config)

**Source:** RESEARCH.md Pattern 8 supplementary note

**Full pattern:**
```yaml
blank_issues_enabled: false
contact_links:
  - name: Questions
    url: https://github.com/davidandrebarros/bensdorp-1
    about: This repository does not accept issues. Please contact the maintainer directly.
```

---

## Shared Patterns

### Typer app import — applies to every command module

Every file under `src/bensdorp1/commands/` uses this import to register against the shared app:

```python
from bensdorp1._app import app
```

Never import from `bensdorp1.cli` inside command modules — that creates a circular import.

---

### mypy strict return type annotation — applies to every command function

Every command function (stub or real) MUST declare `-> None`:

```python
@app.command(rich_help_panel="<PANEL>")
def command_name() -> None:
    ...
```

Without `-> None`, mypy strict (`disallow_incomplete_defs`) will reject the function.

---

### typer.Exit() pattern — applies to every command function

Every command function ends with `raise typer.Exit()` (not `return`):

```python
typer.echo("Not yet implemented.")
raise typer.Exit()
```

For error exits: `raise typer.Exit(1)`. For success: `raise typer.Exit()` or `raise typer.Exit(0)`.

---

### pathlib.Path for all filesystem paths — applies to all phases

Per CLAUDE.md specifics and D-07 (Windows CI): always use `pathlib.Path` for filesystem operations, never string concatenation. This applies to all phases when database, data, or config file paths are involved. Phase 1 has no filesystem path usage in code (stubs only), but this rule applies from Phase 2 onward.

---

## No Analog Found

All 26 files in Phase 1 have no existing analog. This is expected — Phase 1 is the greenfield initialization phase.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| All 26 files listed above | various | various | Repository contained only CLAUDE.md before Phase 1 |

---

## Metadata

**Analog search scope:** Entire repository (`C:\Users\david\Documents\Projetos\bensdorp-1`)
**Files scanned:** 1 existing file (`CLAUDE.md`) — no Python, YAML, or TOML source files found
**Pattern extraction date:** 2026-05-23
**Baseline status:** This PATTERNS.md IS the initial pattern baseline. Phase 2 and later phases will reference the files created in Phase 1 as their analogs.
