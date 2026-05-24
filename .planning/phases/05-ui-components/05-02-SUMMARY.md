---
phase: 05-ui-components
plan: "02"
subsystem: ui
tags: [messages, empty-states, severity, rich, tdd]
dependency_graph:
  requires: [05-01]
  provides: [ui/messages.py, ui/empty_states.py]
  affects: [ui/__init__.py (05-05), all command modules (Phase 6+)]
tech_stack:
  added: []
  patterns: [Severity-enum-with-display-labels, Text-based-prefix-with-plain-title, markup-injection-guard, thin-delegation-wrapper]
key_files:
  created:
    - src/bensdorp1/ui/messages.py
    - src/bensdorp1/ui/empty_states.py
    - tests/test_ui/test_messages.py
    - tests/test_ui/test_empty_states.py
  modified:
    - src/bensdorp1/ui/styles.py
decisions:
  - "Severity uses plain Enum (not StrEnum) — values are display labels, not storage strings"
  - "Prefix line built as rich.text.Text() to prevent markup injection in title and prefix context"
  - "_render_kv_block hardened with markup=False, highlight=False for T-05-04 mitigation"
  - "print_message section order: data, impact, body, actions — matches spec rule 6.12 structure"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-24"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 5 Plan 02: Messages and Empty States Summary

**One-liner:** Severity-prefixed message system with Rich Text-based markup injection guard and thin empty-state wrapper delegating to print_info.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 (RED) | Failing tests for ui/messages.py — severity, color, kv alignment, markup injection | d9bd9f4 |
| 1 (GREEN) | Implement Severity enum, print_message, 4 shortcut aliases | 3af4536 |
| 2 (RED) | Failing tests for ui/empty_states.py — content, suggestion, Info prefix | c2ccd7b |
| 2 (GREEN) | Implement print_empty_state thin wrapper over print_info | 0534baa |

## What Was Built

### `src/bensdorp1/ui/messages.py`

- `class Severity(Enum)` with 4 members: ERROR="Error", WARNING="Warning", INFO="Info", SUCCESS="Success". Plain `Enum` (not `StrEnum`) — values are display labels.
- `_SEVERITY_COLORS: dict[Severity, str]` mapping each severity to its spec rule 6.29 color (red/yellow/cyan/green).
- `print_message(severity, title, *, data, body, impact, actions, console)` implementing rule 6.12 critical message structure. Builds prefix as `rich.text.Text()` to prevent markup injection in both prefix context and title (T-05-04 mitigation). Each optional block guarded by `if X:` — no spurious blank lines when absent (Pitfall #6).
- 4 shortcut aliases: `print_error`, `print_warning`, `print_info`, `print_success`.

### `src/bensdorp1/ui/empty_states.py`

- `print_empty_state(entity, suggestion=None, *, console)` — builds `"No {entity} found."`, optionally appends suggestion, delegates to `print_info`. 17 logical lines (thin wrapper per plan specification).

### Modified: `src/bensdorp1/ui/styles.py`

- `_render_kv_block` hardened with `markup=False, highlight=False` to prevent Rich markup injection from caller-supplied dict values (Rule 2 security fix — T-05-04 mitigation).

## Test Coverage

| File | Tests | Assertions Covered |
|------|-------|--------------------|
| tests/test_ui/test_messages.py | 23 | Severity enum values, all 4 prefix text outputs, all 4 ANSI colors, NO_COLOR fallback, kv alignment, actions list, impact+body blocks, markup injection guard (data values), title markup injection (no bold from injected markup), no bold ANSI, no decorative icons |
| tests/test_ui/test_empty_states.py | 6 | Basic content, suggestion appended, explicit console, Info prefix, no trailing garbage |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Security] Hardened _render_kv_block with markup=False**
- **Found during:** Task 1
- **Issue:** `_render_kv_block` in styles.py used `console.print(f"...")` which allowed Rich markup injection from untrusted `data` dict values. The plan called `_render_kv_block` for kv rendering but also required markup injection to be blocked (T-05-04).
- **Fix:** Added `markup=False, highlight=False` to `console.print()` call in `_render_kv_block`. All styles.py tests continue to pass (33 tests green).
- **Files modified:** `src/bensdorp1/ui/styles.py`
- **Commit:** 3af4536

**2. [Rule 2 - Security] Used Text() for prefix+title instead of f-string markup**
- **Found during:** Task 1
- **Issue:** The plan action suggested `con.print(prefix_markup + title, ...)` where title is concatenated into a Rich markup string. This would allow Rich markup injection from the `title` parameter if it contained `[bold]` etc.
- **Fix:** Built prefix line as `rich.text.Text()` object: append colored prefix text, then append plain title. This prevents any markup interpretation from the title string.
- **Files modified:** `src/bensdorp1/ui/messages.py`
- **Commit:** 3af4536

## Known Stubs

None — both modules are fully implemented with live data rendering.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model.

All T-05-04 mitigations verified:
- `data` dict values rendered with `markup=False` via `_render_kv_block`
- `title` rendered via `Text()` — no markup interpretation
- `body` lines rendered via `Text()` — no markup interpretation
- `impact` dict values rendered with `markup=False` via `_render_kv_block`
- `actions` items rendered via `Text()` — no markup interpretation

## Self-Check: PASSED

Files created:
- [x] src/bensdorp1/ui/messages.py
- [x] src/bensdorp1/ui/empty_states.py
- [x] tests/test_ui/test_messages.py
- [x] tests/test_ui/test_empty_states.py

Commits verified:
- [x] d9bd9f4 (RED test: messages)
- [x] 3af4536 (GREEN impl: messages)
- [x] c2ccd7b (RED test: empty_states)
- [x] 0534baa (GREEN impl: empty_states)

Test results:
- [x] 29/29 tests passing (23 messages + 6 empty_states)
- [x] mypy strict: 0 errors
- [x] ruff: 0 errors
