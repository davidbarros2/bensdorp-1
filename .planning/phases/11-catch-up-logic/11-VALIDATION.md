---
phase: 11
slug: catch-up-logic
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-30
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.3 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_commands/test_catchup.py -x` |
| **Full suite command** | `uv run pytest --cov=src/bensdorp1 --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_commands/test_catchup.py -x`
- **After every plan wave:** Run `uv run pytest --cov=src/bensdorp1 --cov-report=term-missing`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 0 | STATE-05 | — | N/A | unit | `uv run pytest tests/test_commands/test_catchup.py -x` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 1 | DATA-06 | T-11-01 | ratio <= 0 guard before apply | unit | `uv run pytest tests/test_commands/test_catchup.py::test_apply_splits_math -x` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 1 | DATA-06 | — | N/A | unit | `uv run pytest tests/test_commands/test_catchup.py::test_split_idempotent -x` | ❌ W0 | ⬜ pending |
| 11-03-01 | 03 | 1 | STATE-05 | — | N/A | unit | `uv run pytest tests/test_commands/test_catchup.py::test_catchup_stop_reconstruction -x` | ❌ W0 | ⬜ pending |
| 11-03-02 | 03 | 1 | STATE-05 | — | N/A | unit | `uv run pytest tests/test_commands/test_catchup.py::test_catchup_summary_rendering -x` | ❌ W0 | ⬜ pending |
| 11-04-01 | 04 | 2 | STATE-07 | — | N/A | unit | `uv run pytest tests/test_commands/test_catchup.py::test_delisted_flag_set -x` | ❌ W0 | ⬜ pending |
| 11-04-02 | 04 | 2 | STATE-07 | — | N/A | unit | `uv run pytest tests/test_commands/test_catchup.py::test_delisted_event_not_repeated -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_commands/test_catchup.py` — stubs for STATE-05, DATA-06, STATE-07 (file does not yet exist)

*All test infrastructure — pytest, db_engine fixture, CliRunner — is already in place from prior phases. Only the test file itself is missing.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Catch-up summary renders correctly after real 2-day absence | STATE-05 | Requires live yfinance data and real market calendar | Run `bensdorp1 scan` after skipping one trading day; verify catch-up block appears before regular scan sections |
| Split detection applies correctly for real stock split | DATA-06 | Requires actual split event in yfinance data | Verify split math against broker statement for a known split |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
