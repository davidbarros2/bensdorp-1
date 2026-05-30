# Phase 10: System Commands - Pattern Map

**Mapped:** 2026-05-30
**Files analyzed:** 6 (3 command files + 3 test files)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/bensdorp1/commands/status.py` | command | request-response (read-only queries) | `src/bensdorp1/commands/config.py` | role-match (multi-section kv display) |
| `src/bensdorp1/commands/refresh.py` | command | request-response + external HTTP | `src/bensdorp1/commands/cash.py` | role-match (state-change + audit log) |
| `src/bensdorp1/commands/restore.py` | command | request-response (file I/O + two confirms) | `src/bensdorp1/commands/cash.py` | exact (confirm-then-act + backup + log_event) |
| `tests/test_commands/test_status.py` | test | request-response | `tests/test_commands/test_config.py` | exact (read-only CLI test pattern) |
| `tests/test_commands/test_refresh.py` | test | request-response + mock HTTP | `tests/test_commands/test_cash.py` | role-match (mock external + assert audit) |
| `tests/test_commands/test_restore.py` | test | request-response + file I/O | `tests/test_commands/test_cash.py` | exact (confirm flow + mock backup + mock log) |

---

## Pattern Assignments

### `src/bensdorp1/commands/status.py` (command, read-only multi-section)

**Primary analog:** `src/bensdorp1/commands/config.py`
**Secondary analog:** `src/bensdorp1/commands/cash.py` (DB entry triad pattern)

**Imports pattern** — copy from `src/bensdorp1/commands/config.py` lines 1-13, then extend:

```python
import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import func, select, text as sa_text
from sqlalchemy.engine import Engine

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import (
    constituents_cache,
    positions,
    price_daily,
    scan_exit_triggers,
    scans,
)
from bensdorp1.ui import format_date, format_timezone_pair, render_kv_block
```

**DB entry triad** — copy verbatim from `src/bensdorp1/commands/config.py` lines 17-23:

```python
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

**Multi-section render_kv_block pattern** — copy from `src/bensdorp1/commands/config.py` lines 40-46 and extend to 4 sections. The section header + separator must use `Text()` wrapping (no Raw strings to console.print):

```python
# From config.py lines 40-46 — single-section pattern to extend:
data: dict[str, str] = { ... }
render_kv_block(data, console)
raise typer.Exit()

# For status.py — four sections with headers and separators:
console.print(Text("Data status"), markup=False, highlight=False)
console.print(Text("-----------"), markup=False, highlight=False)
render_kv_block(data_section, console)
console.print()
console.print(Text("Backup status"), markup=False, highlight=False)
console.print(Text("-------------"), markup=False, highlight=False)
render_kv_block(backup_section, console)
# ... repeat for Database status, Operational status
raise typer.Exit()
```

**Health label formatting** — net-new logic; no existing analog. Health labels appended to value strings before dict construction (safe because `render_kv_block` uses `markup=False, highlight=False` per `src/bensdorp1/ui/styles.py` line 166):

```python
# render_kv_block calls console.print(..., markup=False, highlight=False)
# So [STALE] in a value string is rendered literally, NOT as Rich markup.
# Build inline: "2026-05-22  [STALE]" as plain str, pass as dict value.
def _health_label(status: str) -> str:
    return f"[{status}]"

# Example:
constituents_value = f"{ticker_count} tickers, last updated {format_date(last_fetched.date())}  {_health_label('STALE')}"
```

**DB queries for status sections** — use parameterized SQLAlchemy selects, engine.connect() context manager, no string interpolation:

```python
# Constituents count + last fetched (from RESEARCH.md code examples, verified against schema.py)
with engine.connect() as conn:
    row = conn.execute(
        select(
            func.count(constituents_cache.c.id),
            func.max(constituents_cache.c.fetched_at),
        )
    ).fetchone()
ticker_count: int = row[0] if row else 0
last_fetched: datetime | None = row[1] if row else None

# Pending exits (join pattern from RESEARCH.md code examples)
with engine.connect() as conn:
    pending_exits = conn.execute(
        select(func.count(scan_exit_triggers.c.id))
        .join(positions, scan_exit_triggers.c.position_id == positions.c.id)
        .where(positions.c.closed_at.is_(None))
    ).scalar()
```

**PRAGMA integrity_check** — use `.fetchall()` not `.scalar()` to catch multi-row failure results (Pitfall 4):

