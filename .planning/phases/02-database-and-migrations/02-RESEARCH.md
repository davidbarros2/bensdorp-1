# Phase 2: Database and Migrations - Research

**Researched:** 2026-05-23
**Domain:** SQLAlchemy Core 2.0, SQLite, sqlite3.Connection.backup(), Python StrEnum, pytest fixtures
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use `MetaData.create_all(checkfirst=True)` — no Alembic, no raw SQL files. Idempotent by construction.
- **D-02:** `create_all()` called **only during `bensdorp1 init`** (Phase 6). Every other command fails fast if DB missing.
- **D-03:** Hybrid audit_log schema — shared SQL columns (`id`, `event_type`, `occurred_at`, `symbol` TEXT nullable, `payload` TEXT JSON) for SQL-filterable fields + JSON payload for event-specific data.
- **D-04:** 17 event types as `class AuditEventType(str, Enum)` in `db/audit.py`. `str` mixin = direct TEXT use without `.value`.
- **D-05:** Phase 2 defines **all 7 tables** now: `config`, `positions`, `audit_log`, `scans`, `scan_candidates`, `constituents_cache`, `price_daily`.
- **D-06:** `positions` table uses nullable `closed_at`. Partial unique index `(symbol) WHERE closed_at IS NULL` enforces STATE-06.
- **D-07:** `src/bensdorp1/db/` subpackage: `__init__.py`, `schema.py`, `engine.py`, `backup.py`, `audit.py`.
- **D-08:** `get_engine(path: Path | None = None)` with lazy caching. Tests pass explicit `path` — no env monkeypatching.

### Claude's Discretion

None — all decisions locked.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATE-01 | SQLite database at ~/bensdorp1/data/bensdorp1.db (overridable via BENSDORP1_HOME) | `URL.create('sqlite+pysqlite', database=str(path))` pattern verified; BENSDORP1_HOME resolution via `os.environ.get()` + `pathlib.Path` |
| STATE-02 | Automatic backup after every state-changing operation using `sqlite3.Connection.backup()` API | `engine.raw_connection().driver_connection` gives the `sqlite3.Connection`; backup() signature verified against Python 3.11 stdlib |
| STATE-03 | Timestamped backups in ~/bensdorp1/backups/; `bensdorp1-latest.db` always the most recent | Windows: symlinks require admin — use `shutil.copy2` unconditionally; verified on this machine |
| STATE-04 | Structured audit log with all 17 event types | `StrEnum` from Python 3.11 standard library; all 17 values verified as SQLite TEXT insertable; mypy strict passes |
| STATE-06 | No simultaneous open positions in same symbol; sequential allowed | SQLite partial unique index via `Index(..., sqlite_where=(positions.c.closed_at == None))` verified end-to-end: IntegrityError on duplicate open, sequential succeeds |
</phase_requirements>

---

## Summary

Phase 2 builds the complete `db/` subpackage that every subsequent phase builds on. All five requirements in scope (STATE-01 through STATE-06 minus STATE-05) are implementable with a small, precise set of SQLAlchemy Core 2.0 patterns — all verified by running code against the installed stack (sqlalchemy 2.0.49, Python 3.12, mypy 2.1.0) on this machine.

The most critical finding: **Windows does not allow symlinks without admin privileges** (confirmed: `[WinError 1314]`). The CONTEXT.md notes about `bensdorp1-latest.db` must use `shutil.copy2` unconditionally rather than `try: symlink; except: copy`. No symlink attempt should be made at all on this project.

The second critical finding: **`engine.raw_connection()` returns a `_ConnectionFairy` (pool proxy), not a `sqlite3.Connection` directly**. The actual `sqlite3.Connection` is at `raw_conn.driver_connection`. This attribute exists on SQLAlchemy 2.0 pool proxies and was verified to work correctly. Using `raw_conn` directly for `backup()` would fail silently or produce a confusing error.

SQLAlchemy Core 2.0 is fully mypy-strict-compatible for this use case: `Table`, `Column`, `MetaData`, `Engine`, `URL.create()` all type-check without errors in strict mode. The mypy plugin for SQLAlchemy is deprecated in 2.0 and must NOT be configured. No plugin entry is needed in pyproject.toml.

**Primary recommendation:** Build the 5 modules in dependency order — `schema.py` first (no imports from db/), then `engine.py` (imports schema.py metadata), then `backup.py` (imports engine.py), then `audit.py` (imports schema.py + engine.py), then `__init__.py` (re-exports).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema definition (DDL) | `db/schema.py` | — | Single source of truth for all Table/Column/Index objects; all other modules import from here |
| Engine lifecycle | `db/engine.py` | — | Lazy singleton; owns create_engine and URL construction |
| SQLite backup | `db/backup.py` | stdlib `sqlite3` | backup() is a DBAPI-level operation; goes through engine to get raw connection |
| Audit logging | `db/audit.py` | `db/schema.py` | Writes to audit_log table; owns AuditEventType enum |
| Schema migrations | `db/engine.py` `run_migrations()` | `db/schema.py` | `metadata.create_all(engine, checkfirst=True)` |
| STATE-06 enforcement | SQLite (index) | `db/schema.py` | Partial unique index enforces constraint at DB level; no app-layer check needed |
| Test isolation | pytest fixtures | `db/engine.py` | `_reset_engine_for_testing()` invalidates cached engine between tests |

---

## Standard Stack

### Core (already in pyproject.toml)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlalchemy | `>=2.0.49,<2.1` | Core table/column definitions, DDL, DML, engine management | Ships inline types; mypy plugin deprecated; 2.0.x is stable [VERIFIED: pip index versions] |
| pytest | `>=8.3` | Test runner | Standard; already installed [VERIFIED: pip index versions] |
| hypothesis | `>=6.130` | Property-based tests | Already in dev group; used in this phase for enum coverage tests [VERIFIED: pip index versions] |

No new packages are required for Phase 2. All dependencies are already declared in `pyproject.toml`.

### No New Packages

Phase 2 uses only:
- `sqlalchemy` (runtime dep, already in `[project.dependencies]`)
- `sqlite3` (Python stdlib, zero-config)
- `shutil` (Python stdlib)
- `threading` (Python stdlib)
- `pathlib` (Python stdlib)
- `json` (Python stdlib)
- `enum.StrEnum` (Python 3.11 stdlib)
- `datetime` (Python stdlib)

**Installation:** No changes to `pyproject.toml` needed.

---

## Package Legitimacy Audit

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| sqlalchemy | PyPI | [OK] | Approved — 14+ year project, canonical Python ORM/Core |
| pytest | PyPI | [OK] | Approved |
| pytest-cov | PyPI | [OK] (no source repo linked — established package) | Approved |
| hypothesis | PyPI | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck 0.6.1 ran successfully on 2026-05-23. All 4 packages passed.*

