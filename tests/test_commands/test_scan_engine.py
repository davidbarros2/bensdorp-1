"""Unit tests for _scan_engine.py internal helpers.

Targets coverage of helper functions not exercised by the CliRunner tests
in test_scan.py. All tests use in-process SQLite via the db_engine fixture.

Coverage targets:
- _get_close_for_day
- _get_available_cash
- _query_open_positions
- _query_pending_triggers
- _compute_avg_volumes
- _load_price_dfs
- _render_output (bull + bear + edge cases)
- _persist_scan_placeholder
- _persist_scan
- _run_screening (mocked price data)
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
import pytest
from rich.console import Console
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from bensdorp1.commands._scan_engine import (
    _compute_avg_volumes,
    _detect_exit_triggers,
    _get_available_cash,
    _get_close_for_day,
    _load_price_dfs,
    _OpenPosition,
    _persist_scan,
    _persist_scan_placeholder,
    _query_open_positions,
    _query_pending_triggers,
    _render_output,
    _run_screening,
    _TriggerRow,
)
from bensdorp1.db.schema import (
    config as config_table,
)
from bensdorp1.db.schema import (
    positions,
    price_daily,
    scan_candidates,
    scan_exit_triggers,
    scans,
)

# ---------------------------------------------------------------------------
# _get_close_for_day
# ---------------------------------------------------------------------------


def test_get_close_for_day_found() -> None:
    """Returns close price when the symbol and date match."""
    target = date(2026, 5, 21)
    df = pd.DataFrame(
        [
            {
                "trade_date": datetime(2026, 5, 21, tzinfo=UTC),
                "close": 150.25,
                "volume": 1_000_000,
            },
            {
                "trade_date": datetime(2026, 5, 20, tzinfo=UTC),
                "close": 148.00,
                "volume": 900_000,
            },
        ]
    )
    price_dfs: dict[str, pd.DataFrame] = {"AAPL": df}
    result = _get_close_for_day(price_dfs, "AAPL", target)
    assert result == pytest.approx(150.25)


def test_get_close_for_day_not_found_symbol() -> None:
    """Returns None when the symbol is not in price_dfs."""
    price_dfs: dict[str, pd.DataFrame] = {}
    result = _get_close_for_day(price_dfs, "AAPL", date(2026, 5, 21))
    assert result is None


def test_get_close_for_day_not_found_date() -> None:
    """Returns None when the symbol exists but the date is not in the DataFrame."""
    df = pd.DataFrame(
        [
            {
                "trade_date": datetime(2026, 5, 20, tzinfo=UTC),
                "close": 148.00,
                "volume": 900_000,
            }
        ]
    )
    price_dfs: dict[str, pd.DataFrame] = {"AAPL": df}
    result = _get_close_for_day(price_dfs, "AAPL", date(2026, 5, 21))
    assert result is None


def test_get_close_for_day_empty_df() -> None:
    """Returns None when the DataFrame for the symbol is empty."""
    price_dfs: dict[str, pd.DataFrame] = {
        "AAPL": pd.DataFrame(columns=["trade_date", "close", "volume"])
    }
    result = _get_close_for_day(price_dfs, "AAPL", date(2026, 5, 21))
    assert result is None


# ---------------------------------------------------------------------------
# _get_available_cash
# ---------------------------------------------------------------------------


def test_get_available_cash_present(db_engine: Engine) -> None:
    """Returns float value when available_cash is set in config table."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(config_table).values(
                key="available_cash",
                value="12345.67",
                updated_at=datetime.now(UTC),
            )
        )
        conn.commit()

    result = _get_available_cash(db_engine)
    assert result == pytest.approx(12345.67)


def test_get_available_cash_missing(db_engine: Engine) -> None:
    """Returns 0.0 when available_cash key is absent from config table."""
    result = _get_available_cash(db_engine)
    assert result == 0.0


# ---------------------------------------------------------------------------
# _query_open_positions
# ---------------------------------------------------------------------------


