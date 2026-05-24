# Phase 5: UI Components - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the `ui/` subpackage and `config.py` — all shared formatting, rendering, and feedback primitives that every command (Phases 6–14) will call. This phase renders the 31 style-guide rules from spec section 6 as executable, tested code.

Specifically delivers:
- `src/bensdorp1/config.py` — static/env-based config constants (PROJECT_NAME, DATA_DIR, MARKET_TZ, USER_TZ)
- `src/bensdorp1/ui/__init__.py` — public API re-exports (mirrors db/, data/, strategy/ pattern)
- `src/bensdorp1/ui/styles.py` — Rich Style constants + color palette from spec 6.29
- `src/bensdorp1/ui/tables.py` — Rich Table renderer (no-border minimalist, rule 6.8/6.9)
- `src/bensdorp1/ui/messages.py` — severity prefix functions + critical message structure (rules 6.12/6.13)
- `src/bensdorp1/ui/prompts.py` — confirmation [y/n] prompt + free-text and number prompts (rules 6.15/6.16/6.17/6.18)
- `src/bensdorp1/ui/progress.py` — feedback threshold context managers: spinner, track, multi_step (rules 6.20/6.21/6.22/6.23)
- `src/bensdorp1/ui/empty_states.py` — empty state message helpers (rules 6.11/6.19)
- Numerical formatters (format_price, format_pct, format_pnl, format_volume, format_days) — rule 6.10
- Date/time formatters (format_date, format_time, format_timezone_pair, format_relative_duration) — rules 6.24/6.25/6.26/6.27

**Depends on:** Phase 1 (not Phase 4). No imports from db/, data/, or strategy/.

</domain>

<decisions>
## Implementation Decisions

### Source of Truth for UI Rules
- **D-01:** `.planning/Bensdorp_1.md` section 6 (rules 6.1–6.31) is the authoritative source for all 31 style-guide rules. Section 7 (specific flows: init, scan, buy/sell/fix, catch-up, restore) provides the concrete output layouts that ui/ primitives must produce. `REQUIREMENTS.md` UI-01–UI-10 and `research/FEATURES.md` output conventions are supplementary only. The planner must read Bensdorp_1.md §6 and §7 in full before writing any plan.

### Table Renderer
- **D-02:** Use Rich's `Table` class. Configuration: `box=None, show_edge=False, padding=(0, 1), header_style=""`. This produces no borders, no bold headers (rule 6.31), and 2-space column separation (1-space padding each side of a cell → 2-space gap between adjacent columns — rule 6.8). Number columns use `justify="right"` (rule 6.9). Text columns use `justify="left"`. Color and NO_COLOR/non-TTY fallback handled automatically by Rich's Console.

### Feedback Threshold API
- **D-03:** Context manager API with three primitives in `ui/progress.py`:
  - `feedback.spinner(description, console=None)` — unknown-duration operations. Silent if completes in <1s; braille spinner `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` (rule 6.22) if ≥1s. Returns context manager.
  - `feedback.track(description, total, console=None)` — countable items. Silent <1s; spinner 1–6s; progress bar 6–30s; progress bar + ETA >30s (rules 6.20/6.21). `advance(current_label)` called per iteration.
  - `feedback.multi_step(total, console=None)` — multi-phase wrapper. Returns a context manager whose `step(description, total=None)` method yields either a spinner (no total) or track context. Completed phases show `done.` appended (rule 6.23). Phase headers display as `[N/TOTAL] description`.

### Testing Approach
- **D-04:** Unit tests only in Phase 5. Snapshot tests are Phase 13 territory.
  - Format functions (pure): plain `assert` on return values.
  - Table/message/prompt rendering: instantiate `Console(record=True)`, run the render function passing that console, then `console.export_text()` → assert on the string.
  - Color path: `Console(record=True, force_terminal=True)` + `console.export_text(styles=True)` for ANSI verification.
  - NO_COLOR fallback: `Console(record=True, no_color=True)`.
  - Feedback threshold: mock `time.time()` to simulate elapsed durations; assert which visual tier activates.