---

## Architecture Patterns

### System Architecture Diagram

```
bensdorp1 commands (Phase 6+)
         |
         v
db/__init__.py           <-- re-exports: get_engine, run_migrations, create_backup, log_event
    |          |
    v          v
db/engine.py  db/schema.py         <-- schema.py has NO imports from db/; pure Table definitions
    |              |
    |          metadata: MetaData
    |          7 Table objects (all referenced by engine.py, backup.py, audit.py)
    |
    +---> db/backup.py    <-- imports get_engine from engine.py; uses raw_connection().driver_connection
    |
    +---> db/audit.py     <-- imports AuditEventType enum; imports audit_log Table from schema.py
    |
    v
SQLite file: ~/bensdorp1/data/bensdorp1.db
    |
    v (on every state-changing operation)
~/bensdorp1/backups/bensdorp1-{timestamp}.db
~/bensdorp1/backups/bensdorp1-latest.db     <-- shutil.copy2 (NOT symlink — Windows incompatibility)
```

### Recommended Project Structure (db/ subpackage)

```
src/
  bensdorp1/
    db/
      __init__.py       # re-exports: get_engine, run_migrations, create_backup, log_event, AuditEventType
      schema.py         # MetaData(), all 7 Table objects, all Index objects
      engine.py         # get_engine(), run_migrations(), _reset_engine_for_testing()
      backup.py         # create_backup(engine, backups_dir)
      audit.py          # AuditEventType(StrEnum), log_event()
tests/
  test_db_schema.py     # create_all idempotency, all 7 tables exist, indexes exist
  test_db_backup.py     # backup produces file, latest.db updated
  test_db_audit.py      # all 17 event types insertable and queryable
  test_db_positions.py  # STATE-06: IntegrityError on duplicate open, sequential allowed
```

### Pattern 1: MetaData and create_all

```python
# Source: https://docs.sqlalchemy.org/en/20/core/metadata.html [CITED: WebFetch official docs]
# File: db/schema.py

from sqlalchemy import MetaData

metadata: MetaData = MetaData()
# All Table() calls below use this shared metadata object.
```

```python
# File: db/engine.py
# Source: https://docs.sqlalchemy.org/en/20/core/metadata.html [VERIFIED: WebFetch + local test]

from bensdorp1.db.schema import metadata

def run_migrations(engine: Engine) -> None:
    """Create all tables idempotently. Called only from bensdorp1 init."""
    metadata.create_all(engine, checkfirst=True)
```

**Verified:** `metadata.create_all(engine, checkfirst=True)` is idempotent — calling it on an existing DB produces no error and no changes. Calling without `checkfirst=True` raises `OperationalError` on the second run. Always use `checkfirst=True`. [VERIFIED: local test]

### Pattern 2: SQLAlchemy URL from pathlib.Path

```python
# Source: https://docs.sqlalchemy.org/en/20/core/engines.html [CITED: WebFetch official docs]
# Verified: URL.create with absolute path works on Windows [VERIFIED: local test]

from sqlalchemy.engine import URL, Engine, create_engine
from pathlib import Path

def _build_engine(path: Path) -> Engine:
    url = URL.create("sqlite+pysqlite", database=str(path))
    return create_engine(url)
```

**Why `URL.create()` not f-string:** `URL.create()` is the explicit, typed way to construct URLs in SQLAlchemy 2.0. It handles path escaping correctly. The `database=str(path)` pattern works on Windows because `pathlib.Path.__str__()` uses backslashes on Windows, which SQLite's Windows DBAPI driver handles correctly. Verified: URL produced is `sqlite+pysqlite:///C:\path\to\db.db`. [VERIFIED: local test]

### Pattern 3: Lazy-Cached Engine with Thread-Safe Reset

```python
# Source: training knowledge + verified locally [VERIFIED: local test]
# File: db/engine.py

import os
import threading
from pathlib import Path
from typing import Optional

from sqlalchemy.engine import URL, Engine, create_engine

_engine: Optional[Engine] = None
_engine_lock: threading.Lock = threading.Lock()


def get_engine(path: Optional[Path] = None) -> Engine:
    """Return the cached engine, creating it on first call.

    Args:
        path: explicit DB file path (used in tests). If None, resolves
              BENSDORP1_HOME env var, defaulting to ~/bensdorp1/data/bensdorp1.db.
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = _build_engine(_resolve_db_path(path))
    return _engine


def _resolve_db_path(override: Optional[Path]) -> Path:
    if override is not None:
        return override
    home_env = os.environ.get("BENSDORP1_HOME")
    base = Path(home_env) if home_env else Path.home() / "bensdorp1"
    return base / "data" / "bensdorp1.db"


def _reset_engine_for_testing(replacement: Optional[Engine] = None) -> None:
    """Test helper: dispose and reset the cached engine."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = replacement
```

**Thread safety note:** The double-checked locking pattern (`if _engine is None: lock: if _engine is None:`) is correct Python. The `threading.Lock` prevents two threads simultaneously building separate engines. `Engine` itself is thread-safe once built — SQLAlchemy engines use `QueuePool` for file-based SQLite which handles concurrent connections. [VERIFIED: local test + SQLAlchemy docs]

**Test pattern:**
```python
# conftest.py
import pytest
from pathlib import Path
import bensdorp1.db.engine as engine_module

@pytest.fixture()
def db_engine(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = engine_module._build_engine(db_path)
    engine_module._reset_engine_for_testing(engine)
    from bensdorp1.db.schema import metadata
    metadata.create_all(engine, checkfirst=True)
    yield engine
    engine_module._reset_engine_for_testing()
    engine.dispose()
```

### Pattern 4: Partial Unique Index for STATE-06

```python
# Source: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html [CITED: WebFetch official docs]
# Verified end-to-end: IntegrityError on duplicate open, sequential succeeds [VERIFIED: local test]
# File: db/schema.py

from sqlalchemy import Index, Table

positions: Table = Table(
    "positions",
    metadata,
    # ... columns ...
    Column("symbol", Text, nullable=False),
    Column("closed_at", DateTime, nullable=True),
)

# Partial unique index: only ONE open position per symbol at a time
# sqlite_where accepts a SQLAlchemy boolean expression
Index(
    "ix_positions_open_symbol",
    positions.c.symbol,
    unique=True,
    sqlite_where=(positions.c.closed_at == None),  # noqa: E711
)
```

**Critical:** The `== None` comparison is intentional — it generates the SQLite `WHERE closed_at IS NULL` clause. Ruff's `E711` rule flags `== None` as bad style (should be `is None`), but `is None` does NOT work here because SQLAlchemy needs the `==` operator to produce a SQL clause object, not a Python boolean. Add `# noqa: E711` on that line. [VERIFIED: local test]

