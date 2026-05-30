---
phase: 10-system-commands
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/bensdorp1/commands/status.py
  - src/bensdorp1/commands/refresh.py
  - src/bensdorp1/commands/restore.py
  - tests/test_commands/test_status.py
  - tests/test_commands/test_refresh.py
  - tests/test_commands/test_restore.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-05-30T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Three command modules were reviewed: `status.py` (health dashboard), `refresh.py` (force re-fetch of S&P 500 constituents), and `restore.py` (database restore from backup file), plus their corresponding test suites. The logic is generally coherent and the defensive patterns are solid (parameterized SQL, markup=False throughout, Windows path handling). Two correctness bugs were found — both in `restore.py` — and three robustness warnings were found across `status.py` and `restore.py`.

---

## Critical Issues

### CR-01: Audit event written to wrong (stale) engine after restore

**File:** `src/bensdorp1/commands/restore.py:161`

**Issue:** After `shutil.copy2(resolved, db_path)` overwrites the live database file at step 8, step 9 calls `log_event(engine, ...)` using the `engine` created at the top of the function (step 1, before the restore). SQLAlchemy's connection pool still holds a pool of connections to the **pre-restore** file. On SQLite with the default `StaticPool` / `NullPool` path, the underlying file descriptor was opened before the overwrite; depending on OS and pool configuration, the audit event is either written to the old WAL state that is subsequently discarded, or silently succeeds but only because the pool reopens the file — in which case the comment "Log RESTORE_PERFORMED to the **restored** DB" is correct by coincidence, not by design.

The real risk is that `get_engine()` caches the engine as a module-level singleton (`_engine` in `db/engine.py`). Subsequent commands reuse that same engine. If SQLite's connection pool cached an open file handle to the old database before `shutil.copy2` replaced the file, those subsequent commands may operate on stale connection state until the process exits. The correct approach is to dispose the engine after the file copy and call `get_engine()` fresh so the pool re-opens the new file.

**Fix:**
```python
# After shutil.copy2(resolved, db_path) succeeds:
engine.dispose()  # release all pooled connections to the old file
from bensdorp1.db.engine import _reset_engine_for_testing  # or make a public reset helper
# --- better: expose a public reset in db/__init__.py ---
# For production code, call a new public helper:
#   bensdorp1.db.reset_engine()
# which calls _reset_engine_for_testing(None), then:
fresh_engine = get_engine(db_path)
log_event(fresh_engine, AuditEventType.RESTORE_PERFORMED, payload=payload)
```

At minimum, add `engine.dispose()` before `log_event()`. Ideally, expose `_reset_engine_for_testing` under a production-safe name (e.g., `reset_engine`) in `db/__init__.py` so `restore.py` can clear and re-initialize the singleton cleanly.

---

### CR-02: Pre-restore backup uses `shutil.copy2` on live database — same bug `backup.py` explicitly avoids

**File:** `src/bensdorp1/commands/restore.py:140`

**Issue:** Step 7 creates the pre-restore backup with:
```python
shutil.copy2(db_path, pre_restore_path)
```
`backup.py` — the project's own backup primitive — explicitly documents why `shutil.copy2` on a live file is wrong and instead uses `sqlite3.Connection.backup()` to take a consistent snapshot even while a writer is active (see `backup.py` lines 5-7: "Uses `sqlite3.Connection.backup()` (NOT shutil.copy on the live file)"). If the database has an active WAL (Write-Ahead Log) file at the time of restore, the copied file may be in an inconsistent state. The pre-restore backup is the user's only safety net — an inconsistent file defeats its purpose.

**Fix:**
```python
from bensdorp1.db import create_backup

# Replace step 7:
# shutil.copy2(db_path, pre_restore_path)  # WRONG — may copy inconsistent WAL state
pre_restore_path = create_backup(engine, backups_dir)
# create_backup() uses sqlite3.Connection.backup() for consistency
# and returns the path to the newly created file
```

---

## Warnings

### WR-01: `_constituents_section` threshold labels are inverted — STALE is less severe than WARNING

**File:** `src/bensdorp1/commands/status.py:76-82`

**Issue:** The threshold ordering and label assignment reads:
```python
if age <= timedelta(days=_STALE_DAYS_CONSTITUENTS):   # <= 7 days
    label = "OK"
elif age <= timedelta(days=_WARNING_DAYS_CONSTITUENTS):  # <= 14 days
    label = "STALE"
else:                                                  # > 14 days
    label = "WARNING"
```
This makes `[STALE]` a *less* severe signal than `[WARNING]`. In conventional usage "stale" means "old but maybe ok" while "warning" means "take action". The label semantics match that expectation. However, in the backup section (`_backup_section`, line 119) the only two labels are `OK` / `STALE`, with no "WARNING" tier. This inconsistency means the user sees `[WARNING]` (the most severe label) when constituents are > 14 days old, but `[STALE]` (middle tier) when the *backup* is > 3 days old — even though a stale backup is arguably more urgent than slightly old constituent data. The label naming is inconsistent across sections and will confuse users.

