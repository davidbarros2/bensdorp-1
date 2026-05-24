---
phase: 6
slug: first-run-init-command
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-24
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_commands/ -x` |
| **Full suite command** | `uv run pytest --cov=bensdorp1 --cov-report=term-missing` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_commands/ -x`
- **After every plan wave:** Run `uv run pytest --cov=bensdorp1 --cov-report=term-missing`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | CMD-01 | T-markup-injection | `format_price(cash)` + `Text()` block markup injection | integration | `uv run pytest tests/test_commands/test_init.py -x && uv run mypy src/bensdorp1/commands/init.py --strict && uv run ruff check src/bensdorp1/commands/init.py && uv run ruff format --check src/bensdorp1/commands/init.py` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | CMD-01 | — | N/A | unit | `uv run pytest tests/test_cli.py -x` | ✅ | ⬜ pending |
| 06-02-01 | 02 | 2 | CMD-01 | — | N/A | unit | `uv run pytest tests/test_commands/ -x` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | CMD-01 | — | guard, cash validation, abort | unit | `uv run pytest tests/test_commands/test_init.py -v && uv run pytest --cov=bensdorp1 --cov-report=term-missing && uv run mypy src/ --strict && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_commands/__init__.py` — empty file (matches `tests/test_ui/__init__.py` pattern)
- [ ] `tests/test_commands/test_init.py` — covers 4 scenarios: guard fires when DB exists, happy path, cash validation, Ctrl+C abort

*Existing infrastructure (`tests/conftest.py` with `db_engine` and `record_console` fixtures) covers all phase requirements — no new conftest needed.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
