"""Show full day-by-day stop history for a single open position."""

from datetime import date, timedelta

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.data import get_trading_days
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import positions, price_daily
from bensdorp1.ui import (
    format_date,
    format_price,
    print_error,
    print_info,
    render_kv_block,
    render_table,
)


@app.command(rich_help_panel="Positions")
def detail(
    symbol: str = typer.Argument(..., help="Ticker symbol of an open position."),
) -> None:
    """Show full history of a single open position."""

    # A. DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # B. Open-position lookup (SP-4)
    with engine.connect() as conn:
        pos_row = conn.execute(
            select(positions).where(
                (positions.c.symbol == symbol.upper()) & (positions.c.closed_at == None)  # noqa: E711
            )
        ).fetchone()

    if pos_row is None:
        sym = symbol.upper()
        hint = f"To see history of a closed position: bensdorp1 audit --symbol {sym}"
        print_error(
            f"No open position for {sym}.",
            actions=[hint],
            console=console,
        )
        raise typer.Exit(code=1)

    # C. Render position summary kv-block
    render_kv_block(
        {
            "Symbol": pos_row.symbol,
            "Entry date": format_date(pos_row.entry_date.date()),
            "Entry price": format_price(pos_row.entry_close),
            "Shares": str(pos_row.shares),
            "Initial stop": format_price(pos_row.initial_stop),
        },
        console,
    )
    console.print()

    # D. Section header (SP-9)
    console.print(Text("Stop history"))
    console.print(Text("-" * 12))
    console.print()

    # E. Fetch all price_daily rows after entry_date for SYMBOL
    with engine.connect() as conn:
        price_rows = conn.execute(
            select(price_daily.c.trade_date, price_daily.c.close)
            .where(
                (price_daily.c.symbol == symbol.upper())
                & (price_daily.c.trade_date > pos_row.entry_date)
            )
            .order_by(price_daily.c.trade_date.asc())
        ).fetchall()

    # F. Build close map
    close_map: dict[date, float] = {r.trade_date.date(): r.close for r in price_rows}

    if not close_map:
        print_info("No price history available yet for this position.", console=console)
        raise typer.Exit()

    # G. Walk every NYSE trading day from entry_date+1 to last_price_date
    last_price_date = max(close_map.keys())
    trading_days = get_trading_days(
        pos_row.entry_date.date() + timedelta(days=1), last_price_date
    )

    history_rows: list[list[str]] = []
    running_max: float = pos_row.entry_close

    for day in trading_days:
        day_date = day.date()
        day_close = close_map.get(day_date)
        if day_close is None:
            continue  # gap in price data — skip (Pitfall 4)
        running_max = max(running_max, day_close)
        trailing_stop = running_max * 0.75
        effective_stop = max(pos_row.initial_stop, trailing_stop)
        history_rows.append(
            [
                format_date(day_date),
                format_price(day_close),
                format_price(running_max),
                format_price(trailing_stop),
                format_price(effective_stop),
            ]
        )

    # H. Render stop history table
    render_table(
        columns=[
            ("Date", "left"),
            ("Close", "right"),
            ("Highest close", "right"),
            ("Trailing stop", "right"),
            ("Effective stop", "right"),
        ],
        rows=history_rows,
        console=console,
    )