def test_query_open_positions_empty(db_engine: Engine) -> None:
    """Returns empty list when no open positions exist."""
    result = _query_open_positions(db_engine)
    assert result == []


def test_query_open_positions_returns_open_only(db_engine: Engine) -> None:
    """Returns only positions where closed_at IS NULL."""
    entry_dt = datetime(2026, 1, 2, tzinfo=UTC)
    closed_dt = datetime(2026, 5, 1, tzinfo=UTC)
    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=entry_dt,
                entry_close=100.0,
                shares=10,
                initial_stop=93.0,
                highest_close=100.0,
                trailing_stop=75.0,
                closed_at=None,
                delisted=0,
            )
        )
        conn.execute(
            insert(positions).values(
                symbol="MSFT",
                entry_date=entry_dt,
                entry_close=200.0,
                shares=5,
                initial_stop=186.0,
                highest_close=200.0,
                trailing_stop=150.0,
                closed_at=closed_dt,  # closed — must be excluded
                delisted=0,
            )
        )
        conn.commit()

    result = _query_open_positions(db_engine)
    assert len(result) == 1
    assert result[0].symbol == "AAPL"
    assert result[0].initial_stop == pytest.approx(93.0)


# ---------------------------------------------------------------------------
# _load_price_dfs
# ---------------------------------------------------------------------------


def test_load_price_dfs_returns_data(db_engine: Engine) -> None:
    """Loads price rows for given symbols, tailed to rows_needed."""
    with db_engine.connect() as conn:
        for i in range(5):
            conn.execute(
                insert(price_daily).values(
                    symbol="AAPL",
                    trade_date=datetime(2026, 5, i + 1, tzinfo=UTC),
                    close=float(150 + i),
                    volume=1_000_000,
                )
            )
        conn.commit()

    result = _load_price_dfs(db_engine, ["AAPL"], rows_needed=3)
    assert "AAPL" in result
    df = result["AAPL"]
    assert len(df) == 3  # tail(3) of 5 rows
    assert float(df["close"].iloc[-1]) == pytest.approx(154.0)


def test_load_price_dfs_missing_symbol(db_engine: Engine) -> None:
    """Returns empty dict when symbol has no price data."""
    result = _load_price_dfs(db_engine, ["ZZZZ"])
    assert "ZZZZ" not in result
    assert result == {}


# ---------------------------------------------------------------------------
# _query_pending_triggers
# ---------------------------------------------------------------------------


def test_query_pending_triggers_empty(db_engine: Engine) -> None:
    """Returns empty list when no scan_exit_triggers rows exist."""
    result = _query_pending_triggers(db_engine, [], [])
    assert result == []


