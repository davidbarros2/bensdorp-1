"""Tests for STRAT-06 through STRAT-09: position sizing and stop calculations.

Pure computation — no db_engine fixture needed. All functions receive scalar
float/int arguments.

Covers: compute_position_size, compute_initial_stop, update_highest_close,
        compute_trailing_stop, compute_effective_stop, is_exit_triggered.
TEST-03 Hypothesis invariants:
  1. effective_stop >= initial_stop always
  2. trailing stop is monotonically non-decreasing
"""

import math

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

_price_st = st.floats(
    min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False
)


# --- Unit tests ---


def test_compute_position_size_normal() -> None:
    """cash=100000.0, prev_close=50.0 yields 200 shares (floor(10000/50))."""
    result = compute_position_size(100000.0, 50.0)
    assert result == 200
    assert isinstance(result, int)


def test_compute_position_size_zero() -> None:
    """cash=1.0, prev_close=1000.0 yields 0 shares (D-06: return 0 when < 1 share)."""
    result = compute_position_size(1.0, 1000.0)
    assert result == 0
    assert isinstance(result, int)


def test_compute_position_size_zero_price() -> None:
    """Returns 0 when prev_close <= 0.0 (CR-02 guard against division by zero)."""
    result = compute_position_size(100_000.0, 0.0)
    assert result == 0
    assert isinstance(result, int)


def test_compute_position_size_boundary() -> None:
    """cash=100.0, prev_close=10.0 yields 1 share (floor(10.0/10.0) = 1)."""
    result = compute_position_size(100.0, 10.0)
    assert result == 1
    assert isinstance(result, int)


def test_compute_position_size_uses_floor() -> None:
    """compute_position_size uses math.floor, not int truncation."""
    # 10% of 99 = 9.9; 9.9 / 10.0 = 0.99; floor -> 0, not 1
    result = compute_position_size(99.0, 10.0)
    assert result == math.floor((99.0 * 0.10) / 10.0)
    assert isinstance(result, int)


def test_compute_initial_stop() -> None:
    """entry_close=100.0 yields initial stop of 93.0 (STRAT-07)."""
    result = compute_initial_stop(100.0)
    assert result == pytest.approx(93.0)


def test_compute_initial_stop_fractional() -> None:
    """entry_close=50.75 yields 50.75 * 0.93."""
    result = compute_initial_stop(50.75)
    assert result == pytest.approx(50.75 * 0.93)


def test_update_highest_close_update() -> None:
    """new_close=75.0 > current=50.0 returns 75.0."""
    result = update_highest_close(50.0, 75.0)
    assert result == 75.0


def test_update_highest_close_no_update() -> None:
    """new_close=75.0 < current=100.0 returns 100.0 (highest unchanged)."""
    result = update_highest_close(100.0, 75.0)
    assert result == 100.0


def test_update_highest_close_equal() -> None:
    """new_close=50.0 == current=50.0 returns 50.0."""
    result = update_highest_close(50.0, 50.0)
    assert result == 50.0


def test_compute_trailing_stop() -> None:
    """highest_close=100.0 yields trailing stop of 75.0 (STRAT-08)."""
    result = compute_trailing_stop(100.0)
    assert result == pytest.approx(75.0)


def test_compute_effective_stop_initial_wins() -> None:
    """initial_stop=80.0 > trailing_stop=70.0 returns 80.0 (STRAT-09)."""
    result = compute_effective_stop(80.0, 70.0)
    assert result == pytest.approx(80.0)


def test_compute_effective_stop_trailing_wins() -> None:
    """trailing_stop=80.0 > initial_stop=70.0 returns 80.0 (STRAT-09)."""
    result = compute_effective_stop(70.0, 80.0)
    assert result == pytest.approx(80.0)


def test_compute_effective_stop_equal() -> None:
    """initial_stop=75.0 == trailing_stop=75.0 returns 75.0."""
    result = compute_effective_stop(75.0, 75.0)
    assert result == pytest.approx(75.0)


def test_is_exit_triggered_true() -> None:
    """close=50.0 < effective_stop=55.0 returns True (exit signal)."""
    result = is_exit_triggered(50.0, 55.0)
    assert result is True


def test_is_exit_triggered_false() -> None:
    """close=60.0 > effective_stop=55.0 returns False (no exit)."""
    result = is_exit_triggered(60.0, 55.0)
    assert result is False


def test_is_exit_triggered_boundary() -> None:
    """close=55.0 == effective_stop=55.0 returns True (equality triggers exit)."""
    result = is_exit_triggered(55.0, 55.0)
    assert result is True


# --- Hypothesis property tests ---


@given(_price_st, _price_st)
@settings(max_examples=500)
def test_effective_stop_ge_initial(initial: float, trailing: float) -> None:
    """Effective stop is always >= initial stop regardless of trailing stop value."""
    result = compute_effective_stop(initial, trailing)
    assert result >= initial


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
