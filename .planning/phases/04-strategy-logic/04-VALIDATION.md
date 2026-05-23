---
phase: 4
slug: strategy-logic
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-23
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3 + hypothesis 6.152.9 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_strategy/ -x -q` |
| **Full suite command** | `uv run pytest --cov=bensdorp1.strategy --cov-report=term-missing` |
| **Estimated runtime** | ~15 seconds (Hypothesis adds ~5 s with 500 examples per property) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_strategy/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/test_strategy/ --cov=bensdorp1.strategy --cov-report=term-missing`
- **Before `/gsd-verify-work`:** Full suite green + `uv run pytest --cov=bensdorp1 --cov-report=term-missing --cov-fail-under=90` + `uv run mypy src/` + `uv run ruff check src/`
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| screening.py skeleton | Wave 1 | 1 | STRAT-01..04 | — | No user input enters strategy/ | unit | `uv run pytest tests/test_strategy/test_screening.py -x -q` | ❌ W0 | ⬜ pending |
| regime_filter on | Wave 1 | 1 | STRAT-01 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_on -x` | ❌ W0 | ⬜ pending |
| regime_filter off | Wave 1 | 1 | STRAT-01 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_off -x` | ❌ W0 | ⬜ pending |
| regime_filter ValueError | Wave 1 | 1 | STRAT-01 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_insufficient_rows -x` | ❌ W0 | ⬜ pending |
| liquidity_filter top quartile | Wave 1 | 1 | STRAT-02 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_top_quartile -x` | ❌ W0 | ⬜ pending |
| liquidity_filter empty | Wave 1 | 1 | STRAT-02 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_empty -x` | ❌ W0 | ⬜ pending |
| liquidity_filter ValueError | Wave 1 | 1 | STRAT-02 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_insufficient -x` | ❌ W0 | ⬜ pending |
| momentum_filter pass | Wave 1 | 1 | STRAT-03 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_momentum_filter_pass -x` | ❌ W0 | ⬜ pending |
| momentum_filter reject | Wave 1 | 1 | STRAT-03 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_momentum_filter_reject -x` | ❌ W0 | ⬜ pending |
| momentum_filter ValueError | Wave 1 | 1 | STRAT-03 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_momentum_filter_insufficient -x` | ❌ W0 | ⬜ pending |
| rank_candidates ordering | Wave 1 | 1 | STRAT-04 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_ordering -x` | ❌ W0 | ⬜ pending |
| rank_candidates limits to 10 | Wave 1 | 1 | STRAT-04, STRAT-05 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_limits_to_10 -x` | ❌ W0 | ⬜ pending |
| rank_candidates empty | Wave 1 | 1 | STRAT-04 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_empty -x` | ❌ W0 | ⬜ pending |
| rank_candidates ValueError | Wave 1 | 1 | STRAT-04 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_insufficient_rows -x` | ❌ W0 | ⬜ pending |
| positions.py skeleton | Wave 2 | 2 | STRAT-06..09 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py -x -q` | ❌ W0 | ⬜ pending |
| compute_position_size normal | Wave 2 | 2 | STRAT-06 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_position_size_normal -x` | ❌ W0 | ⬜ pending |
| compute_position_size zero (D-06) | Wave 2 | 2 | STRAT-06 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_position_size_zero -x` | ❌ W0 | ⬜ pending |
| compute_initial_stop | Wave 2 | 2 | STRAT-07 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_initial_stop -x` | ❌ W0 | ⬜ pending |
| update_highest_close update | Wave 2 | 2 | STRAT-08 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_update_highest_close_update -x` | ❌ W0 | ⬜ pending |
| update_highest_close no-op | Wave 2 | 2 | STRAT-08 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_update_highest_close_no_update -x` | ❌ W0 | ⬜ pending |
| compute_trailing_stop | Wave 2 | 2 | STRAT-08 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_trailing_stop -x` | ❌ W0 | ⬜ pending |
| compute_effective_stop | Wave 2 | 2 | STRAT-09 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_effective_stop -x` | ❌ W0 | ⬜ pending |
| is_exit_triggered True | Wave 2 | 2 | STRAT-09 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_is_exit_triggered_true -x` | ❌ W0 | ⬜ pending |
| is_exit_triggered False | Wave 2 | 2 | STRAT-09 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_is_exit_triggered_false -x` | ❌ W0 | ⬜ pending |
| Invariant 1: effective_stop >= initial (Hypothesis) | Wave 2 | 2 | TEST-03 | — | N/A | property | `uv run pytest tests/test_strategy/test_positions.py::test_effective_stop_ge_initial -x` | ❌ W0 | ⬜ pending |
| Invariant 2: trailing stop monotonic (Hypothesis) | Wave 2 | 2 | TEST-03 | — | N/A | property | `uv run pytest tests/test_strategy/test_positions.py::test_trailing_stop_monotonic -x` | ❌ W0 | ⬜ pending |
| Invariant 3: rank_candidates <= 10 (Hypothesis) | Wave 1 | 1 | TEST-03, STRAT-05 | — | N/A | property | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_max_ten -x` | ❌ W0 | ⬜ pending |
| Invariant 4: regime_filter False <= sma200 (Hypothesis) | Wave 1 | 1 | TEST-03, STRAT-01 | — | N/A | property | `uv run pytest tests/test_strategy/test_screening.py::test_regime_off_when_close_le_sma200 -x` | ❌ W0 | ⬜ pending |
| strategy/__init__.py re-exports | Wave 3 | 3 | All STRAT | — | N/A | unit | `uv run pytest --co -q` (import check) | ❌ W0 | ⬜ pending |
| strategy-only coverage gate | Wave 3 | 3 | TEST-01 | — | N/A | coverage | `uv run pytest tests/test_strategy/ --cov=bensdorp1.strategy --cov-fail-under=95` | ❌ W0 | ⬜ pending |
| all-modules coverage gate | Wave 3 | 3 | TEST-02 | — | N/A | coverage | `uv run pytest --cov=bensdorp1 --cov-fail-under=90` | ❌ W0 | ⬜ pending |
| mypy strict clean | Wave 3 | 3 | All STRAT | — | N/A | type | `uv run mypy src/bensdorp1/strategy/` | ❌ W0 | ⬜ pending |
| ruff clean | Wave 3 | 3 | All STRAT | — | N/A | lint | `uv run ruff check src/bensdorp1/strategy/` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/bensdorp1/strategy/__init__.py` — package marker + re-exports (mirrors db/ and data/ pattern)
- [ ] `src/bensdorp1/strategy/screening.py` — 4 function stubs (regime_filter, liquidity_filter, momentum_filter, rank_candidates) + Candidate TypedDict
- [ ] `src/bensdorp1/strategy/positions.py` — 6 function stubs (compute_position_size, compute_initial_stop, update_highest_close, compute_trailing_stop, compute_effective_stop, is_exit_triggered)
- [ ] `tests/test_strategy/__init__.py` — empty package marker
- [ ] `tests/test_strategy/test_screening.py` — test stubs for STRAT-01 through STRAT-04 + Hypothesis invariants 3, 4
- [ ] `tests/test_strategy/test_positions.py` — test stubs for STRAT-06 through STRAT-09 + Hypothesis invariants 1, 2

*Existing `pyproject.toml`, `conftest.py`, `tests/` infrastructure is reusable — no new dependencies.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | All strategy/ behaviors are pure math with no I/O | — |

*All phase behaviors have automated verification. No external services, HTTP calls, or filesystem operations in strategy/.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