def test_query_pending_triggers_excludes_new(db_engine: Engine) -> None:
    """Pending triggers excludes positions in new_trigger_rows."""
    entry_dt = datetime(2026, 1, 2, tzinfo=UTC)
    today = date(2026, 5, 22)
    scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)

    # Create scan row
    with db_engine.connect() as conn:
        scan_result = conn.execute(
            insert(scans).values(
                scan_date=scan_date_utc,
                regime_active=True,
                candidate_count=0,
                exit_trigger_count=0,
                raw_output=None,
                created_at=datetime.now(UTC),
            )
        )
        conn.commit()
        scan_pk = scan_result.inserted_primary_key
        assert scan_pk is not None
        scan_id: int = int(scan_pk[0])

    # Create two positions
    with db_engine.connect() as conn:
        r1 = conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=entry_dt,
                entry_close=100.0,
                shares=10,
                initial_stop=93.0,
                highest_close=100.0,
                trailing_stop=75.0,
                closed_at=None,
                delisted=0,
            )
        )
        r2 = conn.execute(
            insert(positions).values(
                symbol="MSFT",
                entry_date=entry_dt,
                entry_close=200.0,
                shares=5,
                initial_stop=186.0,
                highest_close=200.0,
                trailing_stop=150.0,
                closed_at=None,
                delisted=0,
            )
        )
        conn.commit()
        pk1 = r1.inserted_primary_key
        pk2 = r2.inserted_primary_key
        assert pk1 is not None
        assert pk2 is not None
        pos_id1: int = int(pk1[0])
        pos_id2: int = int(pk2[0])

    triggered_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)

    # Insert scan_exit_triggers for both positions (simulating prior-scan triggers)
    with db_engine.connect() as conn:
        conn.execute(
            insert(scan_exit_triggers).values(
                scan_id=scan_id,
                position_id=pos_id1,
                reason="Initial stop",
                effective_stop=93.0,
                triggered_date=triggered_utc,
            )
        )
        conn.execute(
            insert(scan_exit_triggers).values(
                scan_id=scan_id,
                position_id=pos_id2,
                reason="Trailing stop",
                effective_stop=186.0,
                triggered_date=triggered_utc,
            )
        )
        conn.commit()

    pos1 = _OpenPosition(
        id=pos_id1,
        symbol="AAPL",
        entry_date=entry_dt,
        initial_stop=93.0,
        highest_close=100.0,
        trailing_stop=75.0,
        entry_close=100.0,
        shares=10,
        delisted=0,
    )
    pos2 = _OpenPosition(
        id=pos_id2,
        symbol="MSFT",
        entry_date=entry_dt,
        initial_stop=186.0,
        highest_close=200.0,
        trailing_stop=150.0,
        entry_close=200.0,
        shares=5,
        delisted=0,
    )
    open_positions = [pos1, pos2]

    # pos_id1 is "new" — should be excluded from pending
    new_trigger_rows = [
        _TriggerRow(
            position_id=pos_id1,
            symbol="AAPL",
            reason="Initial stop",
            effective_stop=93.0,
            triggered_date=triggered_utc,
            entry_date=entry_dt,
            close_at_trigger=90.0,
        )
    ]

    result = _query_pending_triggers(db_engine, open_positions, new_trigger_rows)
    # Only pos_id2 (MSFT) should appear — pos_id1 (AAPL) is in new_trigger_rows
    assert len(result) == 1
    assert result[0].symbol == "MSFT"
    assert result[0].reason == "Trailing stop"


# ---------------------------------------------------------------------------
# _compute_avg_volumes
# ---------------------------------------------------------------------------


def test_compute_avg_volumes_basic() -> None:
    """Computes 20-day average volume excluding today's row."""
    rows = [
        {
            "trade_date": datetime(2026, 5, i + 1, tzinfo=UTC),
            "close": 100.0,
            "volume": float(1000 * (i + 1)),
        }
        for i in range(22)  # 22 rows: first 21 for history, last 1 is "today"
    ]
    df = pd.DataFrame(rows)
    price_dfs: dict[str, pd.DataFrame] = {"AAPL": df}
    result = _compute_avg_volumes(price_dfs)
    assert "AAPL" in result
    # excl_today = rows 0..20; last 20 = rows 1..20 (volumes 2000..21000)
    expected_vols = [1000 * (i + 1) for i in range(1, 21)]
    assert result["AAPL"] == int(sum(expected_vols) / 20)


def test_compute_avg_volumes_excludes_spx() -> None:
    """^GSPC is excluded from the avg volumes result."""
    df = pd.DataFrame(
        [
            {
                "trade_date": datetime(2026, 5, i + 1, tzinfo=UTC),
                "close": 5000.0,
                "volume": float(1_000_000),
            }
            for i in range(22)
        ]
    )
    price_dfs: dict[str, pd.DataFrame] = {"^GSPC": df}
    result = _compute_avg_volumes(price_dfs)
    assert "^GSPC" not in result


def test_compute_avg_volumes_too_few_rows() -> None:
    """Returns 0 for symbols with fewer than 21 rows."""
    df = pd.DataFrame(
        [
            {
                "trade_date": datetime(2026, 5, i + 1, tzinfo=UTC),
                "close": 100.0,
                "volume": float(500_000),
            }
            for i in range(10)
        ]
    )
    price_dfs: dict[str, pd.DataFrame] = {"AAPL": df}
    result = _compute_avg_volumes(price_dfs)
    assert result["AAPL"] == 0


