---
phase: 10
slug: system-commands
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-30
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_commands/test_status.py tests/test_commands/test_refresh.py tests/test_commands/test_restore.py -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_commands/test_status.py tests/test_commands/test_refresh.py tests/test_commands/test_restore.py -x -q`
- **After every plan wave:** Run `uv run pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | CMD-14 | — | N/A | integration | `uv run pytest tests/test_commands/test_status.py -x -q` | ✅ | ⬜ pending |
| 10-01-02 | 01 | 1 | CMD-14 | — | N/A | integration | `uv run pytest tests/test_commands/test_status.py -x -q` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 1 | CMD-15 | — | N/A | integration | `uv run pytest tests/test_commands/test_refresh.py -x -q` | ✅ | ⬜ pending |
| 10-02-02 | 02 | 1 | CMD-15 | — | N/A | integration | `uv run pytest tests/test_commands/test_refresh.py -x -q` | ✅ | ⬜ pending |
| 10-03-01 | 03 | 1 | CMD-02 | — | Input path validated before any confirmation or DB access | integration | `uv run pytest tests/test_commands/test_restore.py -x -q` | ✅ | ⬜ pending |
| 10-03-02 | 03 | 1 | CMD-02 | — | Double confirmation required; no bypass | integration | `uv run pytest tests/test_commands/test_restore.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing infrastructure covers all phase requirements.

*Test files `tests/test_commands/test_status.py`, `tests/test_commands/test_refresh.py`, `tests/test_commands/test_restore.py` will be created as part of command implementation plans. No separate Wave 0 stub step needed — each command plan includes its own test file creation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `status` output freshness (STALE thresholds) depends on actual system clock vs. last fetched_at | CMD-02 | Time-dependent threshold logic requires real elapsed time | Seed DB with `fetched_at` = 8 days ago; run `bensdorp1 status`; confirm `[STALE]` shown next to Constituents |
| `restore` on Windows file locking | CMD-15 | SQLite file lock during restore not easily simulated | Run `bensdorp1 restore path/to/backup.db` with active engine and verify error or success |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
