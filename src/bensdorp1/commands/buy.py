"""Record confirmed buy transaction."""

import datetime
from datetime import UTC
from typing import Any

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import insert, select

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR, MARKET_TZ
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import constituents_cache, positions, scan_candidates, scans
from bensdorp1.ui import (
    confirm_prompt,
    format_price,
    print_error,
    print_success,
    print_warning,
    render_kv_block,
)

SEPARATOR: str = "=" * 64  # matches spec §7.3 — 64 '=' characters


@app.command(rich_help_panel="Confirmations")
def buy(
    symbol: str = typer.Argument(..., help="Ticker symbol (e.g. NVDA)."),
    price: float = typer.Argument(..., help="Buy price per share."),
    shares: int = typer.Argument(..., help="Number of shares."),
    date: str | None = typer.Option(
        None, "--date", help="Buy date (YYYY-MM-DD). Defaults to today ET."
    ),
) -> None:
    """Record a confirmed buy transaction."""
    # A. DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # B. Resolve buy_date and entry_dt (per D-10)
    buy_date: datetime.date
    if date is None:
        buy_date = datetime.datetime.now(MARKET_TZ).date()
    else:
        try:
            buy_date = datetime.date.fromisoformat(date)
        except ValueError:
            print_error(
                f"Invalid --date value {date!r}. Expected YYYY-MM-DD.",
                console=console,
            )
            raise typer.Exit(code=1) from None
    entry_dt = datetime.datetime(
        buy_date.year, buy_date.month, buy_date.day, tzinfo=UTC
    )

    # C. Validation order per D-04
    with engine.connect() as conn:
        # 1. Constituent check
        constituent_row = conn.execute(
            select(constituents_cache.c.symbol).where(
                constituents_cache.c.symbol == symbol.upper()
            )
        ).fetchone()
        if constituent_row is None:
            print_error(
                f"{symbol.upper()} is not a valid S&P 500 constituent.",
                actions=["Run `bensdorp1 scan` to refresh the constituents list."],
                console=console,
            )
            raise typer.Exit(code=1)

        # 2. No-open-position check
        open_pos_row = conn.execute(
            select(positions.c.id).where(
                (positions.c.symbol == symbol.upper()) & (positions.c.closed_at == None)  # noqa: E711
            )
        ).fetchone()
        if open_pos_row is not None:
            print_error(
                f"An open position for {symbol.upper()} already exists.",
                actions=["Use `bensdorp1 portfolio` to view current positions."],
                console=console,
            )
            raise typer.Exit(code=1)

    # 3. Price/shares > 0
    if price <= 0 or shares <= 0:
        print_error(
            "Price and shares must be greater than zero.",
            data={"Price": format_price(price), "Shares": str(shares)},
            console=console,
        )
        raise typer.Exit(code=1)

    # D. On-signal check per D-05
    buy_date_utc = entry_dt
    on_signal: bool
    signal_scan_id: int | None
    signal_rank: int | None
    signal_scan_date: datetime.date | None

    with engine.connect() as conn:
        scan_row = conn.execute(
            select(scans.c.id, scans.c.scan_date)
            .where(scans.c.scan_date <= buy_date_utc)
            .order_by(scans.c.scan_date.desc())
            .limit(1)
        ).fetchone()

        if scan_row is None:
            on_signal = False
            signal_scan_id = None
            signal_rank = None
            signal_scan_date = None
        else:
            candidate_row = conn.execute(
                select(scan_candidates.c.rank).where(
                    (scan_candidates.c.scan_id == scan_row.id)
                    & (scan_candidates.c.symbol == symbol.upper())
                    & (scan_candidates.c.rank <= 10)
                )
            ).fetchone()
            if candidate_row is not None:
                on_signal = True
                signal_scan_id = int(scan_row.id)
                signal_rank = int(candidate_row.rank)
                signal_scan_date = scan_row.scan_date.date()
            else:
                on_signal = False
                signal_scan_id = None
                signal_rank = None
                signal_scan_date = None

    # E. Off-signal warning (D-06) — only when NOT on_signal
    if not on_signal:
        print_warning(
            f"{symbol.upper()} was not in the top 10 buy candidates"
            " of the latest scan.",
            body=["This buy will be recorded as off-signal in the audit log."],
            console=console,
        )
        console.print()
        try:
            off_signal_ok = confirm_prompt("Continue?", console=console)
        except KeyboardInterrupt:
            raise typer.Exit() from None
        if not off_signal_ok:
            raise typer.Exit()

    # F. Main confirmation block (D-08)
    try:
        console.print(Text(SEPARATOR))
        console.print(Text("Confirm buy"))
        console.print(Text(SEPARATOR))
        console.print()
        kv_data: dict[str, str] = {
            "Symbol": symbol.upper(),
            "Buy price": format_price(price),
            "Shares": str(shares),
            "Buy value": format_price(price * shares),
            "Date": buy_date.isoformat(),
        }
        if on_signal and signal_scan_date is not None and signal_rank is not None:
            kv_data["Signal scan"] = (
                f"{signal_scan_date.isoformat()}"
                f" ({symbol.upper()} was rank {signal_rank})"
            )
        render_kv_block(kv_data, console)
        console.print()
        confirmed = confirm_prompt("Confirm buy?", console=console)
    except KeyboardInterrupt:
        raise typer.Exit() from None
    if not confirmed:
        raise typer.Exit()

    # G. State-changing write (D-09)
    with engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol=symbol.upper(),
                entry_date=entry_dt,
                entry_close=price,
                shares=shares,
                initial_stop=price * 0.93,
                highest_close=price,
                trailing_stop=price * 0.75,
                scan_id=signal_scan_id,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        conn.commit()

    create_backup(engine, DATA_DIR / "backups")
    payload: dict[str, Any] = {
        "price": price,
        "shares": shares,
        "date": buy_date.isoformat(),
        "scan_id": signal_scan_id,
        "on_signal": on_signal,
    }
    log_event(
        engine,
        AuditEventType.BUY_CONFIRMED,
        symbol=symbol.upper(),
        payload=payload,
    )
    print_success("Buy recorded.", console=console)