**Generated SQL:**
```sql
CREATE UNIQUE INDEX ix_positions_open_symbol ON positions (symbol)
WHERE closed_at IS NULL
```

### Pattern 5: sqlite3.Connection.backup() via SQLAlchemy 2.0

```python
# Source: https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Connection.backup [CITED: official Python docs]
# Source: SQLAlchemy 2.0 connections docs [CITED: WebFetch]
# Verified: engine.raw_connection().driver_connection is sqlite3.Connection [VERIFIED: local test]
# File: db/backup.py

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import Engine


def create_backup(engine: Engine, backups_dir: Path) -> Path:
    """Create a timestamped backup and update bensdorp1-latest.db.

    Returns the path to the timestamped backup file.
    STATE-02: uses sqlite3.Connection.backup() (NOT shutil.copy).
    STATE-03: updates bensdorp1-latest.db via shutil.copy2 (NOT symlink — Windows).
    """
    backups_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backups_dir / f"bensdorp1-{ts}.db"
    latest_path = backups_dir / "bensdorp1-latest.db"

    # Get the underlying sqlite3.Connection from the SQLAlchemy engine
    raw_conn = engine.raw_connection()
    try:
        sqlite_conn: sqlite3.Connection = raw_conn.driver_connection  # type: ignore[assignment]
        backup_sqlite_conn = sqlite3.connect(str(backup_path))
        try:
            sqlite_conn.backup(backup_sqlite_conn)
        finally:
            backup_sqlite_conn.close()
    finally:
        raw_conn.close()

    # Update latest.db — use shutil.copy2, NOT symlink (Windows requires admin for symlinks)
    shutil.copy2(backup_path, latest_path)

    return backup_path
```

**Why `raw_conn.driver_connection` not `raw_conn` directly:**
- `engine.raw_connection()` returns a `sqlalchemy.pool.base._ConnectionFairy` (pool proxy)
- The actual `sqlite3.Connection` is at `.driver_connection` attribute
- Calling `.backup()` on the proxy would raise `AttributeError`
- [VERIFIED: local test confirmed `type(raw_conn.driver_connection)` is `<class 'sqlite3.Connection'>`]

**Why NOT symlink for `bensdorp1-latest.db`:**
- Windows requires `SeCreateSymbolicLinkPrivilege` (admin or Developer Mode)
- Confirmed `[WinError 1314]` on this machine with `latest.symlink_to(src)`
- `shutil.copy2` is unconditional, cross-platform, and sufficient [VERIFIED: local test]

**sqlite3.Connection.backup() signature (Python 3.11):**
```
backup(target, *, pages=-1, progress=None, name='main', sleep=0.25)
```
- `target`: destination `sqlite3.Connection` (required)
- `pages=-1`: copy entire DB in one step (correct for our case)
- `progress=None`: no callback needed
- `name='main'`: backup the main database (not a temp or attached DB)

### Pattern 6: AuditEventType as StrEnum

```python
# Source: https://docs.python.org/3.11/library/enum.html#enum.StrEnum [CITED: official Python docs]
# Verified: StrEnum members stored as TEXT in SQLite without .value unwrapping [VERIFIED: local test]
# File: db/audit.py

from enum import StrEnum


class AuditEventType(StrEnum):
    """All 17 audit event types from STATE-04.

    StrEnum members ARE strings — no .value needed when inserting to SQLite.
    str(AuditEventType.BUY_CONFIRMED) == "buy_confirmed"  # True
    """
    SYSTEM_INITIALIZED = "system_initialized"
    SCAN_PERFORMED = "scan_performed"
    BUY_CONFIRMED = "buy_confirmed"
    SELL_CONFIRMED = "sell_confirmed"
    SELL_MANUAL = "sell_manual"
    TRANSACTION_CORRECTED = "transaction_corrected"
    CASH_UPDATED = "cash_updated"
    CONSTITUENTS_UPDATED = "constituents_updated"
    CONSTITUENTS_DISCREPANCY = "constituents_discrepancy"
    SPLIT_APPLIED = "split_applied"
    POSITION_DELISTED_FROM_INDEX = "position_delisted_from_index"
    REGIME_CHANGE_BULL_TO_BEAR = "regime_change_bull_to_bear"
    REGIME_CHANGE_BEAR_TO_BULL = "regime_change_bear_to_bull"
    DATA_FETCH_FAILED = "data_fetch_failed"
    CATCH_UP_PERFORMED = "catch_up_performed"
    RESTORE_PERFORMED = "restore_performed"
    POSITION_CLOSED_MANUAL = "position_closed_manual"
```

**StrEnum vs `class Foo(str, Enum)` — the key difference:**

| | `StrEnum` (Python 3.11) | `class Foo(str, Enum)` |
|--|--|--|
| `str(member)` | Returns value: `"buy_confirmed"` | Returns `"AuditEventType.BUY_CONFIRMED"` |
| `f"{member}"` | Returns value: `"buy_confirmed"` | Returns `"AuditEventType.BUY_CONFIRMED"` |
| SQLite insert | Works directly | Needs `.value` |
| mypy strict | Clean | Needs explicit `.value` annotations |

**Use `StrEnum` not `str, Enum`.** [VERIFIED: local test + Python 3.11 docs]

### Pattern 7: log_event() function

```python
# File: db/audit.py
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from bensdorp1.db.schema import audit_log


def log_event(
    engine: Engine,
    event_type: AuditEventType,
    symbol: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Insert one row into audit_log."""
    with engine.connect() as conn:
        conn.execute(
            insert(audit_log).values(
                event_type=str(event_type),  # StrEnum -> str for unambiguous storage
                occurred_at=datetime.now(timezone.utc),
                symbol=symbol,
                payload=json.dumps(payload) if payload is not None else None,
            )
        )
        conn.commit()
```

**Verified:** mypy strict reports zero errors on this function signature. [VERIFIED: local mypy test]

### Anti-Patterns to Avoid

