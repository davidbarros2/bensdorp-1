# Phase 2: Database and Migrations - Context

**Gathered:** 2026-05-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Define the complete SQLite schema, run migrations idempotently via SQLAlchemy, and implement all state-management primitives (backup, audit log) — all in isolation before any command uses them. Phase 3 (data sources) and beyond build on this foundation.

This phase delivers: the full `db/` subpackage (`schema.py`, `engine.py`, `backup.py`, `audit.py`), all 7 tables with their columns and indexes, and the `AuditEventType` enum covering all 17 event types.

No business logic, no data fetching, no command implementations. Commands remain stubs; the `init` command (Phase 6) is what calls `create_all()` in production.

</domain>

<decisions>
## Implementation Decisions

### Migration Mechanism
- **D-01:** Use `MetaData.create_all(checkfirst=True)` — no Alembic, no raw SQL files. SQLAlchemy `CREATE TABLE IF NOT EXISTS` for every table. Idempotent by construction. No extra dependency.
- **D-02:** `create_all()` is called **only during `bensdorp1 init`** (Phase 6 implements the actual call). Every other command fails fast if the DB is missing with a clear error: `"Database not found — run bensdorp1 init first."` No auto-creation on startup.

### Audit Log Design
- **D-03:** Hybrid schema — `audit_log` table has shared SQL columns (`id`, `event_type`, `occurred_at`, `symbol` (nullable TEXT), `payload TEXT` as JSON) for SQL-filterable fields + JSON payload for event-specific data. The `audit` command's `--symbol`, `--since`, `--until`, `--type`, `--limit` filters operate on SQL columns. Event-specific details are deserialized from `payload` at display time.
- **D-04:** The 17 event types are represented as `class AuditEventType(str, Enum)` in `db/audit.py`. `str` mixin allows direct use as SQLite TEXT values without `.value` unwrapping. mypy catches typos at call sites; exhaustiveness checking works in match/case.

### Schema Scope
- **D-05:** Phase 2 defines **all 7 tables** with complete columns and indexes: `config`, `positions`, `audit_log`, `scans`, `scan_candidates`, `constituents_cache`, `price_daily`. Later phases add query functions — they do NOT alter the schema. No `ALTER TABLE` surprises at integration time.
- **D-06:** `positions` table uses a **single table with nullable `closed_at`**. `closed_at IS NULL` = open; `NOT NULL` = closed. STATE-06 (no simultaneous same-symbol positions) is enforced by a **partial unique index** on `(symbol) WHERE closed_at IS NULL`. SQLite supports partial indexes — no application-layer check needed.

### db/ Module Structure
- **D-07:** `src/bensdorp1/db/` subpackage with these modules:
  - `__init__.py` — re-exports `get_engine`, `run_migrations` for command use
  - `schema.py` — all `Table` / `Column` definitions + shared `metadata = MetaData()` object
  - `engine.py` — `get_engine(path: Path | None = None)` function with lazy caching
  - `backup.py` — `sqlite3.Connection.backup()` wrapper + timestamped snapshot logic
  - `audit.py` — `AuditEventType` enum + `log_event()` function
- **D-08:** `get_engine(path: Path | None = None)` in `engine.py` — resolves `BENSDORP1_HOME` on first call, creates the SQLAlchemy engine, caches it in a module-level variable, returns cached engine on subsequent calls. Tests pass an explicit `path` to a temp directory — no `BENSDORP1_HOME` monkeypatching required.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specifications
- `.planning/ROADMAP.md` §Phase 2 — Goal, success criteria, and requirements list for this phase
- `.planning/REQUIREMENTS.md` — STATE-01, STATE-02, STATE-03, STATE-04, STATE-06 (the 5 requirements in scope for Phase 2)
- `.planning/PROJECT.md` — Key Decisions table (SQLAlchemy Core chosen over ORM; see rationale)

### Technology guidance (in CLAUDE.md)
- `CLAUDE.md` §Verified Library Versions — pinned versions: sqlalchemy `>=2.0.49,<2.1`, pydantic `>=2.13.4`
- `CLAUDE.md` §pyproject.toml Structure for uv — PEP 735 dependency groups (no [tool.uv.dev-dependencies])
- `CLAUDE.md` §mypy Strict Mode Configuration — strict mode flags; SQLAlchemy 2.0 ships inline types, no override needed
- `CLAUDE.md` §Ruff Configuration — TC rules and SQLAlchemy Core: `SQLAlchemy Core Table/Column are evaluated at import time` — must be excluded from TC rules; declare as runtime-evaluated
- `CLAUDE.md` §Alternatives Considered and Rejected — SQLAlchemy Core vs ORM vs raw sqlite3 rationale

### Phase 1 context (established patterns)
- `.planning/phases/01-project-skeleton-and-tooling/01-CONTEXT.md` — src/ layout decisions (D-01, D-02, D-03), pathlib.Path-throughout rule (D-03 specifics), CI matrix

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/bensdorp1/_app.py` — Typer app singleton. All command modules import from here; `db/` modules must NOT import `_app.py` (no circular dependency — `db/` is a pure data layer).
- `src/bensdorp1/commands/` — all 17 stubs exist. Phase 2 does not modify any command module; it only creates the `db/` subpackage.

### Established Patterns
- **`src/` layout** — new `db/` subpackage lives at `src/bensdorp1/db/`. No flat modules at repo root.
- **`pathlib.Path` throughout** — BENSDORP1_HOME resolution, DB file path, backup directory must all use `Path`, never string concatenation. User runs on Windows.
- **`-> None` on every function** — mypy strict requires explicit return types on all functions.
- **PEP 735 dependency groups** — if SQLAlchemy is not already a runtime dep, add it to `[project.dependencies]` (not dev group).

### Integration Points
- `src/bensdorp1/commands/init.py` (stub) — Phase 6 will call `db.run_migrations()` from this stub. Phase 2 only defines `run_migrations()`, not calls it.
- All state-changing commands (`buy`, `sell`, `fix`, `cash`) — will call `db.get_engine()` and `db.backup.create_backup()` after every write. Phase 2 implements those primitives; commands call them in later phases.

</code_context>

<specifics>
## Specific Ideas

- Partial unique index for STATE-06: `CREATE UNIQUE INDEX ix_positions_open_symbol ON positions (symbol) WHERE closed_at IS NULL` — SQLite supports this natively. SQLAlchemy Core can define it via `Index('ix_positions_open_symbol', positions.c.symbol, sqlite_where=(positions.c.closed_at == None))`.
- `AuditEventType` enum values must match the exact 17 strings from REQUIREMENTS.md STATE-04 (`system_initialized`, `scan_performed`, `buy_confirmed`, `sell_confirmed`, `sell_manual`, `transaction_corrected`, `cash_updated`, `constituents_updated`, `constituents_discrepancy`, `split_applied`, `position_delisted_from_index`, `regime_change_bull_to_bear`, `regime_change_bear_to_bull`, `data_fetch_failed`, `catch_up_performed`, `restore_performed`, `position_closed_manual`).
- `backup.py` must use `sqlite3.Connection.backup()` API (STATE-02 specifies this explicitly — not `shutil.copy`).
- Backup file naming: `bensdorp1-{timestamp}.db` in `~/bensdorp1/backups/`; symlink/copy `bensdorp1-latest.db` to point to the newest (STATE-03).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-Database and Migrations*
*Context gathered: 2026-05-23*
