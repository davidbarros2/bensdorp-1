---
phase: 01-project-skeleton-and-tooling
reviewed: 2026-05-23T00:00:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - pyproject.toml
  - src/bensdorp1/__init__.py
  - src/bensdorp1/_app.py
  - src/bensdorp1/cli.py
  - src/bensdorp1/commands/__init__.py
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
  - tests/__init__.py
  - tests/test_cli.py
  - tests/test_repo.py
  - .github/workflows/ci.yml
  - .github/workflows/close-pr.yml
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-23
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Reviewed 27 source files for Phase 1 (project skeleton and tooling). The Python package structure, Typer wiring, mypy strict configuration, and ruff setup are all sound. The command stubs are correctly formed and the import-order justification for `cli.py` is valid.

Two blockers were found: a functional bug in `help.py` that produces wrong usage output for every `help <command>` invocation (confirmed by live test), and a GitHub Actions security issue in `close-pr.yml` using an unpinned third-party action under `pull_request_target` with write permissions and no `permissions:` restriction.

Five warnings cover missing dependencies, an undocumented CI flag, missing configuration sections, and a weak test assertion. Three info items cover minor quality issues.

---

## Critical Issues

### CR-01: `help <command>` shows wrong usage line for every subcommand

**File:** `src/bensdorp1/commands/help.py:18`
**Issue:** `cmd_obj.get_help(root_ctx)` passes the root Typer context to the subcommand's `get_help()` method. Click's `get_help(ctx)` uses `ctx.command_path` to build the usage line. Because `root_ctx.command_path` is `"bensdorp1"`, every invocation of `help <cmd>` prints `Usage: bensdorp1 [OPTIONS]` instead of `Usage: bensdorp1 scan [OPTIONS]` (or whatever the subcommand is). Confirmed by running `help scan` live — output begins with `Usage: bensdorp1 [OPTIONS]`. The correct fix is to construct a child context for the subcommand.

**Fix:**
```python
# Replace line 18:
#   typer.echo(cmd_obj.get_help(root_ctx))
# With:
import click
sub_ctx = click.Context(cmd_obj, parent=root_ctx, info_name=command)
typer.echo(cmd_obj.get_help(sub_ctx))
```

This gives a correct usage line: `Usage: bensdorp1 scan [OPTIONS]`.

---

### CR-02: `close-pr.yml` uses `pull_request_target` with an unpinned third-party action and no permission restriction

**File:** `.github/workflows/close-pr.yml:5,12`
**Issue:** `pull_request_target` runs workflows with write access to the base repository's secrets and refs, even when the PR comes from a fork. The action `superbrothers/close-pull-request@v3` is pinned to a mutable version tag (`v3`), not an immutable commit SHA. If the `v3` tag is ever moved (intentionally or via a supply-chain attack), the workflow will execute arbitrary code with write permissions on the repository. There is also no `permissions:` block to restrict the GITHUB_TOKEN to the minimum required (`pull-requests: write`), leaving all default write scopes open.

**Fix:**
```yaml
permissions:
  pull-requests: write

jobs:
  close:
    runs-on: ubuntu-latest
    steps:
      # Pin to a specific commit SHA instead of a mutable tag:
      - uses: superbrothers/close-pull-request@a632fa08f1cc31fa4b2ea3c737a7c53f119e9ce8
        with:
          comment: |
            ...
```
Find the current commit SHA for `v3` via:
`gh api repos/superbrothers/close-pull-request/git/ref/tags/v3`

---

## Warnings

### WR-01: `lxml` is missing from runtime dependencies

**File:** `pyproject.toml:10-21`
**Issue:** `beautifulsoup4` is declared as a runtime dependency (correct, as it is used for S&P 500 constituent scraping). `CLAUDE.md` explicitly states "pair with lxml for speed". If any implementation code passes `"lxml"` as the parser argument to `BeautifulSoup()`, it will raise `bs4.FeatureNotFound` at runtime because `lxml` is not installed. bs4 silently falls back to `html.parser` only when no parser is specified — a specified parser that is absent raises an exception.

**Fix:**
```toml
dependencies = [
    ...
    "beautifulsoup4>=4.14.3",
    "lxml>=5.0",
    ...
]
```

---

### WR-02: `uv sync --locked --dev` uses an undocumented flag in CI

**File:** `.github/workflows/ci.yml:28`
**Issue:** `--dev` is not a documented flag for `uv sync`. The documented flags are `--no-dev`, `--only-dev`, and `--group <name>`. With PEP 735 `[dependency-groups]`, `uv sync` installs the `dev` group automatically — no extra flag is needed. While the current uv version (0.10.x) silently accepts `--dev` without erroring, this is undocumented behavior that may break in any future uv release. The CLAUDE.md explicitly notes that `[tool.uv.dev-dependencies]` is the legacy format and `[dependency-groups]` (PEP 735) is the correct approach, and uv's own docs confirm `uv sync` installs the dev group by default.

