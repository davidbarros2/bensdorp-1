# Technology Stack: bensdorp1

**Project:** bensdorp1 — Python CLI trading signal tool
**Researched:** 2026-05-23
**Overall confidence:** HIGH (all major claims verified against official docs or PyPI)

---

## Verified Library Versions (May 2026)

These are current stable releases. Pin to these or newer compatible versions.

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

---

## pyproject.toml Structure for uv

### Full annotated template

```toml
[project]
name = "bensdorp1"
version = "0.1.0"
description = "Daily trading signal CLI for System #1 trend following"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "David Barros", email = "davidandrebarros@gmail.com" }]

dependencies = [
    "typer>=0.21.1",
    "rich>=14.0",
    "sqlalchemy>=2.0.49,<2.1",
    "pydantic>=2.13.4",
    "yfinance>=1.3.0",
    "pandas-market-calendars>=5.3.2",
    "httpx>=0.28.1",
    "beautifulsoup4>=4.14.3",
    "lxml>=5.0",          # parser backend for bs4; faster than html.parser
    "pandas>=3.0.3",
    "numpy>=2.0",
]

[project.scripts]
bensdorp1 = "bensdorp1.cli:app"

[build-system]
requires = ["uv_build>=0.5"]
build-backend = "uv_build"

# Development dependencies use PEP 735 [dependency-groups], NOT [tool.uv.dev-dependencies]
# [tool.uv.dev-dependencies] is the legacy format — avoid it for new projects.
# uv sync installs the "dev" group automatically; other groups require --group <name>.
[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-cov>=7.1.0",
    "hypothesis>=6.130",
    "mypy>=2.1.0",
    "ruff>=0.15",
]

[tool.uv]
# Ensures the package itself is installed in editable mode during development
dev-mode = true
```

### Key structural decisions

**`[project.scripts]`** registers the `bensdorp1` CLI entry point. After `uv sync`, running `bensdorp1` invokes `bensdorp1.cli:app`. The entry point must point to a `typer.Typer` instance, not a function.

**`uv_build` as build backend** — uv's own backend (stable since 2025-07); zero-config for pure-Python packages. 10-35x faster than hatchling/flit. No `[tool.hatch.*]` configuration needed.

**`[dependency-groups]` not `[tool.uv.dev-dependencies]`** — PEP 735 is the standard. `[tool.uv.dev-dependencies]` is legacy and deptry/other tools may not recognize it. `uv add --dev` writes to `[dependency-groups].dev`.

---

## Typer: Multi-Command Structure in Separate Modules

### The critical behavioral shift

When a `Typer()` app has exactly one `@app.command()`, Typer presents it as a root command (no sub-command name in help). The moment a second command is added, every command requires a name. This means a project with 17 commands must be organized as a multi-command app from day one.

### Recommended layout

```
bensdorp1/
  cli.py          # root app; registers sub-apps; console_script entry point
  commands/
    scan.py       # app = typer.Typer(); @app.command() def scan(...)
    portfolio.py
    history.py
    buy.py
    sell.py
    ...           # one module per logical command group
```

### Root app wiring (cli.py)

```python
import typer
from bensdorp1.commands import scan, portfolio, history, buy, sell, fix

app = typer.Typer(
    name="bensdorp1",
    help="Daily trading signal CLI.",
    no_args_is_help=True,         # show help when called with no arguments
    add_completion=False,         # disable shell completion if not needed
)

# Commands registered directly (not as sub-groups) appear at top level:
app.add_typer(scan.app, name="scan")
app.add_typer(portfolio.app, name="portfolio")
app.add_typer(buy.app, name="buy")
# ...

if __name__ == "__main__":
    app()
```

### Per-command module pattern

```python
# commands/scan.py
import typer
from typing import Optional

app = typer.Typer(help="Run end-of-day screening.")

@app.command()
def scan(force: bool = typer.Option(False, "--force", help="Skip time guard.")) -> None:
    """Run the daily scan."""
    ...
```

### When a command takes a single positional action

Some of the 17 commands (e.g., `buy SYMBOL PRICE SHARES`) are single-action commands. Make each its own `Typer` app with one `@app.command()` decorated function. Do not use sub-commands for these.

### Flat top-level commands (no nested groups)

Because the spec has 17 flat commands (not hierarchical), do **not** use nested `add_typer` chains. Keep all commands at depth 1. The layout above (single `add_typer` per command at the root app level) is correct.

---

## mypy Strict Mode Configuration

### The core problem with this stack

