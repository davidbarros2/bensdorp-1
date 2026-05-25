---
phase: 09-consultation-commands
plan: "04"
subsystem: commands
tags: [history, cmd-05, read-only, render_table, subquery]
dependency_graph:
  requires: [09-01]
  provides: [CMD-05]
  affects: [cli, db.schema.scans, db.schema.scan_candidates, ui.render_table]
tech_stack:
  added: []
  patterns:
    - SQLAlchemy AND-filter construction via .where(*filters) splat (SP-7)
    - Per-scan top-3 sub-query ordered by rank ASC LIMIT 3
    - Optional[str] date argument parsed with datetime.date.fromisoformat + UTC wrapping
key_files:
  created: []
  modified:
    - src/bensdorp1/commands/history.py
    - tests/test_commands/test_history.py
decisions:
  - Detected `filters` list empty → table truly empty (no second COUNT query needed)
  - Used str | None (UP045 union syntax) after ruff flagged Optional[str] as fixable
metrics:
  duration: "~8 minutes"
  completed: "2026-05-25"
  tasks_completed: 1
  files_modified: 2
---

# Phase 09 Plan 04: History Command Summary

**One-liner:** `bensdorp1 history` renders a 5-column scan-history table with optional `--limit`/`--since` filters and per-scan top-3 candidate sub-query from `scan_candidates`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement history.py + fill in 4 test stubs | dbf43fa | src/bensdorp1/commands/history.py, tests/test_commands/test_history.py |

## What Was Built

Replaced the 11-line `history.py` stub with a full CMD-05 implementation:

- `@app.command(rich_help_panel="Daily operation")` with `--limit` (default 20) and `--since` (optional YYYY-MM-DD) options
- DB entry triad (SP-1): `get_engine` + `run_migrations` + `Console()`
- `--since` parsed with `datetime.date.fromisoformat(since)` wrapped as `datetime(..., tzinfo=UTC)`; invalid input exits code 1 with descriptive error
- `filters: list[Any] = []` built conditionally; passed to `.where(*filters)` (SP-7)
- Scans queried `ORDER BY scan_date DESC LIMIT limit`
- For each scan, sub-query `scan_candidates` ordered by `rank ASC LIMIT 3` → comma-joined string; bear days (zero candidates) show `"—"`
- 5-column `render_table` call: Date, Regime, Exits, Candidates, Top candidates
- Empty table (no filters + zero rows) → "No scans recorded yet. Run `bensdorp1 scan`..."
- Non-empty table filtered to zero rows → "No scans match the given filters."

Filled in 4 Wave 0 test stubs in `test_history.py`:
1. `test_history_empty_state_when_no_scans` — mock engine; empty fetchall; assert "No scans recorded yet" and exit 0
2. `test_history_shows_compact_table_ordered_by_date_desc` — real SQLite; 3 scans + candidates for middle scan; assert all dates present, "NVDA, AAPL, MSFT", em dash for bear day
3. `test_history_limit_flag_returns_only_n_rows` — 3 scans, `--limit 2`; assert only 2 most-recent dates appear
4. `test_history_invalid_since_exits_code_1` — `--since not-a-date`; assert exit code 1 and "Invalid --since" in output

## Verification

- `uv run pytest tests/test_commands/test_history.py -x -q` → 4 passed
- `uv run mypy --strict src/bensdorp1/commands/history.py` → 0 errors
- `uv run ruff check src/bensdorp1/commands/history.py tests/test_commands/test_history.py` → All checks passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced Optional[str] with str | None (ruff UP045)**
- **Found during:** Task 1 verification (ruff check)
- **Issue:** ruff UP045 flagged `Optional[str]` and `Optional[datetime.datetime]` as fixable — Python 3.10+ union syntax preferred
- **Fix:** Removed `Optional` import; replaced both annotations with `str | None` and `datetime.datetime | None`
- **Files modified:** src/bensdorp1/commands/history.py
- **Commit:** dbf43fa (fixed in same commit before staging)

## Known Stubs

None — all stubs replaced with working implementations.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The `--since` SQL injection threat (T-09-04-T1) is mitigated via `datetime.date.fromisoformat()` + SQLAlchemy parameterized binding. No new threat surface beyond what the plan's threat model already covers.

## Self-Check

- [x] `src/bensdorp1/commands/history.py` exists and contains implementation
- [x] `tests/test_commands/test_history.py` exists with 4 non-skipped tests
- [x] Commit dbf43fa exists in git log
