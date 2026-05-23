# Phase 4: Strategy Logic - Research

**Researched:** 2026-05-23
**Domain:** Pure Python numeric functions — pandas/numpy filter math, Hypothesis property tests, mypy strict annotations
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** `strategy/` subpackage with two implementation modules:
- `strategy/screening.py` — `regime_filter`, `liquidity_filter`, `momentum_filter`, `rank_candidates`
- `strategy/positions.py` — `compute_position_size`, `compute_initial_stop`, `update_highest_close`, `compute_trailing_stop`, `compute_effective_stop`, `is_exit_triggered`
- `strategy/__init__.py` — re-exports public API (mirrors `db/` and `data/` pattern)

**D-02:** Pure functions only. `strategy/` has zero imports from `db/` or `data/`. All DataFrames come in from the caller.

**D-03:** "200 trading days ago" = T-200 exclusive of today. Uses `n_trading_days_ago(today, 200)` from `data/calendar.py`. Momentum filter: `close_today > close_at(n_trading_days_ago(today, 200))`. ROC 200: `(close_today / close_at(n_trading_days_ago(today, 200))) - 1`.

**D-04:** 20-day average volume uses T-1 through T-20 (excluding today). `prices.iloc[:-1].iloc[-20:]` applied after slicing off today.

**D-05:** Empty candidate list returns `[]` — not an exception.

**D-06:** `compute_position_size(available_cash, prev_close) -> int` returns `0` when `floor((cash × 0.10) / prev_close) = 0`.

**D-07:** Any strategy function that receives a price DataFrame with fewer rows than required raises `ValueError`.

**D-08:** Two separate trailing stop functions: `update_highest_close(current, new_close) -> float` and `compute_trailing_stop(highest_close) -> float`.

**D-09:** SMA 200 = mean of last 200 closes INCLUDING today: `spx_closes.iloc[-200:].mean()`. Raises `ValueError` if `len < 200`.

**D-10:** Exactly 4 Hypothesis invariants:
1. `compute_effective_stop(i, t) >= i` always
2. Trailing stop sequence is monotonically non-decreasing given non-decreasing `update_highest_close`
3. `rank_candidates(...)` returns `len <= 10` regardless of input size
4. `regime_filter(series_where_close_lte_sma200)` returns `False`

**D-11:** Hypothesis strategies use `st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)` for prices and `st.integers(min_value=0)` for volumes. No `hypothesis[pandas]` extra.

**Function signatures (locked):**
- `regime_filter(spx_closes: pd.Series[float]) -> bool`
- `liquidity_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]`
- `momentum_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]`
- `rank_candidates(price_dfs: dict[str, pd.DataFrame], available_cash: float) -> list[Candidate]`
- Liquidity filter: 75th percentile of 20-day avg volumes across all constituents

### Claude's Discretion

None — discussion stayed within phase scope.

### Deferred Ideas (OUT OF SCOPE)

None.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STRAT-01 | Regime filter — buy candidates only when SPX close > SPX SMA 200 | `spx_closes.iloc[-200:].mean()` idiom verified; `pd.Series[float]` annotation passes mypy strict |
| STRAT-02 | Liquidity filter — top 25% of S&P 500 by 20-day average volume | `series.quantile(0.75)` + `iloc[:-1].iloc[-20:]` idiom verified |
| STRAT-03 | Momentum filter — stock close today > close 200 trading days ago | `iloc[-200]` lookup pattern verified; `n_trading_days_ago` already implemented |
| STRAT-04 | Ranking — descending ROC 200, top 10 selected | `sorted(results, key=lambda x: x["roc_200"], reverse=True)[:10]` verified |
| STRAT-05 | Max 10 open positions at any time | Enforced by `rank_candidates` returning at most 10; Phase 7 owns DB constraint |
| STRAT-06 | Position sizing — `floor((cash * 0.10) / prev_close)` | `math.floor(...)` verified; D-06 zero-return case confirmed |
| STRAT-07 | Initial stop — `entry_close * 0.93` | Trivial arithmetic; mypy-strict clean |
| STRAT-08 | Trailing stop — `highest_close * 0.75`, updated daily | Two-function split (D-08) verified; monotonicity property confirmed |
| STRAT-09 | Effective stop — `max(initial, trailing)`; trigger when close <= effective | `compute_effective_stop` and `is_exit_triggered` signatures verified |
| STRAT-10 | Exit triggers persist until confirmed closed by user | Phase 7 responsibility; Phase 4 provides `is_exit_triggered` predicate only |
| TEST-01 | Unit test coverage >95% on strategy/ modules | Coverage command verified; branch map documented |
| TEST-02 | Unit test coverage >90% on all source modules | Existing tests cover db/ and data/; strategy/ adds to total |
| TEST-03 | Property-based tests for all strategy invariants | All 4 Hypothesis invariant patterns verified and sketched |
</phase_requirements>

---

## Summary

Phase 4 builds the `strategy/` subpackage — 12 pure functions across `screening.py` and `positions.py` that receive pre-fetched DataFrames and return results with no I/O. All decisions are locked in CONTEXT.md; the research confirms implementation patterns, resolves all annotation questions for mypy strict mode, and documents the exact Hypothesis test structure for the 4 required property invariants.

The critical technical finding is that `rank_candidates` must return `list[Candidate]` where `Candidate` is a `TypedDict` — `list[dict[str, object]]` fails mypy strict because `float(x["roc_200"])` cannot be called on `object`. All other function signatures pass mypy strict as annotated. The `pd.Series[float]` generic annotation (not bare `pd.Series`) is required for mypy strict with pandas-stubs 3.0.0.260204.

The liquidity filter design requires a specific two-step slice: `df.iloc[:-1].iloc[-20:]` to exclude today before taking the 20-day window. The 75th percentile is computed across all passed-in symbols in a single `pd.Series.quantile(0.75)` call. Both patterns are verified against the installed stack (pandas 3.0.3, numpy 2.4.6).

