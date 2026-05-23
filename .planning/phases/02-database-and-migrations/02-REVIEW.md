---
phase: 02-database-and-migrations
reviewed: 2026-05-23T11:58:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/bensdorp1/db/__init__.py
  - src/bensdorp1/db/audit.py
  - src/bensdorp1/db/backup.py
  - src/bensdorp1/db/engine.py
  - src/bensdorp1/db/schema.py
  - tests/conftest.py
  - tests/test_db_audit.py
  - tests/test_db_backup.py
  - tests/test_db_engine.py
  - tests/test_db_positions.py
  - tests/test_db_schema.py
findings:
  critical: 3
  warning: 6
  info: 3
  total: 12
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-23T11:58:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the full `db/` subpackage (schema DDL, engine singleton, backup primitive, audit event log) and all associated tests. The overall architecture is sound — SQLAlchemy Core 2.0, parameterized inserts, the Windows-safe `sqlite3.Connection.backup()` API, and the StrEnum audit event log are all correctly chosen. However, three blockers were found: (1) a missing null guard on `driver_connection` in `backup.py` that can produce a corrupted backup file and a misleading `AttributeError`; (2) `DateTime` columns throughout `schema.py` silently strip timezone info on round-trip, making all retrieved timestamps naive and breaking any UTC comparison in future commands; (3) `_build_engine` / `get_engine` never creates the parent directory for the DB file, causing a cryptic `OperationalError` on first run. Additionally six warnings cover a double-dispose in the test fixture teardown, an unnecessary suppressed ruff rule, an untested public API, a silent timestamp-collision overwrite in backups, a missing uniqueness constraint on scan candidates, and a missing guard for large volume integers.

---

## Critical Issues

### CR-01: `driver_connection` can return `None`; null guard is missing, leaving a corrupted backup file on disk

**File:** `src/bensdorp1/db/backup.py:45-48`

**Issue:** `raw_conn.driver_connection` is typed `Optional[Any]` by SQLAlchemy (confirmed in source). It returns `None` when `_connection_record.dbapi_connection is None`, which can happen if the pool connection is in an invalidated state. The `type: ignore[assignment]` on line 45 suppresses the type error rather than handling it. When `driver_connection` is `None`, line 48 raises `AttributeError: 'NoneType' object has no attribute 'backup'`. The `finally` block closes `backup_sqlite_conn` (which was already opened by `sqlite3.connect()` on line 46, creating an empty file on disk), but `shutil.copy2` is never called. The result is a zero-byte backup file left on disk and `bensdorp1-latest.db` not updated — silent data integrity failure with no diagnostic message.

**Fix:**
```python
raw_conn = engine.raw_connection()
try:
    sqlite_conn = raw_conn.driver_connection
    if not isinstance(sqlite_conn, sqlite3.Connection):
        raise RuntimeError(
            f"Expected sqlite3.Connection from pool; got {type(sqlite_conn)!r}. "
            "Cannot create backup."
        )
    backup_sqlite_conn = sqlite3.connect(str(backup_path))
    try:
        sqlite_conn.backup(backup_sqlite_conn)
    finally:
        backup_sqlite_conn.close()
finally:
    raw_conn.close()
```

---

### CR-02: All `DateTime` columns silently strip timezone info on SQLite round-trip

**File:** `src/bensdorp1/db/schema.py:27,35,39,51,60,70,96,102,111`

**Issue:** Every `DateTime` column is defined without `timezone=True` (the default is `False`). SQLite stores datetime as text without timezone offset. On retrieval SQLAlchemy returns a naive `datetime` object (`tzinfo=None`) even when the inserted value was UTC-aware. Verified empirically:

```
Inserting: 2026-05-23 11:56:41.653561+00:00  tzinfo: UTC
Retrieved: 2026-05-23 11:56:41.653561         tzinfo: None
```

This means any future code that compares retrieved timestamps with `datetime.now(UTC)` will raise `TypeError: can't compare offset-naive and offset-aware datetimes`. All seven tables are affected. The `occurred_at` column in `audit_log` is particularly dangerous — `log_event()` inserts `datetime.now(UTC)` (aware), but reads will produce naive values. The `scan_date` unique constraint on `scans` could silently permit duplicates if insertion logic uses aware datetimes and comparison uses naive ones.

**Fix:** Use `DateTime(timezone=True)` on every timestamp column. For SQLite this stores an ISO-8601 string with offset; for future migration to PostgreSQL it maps to `TIMESTAMP WITH TIME ZONE`. Example for `audit_log`:

```python
Column("occurred_at", DateTime(timezone=True), nullable=False),
```

Apply this to: `config.updated_at`, `scans.scan_date`, `scans.created_at`, `positions.entry_date`, `positions.closed_at`, `audit_log.occurred_at`, `constituents_cache.fetched_at`, `price_daily.trade_date`.

---

### CR-03: `_build_engine` / `get_engine` never creates the parent directory; first run fails with cryptic error

