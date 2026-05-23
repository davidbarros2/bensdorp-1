# Phase 4: Strategy Logic - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 6
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/bensdorp1/strategy/__init__.py` | package init | N/A | `src/bensdorp1/db/__init__.py` | exact |
| `src/bensdorp1/strategy/screening.py` | utility (pure math) | transform | `src/bensdorp1/data/calendar.py` | role-match |
| `src/bensdorp1/strategy/positions.py` | utility (pure math) | transform | `src/bensdorp1/data/calendar.py` | role-match |
| `tests/test_strategy/__init__.py` | test package marker | N/A | `tests/__init__.py` | exact |
| `tests/test_strategy/test_screening.py` | test | transform | `tests/test_data_calendar.py` | role-match |
| `tests/test_strategy/test_positions.py` | test | transform | `tests/test_data_calendar.py` | role-match |

---

## Pattern Assignments

### `src/bensdorp1/strategy/__init__.py` (package init)

**Analog:** `src/bensdorp1/db/__init__.py` (lines 1–13)

**Module docstring pattern:**
```python
"""Public surface of the bensdorp1.db subpackage."""
```

**Import re-export pattern** (lines 3–5):
```python
from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.backup import create_backup
from bensdorp1.db.engine import get_engine, run_migrations
```

**`__all__` pattern** (lines 7–13):
```python
__all__ = [
    "AuditEventType",
    "create_backup",
    "get_engine",
    "log_event",
    "run_migrations",
]
```

**How to apply to `strategy/__init__.py`:**

- Replace the module docstring to describe the `strategy/` subpackage. Include a note that all exported names are pure functions with no I/O or DB dependency.
- Replace the `from bensdorp1.db.*` lines with explicit imports from `bensdorp1.strategy.screening` and `bensdorp1.strategy.positions`.
- `Candidate` TypedDict must appear in `__all__` (see RESEARCH.md Pitfall 6: mypy strict `no_implicit_reexport` requires explicit re-export of TypedDict).
- Do NOT use `from .screening import *` — mypy strict requires named imports.

**`data/__init__.py`** is a secondary reference showing the same pattern with an out-of-scope note in the docstring (lines 1–19 of `src/bensdorp1/data/__init__.py`) — copy this style when there are notes to add:
```python
"""Public surface of the bensdorp1.data subpackage.

DATA-06 (split detection and automatic position adjustment) is OUT OF SCOPE for Phase 3.
Split detection is owned by Phase 11 (Catch-Up Logic). See ROADMAP.md §Phase 11.
"""
```

---

### `src/bensdorp1/strategy/screening.py` (utility, transform)

**Analog:** `src/bensdorp1/data/calendar.py`

**Module docstring + dependency note pattern** (lines 1–7):
```python
"""NYSE trading-day wrappers using pandas_market_calendars v5.

No I/O — pure computation over the NYSE holiday calendar.
DATA-07: NYSE market calendar via pandas_market_calendars for trading-day arithmetic.
Depends on: pandas_market_calendars>=5.3.2 (zoneinfo-based, no pytz)
Used by: data/prices.py, commands/scan.py (Phase 7), commands/init.py (Phase 6)
"""
```
Apply to `screening.py`: lead with "No I/O — pure filter math over pre-fetched DataFrames." List each STRAT requirement ID satisfied. Name the Used-by callers (Phase 7 scan command).

**Import block pattern** (lines 9–12):
```python
from datetime import date, timedelta

