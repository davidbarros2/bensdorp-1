"""Integration tests confirming STATE-06 partial unique index enforcement.

STATE-06: no two simultaneously open positions for the same symbol.
The ix_positions_open_symbol partial unique index enforces this at the SQLite
level — no INSERT can bypass it regardless of code path.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from bensdorp1.db.schema import positions


def test_duplicate_open_position_rejected(db_engine: Engine) -> None:
    """Second open position for the same symbol raises IntegrityError.

    The partial unique index ix_positions_open_symbol is defined as
    UNIQUE (symbol) WHERE closed_at IS NULL, so inserting two rows with
    closed_at=None for the same symbol must raise IntegrityError at the DB level.
    """
    now = datetime.now(UTC)
    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=now,
                entry_close=150.0,
                shares=10,
                initial_stop=139.5,
                highest_close=150.0,
                trailing_stop=112.5,
                closed_at=None,
            )
        )
        conn.commit()
        with pytest.raises(IntegrityError):
            conn.execute(
                insert(positions).values(
                    symbol="AAPL",
                    entry_date=now,
                    entry_close=155.0,
                    shares=10,
                    initial_stop=144.15,
                    highest_close=155.0,
                    trailing_stop=116.25,
                    closed_at=None,
                )
            )


def test_sequential_positions_allowed(db_engine: Engine) -> None:
    """Close a position then re-enter the same symbol — no error raised.

    Closing a position (setting closed_at to a datetime) removes it from the
    partial index scope, so a new open position for the same symbol succeeds.
    """
    now = datetime.now(UTC)
    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="MSFT",
                entry_date=now,
                entry_close=300.0,
                shares=5,
                initial_stop=279.0,
                highest_close=300.0,
                trailing_stop=225.0,
                closed_at=None,
            )
        )
        conn.commit()
        conn.execute(
            update(positions)
            .where(positions.c.symbol == "MSFT")
            .values(closed_at=now, exit_price=310.0, realized_pnl=50.0)
        )
        conn.commit()
        conn.execute(
            insert(positions).values(
                symbol="MSFT",
                entry_date=now,
                entry_close=315.0,
                shares=5,
                initial_stop=292.95,
                highest_close=315.0,
                trailing_stop=236.25,
                closed_at=None,
            )
        )
        conn.commit()
        # No exception raised = test passes


def test_different_symbols_can_both_be_open(db_engine: Engine) -> None:
    """Two different symbols can both have open positions simultaneously.

    The partial index applies per symbol; AAPL and GOOG are distinct and can
    each have one row with closed_at=None at the same time.
    """
    now = datetime.now(UTC)
    with db_engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol="AAPL",
                entry_date=now,
                entry_close=150.0,
                shares=10,
                initial_stop=139.5,
                highest_close=150.0,
                trailing_stop=112.5,
                closed_at=None,
            )
        )
        conn.execute(
            insert(positions).values(
                symbol="GOOG",
                entry_date=now,
                entry_close=2800.0,
                shares=1,
                initial_stop=2604.0,
                highest_close=2800.0,
                trailing_stop=2100.0,
                closed_at=None,
            )
        )
        conn.commit()
        # Both inserts succeed — no exception
