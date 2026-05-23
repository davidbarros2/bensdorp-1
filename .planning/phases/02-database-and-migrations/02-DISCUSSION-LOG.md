# Phase 2: Database and Migrations - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 2-database-and-migrations
**Areas discussed:** Migration mechanism, Audit log payload design, Full schema scope, db/ module structure

---

## Migration Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| SQLAlchemy create_all() | MetaData.create_all(checkfirst=True) — zero extra dependency, idempotent, schema defined in Python using Table/Column objects | ✓ |
| Alembic | Proper migration tool with version history and upgrade/downgrade scripts. Adds alembic dep + alembic/ directory | |
| Raw SQL file | A .sql file with CREATE TABLE IF NOT EXISTS statements, executed at startup | |

**User's choice:** SQLAlchemy create_all() (Recommended)
**Notes:** None beyond selection.

### When does create_all() run?

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit only in `init` | create_all() called once during `bensdorp1 init`. Other commands fail fast if DB missing | ✓ |
| Auto on every startup | Every command calls ensure_db() which runs create_all() if tables are missing | |

**User's choice:** Explicit only in `init` (Recommended)
**Notes:** None beyond selection.

---

## Audit Log Payload Design

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: shared columns + JSON payload | id, event_type, occurred_at, symbol (nullable), payload TEXT (JSON). SQL filters use columns; event-specific data in payload | ✓ |
| Full flat columns | One table with every possible field as a column (~30+ columns, mostly NULL) | |
| Pure JSON — one blob column | Only id, event_type, occurred_at as columns; everything else in JSON | |

**User's choice:** Hybrid: shared columns + JSON payload (Recommended)
**Notes:** None beyond selection.

### Event type representation

| Option | Description | Selected |
|--------|-------------|----------|
| Python Enum | class AuditEventType(str, Enum) — mypy exhaustiveness checking, type-safe at call sites | ✓ |
| String constants module | MODULE_CONSTANTS = {'SCAN_PERFORMED': 'scan_performed', ...} | |
| Pydantic models per event type | One Pydantic model per event type that validates its own payload fields | |

**User's choice:** Python Enum (Recommended)
**Notes:** None beyond selection.

---

## Full Schema Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full schema now — all 7 tables | Phase 2 defines config, positions, audit_log, scans, scan_candidates, constituents_cache, price_daily with complete columns and indexes | ✓ |
| State tables only now | Phase 2 defines only positions, audit_log, and config; later phases add their own tables | |

**User's choice:** Full schema now — all 7 tables (Recommended)
**Notes:** None beyond selection.

### Closed positions tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Single positions table with nullable closed_at | closed_at IS NULL = open; NOT NULL = closed. Partial unique index enforces STATE-06 | ✓ |
| Separate open_positions and closed_positions tables | Cleaner reads but requires row move on close; UNION queries for audit | |

**User's choice:** Single positions table with nullable closed_at (Recommended)
**Notes:** None beyond selection.

---

## db/ Module Structure

| Option | Description | Selected |
|--------|-------------|----------|
| db/ subpackage — 4–5 focused modules | schema.py, engine.py, backup.py, audit.py. Each module has one responsibility | ✓ |
| Single db.py file | Everything in one file: schema, engine, backup, audit | |

**User's choice:** db/ subpackage — 4–5 focused modules (Recommended)
**Notes:** None beyond selection.

### Connection/engine management

| Option | Description | Selected |
|--------|-------------|----------|
| get_engine() with lazy caching | db/engine.py has get_engine(path: Path \| None = None) — resolves BENSDORP1_HOME on first call, caches engine. Tests pass a temp path | ✓ |
| Module-level singleton at import | engine = create_engine(resolve_db_path()) at module level — runs at import time, harder to test | |

**User's choice:** get_engine() with lazy caching (Recommended)
**Notes:** None beyond selection.

---

## Claude's Discretion

None — user made explicit choices for all presented decisions.

## Deferred Ideas

None — discussion stayed within phase scope.
