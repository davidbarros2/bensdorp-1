# Phase 5: UI Components - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 05-ui-components
**Areas discussed:** Source of truth for 31 rules, Rich Table vs. plain-text, Feedback threshold API, Testing scope, Confirmation prompts, Console instance ownership, Severity prefix API, config.py scope

---

## Source of Truth for the 31 Style Guide Rules

| Option | Description | Selected |
|--------|-------------|----------|
| REQUIREMENTS.md + FEATURES.md only | Treat the two planning docs as the complete source | |
| REQUIREMENTS.md + FEATURES.md + Bensdorp_1.md | All three combined | ✓ |

**User's choice:** REQUIREMENTS.md + FEATURES.md + `.planning/Bensdorp_1.md` (the full project spec)
**Notes:** `.planning/Bensdorp_1.md` exists in the .planning root and contains section 6 with exactly 31 numbered rules (6.1–6.31) plus section 7 with concrete flow screens. This is the authoritative spec document. REQUIREMENTS.md and FEATURES.md are supplementary.

---

## Rich Table vs. Plain-text Renderer

| Option | Description | Selected |
|--------|-------------|----------|
| Rich Table with box=None (Recommended) | box=None + show_edge=False + padding=(0,1) + header_style="" gives no-border minimalist output | ✓ |
| Plain-text formatter | Write string formatting manually (ljust/rjust), decoupled from Rich's Table internals | |

**User's choice:** Rich Table with box=None
**Notes:** Rich is mandated by spec 3.1. `padding=(0,1)` gives exactly 2-space column separation. `header_style=""` disables default bold headers (required by rule 6.31). Column `justify` handles alignment per rule 6.9.

---

## Feedback Threshold Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Context manager with declared total (Recommended) | Caller wraps in context manager; total=N for countable, omit for unknown-duration; threshold logic is internal | ✓ |
| Explicit tier selection by caller | Commands explicitly call feedback.spinner() or feedback.progress() | |
| Decorator-based | Decorate functions with @feedback.spinner or @feedback.progress(total=N) | |

**User's choice:** Context manager with declared total
**Notes:** Three primitives: `feedback.spinner()`, `feedback.track(total=N)`, `feedback.multi_step(total=N)`. Adaptive logic (which tier to show) is internal. Spec flows show operations always know their total when a progress bar is needed.

---

## Phase 5 Testing Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Console(record=True) + export_text() (Recommended) | Inject Console(record=True) into functions; capture via export_text(); mock time.time() for thresholds | ✓ |
| Capture stdout with capsys (pytest) | Functions print directly; use capsys.readouterr() | |
| Return strings, don't print | Functions return formatted strings; callers print | |

**User's choice:** Console(record=True) + export_text()
**Notes:** Unit tests only in Phase 5. Snapshot tests are Phase 13 territory. Pure format functions tested with plain assertions. Color path uses force_terminal=True; NO_COLOR fallback uses no_color=True.

---

## Confirmation Prompts ([y/n])

| Option | Description | Selected |
|--------|-------------|----------|
| Custom confirm_prompt() in ui/prompts.py (Recommended) | Uses input() directly; exact [y/n] display; re-prompts on empty; catches KeyboardInterrupt | ✓ |
| typer.confirm() with default=None | Built-in Typer; Ctrl+C raises typer.Abort() without spec's exact cancellation message | |
| Rich Prompt.ask() | More control than typer; but formats choices as (y/Y/n/N) not [y/n] by default | |

**User's choice:** Custom confirm_prompt() in ui/prompts.py
**Notes:** `typer.confirm()` doesn't produce spec rule 6.18's exact cancellation message on Ctrl+C without try/except at every call site. Custom function is simpler and fully spec-compliant.

---

## Console Instance Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Optional console parameter + module-level default (Recommended) | All functions accept console: Console | None = None; tests pass Console(record=True) | ✓ |
| Global singleton only | Module-level console; tests must monkeypatch | |
| Always require console parameter | No default; every caller must provide one | |

**User's choice:** Optional console parameter + module-level default
**Notes:** Module-level `_console = Console()` as fallback. Tests pass `Console(record=True)` explicitly — no global state mutation needed. Mirrors how Rich itself handles console injection.

---

## Severity Prefix API

| Option | Description | Selected |
|--------|-------------|----------|
| Shortcut aliases + base print_message() (Recommended) | print_error/warning/info/success shortcuts + base function | ✓ |
| Single format_message(Severity, title, ...) only | One function, caller always specifies severity | |
| MessageBuilder class | Builder pattern for complex messages | |

**User's choice:** Shortcut aliases + base print_message()
**Notes:** `print_message(severity, title, *, data, body, impact, actions, console)` as base. Shortcut aliases for readability in command code. `Severity` enum with ERROR/WARNING/INFO/SUCCESS. Color applied to prefix only per rule 6.13.

---

## config.py Scope in Phase 5

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 5 creates config.py with env-based config (Recommended) | PROJECT_NAME, MARKET_TZ, USER_TZ, DATA_DIR — no DB reads | ✓ |
| config.py stays in Phase 6 | Phase 5 hardcodes timezone defaults in ui/ | |

**User's choice:** Phase 5 creates config.py
**Notes:** Phase 5 needs USER_TZ and MARKET_TZ for rule 6.26 (timezone display). Phase 6+ needs DATA_DIR for DB path. Clean separation: config.py is static/env-based; DB holds mutable state. All constants defined once in spec 3.5.

---

## Claude's Discretion

- Exact Rich Table parameter values (box=None, show_edge=False, padding=(0,1)) — spec says "minimalist", implementation details chosen by builder
- Module-level `_console` location (`ui/styles.py` vs `ui/__init__.py`) — builder choice
- `Severity` enum vs string constants — builder choice (enum chosen for type safety)
- `ZoneInfo` key splitting for city label extraction — builder choice

## Deferred Ideas

None — discussion stayed within phase scope.