**File:** `src/bensdorp1/db/engine.py:34-41,44-60`

**Issue:** `_build_engine` calls `create_engine(url)` where `url` points to `~/bensdorp1/data/bensdorp1.db`. The directory `~/bensdorp1/data/` does not exist on a fresh install. SQLAlchemy defers connecting until the first query, so `create_engine` succeeds but the first `engine.connect()` (inside `run_migrations` or any other operation) raises:

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
```

This is the first thing a new user will see. There is no `mkdir(parents=True, exist_ok=True)` anywhere in the engine creation path. (Confirmed with a live test — the directory must pre-exist for SQLite to open the file.) The `backup.py` module correctly does `backups_dir.mkdir(parents=True, exist_ok=True)`, showing the pattern is known.

**Fix:** In `_build_engine`, create the parent directory before building the URL:

```python
def _build_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    url = URL.create("sqlite+pysqlite", database=str(path))
    return create_engine(url)
```

---

## Warnings

### WR-01: Double dispose in `db_engine` fixture teardown

**File:** `tests/conftest.py:34-35`

**Issue:** At teardown, `_reset_engine_for_testing()` (line 34) is called with no arguments. Inside that function, since `_engine is engine` (set on line 29), `_engine.dispose()` is called. Then line 35 calls `engine.dispose()` again on the same object. `Engine.dispose()` is idempotent, so this does not crash, but it is misleading: the comment "CRITICAL on Windows: prevents [WinError 32] in tmp_path" implies line 35 is the primary dispose, when in fact `_reset_engine_for_testing()` already disposed it. If `_reset_engine_for_testing` is ever refactored to not call `dispose`, the double-dispose comment will mask the regression.

**Fix:** Remove the redundant `engine.dispose()` call, or restructure teardown to make the dispose explicit and the singleton reset separate:

```python
finally:
    engine_module._reset_engine_for_testing()
    # _reset_engine_for_testing() already called engine.dispose() above;
    # no second call needed.
```

Or restructure `_reset_engine_for_testing` to not dispose (just clear the reference) and always dispose explicitly at the call site.

---

### WR-02: `# noqa: UP017` suppresses a valid modernization rule; inconsistent with `audit.py`

**File:** `src/bensdorp1/db/backup.py:38`

**Issue:** Line 38 uses `timezone.utc` and suppresses the UP017 ruff rule (`datetime.timezone.utc` → `datetime.UTC`). Python 3.11 introduced `datetime.UTC` and the project requires `>=3.11`. `audit.py` already uses `from datetime import UTC, datetime` correctly. Suppressing UP017 in `backup.py` creates an inconsistency and hides a legitimate improvement. The `noqa` comment should be removed and the import updated.

**Fix:**
```python
# Change import:
from datetime import UTC, datetime

# Change line 38:
ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
```

---

### WR-03: `get_engine` singleton behavior is entirely untested

**File:** `tests/test_db_engine.py` (entire file)

**Issue:** `test_db_engine.py` contains four tests: `_build_engine`, `_resolve_db_path` (twice), and `run_migrations`. None of them call `get_engine()`. The most critical behavior of the module — that `get_engine()` caches and returns the same engine on repeated calls, that it ignores the `path` argument after the first call, and that it is thread-safe — has zero test coverage. The docstring even says "subsequent calls return the cached engine regardless of path," which is a subtle behavior that can cause hard-to-debug test pollution.

**Fix:** Add tests for the public API:

```python
def test_get_engine_returns_cached_singleton(tmp_path: Path) -> None:
    engine_module._reset_engine_for_testing()
    e1 = engine_module.get_engine(tmp_path / "a.db")
    e2 = engine_module.get_engine(tmp_path / "b.db")  # different path, ignored
    assert e1 is e2
    engine_module._reset_engine_for_testing()

def test_get_engine_returns_engine_instance(tmp_path: Path) -> None:
    engine_module._reset_engine_for_testing()
    e = engine_module.get_engine(tmp_path / "t.db")
    assert isinstance(e, Engine)
    engine_module._reset_engine_for_testing()
```

---

### WR-04: Backup timestamp has second-level precision; rapid calls silently overwrite previous backup

**File:** `src/bensdorp1/db/backup.py:38-39`

**Issue:** The timestamp format `%Y%m%dT%H%M%SZ` has one-second precision. If `create_backup` is called twice within the same wall-clock second (e.g., two buy confirmations in quick succession, or a test that runs fast), the second call opens the same `backup_path` via `sqlite3.connect()` — which opens, not creates — and overwrites the previous backup with a fresh `backup()` call. There is no check for path existence and no error is raised. One second of backup window is lost silently.

**Fix:** Add microsecond precision or a uniqueness check:

```python
ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
# Or: raise if backup_path already exists
if backup_path.exists():
    raise FileExistsError(f"Backup file already exists: {backup_path}")
```

---

