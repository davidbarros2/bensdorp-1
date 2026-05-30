# Phase 10: System Commands - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `status`, `refresh`, and `restore` — three system-level utility commands that let the user inspect health diagnostics, force a constituents re-fetch, and safely replace the active database from a backup file. None of these commands modify positions or scan state.

**Specifically delivers:**
- `src/bensdorp1/commands/status.py` — diagnostic dashboard with 4 sections and health markers
- `src/bensdorp1/commands/refresh.py` — forced constituent re-fetch with change summary
- `src/bensdorp1/commands/restore.py` — guarded DB replacement with two confirmations and pre-restore backup
- `tests/test_commands/test_status.py`, `test_refresh.py`, `test_restore.py` — CliRunner integration tests

**Does NOT include:** catch-up logic (Phase 11), split detection (Phase 11), validate command (Phase 12), snapshot tests (Phase 13).

</domain>

<decisions>
## Implementation Decisions

### `status` — health markers and thresholds

- **D-01:** Data section thresholds — constituents freshness: >7 days old = STALE (mirrors the 7-day cache TTL already enforced at scan time), >14 days = WARNING. Last scan freshness: >1 trading day since last scan = STALE (user should scan every trading day).
- **D-02:** Backup section threshold — >3 days since last backup = STALE (state-changing operations create backups; >3 days without one signals gap in usage). Database integrity check result: binary OK / FAILED (PRAGMA integrity_check result).
- **D-03:** Health label rendering — use severity colors from the existing `ui/messages.py` palette: OK = green, STALE = yellow, WARNING = yellow, FAILED = red. Falls back to plain `[OK]` / `[STALE]` / `[WARNING]` / `[FAILED]` text in non-color terminals (Rich handles this automatically via the existing `Console` setup).
- **D-04 (Claude discretion):** `status` dashboard layout — four `render_kv_block` sections with `---` separators and section headings, consistent with the Phase 9 `config` and `detail` pattern. Section order: Data status → Backup status → Database status → Operational status.
- **D-05 (Claude discretion):** Health labels appear inline after the value, space-separated — e.g., `Last updated:  2026-05-22  [STALE]`. Not on a separate line. Not a column in a table.
- **D-06 (Claude discretion):** Operational status section shows: last scan date + health label, open positions count, pending exit triggers count. "Pending exit triggers" = open `scan_exit_triggers` rows where the position's `closed_at` is NULL.

### `restore` — validation and double-confirmation flow

- **D-07:** Schema validation runs first (before any confirmation). Validation = `PRAGMA integrity_check` returns `'ok'` AND all 7 expected table names are present (`config`, `scans`, `positions`, `audit_log`, `scan_candidates`, `scan_exit_triggers`, `constituents_cache`, `price_daily`). If either check fails, abort with a clear error before showing any prompts.
- **D-08:** First confirmation — show file info (resolved absolute path, file size in KB/MB, last modified date), then: "Replace active database with this file?". Uses `confirm_prompt` from `bensdorp1.ui`.
- **D-09:** Second confirmation wording — "A pre-restore backup will be created first. This will overwrite your current database. Are you sure?". Uses `confirm_prompt`.
- **D-10 (Claude discretion):** Pre-restore backup filename: `bensdorp1-pre-restore-{timestamp}.db` in the standard `~/bensdorp1/backups/` directory, using the same `create_backup` call pattern from `db/backup.py`. The restore backup is created _after_ both confirmations, _before_ the file copy. On failure between backup creation and file copy, print an error naming the pre-restore backup location so the user can recover.
- **D-11 (Claude discretion):** `restore_performed` audit event is logged in the NEW (restored) database after the file is swapped in, not in the pre-restore database. Payload: `{"restored_from": str(PATH), "pre_restore_backup": str(backup_path)}`.
- **D-12 (Claude discretion):** File copy uses `shutil.copy2(PATH, active_db_path)` — same as the backup pattern but in reverse. Atomic at the OS level on the same filesystem; acceptable for a single-user local tool.

### `refresh` — change summary format

