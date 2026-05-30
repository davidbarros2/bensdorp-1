---
phase: 10-system-commands
fixed_at: 2026-05-30T16:10:00Z
review_path: .planning/phases/10-system-commands/10-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-05-30T16:10:00Z
**Source review:** .planning/phases/10-system-commands/10-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01 + CR-02 + WR-03: restore.py correctness fixes (committed together)

**Files modified:** `src/bensdorp1/commands/restore.py`, `src/bensdorp1/db/engine.py`, `src/bensdorp1/db/__init__.py`
**Commit:** b75f72b
**Applied fix:**
- CR-01: Added `reset_engine()` public helper to `db/engine.py` (disposes and clears the singleton). Exported it from `db/__init__.py`. In `restore.py`, after `shutil.copy2` succeeds, call `reset_engine()` then `get_engine(db_path)` to get a fresh engine, and pass that fresh engine to `log_event()`. This ensures the audit event is written to the newly-restored database rather than stale connection state.
- CR-02: Replaced `shutil.copy2(db_path, pre_restore_path)` for the pre-restore backup with `create_backup(engine, backups_dir)`, which uses `sqlite3.Connection.backup()` for a consistent snapshot that is safe even with an active WAL file. Removed manual timestamp/path construction — `create_backup` returns the path.
- WR-03: Added `if not db_path.exists()` guard before the pre-restore backup step. If the active database does not exist (user never ran `init`), prints a clear error message and exits with code 1 instead of producing a misleading `FileNotFoundError` from `shutil.copy2`.

---

### WR-01: Standardise health label severity ladder in status.py

**Files modified:** `src/bensdorp1/commands/status.py`
**Commit:** 9c3cdcf
**Applied fix:** Replaced the inconsistent `OK / STALE / WARNING` ladder with a uniform `OK / STALE / OUTDATED` ladder used by both the constituents section and the backup section. Renamed `_WARNING_DAYS_CONSTITUENTS` to `_OUTDATED_DAYS_CONSTITUENTS`. Added `_OUTDATED_DAYS_BACKUP = 7` threshold to give the backup section a three-tier ladder (was previously only two tiers: OK / STALE). Added a comment documenting the severity ordering at the threshold constants block.

---

### WR-02: Catch TypeError in operational section staleness check

**Files modified:** `src/bensdorp1/commands/status.py`
**Commit:** 5690fdf
**Applied fix:** Extended `except ValueError` to `except (ValueError, TypeError)` in `_operational_section`. When SQLite returns the aggregate `max(scan_date)` as a raw `str` instead of a `datetime`, the comparison `str >= date` raises `TypeError`. The previous except clause did not catch it, causing the `status` command to crash. Added an inline comment explaining the root cause.

---

### IN-01: Inline `_health_label` trivial wrapper

**Files modified:** `src/bensdorp1/commands/status.py`
**Commit:** 6cf85df
**Applied fix:** Removed the `_health_label()` function (body was `return f"[{label}]"`) and replaced all 5 call sites with inline f-strings or string literals. Also updated the empty-cache constituents label from `[WARNING]` to `[OUTDATED]` to stay consistent with the `OK/STALE/OUTDATED` ladder introduced in WR-01.

---

### IN-02: Remove fragile scalar-order mock in test_status_integrity_failed

**Files modified:** `tests/test_commands/test_status.py`
**Commit:** 92c1be0
**Applied fix:** Rewrote `test_status_integrity_failed` to accept the real `db_engine` fixture and patch only `_database_section` to return a canned `{"Integrity check": "FAILED"}` dict. This eliminates the shared `scalar_call_count` counter whose correctness depended on the undocumented section-call order inside `status()`. Also removed the now-unused `MagicMock` import.

---

---

### Post-fix: test_restore_full_flow glob pattern

**Files modified:** `tests/test_commands/test_restore.py`
**Commit:** 8efee50
**Applied fix:** CR-02 changed the pre-restore backup from `shutil.copy2` (which used a `bensdorp1-pre-restore-*.db` filename) to `create_backup()` (which generates `bensdorp1-{timestamp}.db`). Updated the test assertion from `glob("bensdorp1-pre-restore-*.db")` to `glob("bensdorp1-*.db")` excluding `bensdorp1-latest.db`.

---

**Final state:** 375/375 tests passing. `ruff check` and `mypy` clean.

_Fixed: 2026-05-30T16:10:00Z_
_Fixer: Claude (gsd-code-fixer) + orchestrator_
_Iteration: 1_
