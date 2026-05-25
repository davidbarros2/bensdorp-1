"""Record confirmed sell transaction."""

import datetime
from datetime import UTC
from typing import Any

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select, text, update

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR, MARKET_TZ
from bensdorp1.data import get_trading_days
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import positions, scan_exit_triggers
from bensdorp1.ui import (
    confirm_prompt,
    format_days,
    format_pct,
    format_pnl,
    format_price,
    print_error,
    print_success,
    render_kv_block,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SEPARATOR: str = "=" * 64

_REASON_MAP: dict[str, str] = {
    "Trailing stop": "stop_trailing",
    "Initial stop": "stop_initial",
}


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="Confirmations")
def sell(
    symbol: str = typer.Argument(..., help="Ticker symbol (e.g. AAPL)."),
    price: float = typer.Argument(..., help="Sell price per share."),
    date: str | None = typer.Option(
        None, "--date", help="Sell date (YYYY-MM-DD). Defaults to today ET."
    ),
    manual: str | None = typer.Option(
        None, "--manual", help="Manual sell reason (skips exit trigger lookup)."
    ),
) -> None:
    """Record a confirmed sell transaction."""

    # A. DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # B. Resolve sell_date and sell_dt
    sell_date: datetime.date
    if date is None:
        sell_date = datetime.datetime.now(MARKET_TZ).date()
    else:
        try:
            sell_date = datetime.date.fromisoformat(date)
        except ValueError:
            print_error(
                f"Invalid date format: {date!r}. Expected YYYY-MM-DD.",
                console=console,
            )
            raise typer.Exit(code=1) from None

    sell_dt = datetime.datetime(
        sell_date.year, sell_date.month, sell_date.day, tzinfo=UTC
    )

    # C. Validation per D-18
    # 1. Open position lookup
    with engine.connect() as conn:
        pos_row = conn.execute(
            select(
                positions.c.id,
                positions.c.entry_close,
                positions.c.shares,
                positions.c.entry_date,
            ).where(
                (positions.c.symbol == symbol.upper()) & (positions.c.closed_at == None)  # noqa: E711
            )
        ).fetchone()

    if pos_row is None:
        print_error(
            f"No open position for {symbol.upper()}.",
            actions=["Use `bensdorp1 portfolio` to view current positions."],
            console=console,
        )
        raise typer.Exit(code=1)

    position_id: int = pos_row.id
    entry_close: float = pos_row.entry_close
    shares: int = pos_row.shares
    entry_date: datetime.datetime = pos_row.entry_date

    # 2. Price > 0
    if price <= 0:
        print_error(
            "Sell price must be greater than zero.",
            console=console,
        )
        raise typer.Exit(code=1)

    # 3. sell_date >= entry_date.date()
    if sell_date < entry_date.date():
        print_error(
            f"--date {sell_date.isoformat()} is earlier than entry date"
            f" {entry_date.date().isoformat()}.",
            console=console,
        )
        raise typer.Exit(code=1)

    # D. Determine closed_reason / closed_manual_reason / display_reason / event_type
    closed_reason: str
    closed_manual_reason: str | None
    display_reason: str
    event_type: AuditEventType

    if manual is not None:
        closed_reason = "manual"
        closed_manual_reason = manual
        display_reason = "Manual"
        event_type = AuditEventType.SELL_MANUAL
    else:
        with engine.connect() as conn:
            trigger_row = conn.execute(
                select(scan_exit_triggers.c.reason)
                .where(scan_exit_triggers.c.position_id == position_id)
                .order_by(scan_exit_triggers.c.id.asc())
                .limit(1)
            ).fetchone()

        if trigger_row is None:
            print_error(
                f"No exit trigger on record for {symbol.upper()}.",
                body=[
                    "To record a manual sell, use: bensdorp1 sell SYMBOL PRICE --manual REASON"  # noqa: E501
                ],
                console=console,
            )
            raise typer.Exit(code=1)

        closed_reason = _REASON_MAP.get(trigger_row.reason, "stop_trailing")
        closed_manual_reason = None
        display_reason = trigger_row.reason
        event_type = AuditEventType.SELL_CONFIRMED

    # E. Computed values
    sell_value: float = price * shares
    entry_value: float = entry_close * shares
    days_held: int = len(get_trading_days(entry_date.date(), sell_date))
    realized_pnl: float = (price - entry_close) * shares
    realized_pnl_pct: float = (price / entry_close - 1) * 100.0
    pnl_display: str = f"{format_pnl(realized_pnl)} ({format_pct(realized_pnl_pct)})"

    # F. Confirmation block
    try:
        console.print(Text(SEPARATOR))
        if manual is not None:
            console.print(Text("Confirm sell (manual)"))
        else:
            console.print(Text("Confirm sell"))
        console.print(Text(SEPARATOR))
        console.print()

        kv_data: dict[str, str] = {
            "Symbol": symbol.upper(),
            "Sell price": format_price(price),
            "Sell value": format_price(sell_value),
            "Shares sold": str(shares),
            "Entry price": format_price(entry_close),
            "Entry value": format_price(entry_value),
            "Days held": format_days(days_held),
            "Realized P&L": pnl_display,
            "Closing reason": display_reason,
        }
        if manual is not None:
            kv_data["Manual reason"] = manual

        render_kv_block(kv_data, console)
        console.print()
        confirmed = confirm_prompt("Confirm sell?", console=console)
    except KeyboardInterrupt:
        raise typer.Exit() from None

    if not confirmed:
        raise typer.Exit()

    # G. State-changing write
    # Two-step UPDATE: the core columns are in the Table object; closed_reason and
    # closed_manual_reason are added via ALTER TABLE in run_migrations (not in schema.py
    # DDL), so they must be updated via a parameterized text() statement.
    with engine.connect() as conn:
        conn.execute(
            update(positions)
            .where(positions.c.id == position_id)
            .values(
                closed_at=sell_dt,
                exit_price=price,
                realized_pnl=realized_pnl,
            )
        )
        conn.execute(
            text(
                "UPDATE positions"
                " SET closed_reason = :closed_reason,"
                " closed_manual_reason = :closed_manual_reason"
                " WHERE id = :position_id"
            ),
            {
                "closed_reason": closed_reason,
                "closed_manual_reason": closed_manual_reason,
                "position_id": position_id,
            },
        )
        conn.commit()

    create_backup(engine, DATA_DIR / "backups")

    payload: dict[str, Any] = {
        "symbol": symbol.upper(),
        "sell_price": price,
        "shares": shares,
        "entry_price": entry_close,
        "realized_pnl": realized_pnl,
        "realized_pnl_pct": realized_pnl_pct,
        "closed_reason": closed_reason,
        "closed_manual_reason": closed_manual_reason,
    }
    log_event(engine, event_type, symbol=symbol.upper(), payload=payload)

    print_success("Sell recorded.", console=console)
