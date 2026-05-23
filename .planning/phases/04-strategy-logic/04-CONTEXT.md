# Phase 4: Strategy Logic - Context

**Gathered:** 2026-05-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the `strategy/` subpackage — all System #1 filters, ranking, and stop calculations implemented as pure functions. The subpackage receives pre-fetched DataFrames and returns results; it has no DB dependency and never calls yfinance or SQLAlchemy directly.

This phase delivers: `src/bensdorp1/strategy/` with `screening.py` (regime filter, liquidity filter, momentum filter, ranking), `positions.py` (position sizing, initial stop, trailing stop, effective stop, exit trigger), and `__init__.py`.

Phase 7 (Scan) and Phase 8 (Buy) call into this subpackage. They are responsible for all DB reads — they build the required DataFrames and pass them in.

Test coverage targets: >95% line coverage on `strategy/` modules; >90% on all source modules. Hypothesis property tests verify the 4 defined invariants.

</domain>

<decisions>
## Implementation Decisions

### Module Layout
- **D-01:** `strategy/` subpackage with two implementation modules:
  - `strategy/screening.py` — `regime_filter`, `liquidity_filter`, `momentum_filter`, `rank_candidates`
  - `strategy/positions.py` — `compute_position_size`, `compute_initial_stop`, `update_highest_close`, `compute_trailing_stop`, `compute_effective_stop`, `is_exit_triggered`
  - `strategy/__init__.py` — re-exports public API (mirrors `db/` and `data/` pattern)

### Strategy Purity
- **D-02:** Pure functions only. `strategy/` has zero imports from `db/` or `data/`. All DataFrames come in from the caller. Phase 7 performs all `price_daily` reads and passes pre-fetched DataFrames to `screening.py`. Phase 7 reads open positions from DB and passes their fields as scalars to `positions.py`. This makes Phase 4 100% testable with in-memory DataFrames — no DB fixture needed.

