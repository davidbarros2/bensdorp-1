"""Interactively correct the last transaction for a symbol."""

import datetime
from datetime import UTC
from typing import Any

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select, update

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import positions
from bensdorp1.ui import (
    confirm_prompt,
    format_date,
    format_price,
    print_error,
    print_info,
    print_success,
    render_kv_block,
    render_table,
)

SEPARATOR: str = "=" * 64


@app.command(rich_help_panel="Confirmations")
def fix(
    symbol: str = typer.Argument(..., help="Ticker symbol to correct."),
    date: str | None = typer.Option(
        None, "--date", help="(Reserved; unused in Phase 8.)"
    ),
) -> None:
    """Interactively correct the last transaction for a symbol."""
    _unused = date  # Reserved for future use

    # A. DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # B. Identify the transaction (D-19)
    with engine.connect() as conn:
        open_row = conn.execute(
            select(
                positions.c.id,
                positions.c.entry_date,
                positions.c.entry_close,
                positions.c.shares,
                positions.c.initial_stop,
            ).where(
                (positions.c.symbol == symbol.upper())
                & (positions.c.closed_at == None)  # noqa: E711
            )
        ).fetchone()

    if open_row is not None:
        target_kind = "buy"
        position_id: int = int(open_row.id)
        current_entry_date: datetime.datetime = open_row.entry_date
        current_entry_close: float = float(open_row.entry_close)
        current_shares: int = int(open_row.shares)
        current_initial_stop: float = float(open_row.initial_stop)
    else:
        with engine.connect() as conn:
            closed_row = conn.execute(
                select(
                    positions.c.id,
                    positions.c.entry_close,
                    positions.c.shares,
                    positions.c.closed_at,
                    positions.c.exit_price,
                    positions.c.closed_reason,
                    positions.c.closed_manual_reason,
                    positions.c.realized_pnl,
                )
                .where(
                    (positions.c.symbol == symbol.upper())
                    & (positions.c.closed_at != None)  # noqa: E711
                )
                .order_by(positions.c.closed_at.desc())
                .limit(1)
            ).fetchone()

        if closed_row is None:
            print_error(
                f"No transaction found for {symbol.upper()}.",
                console=console,
            )
            raise typer.Exit(code=1)

        target_kind = "sell"
        position_id = int(closed_row.id)
        current_entry_close = float(closed_row.entry_close)
        current_shares = int(closed_row.shares)
        current_closed_at: datetime.datetime = closed_row.closed_at
        current_exit_price: float = float(closed_row.exit_price)
        current_closed_reason: str | None = closed_row.closed_reason
        current_closed_manual_reason: str | None = closed_row.closed_manual_reason
        current_realized_pnl: float | None = (
            float(closed_row.realized_pnl)
            if closed_row.realized_pnl is not None
            else None
        )

    # C. Identification confirmation prompt (spec §7.5 Step 1)
    try:
        console.print(Text(SEPARATOR))
        console.print(Text("Confirm fix target"))
        console.print(Text(SEPARATOR))
        console.print()

        if target_kind == "buy":
            kv_data: dict[str, str] = {
                "Transaction": (
                    f"Buy {symbol.upper()} on"
                    f" {format_date(current_entry_date.date())}"
                ),
                "Date": format_date(current_entry_date.date()),
                "Price": format_price(current_entry_close),
                "Shares": str(current_shares),
            }
        else:
            kv_data = {
                "Transaction": (
                    f"Sell {symbol.upper()} on"
                    f" {format_date(current_closed_at.date())}"
                ),
                "Date": format_date(current_closed_at.date()),
                "Price": format_price(current_exit_price),
                "Shares": str(current_shares),
            }
            if current_closed_reason == "manual" and current_closed_manual_reason:
                kv_data["Manual reason"] = current_closed_manual_reason

        render_kv_block(kv_data, console)
        console.print()
        confirmed = confirm_prompt(
            "Is this the transaction to fix?", console=console
        )
    except KeyboardInterrupt:
        console.print()
        console.print(Text("Operation aborted. No changes were made."))
        raise typer.Exit() from None

    if not confirmed:
        raise typer.Exit()

    console.print()

    # D. Field-by-field input loop (D-20)
    try:
        if target_kind == "buy":
            # Date
            raw_date = input(
                f"Date    [{format_date(current_entry_date.date())}]:  "
            ).strip()
            if raw_date:
                try:
                    new_date: datetime.date = datetime.date.fromisoformat(raw_date)
                except ValueError:
                    print_error("Expected YYYY-MM-DD.", console=console)
                    raise typer.Exit(code=1) from None
            else:
                new_date = current_entry_date.date()

            # Price
            raw_price = input(
                f"Price   [{format_price(current_entry_close)}]:  "
            ).strip()
            if raw_price:
                clean_price = raw_price.lstrip("$").replace(",", "")
                try:
                    new_price: float = float(clean_price)
                except ValueError:
                    print_error("Expected a numeric price.", console=console)
                    raise typer.Exit(code=1) from None
            else:
                new_price = current_entry_close

            # Shares
            raw_shares = input(f"Shares  [{current_shares}]:  ").strip()
            if raw_shares:
                try:
                    new_shares: int = int(raw_shares)
                except ValueError:
                    print_error(
                        "Expected an integer number of shares.", console=console
                    )
                    raise typer.Exit(code=1) from None
            else:
                new_shares = current_shares

        else:
            # Sell: date, price, manual_reason (if applicable)
            raw_date = input(
                f"Date    [{format_date(current_closed_at.date())}]:  "
            ).strip()
            if raw_date:
                try:
                    new_date = datetime.date.fromisoformat(raw_date)
                except ValueError:
                    print_error("Expected YYYY-MM-DD.", console=console)
                    raise typer.Exit(code=1) from None
            else:
                new_date = current_closed_at.date()

            raw_price = input(
                f"Price   [{format_price(current_exit_price)}]:  "
            ).strip()
            if raw_price:
                clean_price = raw_price.lstrip("$").replace(",", "")
                try:
                    new_price = float(clean_price)
                except ValueError:
                    print_error("Expected a numeric price.", console=console)
                    raise typer.Exit(code=1) from None
            else:
                new_price = current_exit_price

            new_manual_reason: str | None = current_closed_manual_reason
            if current_closed_reason == "manual":
                raw_manual = input(
                    f"Manual reason  [{current_closed_manual_reason or ''}]:  "
                ).strip()
                if raw_manual:
                    new_manual_reason = raw_manual

    except KeyboardInterrupt:
        console.print()
        console.print(Text("Operation aborted. No changes were made."))
        raise typer.Exit() from None

    # E. Detect changes
    if target_kind == "buy":
        any_changes = (
            (new_date != current_entry_date.date())
            or (new_price != current_entry_close)
            or (new_shares != current_shares)
        )
    else:
        any_changes = (
            (new_date != current_closed_at.date())
            or (new_price != current_exit_price)
            or (new_manual_reason != current_closed_manual_reason)
        )

    if not any_changes:
        print_info("No changes detected. Nothing to update.", console=console)
        raise typer.Exit()

    # F. Recalculations (D-21, D-22)
    if target_kind == "buy":
        if new_price != current_entry_close:
            new_initial_stop: float = new_price * 0.93
        else:
            new_initial_stop = current_initial_stop
        # trailing_stop and highest_close NEVER changed (D-22)
        new_realized_pnl: float | None = None
    else:
        new_initial_stop = 0.0  # not used for sell
        if new_price != current_exit_price:
            new_realized_pnl = (new_price - current_entry_close) * current_shares
        else:
            new_realized_pnl = current_realized_pnl

    # G. Before/after diff (D-23)
    console.print()
    console.print(Text(SEPARATOR))
    console.print(Text("Confirm correction"))
    console.print(Text(SEPARATOR))
    console.print()

    if target_kind == "buy":
        transaction_label = (
            f"Buy {symbol.upper()} on {format_date(current_entry_date.date())}"
        )
    else:
        transaction_label = (
            f"Sell {symbol.upper()} on {format_date(current_closed_at.date())}"
        )

    render_kv_block({"Transaction": transaction_label}, console)
    console.print()

    # Build diff rows for changed fields only
    diff_rows: list[list[str]] = []
    if target_kind == "buy":
        if new_price != current_entry_close:
            diff_rows.append(
                ["Price", format_price(current_entry_close), format_price(new_price)]
            )
        if new_shares != current_shares:
            diff_rows.append(["Shares", str(current_shares), str(new_shares)])
        if new_date != current_entry_date.date():
            diff_rows.append(
                [
                    "Date",
                    format_date(current_entry_date.date()),
                    format_date(new_date),
                ]
            )
    else:
        if new_price != current_exit_price:
            diff_rows.append(
                ["Price", format_price(current_exit_price), format_price(new_price)]
            )
        if new_date != current_closed_at.date():
            diff_rows.append(
                [
                    "Date",
                    format_date(current_closed_at.date()),
                    format_date(new_date),
                ]
            )
        if new_manual_reason != current_closed_manual_reason:
            diff_rows.append(
                [
                    "Manual reason",
                    current_closed_manual_reason or "",
                    new_manual_reason or "",
                ]
            )

    render_table(
        columns=[("Field", "left"), ("Before", "left"), ("After", "left")],
        rows=diff_rows,
        console=console,
    )

    # Show "Impact on this position" if derived values changed
    if target_kind == "buy" and new_price != current_entry_close:
        console.print()
        console.print(Text("Impact on this position"))
        console.print(Text("-" * 23))
        render_kv_block(
            {
                "Initial stop": (
                    f"{format_price(current_initial_stop)}"
                    f" -> {format_price(new_initial_stop)}"
                )
            },
            console,
        )
    elif target_kind == "sell" and new_price != current_exit_price:
        console.print()
        console.print(Text("Impact on this position"))
        console.print(Text("-" * 23))
        old_pnl_str = (
            format_price(current_realized_pnl)
            if current_realized_pnl is not None
            else "N/A"
        )
        new_pnl_str = (
            format_price(new_realized_pnl)
            if new_realized_pnl is not None
            else "N/A"
        )
        render_kv_block(
            {"Realized P&L": f"{old_pnl_str} -> {new_pnl_str}"},
            console,
        )

    console.print()
    console.print(Text("This correction will be recorded in the audit log."))
    console.print(Text("The original entry will be preserved as a historical record."))
    console.print()

    # H. Confirmation prompt
    try:
        confirmed = confirm_prompt("Confirm correction?", console=console)
    except KeyboardInterrupt:
        raise typer.Exit() from None

    if not confirmed:
        raise typer.Exit()

    # I. State-changing write (D-24)
    with engine.connect() as conn:
        if target_kind == "buy":
            new_entry_dt = datetime.datetime(
                new_date.year, new_date.month, new_date.day, tzinfo=UTC
            )
            conn.execute(
                update(positions)
                .where(positions.c.id == position_id)
                .values(
                    entry_date=new_entry_dt,
                    entry_close=new_price,
                    shares=new_shares,
                    initial_stop=new_initial_stop,
                )
            )
        else:
            new_closed_dt = datetime.datetime(
                new_date.year, new_date.month, new_date.day, tzinfo=UTC
            )
            conn.execute(
                update(positions)
                .where(positions.c.id == position_id)
                .values(
                    closed_at=new_closed_dt,
                    exit_price=new_price,
                    realized_pnl=new_realized_pnl,
                    closed_manual_reason=new_manual_reason,
                )
            )
        conn.commit()

    create_backup(engine, DATA_DIR / "backups")

    # Build before/after payload (D-24)
    if target_kind == "buy":
        payload: dict[str, Any] = {
            "target_kind": "buy",
            "before": {
                "entry_close": current_entry_close,
                "shares": current_shares,
                "entry_date": current_entry_date.date().isoformat(),
                "initial_stop": current_initial_stop,
            },
            "after": {
                "entry_close": new_price,
                "shares": new_shares,
                "entry_date": new_date.isoformat(),
                "initial_stop": new_initial_stop,
            },
        }
    else:
        payload = {
            "target_kind": "sell",
            "before": {
                "exit_price": current_exit_price,
                "closed_at": current_closed_at.date().isoformat(),
                "closed_manual_reason": current_closed_manual_reason,
                "realized_pnl": current_realized_pnl,
            },
            "after": {
                "exit_price": new_price,
                "closed_at": new_date.isoformat(),
                "closed_manual_reason": new_manual_reason,
                "realized_pnl": new_realized_pnl,
            },
        }

    log_event(
        engine,
        AuditEventType.TRANSACTION_CORRECTED,
        symbol=symbol.upper(),
        payload=payload,
    )

    print_success("Transaction corrected.", console=console)