**Fix:**
```yaml
# Line 28 — remove the --dev flag:
run: uv sync --locked
```

---

### WR-03: `pytest-cov` is installed but never configured or invoked

**File:** `pyproject.toml:30`, `.github/workflows/ci.yml:31`
**Issue:** `pytest-cov>=7.1.0` is declared as a dev dependency but there is no `[tool.coverage.run]`, `[tool.coverage.report]`, or `addopts = ["--cov=src/bensdorp1"]` in `[tool.pytest.ini_options]`. The CI `pytest` step runs without `--cov`. CLAUDE.md states coverage must be "configured via `[tool.coverage.*]` in pyproject.toml". As-is, installing pytest-cov has no effect.

**Fix:**
Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--cov=src/bensdorp1", "--cov-report=term-missing"]

[tool.coverage.run]
branch = true
source = ["src/bensdorp1"]

[tool.coverage.report]
show_missing = true
```

---

### WR-04: Hypothesis database leaks state between CI runs; no profile configured

**File:** `pyproject.toml`
**Issue:** `hypothesis>=6.130` is installed as a dev dependency. CLAUDE.md explicitly says to "suppress database between CI runs (avoids state leaking between PRs)" and "limit example count for CI speed". Without a `[tool.hypothesis]` profile, Hypothesis uses its default local database (which persists between runs in CI, causing non-deterministic behaviour) and the default example count (100), which can make CI slow when Hypothesis tests are added.

**Fix:**
```toml
[tool.hypothesis]
suppress_health_check = []
database = ":memory:"
max_examples = 50
```
For local development, override in a `settings` profile or via `@settings(max_examples=500)`.

---

### WR-05: `test_help_subcommand_shows_help` makes no assertion on output content

**File:** `tests/test_cli.py:82-84`
**Issue:** The test only asserts `exit_code == 0`. It does not verify that the output contains the command name, its docstring, or any usage information. This allowed CR-01 (wrong usage line for `help <command>`) to exist undetected — the test passes while the output is functionally incorrect. A test named `shows_help` that does not inspect the help output is not testing what its name claims.

**Fix:**
```python
def test_help_subcommand_shows_help(cmd: str) -> None:
    result = runner.invoke(app, ["help", cmd])
    assert result.exit_code == 0
    # Usage line must reference the subcommand, not the root app
    assert f"bensdorp1 {cmd}" in result.output
```

---

## Info

### IN-01: `validate` docstring references DATE but the function has no `date` parameter

**File:** `src/bensdorp1/commands/validate.py:8`
**Issue:** The docstring reads `"Show what buy candidates System 1 would have produced on DATE."` The string `DATE` implies a parameter that will be added in a future implementation. As a stub it is not functional, but the docstring appears verbatim in `--help` output and in `help validate`, misleading users into trying `bensdorp1 validate 2025-01-15` (which will fail with "Got unexpected extra argument"). The docstring should not reference parameters that do not exist.

**Fix:**
```python
"""Show what buy candidates System 1 would have produced on a historical date."""
```
Update to include the actual `date` parameter when the command is implemented.

---

### IN-02: `*.pyi` in `.gitignore` will silently prevent committing hand-written type stubs

**File:** `.gitignore:20`
**Issue:** The rule `*.pyi` globally ignores all `.pyi` files regardless of directory. If hand-written stubs are added under `src/` (a common pattern when wrapping libraries that lack stubs), they will be invisible to git. The intent was almost certainly to exclude generated stubs, not source stubs. All `.pyi` files currently in the repo live under `.venv/` which is already excluded by the `.venv/` rule, making this rule redundant today but dangerous later.

**Fix:** Remove the `*.pyi` line from `.gitignore`. Generated stubs (e.g., from `stubgen`) should be placed in an explicitly ignored directory rather than relying on a global extension pattern.

---

### IN-03: Third-party actions in `ci.yml` are pinned to mutable version tags, not commit SHAs

**File:** `.github/workflows/ci.yml:18,21`
**Issue:** `actions/checkout@v4` and `astral-sh/setup-uv@v6` are pinned to mutable major version tags. If these tags are moved to a different commit (supply chain compromise or accidental force-push), CI will execute different code than expected. This is a lower-severity variant of the concern raised in CR-02, limited to CI rather than write-permission workflows.

**Fix:** Pin to commit SHAs:
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
- uses: astral-sh/setup-uv@f0ec1fc3b38f5e7cd731bb6ce540c5af426746bb  # v6.1.0
```
Retrieve current SHAs via `gh api repos/actions/checkout/git/ref/tags/v4`.

---

_Reviewed: 2026-05-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