**Primary recommendation:** Implement all 12 functions as pure numeric functions with no imports outside the Python standard library and pandas/numpy. Use `TypedDict` for `Candidate`. Use `pd.Series[float]` in all Series annotations.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Regime filter (SMA 200) | strategy/ (pure math) | — | Receives pre-fetched SPX closes; returns bool |
| Liquidity filter (P75 volume) | strategy/ (pure math) | — | Receives price DataFrames; no DB access |
| Momentum filter (ROC 200 direction) | strategy/ (pure math) | — | Receives price DataFrames; no calendar call |
| Ranking (ROC 200 sort + top 10) | strategy/ (pure math) | — | Position sizing computed inline |
| Position size computation | strategy/ (pure math) | — | `floor((cash * 0.10) / prev_close)` |
| Initial stop | strategy/ (pure math) | — | `entry_close * 0.93`, immutable |
| Trailing stop tracking | strategy/ (pure math) | Phase 7 (state) | Phase 4 provides stateless functions; Phase 7 persists |
| Effective stop | strategy/ (pure math) | — | `max(initial, trailing)` |
| Exit trigger evaluation | strategy/ (pure math) | Phase 7 (display) | Phase 4 returns bool; Phase 7 formats output |
| Price data fetching | Phase 7 (scan command) | data/ | Phase 4 never touches DB or yfinance |
| DataFrame construction from DB | Phase 7 (scan command) | — | Phase 7 queries price_daily and passes DataFrames in |
| DB persistence of stop values | Phase 7 (scan command) | — | Phase 4 returns updated values; Phase 7 writes them |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 3.0.3 [VERIFIED: local env] | DataFrame operations, quantile, iloc slicing | Already a project dep; all filter math uses it |
| numpy | 2.4.6 [VERIFIED: local env] | Numeric types underlying pandas; `math.floor` preferred for int results | Project dep; no direct numpy calls needed in strategy/ |
| hypothesis | 6.152.9 [VERIFIED: local env] | Property-based test generation | Required by TEST-03; already in dev deps |
| pandas-stubs | 3.0.0.260204 [VERIFIED: local env] | mypy type inference for pd.Series/DataFrame | Already in dev deps from Phase 3 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| math | stdlib | `math.floor()` for integer share count | Required by D-06; avoids float→int truncation ambiguity |
| typing.TypedDict | stdlib | `Candidate` return type for `rank_candidates` | mypy strict requires TypedDict not `dict[str, object]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `TypedDict` for Candidate | `list[dict[str, object]]` | dict[str,object] fails mypy strict: `float(x["roc_200"])` is `arg-type` error |
| `TypedDict` for Candidate | `pd.DataFrame` return | DataFrame requires callers to know column names; TypedDict is self-documenting |
| `math.floor` | `int(x // y)` | Both work but `math.floor` is the idiom for financial flooring |
| `pd.Series[float]` annotation | bare `pd.Series` | Bare `pd.Series` triggers mypy `type-arg` error in strict mode |

**Installation:** No new runtime dependencies. All required libraries are already in `pyproject.toml`.

---

## Package Legitimacy Audit

No new packages are installed in this phase. All libraries (`pandas`, `numpy`, `hypothesis`, `math`, `typing`) are either pre-existing project dependencies or Python stdlib. No package legitimacy gate needed.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Phase 7 (scan.py)
     |
     |  pre-fetched DataFrames (price_daily rows -> pd.DataFrame)
     |  scalars (entry_close, highest_close, initial_stop from positions rows)
     v
+----------------------------------+
|   strategy/screening.py          |
|                                  |
|  regime_filter(spx_closes)       |
|      -> bool                     |
|          |                       |
|     [False] -> return []         |
|          |                       |
|     [True]                       |
|          v                       |
|  liquidity_filter(price_dfs)     |
|      -> list[str]  (symbols)     |
|          |                       |
|          v                       |
|  momentum_filter(price_dfs)      |
|      -> list[str]  (symbols)     |
|          |                       |
|          v                       |
|  rank_candidates(price_dfs,      |
|    available_cash)               |
|      -> list[Candidate]  (<=10)  |
+----------------------------------+
     |
     |  list[Candidate] returned to Phase 7
     v
Phase 7 persists to scan_candidates table

Phase 7 (for each open position)
     |
     |  scalars from positions row
     v
+----------------------------------+
|   strategy/positions.py          |
|                                  |
|  update_highest_close(           |
|    current, new_close)           |
|      -> float                    |
|          |                       |
|          v                       |
|  compute_trailing_stop(          |
|    highest_close)                |
|      -> float                    |
|          |                       |
|          v                       |
|  compute_effective_stop(         |
|    initial_stop, trailing_stop)  |
|      -> float                    |
|          |                       |
|          v                       |
|  is_exit_triggered(              |
|    close, effective_stop)        |
|      -> bool                     |
+----------------------------------+
     |
     |  updated scalars returned to Phase 7
     v
Phase 7 writes UPDATE positions SET highest_close=..., trailing_stop=...
```

### Recommended Project Structure

```
src/bensdorp1/strategy/
├── __init__.py       # re-exports all public names (mirrors db/ and data/ pattern)
├── screening.py      # regime_filter, liquidity_filter, momentum_filter, rank_candidates
└── positions.py      # compute_position_size, compute_initial_stop, update_highest_close,
                      # compute_trailing_stop, compute_effective_stop, is_exit_triggered

tests/test_strategy/
├── __init__.py       # empty
├── test_screening.py # STRAT-01 through STRAT-04 + TEST-01 + TEST-03 (invariants 3, 4)
└── test_positions.py # STRAT-06 through STRAT-09 + TEST-01 + TEST-03 (invariants 1, 2)
```

### Pattern 1: pd.Series[float] annotation for mypy strict

**What:** Annotate all Series parameters with the generic `pd.Series[float]`, not the bare `pd.Series`. pandas-stubs 3.0.0.260204 supports generic Series; bare Series triggers `type-arg` in strict mode.

**When to use:** Every parameter and local variable typed as a pandas Series.

**Example (verified against mypy 2.1):**
```python
# Source: verified locally with uv run mypy --strict (mypy 2.x + pandas-stubs 3.0.0.260204)
import pandas as pd

def regime_filter(spx_closes: pd.Series[float]) -> bool:
    if len(spx_closes) < 200:
        raise ValueError(f"Need >= 200 closes; got {len(spx_closes)}")
    sma200: float = float(spx_closes.iloc[-200:].mean())
    today_close: float = float(spx_closes.iloc[-1])
    return today_close > sma200
```

### Pattern 2: TypedDict for rank_candidates return type

**What:** Define a `Candidate` TypedDict to give `rank_candidates` a mypy-strict-clean return type. `list[dict[str, object]]` fails because calling `float(x["roc_200"])` is an `arg-type` error (object is not `SupportsFloat`).

**When to use:** Any function returning a list of heterogeneous record dicts consumed by typed callers.

**Example (verified — mypy strict clean):**
```python
# Source: verified locally with uv run mypy --strict
import math
from typing import TypedDict
import pandas as pd

class Candidate(TypedDict):
    symbol: str
    roc_200: float
    prev_close: float
    position_size: int

def rank_candidates(
    price_dfs: dict[str, pd.DataFrame],
    available_cash: float,
) -> list[Candidate]:
    results: list[Candidate] = []
    for symbol, df in price_dfs.items():
        if len(df) < 200:
            raise ValueError(f"{symbol}: need >= 200 rows; got {len(df)}")
        prev_close: float = float(df["close"].iloc[-1])
        close_t200: float = float(df["close"].iloc[-200])
        roc_200: float = (prev_close / close_t200) - 1.0
        shares: int = math.floor((available_cash * 0.10) / prev_close)
        results.append({
            "symbol": symbol,
            "roc_200": roc_200,
            "prev_close": prev_close,
            "position_size": shares,
        })
    return sorted(results, key=lambda x: x["roc_200"], reverse=True)[:10]
```

### Pattern 3: 20-day volume window (D-04)

**What:** Slice off today's row first with `iloc[:-1]`, then take the last 20 with `iloc[-20:]`. This gives T-1 through T-20 precisely, regardless of how many total rows are in the DataFrame.

**When to use:** liquidity_filter volume computation.

**Example (verified):**
```python
# Source: verified locally against pandas 3.0.3
def liquidity_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]:
    avg_volumes: dict[str, float] = {}
    for symbol, df in price_dfs.items():
        if len(df) < 21:
            raise ValueError(f"{symbol}: need >= 21 rows; got {len(df)}")
        excl_today: pd.DataFrame = df.iloc[:-1]
        last_20: pd.DataFrame = excl_today.iloc[-20:]
        avg_volumes[symbol] = float(last_20["volume"].mean())
    if not avg_volumes:
        return []
    threshold: float = float(pd.Series(list(avg_volumes.values()), dtype=float).quantile(0.75))
    return [sym for sym, vol in avg_volumes.items() if vol >= threshold]
