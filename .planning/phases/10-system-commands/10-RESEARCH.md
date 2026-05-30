# Phase 10: System Commands - Research

**Researched:** 2026-05-30
**Domain:** Python CLI — SQLite diagnostics, constituent refresh, database restore
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**status thresholds and labels**
- D-01: Constituents freshness >7 days = STALE, >14 days = WARNING. Last scan >1 trading day since last scan = STALE.
- D-02: Backup >3 days since last backup = STALE. DB integrity = binary OK / FAILED.
- D-03: Health label colors: OK=green, STALE=yellow, WARNING=yellow, FAILED=red. Plain text fallback handled by Rich automatically.
- D-04: Dashboard layout — four `render_kv_block` sections with `---` separators. Section order: Data status → Backup status → Database status → Operational status.
- D-05: Health labels inline after value, space-separated: `Last updated:  2026-05-22  [STALE]`.
- D-06: Operational status shows: last scan date + health label, open positions count, pending exit triggers count. "Pending exit triggers" = open `scan_exit_triggers` rows where the position's `closed_at` IS NULL.

**restore validation and flow**
- D-07: Schema validation first (before any prompt). Validation = `PRAGMA integrity_check` returns `'ok'` AND all 8 expected table names present: `config`, `scans`, `positions`, `audit_log`, `scan_candidates`, `scan_exit_triggers`, `constituents_cache`, `price_daily`.
- D-08: First confirmation — show file info (resolved absolute path, file size KB/MB, last modified date), then: "Replace active database with this file?".
- D-09: Second confirmation wording: "A pre-restore backup will be created first. This will overwrite your current database. Are you sure?".
- D-10: Pre-restore backup filename: `bensdorp1-pre-restore-{timestamp}.db` in `~/bensdorp1/backups/`, using `create_backup` call pattern. Created after both confirmations, before the file copy. On failure between backup and copy, print error naming pre-restore backup location.
- D-11: `restore_performed` audit event logged in the NEW (restored) database after swap. Payload: `{"restored_from": str(PATH), "pre_restore_backup": str(backup_path)}`.
- D-12: File copy uses `shutil.copy2(PATH, active_db_path)`.

**refresh change output**
- D-13: On changes — "Added: N tickers, Removed: N ticker(s)." + `render_table` of changed tickers (Added / Removed sections). No table on no-change.
- D-14: On no-change — "Constituents up to date. N tickers, no changes." via `print_success`.
- D-15: `refresh` calls `refresh_constituents(engine)` from `bensdorp1.data.constituents`. SpinnerContext during fetch. Logs `CONSTITUENTS_UPDATED`. On discrepancy >= 4, shows standard discrepancy warning.

**code organization**
- D-16: Single file per command: `status.py`, `refresh.py`, `restore.py`.
- D-17: `restore.py` opens the backup file as a separate SQLAlchemy engine for validation (read-only check), then closes it before file copy. Never modify the backup file.

### Claude's Discretion
D-04, D-05, D-06, D-10, D-11, D-12, D-15, D-16, D-17 are Claude's discretion (already chosen above).

### Deferred Ideas (OUT OF SCOPE)
- Catch-up logic and split detection after absence — Phase 11
- Validate command (`bensdorp1 validate DATE`) — Phase 12
- Snapshot tests for `status`, `refresh`, `restore` output — Phase 13
- Progress bar for `refresh` (spinner is sufficient in the 1-6s range)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CMD-02 | `bensdorp1 restore PATH` — replaces current DB with backup; validates schema; two confirmation prompts; creates pre-restore backup automatically | D-07 through D-12; `create_backup`, `shutil.copy2`, SQLAlchemy secondary engine pattern all confirmed in codebase |
| CMD-14 | `bensdorp1 status` — diagnostic dashboard: data status, backup status, DB health, operational summary | D-01 through D-06; all queries confirmed against live `schema.py`; backup dir listing pattern confirmed |
| CMD-15 | `bensdorp1 refresh` — forces re-fetch and re-verification of S&P 500 constituents from both sources | D-13 through D-15; `refresh_constituents(engine)` confirmed as correct function name in `data/__init__.py` |
</phase_requirements>

---

## Summary

Phase 10 implements three stub-replacing command files — `status.py`, `refresh.py`, and `restore.py` — that are already registered in `cli.py` and currently emit "Not yet implemented." All infrastructure is in place: the DB schema, UI components, backup primitives, audit event types, and constituent-fetch logic are all production-ready from earlier phases. This phase is pure assembly work — calling existing functions in the correct order with correct error handling.