**Fix:** Standardise the severity ladder across all sections. Either use `OK / WARNING / CRITICAL` uniformly, or rename the constituent section's third-tier label to something other than `WARNING` (e.g., `OUTDATED`). The backup section should gain a third `WARNING` tier if > 7 days. At minimum, document the intended severity ordering at the top of the module so future maintainers do not accidentally invert tiers.

---

### WR-02: `_operational_section` last-scan staleness check silently degrades on non-datetime scalar

**File:** `src/bensdorp1/commands/status.py:169-189`

**Issue:** `scans.c.scan_date` is declared `DateTime(timezone=True)` in schema. SQLAlchemy may return the raw scalar from `func.max(scans.c.scan_date)` as either a `datetime` or a plain `str` (SQLite stores ISO strings and the column converter does not always fire on aggregate functions). The code guards against this with `isinstance(last_scan_dt, datetime)` checks at lines 170 and 177, and falls back to `str(last_scan_dt)` for display — correctly. However the staleness label at line 181 is only computed inside the `isinstance(last_scan_dt, datetime)` branch; if the returned value is a string (not a datetime), the code still reaches `label = "OK" if scan_date >= boundary else "STALE"` at line 181 because `scan_date` is set unconditionally at line 177-180:

```python
scan_date = (
    last_scan_dt.date()          # only reached when isinstance is True
    if isinstance(last_scan_dt, datetime)
    else last_scan_dt            # raw str — comparing str >= date raises TypeError
)
label = "OK" if scan_date >= boundary else "STALE"
```

If SQLite returns a string (e.g., `"2026-05-29 20:00:00+00:00"`), `scan_date` is that string, and `scan_date >= boundary` compares `str >= date`, raising `TypeError` at runtime. The `except ValueError` at line 182 does *not* catch `TypeError`, so the command crashes.

**Fix:**
```python
except (ValueError, TypeError):
    label = "STALE"
```
Or, more robustly, parse the raw scalar through a helper that always returns a `date`:
```python
if isinstance(last_scan_raw, str):
    from datetime import date
    last_scan_dt = datetime.fromisoformat(last_scan_raw).replace(tzinfo=UTC)
```

---

### WR-03: `restore` disposes `val_engine` in `finally` but does not guard `engine.connect()` failure before the pre-restore backup

**File:** `src/bensdorp1/commands/restore.py:47-57`

**Issue:** If `run_migrations(engine)` at line 50 raises (e.g., the active database is locked or corrupt), execution still reaches step 7 (`shutil.copy2(db_path, pre_restore_path)`) — except it does not, because an exception propagates. However there is a subtler issue: `db_path` (line 48) is constructed as `DATA_DIR / "data" / "bensdorp1.db"` but no check is performed that this file actually exists before calling `shutil.copy2(db_path, pre_restore_path)` at line 140. If the user has never run `bensdorp1 init` and the active DB does not exist, `shutil.copy2` raises `FileNotFoundError`, which is caught by the generic `except Exception` at line 145 and reported as "Failed to copy backup file to active database" — a misleading error message for a missing source file rather than a missing destination write.

**Fix:**
```python
# Before step 7 (line 137), add an existence guard:
if not db_path.exists():
    print_error(
        "No active database found. Run `bensdorp1 init` first.",
        console=console,
    )
    raise typer.Exit(code=1)
```

---

## Info

### IN-01: `_health_label` is a trivial wrapper with no added value

**File:** `src/bensdorp1/commands/status.py:40-42`

**Issue:** The function body is exactly `return f"[{label}]"`. It is called 6 times in the file but adds no validation, formatting logic, or future-proofing — it is purely an f-string alias. This is dead abstraction: readers must look up the function to understand what it does, gaining nothing over the inline literal.

**Fix:** Inline the format string at call sites, e.g., replace `_health_label('OK')` with `"[OK]"`. If the bracket format is intentionally centralised for future UI-framework migration, add a comment explaining that intent.

---

### IN-02: Test `test_status_integrity_failed` comment and scalar call order are misaligned

**File:** `tests/test_commands/test_status.py:121`

**Issue:** The comment at line 121 says `scalar_call_count == 1` maps to "price_daily count (from constituents section)". Looking at the production code, `_constituents_section` calls `select(func.count(price_daily.c.id))` via `.scalar()` (line 60 of `status.py`). But `_operational_section` calls `.scalar()` three times (lines 150, 153, 156). The mock comment says call 1 = price_daily count, call 2 = last scan date, calls 3+ = 0 for position counts. This ordering is only correct if all four section helper functions execute their queries in a predictable, sequential, single-connection context — which they do not. Each section opens its own `engine.connect()` context, meaning the mock's `conn.execute.side_effect` counter is shared across all `connect()` calls but the ordering depends on the section call order in `status()`. If the section call order changes, the mock silently breaks. This is a test fragility issue rather than a correctness bug, but it is a meaningful reliability concern.

**Fix:** Use separate `MagicMock` objects per section, or use a real in-memory engine (as `db_engine` fixture provides) for the integrity-check test instead of a fully hand-rolled mock. The existing `db_engine`-based tests (`test_status_ok_constituents`, etc.) are more robust; the mock-only test should either be eliminated or its mock setup documented with an explicit ordering guarantee.

---

_Reviewed: 2026-05-30T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