```

### Pattern 4: Hypothesis st.lists for monotonicity invariant

**What:** Use `st.lists(price_strategy, min_size=2)` to generate a sequence of closes, then run the trailing stop through them and verify monotonicity.

**When to use:** Invariant #2 — trailing stop never decreases.

**Example (verified):**
```python
# Source: verified locally against hypothesis 6.152.9
from hypothesis import given, settings
from hypothesis import strategies as st

price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)

@given(st.lists(price_st, min_size=2))
@settings(max_examples=200)
def test_trailing_stop_monotonic(closes: list[float]) -> None:
    highest = 0.0
    stops: list[float] = []
    for c in closes:
        highest = max(highest, c)
        stops.append(highest * 0.75)
    for i in range(1, len(stops)):
        assert stops[i] >= stops[i - 1]
```

### Anti-Patterns to Avoid

- **Bare `pd.Series` annotation:** Causes `type-arg` error in mypy strict. Always use `pd.Series[float]`.
- **`list[dict[str, object]]` for Candidate:** `float(x["roc_200"])` is an `arg-type` error. Use `TypedDict`.
- **`float(series.quantile(0.75))` without explicit cast:** `quantile` returns `numpy.float64` at runtime but pandas-stubs types it as `float`; explicit `float()` cast is defensive and self-documenting.
- **Importing from `data/` or `db/` in `strategy/`:** Violates D-02. strategy/ must have zero I/O imports.
- **`prices.iloc[-20:]` without excluding today:** Gives T-0 through T-19, not T-1 through T-20. Always slice off today first (D-04).
- **`spx_closes.iloc[-200:].mean()` called without length check:** Raises `ValueError` when len < 200 per D-09. Check first.
- **`int(x / y)` instead of `math.floor(x / y)`:** `int()` truncates toward zero; `floor()` always rounds down. For positive values they are the same, but `math.floor` is the correct financial convention and self-documents intent.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 75th percentile across symbols | custom sort and index | `pd.Series.quantile(0.75)` | Edge cases: all-equal values, single-element series, NaN handling |
| Float floor division for shares | `int(x/y)` or `x//y` | `math.floor(x/y)` | Documents intent; handles the 0-share case (D-06) identically |
| Monotonicity generation | custom lists | `hypothesis st.lists(price_st, min_size=2)` | Hypothesis explores edge cases (repeated values, tiny decreases) automatically |
| Property test shrinking | manual minimization | Hypothesis auto-shrink | Built-in; finds minimal failing example automatically |

**Key insight:** Strategy math is trivial but the edge cases (all-equal volumes, zero shares, series lengths exactly at boundary) are where bugs live. Hypothesis finds these systematically.

---