import pandas as pd
import pandas_market_calendars as mcal
```
Apply to `screening.py`: replace with stdlib imports first (`math`, `typing`), then third-party (`import pandas as pd`). No imports from `bensdorp1.db` or `bensdorp1.data` — violates D-02.

**Function signature + docstring pattern** (lines 17–22 of `calendar.py`):
```python
def get_trading_days(start: date, end: date) -> pd.DatetimeIndex:
    """Return NYSE trading days between start and end (inclusive), UTC timezone."""
    return _NYSE.valid_days(  # type: ignore[no-any-return]
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
```
Apply to `screening.py` functions:
- Every function has an explicit return type annotation (mypy strict).
- One-line summary followed by blank line then expanded docstring with arg/raises/returns sections (see `n_trading_days_ago` lines 35–43 of `calendar.py` for the expanded form).

**ValueError pattern with message** (lines 51–52 of `calendar.py`):
```python
if len(days) < n:
    raise ValueError(f"Not enough trading days in range for n={n}")
```
Apply to `screening.py` per D-07: check row count before indexing, raise `ValueError` with a message stating expected vs. actual. Example: `f"regime_filter: need >= 200 closes; got {len(spx_closes)}"`.

**Concrete signatures for `screening.py` (from RESEARCH.md, verified mypy strict):**
```python
def regime_filter(spx_closes: pd.Series[float]) -> bool: ...
def liquidity_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]: ...
def momentum_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]: ...
def rank_candidates(
    price_dfs: dict[str, pd.DataFrame],
    available_cash: float,
) -> list[Candidate]: ...
```

**TypedDict placement:** Define `Candidate` at module level before the functions that reference it, after imports:
```python
from typing import TypedDict

class Candidate(TypedDict):
    symbol: str
    roc_200: float
    prev_close: float
    position_size: int
```

---

### `src/bensdorp1/strategy/positions.py` (utility, transform)

**Analog:** `src/bensdorp1/data/calendar.py`

**Module docstring pattern** (same template as `calendar.py` lines 1–7): lead with "No I/O — pure stop arithmetic." List STRAT-06 through STRAT-09. List Used-by callers (Phase 7 scan command, Phase 8 buy command).

**Import block:** `positions.py` uses only `math` from stdlib. No pandas, no numpy, no project imports.
```python
import math
```

**Single-line function docstring pattern** (e.g., `is_trading_day` lines 25–26):
```python
def is_trading_day(dt: date) -> bool:
    """Return True if dt is a NYSE trading day."""
```
Apply to trivial one-liner functions in `positions.py`:
```python
def compute_initial_stop(entry_close: float) -> float:
    """Return initial stop: entry_close * 0.93. Set once; never changes."""
    return entry_close * 0.93
```

**Concrete signatures for `positions.py` (from RESEARCH.md, verified mypy strict):**
```python
def compute_position_size(available_cash: float, prev_close: float) -> int: ...
def compute_initial_stop(entry_close: float) -> float: ...
def update_highest_close(current: float, new_close: float) -> float: ...
def compute_trailing_stop(highest_close: float) -> float: ...
def compute_effective_stop(initial_stop: float, trailing_stop: float) -> float: ...
def is_exit_triggered(close: float, effective_stop: float) -> bool: ...
```

---

### `tests/test_strategy/__init__.py` (test package marker)

**Analog:** `tests/__init__.py`

The existing `tests/__init__.py` is an empty file (one blank line). `tests/test_strategy/__init__.py` must be the same: an empty file with no content. No docstring, no imports.

---

### `tests/test_strategy/test_screening.py` (test, transform)

**Analog:** `tests/test_data_calendar.py`

**Module docstring pattern** (lines 1–6 of `test_data_calendar.py`):
```python
"""Tests for DATA-07: NYSE calendar wrappers in data/calendar.py.

Pure computation — no db_engine fixture needed. Tests verify trading-day
exclusion, n_trading_days_ago arithmetic, and is_trading_day accuracy.

Analog: tests/test_db_engine.py
"""
```
Apply to `test_screening.py`: describe STRAT-01 through STRAT-04 + TEST-03 invariants 3 and 4. Note "Pure computation — no db_engine fixture needed." Note "No yfinance or DB — DataFrames constructed in-test."

**Import block pattern** (lines 8–13 of `test_data_calendar.py`):
```python
from datetime import date

import pytest