### WR-05: `scan_candidates` has no unique constraint on `(scan_id, rank)` or `(scan_id, symbol)`

**File:** `src/bensdorp1/db/schema.py:78-88`

**Issue:** The `scan_candidates` table allows multiple rows with the same `rank` value within a single scan, and also allows the same `symbol` to appear multiple times in the same scan's candidate list. Both cases represent corrupted scan output. There is no `Index` or `UniqueConstraint` on `(scan_id, rank)` or `(scan_id, symbol)`. All other tables with similar cardinality constraints use DB-level enforcement (e.g., `ix_positions_open_symbol`, `ix_price_daily_symbol_date`).

**Fix:**
```python
Index(
    "ix_scan_candidates_scan_rank",
    scan_candidates.c.scan_id,
    scan_candidates.c.rank,
    unique=True,
)
Index(
    "ix_scan_candidates_scan_symbol",
    scan_candidates.c.scan_id,
    scan_candidates.c.symbol,
    unique=True,
)
```

---

### WR-06: Unnecessary local import in `run_migrations` obscures the real dependency graph

**File:** `src/bensdorp1/db/engine.py:68`

**Issue:** `run_migrations` uses a local import `from bensdorp1.db.schema import metadata` with the comment "avoids circular import risk." `schema.py` has zero imports from `bensdorp1.*` — it only imports from `sqlalchemy`. A top-level import of `metadata` in `engine.py` would create no circular dependency. The local import is non-standard, makes the dependency implicit, and will confuse tools like `mypy`, `ruff`, and any module graph analyzer that expects imports at the top level. The comment perpetuates a false belief about a risk that does not exist.

**Fix:** Move the import to the top of `engine.py`:

```python
from bensdorp1.db.schema import metadata
```

And remove the comment. Verify with `python -c "import bensdorp1.db.engine"` that no `ImportError` occurs.

---

## Info

### IN-01: `price_daily.volume` typed as `Integer` — consider `BigInteger` for correctness

**File:** `src/bensdorp1/db/schema.py:106`

**Issue:** `Integer` in SQLAlchemy maps to a signed 32-bit integer in the Python type system and in portable SQL DDL. Daily volume for S&P 500 stocks frequently exceeds 2^31-1 (2,147,483,647 shares): AAPL commonly trades 50M–500M shares per day, and some broad ETFs (SPY, QQQ) routinely exceed 100M. SQLite's native INTEGER type handles up to 8 bytes, so data is not lost at the SQLite level, but the mismatch between the declared column type and the actual domain will surface as mypy complaints when volume values from `yfinance` (which returns `int64`) are bound to this column.

**Fix:** Use `BigInteger` to accurately represent the domain:

```python
from sqlalchemy import BigInteger
# ...
Column("volume", BigInteger, nullable=True),
```

---

### IN-02: `test_db_backup.py` does not verify backup contains source data

**File:** `tests/test_db_backup.py` (entire file)

**Issue:** Five tests cover file existence, directory creation, name format, SQLite validity, and return type — but none insert data into the source database and verify the backup contains it. `test_backup_is_valid_sqlite` only runs `SELECT 1`, which succeeds even on an empty SQLite file. A regression where `sqlite_conn.backup(backup_sqlite_conn)` is skipped or called in the wrong direction would pass all current tests.

**Fix:** Add a data integrity test:

```python
def test_backup_contains_source_data(db_engine: Engine, tmp_path: Path) -> None:
    from sqlalchemy import insert, select
    from bensdorp1.db.schema import audit_log
    from bensdorp1.db.audit import AuditEventType, log_event

    log_event(db_engine, AuditEventType.SYSTEM_INITIALIZED)
    backups_dir = tmp_path / "backups"
    result = create_backup(db_engine, backups_dir)

    conn = sqlite3.connect(str(result))
    try:
        rows = conn.execute("SELECT event_type FROM audit_log").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "system_initialized"
    finally:
        conn.close()
```

---

### IN-03: `__init__.py` does not export `schema` table objects; callers must know internal layout

**File:** `src/bensdorp1/db/__init__.py`

**Issue:** The public `__all__` exports `AuditEventType`, `create_backup`, `get_engine`, `log_event`, and `run_migrations` — but none of the `Table` objects (`positions`, `scans`, `audit_log`, etc.). Commands and tests must import directly from `bensdorp1.db.schema`, bypassing the public surface. This is not a bug today, but it means the package boundary is leaky: any refactoring of `schema.py` (e.g., renaming a module) requires updating every caller, not just `__init__.py`. If the design intent is that commands compose SQL via the `Table` objects, those should be part of the public API.

**Fix:** Either explicitly re-export the `Table` objects used by commands:

```python
from bensdorp1.db.schema import audit_log, positions, scans  # add as needed
__all__ = [..., "audit_log", "positions", "scans"]
```

Or document in a module docstring that `bensdorp1.db.schema` is a semi-public module that callers import directly by convention.

---

_Reviewed: 2026-05-23T11:58:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
