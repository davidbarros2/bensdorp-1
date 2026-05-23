"""Tests for DATA-03, DATA-04, DATA-08, DATA-09, DATA-10: price download,
normalization, retry, coverage.

Uses db_engine fixture for DB-state assertions. yfinance.download and
time.sleep are mocked via unittest.mock.patch.
"""

import json
from datetime import UTC, date, datetime, timedelta
from unittest.mock import call, patch

import numpy as np
import pandas as pd
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Engine

from bensdorp1.data import prices as prices_module
from bensdorp1.data.prices import check_price_coverage, update_price_data
from bensdorp1.db.schema import audit_log, constituents_cache, price_daily

# ---------------------------------------------------------------------------
# Helper factories for constructing mock yfinance DataFrames
# ---------------------------------------------------------------------------


def _make_bulk_df(
    tickers: list[str],
    dates: list[date],
    closes: dict[str, list[float]],
    volumes: dict[str, list[int]],
) -> pd.DataFrame:
    """Construct a DataFrame with 2-level column MultiIndex (Price, Ticker).

    Simulates yfinance bulk download output before stacking.
    Indexed by pd.DatetimeIndex(dates, tz="UTC").
    Closes/volumes may contain np.nan to simulate failed tickers.
    """
    index = pd.DatetimeIndex(
        [pd.Timestamp(d, tz="UTC") for d in dates], name="Date"
    )
    col_tuples = [(field, tkr) for tkr in tickers for field in ("Close", "Volume")]
    columns = pd.MultiIndex.from_tuples(col_tuples, names=["Price", "Ticker"])
    data: dict[tuple[str, str], object] = {}
    for tkr in tickers:
        data[("Close", tkr)] = closes.get(tkr, [np.nan] * len(dates))
        data[("Volume", tkr)] = volumes.get(tkr, [0] * len(dates))
    df = pd.DataFrame(data, index=index, columns=columns)
    return df


def _make_single_df(
    dates: list[date],
    closes: list[float],
    volumes: list[int],
) -> pd.DataFrame:
    """Construct a single-ticker DataFrame with flat columns Close/Volume.

    Simulates yfinance single-ticker download (multi_level_index=False).
    """
    index = pd.DatetimeIndex(
        [pd.Timestamp(d, tz="UTC") for d in dates], name="Date"
    )
    return pd.DataFrame({"Close": closes, "Volume": volumes}, index=index)


# ---------------------------------------------------------------------------
# Tests: DATA-08 ticker normalization helpers
# ---------------------------------------------------------------------------


def test_to_yfinance_period_to_hyphen() -> None:
    """DATA-08: _to_yfinance converts period form to hyphen form."""
    assert prices_module._to_yfinance("BRK.B") == "BRK-B"


def test_to_yfinance_gspc_is_no_op() -> None:
    """D-04 + DATA-08: ^GSPC is unchanged by _to_yfinance (no dot to replace)."""
    assert prices_module._to_yfinance("^GSPC") == "^GSPC"


def test_to_yfinance_plain_ticker_unchanged() -> None:
    """DATA-08: plain tickers without dots are unchanged by _to_yfinance."""
    assert prices_module._to_yfinance("AAPL") == "AAPL"


def test_to_db_hyphen_to_period() -> None:
    """DATA-08: _to_db converts hyphen form back to period form."""
    assert prices_module._to_db("BRK-B") == "BRK.B"


def test_to_db_gspc_is_no_op() -> None:
    """DATA-08: ^GSPC is unchanged by _to_db (no hyphen to replace)."""
    assert prices_module._to_db("^GSPC") == "^GSPC"


# ---------------------------------------------------------------------------
# Tests: DATA-03 auto_adjust=True and D-04 ^GSPC always included
# ---------------------------------------------------------------------------