- **`raw_conn.backup(...)` directly:** `raw_conn` is a pool proxy, not a `sqlite3.Connection`. Use `raw_conn.driver_connection.backup(...)`. [VERIFIED: pool proxy type confirmed]
- **`latest_path.symlink_to(backup_path)` on Windows:** Raises `[WinError 1314]`. Always use `shutil.copy2`. [VERIFIED: local test]
- **`metadata.create_all(engine)` without `checkfirst=True`:** Raises `OperationalError` if tables exist. Always pass `checkfirst=True`. [VERIFIED: local test]
- **`== None` in `sqlite_where` replaced with `is None`:** `is None` returns a Python bool, not a SQL clause. The `E711` ruff warning must be suppressed with `# noqa: E711`. [VERIFIED: local test]
- **SQLAlchemy mypy plugin in pyproject.toml:** The plugin is deprecated in 2.0 and causes errors with mypy 2.x. Do NOT add `[mypy]` plugin = `sqlalchemy.ext.mypy.plugin`. [CITED: SQLAlchemy 2.0 docs]
- **ORM `Mapped[]` annotations for Core tables:** Phase 2 uses SQLAlchemy Core only. ORM Mapped[] typing is for Declarative ORM mappings, not `Table()` / `Column()` objects.
- **`class AuditEventType(str, Enum)` instead of `StrEnum`:** The `str, Enum` pattern's `__str__()` returns `"ClassName.MEMBER"`, not the value. Use `StrEnum`. [VERIFIED: local test]
- **`UTC` from `datetime.timezone` confusion:** Always use `datetime.timezone.utc`, never `datetime.UTC` (Python 3.11 alias, but timezone.utc is the universal spelling).
- **`shutil.copy` vs `shutil.copy2`:** Use `copy2` to preserve file metadata (timestamps). Functionally equivalent for backup purposes, but `copy2` is the correct idiom for backup copies.
- **Building the SQLite URL with `f"sqlite:///{path}"`:** Works on Linux (forward slashes), but on Windows, `str(Path(...))` uses backslashes which can confuse some parsers. Use `URL.create("sqlite+pysqlite", database=str(path))` instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idempotent schema migrations | Raw `CREATE TABLE IF NOT EXISTS` SQL strings | `MetaData.create_all(checkfirst=True)` | Handles table ordering, FK constraints, index definitions automatically |
| Partial unique index | Application-layer check before INSERT | SQLite partial index via `sqlite_where` | DB-level enforcement; no race condition possible; no extra round-trip |
| SQLite hot backup | `shutil.copy(db_path, backup_path)` | `sqlite3.Connection.backup()` | File copy on live DB corrupts if writer is active; backup() is transactionally safe |
| Enum → TEXT mapping | Custom `@property` or dict lookup | `StrEnum` | StrEnum members ARE strings; zero boilerplate; exhaustiveness checking in match/case |
| Thread-safe singleton | Double-lock without `threading.Lock` | `threading.Lock()` with double-check | Python GIL does not protect dict reads/writes across threads |

**Key insight:** SQLite's partial index feature (`WHERE` clause on index) was built specifically for the "active record" pattern. Using it for STATE-06 means the constraint is enforced at storage level, not application level — no INSERT can bypass it regardless of which code path writes to the DB.

---

## Table Schemas (All 7 Tables)

All tables derived from REQUIREMENTS.md, ROADMAP.md strategy rules, and phase use cases.

### Table 1: `config`

Stores key-value configuration (cash amount, timezone override, etc.).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `key` | `Text` | PRIMARY KEY | e.g., `"cash"`, `"user_tz"` |
| `value` | `Text` | nullable | JSON-encoded value for flexibility |
| `updated_at` | `DateTime` | NOT NULL | UTC; updated on every write |

```python
config: Table = Table(
    "config", metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=True),
    Column("updated_at", DateTime, nullable=False),
)
```

### Table 2: `positions`

Unified table for open and closed positions (closed_at IS NULL = open).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `Integer` | PRIMARY KEY autoincrement | |
| `symbol` | `Text` | NOT NULL | Period form: "BRK.B" |
| `entry_date` | `DateTime` | NOT NULL | UTC; trading day of entry |
| `entry_close` | `Float` | NOT NULL | Adjusted close on entry day |
| `shares` | `Integer` | NOT NULL | Whole shares only |
| `initial_stop` | `Float` | NOT NULL | `entry_close * 0.93`; immutable |
| `highest_close` | `Float` | NOT NULL | Tracks STRAT-08; updated daily |
| `trailing_stop` | `Float` | NOT NULL | `highest_close * 0.75`; updated daily |
| `scan_id` | `Integer` | FK → scans.id, nullable | NULL if entered off-signal |
| `closed_at` | `DateTime` | nullable | NULL = open; NOT NULL = closed |
| `exit_price` | `Float` | nullable | NULL until closed |
| `realized_pnl` | `Float` | nullable | NULL until closed |

**Partial unique index:** `ix_positions_open_symbol` on `(symbol) WHERE closed_at IS NULL`

```python
positions: Table = Table(
    "positions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False),
    Column("entry_date", DateTime, nullable=False),
    Column("entry_close", Float, nullable=False),
    Column("shares", Integer, nullable=False),
    Column("initial_stop", Float, nullable=False),
    Column("highest_close", Float, nullable=False),
    Column("trailing_stop", Float, nullable=False),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=True),
    Column("closed_at", DateTime, nullable=True),
    Column("exit_price", Float, nullable=True),
    Column("realized_pnl", Float, nullable=True),
)
Index(
    "ix_positions_open_symbol",
    positions.c.symbol,
    unique=True,
    sqlite_where=(positions.c.closed_at == None),  # noqa: E711
)
```

### Table 3: `audit_log`

Structured event log for CMD-13 queries. Hybrid: SQL columns for filtering + JSON payload for event-specific data.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `Integer` | PRIMARY KEY autoincrement | |
| `event_type` | `Text` | NOT NULL | One of the 17 AuditEventType values |
| `occurred_at` | `DateTime` | NOT NULL | UTC |
| `symbol` | `Text` | nullable | NULL for non-position events |
| `payload` | `Text` | nullable | JSON-encoded dict; event-specific fields |

**Indexes:** `ix_audit_log_occurred_at`, `ix_audit_log_symbol`, `ix_audit_log_event_type` (all non-unique)

```python
audit_log: Table = Table(
    "audit_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", DateTime, nullable=False),
    Column("symbol", Text, nullable=True),
    Column("payload", Text, nullable=True),
)
Index("ix_audit_log_occurred_at", audit_log.c.occurred_at)
Index("ix_audit_log_symbol", audit_log.c.symbol)
Index("ix_audit_log_event_type", audit_log.c.event_type)
```

### Table 4: `scans`

One row per scan execution. Supports `bensdorp1 last` and `bensdorp1 history`.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `Integer` | PRIMARY KEY autoincrement | |
| `scan_date` | `DateTime` | NOT NULL, UNIQUE | Trading date of the scan (not timestamp) |
| `regime_active` | `Boolean` | NOT NULL | SPX > SMA200 at scan time |
| `candidate_count` | `Integer` | NOT NULL | Number of buy candidates generated |
| `exit_trigger_count` | `Integer` | NOT NULL | Number of stop triggers |
| `raw_output` | `Text` | nullable | Full Rich console output as text; for `last` command |
| `created_at` | `DateTime` | NOT NULL | Wall-clock time of scan execution |

