<!-- GSD:project-start source:PROJECT.md -->

## Project

**bensdorp1**

`bensdorp1` is a single-user command-line interface for screening and monitoring stock positions based on System #1 (Trend Following on S&P 500 Stocks) from Laurens Bensdorp's "Trading Retirement Accounts". It generates daily buy candidates and monitors open positions for exit triggers — it does not execute trades. The user executes all trades manually via their broker; the CLI records confirmations and maintains state.

**Core Value:** Every trading day, show the user exactly which positions triggered a stop and which stocks are top buy candidates, so they need less than 5 minutes of decision time.

### Constraints

- **Language**: Python 3.11+ — specified in requirements
- **Package manager**: uv — specified in requirements
- **Database**: SQLite only, no external services — zero-config requirement
- **Market data**: yfinance only — free, no API key
- **Data directory**: ~/bensdorp1/ default; overridable via BENSDORP1_HOME env var
- **Timezone**: Eastern Time internally; Lisbon for user display (BENSDORP1_USER_TZ override)
- **Scan guard**: refuse scan if before 16:30 ET (market close + 30min buffer)
- **Max positions**: 10 simultaneous open positions (strategy rule)
- **No extensibility**: do not design for hypothetical future features; v1 is complete

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Verified Library Versions (May 2026)

| Library | Pinned version | Notes |
|---------|---------------|-------|
| typer | `>=0.21.1` | Rich is now a required dep (not optional) since 0.12 |
| rich | `>=14.0` | Pulled transitively by Typer; declare explicitly anyway |
| sqlalchemy | `>=2.0.49,<2.1` | Stay on 2.0.x; 2.1 is in beta and removes the mypy plugin |
| pydantic | `>=2.13.4` | v2 GA; latest is 2.13.4 |
| yfinance | `>=1.3.0` | 1.0 was the "stable" milestone; 1.3.0 is current |
| pandas-market-calendars | `>=5.3.2` | v5.0 (Apr 2025) dropped pytz, now uses zoneinfo; requires Python >=3.10 |
| httpx | `>=0.28.1` | Sync client is sufficient; no need for async transport |
| beautifulsoup4 | `>=4.14.3` | Import as `bs4`; pair with `lxml` for speed |
| pandas | `>=3.0.3` | pandas 3.x is NumPy 2.x-compatible |
| numpy | `>=2.0` | NumPy 2.0 broke binary ABI; use 2.x throughout |
| pytest | `>=8.3` | — |
| pytest-cov | `>=7.1.0` | Configure via `[tool.coverage.*]` in pyproject.toml |
| hypothesis | `>=6.130` | numpy and pandas extras available |
| ruff | `>=0.15` | 0.15.x is current; version 0.x still; fast-moving |
| mypy | `>=2.1.0` | 2.0 introduced parallel checking; 2.1 is current stable |
| uv | `>=0.7` | Use `uv_build` as build backend (stable since 0.5) |

## pyproject.toml Structure for uv

### Full annotated template

# Development dependencies use PEP 735 [dependency-groups], NOT [tool.uv.dev-dependencies]

# [tool.uv.dev-dependencies] is the legacy format — avoid it for new projects.

# uv sync installs the "dev" group automatically; other groups require --group <name>.

# Ensures the package itself is installed in editable mode during development

### Key structural decisions

## Typer: Multi-Command Structure in Separate Modules

### The critical behavioral shift

### Recommended layout

### Root app wiring (cli.py)

# Commands registered directly (not as sub-groups) appear at top level:

# ...

### Per-command module pattern

# commands/scan.py

### When a command takes a single positional action

### Flat top-level commands (no nested groups)

## mypy Strict Mode Configuration

### The core problem with this stack

### Recommended pyproject.toml configuration

# Show error codes so targeted ignores can be written

# Modules without stubs — suppress only missing stubs, not all errors

# pandas and numpy ship their own stubs — no override needed

# sqlalchemy 2.0 ships inline types — no override needed

# pydantic v2 ships inline types — no override needed

# httpx ships inline types — no override needed

### What `strict = true` enables (mypy 2.1)