def test_download_called_with_auto_adjust_true(db_engine: Engine) -> None:
    """DATA-03: yfinance.download is always called with auto_adjust=True."""
    mock_df = _make_bulk_df(
        ["AAPL", "^GSPC"],
        [date(2025, 1, 2)],
        {"AAPL": [150.0], "^GSPC": [4700.0]},
        {"AAPL": [1000], "^GSPC": [2000]},
    )
    with patch("yfinance.download", return_value=mock_df) as mock_dl:
        update_price_data(db_engine, ["AAPL"])
    # The first (bulk) call must have auto_adjust=True
    first_call_kwargs = mock_dl.call_args_list[0].kwargs
    assert first_call_kwargs.get("auto_adjust") is True


def test_download_includes_gspc(db_engine: Engine) -> None:
    """D-04: update_price_data always adds ^GSPC to the ticker list."""
    mock_df = _make_bulk_df(
        ["AAPL", "^GSPC"],
        [date(2025, 1, 2)],
        {"AAPL": [150.0], "^GSPC": [4700.0]},
        {"AAPL": [1000], "^GSPC": [2000]},
    )
    with patch("yfinance.download", return_value=mock_df) as mock_dl:
        update_price_data(db_engine, ["AAPL"])
    first_call_tickers = mock_dl.call_args_list[0].args[0]
    assert "^GSPC" in first_call_tickers


# ---------------------------------------------------------------------------
# Test: DATA-04 220-day default date range
# ---------------------------------------------------------------------------


def test_220_days_range_default(db_engine: Engine) -> None:
    """DATA-04: default date range is today minus 350 calendar days through today."""
    mock_df = _make_bulk_df(
        ["AAPL", "^GSPC"],
        [date(2025, 1, 2)],
        {"AAPL": [150.0], "^GSPC": [4700.0]},
        {"AAPL": [1000], "^GSPC": [2000]},
    )
    today = date.today()
    expected_start = (today - timedelta(days=350)).isoformat()
    expected_end = today.isoformat()
    with patch("yfinance.download", return_value=mock_df) as mock_dl:
        update_price_data(db_engine, ["AAPL"])
    first_call_kwargs = mock_dl.call_args_list[0].kwargs
    assert first_call_kwargs.get("end") == expected_end
    assert first_call_kwargs.get("start") == expected_start


# ---------------------------------------------------------------------------
# Tests: DATA-08 ticker normalization round-trip in DB and yfinance calls
# ---------------------------------------------------------------------------


def test_ticker_normalization_period_stored_in_db(db_engine: Engine) -> None:
    """DATA-08: period form (BRK.B) is stored in price_daily, not hyphen form."""
    mock_df = _make_bulk_df(
        ["BRK-B", "^GSPC"],
        [date(2025, 1, 2)],
        {"BRK-B": [200.0], "^GSPC": [4700.0]},
        {"BRK-B": [500], "^GSPC": [2000]},
    )
    with patch("yfinance.download", return_value=mock_df):
        update_price_data(db_engine, ["BRK.B"])
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(price_daily).where(price_daily.c.symbol == "BRK.B")
        ).fetchall()
    assert len(rows) > 0, "Expected at least 1 row for BRK.B (period form)"


def test_yfinance_called_with_hyphen_form(db_engine: Engine) -> None:
    """DATA-08: yfinance is called with hyphen form (BRK-B), not period form."""
    mock_df = _make_bulk_df(
        ["BRK-B", "^GSPC"],
        [date(2025, 1, 2)],
        {"BRK-B": [200.0], "^GSPC": [4700.0]},
        {"BRK-B": [500], "^GSPC": [2000]},
    )
    with patch("yfinance.download", return_value=mock_df) as mock_dl:
        update_price_data(db_engine, ["BRK.B"])
    first_call_tickers = mock_dl.call_args_list[0].args[0]
    assert "BRK-B" in first_call_tickers, "Expected hyphen form in yfinance call"
    assert "BRK.B" not in first_call_tickers, "Period form must NOT reach yfinance"


# ---------------------------------------------------------------------------
# Tests: DATA-09 retry backoff
# ---------------------------------------------------------------------------


