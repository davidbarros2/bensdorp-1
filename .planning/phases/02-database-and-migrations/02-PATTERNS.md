# Phase 2: Database and Migrations - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 11 (5 source + 6 test)
**Analogs found:** 7 / 11 (4 files have no codebase analog — patterns come from RESEARCH.md)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/bensdorp1/db/__init__.py` | package-init / re-export | n/a | `src/bensdorp1/cli.py` | role-match (re-export module) |
| `src/bensdorp1/db/schema.py` | schema-definition | n/a (DDL only) | none — no schema files exist yet | no analog |
| `src/bensdorp1/db/engine.py` | service / singleton | request-response | `src/bensdorp1/_app.py` | partial (module-level singleton) |
| `src/bensdorp1/db/backup.py` | utility | file-I/O | none — no file-I/O utilities exist | no analog |
| `src/bensdorp1/db/audit.py` | service + enum | CRUD | none — no enum+writer modules exist | no analog |
| `tests/conftest.py` | test-fixture | n/a | `tests/test_cli.py` (runner setup) | partial (module-level test setup) |
| `tests/test_db_schema.py` | integration-test | n/a | `tests/test_repo.py` | role-match (existence assertions) |
| `tests/test_db_engine.py` | unit-test | n/a | `tests/test_cli.py` | role-match (parametrize + exit assertions) |
| `tests/test_db_backup.py` | unit-test | file-I/O | `tests/test_repo.py` | partial (pathlib assertions) |
| `tests/test_db_audit.py` | unit-test | CRUD | `tests/test_cli.py` | partial (parametrize pattern) |
| `tests/test_db_positions.py` | integration-test | CRUD | `tests/test_cli.py` | partial (pytest.raises pattern) |

---

## Pattern Assignments

### `src/bensdorp1/db/__init__.py` (package-init, re-export)

**Analog:** `src/bensdorp1/cli.py`

The project uses selective `__all__` re-exports in package `__init__.py` files. `cli.py` demonstrates the pattern: import from submodules to expose a clean public surface, declare `__all__` explicitly.

**Re-export pattern** (`src/bensdorp1/cli.py`, lines 1–23):
```python
from bensdorp1._app import app  # re-export for entry point

# Import all command modules to trigger @app.command() decorations:
import bensdorp1.commands.audit  # noqa: F401
import bensdorp1.commands.buy  # noqa: F401
# ...

__all__ = ["app"]
```

**Apply to `db/__init__.py`:**
```python
from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.backup import create_backup
from bensdorp1.db.engine import get_engine, run_migrations

__all__ = ["get_engine", "run_migrations", "create_backup", "log_event", "AuditEventType"]
```

Key rule from `cli.py`: ruff `I001` may be suppressed on the init if import ordering would conflict with side-effect ordering. Use `# noqa: F401` on imports that exist only for re-export.

---

### `src/bensdorp1/db/schema.py` (schema-definition, DDL)

**Analog:** None — no schema files exist in the codebase. Use RESEARCH.md Pattern 1 and Code Examples section.

**Imports pattern** (from RESEARCH.md, verified locally):
```python
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
```

**Module-level singleton pattern** (`src/bensdorp1/_app.py`, lines 1–9):
```python
import typer

app = typer.Typer(
    name="bensdorp1",
    ...
)
```
Apply the same module-level singleton pattern for `metadata`:
```python
metadata: MetaData = MetaData()
```

**Core table definition pattern** (RESEARCH.md Code Examples, schema.py skeleton):
```python
config: Table = Table(
    "config",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=True),
    Column("updated_at", DateTime, nullable=False),
)
```

**Partial unique index pattern** (RESEARCH.md Pattern 4):
```python
Index(
    "ix_positions_open_symbol",
    positions.c.symbol,
    unique=True,
    sqlite_where=(positions.c.closed_at == None),  # noqa: E711
)
```
The `# noqa: E711` is mandatory — ruff flags `== None` but `is None` breaks SQLAlchemy's SQL expression generation.

