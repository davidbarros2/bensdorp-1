"""Tests for STRAT-01 through STRAT-04: screening functions in strategy/screening.py.

Pure computation — no db_engine fixture needed. DataFrames constructed inline.
No yfinance or DB — DataFrames constructed in-test from synthetic data.

Covers: regime_filter, liquidity_filter, momentum_filter, rank_candidates.
Hypothesis invariants: 3 (rank_candidates <= 10) and 4 (regime_filter False when close <= SMA 200).
"""

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

_price_st = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)


def build_price_df(
    n_rows: int,
    close_values: list[float],
    volume_values: list[int] | None = None,
) -> pd.DataFrame:
    """Construct a DataFrame with columns 'close' and 'volume' of length n_rows."""
    if volume_values is None:
        volume_values = [1_000_000] * n_rows
    return pd.DataFrame(
        {
            "close": close_values[:n_rows],
            "volume": volume_values[:n_rows],
        }
    )


# --- regime_filter unit tests ---


def test_regime_filter_on() -> None:
    """Returns True when today's close is well above the SMA 200."""
    # 199 rows of 100.0 + 1 final row of 1000.0; sma200 will be ~104.5; close=1000
    values = [100.0] * 199 + [1000.0]
    series = pd.Series(values, dtype=float)
    assert regime_filter(series) is True


def test_regime_filter_off() -> None:
    """Returns False when today's close is well below the SMA 200."""
    # 199 rows of 100.0 + 1 final row of 0.01; sma200 will be ~99.96; close=0.01
    values = [100.0] * 199 + [0.01]
    series = pd.Series(values, dtype=float)
    assert regime_filter(series) is False


def test_regime_filter_boundary() -> None:
    """Returns False when today's close equals SMA 200 (strict greater-than required)."""
    values = [100.0] * 200
    series = pd.Series(values, dtype=float)
    # close == sma200 == 100.0; strict > is False
    assert regime_filter(series) is False


def test_regime_filter_insufficient_rows() -> None:
    """Raises ValueError with descriptive message when fewer than 200 rows provided."""
    series = pd.Series([1.0] * 50, dtype=float)
    with pytest.raises(ValueError, match=r"need >= 200"):
        regime_filter(series)


# --- liquidity_filter unit tests ---


def test_liquidity_filter_top_quartile() -> None:
    """Keeps only symbols at or above the 75th percentile of 20-day average volume."""
    # 4 symbols with avg volumes 100, 200, 300, 400; 75th percentile = 325.0
    # Symbols with avg volume >= 325 (i.e., 400) should be included.
    # Quantile(0.75) of [100, 200, 300, 400] = 325.0
    def make_df(avg_vol: int) -> pd.DataFrame:
        # 21 rows: first 20 are T-20 through T-1, last is today
        return pd.DataFrame(
            {
                "close": [100.0] * 21,
                "volume": [avg_vol] * 21,
            }
        )

    price_dfs = {
        "A": make_df(100),
        "B": make_df(200),
        "C": make_df(300),
        "D": make_df(400),
    }
    result = liquidity_filter(price_dfs)
    # 75th percentile of [100, 200, 300, 400] = 325.0
    # Only D (400) is >= 325
    assert "D" in result
    assert "A" not in result
    assert "B" not in result


def test_liquidity_filter_empty() -> None:
    """Returns empty list when price_dfs is empty."""
    assert liquidity_filter({}) == []


def test_liquidity_filter_insufficient() -> None:
    """Raises ValueError when a symbol has fewer than 21 rows."""
    price_dfs = {
        "AAPL": pd.DataFrame(
            {
                "close": [100.0] * 20,
                "volume": [1_000_000] * 20,
            }
        )
    }
    with pytest.raises(ValueError, match=r"needs >= 21"):
        liquidity_filter(price_dfs)


def test_liquidity_filter_nan_volume() -> None:
    """Excludes symbols whose 20-day volume window contains NaN (conservative behavior)."""
    import numpy as np

    # Two symbols: one with valid volume, one with NaN in the 20-day window
    def make_valid_df() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": [100.0] * 21,
                "volume": [1_000_000] * 21,
            }
        )

    nan_volumes = [float("nan")] * 20 + [1_000_000]
    nan_df = pd.DataFrame(
        {
            "close": [100.0] * 21,
            "volume": nan_volumes,
        }
    )

    price_dfs = {
        "GOOD": make_valid_df(),
        "NAN": nan_df,
    }
    result = liquidity_filter(price_dfs)
    # NAN symbol has NaN mean, which fails >= threshold — excluded
    assert "NAN" not in result
    assert "GOOD" in result


# --- momentum_filter unit tests ---


def test_momentum_filter_pass() -> None:
    """Includes symbol when today's close is strictly above close 200 rows ago."""
    closes = [100.0] * 199 + [150.0]  # 200 rows; close[-1]=150 > close[-200]=100
    df = build_price_df(200, closes)
    result = momentum_filter({"AAPL": df})
    assert "AAPL" in result