mypy 2.x strict mode + Typer + SQLAlchemy Core + Pydantic v2 each have specific friction points:

1. **Typer decorators produce `misc` or `arg-type` errors** because Typer's decorator returns types like `Callable[..., Any]`. Use targeted `# type: ignore[misc]` only on the `@app.command()` and `@app.callback()` lines if needed — do not suppress broadly.

2. **SQLAlchemy Core `Table` is dynamically constructed** — mypy cannot infer column types from `Table(...)` definitions. Accessing `.c.my_column` returns `Any`. This is a fundamental limitation acknowledged by SQLAlchemy's own docs (they state *"Table is a dynamically built construct, so Mypy has no way to know what columns it contains"*). There is no fix. Accept `Any` for column access, or use typed column variables:
   ```python
   price_col: Column[Decimal] = Column("price", Numeric(10, 4))
   ```

3. **The SQLAlchemy mypy plugin is deprecated and removed in 2.1** — do not install it. Do not add `sqlalchemy.ext.mypy.plugin` to `plugins`. For SQLAlchemy 2.0 Core, no plugin is needed or wanted.

4. **Pydantic v2 mypy plugin is current and supported** — add `pydantic.mypy` to plugins.

5. **`no_implicit_reexport`** (enabled by strict) means any symbol imported in `__init__.py` and re-exported must either be in `__all__` or use `import X as X` syntax.

6. **mypy 2.0 dropped Python 3.9 support** — targeting Python 3.11 is correct and avoids this.

### Recommended pyproject.toml configuration

```toml
[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["pydantic.mypy"]

# Show error codes so targeted ignores can be written
show_error_codes = true

# Modules without stubs — suppress only missing stubs, not all errors
[[tool.mypy.overrides]]
module = [
    "yfinance",
    "yfinance.*",
    "pandas_market_calendars",
    "pandas_market_calendars.*",
    "bs4",
    "bs4.*",
]
ignore_missing_imports = true

# pandas and numpy ship their own stubs — no override needed
# sqlalchemy 2.0 ships inline types — no override needed
# pydantic v2 ships inline types — no override needed
# httpx ships inline types — no override needed

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

### What `strict = true` enables (mypy 2.1)

These 15 flags are activated by `strict`:

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

Typer's `@app.command()` and `@app.add_typer()` produce `[misc]` errors under strict because Click's internal decorator typing is not fully precise. The least-noise approach:

```python
@app.command()  # type: ignore[misc]
def scan(...) -> None:
    ...
```

Alternatively, use a per-module override for the `commands/` directory only:

```toml
[[tool.mypy.overrides]]
module = ["bensdorp1.commands.*"]
disallow_untyped_decorators = false
```

### Stub packages to install as dev dependencies

```toml
[dependency-groups]
dev = [
    ...
    "types-beautifulsoup4>=4.12",  # bs4 stubs
    # pandas-stubs is bundled with pandas 2.0+ — do NOT install separately
    # numpy stubs are bundled with numpy 2.x — do NOT install separately
    # sqlalchemy 2.0 has inline types — do NOT install sqlalchemy-stubs or sqlalchemy2-stubs
]
```

---

## Ruff Configuration

### Recommended pyproject.toml section

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # Pyflakes
    "I",    # isort
    "UP",   # pyupgrade — modernize syntax (e.g. Union[X, Y] → X | Y)
    "B",    # flake8-bugbear — opinionated bug detection
    "SIM",  # flake8-simplify
    "C4",   # flake8-comprehensions
    "RET",  # flake8-return
    "PTH",  # flake8-use-pathlib
    "ANN",  # flake8-annotations — enforce type annotations
    "TC",   # flake8-type-checking — move runtime-only imports to TYPE_CHECKING
    "RUF",  # Ruff-native rules
    "TRY",  # flake8-try-except-raise patterns
    "EM",   # flake8-errmsg — no inline strings in raise
]
ignore = [
    "ANN101",  # missing type for `self` — not required in modern Python
    "ANN102",  # missing type for `cls`
    "ANN401",  # Dynamically typed expressions (Any) — needed for SQLAlchemy Core columns
    "TRY003",  # Long messages in exception raises — overly strict
    "EM101",   # String literals in raises — conflicts with simple CLIs
    "EM102",   # f-string in raises
]

[tool.ruff.lint.isort]
known-first-party = ["bensdorp1"]
# Force imports to be split into sections (stdlib, third-party, first-party)
force-sort-within-sections = true

[tool.ruff.lint.flake8-type-checking]
# SQLAlchemy Core Table/Column are evaluated at import time, not just TYPE_CHECKING
# Declare these as runtime-evaluated so TC rules don't move them into TYPE_CHECKING blocks
runtime-evaluated-base-classes = ["pydantic.BaseModel"]
# Any SQLAlchemy types used in function signatures should stay out of TYPE_CHECKING
# because SQLAlchemy inspects them at runtime
```