### Confirmation Prompts
- **D-05:** Custom `confirm_prompt(message: str, *, console: Console | None = None) -> bool` in `ui/prompts.py`. Uses `input()` directly (not `typer.confirm()` or `Rich.Prompt`). Displays exactly `[y/n]` (rule 6.15). Accepts `y Y n N`; re-prompts on empty input or any other character. Catches `KeyboardInterrupt` → prints `"Operation aborted. No changes were made."` to console (rule 6.18) → returns `False`. Returning `False` on `n` also prints the cancellation message at the call site (each command is responsible for printing it after receiving `False`).

### Console Instance Ownership
- **D-06:** All UI functions accept an optional `console: Console | None = None` parameter. When `None`, falls back to a module-level `_console = Console()` defined in `ui/styles.py` (or `ui/__init__.py`). Tests always pass `Console(record=True)` explicitly. No global state mutation required for testing. The module-level `_console` uses default Rich settings (auto-detects TTY, respects `NO_COLOR` env var).

### Severity Prefix API
- **D-07:** `ui/messages.py` exposes:
  - A `Severity` enum: `ERROR`, `WARNING`, `INFO`, `SUCCESS`.
  - A base function: `print_message(severity: Severity, title: str, *, data: dict[str, str] | None = None, body: list[str] | None = None, impact: dict[str, str] | None = None, actions: list[str] | None = None, console: Console | None = None) -> None`. Implements the critical message structure from spec rule 6.12. Color applied to prefix only (rule 6.13); rest is terminal default.
  - Shortcut aliases: `print_error(title, ...)`, `print_warning(title, ...)`, `print_info(title, ...)`, `print_success(title, ...)`. Commands call shortcuts; base function is what tests verify.
  - Severity → prefix + color mapping: `Error:` red, `Warning:` yellow, `Info:` cyan, `Success:` green (rule 6.13). `bright_black` used for muted/secondary text (rule 6.29).

### config.py Scope
- **D-08:** Phase 5 creates `src/bensdorp1/config.py` with **env-based/static config only** — no DB reads, no I/O:
  ```python
  PROJECT_NAME = "bensdorp1"
  MARKET_TZ = ZoneInfo("America/New_York")
  USER_TZ = ZoneInfo(os.environ.get("BENSDORP1_USER_TZ", "Europe/Lisbon"))
  DATA_DIR = Path(os.environ.get("BENSDORP1_HOME", Path.home() / PROJECT_NAME))
  ```
  `ui/` imports `MARKET_TZ` and `USER_TZ` from `config.py` for timezone display (rule 6.26). Phases 6+ import `DATA_DIR` from `config.py` for DB path. `config.py` is read-only at import time — no side effects.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary specification (authoritative)
- `.planning/Bensdorp_1.md` §6 — The 31 UI/UX style guide rules 6.1–6.31 (canonical source of truth for all ui/ primitives)
- `.planning/Bensdorp_1.md` §7 — Specific flows: init (7.1), scan (7.2), buy (7.3), sell (7.4), fix (7.5), catch-up (7.6) — concrete output layouts that ui/ primitives must reproduce
- `.planning/Bensdorp_1.md` §3.1 — Rich explicitly mandated for output rendering
- `.planning/Bensdorp_1.md` §3.3 — Project layout: exact `ui/` module structure (styles.py, tables.py, messages.py, prompts.py, progress.py, empty_states.py)
- `.planning/Bensdorp_1.md` §3.5 — PROJECT_NAME parametrization (one definition, all refs use constant)

### Supplementary (for cross-reference)
- `.planning/REQUIREMENTS.md` — UI-01 through UI-10 (supplementary requirements; Bensdorp_1.md §6 is authoritative)
- `.planning/research/FEATURES.md` §Output Formatting Conventions — supplementary formatting conventions (numbers, colors, tables, dates)

### Phase dependency context
- `.planning/ROADMAP.md` §Phase 5 — Goal, success criteria (5 items), dependency on Phase 1
- `.planning/phases/01-project-skeleton-and-tooling/01-CONTEXT.md` — Phase 1 decisions; cli.py and _app.py patterns

### Technology
- `CLAUDE.md` §Verified Library Versions — `rich >=14.0`, `typer >=0.21.1` (Rich is a required dep of Typer since 0.12)
- `CLAUDE.md` §mypy Strict Mode Configuration — ui/ must pass mypy strict; no `# type: ignore` without documented reason
- `CLAUDE.md` §Ruff Configuration — formatter and linter rules apply to ui/