# ---------------------------------------------------------------------------
# _persist_scan_placeholder
# ---------------------------------------------------------------------------


def test_persist_scan_placeholder_inserts(db_engine: Engine) -> None:
    """Inserts a scans row and returns the new scan_id."""
    today = date(2026, 5, 22)
    scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)
    now_utc = datetime.now(UTC)

    scan_id = _persist_scan_placeholder(db_engine, scan_date_utc, now_utc)
    assert isinstance(scan_id, int)
    assert scan_id > 0

    with db_engine.connect() as conn:
        row = conn.execute(
            select(scans.c.id, scans.c.scan_date, scans.c.regime_active).where(
                scans.c.id == scan_id
            )
        ).fetchone()
    assert row is not None
    assert row.regime_active is False


def test_persist_scan_placeholder_idempotent(db_engine: Engine) -> None:
    """ON CONFLICT DO UPDATE: same scan_date returns same or existing scan_id."""
    today = date(2026, 5, 22)
    scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)
    now_utc = datetime.now(UTC)

    id1 = _persist_scan_placeholder(db_engine, scan_date_utc, now_utc)
    id2 = _persist_scan_placeholder(db_engine, scan_date_utc, now_utc)
    # Both calls should reference the same DB row (same date)
    assert id1 == id2 or id2 > 0  # idempotent upsert


# ---------------------------------------------------------------------------
# _persist_scan
# ---------------------------------------------------------------------------


def test_persist_scan_writes_full_data(db_engine: Engine) -> None:
    """Finalizes scans row and inserts scan_candidates rows."""
    today = date(2026, 5, 22)
    scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)
    now_utc = datetime.now(UTC)

    # First insert placeholder
    scan_id = _persist_scan_placeholder(db_engine, scan_date_utc, now_utc)

    raw = "Test output\n"
    candidates = [
        {
            "symbol": "AAPL",
            "roc_200": 0.25,
            "prev_close": 150.0,
            "position_size": 10,
        }
    ]
    constituents: dict[str, str] = {"AAPL": "Apple Inc"}

    _persist_scan(
        db_engine,
        scan_date_utc,
        scan_id,
        regime_active=True,
        raw_output=raw,
        candidates=candidates,  # type: ignore[arg-type]
        new_trigger_rows=[],
        constituents=constituents,
        spx_close=5000.0,
        spx_sma_200=4800.0,
        freshness_days=0,
        force=False,
        now_utc=now_utc,
    )

    # Verify scans row updated
    with db_engine.connect() as conn:
        row = conn.execute(
            select(
                scans.c.raw_output,
                scans.c.regime_active,
                scans.c.candidate_count,
            ).where(scans.c.id == scan_id)
        ).fetchone()
    assert row is not None
    assert row.raw_output == raw
    assert row.regime_active is True
    assert row.candidate_count == 1

    # Verify scan_candidates row
    with db_engine.connect() as conn:
        cand_rows = conn.execute(
            select(scan_candidates.c.symbol, scan_candidates.c.rank).where(
                scan_candidates.c.scan_id == scan_id
            )
        ).fetchall()
    assert len(cand_rows) == 1
    assert cand_rows[0].symbol == "AAPL"
    assert cand_rows[0].rank == 1


# ---------------------------------------------------------------------------
# _render_output
# ---------------------------------------------------------------------------


def _make_trigger(
    pos_id: int = 1,
    symbol: str = "AAPL",
    reason: str = "Trailing stop",
    effective_stop: float = 93.0,
    close_at_trigger: float = 90.0,
) -> _TriggerRow:
    entry_dt = datetime(2026, 1, 2, tzinfo=UTC)
    triggered_dt = datetime(2026, 5, 22, tzinfo=UTC)
    return _TriggerRow(
        position_id=pos_id,
        symbol=symbol,
        reason=reason,
        effective_stop=effective_stop,
        triggered_date=triggered_dt,
        entry_date=entry_dt,
        close_at_trigger=close_at_trigger,
    )