from bensdorp1.data.calendar import get_trading_days, is_trading_day, n_trading_days_ago
```
Apply to `test_screening.py`:
```python
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bensdorp1.strategy.screening import (
    Candidate,
    liquidity_filter,
    momentum_filter,
    rank_candidates,
    regime_filter,
)
```

**Test function naming convention** (lines 16–71 of `test_data_calendar.py`): `test_<function>_<scenario>` — descriptive verb phrases. Examples from analog: `test_get_trading_days_excludes_new_years_day`, `test_n_trading_days_ago_skips_weekend`.

Apply to `test_screening.py`: `test_regime_filter_on`, `test_regime_filter_off`, `test_regime_filter_insufficient_rows`, `test_liquidity_filter_top_quartile`, `test_liquidity_filter_empty`, `test_liquidity_filter_insufficient`, `test_momentum_filter_pass`, `test_momentum_filter_reject`, `test_rank_candidates_ordering`, `test_rank_candidates_limits_to_10`.

**ValueError assertion pattern** (lines 68–71 of `test_data_calendar.py`):
```python
def test_n_trading_days_ago_raises_when_buffer_insufficient() -> None:
    """Requesting 10000 trading days raises ValueError with expected message."""
    with pytest.raises(ValueError, match=r"Not enough trading days"):
        n_trading_days_ago(10000)
```
Apply to ValueError tests in `test_screening.py` — use `pytest.raises(ValueError, match=r"...")` for all D-07 row-count error tests.

**One-line docstring per test** (line 17, 24, 29, 34, 39 of `test_data_calendar.py`): every test function has exactly one descriptive docstring sentence explaining what it verifies.

**Hypothesis test section placement:** Property-based tests go after all unit tests in the file. Use a blank line + comment separator: `# --- Hypothesis property tests ---`.

**Hypothesis `_price_st` strategy definition** (shared between files, from RESEARCH.md D-11):
```python
_price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)
```
Define at module level before the property test functions. This definition is the same in both test files.

**Invariant 3 test structure** (from RESEARCH.md, verified hypothesis 6.152.9):
```python
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

**Invariant 4 test structure** (from RESEARCH.md):
```python
@given(st.lists(_price_st, min_size=200, max_size=200))
@settings(max_examples=500)
def test_regime_off_when_close_le_sma200(values: list[float]) -> None:
    """regime_filter returns False whenever today's close is at or below SMA 200."""
    bearish = values[:-1] + [min(values) * 0.5]
    series = pd.Series(bearish, dtype=float)
    sma200 = float(series.iloc[-200:].mean())
    today_close = float(series.iloc[-1])
    result = regime_filter(series)
    if today_close <= sma200:
        assert result is False
```

---

### `tests/test_strategy/test_positions.py` (test, transform)

**Analog:** `tests/test_data_calendar.py`

Same conventions as `test_screening.py` above. Apply to the positions module:

**Module docstring pattern:**
```python
"""Tests for STRAT-06 through STRAT-09: position sizing and stop calculations.

Pure computation — no db_engine fixture needed. DataFrames are not used here;
all functions receive scalar float/int arguments.

Covers: compute_position_size, compute_initial_stop, update_highest_close,
        compute_trailing_stop, compute_effective_stop, is_exit_triggered.
Hypothesis invariants: effective_stop >= initial_stop, trailing stop monotonic.
"""
```

**Import block:**
```python
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bensdorp1.strategy.positions import (
    compute_effective_stop,
    compute_initial_stop,
    compute_position_size,
    compute_trailing_stop,
    is_exit_triggered,
    update_highest_close,
)
```

**Unit test naming:** `test_compute_position_size_normal`, `test_compute_position_size_zero`, `test_compute_initial_stop`, `test_update_highest_close_update`, `test_update_highest_close_no_update`, `test_compute_trailing_stop`, `test_compute_effective_stop`, `test_is_exit_triggered_true`, `test_is_exit_triggered_false`.

**One-line docstrings:** Same convention as `test_data_calendar.py` — one sentence per test explaining the assertion.

**Invariant 1 test structure** (from RESEARCH.md, verified):
```python
_price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)

