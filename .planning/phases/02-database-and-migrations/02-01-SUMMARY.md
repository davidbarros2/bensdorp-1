---
phase: 02-database-and-migrations
plan: "01"
subsystem: db
tags: [sqlalchemy, schema, ddl, sqlite, partial-index]
dependency_graph:
  requires: []
  provides:
    - bensdorp1.db.schema.metadata
    - bensdorp1.db.schema.config
    - bensdorp1.db.schema.scans
    - bensdorp1.db.schema.positions
    - bensdorp1.db.schema.audit_log
    - bensdorp1.db.schema.scan_candidates
    - bensdorp1.db.schema.constituents_cache
    - bensdorp1.db.schema.price_daily
  affects: []
tech_stack:
  added: []
  patterns:
    - SQLAlchemy Core 2.0 MetaData singleton with module-level annotation
    - Table() with Column() definitions — all 7 tables in parent-before-child order
    - Partial unique index via sqlite_where with mandatory noqa E711
    - Composite unique index on (symbol, trade_date) for price_daily
    - Non-unique indexes on audit_log for query performance
key_files:
  created:
    - src/bensdorp1/db/__init__.py
    - src/bensdorp1/db/schema.py
  modified: []
decisions:
  - "Table definition order follows parent-before-child (scans before positions/scan_candidates) for readability; SQLAlchemy resolves FK string references at create_all() time so order does not affect correctness"
  - "db/__init__.py uses empty __all__ = [] placeholder for Wave 1; imports from engine.py, backup.py, audit.py added in Waves 2-4 when those modules exist"
  - "schema.py module docstring split to two lines to satisfy E501 (88-char line length); content is unchanged"
metrics:
  duration: "1m 12s"
  completed_date: "2026-05-23"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 02 Plan 01: DB Schema Foundation Summary

**One-liner:** SQLAlchemy Core 2.0 schema with 7 tables, partial unique index on (symbol WHERE closed_at IS NULL), and composite unique index on (symbol, trade_date).

## What Was Built

Created the `db/` subpackage foundation — the single source of truth for all DDL. Every subsequent db/ module (`engine.py`, `backup.py`, `audit.py`) imports from `schema.py`.

### `src/bensdorp1/db/__init__.py`

Minimal Wave-1 package init. Contains a module docstring explaining that imports are added in Waves 2-4, and an empty `__all__ = []` placeholder. Does not import from any db/ submodule (none exist yet).

### `src/bensdorp1/db/schema.py`

Pure DDL module — no stdlib imports, no local imports, no functions. Contains:

- `metadata: MetaData = MetaData()` — shared singleton imported by all other db/ modules
- 7 Table objects in parent-before-child order: `config`, `scans`, `positions`, `audit_log`, `scan_candidates`, `constituents_cache`, `price_daily`
- 6 indexes defined immediately after their parent table:
  - `ix_positions_open_symbol` — partial unique index on `(symbol) WHERE closed_at IS NULL` (enforces STATE-06 at DB level, no application-layer check needed)
  - `ix_audit_log_occurred_at`, `ix_audit_log_symbol`, `ix_audit_log_event_type` — non-unique query indexes
  - `ix_price_daily_symbol_date` — composite unique index on `(symbol, trade_date)`

## Verification Results

All 4 plan verifications passed:

1. `metadata.tables` contains exactly 7 keys: config, scans, positions, audit_log, scan_candidates, constituents_cache, price_daily
2. `ix_positions_open_symbol` registered in `positions.indexes`
3. `uv run ruff check src/bensdorp1/db/` — exits 0, all checks passed
4. `uv run mypy src/bensdorp1/db/` — exits 0, no issues found in 2 source files

## Acceptance Criteria Status

- [x] `src/bensdorp1/db/__init__.py` exists and is importable
- [x] `src/bensdorp1/db/schema.py` exists and is importable
- [x] `metadata.tables` contains exactly 7 keys
- [x] `positions` table has exactly 12 columns (id, symbol, entry_date, entry_close, shares, initial_stop, highest_close, trailing_stop, scan_id, closed_at, exit_price, realized_pnl)
- [x] `audit_log` table has exactly 5 columns (id, event_type, occurred_at, symbol, payload)
- [x] `scans.scan_date` has `unique=True`
- [x] `ix_positions_open_symbol` is registered (partial unique, sqlite_where=closed_at IS NULL)
- [x] `ix_price_daily_symbol_date` is registered (composite unique: symbol, trade_date)
- [x] `ix_audit_log_occurred_at`, `ix_audit_log_symbol`, `ix_audit_log_event_type` are registered
- [x] `ruff check` exits 0 (E711 suppressed with noqa on sqlite_where line)
- [x] `mypy strict` exits 0 on `src/bensdorp1/db/`

## Commits

| Hash | Message |
|------|---------|
| 1226ff3 | feat(02-01): create db/ subpackage with shared MetaData and 7 table definitions |

## Deviations from Plan

None — plan executed exactly as written. One minor fixup during execution: schema.py module docstring was split into two lines to satisfy ruff E501 (88-char line length); the content was unchanged.

## Known Stubs

None. Both files are complete Wave-1 deliverables. `db/__init__.py` intentionally has `__all__ = []` — this is not a stub, it is the correct placeholder until Wave-2+ modules exist.

## Threat Flags

No new threat surface introduced. `schema.py` defines DDL only (no DML, no network access, no file I/O). The partial unique index directly mitigates T-2-01 / STATE-06 at the storage layer.

## Self-Check: PASSED

- `src/bensdorp1/db/__init__.py` — FOUND
- `src/bensdorp1/db/schema.py` — FOUND
- Commit `1226ff3` — FOUND (git log confirmed)