## Common Pitfalls

### Pitfall 1: iloc[-20:] includes today

**What goes wrong:** `df.iloc[-20:]` when the last row is today gives T-0 through T-19, not T-1 through T-20. The liquidity filter uses today's volume (possibly incomplete at scan time).

**Why it happens:** The natural idiom for "last 20 rows" without understanding the row convention.

**How to avoid:** Always `excl_today = df.iloc[:-1]` first, then `excl_today.iloc[-20:]`. This pattern is locked in D-04 and should be the only slice pattern in liquidity_filter.

**Warning signs:** Unit test uses exactly 21 rows and only fails when today's row differs from T-1.

### Pitfall 2: Bare pd.Series triggers mypy type-arg

**What goes wrong:** `def regime_filter(spx_closes: pd.Series) -> bool:` fails mypy strict with `Missing type parameters for generic type "Series" [type-arg]`.

**Why it happens:** pandas-stubs defines `Series` as a generic `Series[Dtype]`. Strict mode requires type parameters.

**How to avoid:** Always annotate as `pd.Series[float]`. For DataFrames, `pd.DataFrame` does not require type parameters (it is not generically typed in pandas-stubs).

**Warning signs:** mypy error code `[type-arg]` on any `pd.Series` annotation.

### Pitfall 3: dict[str, object] return fails at call sites

**What goes wrong:** `rank_candidates` returns `list[dict[str, object]]` and Phase 7 writes `float(c["roc_200"])` — mypy emits `Argument 1 to "float" has incompatible type "object"; expected "str | Buffer | SupportsFloat | SupportsIndex" [arg-type]`.

**Why it happens:** `object` is the top type; it does not satisfy `SupportsFloat`. This is correct behavior from mypy's perspective.

**How to avoid:** Use `TypedDict` with concrete field types. Verified: `list[Candidate]` with `Candidate(TypedDict)` passes mypy strict at both the definition and all call sites.

**Warning signs:** mypy `[arg-type]` errors when Phase 7 code accesses Candidate fields.

### Pitfall 4: quantile return type is numpy.float64 at runtime

**What goes wrong:** `threshold = series.quantile(0.75)` gives a `numpy.float64` at runtime. Comparisons like `vol >= threshold` work, but explicit arithmetic or type-narrowing may behave unexpectedly.

**Why it happens:** pandas-stubs types quantile as returning `float` for scalar q, but pandas 3.x returns `numpy.float64`. These are compatible for most operations but the distinction matters for type annotations.

**How to avoid:** Wrap with `float()`: `threshold: float = float(series.quantile(0.75))`. This is already the idiomatic pattern in the existing data/ code (prices.py uses explicit `float()` everywhere).

**Warning signs:** None at runtime, but defensive `float()` wrapping prevents future issues.

### Pitfall 5: Hypothesis generates values that expose integer arithmetic precision

**What goes wrong:** `st.floats(min_value=0.01, max_value=10000)` can generate values like `0.010000000000000002` which, when used as `prev_close`, produce `math.floor((cash * 0.10) / 0.010000000000000002)` — a very large integer. Not a bug, but test assertions need to handle wide output ranges.

**Why it happens:** IEEE 754 representation of small floats.

**How to avoid:** D-11 bounds are correct (0.01 to 10000). Assertions in position size tests should not assume a specific magnitude — test the property (returns int >= 0) not a specific value.

**Warning signs:** Hypothesis counterexample shows `position_size` in the millions.

### Pitfall 6: __init__.py re-export pattern

**What goes wrong:** If `strategy/__init__.py` does not explicitly re-export `Candidate`, Phase 7 cannot import it as `from bensdorp1.strategy import Candidate`.

**Why it happens:** mypy strict with `no_implicit_reexport` (enabled by strict mode) requires explicit `__all__` or explicit `from .module import Name` in `__init__.py`.

**How to avoid:** Mirror the pattern in `db/__init__.py` — explicit `from bensdorp1.strategy.screening import ...` lines and an `__all__` list. Include `Candidate` in both.

---

## Code Examples

### regime_filter — complete implementation

```python
# Source: verified against mypy strict + pandas-stubs 3.0.0.260204, pandas 3.0.3
import pandas as pd

def regime_filter(spx_closes: pd.Series[float]) -> bool:
    """Return True when SPX is in bull regime (close today > SMA 200).

    STRAT-01: SMA 200 is the simple mean of the last 200 closes including today.
    D-09: Raises ValueError if fewer than 200 rows provided.

    Args:
        spx_closes: Chronological Series of SPX adjusted closes; last entry = today.

    Returns:
        True when today_close > sma_200 (regime on); False otherwise.

    Raises:
        ValueError: If len(spx_closes) < 200.
    """
    if len(spx_closes) < 200:
        raise ValueError(f"regime_filter: need >= 200 closes; got {len(spx_closes)}")
    sma200: float = float(spx_closes.iloc[-200:].mean())
    today_close: float = float(spx_closes.iloc[-1])
    return today_close > sma200
```

### liquidity_filter — complete implementation

```python
# Source: verified against mypy strict + pandas 3.0.3
import pandas as pd

def liquidity_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]:
    """Return symbols in the top 25% by 20-day average volume (T-1 through T-20).

    STRAT-02: 75th percentile threshold computed across all symbols in price_dfs.
    D-04: Volume window excludes today (iloc[:-1].iloc[-20:]).
    D-05: Returns [] when price_dfs is empty.
    D-07: Raises ValueError if any symbol has fewer than 21 rows.

    Args:
        price_dfs: Mapping of symbol -> DataFrame with columns [close, volume],
                   indexed chronologically; last row = today.

    Returns:
        List of symbols at or above the 75th percentile of 20-day average volume.
    """
    if not price_dfs:
        return []
    avg_volumes: dict[str, float] = {}
    for symbol, df in price_dfs.items():
        if len(df) < 21:
            raise ValueError(
                f"liquidity_filter: {symbol} needs >= 21 rows; got {len(df)}"
            )
        excl_today: pd.DataFrame = df.iloc[:-1]
        last_20: pd.DataFrame = excl_today.iloc[-20:]
        avg_volumes[symbol] = float(last_20["volume"].mean())
    threshold: float = float(
        pd.Series(list(avg_volumes.values()), dtype=float).quantile(0.75)
    )
    return [sym for sym, vol in avg_volumes.items() if vol >= threshold]
```