- **D-13:** On changes found — show a summary line ("Added: N tickers, Removed: N ticker(s).") followed by a table of only the changed tickers (two sections: Added / Removed), using `render_table`. No table on no-change runs.
- **D-14:** On no-change run — show: "Constituents up to date. N tickers, no changes." (plain `print_success` line). No table.
- **D-15 (Claude discretion):** `refresh` calls the existing `fetch_constituents(engine)` from `bensdorp1.data.constituents` — that function is documented as called from `refresh.py`. Shows a spinner (Phase 5 `SpinnerContext`) during the fetch (expected 1–6s for two HTTP requests). Logs `CONSTITUENTS_UPDATED` audit event (already in `AuditEventType`). On discrepancy ≥ 4, also shows the standard discrepancy warning from Phase 3's classification logic.

### Code organization

- **D-16 (Claude discretion):** Single file per command (carried from Phase 8 D-25 / Phase 9 D-09). No engine split. `status.py`, `refresh.py`, `restore.py` — three independent files.
- **D-17 (Claude discretion):** `restore.py` opens the backup file path as a separate SQLAlchemy engine for validation (read-only check), then closes it before doing the file copy. Never modify the backup file.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary specification (authoritative)
- `.planning/Bensdorp_1.md` §5.2.13 — `status` command: 4 diagnostic sections, all values sourced from live state
- `.planning/Bensdorp_1.md` §5.2.14 — `refresh` command: force re-fetch from both sources, change summary output
- `.planning/Bensdorp_1.md` §5.2.15 — `restore` command: PATH arg, two confirmations, validations, pre-restore backup, `restore_performed` audit event in restored state
- `.planning/Bensdorp_1.md` §10 — Backup and recovery spec (naming conventions, pre-restore backup path, `bensdorp1-pre-restore-{timestamp}.db`)
- `.planning/Bensdorp_1.md` §6 — 31 UI/UX style guide rules (all output must comply)
- `.planning/REQUIREMENTS.md` CMD-02, CMD-14, CMD-15

### Existing implementations to read before coding
- `src/bensdorp1/db/schema.py` — all 7 table objects; use for status section data queries AND restore schema validation table-name check
- `src/bensdorp1/db/audit.py` — `AuditEventType.CONSTITUENTS_UPDATED`, `AuditEventType.RESTORE_PERFORMED` (both already exist); `log_event()` call pattern
- `src/bensdorp1/db/backup.py` — `create_backup(engine, backups_dir)` — call for pre-restore backup creation; understand the `shutil.copy2` + latest.db pattern
- `src/bensdorp1/db/engine.py` — `get_engine()`, `run_migrations()`, `BENSDORP1_HOME` resolution for data directory path
- `src/bensdorp1/data/constituents.py` — `fetch_constituents(engine)` is the entry point for `refresh`; understand discrepancy classification and what it returns to build the change summary
- `src/bensdorp1/ui/__init__.py` — `print_error`, `print_info`, `print_success`, `render_kv_block`, `render_table`, `confirm_prompt`
- `src/bensdorp1/ui/progress.py` — `SpinnerContext` for refresh HTTP fetch feedback
- `src/bensdorp1/config.py` — `DATA_DIR`, `BACKUPS_DIR` path resolution
- `src/bensdorp1/commands/cash.py` — canonical pattern for `confirm_prompt` + state-changing operation + `log_event` (reference for `restore` confirmation flow)
- `src/bensdorp1/commands/config.py` — canonical pattern for `render_kv_block` multi-section output (reference for `status` layout)

### Prior phase context
- `.planning/phases/09-consultation-commands/09-CONTEXT.md` — D-09: single file per command; `render_kv_block` usage patterns; `confirm_prompt` abort handling
- `.planning/phases/08-confirmation-commands/08-CONTEXT.md` — D-25/D-26: single file, no engine split; `create_backup` call pattern; `confirm_prompt` re-raise behavior