### Existing code (read before planning modules)
- `src/bensdorp1/_app.py` — Typer app: `rich_markup_mode="rich"`, `pretty_exceptions_enable=False`
- `src/bensdorp1/db/__init__.py` — re-export pattern that ui/__init__.py mirrors
- `src/bensdorp1/strategy/__init__.py` — re-export pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/bensdorp1/_app.py`: `app = typer.Typer(rich_markup_mode="rich", ...)` — Rich is already in the environment; no additional installation needed. `pretty_exceptions_enable=False` means error output goes through ui/ primitives, not Typer's built-in formatting.
- `src/bensdorp1/commands/help.py`: currently uses `typer.echo()` directly. It is the only real command implementation. After Phase 5, future commands will use ui/ primitives.
- `src/bensdorp1/db/__init__.py`, `src/bensdorp1/data/__init__.py`, `src/bensdorp1/strategy/__init__.py`: established re-export pattern — `ui/__init__.py` follows the same convention.

### Established Patterns
- **`src/` layout**: new subpackage at `src/bensdorp1/ui/`. No flat modules at repo root.
- **`-> None` explicit return types**: mypy strict requires annotations on every function; all ui/ functions that print must annotate `-> None`.
- **No circular imports**: `ui/` MUST NOT import from `commands/`, `db/`, `data/`, or `strategy/`. Only `config.py` and stdlib/Rich are allowed.
- **PEP 735 dependency groups**: no new runtime deps expected; Rich and typer already present.

### Integration Points
- `src/bensdorp1/commands/` — 17 stub command modules. They currently have no real logic. Phases 6–14 will import from `ui/` to produce all their output. Phase 5 does not modify existing command stubs.
- `tests/` — Phase 5 creates `tests/test_ui/` directory mirroring the `ui/` structure. Tests use `conftest.py` from the root tests/ for shared fixtures (e.g., `test_console` fixture returning `Console(record=True)`).

</code_context>

<specifics>
## Specific Ideas

### Exact spinner frames
Rule 6.22 specifies exactly: `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` (10 frames, Unicode braille). Not ASCII. Not any other sequence. Rich has built-in spinners — check if "dots" or another preset matches exactly; if not, register a custom spinner.

### Progress bar characters
Rule 6.30 explicitly allows `█` (full block) and `░` (light shade) as exceptions to the no-unicode-icons rule. The progress bar uses these two characters only.

### Progress bar layout (rule 6.21)
```
[N/TOTAL] Description of the current step...

Progress:   ████████████░░░░░░░░  127/503  (25%)
Current:    GOOGL — additional context
Elapsed:    1m 42s
Remaining:  ~5m 12s
```
This is the exact required format. The `track()` context manager must reproduce this layout.

### Key:value alignment (rule 6.4)
When multiple key:value pairs appear in a block, values align at the column determined by the longest key + colon + 2 spaces. `ui/messages.py` must implement this alignment for the `data=` dict parameter of `print_message()`.

### Relative duration brackets (rule 6.27)
- Less than 1 minute: `just now`
- 1–59 minutes: `N minutes ago`
- 1–23 hours: `N hours ago`
- 1–30 days: `N days ago`
- 1–11 months: `N months ago`
- 1+ years: `N years ago`

### Screen title separators (rule 6.2)
`===` spanning **full content width** for screen titles (e.g., `bensdorp1 init` welcome screen). `---` spanning **only the section header text width** for subsection headers. Always one blank line before and after every separator.

### No bold anywhere (rule 6.31)
`header_style=""` on Rich Tables. No `[bold]` markup anywhere in ui/. No Rich Text with bold Style. Even file paths and commands in output use plain text.

### Timezone display city label (rule 6.26)
The user's local timezone label is the **city name**: "Lisbon" (not "WET", not "UTC+1", not "Europe/Lisbon"). `USER_TZ`'s city is extracted from the ZoneInfo key: `USER_TZ.key.split("/")[-1]` → "Lisbon". For `America/New_York` → display as "ET" (Eastern Time abbreviation, not "New_York").

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 5-UI Components*
*Context gathered: 2026-05-24*
