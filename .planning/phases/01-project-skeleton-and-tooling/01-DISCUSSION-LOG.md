# Phase 1: Project Skeleton and Tooling - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 1-Project Skeleton and Tooling
**Areas discussed:** Package layout, Stub commands in Phase 1, CI matrix scope, help command design

---

## Package layout

| Option | Description | Selected |
|--------|-------------|----------|
| src/ layout — src/bensdorp1/ | Prevents accidental imports of uninstalled package during tests; pypa-recommended | ✓ |
| Flat layout — bensdorp1/ at root | Simpler, fewer directories, but test runs can accidentally import the source tree | |

**User's choice:** src/ layout

---

| Option | Description | Selected |
|--------|-------------|----------|
| commands/ subpackage from day 1 | Each command in its own module; scales naturally across all 14 phases | ✓ |
| Single cli.py for Phase 1 | Simpler start, needs splitting later | |

**User's choice:** commands/ subpackage from day 1

---

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: commands/ + cli.py only | No empty placeholder directories; other subpackages added by their phases | ✓ |
| Full skeleton now | Create all top-level subpackages now with __init__.py placeholders | |

**User's choice:** Minimal skeleton for Phase 1

---

## Stub commands in Phase 1

| Option | Description | Selected |
|--------|-------------|----------|
| All 17 commands stubbed now | Every command registered with Typer; replaced phase by phase | ✓ |
| Only help for now | help is the only command; later phases add commands | |

**User's choice:** All 17 commands stubbed now

---

| Option | Description | Selected |
|--------|-------------|----------|
| Print 'not yet implemented' + exit 0 | Typer callback raises typer.Exit(); user gets feedback, no traceback | ✓ |
| Raise NotImplementedError | Python exception, traceback, fails CI tests if called | |
| Silent exit | Return immediately with no output; ambiguous | |

**User's choice:** Print a clear "not yet implemented" message + exit 0

---

## CI matrix scope

| Option | Description | Selected |
|--------|-------------|----------|
| Python 3.11 only | Matches project constraint; no version matrix overhead | ✓ |
| Python 3.11 + 3.12 | Forward compatibility; doubles CI time | |
| Python 3.11 + 3.12 + 3.13 | Full forward-compat matrix | |

**User's choice:** Python 3.11 only

---

| Option | Description | Selected |
|--------|-------------|----------|
| ubuntu-latest only | Fastest, cheapest | |
| ubuntu-latest + windows-latest | Ensures Windows compatibility | ✓ |
| ubuntu + windows + macos | Full cross-platform | |

**User's choice:** ubuntu-latest + windows-latest
**Notes:** User's daily driver is Windows; they will run the CLI from Windows command line. Cross-platform CI is meaningful here.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, cache uv downloads | GitHub Actions cache for ~/.cache/uv; cuts install time significantly | ✓ |
| No cache | Simpler YAML but slower runs | |

**User's choice:** Yes, cache uv downloads

---

## help command design

| Option | Description | Selected |
|--------|-------------|----------|
| Delegate to Typer's --help for that command | help scan → internally calls scan --help; single source of truth | ✓ |
| Hand-written help strings per command | More control but drift risk across 17 commands | |

**User's choice:** Delegate to Typer's --help

---

| Option | Description | Selected |
|--------|-------------|----------|
| Rich panels by category in --help output | Commands grouped into Rich Panels via rich_help_panel parameter | ✓ |
| Flat alphabetical list | Typer's default A-Z | |
| Custom printed table | help prints its own Rich table | |

**User's choice:** Rich panels by category

---

| Option | Description | Selected |
|--------|-------------|----------|
| Setup / Daily operation / Confirmations / Positions / System | init+restore / scan+last+history / buy+sell+fix / portfolio+detail / cash+config+audit+status+refresh+validate+help | ✓ |
| You decide | Claude picks grouping | |

**User's choice:** Setup / Daily operation / Confirmations / Positions / System

---

## Claude's Discretion

None — user made explicit choices for every decision point.

## Deferred Ideas

None — discussion stayed within Phase 1 scope.