The main complexity is concentrated in two areas: (1) `status.py` must execute five distinct DB queries plus a filesystem scan against the backups directory, then format conditional health labels inline; and (2) `restore.py` must manage a multi-step file operation with two confirmation checkpoints, a secondary SQLAlchemy engine for validation, and an error-recovery path.

**Primary recommendation:** Follow the canonical patterns in `commands/cash.py` (confirm-then-act + log_event) and `commands/config.py` (multi-section render_kv_block). The only net-new logic in this phase is: (a) inline `[OK]/[STALE]/[WARNING]/[FAILED]` label formatting for status, (b) pre/post constituent cache comparison for refresh change summary, and (c) the secondary-engine open/close/copy sequence for restore.

**Critical naming correction:** The CONTEXT.md (`canonical_refs` section and D-15) references `fetch_constituents(engine)` as the entry point for `refresh.py`, but the actual codebase function is `refresh_constituents(engine)` (in `bensdorp1/data/constituents.py` line 149 and exported from `bensdorp1/data/__init__.py`). Plans MUST use `refresh_constituents`, not `fetch_constituents`. [VERIFIED: codebase grep]

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Data freshness query (constituents) | Database / Storage | — | Count + max(fetched_at) from constituents_cache |
| Backup directory scan | OS Filesystem | — | Glob backups_dir for .db files, stat mtime |
| SQLite PRAGMA integrity_check | Database / Storage | — | Raw SQLite connection via SQLAlchemy text() |
| Schema validation (restore) | Database / Storage | — | Secondary engine + inspector or metadata inspection |
| Health label formatting | CLI Output | — | Pure string logic, no tier boundary |
| Constituent re-fetch | External HTTP | Database / Storage | refresh_constituents fetches Wikipedia + Slickcharts, persists result |
| Pre-restore backup creation | Database / Storage | OS Filesystem | create_backup() uses sqlite3 backup API, then shutil.copy2 |
| Active DB file replacement | OS Filesystem | — | shutil.copy2(PATH, active_db_path) |
| Audit event logging | Database / Storage | — | log_event() writes to audit_log table |

---

## Standard Stack

No new packages needed. All dependencies are from prior phases. [VERIFIED: codebase grep]

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | >=0.21.1 | CLI command registration | Project standard per CLAUDE.md |
| sqlalchemy | >=2.0.49,<2.1 | DB queries, secondary engine for validation | Project standard per CLAUDE.md |
| rich | >=14.0 | Console, Text, render_kv_block, render_table | Project standard per CLAUDE.md |
| shutil (stdlib) | — | shutil.copy2 for file replacement | stdlib, already used in backup.py |
| sqlite3 (stdlib) | — | PRAGMA integrity_check via text() | stdlib, already used in backup.py |
| pathlib (stdlib) | — | Path resolution, backups_dir listing | stdlib, used everywhere |
| zoneinfo (stdlib) | — | Timezone for backup timestamp display | stdlib, used in config.py |

### No New Packages

This phase introduces zero new dependencies. [VERIFIED: codebase grep — all required modules already imported in prior phases]

## Package Legitimacy Audit