def test_failed_ticker_retried_with_backoff(db_engine: Engine) -> None:
    """DATA-09: failed ticker triggers per-symbol retry with backoff delays.

    Simulates: bulk fails for AAPL, first single-ticker attempt also fails
    (triggers sleep(1.0)), second attempt succeeds. Verifies backoff sequence.
    """
    # Bulk download returns all-NaN for AAPL (simulates bulk failure)
    bulk_df = _make_bulk_df(
        ["AAPL", "^GSPC"],
        [date(2025, 1, 2)],
        {"AAPL": [np.nan], "^GSPC": [4700.0]},
        {"AAPL": [0], "^GSPC": [2000]},
    )
    # Second single-ticker attempt succeeds
    retry_df = _make_single_df(
        [date(2025, 1, 2)],
        [150.0],
        [1000],
    )

    single_call_count = {"n": 0}

    def _side_effect(tickers: object, **kwargs: object) -> pd.DataFrame:
        if isinstance(tickers, list):
            return bulk_df
        # First single-ticker call returns empty (fail); second returns data
        single_call_count["n"] += 1
        if single_call_count["n"] == 1:
            return pd.DataFrame()
        return retry_df

    with (
        patch("yfinance.download", side_effect=_side_effect),
        patch("bensdorp1.data.prices.time.sleep") as mock_sleep,
    ):
        update_price_data(db_engine, ["AAPL"])

    # sleep(1.0) called after first failed attempt, before second attempt
    # second attempt succeeds so sleep(2.0) is NOT called
    assert mock_sleep.call_args_list == [call(1.0)]


def test_failed_ticker_exhausts_retries_emits_audit(db_engine: Engine) -> None:
    """DATA-09: ticker exhausting all 3 retries emits DATA_FETCH_FAILED event."""
    # Both bulk and all single-ticker retries return empty/NaN
    bulk_df = _make_bulk_df(
        ["DEADCO", "^GSPC"],
        [date(2025, 1, 2)],
        {"DEADCO": [np.nan], "^GSPC": [4700.0]},
        {"DEADCO": [0], "^GSPC": [2000]},
    )

    def _side_effect(tickers: object, **kwargs: object) -> pd.DataFrame:
        if isinstance(tickers, list):
            return bulk_df
        return pd.DataFrame()  # always empty for single-ticker retries

    with (
        patch("yfinance.download", side_effect=_side_effect),
        patch("bensdorp1.data.prices.time.sleep") as mock_sleep,
    ):
        update_price_data(db_engine, ["DEADCO"])

    # Audit event emitted for DEADCO
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(audit_log).where(
                audit_log.c.event_type == "data_fetch_failed"
            )
        ).fetchall()
    assert len(rows) == 1, "Expected exactly 1 DATA_FETCH_FAILED audit event"
    assert rows[0].symbol == "DEADCO", "Expected DB period form in audit event"

    payload = json.loads(rows[0][4])  # column 4 = payload
    assert payload["retries"] == 3

    # sleep called between attempts 1->2 and 2->3, NOT after final attempt
    assert mock_sleep.call_args_list == [call(1.0), call(2.0)]


# ---------------------------------------------------------------------------
# Test: price rows persisted in DB
# ---------------------------------------------------------------------------


def test_price_rows_persisted_in_db(db_engine: Engine) -> None:
    """End-to-end: downloaded prices are persisted in price_daily with UTC dates."""
    dates = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    mock_df = _make_bulk_df(
        ["AAPL", "^GSPC"],
        dates,
        {"AAPL": [150.0, 151.0, 152.0], "^GSPC": [4700.0, 4710.0, 4720.0]},
        {"AAPL": [1000, 1100, 1200], "^GSPC": [2000, 2100, 2200]},
    )
    with patch("yfinance.download", return_value=mock_df):
        update_price_data(db_engine, ["AAPL"])
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(price_daily)
            .where(price_daily.c.symbol == "AAPL")
            .order_by(price_daily.c.trade_date)
        ).fetchall()
    assert len(rows) == 3
    closes = [r.close for r in rows]
    assert closes == [150.0, 151.0, 152.0]
    for r in rows:
        assert r.trade_date is not None, "trade_date must not be None"