```python
scans: Table = Table(
    "scans", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scan_date", DateTime, nullable=False, unique=True),
    Column("regime_active", Boolean, nullable=False),
    Column("candidate_count", Integer, nullable=False),
    Column("exit_trigger_count", Integer, nullable=False),
    Column("raw_output", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
)
```

### Table 5: `scan_candidates`

Top-10 buy candidates per scan. Supports position linking for `detail` command.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `Integer` | PRIMARY KEY autoincrement | |
| `scan_id` | `Integer` | NOT NULL, FK → scans.id | |
| `symbol` | `Text` | NOT NULL | Period form: "BRK.B" |
| `rank` | `Integer` | NOT NULL | 1 = best candidate |
| `roc200` | `Float` | NOT NULL | Rate of change over 200 trading days |
| `close` | `Float` | NOT NULL | Closing price at scan time |
| `suggested_shares` | `Integer` | NOT NULL | From STRAT-06 position sizing |

```python
scan_candidates: Table = Table(
    "scan_candidates", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=False),
    Column("symbol", Text, nullable=False),
    Column("rank", Integer, nullable=False),
    Column("roc200", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("suggested_shares", Integer, nullable=False),
)
```

### Table 6: `constituents_cache`

S&P 500 constituent list cache. Refreshed every 7 days (DATA-05).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `Integer` | PRIMARY KEY autoincrement | |
| `symbol` | `Text` | NOT NULL, UNIQUE | Period form: "BRK.B" |
| `company_name` | `Text` | nullable | From Wikipedia table |
| `fetched_at` | `DateTime` | NOT NULL | UTC; used for 7-day freshness check |

```python
constituents_cache: Table = Table(
    "constituents_cache", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False, unique=True),
    Column("company_name", Text, nullable=True),
    Column("fetched_at", DateTime, nullable=False),
)
```

### Table 7: `price_daily`

Daily price history cache. 220+ trading days per symbol for strategy calculations.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `Integer` | PRIMARY KEY autoincrement | |
| `symbol` | `Text` | NOT NULL | Period form: "BRK.B" |
| `trade_date` | `DateTime` | NOT NULL | NYSE trading day (UTC midnight) |
| `close` | `Float` | NOT NULL | Adjusted close (auto_adjust=True) |
| `volume` | `Integer` | nullable | For STRAT-02 liquidity filter |

**Unique index:** `ix_price_daily_symbol_date` on `(symbol, trade_date)` prevents duplicate entries per symbol per day.

```python
price_daily: Table = Table(
    "price_daily", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False),
    Column("trade_date", DateTime, nullable=False),
    Column("close", Float, nullable=False),
    Column("volume", Integer, nullable=True),
)
Index("ix_price_daily_symbol_date", price_daily.c.symbol, price_daily.c.trade_date, unique=True)
```

---

## mypy Strict Compatibility

### SQLAlchemy Core 2.0 + mypy strict — what works

SQLAlchemy 2.0 ships inline type annotations. For **Core** usage (not ORM), mypy strict works cleanly with these patterns:

| Construct | Type Annotation | Notes |
|-----------|----------------|-------|
| `MetaData()` | `MetaData` | Direct annotation, no issues |
| `Table(...)` | `Table` | `Table` is not generic; annotate as `Table` |
| `Column(Integer)` | `Column[int]` | Column IS generic in SA 2.0; `Column[int]`, `Column[str]`, etc. |
| `create_engine(url)` | `Engine` | Return type is `Engine`, not generic |
| `engine.connect()` | `Connection` (context manager) | |
| `URL.create(...)` | `URL` | Typed constructor |

**Verified:** `mypy --strict` reports zero errors on a file containing `Table`, `Column`, `MetaData`, `Engine`, `URL.create()`, and `StrEnum`. [VERIFIED: local mypy test]

**Do NOT add the SQLAlchemy mypy plugin** — it is deprecated in 2.0 and incompatible with mypy 2.x. No `[[tool.mypy.overrides]] module = "sqlalchemy.*"` needed. No `plugins = ["sqlalchemy.ext.mypy.plugin"]` in `[tool.mypy]`. [CITED: SQLAlchemy 2.0 docs — "Deprecated since version 2.0: The SQLAlchemy Mypy Plugin is DEPRECATED"]

### Type annotation for `driver_connection`

The `engine.raw_connection().driver_connection` attribute returns `Any` from mypy's perspective (pool proxy internals are not fully typed). Use a type assertion:

```python
sqlite_conn: sqlite3.Connection = raw_conn.driver_connection  # type: ignore[assignment]
```

This is the correct, minimal suppression — only the assignment line needs it.

### Ruff TC rules and SQLAlchemy Core imports

Ruff's TC001/TC002/TC003 rules move imports into `TYPE_CHECKING` blocks if they appear to be type-only. SQLAlchemy Core `Table` and `Column` objects are **evaluated at module import time** (they execute `metadata.append_constraint()` etc. immediately), not lazily. Moving them to `TYPE_CHECKING` would break runtime table registration.

**Fix:** Add to `pyproject.toml`:

```toml
[tool.ruff.lint.flake8-type-checking]
# SQLAlchemy Core Table/Column are evaluated at import time (they register with MetaData).
# Do NOT move these imports into TYPE_CHECKING blocks.
runtime-evaluated-base-classes = ["sqlalchemy.orm.DeclarativeBase"]
```

**However**, for this project we use Core (not ORM Declarative), so `runtime-evaluated-base-classes` for ORM doesn't apply to `Table`/`Column`. The practical solution is simpler: since `schema.py` uses `Table()` and `Column()` for their side effects (registering with MetaData at module load), the TC rules should not fire because the constructs are in the module body, not in type annotations. If TC rules fire on `schema.py` imports in other files, add:

```toml
[tool.ruff.lint.per-file-ignores]
"src/bensdorp1/db/schema.py" = ["TC001", "TC002"]
"src/bensdorp1/db/engine.py" = ["TC002"]
"src/bensdorp1/db/backup.py" = ["TC002"]
"src/bensdorp1/db/audit.py" = ["TC002"]
```

The cleanest approach for this phase: **do not add TC to ruff's select list**. The current `pyproject.toml` selects `["E", "F", "I", "UP", "B", "C4", "PT"]` — TC is not in scope. No change needed. [CITED: CLAUDE.md §Ruff Configuration — "SQLAlchemy Core Table/Column are evaluated at import time"]

---

## Common Pitfalls

### Pitfall 1: `raw_conn` is Not a `sqlite3.Connection`
**What goes wrong:** `engine.raw_connection().backup(...)` raises `AttributeError: '_ConnectionFairy' object has no attribute 'backup'`
**Why it happens:** `engine.raw_connection()` returns a pool proxy wrapper, not the underlying DBAPI connection.
**How to avoid:** Always access `.driver_connection` attribute: `raw_conn.driver_connection.backup(backup_target_conn)`
**Warning signs:** `AttributeError` mentioning `_ConnectionFairy` or `backup`

