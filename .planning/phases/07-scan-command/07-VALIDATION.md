---
phase: 7
slug: scan-command
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-05-24
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.3 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_commands/test_scan.py -x` |
| **Full suite command** | `uv run pytest --cov=bensdorp1 --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_commands/test_scan.py -x`
- **After every plan wave:** Run `uv run pytest --cov=bensdorp1 --cov-report=term-missing`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-schema | TBD | 1 | CMD-03 | T-7-01 | scan_exit_triggers uses parameterized inserts | unit | `uv run pytest tests/test_commands/test_scan.py::test_schema_has_exit_triggers_table -x` | ❌ W0 | ⬜ pending |
| 7-engine-core | TBD | 2 | CMD-03 | T-7-02 | All DB writes use bound params; Rich Text() wraps symbol strings | unit | `uv run pytest tests/test_commands/test_scan.py::test_catchup_stop_updates -x` | ❌ W0 | ⬜ pending |
| 7-engine-triggers | TBD | 2 | CMD-03 / STRAT-10 | T-7-02 | Stop freeze after trigger; trigger date accurate | unit | `uv run pytest tests/test_commands/test_scan.py::test_stop_freeze_after_trigger tests/test_commands/test_scan.py::test_exit_trigger_on_missed_day -x` | ❌ W0 | ⬜ pending |
| 7-scan-cmd | TBD | 3 | CMD-03 | T-7-03 | Time gate refuses before 16:30 ET | integration | `uv run pytest tests/test_commands/test_scan.py::test_time_gate -x` | ❌ W0 | ⬜ pending |
| 7-happy-path | TBD | 3 | CMD-03 / STRAT-01 | — | Full output sections present; no markup injection | integration | `uv run pytest tests/test_commands/test_scan.py::test_happy_path_bull tests/test_commands/test_scan.py::test_bearish_regime -x` | ❌ W0 | ⬜ pending |
| 7-idempotency | TBD | 3 | CMD-03 | — | Same-day shows raw_output; --force re-fetches | integration | `uv run pytest tests/test_commands/test_scan.py::test_idempotent_same_day tests/test_commands/test_scan.py::test_force_reruns_scan -x` | ❌ W0 | ⬜ pending |
| 7-non-trading | TBD | 3 | CMD-03 | — | Non-trading day Info message + last raw_output | integration | `uv run pytest tests/test_commands/test_scan.py::test_non_trading_day -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_commands/test_scan.py` — stubs for all scan test scenarios (file does not yet exist)
- [ ] `tests/test_commands/__init__.py` — EXISTS (created in Phase 6)
- [ ] `tests/conftest.py` — EXISTS with `db_engine` and `record_console` fixtures

*No additional fixtures needed beyond the existing `db_engine` from conftest.py.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Actual 16:30 ET time gate on real clock | CMD-03 | Requires real system time past 16:30 ET | Run `bensdorp1 scan` after 16:30 ET on a trading day |
| Phase B progress bar renders correctly | CMD-03 | Rich live rendering hard to assert in CliRunner | Run `bensdorp1 scan --force` and observe [1/2]/[2/2] multi-step output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
