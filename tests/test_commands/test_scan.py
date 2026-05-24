"""Tests for commands/scan.py and commands/_scan_engine.py.

Implements all 10 scan test scenarios (D-23 CliRunner tests + D-24 unit tests).
"""

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.config import MARKET_TZ

runner = CliRunner()


# ---------------------------------------------------------------------------
# Unit test: schema
# ---------------------------------------------------------------------------


def test_schema_has_exit_triggers_table() -> None:
    """scan_exit_triggers table exists with correct columns and FK constraints."""
    from bensdorp1.db.schema import metadata

    assert "scan_exit_triggers" in metadata.tables
    table = metadata.tables["scan_exit_triggers"]
    col_names = [c.name for c in table.columns]
    assert "id" in col_names
    assert "scan_id" in col_names
    assert "position_id" in col_names
    assert "reason" in col_names
    assert "effective_stop" in col_names
    assert "triggered_date" in col_names


# ---------------------------------------------------------------------------
# CliRunner integration tests (D-23)
# ---------------------------------------------------------------------------


def test_time_gate(tmp_path: Path) -> None:
    """scan refuses with exit code 1 when invoked before 16:30 ET."""
    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
    ):
        # 15:00 ET — before 16:30 gate
        mock_dt.now.return_value = datetime(2026, 5, 21, 15, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan"])

    assert result.exit_code == 1
    assert "16:30 ET" in result.output


def test_happy_path_bull(tmp_path: Path) -> None:
    """Happy path: bull regime, scan output rendered and printed."""
    mock_engine = MagicMock()

    # Mock fetchone for idempotency check → None (no existing scan)
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = None

    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
        patch("bensdorp1.commands.scan.is_trading_day", return_value=True),
        patch("bensdorp1.commands.scan.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.scan.run_migrations"),
        patch(
            "bensdorp1.commands.scan.run_scan",
            return_value="Scan for 2026-05-21\nBull market\n",
        ),
    ):
        mock_dt.now.return_value = datetime(2026, 5, 21, 17, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert "Scan for 2026-05-21" in result.output


def test_bearish_regime(tmp_path: Path) -> None:
    """Bearish regime: buy candidates section suppressed; exit triggers still shown."""
    mock_engine = MagicMock()

    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = None

    bear_output = "Scan for 2026-05-21\nBear market\nExit triggers: 1\n"

    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
        patch("bensdorp1.commands.scan.is_trading_day", return_value=True),
        patch("bensdorp1.commands.scan.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.scan.run_migrations"),
        patch(
            "bensdorp1.commands.scan.run_scan",
            return_value=bear_output,
        ),
    ):
        mock_dt.now.return_value = datetime(2026, 5, 21, 17, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert "Buy candidates" not in result.output
    assert "Exit triggers: 1" in result.output


def test_idempotent_same_day(tmp_path: Path) -> None:
    """Same-day re-run without --force shows cached raw_output; run_scan not called."""
    mock_engine = MagicMock()
    stored_output = "Scan for 2026-05-21\nStored result\n"

    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = MagicMock(
        raw_output=stored_output
    )

    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
        patch("bensdorp1.commands.scan.is_trading_day", return_value=True),
        patch("bensdorp1.commands.scan.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.scan.run_migrations"),
        patch("bensdorp1.commands.scan.run_scan") as mock_run_scan,
    ):
        mock_dt.now.return_value = datetime(2026, 5, 21, 17, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert stored_output in result.output
    mock_run_scan.assert_not_called()  # D-01: no re-compute


def test_force_reruns_scan(tmp_path: Path) -> None:
    """--force flag causes scan to re-fetch data and overwrite same-day result."""
    mock_engine = MagicMock()
    stored_output = "Scan for 2026-05-21\nStored result\n"

    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = MagicMock(
        raw_output=stored_output
    )

    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
        patch("bensdorp1.commands.scan.is_trading_day", return_value=True),
        patch("bensdorp1.commands.scan.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.scan.run_migrations"),
        patch(
            "bensdorp1.commands.scan.run_scan",
            return_value="Fresh scan output\n",
        ) as mock_run_scan,
    ):
        mock_dt.now.return_value = datetime(2026, 5, 21, 17, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan", "--force"])

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    mock_run_scan.assert_called_once()  # D-02: re-run enforced


def test_non_trading_day(tmp_path: Path) -> None:
    """Non-trading day: Info message printed and last raw_output shown."""
    mock_engine = MagicMock()
    last_scan_dt = datetime(2026, 5, 20, tzinfo=UTC)
    last_output = "Last scan output from 2026-05-20\n"

    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = MagicMock(
        scan_date=last_scan_dt,
        raw_output=last_output,
    )

    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
        patch("bensdorp1.commands.scan.is_trading_day", return_value=False),
        patch("bensdorp1.commands.scan.get_engine", return_value=mock_engine),
    ):
        # Saturday at 17:00 ET — after 16:30 so time gate passes, but weekend
        mock_dt.now.return_value = datetime(2026, 5, 23, 17, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0, f"Unexpected exit. Output:\n{result.output}"
    assert "not a trading day" in result.output.lower()
    assert last_output in result.output


# ---------------------------------------------------------------------------
# Unit tests: _scan_engine internals (D-24)
# ---------------------------------------------------------------------------


def test_catchup_stop_updates(db_engine: Engine) -> None:
    """Catch-up logic: trailing stop updated for each missed trading day in sequence."""
    from bensdorp1.commands._scan_engine import _OpenPosition, _update_position_stops
    from bensdorp1.db.schema import positions, price_daily

    # Position: highest_close=100.0, trailing_stop=75.0, initial_stop=93.0
    # effective_stop=max(93.0, 75.0)=93.0
    entry_dt = datetime(2026, 1, 2, tzinfo=UTC)
    with db_engine.connect() as conn:
        result = conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=entry_dt,
                entry_close=100.0,
                shares=10,
                initial_stop=93.0,
                highest_close=100.0,
                trailing_stop=75.0,
                closed_at=None,
            )
        )
        conn.commit()
        pk = result.inserted_primary_key
        assert pk is not None
        pos_id: int = int(pk[0])

    # Three missed trading days with closes above effective_stop
    days = [
        date(2026, 5, 19),
        date(2026, 5, 20),
        date(2026, 5, 21),
    ]
    closes = [102.0, 104.0, 106.0]
    with db_engine.connect() as conn:
        for d, c in zip(days, closes, strict=True):
            conn.execute(
                insert(price_daily).values(
                    symbol="AAPL",
                    trade_date=datetime(d.year, d.month, d.day, tzinfo=UTC),
                    close=c,
                    volume=1_000_000,
                )
            )
        conn.commit()

    # Build price_dfs for _update_position_stops
    price_dfs: dict[str, pd.DataFrame] = {
        "AAPL": pd.DataFrame(
            [
                {
                    "trade_date": datetime(d.year, d.month, d.day, tzinfo=UTC),
                    "close": c,
                    "volume": 1_000_000,
                }
                for d, c in zip(days, closes, strict=True)
            ]
        )
    }

    pos = _OpenPosition(
        id=int(pos_id),
        symbol="AAPL",
        entry_date=entry_dt,
        initial_stop=93.0,
        highest_close=100.0,
        trailing_stop=75.0,
    )
    open_positions = [pos]
    triggered_ids: dict[int, tuple[date, float, float]] = {}

    # missed_days = first two days; today = last day
    _update_position_stops(
        db_engine,
        open_positions,
        [days[0], days[1]],
        days[2],
        price_dfs,
        triggered_ids,
    )

    # After 3 days of closes (102, 104, 106), all above effective_stop (93.0):
    # highest_close should be 106.0, trailing_stop = 106.0 * 0.75 = 79.5
    with db_engine.connect() as conn:
        row = conn.execute(
            select(positions.c.highest_close, positions.c.trailing_stop).where(
                positions.c.id == pos_id
            )
        ).fetchone()

    assert row is not None
    assert row.highest_close == pytest.approx(106.0)
    assert row.trailing_stop == pytest.approx(106.0 * 0.75)


