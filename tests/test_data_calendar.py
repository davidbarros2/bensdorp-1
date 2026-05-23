"""Tests for DATA-07: NYSE calendar wrappers in data/calendar.py.

Pure computation — no db_engine fixture needed. Tests verify trading-day
exclusion, n_trading_days_ago arithmetic, and is_trading_day accuracy.

Analog: tests/test_db_engine.py
"""

from datetime import date

import pytest

from bensdorp1.data.calendar import get_trading_days, is_trading_day, n_trading_days_ago


def test_get_trading_days_excludes_new_years_day() -> None:
    """New Year's Day (2025-01-01) is a holiday and must not appear in results."""
    days = get_trading_days(date(2025, 1, 1), date(2025, 1, 5))
    dates = [d.date() for d in days]
    assert date(2025, 1, 1) not in dates


def test_get_trading_days_excludes_weekends() -> None:
    """Saturday 2025-01-04 and Sunday 2025-01-05 are weekends; range returns empty."""
    days = get_trading_days(date(2025, 1, 4), date(2025, 1, 5))
    assert len(days) == 0


def test_is_trading_day_true_for_thursday() -> None:
    """2025-01-02 is a regular Thursday session — must return True."""
    assert is_trading_day(date(2025, 1, 2)) is True


def test_is_trading_day_false_for_saturday() -> None:
    """2025-01-04 is a Saturday — must return False."""
    assert is_trading_day(date(2025, 1, 4)) is False


def test_is_trading_day_false_for_holiday() -> None:
    """2025-01-01 is New Year's Day (NYSE holiday) — must return False."""
    assert is_trading_day(date(2025, 1, 1)) is False


def test_n_trading_days_ago_one_step() -> None:
    """One trading day before Friday 2025-01-03 is Thursday 2025-01-02."""
    result = n_trading_days_ago(1, reference=date(2025, 1, 3))
    assert result == date(2025, 1, 2)


def test_n_trading_days_ago_skips_weekend() -> None:
    """One trading day before Monday 2025-01-06 skips the weekend to Friday 2025-01-03.

    Monday Jan 6 -> Friday Jan 3, skipping Saturday and Sunday.
    """
    result = n_trading_days_ago(1, reference=date(2025, 1, 6))
    assert result == date(2025, 1, 3)


def test_n_trading_days_ago_220_does_not_raise() -> None:
    """220 trading days before 2025-12-31 returns a date without raising.

    Validates the DATA-04 use case: 220-day lookback for price history.
    """
    result = n_trading_days_ago(220, reference=date(2025, 12, 31))
    assert isinstance(result, date)


def test_n_trading_days_ago_raises_when_buffer_insufficient() -> None:
    """Requesting 10000 trading days raises ValueError with expected message."""
    with pytest.raises(ValueError, match=r"Not enough trading days"):
        n_trading_days_ago(10000)
