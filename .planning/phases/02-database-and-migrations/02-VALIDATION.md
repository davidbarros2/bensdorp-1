---
phase: 2
slug: database-and-migrations
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-23
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — already configured |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src/` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | STATE-01 | — | N/A | unit | `uv run pytest tests/test_db_schema.py::test_all_tables_created -x` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | STATE-01 | — | N/A | unit | `uv run pytest tests/test_db_schema.py::test_create_all_idempotent -x` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 1 | STATE-01 | — | N/A | unit | `uv run pytest tests/test_db_engine.py::test_bensdorp1_home_override -x` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 2 | STATE-02 | T-2-01 | backup() uses sqlite3 API not file copy | unit | `uv run pytest tests/test_db_backup.py::test_backup_creates_valid_db -x` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 2 | STATE-03 | — | N/A | unit | `uv run pytest tests/test_db_backup.py::test_backup_timestamped_filename -x` | ❌ W0 | ⬜ pending |
| 2-02-03 | 02 | 2 | STATE-03 | — | N/A | unit | `uv run pytest tests/test_db_backup.py::test_latest_db_updated -x` | ❌ W0 | ⬜ pending |
| 2-03-01 | 03 | 3 | STATE-04 | T-2-02 | StrEnum values prevent injection; parameterized inserts | unit | `uv run pytest tests/test_db_audit.py::test_all_event_types_insertable -x` | ❌ W0 | ⬜ pending |
| 2-03-02 | 03 | 3 | STATE-04 | — | N/A | unit | `uv run pytest tests/test_db_audit.py::test_log_event_with_payload -x` | ❌ W0 | ⬜ pending |
| 2-04-01 | 04 | 4 | STATE-06 | — | N/A | unit | `uv run pytest tests/test_db_positions.py::test_duplicate_open_position_rejected -x` | ❌ W0 | ⬜ pending |
| 2-04-02 | 04 | 4 | STATE-06 | — | N/A | unit | `uv run pytest tests/test_db_positions.py::test_sequential_positions_allowed -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — `db_engine` fixture: tmp_path file-based SQLite, create_all, engine reset, engine.dispose() teardown (CRITICAL on Windows to release file handles)
- [ ] `tests/test_db_schema.py` — stubs for STATE-01: all 7 tables created, idempotent create_all, partial index present
- [ ] `tests/test_db_engine.py` — stubs for STATE-01: BENSDORP1_HOME override, lazy caching, path override
- [ ] `tests/test_db_backup.py` — stubs for STATE-02/STATE-03: backup API used, timestamped filename, latest.db updated
- [ ] `tests/test_db_audit.py` — stubs for STATE-04: all 17 event types insertable, log_event() stores correctly
- [ ] `tests/test_db_positions.py` — stubs for STATE-06: IntegrityError on duplicate open, sequential positions succeed

*(Existing `tests/test_cli.py` and `tests/test_repo.py` from Phase 1 are unaffected — all pass.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| All behaviors have automated verification | — | — | — |

*All phase behaviors have automated verification.*

---

## Threat Model

| ID | Threat | STRIDE | Mitigation | ASVS |
|----|--------|--------|-----------|------|
| T-2-01 | SQL injection via symbol or payload fields | Tampering | SQLAlchemy Core parameterized queries via `insert().values(...)` — never string interpolation | V5.3 |
| T-2-02 | Audit event type bypass (arbitrary strings in event_type) | Tampering | `StrEnum` with exhaustive 17 members; only valid values compile | V5.2 |
| T-2-03 | Backup corruption on live DB via file copy | Tampering | `sqlite3.Connection.backup()` is transactionally safe; `shutil.copy` is not — correct API mandatory | — |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