### Technology
- `CLAUDE.md` §Verified Library Versions — typer >=0.21.1, sqlalchemy >=2.0.49
- `CLAUDE.md` §mypy Strict Mode Configuration

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ui.render_kv_block(data, console)` — use for all 4 `status` sections with section headers and `---` separators
- `ui.render_table(headers, rows, console)` — use for `refresh` change summary table (Added / Removed tickers)
- `ui.print_success(title)` / `ui.print_info(title)` — for `refresh` no-change message and `restore` success
- `ui.print_error(title, actions=[])` — for validation failures in `restore` (invalid file, integrity fail, schema fail)
- `ui.confirm_prompt(prompt, console)` — for `restore` two-confirmation flow; already handles Ctrl+C (re-raises `KeyboardInterrupt`)
- `ui/progress.py` `SpinnerContext` — for `refresh` fetch feedback
- `db.create_backup(engine, backups_dir)` — for `restore` pre-restore backup creation
- `db.log_event(engine, event_type, payload)` — for `CONSTITUENTS_UPDATED` and `RESTORE_PERFORMED` events
- `data.constituents.fetch_constituents(engine)` — existing entry point for `refresh`; Phase 10 does NOT duplicate this logic

### Established Patterns
- `_app.py`: `app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)`. `-> None` on all command functions. `raise typer.Exit()` early exits, `raise typer.Exit(code=1)` error exits.
- Console ownership: `console = Console()` at command entry; pass to all UI calls. Tests use `Console(record=True)`.
- `Text()` wrapping for all strings passed to `console.print()` — markup safety.
- CliRunner from `typer.testing` for all CLI tests — no subprocess. Real SQLite temp file DB seeded per test.
- SQLAlchemy parameterized queries only — no string interpolation.
- `engine.connect()` context manager for DB reads; `conn.commit()` after writes.

### Integration Points
- `commands/status.py` reads live data from: `constituents_cache` (count + max `fetched_at`), `price_daily` (total row count), `scans` (most recent `scan_date`), `positions` (WHERE `closed_at` IS NULL — count), `scan_exit_triggers` (JOIN positions WHERE `closed_at` IS NULL — count), `config` table (not used directly by status), backup directory listing (newest `.db` file mtime + file size), SQLite `PRAGMA integrity_check`.
- `commands/refresh.py` calls `data.constituents.fetch_constituents(engine)` then computes the diff against the updated cache; logs `CONSTITUENTS_UPDATED`.
- `commands/restore.py` opens PATH as a separate read-only engine for validation, then closes it; creates pre-restore backup; copies file; logs `RESTORE_PERFORMED` to the restored DB.

</code_context>

<specifics>
## Specific Ideas

### `status` dashboard sketch
```
Data status
-----------
Constituents:     503 tickers, last updated 2026-05-23  [STALE]
Price cache:      110,660 rows

Backup status
-------------
Last backup:      2026-05-30 09:12 ET  [OK]
Location:         ~/bensdorp1/backups/bensdorp1-latest.db
Snapshots:        14 files

Database status
---------------
File size:        4.2 MB
Integrity check:  OK

Operational status
------------------
Last scan:        2026-05-29  [STALE]
Open positions:   3
Pending exits:    1
```

### `refresh` change output (changes found)
```
Fetching S&P 500 constituents...

Added: 2 tickers, Removed: 1 ticker.

Added            Removed
-----------      --------
VLTO             SIVB
SOLV
```

### `refresh` no-change output
```
Constituents up to date. 503 tickers, no changes.
```

### `restore` flow
```
Validating backup file...

Path:          ~/bensdorp1/backups/bensdorp1-2026-05-28-093012.db
Size:          4.1 MB
Modified:      2026-05-28 09:30 ET

Replace active database with this file? [y/n]: y

A pre-restore backup will be created first. This will overwrite your current database. Are you sure? [y/n]: y

Creating pre-restore backup... done.
Restoring database... done.

Database restored. Run `bensdorp1 status` to verify.
```

</specifics>

<deferred>
## Deferred Ideas

- Catch-up logic and split detection after absence — Phase 11
- Validate command (`bensdorp1 validate DATE`) — Phase 12
- Snapshot tests for `status`, `refresh`, `restore` output — Phase 13
- Progress bar for `refresh` (it falls in the 1-6s spinner range; if a future network environment is slower, Phase 13 hardening can address it)

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-System Commands*
*Context gathered: 2026-05-30*
