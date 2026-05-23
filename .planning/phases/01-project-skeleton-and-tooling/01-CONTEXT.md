# Phase 1: Project Skeleton and Tooling - Context

**Gathered:** 2026-05-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the repository skeleton so a developer can clone, install with `uv`, and run `bensdorp1 help` — and the GitHub Actions CI pipeline runs clean on every push. This phase delivers: pyproject.toml, package layout, all 17 commands as stubs, the help command (real implementation), and two GitHub Actions workflows (ci.yml + close-pr.yml).

No business logic is implemented in this phase. No database, no data fetching, no strategy calculations.

</domain>

<decisions>
## Implementation Decisions

### Package Layout
- **D-01:** Use `src/` layout — package lives at `src/bensdorp1/`, not flat at repo root. Prevents accidental imports of the uninstalled package during test runs; pypa-recommended for installable tools.
- **D-02:** Use a `commands/` subpackage from day 1 — `src/bensdorp1/commands/`. Each command gets its own module (`commands/help.py`, `commands/scan.py`, etc.). Root app wired in `src/bensdorp1/cli.py`.
- **D-03:** Minimal skeleton for Phase 1: only `commands/` + `cli.py` created. No placeholder directories for `db/`, `strategy/`, `data/`, `ui/` — those subpackages are created by their respective phases.

### Stub Commands
- **D-04:** All 17 commands are registered as Typer stubs in Phase 1. Each stub lives in its own module under `commands/`. Rationale: `bensdorp1 help <command>` must work for every command name, not just the ones implemented so far.
- **D-05:** Stub body: prints a message like `"Not yet implemented."` and exits cleanly via `typer.Exit()`. Non-zero exit code is NOT used — stubs are expected placeholders, not errors.

### CI Pipeline
- **D-06:** Python 3.11 only (matches project constraint). No multi-version matrix — single-user personal tool, not a library published to PyPI.
- **D-07:** OS matrix: `ubuntu-latest` + `windows-latest`. User runs this CLI on Windows daily, so Windows CI is meaningful and catches cross-platform issues (path separators, etc.).
- **D-08:** uv download cache enabled in both CI jobs. Cache key based on `uv.lock` (or `pyproject.toml` hash). Cuts install time on cache hits.
- **D-09:** CI workflow (`ci.yml`) runs on every push and PR: `pytest` + `ruff check` + `ruff format --check` + `mypy --strict`.
- **D-10:** Close-PR workflow (`close-pr.yml`) auto-closes any PR with the no-contributions policy message. Runs on `pull_request_target` opened/reopened events (not `pull_request` — `pull_request_target` runs from the base branch with write tokens, which is required to close fork PRs and post comments).

### help Command Design
- **D-11:** `bensdorp1 help [COMMAND]` is a real Typer command. When `COMMAND` is given, it delegates to Typer's built-in `--help` for that subcommand (no hand-crafted docs to maintain). When called without arguments, it shows the full categorized command list.
- **D-12:** Top-level `bensdorp1 --help` uses Typer Rich panels with `rich_markup_mode="rich"`. Commands grouped into panels using the `rich_help_panel` parameter on each `@app.command()`. The same panel groups appear when `help` is called with no argument.
- **D-13:** Command categories (panel names):
  - **Setup**: `init`, `restore`
  - **Daily operation**: `scan`, `last`, `history`
  - **Confirmations**: `buy`, `sell`, `fix`
  - **Positions**: `portfolio`, `detail`
  - **System**: `cash`, `config`, `audit`, `status`, `refresh`, `validate`, `help`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specifications
- `.planning/ROADMAP.md` §Phase 1 — Goal, success criteria, and requirements list for this phase
- `.planning/REQUIREMENTS.md` — CMD-17, REPO-01, REPO-02, REPO-03, REPO-06, REPO-07, TEST-06
- `.planning/PROJECT.md` — Key Decisions table (Typer, ruff, mypy strict already decided)

### Technology guidance (in CLAUDE.md)
- `CLAUDE.md` §Typer — Multi-Command Structure in Separate Modules: recommended layout, root app wiring pattern, per-command module pattern
- `CLAUDE.md` §pyproject.toml Structure for uv — Full annotated template, PEP 735 dependency groups, uv_build backend
- `CLAUDE.md` §Ruff Configuration — recommended pyproject.toml section, formatter config
- `CLAUDE.md` §mypy Strict Mode Configuration — full strict flags, Typer decorator workaround, stub packages
- `CLAUDE.md` §pytest and Coverage Configuration — coverage setup
- `CLAUDE.md` §Verified Library Versions — pinned versions for all dependencies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — this is Phase 1 and the codebase is empty.

### Established Patterns
- None yet — patterns will emerge from Phase 1 and be recorded for downstream phases.

### Integration Points
- `src/bensdorp1/cli.py` is the root Typer app — all commands registered here. Every subsequent phase adds command implementations to this file's command registry.
- `commands/` subpackage — each phase replaces a stub with a real implementation in the same file location.

</code_context>

<specifics>
## Specific Ideas

- User runs the CLI on Windows as their daily driver — Windows path handling must work correctly (use `pathlib.Path` throughout, never string concatenation).
- CI must pass on both ubuntu-latest and windows-latest from day 1, not as an afterthought.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Project Skeleton and Tooling*
*Context gathered: 2026-05-23*