- `disallow_untyped_defs`
- `disallow_incomplete_defs`
- `disallow_untyped_calls`
- `disallow_untyped_decorators` ← this one fires on Typer decorators
- `disallow_any_generics`
- `disallow_subclassing_any`
- `check_untyped_defs`
- `warn_return_any`
- `warn_unused_configs`
- `warn_redundant_casts`
- `warn_unused_ignores`
- `strict_equality`
- `strict_bytes` (new in 2.0, per PEP 688)
- `no_implicit_reexport`
- `extra_checks`

### Managing `disallow_untyped_decorators` with Typer

### Stub packages to install as dev dependencies

## Ruff Configuration

### Recommended pyproject.toml section

# Force imports to be split into sections (stdlib, third-party, first-party)

# SQLAlchemy Core Table/Column are evaluated at import time, not just TYPE_CHECKING

# Declare these as runtime-evaluated so TC rules don't move them into TYPE_CHECKING blocks

# Any SQLAlchemy types used in function signatures should stay out of TYPE_CHECKING

# because SQLAlchemy inspects them at runtime

### Critical: TC rules and SQLAlchemy Core

### Ruff as formatter (replaces Black)

## pytest and Coverage Configuration

### Hypothesis configuration

# Suppress database between CI runs (avoids state leaking between PRs)

# Limit example count for CI speed; remove locally for thoroughness

## Known Compatibility Issues

### pandas-market-calendars v5 and pytz removal

### yfinance download() multi-level column index

# Now df["Close"] works as expected

### yfinance auto_adjust default

### SQLAlchemy 2.0 vs 2.1

### numpy 2.x binary ABI

### mypy 2.0 minimum Python target

### mypy `strict_bytes` (new in 2.0)

## Alternatives Considered and Rejected

| Category | Chosen | Alternative | Why Not |
|----------|--------|-------------|---------|
| CLI | Typer | Click (direct), argparse | Typer is Click with type hints; zero boilerplate |
| CLI | Typer | Cyclopts | Newer but smaller ecosystem; Typer has the docs and stubs |
| DB toolkit | SQLAlchemy Core | raw sqlite3 | Safe SQL composition with named params; no string interpolation risk |
| DB toolkit | SQLAlchemy Core | SQLAlchemy ORM | ORM adds complexity for what is effectively a fixed schema |
| HTTP | httpx | requests | httpx has modern type stubs; requests stubs are third-party and lag |
| Build backend | uv_build | hatchling | uv_build is now stable and default for uv projects; no config overhead |
| Type checker | mypy | Pyright/Pylance | mypy has Pydantic plugin; project uses mypy strict in CI spec |
| Formatter | ruff format | black | ruff format replaces black; running both creates conflicts |
| Linter | ruff | flake8 + isort + pyupgrade | ruff consolidates all of these in one fast pass |

## Sources

- Typer docs (Context7 /fastapi/typer): https://typer.tiangolo.com/tutorial/subcommands/
- uv docs (Context7 /websites/astral_sh_uv): https://docs.astral.sh/uv/concepts/projects/dependencies/
- Ruff rules: https://docs.astral.sh/ruff/rules/
- Ruff configuration: https://docs.astral.sh/ruff/configuration/
- mypy strict mode: https://pydevtools.com/handbook/how-to/how-to-configure-mypy-strict-mode/
- mypy 2.0 changelog: https://mypy.readthedocs.io/en/stable/changelog.html
- Pydantic v2 mypy plugin: https://pydantic.dev/docs/validation/latest/integrations/dev-tools/mypy
- SQLAlchemy mypy plugin deprecation: https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html
- SQLAlchemy Core type inference limitation: https://github.com/sqlalchemy/sqlalchemy/discussions/9801
- Ruff TC / SQLAlchemy known issue: https://github.com/astral-sh/ruff/issues/6510
- yfinance MultiIndex docs: https://ranaroussi.github.io/yfinance/advanced/multi_level_columns.html
- pandas-market-calendars v5 pytz removal: https://pypi.org/project/pandas-market-calendars/
- uv build backend stable: https://pydevtools.com/blog/uv-build-backend/
- PEP 735 dependency groups: https://docs.astral.sh/uv/concepts/projects/dependencies/
- pytest-cov config: https://pytest-cov.readthedocs.io/en/latest/config.html

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