```python
with engine.connect() as conn:
    rows = conn.execute(sa_text("PRAGMA integrity_check")).fetchall()
integrity_ok = len(rows) == 1 and rows[0][0] == "ok"
```

**Backup directory scan** — pathlib glob, guard against missing directory (Pitfall 5):

```python
backups_dir = DATA_DIR / "backups"
if backups_dir.exists():
    db_files = sorted(
        backups_dir.glob("*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    latest_backup_path = db_files[0] if db_files else None
    snapshot_count = len(db_files)
else:
    latest_backup_path = None
    snapshot_count = 0
```

**Exit pattern** — copy from `src/bensdorp1/commands/config.py` line 47:

```python
raise typer.Exit()
```

---

### `src/bensdorp1/commands/refresh.py` (command, external HTTP + audit log)

**Primary analog:** `src/bensdorp1/commands/cash.py` (audit log + success message)
**Secondary analog:** `src/bensdorp1/data/constituents.py` (refresh_constituents function to call)

**Imports pattern** — copy DB entry triad imports from `cash.py` lines 7-31, reduce to needed subset:

```python
import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select
from sqlalchemy.engine import Engine

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.data import refresh_constituents   # NOT fetch_constituents
from bensdorp1.db import get_engine, log_event, run_migrations, AuditEventType
from bensdorp1.db.schema import constituents_cache
from bensdorp1.ui import (
    SpinnerContext,
    print_success,
    print_warning,
    render_table,
)
```

**DB entry triad** — copy verbatim from `cash.py` lines 50-53:

```python
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

**Pre/post snapshot + diff pattern** — net-new logic; no existing analog. Query `constituents_cache` directly (never import private `_read_cached_constituents`):

```python
def _read_symbols(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(select(constituents_cache.c.symbol)).fetchall()
    return {row.symbol for row in rows}

symbols_before = _read_symbols(engine)
with SpinnerContext("Fetching S&P 500 constituents...", console=console):
    refresh_constituents(engine)
symbols_after = _read_symbols(engine)

added = sorted(symbols_after - symbols_before)
removed = sorted(symbols_before - symbols_after)
total_after = len(symbols_after)
```

**render_table call pattern** — from `src/bensdorp1/ui/tables.py` lines 18-41. Columns are `list[tuple[str, Justify]]`, rows are `list[list[str]]`:

```python
# From tables.py signature:
render_table(
    columns=[("Added", "left"), ("Removed", "left")],
    rows=rows_list,
    console=console,
)
```

**print_success (no-change)** — from `cash.py` line 141 pattern:

```python
print_success(f"Constituents up to date. {total_after} tickers, no changes.", console=console)
```

**log_event call** — copy from `cash.py` lines 136-140, substitute event type. Note: `refresh_constituents` already logs `CONSTITUENTS_UPDATED` internally. `refresh.py` does NOT log it again; if a second audit event is needed (e.g., to record diff counts), use `AuditEventType.CONSTITUENTS_UPDATED` with a different payload:

```python
# From cash.py lines 136-140 — pattern to copy:
log_event(
    engine,
    AuditEventType.CASH_UPDATED,
    payload=payload,
)
```

**Exit pattern** — `raise typer.Exit()` at end (no explicit exit needed if function just returns).

---

### `src/bensdorp1/commands/restore.py` (command, file I/O + two confirms + backup)

**Primary analog:** `src/bensdorp1/commands/cash.py` — exact match for confirm-then-act + create_backup + log_event

**Imports pattern** — copy from `cash.py` lines 1-31, extend for restore-specific needs:

```python
import shutil
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import inspect as sa_inspect, text as sa_text
from sqlalchemy.engine import URL, Engine, create_engine

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.ui import (
    confirm_prompt,
    print_error,
    print_info,
    print_success,
    render_kv_block,
)
```

**DB entry triad** — copy verbatim from `cash.py` lines 50-53:

```python
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

**typer.Argument for PATH** — copy pattern from `cash.py` lines 37-46, adapt for Path:

```python
@app.command(rich_help_panel="System")
def restore(
    path: Path = typer.Argument(..., help="Path to the backup .db file to restore."),
) -> None:
    """Replace the active database with a backup file."""
```

**PATH resolution + existence check** — use `Path.resolve()` then check `.exists()`. Exit code 1 on failure:

```python
resolved = path.resolve()
if not resolved.exists():
    print_error(
        f"File not found: {resolved}",
        console=console,
    )
    raise typer.Exit(code=1)
```

**Secondary engine for validation + disposal** — from `db/engine.py` lines 38-49 (`_build_engine` pattern), wrapped in try/finally to guarantee disposal before file copy (Pitfall 2 — Windows file locking):

```python
EXPECTED_TABLES = frozenset({
    "config", "scans", "positions", "audit_log",
    "scan_candidates", "scan_exit_triggers",
    "constituents_cache", "price_daily",
})

val_url = URL.create("sqlite+pysqlite", database=str(resolved))
val_engine = create_engine(val_url)
try:
    with val_engine.connect() as conn:
        rows = conn.execute(sa_text("PRAGMA integrity_check")).fetchall()
        integrity_ok = len(rows) == 1 and rows[0][0] == "ok"
    inspector = sa_inspect(val_engine)
    existing_tables = frozenset(inspector.get_table_names())
    schema_valid = EXPECTED_TABLES.issubset(existing_tables)
except Exception:
    integrity_ok = False
    schema_valid = False
finally:
    val_engine.dispose()  # CRITICAL on Windows — release file handle before copy
```

**Double-confirmation pattern** — copy from `cash.py` lines 107-113 twice, adapting the prompt text:

```python
# First confirmation (cash.py lines 107-113 exact pattern):
try:
    confirmed = confirm_prompt("Replace active database with this file?", console=console)
except KeyboardInterrupt:
    raise typer.Exit() from None
if not confirmed:
    raise typer.Exit()

# Second confirmation — same pattern, different prompt:
try:
    confirmed = confirm_prompt(
        "A pre-restore backup will be created first. "
        "This will overwrite your current database. Are you sure?",
        console=console,
    )
except KeyboardInterrupt:
    raise typer.Exit() from None
if not confirmed:
    raise typer.Exit()
```

**Pre-restore backup creation** — `create_backup` from `cash.py` line 134 pattern. For the exact `bensdorp1-pre-restore-{ts}.db` naming, use inline `shutil.copy2` with timestamp (see RESEARCH.md Pattern 5 and Open Question 1). If using `create_backup()`, accept the standard `bensdorp1-{ts}.db` name:

```python
# Option A: exact pre-restore filename (matches spec §10 example):
from datetime import UTC, datetime
ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
backups_dir = DATA_DIR / "backups"
backups_dir.mkdir(parents=True, exist_ok=True)
pre_restore_path = backups_dir / f"bensdorp1-pre-restore-{ts}.db"
shutil.copy2(db_path, pre_restore_path)

# Option B: call existing create_backup (from cash.py line 134 pattern):
pre_restore_path = create_backup(engine, DATA_DIR / "backups")
```

**Active DB file replacement** — D-12: `shutil.copy2(PATH, active_db_path)`:

```python
shutil.copy2(resolved, db_path)
```

**log_event to restored DB** — D-11: log in the NEW database after swap, not the pre-restore. Open a fresh engine to the same path (engine singleton has been writing to the same path, post-copy reads will see new content):

```python
# log_event call — copy from cash.py lines 136-140 pattern:
payload: dict[str, Any] = {
    "restored_from": str(resolved),
    "pre_restore_backup": str(pre_restore_path),
}
log_event(engine, AuditEventType.RESTORE_PERFORMED, payload=payload)
print_success("Database restored. Run `bensdorp1 status` to verify.", console=console)
```

---

### `tests/test_commands/test_status.py` (test, read-only CLI)

**Primary analog:** `tests/test_commands/test_config.py` — exact match (read-only CLI, db_engine fixture, patch DATA_DIR + get_engine + run_migrations)

**Test file structure** — copy from `test_config.py` lines 1-16:

```python
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import constituents_cache, scans, positions, price_daily

runner = CliRunner()
```

**Test function pattern** — copy from `test_config.py` lines 17-44:

```python
def test_status_shows_four_sections(db_engine: Engine, tmp_path: Path) -> None:
    """status shows all 4 sections when DB has data."""
    # Seed tables as needed...
    with (
        patch("bensdorp1.commands.status.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.status.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.status.run_migrations"),
    ):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Data status" in result.output
    assert "Backup status" in result.output
```

**No-backups test** — patch DATA_DIR to tmp_path (no backups subdir exists → empty glob). No mock needed, just use tmp_path:

```python
def test_status_no_backups_does_not_crash(tmp_path: Path) -> None:
    mock_engine = MagicMock()
    # ... configure mock_engine for all DB queries to return empty results
    with (
        patch("bensdorp1.commands.status.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.status.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.status.run_migrations"),
    ):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "No backups" in result.output  # or similar graceful text
```

---

### `tests/test_commands/test_refresh.py` (test, mock HTTP + diff assertion)

**Primary analog:** `tests/test_commands/test_cash.py` — mock external dependencies + assert audit call

**Test file structure** — copy from `test_cash.py` lines 1-15:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app

runner = CliRunner()
```

**Mock refresh_constituents** — patch the import path in refresh.py module, not the source module:

```python
def test_refresh_no_changes(db_engine: Engine, tmp_path: Path) -> None:
    """refresh shows no-change message when refresh_constituents adds nothing."""
    mock_refresh = MagicMock()  # refresh_constituents does nothing

    with (
        patch("bensdorp1.commands.refresh.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.refresh.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.refresh.run_migrations"),
        patch("bensdorp1.commands.refresh.refresh_constituents", mock_refresh),
    ):
        result = runner.invoke(app, ["refresh"])

    assert result.exit_code == 0
    assert "up to date" in result.output
    mock_refresh.assert_called_once()
```

**Mock + assert log_event** — copy from `test_cash.py` lines 79-106 pattern:

```python
mock_refresh = MagicMock()
mock_log = MagicMock()

with (
    patch("bensdorp1.commands.refresh.refresh_constituents", mock_refresh),
    patch("bensdorp1.commands.refresh.log_event", mock_log),
    ...
):
    result = runner.invoke(app, ["refresh"])
```

---

### `tests/test_commands/test_restore.py` (test, file I/O + double confirm flow)

**Primary analog:** `tests/test_commands/test_cash.py` — confirm flow (input="y\n" / "n\n"), mock backup + log_event

**Test file structure** — copy from `test_cash.py` lines 1-15, add `import tempfile` / `shutil` as needed for creating test DB files:

```python
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import metadata  # for seeding a valid backup file

runner = CliRunner()
```

**Valid backup DB fixture** — create a real SQLite file with all 8 tables for happy-path tests:

```python
@pytest.fixture
def valid_backup_db(tmp_path: Path) -> Path:
    """Create a valid SQLite file with all expected tables for restore tests."""
    from sqlalchemy.engine import URL, create_engine
    backup_path = tmp_path / "bensdorp1-test-backup.db"
    url = URL.create("sqlite+pysqlite", database=str(backup_path))
    engine = create_engine(url)
    metadata.create_all(engine)
    engine.dispose()
    return backup_path
```

**Single-confirm abort** — copy from `test_cash.py` lines 117-155, adapt for double-confirm. First confirm "n\n" should abort without touching backup or log:

```python
def test_restore_first_confirm_no(valid_backup_db: Path, db_engine: Engine, tmp_path: Path) -> None:
    mock_backup = MagicMock()
    mock_log = MagicMock()

    with (
        patch("bensdorp1.commands.restore.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.restore.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.restore.run_migrations"),
        patch("bensdorp1.commands.restore.create_backup", mock_backup),
        patch("bensdorp1.commands.restore.log_event", mock_log),
    ):
        result = runner.invoke(app, ["restore", str(valid_backup_db)], input="n\n")

    assert result.exit_code == 0
    mock_backup.assert_not_called()
    mock_log.assert_not_called()
```

**Double-confirm happy path** — `input="y\ny\n"` feeds both prompts:

```python
result = runner.invoke(app, ["restore", str(valid_backup_db)], input="y\ny\n")
assert result.exit_code == 0
assert "restored" in result.output.lower()
```

---

## Shared Patterns

### DB Entry Triad
**Source:** `src/bensdorp1/commands/cash.py` lines 50-53
**Apply to:** `status.py`, `refresh.py`, `restore.py`

```python
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

### Console Ownership
**Source:** `src/bensdorp1/commands/cash.py` line 53; CONTEXT.md established patterns
**Apply to:** All three command files and all three test files

```python
# Command entry: Console() created at top
console = Console()
# Pass to all UI calls: render_kv_block(data, console), print_success(..., console=console)

# Tests: Console(record=True) passed via CliRunner, or inspect result.output directly
runner = CliRunner()  # CliRunner captures stdout; assert on result.output
```

### Text() Wrapping for console.print()
**Source:** `src/bensdorp1/commands/cash.py` lines 93-94; CONTEXT.md established patterns
**Apply to:** Any direct `console.print()` calls in status.py (section headers, separators)

```python
# Always wrap bare strings:
console.print(Text("Data status"), markup=False, highlight=False)
console.print(Text("-----------"), markup=False, highlight=False)
# NOT: console.print("Data status")  -- allows markup injection
```

### Confirm Prompt + KeyboardInterrupt Handler
**Source:** `src/bensdorp1/commands/cash.py` lines 107-113
**Apply to:** `restore.py` (both confirmation prompts)

```python
try:
    confirmed = confirm_prompt("...", console=console)
except KeyboardInterrupt:
    raise typer.Exit() from None
if not confirmed:
    raise typer.Exit()
```

### create_backup Call
**Source:** `src/bensdorp1/commands/cash.py` line 134; `src/bensdorp1/db/backup.py` lines 21-62
**Apply to:** `restore.py` (pre-restore backup creation)

```python
# create_backup signature:
def create_backup(engine: Engine, backups_dir: Path) -> Path:
    ...  # returns Path to timestamped backup file

# Call pattern from cash.py line 134:
create_backup(engine, DATA_DIR / "backups")
```

### log_event Call
**Source:** `src/bensdorp1/commands/cash.py` lines 136-140; `src/bensdorp1/db/audit.py` lines 44-63
**Apply to:** `refresh.py` (if logging diff counts), `restore.py` (RESTORE_PERFORMED)

```python
# log_event signature:
def log_event(
    engine: Engine,
    event_type: AuditEventType,
    symbol: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None: ...

# Call pattern (positional engine + event_type, keyword payload):
log_event(
    engine,
    AuditEventType.RESTORE_PERFORMED,
    payload={"restored_from": str(resolved), "pre_restore_backup": str(pre_restore_path)},
)
```

### render_kv_block Markup Safety
**Source:** `src/bensdorp1/ui/styles.py` line 166
**Apply to:** `status.py` health labels (the `[STALE]`/`[OK]` strings)

```python
# render_kv_block calls: console.print(..., markup=False, highlight=False)
# So health label strings like "[STALE]" in dict values are safe — rendered literally.
# Never pass health labels through a bare console.print() without markup=False.
```

### Test Patch Pattern
**Source:** `tests/test_commands/test_config.py` lines 31-36; `tests/test_commands/test_cash.py` lines 24-28
**Apply to:** All three test files

```python
with (
    patch("bensdorp1.commands.<module>.DATA_DIR", tmp_path),
    patch("bensdorp1.commands.<module>.get_engine", return_value=db_engine),
    patch("bensdorp1.commands.<module>.run_migrations"),
):
    result = runner.invoke(app, ["<command>"])
```

---

## No Analog Found

All files have analogs. The only net-new logic patterns (no codebase analog) are:

| Logic | File | Reason | Use Instead |
|---|---|---|---|
| Inline health label computation `[OK]/[STALE]/[WARNING]/[FAILED]` | `status.py` | No existing command does conditional inline status strings | RESEARCH.md Pattern 2 |
| Pre/post constituent snapshot diff | `refresh.py` | No existing command compares before/after DB state | RESEARCH.md Pattern 3 |
| Secondary SQLAlchemy engine open/validate/dispose | `restore.py` | No existing command opens a second engine for validation | RESEARCH.md Pattern 4 |
| Valid backup DB pytest fixture | `test_restore.py` | No existing test creates a real SQLite file as test input | Use `_build_engine` + `metadata.create_all` from conftest.py lines 41-43 |

---

## Metadata

**Analog search scope:** `src/bensdorp1/commands/`, `tests/test_commands/`, `src/bensdorp1/ui/`, `src/bensdorp1/db/`, `src/bensdorp1/data/`
**Files read:** `commands/cash.py`, `commands/config.py`, `db/backup.py`, `db/audit.py`, `db/engine.py`, `ui/__init__.py`, `ui/styles.py`, `ui/messages.py`, `ui/progress.py`, `ui/tables.py`, `ui/prompts.py`, `data/constituents.py`, `tests/conftest.py`, `tests/test_commands/test_cash.py`, `tests/test_commands/test_config.py`, `tests/test_commands/test_sell.py`
**Pattern extraction date:** 2026-05-30