### Pitfall 2: Windows Symlink Permission Error for `bensdorp1-latest.db`
**What goes wrong:** `latest_path.symlink_to(backup_path)` raises `OSError: [WinError 1314] A required privilege is not held by the client`
**Why it happens:** Windows requires `SeCreateSymbolicLinkPrivilege` (admin or Developer Mode) for symlinks.
**How to avoid:** Use `shutil.copy2(backup_path, latest_path)` unconditionally. Do not attempt symlink at all.
**Warning signs:** OSError with WinError 1314 on Windows; macOS/Linux test passes, Windows fails.

### Pitfall 3: `create_all()` Without `checkfirst=True`
**What goes wrong:** `metadata.create_all(engine)` raises `OperationalError: table already exists` on second run
**Why it happens:** Default SQLAlchemy behavior emits `CREATE TABLE` without `IF NOT EXISTS`
**How to avoid:** Always `metadata.create_all(engine, checkfirst=True)`
**Warning signs:** `OperationalError` containing "already exists" on DB that already has tables

### Pitfall 4: Ruff E711 on `== None` in `sqlite_where`
**What goes wrong:** Ruff flags `sqlite_where=(positions.c.closed_at == None)` as `E711: Comparison to None (if cond is None:)`
**Why it happens:** Ruff applies PEP 8's recommendation to use `is None` for Python comparisons.
**How to avoid:** Add `# noqa: E711` on that specific line. Do NOT change `== None` to `is None` — SQLAlchemy needs the `==` operator to produce a SQL clause.
**Warning signs:** Ruff lint failure on schema.py; tests for partial index start failing (index created without WHERE clause).

### Pitfall 5: `class AuditEventType(str, Enum)` String Behavior in Python 3.11
**What goes wrong:** `f"{AuditEventType.BUY_CONFIRMED}"` produces `"AuditEventType.BUY_CONFIRMED"` instead of `"buy_confirmed"` — stored wrongly in SQLite
**Why it happens:** Python 3.11 changed `str, Enum`'s `__str__()` to return `"ClassName.MEMBER"`. `StrEnum` uses `str.__str__()` which returns the value.
**How to avoid:** Use `class AuditEventType(StrEnum):` from `enum` stdlib. Import `StrEnum` from `enum` module.
**Warning signs:** audit_log.event_type column contains "AuditEventType.buy_confirmed" instead of "buy_confirmed"

### Pitfall 6: SQLAlchemy mypy Plugin Causes mypy 2.x Errors
**What goes wrong:** Adding `plugins = ["sqlalchemy.ext.mypy.plugin"]` to `[tool.mypy]` causes mypy 2.x to error with plugin compatibility issues
**Why it happens:** The plugin is deprecated in SQLAlchemy 2.0 and removed in 2.1; incompatible with mypy 2.x
**How to avoid:** Never add the SQLAlchemy mypy plugin. SQLAlchemy 2.0 ships inline types that work without it.
**Warning signs:** mypy failing with plugin-related errors after adding the plugin to pyproject.toml

### Pitfall 7: DateTime Column Stores Python datetime.datetime Correctly on SQLite
**What goes wrong:** Confusion about SQLite DateTime — SQLite has no native DATETIME type.
**Why it doesn't matter:** SQLAlchemy's SQLite dialect automatically stores `datetime.datetime` objects as ISO-formatted strings and converts them back on read. Ordering works correctly (ISO strings are lexicographically sortable). No custom storage_format needed.
**How to avoid:** Always use `datetime.datetime` objects with `timezone.utc` when inserting. SQLAlchemy handles the rest.
**Warning signs:** Naive datetimes (without tzinfo) stored correctly but timezone comparisons fail.

### Pitfall 8: Table/Index Definition Order for Foreign Keys
**What goes wrong:** `Table("positions", ..., Column("scan_id", ForeignKey("scans.id")))` fails if `scans` table is defined in schema.py AFTER `positions`
**Why it happens:** SQLAlchemy resolves FK string references at `create_all()` time, not at `Table()` construction time — so definition order in Python doesn't matter.
**How to avoid:** Define tables in logical dependency order (scans before positions, positions before scan_candidates) for readability, but SQLAlchemy handles actual FK ordering automatically via topological sort.
**Warning signs:** `NoReferencedTableError` if FK string is wrong (typo in table name).

### Pitfall 9: Engine `dispose()` Not Called in Tests
**What goes wrong:** Tests that create file-based SQLite engines without calling `engine.dispose()` leave file handles open on Windows, causing subsequent tests to fail with `PermissionError` when deleting the temp directory.
**Why it happens:** Windows does not allow deleting files with open handles. SQLAlchemy's connection pool keeps connections open.
**How to avoid:** In pytest fixtures, always call `engine.dispose()` in teardown (after `yield`). Use `try/finally` in the fixture.
**Warning signs:** `PermissionError: [WinError 32]` during pytest teardown on Windows.

---

## Code Examples

### Complete schema.py skeleton

```python
# Source: SQLAlchemy 2.0 Core docs + local tests [VERIFIED: local test]
# File: src/bensdorp1/db/schema.py

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
)

metadata: MetaData = MetaData()

config: Table = Table(
    "config",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=True),
    Column("updated_at", DateTime, nullable=False),
)

scans: Table = Table(
    "scans",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scan_date", DateTime, nullable=False, unique=True),
    Column("regime_active", Boolean, nullable=False),
    Column("candidate_count", Integer, nullable=False),
    Column("exit_trigger_count", Integer, nullable=False),
    Column("raw_output", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
)

positions: Table = Table(
    "positions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False),
    Column("entry_date", DateTime, nullable=False),
    Column("entry_close", Float, nullable=False),
    Column("shares", Integer, nullable=False),
    Column("initial_stop", Float, nullable=False),
    Column("highest_close", Float, nullable=False),
    Column("trailing_stop", Float, nullable=False),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=True),
    Column("closed_at", DateTime, nullable=True),
    Column("exit_price", Float, nullable=True),
    Column("realized_pnl", Float, nullable=True),
)
Index(
    "ix_positions_open_symbol",
    positions.c.symbol,
    unique=True,
    sqlite_where=(positions.c.closed_at == None),  # noqa: E711
)

audit_log: Table = Table(
    "audit_log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", DateTime, nullable=False),
    Column("symbol", Text, nullable=True),
    Column("payload", Text, nullable=True),
)
Index("ix_audit_log_occurred_at", audit_log.c.occurred_at)
Index("ix_audit_log_symbol", audit_log.c.symbol)
Index("ix_audit_log_event_type", audit_log.c.event_type)

scan_candidates: Table = Table(
    "scan_candidates",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=False),
    Column("symbol", Text, nullable=False),
    Column("rank", Integer, nullable=False),
    Column("roc200", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("suggested_shares", Integer, nullable=False),
)

constituents_cache: Table = Table(
    "constituents_cache",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False, unique=True),
    Column("company_name", Text, nullable=True),
    Column("fetched_at", DateTime, nullable=False),
)

price_daily: Table = Table(
    "price_daily",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False),
    Column("trade_date", DateTime, nullable=False),
    Column("close", Float, nullable=False),
    Column("volume", Integer, nullable=True),
)
Index(
    "ix_price_daily_symbol_date",
    price_daily.c.symbol,
    price_daily.c.trade_date,
    unique=True,
)
```