No new packages are installed in this phase. This section is not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
bensdorp1 status
  |
  +-- DB queries (5 queries) ──> constituents_cache (count, max fetched_at)
  |                           ──> price_daily (row count)
  |                           ──> scans (most recent scan_date)
  |                           ──> positions WHERE closed_at IS NULL (count)
  |                           ──> scan_exit_triggers JOIN positions
  |                               WHERE positions.closed_at IS NULL (count)
  |
  +-- Filesystem scan ──> ~/bensdorp1/backups/*.db (mtime, count)
  |
  +-- PRAGMA integrity_check ──> 'ok' or failure string
  |
  +-- Health label computation ──> [OK]/[STALE]/[WARNING]/[FAILED] inline strings
  |
  +-- render_kv_block (4 sections) ──> console output

bensdorp1 refresh
  |
  +-- read cache snapshot BEFORE (count + set of symbols)
  |
  +-- SpinnerContext ──> refresh_constituents(engine)
  |     |
  |     +-- Wikipedia fetch + Slickcharts fetch
  |     +-- _persist_constituents (DELETE + INSERT)
  |     +-- log_event CONSTITUENTS_UPDATED
  |
  +-- read cache snapshot AFTER (count + set of symbols)
  |
  +-- compute diff (added = after - before, removed = before - after)
  |
  +-- if no changes: print_success "Constituents up to date..."
  +-- if changes: print summary line + render_table (Added / Removed)
  |
  +-- if discrepancy >= 4: print_warning discrepancy message

bensdorp1 restore PATH
  |
  +-- PATH resolution + existence check ──> abort with print_error if missing
  |
  +-- open secondary engine(PATH) ──> PRAGMA integrity_check
  |                                ──> get table names (inspector or metadata)
  |                                ──> close secondary engine
  |
  +-- if validation fails: print_error, raise typer.Exit(code=1)
  |
  +-- show file info kv block (path, size, modified)
  +-- confirm_prompt "Replace active database with this file?"
  |     +-- n/Ctrl+C: Exit(0)
  |
  +-- confirm_prompt "A pre-restore backup will be created first..."
  |     +-- n/Ctrl+C: Exit(0)
  |
  +-- create_backup(engine, backups_dir) ──> pre_restore_path
  |
  +-- shutil.copy2(PATH, active_db_path)
  |
  +-- open engine(active_db_path) ──> log_event RESTORE_PERFORMED
  |
  +-- print_success "Database restored."
```

### Recommended Project Structure (no changes needed)

```
src/bensdorp1/commands/
├── status.py      # replace stub — CMD-14
├── refresh.py     # replace stub — CMD-15
└── restore.py     # replace stub — CMD-02

tests/test_commands/
├── test_status.py   # new
├── test_refresh.py  # new
└── test_restore.py  # new
```

### Pattern 1: Multi-Section render_kv_block with Section Headers and Separators

The `config.py` command uses a single `render_kv_block` call. The `status` command needs the same pattern but with labeled sections separated by `---`. Based on the dashboard sketch in CONTEXT.md and the `render_kv_block` implementation in `ui/styles.py`:

```python
# Source: src/bensdorp1/commands/config.py + CONTEXT.md D-04
# Section header + separator printed before each render_kv_block call
console.print(Text("Data status"), markup=False, highlight=False)
console.print(Text("-----------"), markup=False, highlight=False)
render_kv_block(data_section, console)
console.print()
console.print(Text("Backup status"), markup=False, highlight=False)
# ...
```

[VERIFIED: codebase — render_kv_block signature confirmed in ui/styles.py]

### Pattern 2: Inline Health Label Appended to Value String

D-05 specifies health labels inline after the value. Since `render_kv_block` takes `dict[str, str]`, the label is simply appended to the value string before building the dict:

```python
# Source: CONTEXT.md D-05
def _health_label(status: str) -> str:
    """Return '[OK]', '[STALE]', '[WARNING]', or '[FAILED]' string."""
    return f"[{status}]"

last_updated_str = format_date(fetched_date)  # "2026-05-22"
health = _health_label("STALE")  # "[STALE]"
constituents_value = f"{ticker_count} tickers, last updated {last_updated_str}  {health}"
```

Note: The health label text `[OK]` etc. is plain text, NOT Rich markup. Since `render_kv_block` already uses `markup=False`, square brackets are rendered literally without Rich interpreting them as markup tags. [VERIFIED: codebase — render_kv_block uses `markup=False` in ui/styles.py line 166]

### Pattern 3: Pre/Post Cache Snapshot for Refresh Diff

`refresh_constituents(engine)` performs DELETE+INSERT atomically (constituents.py lines 133-137). To compute the diff, snapshot the symbols before calling refresh, then read again after:

```python
# Source: src/bensdorp1/data/constituents.py (_read_cached_constituents, _persist_constituents)
# BEFORE refresh:
before: dict[str, str] = _read_cached_constituents(engine)  # or re-query directly
# ... call refresh_constituents(engine) ...
# AFTER refresh:
after: dict[str, str] = _read_cached_constituents(engine)

added = sorted(set(after.keys()) - set(before.keys()))
removed = sorted(set(before.keys()) - set(after.keys()))
```

`_read_cached_constituents` is a module-private function. The plan should query `constituents_cache` directly using SQLAlchemy to avoid importing a private function. [VERIFIED: codebase — constituents_cache table schema confirmed in schema.py]

### Pattern 4: Secondary SQLAlchemy Engine for Restore Validation (D-17)

```python
# Source: src/bensdorp1/db/engine.py (_build_engine pattern)
from sqlalchemy import text, inspect as sa_inspect
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.url import URL

def _open_validation_engine(path: Path) -> Engine:
    url = URL.create("sqlite+pysqlite", database=str(path))
    return create_engine(url)

# Use, then dispose:
val_engine = _open_validation_engine(backup_path)
try:
    with val_engine.connect() as conn:
        result = conn.execute(text("PRAGMA integrity_check")).scalar()
        # result == 'ok' means clean
        inspector = sa_inspect(val_engine)
        existing_tables = set(inspector.get_table_names())
except Exception:
    # treat as validation failure
finally:
    val_engine.dispose()
```

[VERIFIED: codebase — SQLAlchemy `inspect` and `text` imported in engine.py and schema.py; PRAGMA pattern consistent with sqlite3 docs]

### Pattern 5: Pre-Restore Backup with Custom Filename (D-10)

`create_backup(engine, backups_dir)` in `db/backup.py` creates a timestamped backup with the filename `bensdorp1-{ts}.db`. D-10 requires the pre-restore backup to be named `bensdorp1-pre-restore-{timestamp}.db`. Looking at `backup.py` lines 38-40, the function hardcodes the `bensdorp1-{ts}.db` naming convention.

**Key finding:** `create_backup()` cannot produce the `bensdorp1-pre-restore-{timestamp}.db` name directly — it uses `bensdorp1-{ts}.db` format. Two implementation options for D-10:

**Option A:** Call `create_backup()` which creates `bensdorp1-{ts}.db`, then rename/copy to the pre-restore name. This adds an extra file operation and creates both filenames in the backups dir.

**Option B:** Inline the backup logic directly in `restore.py` using the same `sqlite3.Connection.backup()` API but with the pre-restore filename. This duplicates ~15 lines from `backup.py` but produces exactly the right filename.

**Option C:** Pass the backup through `create_backup()` and accept the standard filename — D-10 says "using the same `create_backup` call pattern" which implies calling the existing function, even if the filename won't have "pre-restore" in it. The pre-restore backup is still in the right directory and identifiable by timestamp correlation to the restore event.

**Recommendation:** Option C — call `create_backup()` as specified in D-10. The CONTEXT.md says "using the same `create_backup` call pattern from `db/backup.py`." The distinction between `bensdorp1-{ts}.db` and `bensdorp1-pre-restore-{ts}.db` is a naming preference from the spec's example (`§10` shows `bensdorp1-pre-restore-2026-05-22-101205.db`), but D-10 defers to the existing `create_backup` call pattern. If exact naming is required, inline the backup using `shutil.copy2(active_db_path, backups_dir / f"bensdorp1-pre-restore-{ts}.db")` — but note that `create_backup` uses the safer `sqlite3.Connection.backup()` API (not file copy), which matters for live database consistency. [ASSUMED — final naming approach needs planner/coder judgment given the tension between the spec example and the call-pattern directive]

**Safe recommendation for planner:** Use `shutil.copy2` for the pre-restore backup (since the DB is not being written to at restore time — the user is replacing it, not running concurrent writes) with the exact `bensdorp1-pre-restore-{ts}.db` filename. This matches both the spec example and D-10's spirit without duplicating the sqlite3 backup logic. [ASSUMED — this is a judgment call; flagged for human review]

### Pattern 6: confirm_prompt Error Handling (from cash.py)

```python
# Source: src/bensdorp1/commands/cash.py lines 107-113
try:
    confirmed = confirm_prompt("Replace active database with this file?", console=console)
except KeyboardInterrupt:
    raise typer.Exit() from None
if not confirmed:
    raise typer.Exit()
```

This pattern must be applied to BOTH confirmation prompts in `restore.py`. [VERIFIED: codebase — cash.py lines 107-113]

### Anti-Patterns to Avoid

- **Importing private functions from other modules:** Do not import `_read_cached_constituents` or `_is_cache_stale` from `constituents.py` — these are module-private. Query `constituents_cache` table directly via SQLAlchemy.
- **Rich markup brackets:** Do not render `[STALE]` via `console.print("[STALE]")` without `markup=False` — Rich will interpret square brackets as markup and silently eat the text. Always use `markup=False, highlight=False` or wrap in `Text(...)`.
- **File copy on live DB:** `shutil.copy2` on the source backup file (PATH) is safe since it is not the live database. The active DB should NOT be read while copying PATH over it; the secondary engine for validation must be disposed before the copy.
- **Logging to the wrong DB:** `restore_performed` audit event must be logged to the RESTORED database (the new active DB), not the pre-restore snapshot. Open a new engine to the active path after the copy completes.
- **Missing engine reset after restore:** After `shutil.copy2` replaces the active DB file, the cached engine singleton still points to the now-replaced file. Since `restore.py` opens a fresh engine at command entry (and the copy writes to the same file path), the cached engine's connection pool will see the new content — no engine reset needed. But if validation opens the backup PATH as a secondary engine, that must be disposed before the copy. [VERIFIED: engine.py uses the file path as the URL; post-copy reads from the same path will see the new content]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQLite integrity check | Custom table scanner | `PRAGMA integrity_check` via `text()` | Built into SQLite; returns 'ok' or error messages |
| Table existence check | Manual SQL | `inspect(engine).get_table_names()` | SQLAlchemy Inspector handles this reliably |
| Backup creation | Custom file copy | `create_backup(engine, backups_dir)` | Already uses sqlite3.Connection.backup() API for consistency |
| Constituent re-fetch | Custom HTTP calls | `refresh_constituents(engine)` | Already handles Wikipedia + Slickcharts + discrepancy logic + audit event |
| Timestamp formatting | strftime | `format_timezone_pair(dt)` from ui.styles | Dual-timezone display with ET + local per rule 6.26 |
| File size formatting | Custom bytes math | Compute MB/KB inline: `size_bytes / (1024*1024)` | Simple enough; no helper exists, but keep it consistent |

**Key insight:** Every non-trivial operation in this phase already has a tested implementation. The commands are integration glue, not new logic.

---

## Common Pitfalls

### Pitfall 1: `[STALE]` / `[OK]` Consumed by Rich Markup Parser

**What goes wrong:** `console.print("[STALE]")` prints nothing — Rich interprets `[STALE]` as an unknown markup tag and drops it silently.
**Why it happens:** Rich's `markup=True` default interprets square brackets as markup tags.
**How to avoid:** All `console.print()` calls in this phase must use `markup=False, highlight=False`, or wrap strings in `Text(...)`. `render_kv_block` already does this for dict values (confirmed in `ui/styles.py` line 166), so health labels appended to value strings are safe.
**Warning signs:** Output shows value without the health label; no error is raised.

### Pitfall 2: Secondary Engine Not Disposed Before File Copy

**What goes wrong:** `shutil.copy2(PATH, active_db_path)` succeeds on Linux/macOS but raises `[WinError 32] The process cannot access the file` on Windows when the secondary validation engine has an open connection to PATH.
**Why it happens:** Windows file locking; SQLite keeps the file open until the engine is disposed.
**How to avoid:** Always call `val_engine.dispose()` in a `finally:` block before proceeding to the file copy (D-17 pattern).
**Warning signs:** Tests pass on CI (ubuntu-latest) but fail on Windows during manual testing.

### Pitfall 3: `fetch_constituents` vs `refresh_constituents` Naming

**What goes wrong:** CONTEXT.md `canonical_refs` section incorrectly references `fetch_constituents(engine)` as the entry point for `refresh.py`. Using this name causes `ImportError: cannot import name 'fetch_constituents'`.
**Why it happens:** The CONTEXT.md was written before/independently of the actual implementation; the codebase uses `refresh_constituents`.
**How to avoid:** Use `from bensdorp1.data import refresh_constituents` — confirmed via `data/__init__.py` line 8 and `constituents.py` line 149.
**Warning signs:** `ModuleNotFoundError` or `ImportError` on first test run.

### Pitfall 4: PRAGMA integrity_check Returns Multi-Row Result on Failure

**What goes wrong:** `conn.execute(text("PRAGMA integrity_check")).scalar()` returns only the first row. On a corrupted DB, `PRAGMA integrity_check` returns multiple rows (one per error), and the first row is NOT necessarily `'ok'`.
**Why it happens:** `.scalar()` returns only the first column of the first row.
**How to avoid:** Use `.scalars().all()` and check that the result is `['ok']` (exactly one row containing the string 'ok'). Or use `.fetchall()` and check `len(result) == 1 and result[0][0] == 'ok'`.
**Warning signs:** A corrupted backup passes validation; multi-error DBs report the first error only.

### Pitfall 5: Backup Directory Status When No Backups Exist

**What goes wrong:** `status.py` scans `~/bensdorp1/backups/` for `.db` files to report the most recent backup and count. If the directory does not exist or is empty (pre-`init` state), `glob()` returns nothing — the code must handle this without crashing.
**Why it happens:** `status` is designed to be runnable even in degraded state.
**How to avoid:** Check `backups_dir.exists()` before globbing; handle empty list explicitly. Show "No backups found" in the Backup status section instead of crashing on `max([])`.
**Warning signs:** `ValueError: max() arg is an empty sequence` on fresh installations.

### Pitfall 6: D-07 Table Count — 7 vs 8 Tables

**What goes wrong:** CONTEXT.md D-07 says "all 7 expected table names" in one sentence but then lists 8 table names: `config`, `scans`, `positions`, `audit_log`, `scan_candidates`, `scan_exit_triggers`, `constituents_cache`, `price_daily`.
**Why it happens:** The spec body says "7 table objects" (schema.py docstring line 4) but D-07 enumeration lists 8.
**How to avoid:** Use the explicit list of 8 names from D-07, not the count. Verify against `schema.py` — all 8 are confirmed there. [VERIFIED: schema.py defines all 8 tables]
**Warning signs:** Validation passes on a backup that is missing one table.

### Pitfall 7: restore BACKUPS_DIR vs DATA_DIR path

**What goes wrong:** `config.py` and `cash.py` both compute `DATA_DIR / "data" / "bensdorp1.db"` for the db path and `DATA_DIR / "backups"` for backup creation. But `config.py` uses `DATA_DIR` directly (not `DATA_DIR / "data" / "bensdorp1.db"`) for display. `restore.py` must correctly resolve BOTH the active db path (for replacement) and the backups dir (for pre-restore backup).
**How to avoid:** Follow the exact pattern from `cash.py`: `db_path = DATA_DIR / "data" / "bensdorp1.db"` for the engine, and `DATA_DIR / "backups"` for `create_backup`.
**Warning signs:** Backup created in wrong directory or active db path computed incorrectly.

---

## Code Examples

### Query: Constituents freshness for status

```python
# Source: src/bensdorp1/db/schema.py (constituents_cache table definition)
from sqlalchemy import func, select
from bensdorp1.db.schema import constituents_cache

with engine.connect() as conn:
    row = conn.execute(
        select(
            func.count(constituents_cache.c.id),
            func.max(constituents_cache.c.fetched_at),
        )
    ).fetchone()

ticker_count: int = row[0] if row else 0
last_fetched: datetime | None = row[1] if row else None
```

### Query: Pending exit triggers count

```python
# Source: src/bensdorp1/db/schema.py (scan_exit_triggers, positions)
from sqlalchemy import select
from bensdorp1.db.schema import positions, scan_exit_triggers

with engine.connect() as conn:
    pending_exits = conn.execute(
        select(func.count(scan_exit_triggers.c.id))
        .join(positions, scan_exit_triggers.c.position_id == positions.c.id)
        .where(positions.c.closed_at == None)  # noqa: E711
    ).scalar()
```

### Backup directory scan for status

```python
# Source: stdlib pathlib; pattern confirmed via backup.py
from pathlib import Path

backups_dir = DATA_DIR / "backups"
if backups_dir.exists():
    db_files = sorted(
        backups_dir.glob("*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    snapshot_count = len(db_files)
    # exclude bensdorp1-latest.db from count, or include — planner's call
    latest_backup_path = db_files[0] if db_files else None
else:
    db_files = []
    latest_backup_path = None
```

### PRAGMA integrity_check (safe multi-row check)

```python
# Source: SQLite docs; SQLAlchemy text()
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(text("PRAGMA integrity_check")).fetchall()
    integrity_ok = (len(rows) == 1 and rows[0][0] == "ok")
```

### Table names check for restore validation

```python
# Source: SQLAlchemy Inspector docs
from sqlalchemy import inspect as sa_inspect

EXPECTED_TABLES = frozenset({
    "config", "scans", "positions", "audit_log",
    "scan_candidates", "scan_exit_triggers",
    "constituents_cache", "price_daily",
})

inspector = sa_inspect(val_engine)
existing_tables = frozenset(inspector.get_table_names())
schema_valid = EXPECTED_TABLES.issubset(existing_tables)
```

### refresh change summary

```python
# Source: src/bensdorp1/data/constituents.py (_read_cached_constituents pattern)
from sqlalchemy import select
from bensdorp1.db.schema import constituents_cache

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

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `typer.confirm()` for prompts | Custom `confirm_prompt()` from ui/prompts.py | No default value; strict y/n; Ctrl+C handling |
| `shutil.copy` for SQLite backup | `sqlite3.Connection.backup()` API | Consistent snapshot even during concurrent reads |
| Direct `metadata.tables.keys()` | `inspect(engine).get_table_names()` | Works without importing metadata from source |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pre-restore backup can use `shutil.copy2` (not `sqlite3.Connection.backup()`) since the active DB is not being written to during restore | Pitfall 5 / Pattern 5 | Minor: restore backup may be inconsistent if another process writes to the DB simultaneously. Single-user tool makes this extremely unlikely. |
| A2 | D-07 intends 8 table names (the explicit list) rather than 7 (the stated count) | Pitfall 6 | Validation could accept an incomplete schema if the wrong count is used |
| A3 | `refresh.py` should read the cache BEFORE calling `refresh_constituents(engine)` to compute the diff, since the function performs atomic DELETE+INSERT | Pattern 3 | If constituents.py internal behavior changes, the diff would be wrong |

---

## Open Questions

1. **Pre-restore backup naming: `create_backup()` vs inline `shutil.copy2`**
   - What we know: `create_backup()` uses `bensdorp1-{ts}.db` naming; spec §10 shows `bensdorp1-pre-restore-{ts}.db`; D-10 says "same `create_backup` call pattern"
   - What's unclear: Whether exact pre-restore naming is required or the call pattern is the priority
   - Recommendation: Planner should implement with inline `shutil.copy2` using the pre-restore filename, since the active DB is not being actively written to during restore (unlike the live backup use case). This matches the spec example exactly.

2. **Backup count in status: include or exclude `bensdorp1-latest.db`?**
   - What we know: `bensdorp1-latest.db` is always in the backups dir; spec D-04/D-06 show "14 files" in the sketch
   - What's unclear: Whether "14 files" counts or excludes `latest.db`
   - Recommendation: Count all `.db` files in the directory; consistent and predictable. Document in code comment.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|---------|
| Python 3.11+ | All | Confirmed (uv run works) | — | — |
| SQLAlchemy | DB queries | Confirmed (in pyproject.toml) | >=2.0.49,<2.1 | — |
| Rich | UI output | Confirmed (in pyproject.toml) | >=14.0 | — |
| shutil (stdlib) | file copy | Always available | — | — |
| sqlite3 (stdlib) | PRAGMA | Always available | — | — |
| pytest / uv | Tests | Confirmed (`uv run pytest` works) | >=8.3 | — |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_commands/test_status.py tests/test_commands/test_refresh.py tests/test_commands/test_restore.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CMD-14 | `status` shows 4-section dashboard with correct data | integration | `uv run pytest tests/test_commands/test_status.py -x` | No — Wave 0 |
| CMD-14 | `status` shows [STALE] when constituents >7 days old | integration | `uv run pytest tests/test_commands/test_status.py::test_status_stale_constituents -x` | No — Wave 0 |
| CMD-14 | `status` shows [OK] when constituents fresh | integration | `uv run pytest tests/test_commands/test_status.py::test_status_ok_constituents -x` | No — Wave 0 |
| CMD-14 | `status` shows [FAILED] when integrity check fails | integration | `uv run pytest tests/test_commands/test_status.py::test_status_integrity_failed -x` | No — Wave 0 |
| CMD-14 | `status` handles no backups without crashing | integration | `uv run pytest tests/test_commands/test_status.py::test_status_no_backups -x` | No — Wave 0 |
| CMD-15 | `refresh` shows no-change message when no diff | integration | `uv run pytest tests/test_commands/test_refresh.py::test_refresh_no_changes -x` | No — Wave 0 |
| CMD-15 | `refresh` shows added/removed table on changes | integration | `uv run pytest tests/test_commands/test_refresh.py::test_refresh_with_changes -x` | No — Wave 0 |
| CMD-02 | `restore` aborts on invalid/missing PATH | integration | `uv run pytest tests/test_commands/test_restore.py::test_restore_invalid_path -x` | No — Wave 0 |
| CMD-02 | `restore` aborts on schema validation failure | integration | `uv run pytest tests/test_commands/test_restore.py::test_restore_schema_invalid -x` | No — Wave 0 |
| CMD-02 | `restore` aborts on 'n' first confirmation | integration | `uv run pytest tests/test_commands/test_restore.py::test_restore_first_confirm_no -x` | No — Wave 0 |
| CMD-02 | `restore` aborts on 'n' second confirmation | integration | `uv run pytest tests/test_commands/test_restore.py::test_restore_second_confirm_no -x` | No — Wave 0 |
| CMD-02 | `restore` creates pre-restore backup + copies + logs event | integration | `uv run pytest tests/test_commands/test_restore.py::test_restore_full_flow -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_commands/test_status.py tests/test_commands/test_refresh.py tests/test_commands/test_restore.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_commands/test_status.py` — covers CMD-14 (does not exist yet)
- [ ] `tests/test_commands/test_refresh.py` — covers CMD-15 (does not exist yet)
- [ ] `tests/test_commands/test_restore.py` — covers CMD-02 (does not exist yet)

---

## Security Domain

> `security_enforcement: true` in `.planning/config.json`; ASVS level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user CLI, no auth |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Single-user CLI |
| V5 Input Validation | Yes | PATH argument validated: existence check + SQLite schema check before any action |
| V6 Cryptography | No | No cryptographic operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via PATH argument | Spoofing / Tampering | `Path(PATH).resolve()` to get absolute path; existence check before opening |
| Malicious SQLite file (crafted to pass schema check) | Tampering | Validation checks schema structure, not data content; acceptable for single-user local tool |
| Rich markup injection via DB values in status output | Tampering | `render_kv_block` already uses `markup=False` — confirmed in `ui/styles.py` line 166 |
| SQL injection via backup file path | Tampering | Path used only in SQLAlchemy URL creation (`URL.create`), not in SQL strings — no injection vector |

**ASVS V5 note:** The PATH argument for `restore` must be validated as a resolvable filesystem path before opening as a SQLAlchemy engine. The validation happens entirely before any state change, meeting ASVS L1 input validation requirements.

---

## Sources

### Primary (HIGH confidence)

- `src/bensdorp1/commands/cash.py` — canonical confirm-then-act + log_event pattern [VERIFIED: codebase]
- `src/bensdorp1/commands/config.py` — canonical multi-section render_kv_block pattern [VERIFIED: codebase]
- `src/bensdorp1/db/backup.py` — create_backup signature and shutil.copy2 pattern [VERIFIED: codebase]
- `src/bensdorp1/db/audit.py` — AuditEventType.RESTORE_PERFORMED, AuditEventType.CONSTITUENTS_UPDATED, log_event signature [VERIFIED: codebase]
- `src/bensdorp1/db/schema.py` — all 8 table objects confirmed [VERIFIED: codebase]
- `src/bensdorp1/data/constituents.py` — `refresh_constituents(engine)` function name and behavior [VERIFIED: codebase]
- `src/bensdorp1/data/__init__.py` — `refresh_constituents` exported, not `fetch_constituents` [VERIFIED: codebase]
- `src/bensdorp1/ui/styles.py` — `render_kv_block` uses `markup=False` on all output [VERIFIED: codebase]
- `src/bensdorp1/ui/prompts.py` — `confirm_prompt` re-raises KeyboardInterrupt [VERIFIED: codebase]
- `.planning/phases/10-system-commands/10-CONTEXT.md` — all locked decisions [VERIFIED: file]

### Secondary (MEDIUM confidence)

- SQLAlchemy `inspect(engine).get_table_names()` — standard SQLAlchemy Inspector API [ASSUMED: training knowledge, consistent with SQLAlchemy 2.0 docs pattern]
- SQLite `PRAGMA integrity_check` returning `['ok']` on clean DB — SQLite documentation [ASSUMED: training knowledge, widely documented]

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in pyproject.toml and existing source
- Architecture: HIGH — all integration points confirmed by reading source files
- Pitfalls: HIGH — most derived from direct codebase inspection (naming mismatch, Windows locking, Rich markup)
- Test patterns: HIGH — confirmed via existing test files in tests/test_commands/

**Research date:** 2026-05-30
**Valid until:** 2026-06-30 (stable codebase, no fast-moving dependencies introduced this phase)