### Boundary Counting
- **D-03:** "200 trading days ago" = T-200 exclusive of today. Uses `n_trading_days_ago(today, 200)` from `data/calendar.py` (already implemented in Phase 3). Momentum filter: `close_today > close_at(n_trading_days_ago(today, 200))`. ROC 200: `(close_today / close_at(n_trading_days_ago(today, 200))) - 1`.
- **D-04:** 20-day average volume for the liquidity filter uses the 20 trading days BEFORE today (T-1 through T-20, excluding today's row). `prices.iloc[-20:]` applied after slicing off today. This avoids data freshness ambiguity at scan time.

### SPX Regime Filter
- **D-09:** SMA 200 = simple arithmetic mean of the last 200 closes INCLUDING today: `spx_closes.iloc[-200:].mean()`. Regime is ON when `today_close > sma_200`. If `len(spx_closes) < 200`, raise `ValueError`.

### Edge Cases and Error Contract
- **D-05:** Empty candidate list is a valid outcome (all stocks failed a filter, or regime is off). Return `[]` — not an exception. Phase 7 displays "No buy candidates today."
- **D-06:** `compute_position_size(available_cash, prev_close) -> int` returns `0` when `floor((cash × 0.10) / prev_close) = 0`. Phase 7 is responsible for detecting 0-share candidates and displaying them appropriately.
- **D-07:** Any strategy function that receives a price DataFrame with fewer rows than required raises `ValueError` with a message stating expected vs. actual row count. This condition indicates a data integrity bug — it should never occur post-init.

### Trailing Stop Functions
- **D-08:** Two separate functions (independently testable):
  - `update_highest_close(current: float, new_close: float) -> float` — returns `max(current, new_close)`
  - `compute_trailing_stop(highest_close: float) -> float` — returns `highest_close * 0.75`
  The "skip entry day" rule is enforced by Phase 7: it only calls `update_highest_close` on scans where `scan_date > entry_date`. Phase 4's functions are stateless and know nothing about entry dates.

### Testing Strategy
- **D-10:** Exactly the 4 Hypothesis invariants defined in ROADMAP success criteria:
  1. `compute_effective_stop(i, t) >= i` always (effective_stop >= initial_stop)
  2. Trailing stop sequence is monotonically non-decreasing given a non-decreasing `update_highest_close` series
  3. `rank_candidates(...)` returns `len(candidates) <= 10` regardless of input size
  4. `regime_filter(spx_series_where_close_lte_sma200)` returns `False` → `liquidity_filter` and `momentum_filter` are not called (tested at Phase 7 integration level, not Phase 4 unit level)
- **D-11:** Hypothesis strategies use `st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)` for prices and `st.integers(min_value=0)` for volumes. Price DataFrames are constructed manually in each test. No `hypothesis[pandas]` extra required.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/ROADMAP.md` §Phase 4 — Goal, success criteria (5 items), and TBD plan count
- `.planning/REQUIREMENTS.md` — STRAT-01 through STRAT-10 (all strategy requirements), TEST-01 through TEST-03 (coverage and Hypothesis targets)
- `.planning/PROJECT.md` — Context section: "200 trading days ago uses NYSE trading calendar only", "trailing stop tracking starts the day AFTER entry (entry day close is the `entry_close`, not tracked)"

### Phase 3 data layer (what strategy/ consumes)
- `.planning/phases/03-data-sources/03-CONTEXT.md` — D-04: `^GSPC` is in `price_daily` with same query pattern as constituent symbols. Phase 4 reads `price_daily WHERE symbol = '^GSPC'` for regime filter input.
- `src/bensdorp1/data/calendar.py` — `n_trading_days_ago(date, n)` function: n=1 returns the NYSE trading day before the reference date (reference excluded). Phase 4 calls `n_trading_days_ago(today, 200)` for T-200 reference date.
- `src/bensdorp1/data/__init__.py` — public API surface of the data layer

### Database schema (what strategy/ does NOT touch but Phase 7 reads to feed strategy/)
- `src/bensdorp1/db/schema.py` — `price_daily` table columns (symbol, trade_date, close, volume) and `positions` table columns (entry_close, initial_stop, highest_close, trailing_stop) — Phase 7 reads these and passes them as DataFrames/scalars to strategy/

### Technology guidance (in CLAUDE.md)
- `CLAUDE.md` §Verified Library Versions — pandas `>=3.0.3`, numpy `>=2.0`
- `CLAUDE.md` §mypy Strict Mode Configuration — `strategy/` MUST pass mypy strict; no `# type: ignore` unless documented

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/bensdorp1/data/calendar.py` — `n_trading_days_ago(date, n)` is the only trading-day arithmetic needed for Phase 4. Phase 4 calls it directly — no re-implementation.
- `src/bensdorp1/db/engine.py` — NOT used by strategy/. Phase 7 uses engine.py to build DataFrames before calling strategy functions.
- `src/bensdorp1/db/audit.py` — NOT used by strategy/. Scan_performed audit event is written by Phase 7, not Phase 4.

### Established Patterns
- **`src/` layout** — new subpackage at `src/bensdorp1/strategy/`. No flat modules at repo root.
- **`pathlib.Path` throughout** — not relevant here (no file I/O in strategy/). Use standard Python types.
- **`-> None` / explicit return types** — mypy strict requires explicit return annotations on every function.
- **No circular imports** — `strategy/` MUST NOT import from `_app.py`, `commands/`, `db/`, or `data/`. Pure math only.
- **PEP 735 dependency groups** — no new runtime deps expected; pandas and numpy are already present.

### Integration Points
- `src/bensdorp1/commands/scan.py` (stub) — Phase 7 will import from `strategy.screening` and `strategy.positions` and call them with pre-fetched DataFrames from `price_daily`.
- `src/bensdorp1/commands/buy.py` (stub) — Phase 8 will call `positions.compute_initial_stop(entry_close)` and initialize `highest_close = 0.0` at buy time.
- `tests/` — Phase 4 creates `tests/test_strategy/` mirroring the `strategy/` structure: `test_screening.py` and `test_positions.py`.

</code_context>

<specifics>
## Specific Ideas

- For the liquidity filter, "top 25%" means the top quartile of S&P 500 constituents by 20-day average volume. Concretely: compute the 75th percentile of average volumes across all constituents, then keep only those at or above that threshold.
- `regime_filter` signature: `regime_filter(spx_closes: pd.Series) -> bool`. Receives a Series of SPX adjusted closes (chronological, last entry = today). Returns True if regime is on.
- `rank_candidates` returns a DataFrame (or list of dicts) with columns: `symbol`, `roc_200`, `prev_close`, `position_size`. Phase 7 reads these to build the scan output. Position sizing is computed inside `rank_candidates` (requires `available_cash` param) so Phase 7 gets ready-to-display rows.
- At buy time (Phase 8): `highest_close` is initialized to `0.0` in the positions table. Phase 7 skips `update_highest_close()` when `scan_date == entry_date` (entry day). From `scan_date > entry_date`, Phase 7 calls `update_highest_close(pos.highest_close, today_close)` on every scan. This enforces the "tracking starts day after entry" rule without any logic in `strategy/`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 4-Strategy Logic*
*Context gathered: 2026-05-23*