### Critical: TC rules and SQLAlchemy Core

The `TC` (flake8-type-checking) rules tell Ruff to move imports that are only used in type annotations into `if TYPE_CHECKING:` blocks. This **breaks SQLAlchemy** because SQLAlchemy Core evaluates column type annotations at import time. Known Ruff issue [#6510](https://github.com/astral-sh/ruff/issues/6510).

Mitigation options (pick one):
1. Omit `TC` from `select` entirely — safest.
2. Keep `TC` but add per-file `# noqa: TC002` comments on SQLAlchemy imports.
3. Use `runtime-evaluated-base-classes` to protect Pydantic models; handle SQLAlchemy manually with noqa.

For this project, omitting `TC` or using targeted noqa is recommended because the project does not have circular import risks that TC is designed to solve.

### Ruff as formatter (replaces Black)

```toml
[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
```

Run `ruff format .` instead of `black .`. Do not run both.

---

## pytest and Coverage Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--cov=bensdorp1",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-config=pyproject.toml",
    "-v",
]

[tool.coverage.run]
source = ["bensdorp1"]
branch = true
omit = [
    "tests/*",
    "bensdorp1/__main__.py",
]

[tool.coverage.report]
show_missing = true
skip_empty = true
fail_under = 90      # matches spec: >90% overall
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

### Hypothesis configuration

```toml
[tool.hypothesis]
# Suppress database between CI runs (avoids state leaking between PRs)
database = ":memory:"
# Limit example count for CI speed; remove locally for thoroughness
max_examples = 100
```

---

## Known Compatibility Issues

### pandas-market-calendars v5 and pytz removal

pandas-market-calendars 5.0 (April 2025) dropped pytz entirely and migrated to `zoneinfo`. If any code in the project or its dependencies uses pytz timezone objects and passes them to pandas-market-calendars, it will raise a `TypeError`. Always use `zoneinfo.ZoneInfo("America/New_York")` for timezone construction. Never use `pytz.timezone(...)` alongside this library.

### yfinance download() multi-level column index

Since yfinance 0.2.x, `yf.download()` returns a **MultiIndex DataFrame** by default, even for a single ticker. Columns are structured as `(Price, Ticker)` not just `Price`. Access patterns that assume `df["Close"]` will fail silently or raise a `KeyError`.

Fix: Pass `multi_level_index=False` to get flat columns for single-ticker downloads:
```python
df = yf.download("AAPL", start="2024-01-01", auto_adjust=True, multi_level_index=False)
# Now df["Close"] works as expected
```

For multi-ticker batch downloads, keep the default MultiIndex and slice with `df["Close"]["AAPL"]`.

### yfinance auto_adjust default

`auto_adjust=True` is now the default (changed in 0.2.28). The spec requires `auto_adjust=True` explicitly. Always pass it explicitly anyway to be immune to future default changes.

### SQLAlchemy 2.0 vs 2.1

SQLAlchemy 2.1 is in beta as of May 2026. The 2.1 release removes the mypy plugin entirely. Do not upgrade to 2.1 until it is stable. Pin `<2.1` in `pyproject.toml`.

### numpy 2.x binary ABI

Any C-extension wheels compiled against NumPy 1.x cannot load against NumPy 2.x. In practice: yfinance, pandas, and pandas-market-calendars all publish NumPy 2.x-compatible wheels. If a transitive dependency pulls in a NumPy 1.x-only wheel, uv will surface a resolver conflict. This is visible at install time, not runtime.

### mypy 2.0 minimum Python target

mypy 2.0 dropped Python 3.9 support. Targeting 3.11 (`python_version = "3.11"` in `[tool.mypy]`) is correct. Do not set `python_version = "3.9"`.

### mypy `strict_bytes` (new in 2.0)

PEP 688 is now enforced by default in mypy 2.0+: `bytearray` and `memoryview` are no longer assignable to `bytes`. If any database utility code or httpx response handling mixes these types, mypy will flag it. Fix by using explicit `.encode()` or `bytes(...)` conversions.

---

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

---

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
