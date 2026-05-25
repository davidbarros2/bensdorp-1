---
phase: 9
slug: consultation-commands
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_commands/ -x -q` |
| **Full suite command** | `uv run pytest --cov=bensdorp1 --cov-fail-under=90 -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_commands/ -x -q`
- **After every plan wave:** Run `uv run pytest --cov=bensdorp1 --cov-fail-under=90 -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 0 | CMD-04, CMD-05 | — | N/A | unit | `uv run pytest tests/test_commands/test_last.py tests/test_commands/test_history.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 1 | CMD-09 | — | No state mutation | integration | `uv run pytest tests/test_commands/test_last.py -x -q` | ✅ | ⬜ pending |
| 09-02-02 | 02 | 1 | CMD-05 | — | No state mutation | integration | `uv run pytest tests/test_commands/test_history.py -x -q` | ✅ | ⬜ pending |
| 09-03-01 | 03 | 2 | CMD-04 | — | Parameterized queries only | integration | `uv run pytest tests/test_commands/test_portfolio.py -x -q` | ✅ | ⬜ pending |
| 09-04-01 | 04 | 2 | CMD-10 | — | No state mutation | integration | `uv run pytest tests/test_commands/test_detail.py -x -q` | ✅ | ⬜ pending |
| 09-05-01 | 05 | 2 | CMD-11, CMD-12 | — | Parameterized update; backup created | integration | `uv run pytest tests/test_commands/test_cash.py tests/test_commands/test_config.py -x -q` | ✅ | ⬜ pending |
| 09-06-01 | 06 | 2 | CMD-13 | — | AND-filter; no injection | integration | `uv run pytest tests/test_commands/test_audit.py -x -q` | ✅ | ⬜ pending |
| 09-07-01 | 07 | 3 | all above | — | Full suite green | integration | `uv run pytest --cov=bensdorp1 --cov-fail-under=90 -q && uv run mypy src/ && uv run ruff check src/ tests/` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_commands/test_last.py` — stubs for CMD-09 (last shows raw_output; empty state)
- [ ] `tests/test_commands/test_history.py` — stubs for CMD-05 (compact table; --limit; --since; empty state)
- [ ] `tests/test_commands/test_portfolio.py` — stubs for CMD-04 (10-col table; empty state; no-price fallback)
- [ ] `tests/test_commands/test_detail.py` — stubs for CMD-10 (per-day stop history; unknown symbol error)
- [ ] `tests/test_commands/test_cash.py` — stubs for CMD-11 (show cash; update cash with confirm; amount=0 valid)
- [ ] `tests/test_commands/test_config.py` — stubs for CMD-12 (kv output with version)
- [ ] `tests/test_commands/test_audit.py` — stubs for CMD-13 (all 5 filter flags; most-recent-first; empty state)

*Note: test files may already exist from Phase 1 stub scaffolding — check before creating.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Terminal width wrapping at 120 chars | UI style guide | Requires real terminal | `bensdorp1 portfolio` in 120-char terminal; verify no wrapping |
| Dual-timezone display (ET + Lisbon) | UI-06 | Timezone display needs real clock | `bensdorp1 audit` — verify both ET and Lisbon times shown |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
