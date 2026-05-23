---
phase: 01-project-skeleton-and-tooling
plan: 01
subsystem: package-skeleton
tags: [pyproject, uv, typer, skeleton, entry-point]
dependency_graph:
  requires: []
  provides: [bensdorp1-package, entry-point, typer-app-singleton]
  affects: [all-subsequent-plans]
tech_stack:
  added: [uv_build, typer, rich, sqlalchemy, pydantic, yfinance, pandas-market-calendars, httpx, beautifulsoup4, pandas, numpy, pytest, pytest-cov, hypothesis, ruff, mypy]
  patterns: [src-layout, typer-_app-singleton, pep735-dependency-groups]
key_files:
  created:
    - pyproject.toml
    - uv.lock
    - src/bensdorp1/__init__.py
    - src/bensdorp1/_app.py
    - src/bensdorp1/cli.py
    - src/bensdorp1/commands/__init__.py
  modified: []
decisions:
  - "Used PEP 735 [dependency-groups] instead of legacy [tool.uv.dev-dependencies]"
  - "cli.py command imports left as comments — command modules do not exist until Plan 02"
  - "uv_build>=0.7,<1.0 liberal upper bound to stay compatible with uv 0.10.12 on dev machine"
metrics:
  duration: "1m 26s"
  completed_date: "2026-05-23"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 0
---

# Phase 1 Plan 1: Package Skeleton Summary

**One-liner:** uv_build package skeleton with Typer app singleton (_app.py) and registration hub (cli.py), PEP 735 dev deps, and full tool configs (mypy strict, ruff, pytest).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write pyproject.toml with uv_build, all dependencies, and tool configs | 112a33f | pyproject.toml, uv.lock |
| 2 | Create package skeleton — __init__.py files, _app.py singleton, cli.py stub | 61794ce | src/bensdorp1/__init__.py, src/bensdorp1/_app.py, src/bensdorp1/cli.py, src/bensdorp1/commands/__init__.py |

## Verification Results

1. `uv lock --check` — exits 0 (lockfile up to date, 64 packages)
2. `uv run python -c "from bensdorp1.cli import app; print('ok')"` — prints "ok", exits 0
3. `grep -c "from bensdorp1" src/bensdorp1/_app.py` — returns 0 (no package imports in _app.py)
4. All four files exist: src/bensdorp1/__init__.py, src/bensdorp1/_app.py, src/bensdorp1/cli.py, src/bensdorp1/commands/__init__.py

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None in this plan. The cli.py command imports are commented out intentionally (command modules do not exist yet; Plan 02 populates them). This is the expected state for Plan 01, not a stub — it is documented in the plan's task 2 action.

## Threat Flags

No new threat surface introduced beyond the plan's threat model. All packages verified via slopcheck 0.6.1 in RESEARCH.md.

## Self-Check: PASSED

- pyproject.toml: FOUND
- uv.lock: FOUND
- src/bensdorp1/__init__.py: FOUND
- src/bensdorp1/_app.py: FOUND
- src/bensdorp1/cli.py: FOUND
- src/bensdorp1/commands/__init__.py: FOUND
- commit 112a33f: FOUND (chore(01-01): add pyproject.toml)
- commit 61794ce: FOUND (feat(01-01): create package skeleton)
