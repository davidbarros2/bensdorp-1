---
phase: 8
slug: confirmation-commands
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_commands/test_buy.py tests/test_commands/test_sell.py tests/test_commands/test_fix.py -x --tb=short` |
| **Full suite command** | `uv run pytest --cov=bensdorp1 --cov-report=term-missing` |
| **Estimated runtime** | ~15 seconds (quick), ~45 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_commands/ -x --tb=short`
- **After every plan wave:** Run `uv run pytest --cov=bensdorp1 --cov-report=term-missing`
- **Before `/gsd-verify-work`:** Full suite must be green + mypy strict + ruff
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | CMD-06 | T-08-01 | SQL injection via symbol rejected by parameterized query | integration | `uv run pytest tests/test_commands/test_buy.py -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 0 | CMD-07 | T-08-01 | SQL injection via reason rejected | integration | `uv run pytest tests/test_commands/test_sell.py -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 0 | CMD-08 | T-08-01 | No DB write on no-changes in fix | integration | `uv run pytest tests/test_commands/test_fix.py -x` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 1 | CMD-06 | T-08-02 | Constituent validation blocks unknown symbol | integration | `uv run pytest tests/test_commands/test_buy.py::test_invalid_constituent -x` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 1 | CMD-06 | — | Duplicate open position rejected before DB insert | integration | `uv run pytest tests/test_commands/test_buy.py::test_duplicate_open_position -x` | ❌ W0 | ⬜ pending |
| 08-02-03 | 02 | 1 | CMD-06 | — | Off-signal warning shown; abort on `n` | integration | `uv run pytest tests/test_commands/test_buy.py::test_off_signal_abort -x` | ❌ W0 | ⬜ pending |
| 08-02-04 | 02 | 1 | CMD-06 | — | On-signal happy path creates open position | integration | `uv run pytest tests/test_commands/test_buy.py::test_happy_path_on_signal -x` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 2 | CMD-07 | T-08-02 | No exit trigger → exit code 1, no DB write | integration | `uv run pytest tests/test_commands/test_sell.py::test_no_exit_trigger -x` | ❌ W0 | ⬜ pending |
| 08-03-02 | 03 | 2 | CMD-07 | — | Normal sell closes position, P&L computed | integration | `uv run pytest tests/test_commands/test_sell.py::test_happy_path_normal -x` | ❌ W0 | ⬜ pending |
| 08-03-03 | 03 | 2 | CMD-07 | — | `--manual REASON` records manual sell event | integration | `uv run pytest tests/test_commands/test_sell.py::test_manual_sell -x` | ❌ W0 | ⬜ pending |
| 08-04-01 | 04 | 3 | CMD-08 | T-08-03 | No transaction found → exit code 1 | integration | `uv run pytest tests/test_commands/test_fix.py::test_no_transaction -x` | ❌ W0 | ⬜ pending |
| 08-04-02 | 04 | 3 | CMD-08 | — | No-changes → Info message, exit 0, no DB write | integration | `uv run pytest tests/test_commands/test_fix.py::test_no_changes -x` | ❌ W0 | ⬜ pending |
| 08-04-03 | 04 | 3 | CMD-08 | — | Price change updates initial_stop in DB | integration | `uv run pytest tests/test_commands/test_fix.py::test_price_change_updates_stop -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_commands/test_buy.py` — stubs for CMD-06 scenarios
- [ ] `tests/test_commands/test_sell.py` — stubs for CMD-07 scenarios
- [ ] `tests/test_commands/test_fix.py` — stubs for CMD-08 scenarios

*Existing test infrastructure (`conftest.py`, `db_engine` fixture) is sufficient — no new fixtures or framework installs needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Ctrl+C during buy confirmation aborts cleanly | UI-07 | CliRunner does not propagate real keyboard signals | Run `bensdorp1 buy NVDA 432.50 23`, press Ctrl+C at prompt; verify "Operation aborted." and exit 0 |
| Ctrl+C during fix field input aborts cleanly | UI-07 | CliRunner does not propagate real keyboard signals | Run `bensdorp1 fix AAPL`, press Ctrl+C at field prompt; verify "Operation aborted." and no DB write |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