def test_stop_freeze_after_trigger(db_engine: Engine) -> None:
    """Triggered position: effective_stop is frozen; position not double-triggered."""
    from bensdorp1.commands._scan_engine import _OpenPosition, _update_position_stops
    from bensdorp1.db.schema import positions, price_daily

    entry_dt = datetime(2026, 1, 2, tzinfo=UTC)
    with db_engine.connect() as conn:
        result = conn.execute(
            insert(positions).values(
                symbol="MSFT",
                entry_date=entry_dt,
                entry_close=100.0,
                shares=5,
                initial_stop=100.0,
                highest_close=100.0,
                trailing_stop=75.0,
                closed_at=None,
            )
        )
        conn.commit()
        pk = result.inserted_primary_key
        assert pk is not None
        pos_id: int = int(pk[0])

    today = date(2026, 5, 22)
    with db_engine.connect() as conn:
        conn.execute(
            insert(price_daily).values(
                symbol="MSFT",
                trade_date=datetime(today.year, today.month, today.day, tzinfo=UTC),
                close=90.0,
                volume=500_000,
            )
        )
        conn.commit()

    today_dt = datetime(today.year, today.month, today.day, tzinfo=UTC)
    price_dfs: dict[str, pd.DataFrame] = {
        "MSFT": pd.DataFrame(
            [
                {
                    "trade_date": today_dt,
                    "close": 90.0,
                    "volume": 500_000,
                }
            ]
        )
    }

    pos = _OpenPosition(
        id=int(pos_id),
        symbol="MSFT",
        entry_date=entry_dt,
        initial_stop=100.0,
        highest_close=100.0,
        trailing_stop=75.0,
    )
    open_positions = [pos]

    # Pre-mark as triggered — position should be frozen (no DB update).
    # Use a sentinel tuple value since the function only checks membership.
    triggered_ids: dict[int, tuple[date, float, float]] = {
        int(pos_id): (today, 90.0, 100.0)
    }

    _update_position_stops(
        db_engine,
        open_positions,
        [],  # no missed days
        today,
        price_dfs,
        triggered_ids,
    )

    # highest_close must remain 100.0 (frozen — no DB write happened)
    with db_engine.connect() as conn:
        row = conn.execute(
            select(positions.c.highest_close, positions.c.trailing_stop).where(
                positions.c.id == pos_id
            )
        ).fetchone()

    assert row is not None
    assert row.highest_close == pytest.approx(100.0)


