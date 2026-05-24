---
phase: 7
slug: scan-command
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-24
approval: phase-7-complete
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
| 7-schema | 01 | 1 | CMD-03 | T-7-01 | scan_exit_triggers uses parameterized inserts | unit | `uv run pytest tests/test_commands/test_scan.py::test_schema_has_exit_triggers_table -x` | ✅ | ✅ green |
| 7-engine-core | 02 | 2 | CMD-03 | T-7-02 | All DB writes use bound params; Rich Text() wraps symbol strings | unit | `uv run pytest tests/test_commands/test_scan.py::test_catchup_stop_updates -x` | ✅ | ✅ green |
| 7-engine-triggers | 02 | 2 | CMD-03 / STRAT-10 | T-7-02 | Stop freeze after trigger; trigger date accurate | unit | `uv run pytest tests/test_commands/test_scan.py::test_stop_freeze_after_trigger tests/test_commands/test_scan.py::test_exit_trigger_on_missed_day -x` | ✅ | ✅ green |
| 7-scan-cmd | 03 | 3 | CMD-03 | T-7-03 | Time gate refuses before 16:30 ET | integration | `uv run pytest tests/test_commands/test_scan.py::test_time_gate -x` | ✅ | ✅ green |
| 7-happy-path | 03 | 3 | CMD-03 / STRAT-01 | — | Full output sections present; no markup injection | integration | `uv run pytest tests/test_commands/test_scan.py::test_happy_path_bull tests/test_commands/test_scan.py::test_bearish_regime -x` | ✅ | ✅ green |
| 7-idempotency | 03 | 3 | CMD-03 | — | Same-day shows raw_output; --force re-fetches | integration | `uv run pytest tests/test_commands/test_scan.py::test_idempotent_same_day tests/test_commands/test_scan.py::test_force_reruns_scan -x` | ✅ | ✅ green |
| 7-non-trading | 03 | 3 | CMD-03 | — | Non-trading day Info message + last raw_output | integration | `uv run pytest tests/test_commands/test_scan.py::test_non_trading_day -x` | ✅ | ✅ green |
| 7-coverage-gate | 04 | 4 | CMD-03 | — | Coverage >= 90% across all modules | suite | `uv run pytest --cov=bensdorp1 --cov-report=term-missing` | ✅ | ✅ green (92%) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_commands/test_scan.py` — 10 test stubs created in Plan 07-01; all implemented in Plan 07-03
- [x] `tests/test_commands/__init__.py` — EXISTS (created in Phase 6)
- [x] `tests/conftest.py` — EXISTS with `db_engine` and `record_console` fixtures

*No additional fixtures needed beyond the existing `db_engine` from conftest.py.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Actual 16:30 ET time gate on real clock | CMD-03 | Requires real system time past 16:30 ET | Run `bensdorp1 scan` after 16:30 ET on a trading day |
| Phase B progress bar renders correctly | CMD-03 | Rich live rendering hard to assert in CliRunner | Run `bensdorp1 scan --force` and observe [1/2]/[2/2] multi-step output |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Full suite: 315 passed, 92% coverage (2026-05-24)
- [x] mypy strict: Success (42 source files, 0 errors)
- [x] ruff check: All checks passed
- [x] ruff format: All files formatted

**Approval:** phase-7-complete