# ---------------------------------------------------------------------------
# Test: idempotent re-runs (ON CONFLICT DO NOTHING)
# ---------------------------------------------------------------------------


def test_rerun_idempotent_no_duplicates(db_engine: Engine) -> None:
    """ON CONFLICT DO NOTHING: calling update_price_data twice leaves no duplicates."""
    mock_df = _make_bulk_df(
        ["AAPL", "^GSPC"],
        [date(2025, 1, 2), date(2025, 1, 3)],
        {"AAPL": [150.0, 151.0], "^GSPC": [4700.0, 4710.0]},
        {"AAPL": [1000, 1100], "^GSPC": [2000, 2100]},
    )
    with patch("yfinance.download", return_value=mock_df):
        update_price_data(db_engine, ["AAPL"])
        update_price_data(db_engine, ["AAPL"])
    with db_engine.connect() as conn:
        count = conn.execute(
            select(func.count()).select_from(price_daily).where(
                price_daily.c.symbol == "AAPL"
            )
        ).scalar_one()
    assert count == 2, f"Expected 2 rows (no duplicates), got {count}"


# ---------------------------------------------------------------------------
# Tests: DATA-10 check_price_coverage
# ---------------------------------------------------------------------------


def _populate_constituents(engine: Engine, symbols: list[str]) -> None:
    """Insert symbols into constituents_cache for coverage tests."""
    now = datetime.now(UTC)
    rows = [
        {"symbol": sym, "company_name": sym, "fetched_at": now}
        for sym in symbols
    ]
    with engine.connect() as conn:
        conn.execute(insert(constituents_cache), rows)
        conn.commit()


def _populate_price_rows(
    engine: Engine, symbol: str, n_days: int, base_date: date | None = None
) -> None:
    """Insert n_days rows into price_daily for the given symbol."""
    ref = base_date or date(2024, 1, 2)
    rows = [
        {
            "symbol": symbol,
            "trade_date": datetime(
                ref.year, ref.month, ref.day, tzinfo=UTC
            )
            + timedelta(days=i),
            "close": 100.0 + i,
            "volume": 1000,
        }
        for i in range(n_days)
    ]
    with engine.connect() as conn:
        conn.execute(insert(price_daily), rows)
        conn.commit()


def test_check_price_coverage_pass(db_engine: Engine) -> None:
    """DATA-10: all 10 constituents have >= 220 rows -> returns (10, 10)."""
    symbols = [f"SYM{i:02d}" for i in range(10)]
    _populate_constituents(db_engine, symbols)
    for sym in symbols:
        _populate_price_rows(db_engine, sym, 220)
    result = check_price_coverage(db_engine, required_days=220)
    assert result == (10, 10)


def test_check_price_coverage_fail(db_engine: Engine) -> None:
    """DATA-10: 8/10 constituents have >= 220 rows, 2 have only 50 -> (8, 10)."""
    symbols = [f"SYM{i:02d}" for i in range(10)]
    _populate_constituents(db_engine, symbols)
    for sym in symbols[:8]:
        _populate_price_rows(db_engine, sym, 220)
    for sym in symbols[8:]:
        _populate_price_rows(db_engine, sym, 50)
    result = check_price_coverage(db_engine)
    assert result == (8, 10)


def test_check_price_coverage_excludes_gspc_from_constituent_total(
    db_engine: Engine,
) -> None:
    """DATA-10 + D-04: ^GSPC in price_daily does not count toward total or covered."""
    _populate_constituents(db_engine, ["AAPL"])
    _populate_price_rows(db_engine, "AAPL", 220)
    _populate_price_rows(db_engine, "^GSPC", 220)
    result = check_price_coverage(db_engine)
    # total = 1 (AAPL only — ^GSPC is not in constituents_cache)
    # covered = 1 (AAPL has 220 rows)
    assert result == (1, 1)