**Table definition order:** `config` → `scans` → `positions` (FK to scans) → `audit_log` → `scan_candidates` (FK to scans) → `constituents_cache` → `price_daily`. SQLAlchemy resolves string FK references at `create_all()` time, so Python definition order doesn't affect correctness — but define parent tables first for readability.

---

### `src/bensdorp1/db/engine.py` (service, singleton, request-response)

**Analog:** `src/bensdorp1/_app.py` — closest existing module-level singleton pattern.

**Module-level singleton pattern** (`_app.py`, lines 1–9):
```python
import typer

app = typer.Typer(
    name="bensdorp1",
    ...
)
```
`engine.py` follows the same principle — one module-level variable, initialized once.

**Full engine module pattern** (RESEARCH.md Pattern 3, verified locally):
```python
import os
import threading
from pathlib import Path
from typing import Optional

from sqlalchemy.engine import URL, Engine, create_engine

_engine: Optional[Engine] = None
_engine_lock: threading.Lock = threading.Lock()


def get_engine(path: Optional[Path] = None) -> Engine:
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


def _build_engine(path: Path) -> Engine:
    url = URL.create("sqlite+pysqlite", database=str(path))
    return create_engine(url)


def run_migrations(engine: Engine) -> None:
    """Create all tables idempotently. Called only from bensdorp1 init."""
    from bensdorp1.db.schema import metadata
    metadata.create_all(engine, checkfirst=True)


def _reset_engine_for_testing(replacement: Optional[Engine] = None) -> None:
    """Test helper: dispose and reset the cached engine."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = replacement
```

**mypy note:** `Optional[Path]` and `Optional[Engine]` are the mypy-strict-compatible spellings for Python 3.11 (use `X | None` only if targeting 3.10+ syntax; both are equivalent under mypy strict with `python_version = "3.11"`). Either form is acceptable; match whatever convention the planner establishes.

**`-> None` on every function** — enforced by mypy strict (`disallow_incomplete_defs`). Every function in `engine.py` must have an explicit return type. `_reset_engine_for_testing` and `run_migrations` both return `None`.

---

### `src/bensdorp1/db/backup.py` (utility, file-I/O)

**Analog:** None — no file-I/O utilities exist. Use RESEARCH.md Pattern 5.

**Full backup function** (RESEARCH.md Pattern 5, verified locally on Windows):
```python
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

    shutil.copy2(backup_path, latest_path)
    return backup_path
```

**Critical Windows constraint:** `latest_path.symlink_to(...)` raises `[WinError 1314]` on this machine. Use `shutil.copy2` unconditionally — no symlink attempt, no try/except around it.

**`driver_connection` suppression:** `raw_conn.driver_connection` returns `Any` from mypy's perspective. The `# type: ignore[assignment]` on that line is the correct minimal suppression — do not add a broader ignore.

---

### `src/bensdorp1/db/audit.py` (service + enum, CRUD)

**Analog:** None — no enum-plus-writer modules exist. Use RESEARCH.md Patterns 6 and 7.

**StrEnum import and class definition** (RESEARCH.md Pattern 6):
```python
from enum import StrEnum


class AuditEventType(StrEnum):
    """All 17 audit event types from STATE-04."""
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

**Use `StrEnum`, not `class AuditEventType(str, Enum)`:** Python 3.11 changed `str, Enum`'s `__str__()` to return `"ClassName.MEMBER"`, not the value. `StrEnum` uses `str.__str__()` which returns the raw value — required for direct SQLite TEXT storage.

**log_event function** (RESEARCH.md Pattern 7, verified under mypy strict):
```python
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
                event_type=str(event_type),
                occurred_at=datetime.now(timezone.utc),
                symbol=symbol,
                payload=json.dumps(payload) if payload is not None else None,
            )
        )
        conn.commit()
