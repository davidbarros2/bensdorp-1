# Phase 4: Strategy Logic - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 4-Strategy Logic
**Areas discussed:** Module layout, Strategy purity, Boundary counting (T-200 + 20-day volume), Edge cases, Trailing stop functions, SPX SMA 200, Hypothesis test strategy

---

## Module Layout

| Option | Description | Selected |
|--------|-------------|----------|
| `strategy/` subpackage — `screening.py` + `positions.py` | Mirrors db/ and data/ pattern. Filters+ranking vs stops+sizing. | ✓ |
| Single `strategy.py` flat file | All 9 functions in one file. Simpler but mixes concerns. | |
| `strategy/` with 3 modules: `filters.py` + `ranking.py` + `positions.py` | More granular but adds a file without benefit. | |

**User's choice:** `strategy/` subpackage — `screening.py` + `positions.py` (recommended)
**Notes:** Follows the established subpackage pattern from db/ and data/.

---

## Strategy Purity

| Option | Description | Selected |
|--------|-------------|----------|
| Pure functions only — Phase 7 does all DB reads | No DB imports in strategy/. 100% testable with in-memory DataFrames. | ✓ |
| strategy/ includes `run_scan(engine, scan_date)` orchestrator | Phase 7 calls one function but strategy/ now depends on SQLAlchemy. | |

**User's choice:** Pure functions only (recommended)
**Notes:** ROADMAP already specifies "pure functions" — user confirmed this aligns with intent.

---

## Boundary Counting — T-200 for Momentum and ROC

| Option | Description | Selected |
|--------|-------------|----------|
| T-200 exclusive — compare today's close to close on NYSE day T-200 | Uses `n_trading_days_ago(today, 200)`. Standard convention matching Phase 3 calendar design. | ✓ |
| T-199 — 200-bar period including today | Would use `n_trading_days_ago(today, 199)`. Less common in EOD systems. | |

**User's choice:** T-200 exclusive (recommended)
**Notes:** `n_trading_days_ago(date, n)` was designed in Phase 3 with n=1 = day before reference. This is consistent.

---

## Boundary Counting — 20-Day Average Volume

| Option | Description | Selected |
|--------|-------------|----------|
| 20 trading days ending yesterday (T-1 to T-20) | Excludes today's volume. Standard for EOD systems. | ✓ |
| 20 trading days including today (T to T-19) | Today's volume is available post-16:30 but adds freshness complexity. | |

**User's choice:** T-1 through T-20 (recommended)
**Notes:** Avoids any ambiguity about whether today's volume is fully settled at scan time.

---

## SPX SMA 200

| Option | Description | Selected |
|--------|-------------|----------|
| Mean of last 200 closes INCLUDING today | `spx_closes.iloc[-200:].mean()`. Standard EOD convention. | ✓ |
| Mean of 200 closes BEFORE today (T-1 to T-200) | Excludes today. Less common. | |

**User's choice:** Including today (recommended)
**Notes:** Regime comparison is `today_close > spx_closes.iloc[-200:].mean()`. Today's close is bar 200.

---

## Edge Cases

| Question | Options | Selected |
|----------|---------|----------|
| All stocks fail filter → empty candidate list? | Return `[]` (valid state) vs. raise ValueError | Return `[]` |
| Position sizing = 0 shares? | Return 0 (Phase 7 handles) vs. raise ValueError | Return 0 |
| Insufficient price data rows? | Raise ValueError vs. return empty gracefully | Raise ValueError |

**User's choice:** All recommended options
**Notes:** Empty candidate list is expected (regime off, bad market). Zero shares is rare but valid. Insufficient data is a bug.

---

## Trailing Stop Functions

| Option | Description | Selected |
|--------|-------------|----------|
| Two separate functions: `update_highest_close()` + `compute_trailing_stop()` | Independently Hypothesis-testable. Phase 7 stores highest_close in DB. | ✓ |
| Single combined `update_trailing_stop()` → `tuple[float, float]` | One call in Phase 7 but can't test `update_highest_close` invariant directly. | |

**User's choice:** Two separate functions (recommended)
**Notes:** "Skip entry day" logic stays in Phase 7, not Phase 4. Phase 4 functions are always pure.

---

## Hypothesis Test Strategy

| Question | Options | Selected |
|----------|---------|----------|
| Number of property test invariants? | 4 ROADMAP invariants only vs. add 1-2 extras | 4 only |
| DataFrame generation approach? | `st.floats` + manual construction vs. `hypothesis.extra.pandas` | `st.floats` + manual |

**User's choice:** Both recommended options
**Notes:** No extras to avoid over-specifying before implementation. No `hypothesis[pandas]` extra to keep tests fast and dependency-light.

---

## Claude's Discretion

- `strategy/__init__.py` public API surface — what to re-export (Claude decides, should mirror db/ and data/ patterns)
- Internal DataFrame column naming conventions within screening.py and positions.py
- Specific test file structure within `tests/test_strategy/`

## Deferred Ideas

None — discussion stayed within phase scope.
