---
phase: 02-database-and-migrations
fixed_at: 2026-05-23T12:30:00Z
review_path: .planning/phases/02-database-and-migrations/02-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-05-23T12:30:00Z
**Source review:** .planning/phases/02-database-and-migrations/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (3 Critical + 6 Warning)
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: `driver_connection` null guard added

**Files modified:** `src/bensdorp1/db/backup.py`
**Commit:** 4ce7bbc
**Applied fix:** Replaced the `type: ignore[assignment]` cast with an `isinstance(sqlite_conn, sqlite3.Connection)` check. If the pool returns anything other than a `sqlite3.Connection`, a `RuntimeError` is raised with a diagnostic message before any file is opened — preventing a zero-byte corrupt backup from being written to disk.

---

### CR-02: All `DateTime` columns now use `timezone=True`

**Files modified:** `src/bensdorp1/db/schema.py`
**Commit:** 2a83214
**Applied fix:** Applied `DateTime(timezone=True)` to all 8 timestamp columns across 6 tables: `config.updated_at`, `scans.scan_date`, `scans.created_at`, `positions.entry_date`, `positions.closed_at`, `audit_log.occurred_at`, `constituents_cache.fetched_at`, `price_daily.trade_date`. SQLite will now store ISO-8601 strings with offset; retrieved values will no longer lose `tzinfo` on round-trip.

---

### CR-03: `_build_engine` creates parent directory before connecting

**Files modified:** `src/bensdorp1/db/engine.py`
**Commit:** a04f370
**Applied fix:** Added `path.parent.mkdir(parents=True, exist_ok=True)` as the first statement in `_build_engine`, before `URL.create()`. First-run users no longer see `OperationalError: unable to open database file` when `~/bensdorp1/data/` does not exist.

---

### WR-01: Double dispose in `db_engine` fixture teardown removed

**Files modified:** `tests/conftest.py`
**Commit:** d2b6dcb
**Applied fix:** Removed the redundant `engine.dispose()` call that followed `_reset_engine_for_testing()`. The internal `_reset_engine_for_testing()` function already calls `dispose()` on the cached engine. Updated the module docstring and teardown comment to correctly attribute where `dispose()` occurs.

---

### WR-02: `# noqa: UP017` suppression removed; import modernized

**Files modified:** `src/bensdorp1/db/backup.py`
**Commit:** 4ce7bbc
**Applied fix:** Changed `from datetime import datetime, timezone` to `from datetime import UTC, datetime`. Replaced `datetime.now(timezone.utc)` with `datetime.now(UTC)` and removed the `# noqa: UP017` comment. Now consistent with `audit.py`.

---

### WR-03: `get_engine` singleton behavior is now tested

**Files modified:** `tests/test_db_engine.py`
**Commit:** 1c2a8a0
**Applied fix:** Added two new tests:
- `test_get_engine_returns_cached_singleton`: calls `get_engine()` twice with different paths and asserts the same `Engine` object is returned both times.
- `test_get_engine_returns_engine_instance`: asserts the return type is `Engine`.
Both tests use `try/finally` to guarantee `_reset_engine_for_testing()` is called, preventing singleton pollution across tests.

---

### WR-04: Backup timestamp uses microsecond precision

**Files modified:** `src/bensdorp1/db/backup.py`
**Commit:** 4ce7bbc
**Applied fix:** Changed `strftime` format from `%Y%m%dT%H%M%SZ` to `%Y%m%dT%H%M%S_%fZ`. The `%f` directive provides 6-digit microsecond precision, making it practically impossible for two rapid calls to produce the same filename and silently overwrite each other.

---

### WR-05: Unique constraints added to `scan_candidates`

**Files modified:** `src/bensdorp1/db/schema.py`
**Commit:** 2a83214
**Applied fix:** Added two unique indexes after the `scan_candidates` table definition:
- `ix_scan_candidates_scan_rank` on `(scan_id, rank)` — prevents duplicate rank values within a single scan.
- `ix_scan_candidates_scan_symbol` on `(scan_id, symbol)` — prevents the same symbol appearing twice in a single scan's candidate list.

---

### WR-06: Local import in `run_migrations` moved to top level

**Files modified:** `src/bensdorp1/db/engine.py`
**Commit:** a04f370
**Applied fix:** Moved `from bensdorp1.db.schema import metadata` from inside `run_migrations` to the module top level. `schema.py` imports only from `sqlalchemy` and creates no circular dependency with `engine.py`. Removed the incorrect "avoids circular import risk" comment.

---

## Skipped Issues

None — all 9 in-scope findings were fixed.

---

_Fixed: 2026-05-23T12:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