```

---

### `tests/conftest.py` (test-fixture)

**Analog:** `tests/test_cli.py` — the only existing test file with module-level setup (`runner = CliRunner()`). Does not use `conftest.py` fixtures yet, but establishes that tests import from `bensdorp1.*` directly.

**Module-level runner pattern** (`tests/test_cli.py`, lines 1–6):
```python
import pytest
from typer.testing import CliRunner

from bensdorp1.cli import app

runner = CliRunner()
```

**db_engine fixture pattern** (RESEARCH.md, conftest.py example, verified locally):
```python
import pytest
from pathlib import Path
from typing import Generator

from sqlalchemy.engine import Engine

import bensdorp1.db.engine as engine_module
from bensdorp1.db.schema import metadata


@pytest.fixture()
def db_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    """Fresh file-based SQLite engine per test. Resets module-level cache."""
    db_path = tmp_path / "test.db"
    engine = engine_module._build_engine(db_path)
    engine_module._reset_engine_for_testing(engine)
    metadata.create_all(engine, checkfirst=True)
    try:
        yield engine
    finally:
        engine_module._reset_engine_for_testing()
        engine.dispose()  # CRITICAL on Windows: releases file handles before tmp_path cleanup
```

**Windows teardown constraint:** `engine.dispose()` must be in the `finally` block. Without it, `tmp_path` cleanup fails with `[WinError 32]` (file in use by SQLAlchemy connection pool).

**Return type annotation:** `Generator[Engine, None, None]` is required for mypy strict on fixture functions that `yield`. Import `Generator` from `typing`.

---

### `tests/test_db_schema.py` (integration-test, existence assertions)

**Analog:** `tests/test_repo.py` — uses `Path` assertions to verify file existence. Same pattern applies to table-existence assertions via `inspect`.

**Pathlib assertion pattern** (`tests/test_repo.py`, lines 1–4):
```python
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

def test_pyproject_toml_exists() -> None:
    assert (REPO_ROOT / "pyproject.toml").exists()
```

**Apply to schema tests** — each test is a single assertion; use `sqlalchemy.inspect` to confirm tables and indexes:
```python
from sqlalchemy import inspect
from sqlalchemy.engine import Engine


def test_all_tables_created(db_engine: Engine) -> None:
    insp = inspect(db_engine)
    tables = set(insp.get_table_names())
    expected = {
        "config", "positions", "audit_log", "scans",
        "scan_candidates", "constituents_cache", "price_daily",
    }
    assert expected == tables


def test_create_all_idempotent(db_engine: Engine) -> None:
    from bensdorp1.db.schema import metadata
    # Second call must not raise
    metadata.create_all(db_engine, checkfirst=True)


def test_partial_index_exists(db_engine: Engine) -> None:
    insp = inspect(db_engine)
    index_names = {idx["name"] for idx in insp.get_indexes("positions")}
    assert "ix_positions_open_symbol" in index_names
```

**Function signature pattern:** every test function is `def test_*(db_engine: Engine) -> None:` — typed, explicit `-> None`, accepting the `db_engine` fixture by name.

---

### `tests/test_db_engine.py` (unit-test)

**Analog:** `tests/test_cli.py` — uses direct function calls, `assert result.exit_code`, and `pytest.mark.parametrize`.

**Import and invoke pattern** (`tests/test_cli.py`, lines 1–8):
```python
import pytest
from typer.testing import CliRunner

from bensdorp1.cli import app

runner = CliRunner()

def test_root_help_exits_cleanly() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
```

**Apply to engine tests** — import the module under test directly; use `monkeypatch` (pytest built-in) for `os.environ`:
```python
import pytest
from pathlib import Path

import bensdorp1.db.engine as engine_module
from bensdorp1.db.engine import get_engine


def test_get_engine_returns_engine(db_engine) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy.engine import Engine
    assert isinstance(db_engine, Engine)


