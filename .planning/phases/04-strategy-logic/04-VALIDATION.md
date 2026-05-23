---
phase: 4
slug: strategy-logic
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-23
audited: 2026-05-23
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
| **Actual runtime** | ~8-9 seconds |

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
| screening.py skeleton | Wave 1 | 1 | STRAT-01..04 | — | No user input enters strategy/ | unit | `uv run pytest tests/test_strategy/test_screening.py -x -q` | ✅ | ✅ green |
| regime_filter on | Wave 1 | 1 | STRAT-01 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_on -x` | ✅ | ✅ green |
| regime_filter off | Wave 1 | 1 | STRAT-01 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_off -x` | ✅ | ✅ green |
| regime_filter ValueError | Wave 1 | 1 | STRAT-01 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_insufficient_rows -x` | ✅ | ✅ green |
| liquidity_filter top quartile | Wave 1 | 1 | STRAT-02 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_top_quartile -x` | ✅ | ✅ green |
| liquidity_filter empty | Wave 1 | 1 | STRAT-02 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_empty -x` | ✅ | ✅ green |
| liquidity_filter ValueError | Wave 1 | 1 | STRAT-02 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_insufficient -x` | ✅ | ✅ green |
| momentum_filter pass | Wave 1 | 1 | STRAT-03 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_momentum_filter_pass -x` | ✅ | ✅ green |
| momentum_filter reject | Wave 1 | 1 | STRAT-03 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_momentum_filter_reject -x` | ✅ | ✅ green |
| momentum_filter ValueError | Wave 1 | 1 | STRAT-03 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_momentum_filter_insufficient -x` | ✅ | ✅ green |
| rank_candidates ordering | Wave 1 | 1 | STRAT-04 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_ordering -x` | ✅ | ✅ green |
| rank_candidates limits to 10 | Wave 1 | 1 | STRAT-04, STRAT-05 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_limits_to_10 -x` | ✅ | ✅ green |
| rank_candidates empty | Wave 1 | 1 | STRAT-04 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_empty -x` | ✅ | ✅ green |
| rank_candidates ValueError | Wave 1 | 1 | STRAT-04 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_insufficient_rows -x` | ✅ | ✅ green |
| positions.py skeleton | Wave 2 | 2 | STRAT-06..09 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py -x -q` | ✅ | ✅ green |
| compute_position_size normal | Wave 2 | 2 | STRAT-06 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_position_size_normal -x` | ✅ | ✅ green |
| compute_position_size zero (D-06) | Wave 2 | 2 | STRAT-06 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_position_size_zero -x` | ✅ | ✅ green |
| compute_initial_stop | Wave 2 | 2 | STRAT-07 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_initial_stop -x` | ✅ | ✅ green |
| update_highest_close update | Wave 2 | 2 | STRAT-08 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_update_highest_close_update -x` | ✅ | ✅ green |
| update_highest_close no-op | Wave 2 | 2 | STRAT-08 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_update_highest_close_no_update -x` | ✅ | ✅ green |
| compute_trailing_stop | Wave 2 | 2 | STRAT-08 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_trailing_stop -x` | ✅ | ✅ green |
| compute_effective_stop | Wave 2 | 2 | STRAT-09 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_effective_stop_initial_wins -x` | ✅ | ✅ green |
| is_exit_triggered True | Wave 2 | 2 | STRAT-09 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_is_exit_triggered_true -x` | ✅ | ✅ green |
| is_exit_triggered False | Wave 2 | 2 | STRAT-09 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_is_exit_triggered_false -x` | ✅ | ✅ green |
| Invariant 1: effective_stop >= initial (Hypothesis) | Wave 2 | 2 | TEST-03 | — | N/A | property | `uv run pytest tests/test_strategy/test_positions.py::test_effective_stop_ge_initial -x` | ✅ | ✅ green |
| Invariant 2: trailing stop monotonic (Hypothesis) | Wave 2 | 2 | TEST-03 | — | N/A | property | `uv run pytest tests/test_strategy/test_positions.py::test_trailing_stop_monotonic -x` | ✅ | ✅ green |
| Invariant 3: rank_candidates <= 10 (Hypothesis) | Wave 1 | 1 | TEST-03, STRAT-05 | — | N/A | property | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_max_ten -x` | ✅ | ✅ green |
| Invariant 4: regime_filter False <= sma200 (Hypothesis) | Wave 1 | 1 | TEST-03, STRAT-01 | — | N/A | property | `uv run pytest tests/test_strategy/test_screening.py::test_regime_off_when_close_le_sma200 -x` | ✅ | ✅ green |
| strategy/__init__.py re-exports | Wave 3 | 3 | All STRAT | — | N/A | unit | `uv run pytest --co -q` (import check) | ✅ | ✅ green |
| strategy-only coverage gate | Wave 3 | 3 | TEST-01 | — | N/A | coverage | `uv run pytest tests/test_strategy/ --cov=bensdorp1.strategy --cov-fail-under=95` | ✅ | ✅ green |
| all-modules coverage gate | Wave 3 | 3 | TEST-02 | — | N/A | coverage | `uv run pytest --cov=bensdorp1 --cov-fail-under=90` | ✅ | ✅ green |
| mypy strict clean | Wave 3 | 3 | All STRAT | — | N/A | type | `uv run mypy src/bensdorp1/strategy/` | ✅ | ✅ green |
| ruff clean | Wave 3 | 3 | All STRAT | — | N/A | lint | `uv run ruff check src/bensdorp1/strategy/` | ✅ | ✅ green |
| CR-02: compute_position_size prev_close <= 0 guard | Audit | post-plan | CR-02 | — | N/A | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_position_size_zero_price -x` | ✅ | ✅ green |
| CR-01: rank_candidates skip close_t200 == 0 guard | Audit | post-plan | CR-01 | — | N/A | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_skip_zero_close_t200 -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `src/bensdorp1/strategy/__init__.py` — package marker + re-exports (mirrors db/ and data/ pattern)
- [x] `src/bensdorp1/strategy/screening.py` — 4 functions + Candidate TypedDict
- [x] `src/bensdorp1/strategy/positions.py` — 6 position sizing and stop functions
- [x] `tests/test_strategy/__init__.py` — empty package marker
- [x] `tests/test_strategy/test_screening.py` — full unit + Hypothesis coverage
- [x] `tests/test_strategy/test_positions.py` — full unit + Hypothesis coverage

*All Wave 0 files exist and are fully implemented.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | All strategy/ behaviors are pure math with no I/O | — |

*All phase behaviors have automated verification. No external services, HTTP calls, or filesystem operations in strategy/.*

---

## Validation Sign-Off

- [x] All tasks have automated verify
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** complete

---

## Validation Audit 2026-05-23

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |

**Gaps resolved:**
- G-01: `positions.py:17` — `compute_position_size` guard for `prev_close <= 0.0` (CR-02 fix from code review). Added `test_compute_position_size_zero_price`.
- G-02: `screening.py:167` — `rank_candidates` skip guard for `close_t200 == 0.0` (CR-01 fix from code review). Added `test_rank_candidates_skip_zero_close_t200`.

**Final coverage:** strategy/ 100% (39 tests, 70 stmts, 0 missed). All-modules: 167 tests passing.