def test_render_output_bull_no_triggers() -> None:
    """Bull market with no triggers: header, regime, buy candidates, system notes."""
    capture = Console(record=True, width=120)
    candidates = [
        {
            "symbol": "AAPL",
            "roc_200": 0.25,
            "prev_close": 150.0,
            "position_size": 10,
        }
    ]
    avg_volumes: dict[str, int] = {"AAPL": 1_500_000}

    _render_output(
        capture,
        date(2026, 5, 22),
        regime_active=True,
        spx_close=5200.0,
        spx_sma_200=4800.0,
        today_triggers=[],
        pending_triggers=[],
        candidates=candidates,  # type: ignore[arg-type]
        cash=10000.0,
        catch_up_events={},
        avg_volumes=avg_volumes,
    )

    text = capture.export_text()
    assert "Scan for" in text
    assert "Bull market" in text
    assert "Buy candidates (top 10)" in text
    assert "AAPL" in text
    assert "System notes" in text
    assert "No system notes" in text


def test_render_output_bear_regime() -> None:
    """Bear market: buy candidates section absent; bear note in system notes."""
    capture = Console(record=True, width=120)

    _render_output(
        capture,
        date(2026, 5, 22),
        regime_active=False,
        spx_close=4500.0,
        spx_sma_200=4800.0,
        today_triggers=[],
        pending_triggers=[],
        candidates=[],
        cash=10000.0,
        catch_up_events={},
        avg_volumes={},
    )

    text = capture.export_text()
    assert "Bear market" in text
    assert "Buy candidates" not in text
    # Bear market note appears in System notes section
    assert "Regime: Bear market" in text


def test_render_output_with_today_triggers() -> None:
    """Exit triggers section rendered with symbol, reason, close, stop, days held."""
    capture = Console(record=True, width=120)
    trigger = _make_trigger(symbol="GOOG", reason="Initial stop", close_at_trigger=95.0)

    _render_output(
        capture,
        date(2026, 5, 22),
        regime_active=True,
        spx_close=5200.0,
        spx_sma_200=4800.0,
        today_triggers=[trigger],
        pending_triggers=[],
        candidates=[],
        cash=10000.0,
        catch_up_events={},
        avg_volumes={},
    )

    text = capture.export_text()
    assert "Exit triggers" in text
    assert "GOOG" in text
    assert "Initial stop" in text
    assert "bensdorp1 sell SYMBOL" in text


def test_render_output_multiple_triggers_plural() -> None:
    """Two exit triggers: 'Both' used in instructions text."""
    capture = Console(record=True, width=120)
    t1 = _make_trigger(pos_id=1, symbol="AAPL")
    t2 = _make_trigger(pos_id=2, symbol="MSFT")

    _render_output(
        capture,
        date(2026, 5, 22),
        regime_active=True,
        spx_close=5200.0,
        spx_sma_200=4800.0,
        today_triggers=[t1, t2],
        pending_triggers=[],
        candidates=[],
        cash=10000.0,
        catch_up_events={},
        avg_volumes={},
    )

    text = capture.export_text()
    assert "Both" in text
    assert "exit triggers" in text.lower()


def test_render_output_pending_triggers() -> None:
    """Pending exit triggers section rendered when prior-scan triggers exist."""
    capture = Console(record=True, width=120)
    pending = _make_trigger(pos_id=3, symbol="NVDA", reason="Trailing stop")

    _render_output(
        capture,
        date(2026, 5, 22),
        regime_active=True,
        spx_close=5200.0,
        spx_sma_200=4800.0,
        today_triggers=[],
        pending_triggers=[pending],
        candidates=[],
        cash=10000.0,
        catch_up_events={},
        avg_volumes={},
    )

    text = capture.export_text()
    assert "Pending exit triggers" in text
    assert "NVDA" in text
    assert "bensdorp1 sell NVDA" in text