def test_bensdorp1_home_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine_module._reset_engine_for_testing()
    home = tmp_path / "custom_home"
    home.mkdir()
    monkeypatch.setenv("BENSDORP1_HOME", str(home))
    resolved = engine_module._resolve_db_path(None)
    assert resolved == home / "data" / "bensdorp1.db"
```

**mypy override:** `bensdorp1.commands.*` already has `disallow_untyped_decorators = false` in `pyproject.toml`. Test files that accept fixtures without explicit types may need a similar override, or use `# type: ignore[no-untyped-def]` on individual functions if mypy strict fires on fixture-injected parameters.

---

### `tests/test_db_backup.py` (unit-test, file-I/O assertions)

**Analog:** `tests/test_repo.py` — pathlib-based file existence assertions.

**Pathlib assertion pattern** (`tests/test_repo.py`, lines 7–10):
```python
def test_license_exists() -> None:
    assert (REPO_ROOT / "LICENSE").exists()
```

**Apply to backup tests:**
```python
from pathlib import Path
from sqlalchemy.engine import Engine
from bensdorp1.db.backup import create_backup


def test_backup_creates_timestamped_file(db_engine: Engine, tmp_path: Path) -> None:
    backups_dir = tmp_path / "backups"
    result = create_backup(db_engine, backups_dir)
    assert result.exists()
    assert result.name.startswith("bensdorp1-")
    assert result.suffix == ".db"


def test_latest_db_updated(db_engine: Engine, tmp_path: Path) -> None:
    backups_dir = tmp_path / "backups"
    create_backup(db_engine, backups_dir)
    assert (backups_dir / "bensdorp1-latest.db").exists()
```

---

### `tests/test_db_audit.py` (unit-test, parametrize)

**Analog:** `tests/test_cli.py` — `@pytest.mark.parametrize` over a list of values.

**Parametrize pattern** (`tests/test_cli.py`, lines 34–58):
```python
@pytest.mark.parametrize(
    "cmd",
    [
        "init",
        "restore",
        # ...
    ],
)
def test_stub_exits_cleanly(cmd: str) -> None:
    result = runner.invoke(app, [cmd])
    assert result.exit_code == 0
```

**Apply to audit tests** — parametrize over all 17 `AuditEventType` members:
```python
import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.schema import audit_log


@pytest.mark.parametrize("event_type", list(AuditEventType))
def test_all_event_types_insertable(db_engine: Engine, event_type: AuditEventType) -> None:
    log_event(db_engine, event_type)
    with db_engine.connect() as conn:
        row = conn.execute(
            select(audit_log).where(audit_log.c.event_type == str(event_type))
        ).fetchone()
    assert row is not None
```

---

### `tests/test_db_positions.py` (integration-test, pytest.raises)

**Analog:** `tests/test_cli.py` — uses `pytest.raises` implicitly (via exit code checks). The explicit `pytest.raises(IntegrityError)` pattern is established in RESEARCH.md.

**pytest.raises pattern** (`tests/test_cli.py`, line 30):
```python
def test_help_unknown_command_exits_nonzero() -> None:
    result = runner.invoke(app, ["help", "nonexistent"])
    assert result.exit_code != 0
```

**Apply to positions tests** (RESEARCH.md Code Examples, test_db_positions.py):
```python
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
```

---

## Shared Patterns

### `-> None` on all functions
**Source:** `src/bensdorp1/commands/init.py` (line 7), `src/bensdorp1/commands/help.py` (line 11)
**Apply to:** Every function in every new file
```python
def init() -> None:
def help(...) -> None:
```
mypy strict (`disallow_incomplete_defs`) rejects functions without explicit return types. No exceptions.

---

### `pathlib.Path` throughout
**Source:** `tests/test_repo.py` (lines 1–3), CONTEXT.md D-03
```python
from pathlib import Path
REPO_ROOT = Path(__file__).parent.parent
```
Apply to: `engine.py` (`_resolve_db_path` returns `Path`), `backup.py` (`backups_dir: Path`, `backup_path: Path`), all test files that deal with filesystem.

