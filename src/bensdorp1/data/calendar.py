"""NYSE trading-day wrappers using pandas_market_calendars v5.

No I/O — pure computation over the NYSE holiday calendar.
DATA-07: NYSE market calendar via pandas_market_calendars for trading-day arithmetic.
Depends on: pandas_market_calendars>=5.3.2 (zoneinfo-based, no pytz)
Used by: data/prices.py, commands/scan.py (Phase 7), commands/init.py (Phase 6)
"""

from datetime import date, timedelta

import pandas as pd
import pandas_market_calendars as mcal

_NYSE = mcal.get_calendar("NYSE")  # module-level; created once at import


def get_trading_days(start: date, end: date) -> pd.DatetimeIndex:
    """Return NYSE trading days between start and end (inclusive), UTC timezone."""
    return _NYSE.valid_days(  # type: ignore[no-any-return]
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )


def is_trading_day(dt: date) -> bool:
    """Return True if dt is a NYSE trading day."""
    ts = pd.Timestamp(dt).normalize().tz_localize("UTC")
    days = get_trading_days(dt, dt)
    return ts in days


_MAX_LOOKBACK_DAYS = 3650  # ~10 years; caps memory use and makes ValueError reachable


def n_trading_days_ago(n: int, reference: date | None = None) -> date:
    """Return the date that was N NYSE trading days before reference (default: today).

    The reference date itself is excluded: n=1 returns the most recent trading
    day strictly before reference.

    Raises ValueError when n exceeds the number of trading days in the lookback
    window (capped at _MAX_LOOKBACK_DAYS calendar days).
    """
    ref = reference or date.today()
    # Exclude the reference day by ending one calendar day earlier
    end = ref - timedelta(days=1)
    # Use the smaller of the adaptive buffer and the fixed max lookback
    lookback = min(int(n * 1.5) + 30, _MAX_LOOKBACK_DAYS)
    start = ref - timedelta(days=lookback)
    days = get_trading_days(start, end)
    if len(days) < n:
        raise ValueError(f"Not enough trading days in range for n={n}")
    return days[-n].date()