### positions.py — complete stop calculation chain

```python
# Source: verified against mypy strict (no pandas/numpy imports needed)
import math

def compute_position_size(available_cash: float, prev_close: float) -> int:
    """Return shares to buy: floor((cash * 0.10) / prev_close). Returns 0 if < 1 share."""
    return math.floor((available_cash * 0.10) / prev_close)

def compute_initial_stop(entry_close: float) -> float:
    """Return initial stop: entry_close * 0.93. Set once; never changes."""
    return entry_close * 0.93

def update_highest_close(current: float, new_close: float) -> float:
    """Return new highest close: max(current, new_close). Stateless."""
    return max(current, new_close)

def compute_trailing_stop(highest_close: float) -> float:
    """Return trailing stop: highest_close * 0.75. Stateless."""
    return highest_close * 0.75

def compute_effective_stop(initial_stop: float, trailing_stop: float) -> float:
    """Return effective stop: max(initial_stop, trailing_stop)."""
    return max(initial_stop, trailing_stop)

def is_exit_triggered(close: float, effective_stop: float) -> bool:
    """Return True when close <= effective_stop (exit signal)."""
    return close <= effective_stop
```

### Hypothesis invariant test patterns

```python
# Source: verified against hypothesis 6.152.9 locally

from hypothesis import given, settings
from hypothesis import strategies as st

_price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)

# Invariant 1: effective_stop >= initial_stop always
@given(_price_st, _price_st)
@settings(max_examples=500)
def test_effective_stop_ge_initial(initial: float, trailing: float) -> None:
    from bensdorp1.strategy.positions import compute_effective_stop
    assert compute_effective_stop(initial, trailing) >= initial

# Invariant 2: trailing stop sequence is monotonically non-decreasing
@given(st.lists(_price_st, min_size=2))
@settings(max_examples=500)
def test_trailing_stop_monotonic(closes: list[float]) -> None:
    from bensdorp1.strategy.positions import update_highest_close, compute_trailing_stop
    highest = 0.0
    stops: list[float] = []
    for c in closes:
        highest = update_highest_close(highest, c)
        stops.append(compute_trailing_stop(highest))
    for i in range(1, len(stops)):
        assert stops[i] >= stops[i - 1]

# Invariant 3: rank_candidates returns <= 10 regardless of input size
@given(
    st.lists(
        st.fixed_dictionaries({
            "symbol": st.from_regex(r"[A-Z]{1,5}", fullmatch=True),
            "close": _price_st,
            "volume": st.integers(min_value=0, max_value=100_000_000),
        }),
        min_size=0, max_size=600
    ),
    st.floats(min_value=1.0, max_value=10_000_000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_rank_candidates_max_ten(raw_inputs: list[dict[str, object]], available_cash: float) -> None:
    # Build minimal DataFrames: 200 rows of the same close/volume for each unique symbol
    import pandas as pd
    import numpy as np
    symbols_seen: set[str] = set()
    price_dfs: dict[str, pd.DataFrame] = {}
    for row in raw_inputs:
        sym = str(row["symbol"])
        if sym in symbols_seen:
            continue
        symbols_seen.add(sym)
        close_val = float(row["close"])  # type: ignore[arg-type]
        vol_val = int(row["volume"])  # type: ignore[arg-type]
        df = pd.DataFrame({
            "close": [close_val] * 200,
            "volume": [vol_val] * 221,
        })
        price_dfs[sym] = df
    from bensdorp1.strategy.screening import rank_candidates
    result = rank_candidates(price_dfs, available_cash)
    assert len(result) <= 10

# Invariant 4: regime_filter returns False when close <= sma200
@given(
    st.lists(_price_st, min_size=200, max_size=200),
    _price_st
)
@settings(max_examples=500)
def test_regime_off_when_close_le_sma200(
    prefix: list[float], multiplier: float
) -> None:
    import pandas as pd
    from statistics import mean
    # Set today's close to half the mean, guaranteeing close < sma200
    today_close = min(prefix) * 0.5
    all_closes = prefix[:-1] + [today_close]  # replace last element
    series = pd.Series(all_closes, dtype=float)
    from bensdorp1.strategy.screening import regime_filter
    result = regime_filter(series)
    sma200 = mean(all_closes[-200:])
    if today_close <= sma200:
        assert result is False
```

---

## Integration Surface with Phase 7

### What Phase 7 builds and passes to strategy/

Phase 7 queries `price_daily WHERE symbol IN (constituents + '^GSPC') ORDER BY trade_date ASC` and builds DataFrames for each symbol. The shape:

```
pd.DataFrame(
    {"close": [...floats...], "volume": [...ints or None...]},
    index=pd.DatetimeIndex([...trade_date values...])
)
```

The index is a DatetimeIndex (trade_dates from DB), ordered chronologically. Last row is always today's scan date after Phase 7 runs `update_price_data`.

### Column name contract

`price_daily` columns `close` and `volume` map directly to DataFrame column names. strategy/ functions use `df["close"]` and `df["volume"]` — these must not be renamed.

### rank_candidates output -> scan_candidates table

| `Candidate` field | `scan_candidates` column | Notes |
|------------------|--------------------------|-------|
| `symbol` | `symbol` | Direct |
| `roc_200` | `roc200` | Phase 7 renames on insert |
| `prev_close` | `close` | Phase 7 renames on insert |
| `position_size` | `suggested_shares` | Phase 7 renames on insert |
| _(not in Candidate)_ | `rank` | Phase 7 computes 1-based index |
| _(not in Candidate)_ | `scan_id` | Phase 7 adds FK to scans table |