Never use `str` for file paths — always `Path`. Never use `f"sqlite:///{path}"` — use `URL.create("sqlite+pysqlite", database=str(path))`.

---

### `datetime.now(timezone.utc)` for all timestamps
**Source:** RESEARCH.md Pattern 5 and Pattern 7 (verified under mypy strict)
```python
from datetime import datetime, timezone
ts = datetime.now(timezone.utc)
```
Apply to: `backup.py` (timestamp in filename), `audit.py` `log_event()` (`occurred_at` column).
Never use `datetime.utcnow()` (naive datetime, deprecated) or `datetime.UTC` (Python 3.11 alias — `timezone.utc` is universal).

---

### SQLAlchemy parameterized inserts (no string interpolation)
**Source:** RESEARCH.md Pattern 7; Security Domain table
```python
from sqlalchemy import insert
conn.execute(
    insert(audit_log).values(
        event_type=str(event_type),
        occurred_at=datetime.now(timezone.utc),
        symbol=symbol,
        payload=json.dumps(payload) if payload is not None else None,
    )
)
conn.commit()
```
Apply to: `audit.py` `log_event()`, and any future DML in test helpers. Never build SQL strings with f-strings or `%` formatting.

---

### mypy strict: `# type: ignore[assignment]` for `driver_connection`
**Source:** RESEARCH.md Pattern 5 (mypy strict compatibility section)
```python
sqlite_conn: sqlite3.Connection = raw_conn.driver_connection  # type: ignore[assignment]
```
Apply to: `backup.py` only. The pool proxy's `driver_connection` attribute returns `Any` — this is the minimum suppression. Do not broaden to `# type: ignore` without the error code.

---

### `noqa: F401` on re-export imports
**Source:** `src/bensdorp1/cli.py` (lines 4–20)
```python
import bensdorp1.commands.audit  # noqa: F401
```
Apply to: `db/__init__.py` only if using bare `import` statements for side-effect re-exports. If using `from ... import` style, `F401` does not fire.

---

### `noqa: E711` on SQLAlchemy `sqlite_where`
**Source:** RESEARCH.md Pattern 4 (critical note)
```python
sqlite_where=(positions.c.closed_at == None),  # noqa: E711
```
Apply to: `schema.py` partial index definition only. Ruff `E711` fires on `== None`; suppression is mandatory because `is None` would produce a Python bool instead of a SQL clause object.

---

### mypy override for test files using untyped fixtures
**Source:** `pyproject.toml` (lines 52–54)
```toml
[[tool.mypy.overrides]]
module = "bensdorp1.commands.*"
disallow_untyped_decorators = false
```
If test fixture injection parameters cause mypy strict errors on test functions, add a parallel override for `tests.*`. Alternatively, annotate fixture parameters explicitly using their types (e.g., `db_engine: Engine`). Prefer explicit annotations over overrides.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/bensdorp1/db/schema.py` | schema-definition | DDL | No SQLAlchemy schema files exist in codebase; use RESEARCH.md Code Examples skeleton |
| `src/bensdorp1/db/backup.py` | utility | file-I/O | No file-I/O utilities exist; use RESEARCH.md Pattern 5 |
| `src/bensdorp1/db/audit.py` | service + enum | CRUD | No enum-plus-writer modules exist; use RESEARCH.md Patterns 6 and 7 |
| `tests/conftest.py` | test-fixture | n/a | No conftest.py exists yet; use RESEARCH.md conftest example |

For these 4 files, the RESEARCH.md patterns are complete and verified locally — they are not hypothetical. Use them directly.

---

## Metadata

**Analog search scope:** `src/bensdorp1/`, `tests/`
**Files scanned:** `_app.py`, `cli.py`, `commands/__init__.py`, `commands/init.py`, `commands/help.py`, `tests/test_cli.py`, `tests/test_repo.py`, `pyproject.toml`
**Pattern extraction date:** 2026-05-23