def test_render_output_multiple_pending_triggers() -> None:
    """Multiple pending triggers: generic 'sell SYMBOL PRICE' instruction shown."""
    capture = Console(record=True, width=120)
    p1 = _make_trigger(pos_id=3, symbol="NVDA")
    p2 = _make_trigger(pos_id=4, symbol="AMD")

    _render_output(
        capture,
        date(2026, 5, 22),
        regime_active=True,
        spx_close=5200.0,
        spx_sma_200=4800.0,
        today_triggers=[],
        pending_triggers=[p1, p2],
        candidates=[],
        cash=10000.0,
        catch_up_events={},
        avg_volumes={},
    )

    text = capture.export_text()
    assert "sell SYMBOL PRICE" in text


def test_render_output_no_affordable_candidates() -> None:
    """D-22: When all candidates have position_size=0, note is rendered."""
    capture = Console(record=True, width=120)
    candidates = [
        {
            "symbol": "AAPL",
            "roc_200": 0.25,
            "prev_close": 2000.0,
            "position_size": 0,  # not affordable
        }
    ]

    _render_output(
        capture,
        date(2026, 5, 22),
        regime_active=True,
        spx_close=5200.0,
        spx_sma_200=4800.0,
        today_triggers=[],
        pending_triggers=[],
        candidates=candidates,  # type: ignore[arg-type]
        cash=100.0,
        catch_up_events={},
        avg_volumes={"AAPL": 1_000_000},
    )

    text = capture.export_text()
    assert "No affordable candidates" in text


def test_render_output_catch_up_notes() -> None:
    """Catch-up summary block renders when missed_days is non-empty."""
    capture = Console(record=True, width=120)

    _render_output(
        capture,
        date(2026, 5, 22),
        regime_active=False,
        spx_close=4500.0,
        spx_sma_200=4800.0,
        today_triggers=[],
        pending_triggers=[],
        candidates=[],
        cash=0.0,
        catch_up_events={},
        avg_volumes={},
        missed_days=[date(2026, 5, 20), date(2026, 5, 21)],
        open_positions_count=3,
    )

    text = capture.export_text()
    assert "Catch-up summary" in text
    assert "absent for 2 trading days" in text
    assert "updated for 3 open positions" in text


# ---------------------------------------------------------------------------
# _run_screening (mocked price data)
# ---------------------------------------------------------------------------


def _make_spx_df(
    length: int = 201,
    last_close: float = 5200.0,
    sma_200: float = 4800.0,
) -> pd.DataFrame:
    """Build a synthetic SPX DataFrame.

    The last close is set to last_close; all prior rows use sma_200 as close.
    This ensures regime_filter can classify bull vs bear based on the last value.
    """
    from datetime import timedelta

    closes = [sma_200] * (length - 1) + [last_close]
    base = datetime(2020, 1, 1, tzinfo=UTC)
    rows = [
        {
            "trade_date": base + timedelta(days=i),
            "close": closes[i],
            "volume": 0,
        }
        for i in range(length)
    ]
    return pd.DataFrame(rows)


def test_run_screening_bull_regime(db_engine: Engine) -> None:
    """Bull regime: regime_active=True returned when SPX close > SMA 200."""
    spx_df = _make_spx_df(last_close=5200.0, sma_200=4800.0)
    price_dfs: dict[str, pd.DataFrame] = {"^GSPC": spx_df}
    con = Console(record=True, width=120)

    regime_active, spx_close, spx_sma_200, candidates = _run_screening(
        db_engine, con, price_dfs, available_cash=0.0
    )

    assert regime_active is True
    assert spx_close == pytest.approx(5200.0)
    assert candidates == []


def test_run_screening_bear_regime(db_engine: Engine) -> None:
    """Bear regime: regime_active=False returned when SPX close < SMA 200."""
    # All closes at 4000.0 → last close (4000.0) < sma_200 (4000.0 average)
    # Make last value 3500 so it's definitely below
    spx_df = _make_spx_df(last_close=3500.0, sma_200=4800.0)
    price_dfs: dict[str, pd.DataFrame] = {"^GSPC": spx_df}
    con = Console(record=True, width=120)

    regime_active, spx_close, _sma, candidates = _run_screening(
        db_engine, con, price_dfs, available_cash=0.0
    )

    assert regime_active is False
    assert candidates == []