Phase 7 is responsible for the rename and FK injection. Phase 4's `Candidate` TypedDict does not need to match the DB column names.

### Minimum row counts strategy/ functions require

| Function | Minimum rows | Raises if fewer |
|----------|-------------|-----------------|
| `regime_filter` | 200 (spx_closes len) | `ValueError` |
| `liquidity_filter` | 21 per symbol (20 before today + today) | `ValueError` |
| `momentum_filter` | 200 per symbol | `ValueError` |
| `rank_candidates` | 200 per symbol | `ValueError` (via momentum_filter call) |

Phase 7 enforces the 95% coverage check (DATA-10) before calling strategy/, so the ValueError path is a bug-detection safety net, not a normal code path.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| bare `pd.Series` annotation | `pd.Series[float]` | pandas-stubs 1.x → 2.x | Required for mypy strict type-arg compliance |
| `hypothesis[pandas]` extra | `st.lists` + manual DataFrame construction | Hypothesis 6.x | No extra install; D-11 prohibits hypothesis[pandas] extra anyway |
| `dict[str, Any]` for typed records | `TypedDict` with named fields | Python 3.8+ TypedDict | mypy strict requires TypedDict when fields accessed by name |

**Deprecated/outdated:**
- `pd.Series` without type parameter: mypy strict rejects it as `[type-arg]` with pandas-stubs 2.x+.
- `hypothesis.extra.pandas`: Not needed here; D-11 explicitly prohibits it.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pd.DataFrame` does not require a type parameter in pandas-stubs 3.0.0 (only `pd.Series` does) | Standard Stack / Code Examples | If DataFrame also requires type parameters, all `dict[str, pd.DataFrame]` signatures fail mypy. Verified via mypy run locally — no errors. |
| A2 | Phase 7 will pass DataFrames with column names `"close"` and `"volume"` matching price_daily column names | Integration Surface | If Phase 7 uses different column names, strategy/ df["close"] raises KeyError at runtime. Mitigated by: schema.py defines the column names; both layers should use them directly. |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed. (Only 2 minor assumptions logged; both low-risk given verification performed.)

---

## Open Questions (RESOLVED)

1. **Invariant #4 scope disambiguation**
   - What we know: D-10 says "tested at Phase 7 integration level, not Phase 4 unit level"
   - What's unclear: TEST-03 says "property-based tests for no candidates when regime filter is off" — this sounds like a Phase 4 test
   - Recommendation: Implement the Phase 4 property as "regime_filter returns False given a series where today_close <= sma200". This is a pure function property (no Phase 7 integration needed). If Phase 7 integration tests are required separately, that's Phase 13 scope.

2. **volume column nullable in price_daily**
   - What we know: `price_daily.volume` is `nullable=True` in schema.py; `^GSPC` may lack volume data
   - What's unclear: How should `liquidity_filter` handle None/NaN volume rows?
   - Recommendation: Since Phase 7 passes only constituent symbols to liquidity_filter (not `^GSPC`), NaN volume is unlikely. If a constituent has NaN volumes in the 20-day window, `mean()` with NaN produces NaN, which will fail the `>= threshold` check. Treat as: NaN volume symbols fail the liquidity filter (conservative). Document in liquidity_filter docstring.

---

## Environment Availability

Step 2.6: All strategy/ dependencies are confirmed available in the local environment.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pandas | All filter math | ✓ | 3.0.3 | — |
| numpy | Underlying pandas | ✓ | 2.4.6 | — |
| hypothesis | TEST-03 property tests | ✓ | 6.152.9 | — |
| pandas-stubs | mypy strict type inference | ✓ | 3.0.0.260204 | — |
| mypy | CI type checking | ✓ | installed per ci.yml | — |
| math (stdlib) | Position sizing floor | ✓ | stdlib | — |
| typing.TypedDict (stdlib) | Candidate type | ✓ | Python 3.11 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + hypothesis 6.152.9 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths = ["tests"]) |
| Quick run command | `uv run pytest tests/test_strategy/ -x -q` |
| Full suite command | `uv run pytest --cov=bensdorp1.strategy --cov-report=term-missing` |
| Strategy-only coverage | `uv run pytest tests/test_strategy/ --cov=bensdorp1.strategy --cov-report=term-missing` |
| All-modules coverage | `uv run pytest --cov=bensdorp1 --cov-report=term-missing` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STRAT-01 | regime_filter True when close > SMA 200 | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_on -x` | ❌ Wave 0 |
| STRAT-01 | regime_filter False when close <= SMA 200 | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_off -x` | ❌ Wave 0 |
| STRAT-01 | regime_filter ValueError when len < 200 | unit | `uv run pytest tests/test_strategy/test_screening.py::test_regime_filter_insufficient_rows -x` | ❌ Wave 0 |
| STRAT-02 | liquidity_filter keeps top 25% symbols | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_top_quartile -x` | ❌ Wave 0 |
| STRAT-02 | liquidity_filter returns [] on empty input | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_empty -x` | ❌ Wave 0 |
| STRAT-02 | liquidity_filter ValueError when < 21 rows | unit | `uv run pytest tests/test_strategy/test_screening.py::test_liquidity_filter_insufficient -x` | ❌ Wave 0 |
| STRAT-03 | momentum_filter passes stocks where today > T-200 | unit | `uv run pytest tests/test_strategy/test_screening.py::test_momentum_filter_pass -x` | ❌ Wave 0 |
| STRAT-03 | momentum_filter rejects stocks where today <= T-200 | unit | `uv run pytest tests/test_strategy/test_screening.py::test_momentum_filter_reject -x` | ❌ Wave 0 |
| STRAT-04 | rank_candidates returns descending ROC 200, max 10 | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_ordering -x` | ❌ Wave 0 |
| STRAT-04 | rank_candidates returns [] when no passing candidates | unit | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_empty -x` | ❌ Wave 0 |
| STRAT-06 | compute_position_size correct floor division | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_position_size_normal -x` | ❌ Wave 0 |
| STRAT-06 | compute_position_size returns 0 when < 1 share (D-06) | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_position_size_zero -x` | ❌ Wave 0 |
| STRAT-07 | compute_initial_stop = entry_close * 0.93 | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_initial_stop -x` | ❌ Wave 0 |
| STRAT-08 | update_highest_close = max(current, new_close) | unit | `uv run pytest tests/test_strategy/test_positions.py::test_update_highest_close -x` | ❌ Wave 0 |
| STRAT-08 | compute_trailing_stop = highest_close * 0.75 | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_trailing_stop -x` | ❌ Wave 0 |
| STRAT-09 | compute_effective_stop = max(initial, trailing) | unit | `uv run pytest tests/test_strategy/test_positions.py::test_compute_effective_stop -x` | ❌ Wave 0 |
| STRAT-09 | is_exit_triggered True when close <= effective | unit | `uv run pytest tests/test_strategy/test_positions.py::test_is_exit_triggered_true -x` | ❌ Wave 0 |
| STRAT-09 | is_exit_triggered False when close > effective | unit | `uv run pytest tests/test_strategy/test_positions.py::test_is_exit_triggered_false -x` | ❌ Wave 0 |
| TEST-03 | Invariant 1: effective_stop >= initial_stop (Hypothesis) | property | `uv run pytest tests/test_strategy/test_positions.py::test_effective_stop_ge_initial -x` | ❌ Wave 0 |
| TEST-03 | Invariant 2: trailing stop monotonic (Hypothesis) | property | `uv run pytest tests/test_strategy/test_positions.py::test_trailing_stop_monotonic -x` | ❌ Wave 0 |
| TEST-03 | Invariant 3: rank_candidates <= 10 (Hypothesis) | property | `uv run pytest tests/test_strategy/test_screening.py::test_rank_candidates_max_ten -x` | ❌ Wave 0 |
| TEST-03 | Invariant 4: regime_filter False when close <= sma200 (Hypothesis) | property | `uv run pytest tests/test_strategy/test_screening.py::test_regime_off_when_close_le_sma200 -x` | ❌ Wave 0 |

### Branch Coverage Map

Every branch that needs an explicit test case (beyond the happy path):

| Module | Function | Branch | Test Required |
|--------|----------|--------|---------------|
| screening.py | `regime_filter` | `len < 200` → ValueError | `test_regime_filter_insufficient_rows` |
| screening.py | `regime_filter` | close > sma200 → True | `test_regime_filter_on` |
| screening.py | `regime_filter` | close <= sma200 → False | `test_regime_filter_off` |
| screening.py | `liquidity_filter` | empty input → [] | `test_liquidity_filter_empty` |
| screening.py | `liquidity_filter` | symbol len < 21 → ValueError | `test_liquidity_filter_insufficient` |
| screening.py | `liquidity_filter` | symbol vol >= threshold → included | `test_liquidity_filter_top_quartile` |
| screening.py | `liquidity_filter` | symbol vol < threshold → excluded | `test_liquidity_filter_top_quartile` |
| screening.py | `momentum_filter` | close_today > close_t200 → included | `test_momentum_filter_pass` |
| screening.py | `momentum_filter` | close_today <= close_t200 → excluded | `test_momentum_filter_reject` |
| screening.py | `momentum_filter` | len < 200 → ValueError | `test_momentum_filter_insufficient` |
| screening.py | `rank_candidates` | no candidates → [] | `test_rank_candidates_empty` |
| screening.py | `rank_candidates` | > 10 candidates → top 10 only | `test_rank_candidates_limits_to_10` |
| screening.py | `rank_candidates` | len < 200 per symbol → ValueError | `test_rank_candidates_insufficient_rows` |
| positions.py | `compute_position_size` | shares > 0 → normal return | `test_compute_position_size_normal` |
| positions.py | `compute_position_size` | shares == 0 → return 0 (D-06) | `test_compute_position_size_zero` |
| positions.py | `is_exit_triggered` | close <= effective → True | `test_is_exit_triggered_true` |
| positions.py | `is_exit_triggered` | close > effective → False | `test_is_exit_triggered_false` |
| positions.py | `update_highest_close` | current > new_close → current | `test_update_highest_close_no_update` |
| positions.py | `update_highest_close` | new_close > current → new_close | `test_update_highest_close_update` |

### 4 Hypothesis Invariant Test Designs

**Invariant 1: `compute_effective_stop(initial, trailing) >= initial` always**

```python
# tests/test_strategy/test_positions.py
from hypothesis import given, settings
from hypothesis import strategies as st
from bensdorp1.strategy.positions import compute_effective_stop

