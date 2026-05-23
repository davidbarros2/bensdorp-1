---
phase: 02-database-and-migrations
plan: "04"
subsystem: db
tags: [audit, enum, sqlite, sqlalchemy-core, state-machine]
dependency_graph:
  requires: [02-02]
  provides: [AuditEventType, log_event]
  affects: [all commands that change state]
tech_stack:
  added: []
  patterns: [StrEnum, parameterized-insert, pytest-parametrize]
key_files:
  created:
    - src/bensdorp1/db/audit.py
    - tests/test_db_audit.py
  modified: []
decisions:
  - "Used `from datetime import UTC` alias (ruff UP017) instead of `timezone.utc` to satisfy ruff at python_version=3.11; RESEARCH.md preference for timezone.utc overridden by active ruff UP rule"
metrics:
  duration: "2m 21s"
  completed: "2026-05-23"
  tasks: 2
  files: 2
---

# Phase 02 Plan 04: Audit Event Log — AuditEventType + log_event() Summary

AuditEventType(StrEnum) with 17 members and log_event() using parameterized SQLAlchemy Core insert into audit_log.

## What Was Built

**`src/bensdorp1/db/audit.py`** — Two exports:
- `AuditEventType(StrEnum)`: 17 members with lowercase snake_case string values matching STATE-04 exactly. Uses `StrEnum` (not `str, Enum`) so `str(member)` returns the value string directly — no `.value` unwrapping needed for SQLite TEXT storage.
- `log_event(engine, event_type, symbol=None, payload=None)`: Inserts one row into `audit_log` via `insert(audit_log).values(...)` parameterized SQL. JSON payload serialized to TEXT. UTC timestamp via `datetime.now(UTC)`.

**`tests/test_db_audit.py`** — 22 test cases (6 test functions):
- `test_all_event_types_insertable` (parametrized x17): every AuditEventType member insertable and queryable by its string value
- `test_log_event_with_symbol`: symbol stored in TEXT column, queryable by value
- `test_log_event_with_payload`: JSON dict round-trips through TEXT column correctly
- `test_log_event_without_symbol_or_payload`: NULL stored as SQL NULL (not "None")
- `test_log_event_inserts_multiple_rows`: audit_log has no unique constraint; two inserts = two rows
- `test_audit_event_type_str_value`: StrEnum behavior confirmed — returns "buy_confirmed" not "AuditEventType.BUY_CONFIRMED"

## Commits

| Task | Description | Hash |
|------|-------------|------|
| 1 | feat(02-04): implement AuditEventType StrEnum and log_event() in audit.py | 1662ab7 |
| 2 | test(02-04): add test_db_audit.py covering all 17 AuditEventType members (STATE-04) | ea48186 |

## Verification

All acceptance criteria met:
- `len(list(AuditEventType)) == 17` — confirmed
- `str(AuditEventType.BUY_CONFIRMED) == "buy_confirmed"` — confirmed
- `class AuditEventType(StrEnum)` — no `(str, Enum)` pattern
- `insert(audit_log).values(...)` — no string interpolation in SQL (T-2-01 mitigated)
- `uv run mypy src/bensdorp1/db/audit.py` — 0 errors
- `uv run ruff check src/bensdorp1/db/audit.py` — 0 errors
- `uv run pytest tests/test_db_audit.py -v` — 22 passed
- `uv run pytest tests/ -x -q` — 73 passed (full suite)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used `from datetime import UTC` instead of `timezone.utc`**
- **Found during:** Task 1 verification (ruff check)
- **Issue:** RESEARCH.md recommended `timezone.utc` as "universal", but ruff UP017 rule (active via `select = ["UP"]` in pyproject.toml) flags `timezone.utc` and requires the `datetime.UTC` alias at `python_version = "3.11"`
- **Fix:** Changed import to `from datetime import UTC, datetime` and used `datetime.now(UTC)` — satisfies both ruff UP017 and mypy strict
- **Files modified:** `src/bensdorp1/db/audit.py`
- **Commit:** 1662ab7

## Threat Mitigations Applied

| Threat ID | Mitigation | Verified |
|-----------|-----------|---------|
| T-2-01 | `insert(audit_log).values(symbol=symbol, payload=...)` — parameterized binding, no string interpolation | Yes — code inspection + tests pass |
| T-2-02 | `AuditEventType(StrEnum)` with 17 exact members; `str(event_type)` always produces known value | Yes — all 17 insertable, str() behavior confirmed |

## Known Stubs

None — audit.py is fully wired. `log_event()` inserts real rows into the real audit_log table. Tests use the `db_engine` fixture which creates a live SQLite file.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. The audit_log table was already defined in schema.py (Wave 1).

## Self-Check: PASSED

- `src/bensdorp1/db/audit.py` — exists, 63 lines
- `tests/test_db_audit.py` — exists, 78 lines
- Commit `1662ab7` — confirmed in git log
- Commit `ea48186` — confirmed in git log