def test_exit_trigger_on_missed_day(db_engine: Engine) -> None:
    """Catch-up: exit trigger recorded with triggered_date of the missed trading day."""
    from bensdorp1.commands._scan_engine import (
        _detect_exit_triggers,  # noqa: F401 — ruff I001 requires sorted order
        _OpenPosition,
        _update_position_stops,
    )
    from bensdorp1.db.schema import positions, scan_exit_triggers, scans

    entry_dt = datetime(2026, 1, 2, tzinfo=UTC)

    # Insert a scans row so _detect_exit_triggers has a valid FK scan_id
    today = date(2026, 5, 22)
    scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)
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

    # Insert position: initial_stop=100.0, trailing_stop=100.0 → effective_stop=100.0
    with db_engine.connect() as conn:
        pos_result = conn.execute(
            insert(positions).values(
                symbol="GOOG",
                entry_date=entry_dt,
                entry_close=100.0,
                shares=3,
                initial_stop=100.0,
                highest_close=100.0,
                trailing_stop=100.0,
                closed_at=None,
            )
        )
        conn.commit()
        pos_pk = pos_result.inserted_primary_key
        assert pos_pk is not None
        pos_id: int = int(pos_pk[0])

    # Missed day: close=95.0 (below effective_stop=100.0)
    missed_day = date(2026, 5, 21)
    missed_day_dt = datetime(
        missed_day.year, missed_day.month, missed_day.day, tzinfo=UTC
    )

    price_dfs: dict[str, pd.DataFrame] = {
        "GOOG": pd.DataFrame(
            [
                {
                    "trade_date": missed_day_dt,
                    "close": 95.0,
                    "volume": 800_000,
                }
            ]
        )
    }

    pos = _OpenPosition(
        id=int(pos_id),
        symbol="GOOG",
        entry_date=entry_dt,
        initial_stop=100.0,
        highest_close=100.0,
        trailing_stop=100.0,
    )
    open_positions = [pos]
    triggered_ids: dict[int, tuple[date, float, float]] = {}

    # Call _update_position_stops with the missed day — adds pos.id to triggered_ids
    _update_position_stops(
        db_engine,
        open_positions,
        [missed_day],  # missed_days
        today,  # today (no price data for today → skip)
        price_dfs,
        triggered_ids,
    )

    # pos.id must be in triggered_ids
    assert int(pos_id) in triggered_ids

    # Call _detect_exit_triggers — should insert a scan_exit_triggers row
    new_triggers = _detect_exit_triggers(
        db_engine,
        open_positions,
        triggered_ids,
        int(scan_id),
        today,
        price_dfs,
    )

    # There must be exactly one new trigger
    assert len(new_triggers) == 1

    # Verify row in DB: triggered_date should be the MISSED DAY's midnight UTC
    # (CR-02: triggered_date now stores the actual day the stop was hit, per D-09).
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(
                scan_exit_triggers.c.triggered_date,
                scan_exit_triggers.c.position_id,
            )
        ).fetchall()

    assert len(rows) == 1
    assert rows[0].position_id == int(pos_id)
    # triggered_date is stored as midnight UTC of the actual trigger day (D-09)
    assert rows[0].triggered_date.date() == missed_day