def test_momentum_filter_reject() -> None:
    """Excludes symbol when today's close is below close 200 rows ago."""
    closes = [100.0] * 199 + [50.0]  # close[-1]=50 < close[-200]=100
    df = build_price_df(200, closes)
    result = momentum_filter({"AAPL": df})
    assert "AAPL" not in result


def test_momentum_filter_boundary() -> None:
    """Excludes symbol when today's close equals close 200 rows ago (strict > required)."""
    closes = [100.0] * 200  # close[-1] == close[-200] == 100.0
    df = build_price_df(200, closes)
    result = momentum_filter({"AAPL": df})
    assert "AAPL" not in result


def test_momentum_filter_insufficient() -> None:
    """Raises ValueError when symbol has fewer than 200 rows."""
    df = build_price_df(199, [100.0] * 199)
    with pytest.raises(ValueError, match=r"needs >= 200"):
        momentum_filter({"AAPL": df})


# --- rank_candidates unit tests ---


def test_rank_candidates_ordering() -> None:
    """Returns candidates sorted descending by roc_200, limited to top 10."""
    # Build 15 symbols with distinct close values so ROC differs
    price_dfs: dict[str, pd.DataFrame] = {}
    for i in range(15):
        # close[-1] = 100 + i*5; close[-200] = 50 (same for all)
        # roc_200 = (close_today / 50) - 1
        closes = [50.0] + [75.0] * 198 + [100.0 + i * 5]
        df = build_price_df(200, closes)
        price_dfs[f"SYM{i:02d}"] = df

    result = rank_candidates(price_dfs, available_cash=100_000.0)
    assert len(result) == 10
    # Verify descending order
    for i in range(1, len(result)):
        assert result[i]["roc_200"] <= result[i - 1]["roc_200"]


def test_rank_candidates_limits_to_10() -> None:
    """Returns at most 10 candidates even when more than 10 symbols are provided."""
    price_dfs: dict[str, pd.DataFrame] = {}
    for i in range(20):
        closes = [50.0] + [75.0] * 198 + [100.0 + i]
        df = build_price_df(200, closes)
        price_dfs[f"SYM{i:02d}"] = df

    result = rank_candidates(price_dfs, available_cash=100_000.0)
    assert len(result) <= 10


def test_rank_candidates_empty() -> None:
    """Returns empty list when price_dfs is empty."""
    result = rank_candidates({}, 100_000.0)
    assert result == []


def test_rank_candidates_insufficient_rows() -> None:
    """Raises ValueError when a symbol has fewer than 200 rows."""
    df = build_price_df(199, [100.0] * 199)
    with pytest.raises(ValueError, match=r"need >= 200|needs >= 200"):
        rank_candidates({"AAPL": df}, 100_000.0)


def test_rank_candidates_zero_position_size() -> None:
    """Returns position_size of 0 when floor division gives less than 1 share."""
    # available_cash=0.01, prev_close=10000.0
    # floor((0.01 * 0.10) / 10000.0) = floor(0.000_0001) = 0
    closes = [10000.0] * 200
    df = build_price_df(200, closes)
    result = rank_candidates({"AAPL": df}, available_cash=0.01)
    assert len(result) == 1
    assert result[0]["position_size"] == 0


# --- Hypothesis property tests ---


@given(
    st.lists(
        st.from_regex(r"[A-Z]{2,5}", fullmatch=True),
        min_size=0,
        max_size=600,
        unique=True,
    ),
    st.floats(
        min_value=1.0,
        max_value=10_000_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
)
@settings(max_examples=200)
def test_rank_candidates_max_ten(symbols: list[str], available_cash: float) -> None:
    """rank_candidates never returns more than 10 candidates regardless of input size."""
    price_dfs: dict[str, pd.DataFrame] = {
        sym: pd.DataFrame(
            {
                "close": [100.0 + i for i in range(200)],
                "volume": [1_000_000] * 200,
            }
        )
        for sym in symbols
    }
    result = rank_candidates(price_dfs, available_cash)
    assert len(result) <= 10


@given(st.lists(_price_st, min_size=200, max_size=200))
@settings(max_examples=500)
def test_regime_off_when_close_le_sma200(values: list[float]) -> None:
    """regime_filter returns False whenever today's close is at or below SMA 200.

    Constructs a series where the last element is the minimum of all values
    (guaranteed <= mean), forcing regime off.
    """
    # Replace last element with min(values)*0.5 to guarantee close <= sma200
    bearish = values[:-1] + [min(values) * 0.5]
    series = pd.Series(bearish, dtype=float)
    sma200 = float(series.iloc[-200:].mean())
    today_close = float(series.iloc[-1])
    result = regime_filter(series)
    if today_close <= sma200:
        assert result is False, (
            f"regime_filter returned True but {today_close} <= {sma200}"
        )