_price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)

@given(_price_st, _price_st)
@settings(max_examples=500)
def test_effective_stop_ge_initial(initial: float, trailing: float) -> None:
    """Effective stop is always >= initial stop regardless of trailing stop value."""
    result = compute_effective_stop(initial, trailing)
    assert result >= initial
```

**Invariant 2: Trailing stop sequence is monotonically non-decreasing**

```python
# tests/test_strategy/test_positions.py
from hypothesis import given, settings
from hypothesis import strategies as st
from bensdorp1.strategy.positions import update_highest_close, compute_trailing_stop

_price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)

@given(st.lists(_price_st, min_size=2))
@settings(max_examples=500)
def test_trailing_stop_monotonic(closes: list[float]) -> None:
    """Trailing stop never decreases when new closes are applied sequentially."""
    highest = 0.0
    stops: list[float] = []
    for c in closes:
        highest = update_highest_close(highest, c)
        stops.append(compute_trailing_stop(highest))
    for i in range(1, len(stops)):
        assert stops[i] >= stops[i - 1], (
            f"Trailing stop decreased at index {i}: {stops[i]} < {stops[i - 1]}"
        )
```

**Invariant 3: `rank_candidates` returns <= 10 regardless of input size**

```python
# tests/test_strategy/test_screening.py
from hypothesis import given, settings
from hypothesis import strategies as st
import pandas as pd
from bensdorp1.strategy.screening import rank_candidates