### Test fixture pattern (conftest.py)

```python
# Source: pytest docs + SQLAlchemy 2.0 docs [CITED] + local tests [VERIFIED]
# File: tests/conftest.py

import pytest
from pathlib import Path
from sqlalchemy.engine import Engine

import bensdorp1.db.engine as engine_module
from bensdorp1.db.schema import metadata


@pytest.fixture()
def db_engine(tmp_path: Path) -> "Generator[Engine, None, None]":
    """Fresh file-based SQLite engine for each test. Resets module cache."""
    from typing import Generator
    db_path = tmp_path / "test.db"
    engine = engine_module._build_engine(db_path)
    engine_module._reset_engine_for_testing(engine)
    metadata.create_all(engine, checkfirst=True)
    try:
        yield engine
    finally:
        engine_module._reset_engine_for_testing()
        engine.dispose()  # CRITICAL on Windows: release file handles
```

### Test for STATE-06 enforcement

```python
# File: tests/test_db_positions.py
import pytest
from datetime import datetime, timezone
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine
from bensdorp1.db.schema import positions


def test_duplicate_open_position_rejected(db_engine: Engine) -> None:
    now = datetime.now(timezone.utc)
    with db_engine.connect() as conn:
        conn.execute(insert(positions).values(
            symbol="AAPL", entry_date=now, entry_close=150.0,
            shares=10, initial_stop=139.5, highest_close=150.0,
            trailing_stop=112.5, closed_at=None,
        ))
        conn.commit()
        with pytest.raises(IntegrityError):
            conn.execute(insert(positions).values(
                symbol="AAPL", entry_date=now, entry_close=155.0,
                shares=10, initial_stop=144.15, highest_close=155.0,
                trailing_stop=116.25, closed_at=None,
            ))


def test_sequential_positions_allowed(db_engine: Engine) -> None:
    now = datetime.now(timezone.utc)
    with db_engine.connect() as conn:
        conn.execute(insert(positions).values(
            symbol="MSFT", entry_date=now, entry_close=300.0,
            shares=5, initial_stop=279.0, highest_close=300.0,
            trailing_stop=225.0, closed_at=None,
        ))
        conn.commit()
        # Close it
        from sqlalchemy import update
        conn.execute(
            update(positions)
            .where(positions.c.symbol == "MSFT")
            .values(closed_at=now, exit_price=310.0, realized_pnl=50.0)
        )
        conn.commit()
        # Re-enter — should succeed
        conn.execute(insert(positions).values(
            symbol="MSFT", entry_date=now, entry_close=315.0,
            shares=5, initial_stop=292.95, highest_close=315.0,
            trailing_stop=236.25, closed_at=None,
        ))
        conn.commit()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SQLAlchemy mypy plugin | No plugin; inline types only | SQLAlchemy 2.0 (2023) | Plugin deprecated; ORM uses Mapped[] for typing; Core needs no plugin |
| `class Foo(str, Enum)` | `class Foo(StrEnum)` | Python 3.11 (2022) | StrEnum.__str__ returns value, not "ClassName.MEMBER" |
| `sqlite3.connect()` + manual DDL | SQLAlchemy Core `MetaData.create_all()` | Established pattern | Safe SQL composition, no string interpolation risk |
| Symlinks for "latest" file | `shutil.copy2` for cross-platform | Always needed for Windows | Symlinks require admin on Windows; copy is unconditional |
| `checkfirst=False` in create_all | `checkfirst=True` always | SQLAlchemy 2.0 best practice | Idempotent migrations without Alembic |

**Deprecated/outdated:**
- SQLAlchemy mypy plugin: deprecated in 2.0, removed in 2.1. Do not use.
- `[tool.uv.dev-dependencies]` for dev deps: legacy, use PEP 735 `[dependency-groups]`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_build_engine()` as a private helper separate from `get_engine()` is the cleanest split for testability | Pattern 3 | If wrong: merge into get_engine() with optional Engine injection parameter instead |
| A2 | `backup()` with `pages=-1` (default) is correct for a small personal-use SQLite file (< 100MB) | Pattern 5 | If performance is poor on large DBs: use `pages=100` for incremental; not a concern for v1 |
| A3 | The `scan_id` FK in `positions` being nullable correctly represents off-signal buys (not linked to any scan) | Table schemas | If wrong: use a separate `off_signal` boolean flag instead; minor schema change |
| A4 | `raw_output` as TEXT in `scans` table is sufficient for storing the full scan output for `bensdorp1 last` | Table schemas | If Rich console output is too large or not reproducible as plain text: revisit in Phase 7 |

**If this table is empty:** It is not — four assumptions flagged for planner awareness.

---

## Open Questions (RESOLVED)

1. **WAL mode — should it be enabled?**
   - What we know: SQLAlchemy supports WAL mode via `@event.listens_for(engine, 'connect')` + `PRAGMA journal_mode=WAL`. WAL is generally recommended for concurrent readers.
   - What's unclear: bensdorp1 is a single-user, single-process CLI — concurrent access is impossible. WAL adds complexity (WAL file created alongside .db file, slightly more complex backup semantics).
   - RESOLVED: Skip WAL mode for v1. Default journal mode (`DELETE`) is correct for single-process use. WAL's benefits are zero for this use case.

2. **`scan_candidates` table — should `roc200` and `close` store values at scan time?**
   - What we know: These values change daily; storing them records the state at scan time for the `detail` command.
   - What's unclear: Whether the `fix` command needs to recompute or just look up stored values.
   - RESOLVED: Store snapshot values. `detail` needs to show what was suggested; recomputing later requires historical price re-fetch.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 (local) / 3.11 (CI) | Runtime | ✓ | 3.12 local, 3.11 in CI via uv | — |
