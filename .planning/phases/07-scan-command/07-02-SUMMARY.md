---
phase: 07-scan-command
plan: "02"
subsystem: commands/_scan_engine
tags: [scan, engine, stop-updates, exit-triggers, catch-up, wave-2]
dependency_graph:
  requires: ["07-01"]
  provides: [run_scan public entry, 7 internal scan helpers, scan_exit_triggers writes]
  affects:
    - src/bensdorp1/commands/_scan_engine.py
tech_stack:
  added: []
  patterns:
    - two-console strategy (con for progress, capture for raw_output)
    - SQLAlchemy ON CONFLICT DO UPDATE for idempotent scan rows
    - NamedTuple internal data structures (_OpenPosition, _TriggerRow)
    - triggered_position_ids set[int] for stop-freeze enforcement
key_files:
  created:
    - src/bensdorp1/commands/_scan_engine.py
  modified: []
decisions:
  - "Two-console strategy: con=progress display, capture=Console(record=True) for raw_output storage and replay"
  - "triggered_position_ids: set[int] tracks stop-freeze across catch-up loop + today (D-07/Pitfall 8)"
  - "_persist_scan_placeholder inserts minimal scans row first to get scan_id FK for scan_exit_triggers; updated with full data in _persist_scan"
  - "Volume display in top-10 table computed via _compute_avg_volumes (separate helper) — matches liquidity_filter 20-day window"
  - "SPX close/SMA rendered with f'{value:,.2f}' (no $ sign) per spec §7.2 — not format_price()"
  - "Bear market note appended to catch_up_notes list before system notes render (D-21)"
metrics:
  duration: "6 minutes"
  completed_date: "2026-05-24"
  tasks: 1
  files: 1
---

# Phase 7 Plan 02: Scan Engine Implementation Summary

Full scan business-logic engine in `_scan_engine.py` with `run_scan(engine, *, force, console) -> str` public entry point and all 7 private helpers: stop-freeze tracking via `triggered_position_ids: set[int]`, catch-up loop over missed trading days, SQLite upsert idempotency, and two-console render strategy.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create _scan_engine.py with all 7 helpers + run_scan | 918d95b | src/bensdorp1/commands/_scan_engine.py |

## Verification Results

```
uv run mypy src/bensdorp1/commands/_scan_engine.py --strict
  -> Success: no issues found in 1 source file (exit 0)

uv run ruff check src/bensdorp1/commands/_scan_engine.py
  -> All checks passed! (exit 0)

uv run ruff format --check src/bensdorp1/commands/_scan_engine.py
  -> 1 file already formatted (exit 0)

File line count: 1095 (min 250 required — PASS)
```

### Acceptance criteria:

- [x] src/bensdorp1/commands/_scan_engine.py exists
- [x] uv run mypy _scan_engine.py --strict exits 0
- [x] uv run ruff check _scan_engine.py exits 0
- [x] uv run ruff format --check _scan_engine.py exits 0
- [x] File contains: def run_scan(
- [x] File contains: def _run_preflight(
- [x] File contains: def _fetch_data(
- [x] File contains: def _update_position_stops(
- [x] File contains: def _detect_exit_triggers(
- [x] File contains: def _run_screening(
- [x] File contains: def _render_output(
- [x] File contains: def _persist_scan(
- [x] File contains: triggered_position_ids: set[int]
- [x] File contains: on_conflict_do_update
- [x] File contains: DATA_DIR / "backups"
- [x] File does NOT contain: format_price(spx
- [x] File does NOT contain: import typer
- [x] File does NOT contain: from bensdorp1._app

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy: unused type: ignore comment + non-indexable Any**
- **Found during:** Task 1 verification (mypy --strict)
- **Issue 1:** `# type: ignore[assignment]` on `entry_date.date()` was flagged as unused — mypy correctly inferred the type; comment was unnecessary.
- **Issue 2:** `result.inserted_primary_key[0]` — `inserted_primary_key` typed as `Any | None` in SQLAlchemy stubs; direct index wasn't accepted without assignment to typed var first.
- **Fix:** Removed the superfluous ignore comment; used intermediate untyped `pk` variable then cast to `int`.
- **Files modified:** src/bensdorp1/commands/_scan_engine.py
- **Commit:** 918d95b (fixed inline before commit)

**2. [Rule 1 - Bug] ruff I001 import sort + ruff format violations**
- **Found during:** Task 1 verification (ruff check / ruff format --check)
- **Issue:** Import block order and formatting did not match ruff expectations; `from bensdorp1.db.schema import config as config_table` was grouped with the rest of the schema imports but ruff split them.
- **Fix:** Applied `ruff check --fix` for I001; applied `ruff format` for formatting.
- **Files modified:** src/bensdorp1/commands/_scan_engine.py
- **Commit:** 918d95b (fixed inline before commit)

**3. [Rule 2 - Auto-add] Volume display for top-10 buy candidates table**
- **Found during:** Task 1 implementation (spec §7.2 requires "Volume (avg 20d)" column)
- **Issue:** Plan spec required `Volume (avg 20d)` column in top-10 table; `format_volume` was imported in the plan but no volume source was passed to `_render_output`.
- **Fix:** Added `_compute_avg_volumes(price_dfs) -> dict[str, int]` helper that mirrors `liquidity_filter`'s 20-day volume window; passed `avg_volumes` dict to `_render_output` as an additional parameter.
- **Files modified:** src/bensdorp1/commands/_scan_engine.py
- **Commit:** 918d95b (fixed inline before commit)

## Known Stubs

None. The plan produced a complete implementation with no stubs or placeholder values.

## Threat Flags

No new security-relevant surface beyond what the plan's threat model covers:
- T-7-01 (SQL injection): All DB writes use SQLAlchemy bound parameters via `.where(col == val)` and `.values(col=val)` — no f-string or %-format SQL.
- T-7-02 (Rich markup injection): All symbol strings from DB flow through `render_table` (which uses `Text(cell)` per row) and `render_kv_block` (uses `markup=False` internally). Direct `capture.print(Text(...))` used for all other strings.
- T-7-03 (Path traversal): `create_backup(engine, DATA_DIR / "backups")` uses Path join.

## Self-Check: PASSED

- [x] src/bensdorp1/commands/_scan_engine.py — 1095 lines, all 8 functions present
- [x] Commit 918d95b exists and created the file
- [x] mypy strict: Success (0 errors)
- [x] ruff check: All checks passed
- [x] ruff format: Already formatted