@given(_price_st, _price_st)
@settings(max_examples=500)
def test_effective_stop_ge_initial(initial: float, trailing: float) -> None:
    """Effective stop is always >= initial stop regardless of trailing stop value."""
    result = compute_effective_stop(initial, trailing)
    assert result >= initial
```

**Invariant 2 test structure** (from RESEARCH.md, verified):
```python
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

---

## Shared Patterns

### Module-level docstring format
**Source:** `src/bensdorp1/data/calendar.py` lines 1–7; `src/bensdorp1/db/__init__.py` line 1
**Apply to:** `strategy/__init__.py`, `strategy/screening.py`, `strategy/positions.py`

Every module opens with a triple-quoted docstring. Implementation modules (calendar.py) include: purpose summary, "No I/O" declaration, relevant requirement IDs, dependencies, and "Used by" list. Package `__init__.py` files use a one-line or two-line docstring.

### Explicit return type annotations (mypy strict)
**Source:** `src/bensdorp1/data/calendar.py` — every function has explicit return type
**Apply to:** All functions in `screening.py` and `positions.py`

```python
# calendar.py lines 17, 25, 35
def get_trading_days(start: date, end: date) -> pd.DatetimeIndex:
def is_trading_day(dt: date) -> bool:
def n_trading_days_ago(n: int, reference: date | None = None) -> date:
```
No bare `pd.Series` — always `pd.Series[float]` (RESEARCH.md Pitfall 2, Pattern 1).

### `__all__` list with named exports
**Source:** `src/bensdorp1/db/__init__.py` lines 7–13; `src/bensdorp1/data/__init__.py` lines 11–18
**Apply to:** `strategy/__init__.py`

Alphabetically sorted `__all__` list. Each name is a string literal. `Candidate` TypedDict must be included — mypy strict `no_implicit_reexport` requires it.

### ValueError message with context
**Source:** `src/bensdorp1/data/calendar.py` lines 51–52
**Apply to:** All row-count guard branches in `screening.py`

Pattern: `raise ValueError(f"<function_name>: <what was needed>; got {actual}")`. Always include both the expected minimum and the actual count.

### Test docstring per function
**Source:** `tests/test_data_calendar.py` — every test has a one-sentence docstring
**Apply to:** All test functions in `test_screening.py` and `test_positions.py`

### `pytest.raises` with `match=` argument
**Source:** `tests/test_data_calendar.py` lines 68–71
**Apply to:** All ValueError test cases in `test_screening.py`

```python
with pytest.raises(ValueError, match=r"need >= 200"):
    regime_filter(pd.Series([1.0] * 50, dtype=float))
```

### No `conftest.py` needed for pure-function tests
**Source:** `tests/test_data_calendar.py` — imports no fixtures, no `db_engine`
**Apply to:** `tests/test_strategy/test_screening.py` and `tests/test_strategy/test_positions.py`

`strategy/` has no DB dependency (D-02). No `conftest.py` is needed in `tests/test_strategy/`. DataFrames are constructed inline in each test.

### `pyproject.toml` — no changes required
**Source:** `pyproject.toml` lines 67–68

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

`testpaths = ["tests"]` already covers `tests/test_strategy/` by subdirectory. No new pytest configuration is needed. No new runtime or dev dependencies are needed (pandas, numpy, hypothesis are already declared).

---

## No Analog Found

All 6 files have close analogs in the codebase. No file requires falling back to RESEARCH.md patterns exclusively.

---

## Metadata

**Analog search scope:** `src/bensdorp1/`, `tests/`
**Files read:** 9 (`db/__init__.py`, `data/__init__.py`, `data/calendar.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_data_calendar.py`, `tests/test_db_audit.py`, `tests/test_data_prices.py`, `pyproject.toml`)
**Pattern extraction date:** 2026-05-23