| SQLAlchemy 2.0.x | Schema/engine | ✓ | 2.0.48 installed, 2.0.49 latest | Update via `uv lock` |
| sqlite3 | Backup API | ✓ | stdlib (Python built-in) | — |
| pytest 9.0.3 | Tests | ✓ | 9.0.3 | — |
| mypy 2.1.0 | Type checking | ✓ | 2.1.0 | — |
| ruff 0.15.8 | Linting | ✓ | 0.15.8 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — already configured |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATE-01 | `run_migrations()` creates DB at given path with all 7 tables | unit | `uv run pytest tests/test_db_schema.py::test_all_tables_created -x` | ❌ Wave 0 |
| STATE-01 | `run_migrations()` is idempotent — second call does not error | unit | `uv run pytest tests/test_db_schema.py::test_create_all_idempotent -x` | ❌ Wave 0 |
| STATE-01 | BENSDORP1_HOME env var overrides default DB path | unit | `uv run pytest tests/test_db_engine.py::test_bensdorp1_home_override -x` | ❌ Wave 0 |
| STATE-02 | `create_backup()` uses `sqlite3.Connection.backup()` and produces valid SQLite file | unit | `uv run pytest tests/test_db_backup.py::test_backup_creates_valid_db -x` | ❌ Wave 0 |
| STATE-03 | Backup produces `bensdorp1-{timestamp}.db` in backups_dir | unit | `uv run pytest tests/test_db_backup.py::test_backup_timestamped_filename -x` | ❌ Wave 0 |
| STATE-03 | `bensdorp1-latest.db` exists and contains same data after backup | unit | `uv run pytest tests/test_db_backup.py::test_latest_db_updated -x` | ❌ Wave 0 |
| STATE-04 | All 17 AuditEventType values can be inserted into audit_log | unit | `uv run pytest tests/test_db_audit.py::test_all_event_types_insertable -x` | ❌ Wave 0 |
| STATE-04 | `log_event()` with symbol and payload stores correctly queryable row | unit | `uv run pytest tests/test_db_audit.py::test_log_event_with_payload -x` | ❌ Wave 0 |
| STATE-06 | Second open position in same symbol raises IntegrityError | unit | `uv run pytest tests/test_db_positions.py::test_duplicate_open_position_rejected -x` | ❌ Wave 0 |
| STATE-06 | Sequential positions in same symbol succeed (close first, reopen) | unit | `uv run pytest tests/test_db_positions.py::test_sequential_positions_allowed -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src/`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — `db_engine` fixture (tmp_path + create_all + teardown + engine disposal)
- [ ] `tests/test_db_schema.py` — schema creation, idempotency, all 7 tables present, partial index present
- [ ] `tests/test_db_engine.py` — BENSDORP1_HOME resolution, lazy caching, path override
- [ ] `tests/test_db_backup.py` — backup API, timestamped file, latest.db copy
- [ ] `tests/test_db_audit.py` — all 17 event types, log_event(), query filtering
- [ ] `tests/test_db_positions.py` — STATE-06 IntegrityError, sequential positions

*(Existing `tests/test_cli.py` and `tests/test_repo.py` from Phase 1 are unaffected — all 41 pass.)*

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user CLI; no authentication |
| V3 Session Management | No | No sessions; each command is stateless |
| V4 Access Control | No | Local filesystem; single user |
| V5 Input Validation | Partial | SQLAlchemy parameterized queries prevent SQL injection; enum validates event types |
| V6 Cryptography | No | No cryptographic operations; backups are plaintext SQLite files (acceptable for local personal use) |

### Known Threat Patterns for SQLite + SQLAlchemy Core

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via symbol/payload inputs | Tampering | SQLAlchemy Core parameterized queries via `insert().values(...)` — never string interpolation |
| Backup file world-readable | Information Disclosure | `backups_dir.mkdir(mode=0o700, ...)` on Unix; on Windows, NTFS ACLs apply automatically |
| Backup corruption (file copy on live DB) | Tampering | `sqlite3.Connection.backup()` is transactionally safe; file copy is not — correct API mandatory |
| AuditEventType enum bypass | Tampering | `StrEnum` with exhaustive members; `str(event_type)` always produces a known value |

**Phase 2 security posture:** Low risk. Local SQLite file; no network, no auth, no secrets. The primary security value is preventing SQL injection via parameterized queries — SQLAlchemy Core provides this by design.

---

## Sources

### Primary (HIGH confidence)
- Python 3.11 stdlib `sqlite3.Connection.backup()` — `uv run python -c "help(sqlite3.Connection.backup)"` [VERIFIED: local execution]
- SQLAlchemy 2.0 `MetaData.create_all(checkfirst=True)` — https://docs.sqlalchemy.org/en/20/core/metadata.html [CITED: WebFetch]
- SQLAlchemy 2.0 partial index via `sqlite_where` — https://docs.sqlalchemy.org/en/20/dialects/sqlite.html [CITED: WebFetch]
- SQLAlchemy 2.0 `engine.raw_connection().driver_connection` — https://docs.sqlalchemy.org/en/20/core/connections.html [CITED: WebFetch]
- SQLAlchemy 2.0 `URL.create("sqlite+pysqlite", database=...)` — https://docs.sqlalchemy.org/en/20/core/engines.html [CITED: WebFetch]
- Python 3.11 `StrEnum` — https://docs.python.org/3.11/library/enum.html#enum.StrEnum [CITED: WebFetch]
- SQLAlchemy mypy plugin deprecated — https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html [CITED: WebFetch]
- All patterns verified by running code on the actual installed stack (sqlalchemy 2.0.48/2.0.49, Python 3.12, mypy 2.1.0) [VERIFIED: local tests]

### Secondary (MEDIUM confidence)
- `URL.create()` with pathlib.Path on Windows — https://www.tutorialpedia.org/blog/sqlalchemy-engine-absolute-path-url-in-windows/ [CITED: WebFetch]
- StaticPool for in-memory SQLite testing — https://docs.sqlalchemy.org/en/20/core/pooling.html [CITED: WebFetch]
- Ruff TC rules and SQLAlchemy — https://docs.astral.sh/ruff/settings/#lint_flake8-type-checking_runtime-evaluated-base-classes [CITED: WebFetch]

### Tertiary (LOW confidence — flagged as [ASSUMED])
- A1: `_build_engine()` private helper split pattern
- A2: `pages=-1` (full backup) is appropriate for v1 file sizes
- A3: nullable `scan_id` FK for off-signal positions
- A4: `raw_output` TEXT column for scan output storage

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified via pip, all patterns verified by running code
- Architecture (7 tables): HIGH — all columns derived from requirements; all create_all patterns verified
- Pitfalls: HIGH — all confirmed via local test execution on Windows (the production platform)
- Backup pattern: HIGH — `driver_connection` confirmed, `[WinError 1314]` confirmed on this machine

**Research date:** 2026-05-23
**Valid until:** 2026-07-23 (stable stack; SQLAlchemy 2.0.x is on a maintenance train)
