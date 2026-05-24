---
phase: 05-ui-components
plan: "01"
subsystem: ui
tags:
  - config
  - ui
  - formatters
  - rich
  - zoneinfo
dependency_graph:
  requires:
    - "01-project-skeleton-and-tooling"
  provides:
    - "bensdorp1.config (PROJECT_NAME, MARKET_TZ, USER_TZ, DATA_DIR)"
    - "bensdorp1.ui.styles (_console, Style constants, all formatters, _render_kv_block)"
  affects:
    - "05-02 through 05-05: all subsequent ui/ plans import from these modules"
tech_stack:
  added:
    - "bensdorp1.config — env-resolved static constants (no new deps)"
    - "bensdorp1.ui.styles — Rich Style constants and pure formatter functions"
  patterns:
    - "Module-level singleton: _console = Console() (analog: data/calendar.py _NYSE)"
    - "Env-resolution at import time: ZoneInfo(os.environ.get(...))"
    - "Pure formatter functions with explicit -> str return types"
    - "KV alignment via max_key_len + 2 padding per rule 6.4"
    - "_now injection for testability in format_relative_duration"
key_files:
  created:
    - src/bensdorp1/config.py
    - src/bensdorp1/ui/__init__.py
    - src/bensdorp1/ui/styles.py
    - tests/test_ui/__init__.py
    - tests/test_ui/test_config.py
    - tests/test_ui/test_styles.py
  modified: []
decisions:
  - "Used datetime.UTC alias (UP017) instead of timezone.utc — ruff enforces this"
  - "SPINNERS accessed via cast(dict[str, Any], _rs.SPINNERS) with type: ignore[attr-defined] — not in rich.spinner __all__ but present at runtime (verified)"
  - "format_relative_duration uses optional _now kwarg for test injection — avoids monkeypatching datetime.now"
  - "Spinner frames comparison uses list(raw_frames) to handle str vs list[str] — Rich 15 returns str, not list"
metrics:
  duration: "~7 minutes"
  completed_date: "2026-05-24"
  tasks_completed: 2
  files_created: 6
---

# Phase 5 Plan 01: Config and Styles Foundation Summary

**One-liner:** `config.py` env-resolved constants (PROJECT_NAME, MARKET_TZ, USER_TZ, DATA_DIR) and `ui/styles.py` Rich console singleton, color palette, 9 formatter functions, and kv-alignment helper — all pure/static, mypy strict clean.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing tests for config.py | 5e2e766 | tests/test_ui/__init__.py, tests/test_ui/test_config.py |
| 1 (GREEN) | Implement config.py | 1170fd9 | src/bensdorp1/config.py, tests/test_ui/test_config.py |
| 2 (RED) | Add failing tests for ui/styles.py | 18b51cc | src/bensdorp1/ui/__init__.py, tests/test_ui/test_styles.py |
| 2 (GREEN) | Implement ui/styles.py | bb3e629 | src/bensdorp1/ui/styles.py, tests/test_ui/test_styles.py |

## Verification Results

- `uv run pytest tests/test_ui/test_config.py tests/test_ui/test_styles.py -x -q`: 41 passed
- `uv run mypy src/bensdorp1/config.py src/bensdorp1/ui/styles.py src/bensdorp1/ui/__init__.py`: no issues
- `uv run ruff check src/bensdorp1/config.py src/bensdorp1/ui/ tests/test_ui/`: no errors
- No imports from bensdorp1.db, bensdorp1.data, bensdorp1.strategy, or bensdorp1.commands

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rich SPINNERS["dots"]["frames"] is str, not list[str]**
- **Found during:** Task 2, GREEN phase
- **Issue:** The plan's test template assumes `list(SPINNERS["dots"]["frames"])` converts a list to a list. In Rich 15.0.0, `SPINNERS["dots"]["frames"]` is a raw string `"⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"`, not a list. `list()` on a string gives list of chars, which matches expected `list("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")`.
- **Fix:** Test uses `list(raw_frames)` which works for both str and list[str] — normalises to `list[str]` for comparison.
- **Files modified:** tests/test_ui/test_styles.py
- **Commit:** bb3e629

**2. [Rule 1 - Bug] SPINNERS not in rich.spinner __all__**
- **Found during:** Task 2, GREEN phase
- **Issue:** mypy strict emits `attr-defined` error for `rich.spinner.SPINNERS` because it is not in `__all__`.
- **Fix:** Used `_rs.SPINNERS  # type: ignore[attr-defined]` with `cast` to `dict[str, Any]` for clean typing.
- **Files modified:** tests/test_ui/test_styles.py
- **Commit:** bb3e629

**3. [Rule 1 - Bug] UP017 timezone.utc should be datetime.UTC**
- **Found during:** Both tasks
- **Issue:** Ruff UP017 rule requires `datetime.UTC` alias over `timezone.utc` (Python 3.11+).
- **Fix:** Used `from datetime import UTC` and replaced all `timezone.utc` references.
- **Files modified:** src/bensdorp1/ui/styles.py, tests/test_ui/test_styles.py
- **Commit:** bb3e629

## Known Stubs

None — all formatters return spec-conformant strings; no placeholder data.

## Threat Flags

No new threat surface beyond what the plan's threat model documents.

## Self-Check: PASSED

- src/bensdorp1/config.py: FOUND
- src/bensdorp1/ui/__init__.py: FOUND
- src/bensdorp1/ui/styles.py: FOUND
- tests/test_ui/__init__.py: FOUND
- tests/test_ui/test_config.py: FOUND
- tests/test_ui/test_styles.py: FOUND
- Commit 5e2e766: FOUND (test RED config)
- Commit 1170fd9: FOUND (feat GREEN config)
- Commit 18b51cc: FOUND (test RED styles)
- Commit bb3e629: FOUND (feat GREEN styles)