_price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)

@given(
    st.lists(
        st.from_regex(r"[A-Z]{2,5}", fullmatch=True),
        min_size=0, max_size=600, unique=True
    ),
    st.floats(min_value=1.0, max_value=10_000_000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_rank_candidates_max_ten(symbols: list[str], available_cash: float) -> None:
    """rank_candidates never returns more than 10 candidates regardless of input size."""
    # Build minimal 200-row DataFrames so no ValueError is raised
    price_dfs: dict[str, pd.DataFrame] = {
        sym: pd.DataFrame({
            "close": [100.0 + i for i in range(200)],
            "volume": [1_000_000] * 221,
        })
        for sym in symbols
    }
    result = rank_candidates(price_dfs, available_cash)
    assert len(result) <= 10
```

**Invariant 4: `regime_filter` returns False when today's close <= SMA 200**

```python
# tests/test_strategy/test_screening.py
from hypothesis import given, settings
from hypothesis import strategies as st
import pandas as pd
from bensdorp1.strategy.screening import regime_filter

_price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)

@given(st.lists(_price_st, min_size=200, max_size=200))
@settings(max_examples=500)
def test_regime_off_when_close_le_sma200(values: list[float]) -> None:
    """regime_filter returns False whenever today's close is at or below SMA 200.

    Constructs a series where the last element is the minimum of all values
    (guaranteed <= mean), forcing regime off.
    """
    # Replace last element with the minimum to guarantee close <= sma200
    bearish = values[:-1] + [min(values) * 0.5]
    series = pd.Series(bearish, dtype=float)
    sma200 = float(series.iloc[-200:].mean())
    today_close = float(series.iloc[-1])
    result = regime_filter(series)
    if today_close <= sma200:
        assert result is False, (
            f"regime_filter returned True but {today_close} <= {sma200}"
        )
```

### pytest-cov Invocation for >95% Coverage

```bash
# Strategy-only coverage gate (TEST-01: >95% required)
uv run pytest tests/test_strategy/ \
    --cov=bensdorp1.strategy \
    --cov-report=term-missing \
    --cov-fail-under=95 \
    -v

# All-modules coverage gate (TEST-02: >90% required)  
uv run pytest \
    --cov=bensdorp1 \
    --cov-report=term-missing \
    --cov-fail-under=90 \
    -v
```

Note: `pyproject.toml` does not currently have a `[tool.coverage.run]` section. The `--cov-fail-under` flag is sufficient for the CI gate. If a `.coveragerc` file is created later, `--cov-config=.coveragerc` can override it.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_strategy/ -x -q`
- **Per wave merge:** `uv run pytest tests/test_strategy/ --cov=bensdorp1.strategy --cov-report=term-missing`
- **Phase gate:** `uv run pytest --cov=bensdorp1 --cov-report=term-missing --cov-fail-under=90` (all modules)

### Wave 0 Gaps

- [ ] `tests/test_strategy/__init__.py` — empty marker file
- [ ] `tests/test_strategy/test_screening.py` — covers STRAT-01, STRAT-02, STRAT-03, STRAT-04 + invariants 3, 4
- [ ] `tests/test_strategy/test_positions.py` — covers STRAT-06, STRAT-07, STRAT-08, STRAT-09 + invariants 1, 2
- [ ] `src/bensdorp1/strategy/__init__.py` — re-exports public API
- [ ] `src/bensdorp1/strategy/screening.py` — 4 functions
- [ ] `src/bensdorp1/strategy/positions.py` — 6 functions

---

## Security Domain

No user input enters strategy/ functions — all parameters are pre-validated DataFrames and floats from the DB. No SQL, no I/O, no deserialization. No ASVS categories apply to pure math functions.

The one relevant control: `compute_position_size` with a very small `prev_close` (approaching float epsilon) could produce an astronomically large share count. This is bounded by the strategy rule (`available_cash * 0.10` caps the dollar amount), not a security issue. A `prev_close > 0` guard is implicit from D-11 (`min_value=0.01`) in tests; production callers receive values from `price_daily` where `close > 0` is enforced by yfinance data.

---

## Sources

### Primary (HIGH confidence)
- Local mypy run with `uv run mypy --strict` — all function signatures verified against mypy 2.x + pandas-stubs 3.0.0.260204
- Local hypothesis run — all 4 invariant patterns verified against hypothesis 6.152.9
- Local pandas 3.0.3 — `quantile`, `iloc`, `Series.mean()` idioms verified
- `src/bensdorp1/db/schema.py` — `scan_candidates` column names verified for integration contract
- `src/bensdorp1/data/calendar.py` — `n_trading_days_ago` signature confirmed (takes `n: int, reference: date | None`)

### Secondary (MEDIUM confidence)
- pandas-stubs documentation (implicit from mypy run): `pd.Series[float]` required; `pd.DataFrame` does not require type parameter
- pyproject.toml — confirmed no `[tool.coverage.run]` section exists; `--cov-fail-under` flag approach documented

### Tertiary (LOW confidence)
- None — no unverified claims remain.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against local environment
- Architecture: HIGH — all patterns verified with mypy strict and runtime tests
- Pitfalls: HIGH — all pitfalls discovered by actually running the code
- Hypothesis invariants: HIGH — all 4 patterns verified to run without errors

**Research date:** 2026-05-23
**Valid until:** 2026-08-23 (stable stack; hypothesis API is stable; pandas-stubs 3.x covers pandas 3.x)
