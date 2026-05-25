"""List all open positions with current metrics — CMD-09."""

import datetime
from datetime import UTC
from typing import Literal

import typer
from rich.console import Console
from sqlalchemy import select

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR, MARKET_TZ
from bensdorp1.data import get_trading_days
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import positions, price_daily
from bensdorp1.ui import (
    format_date,
    format_pct,
    format_pnl,
    format_price,
    print_info,
    render_table,
)

# ---------------------------------------------------------------------------
# Columns per D-06 — exact headers and alignment
# ---------------------------------------------------------------------------

_COLUMNS: list[tuple[str, Literal["left", "right"]]] = [
    ("Symbol", "left"),
    ("Entry date", "left"),
    ("Days", "right"),
    ("Entry $", "right"),
    ("Shares", "right"),
    ("Last $", "right"),
    ("High $", "right"),
    ("Stop $", "right"),
    ("Dist %", "right"),
    ("P&L", "right"),
]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="Positions")
def portfolio() -> None:
    """List all open positions with current metrics."""
    # A. DB entry triad (SP-1)
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # B. Fetch all open positions (SP-4: closed_at == None generates IS NULL)
    with engine.connect() as conn:
        open_positions = conn.execute(
            select(positions).where(positions.c.closed_at == None)  # noqa: E711
        ).fetchall()

    # C. Empty state guard (SP-2, UI-08)
    if not open_positions:
        print_info("No open positions.", console=console)
        raise typer.Exit()

    # D. Compute today reference points (once, outside the loop)
    today_et: datetime.date = datetime.datetime.now(MARKET_TZ).date()
    today_utc_midnight: datetime.datetime = datetime.datetime(
        today_et.year, today_et.month, today_et.day, tzinfo=UTC
    )

    # E. Build rows
    rows: list[list[str]] = []

    with engine.connect() as conn:
        for pos in open_positions:
            # Latest close at or before today
            price_row = conn.execute(
                select(price_daily.c.close)
                .where(
                    (price_daily.c.symbol == pos.symbol)
                    & (price_daily.c.trade_date <= today_utc_midnight)
                )
                .order_by(price_daily.c.trade_date.desc())
                .limit(1)
            ).fetchone()

            days: int = len(get_trading_days(pos.entry_date.date(), today_et))

            if price_row is None:
                # N/A fallback for all price-derived columns (D-07)
                rows.append(
                    [
                        pos.symbol,
                        format_date(pos.entry_date.date()),
                        str(days),
                        format_price(pos.entry_close),
                        str(pos.shares),
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                    ]
                )
            else:
                last_close: float = price_row.close
                # Phase 7 D-18: effective_stop computed at read time, never stored
                effective_stop: float = max(pos.initial_stop, pos.trailing_stop)
                dist_pct: float = (last_close - effective_stop) / last_close * 100.0
                unrealized_pnl: float = (last_close - pos.entry_close) * pos.shares
                rows.append(
                    [
                        pos.symbol,
                        format_date(pos.entry_date.date()),
                        str(days),
                        format_price(pos.entry_close),
                        str(pos.shares),
                        format_price(last_close),
                        format_price(pos.highest_close),
                        format_price(effective_stop),
                        format_pct(dist_pct),
                        format_pnl(unrealized_pnl),
                    ]
                )

    # F. Render table (D-06 exact 10-column layout)
    render_table(columns=_COLUMNS, rows=rows, console=console)
    # Note: "High $" and "Stop $" reflect values as of the last scan run.
    # Run `bensdorp1 scan` to update stop levels with today's close.
    console.print(
        "Note: High $ and Stop $ reflect the last scan run.",
        markup=False,
        highlight=False,
    )