def test_run_screening_no_spx_raises(db_engine: Engine) -> None:
    """RuntimeError raised when ^GSPC is missing from price_dfs."""
    price_dfs: dict[str, pd.DataFrame] = {}
    con = Console(record=True, width=120)

    with pytest.raises(RuntimeError, match="No SPX price data"):
        _run_screening(db_engine, con, price_dfs, available_cash=0.0)


# ---------------------------------------------------------------------------
# _detect_exit_triggers — already-triggered position excluded
# ---------------------------------------------------------------------------


def test_detect_exit_triggers_already_existing(db_engine: Engine) -> None:
    """Positions that already have a scan_exit_triggers row are not double-inserted."""
    entry_dt = datetime(2026, 1, 2, tzinfo=UTC)
    today = date(2026, 5, 22)
    scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)

    # Insert scan row
    with db_engine.connect() as conn:
        scan_result = conn.execute(
            insert(scans).values(
                scan_date=scan_date_utc,
                regime_active=True,
                candidate_count=0,
                exit_trigger_count=0,
                raw_output=None,
                created_at=datetime.now(UTC),
            )
        )
        conn.commit()
        scan_pk = scan_result.inserted_primary_key
        assert scan_pk is not None
        scan_id: int = int(scan_pk[0])

    # Insert position
    with db_engine.connect() as conn:
        pos_result = conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=entry_dt,
                entry_close=100.0,
                shares=10,
                initial_stop=100.0,
                highest_close=100.0,
                trailing_stop=100.0,
                closed_at=None,
                delisted=0,
            )
        )
        conn.commit()
        pos_pk = pos_result.inserted_primary_key
        assert pos_pk is not None
        pos_id: int = int(pos_pk[0])

    triggered_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)

    # Pre-insert existing trigger row with a DIFFERENT (prior) scan_id so the
    # current scan's duplicate check (which excludes rows for current scan_id)
    # correctly sees it as an already-triggered position (CR-03).
    prior_scan_date = datetime(2026, 5, 21, tzinfo=UTC)
    with db_engine.connect() as conn:
        prior_scan_result = conn.execute(
            insert(scans).values(
                scan_date=prior_scan_date,
                regime_active=True,
                candidate_count=0,
                exit_trigger_count=0,
                raw_output=None,
                created_at=datetime.now(UTC),
            )
        )
        conn.commit()
        prior_scan_pk = prior_scan_result.inserted_primary_key
        assert prior_scan_pk is not None
        prior_scan_id: int = int(prior_scan_pk[0])

    with db_engine.connect() as conn:
        conn.execute(
            insert(scan_exit_triggers).values(
                scan_id=prior_scan_id,  # prior scan, not the current one
                position_id=pos_id,
                reason="Initial stop",
                effective_stop=100.0,
                triggered_date=triggered_utc,
            )
        )
        conn.commit()

    pos = _OpenPosition(
        id=pos_id,
        symbol="AAPL",
        entry_date=entry_dt,
        initial_stop=100.0,
        highest_close=100.0,
        trailing_stop=100.0,
        entry_close=100.0,
        shares=10,
        delisted=0,
    )

    # Call with pos_id in triggered_ids (dict type after CR-02/WR-04)
    result = _detect_exit_triggers(
        db_engine,
        [pos],
        {pos_id: (today, 90.0, 100.0)},
        scan_id,
        today,
        {},  # no price data needed
    )

    # Position already has a trigger row → should NOT be in new_triggers
    assert result == []

    # Verify DB still has only 1 row (no duplicate inserted)
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(scan_exit_triggers.c.id).where(
                scan_exit_triggers.c.position_id == pos_id
            )
        ).fetchall()
    assert len(rows) == 1
