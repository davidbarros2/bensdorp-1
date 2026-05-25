"""Show current cash balance, or update it — CMD-11."""

import datetime
from datetime import UTC
from typing import Any

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import config as config_table
from bensdorp1.ui import (
    confirm_prompt,
    format_price,
    format_timezone_pair,
    print_error,
    print_info,
    print_success,
    render_kv_block,
)

SEPARATOR: str = "=" * 64  # matches spec §7.1 exactly — 64 '=' characters


@app.command(rich_help_panel="System")
def cash(
    amount: float | None = typer.Argument(
        None,
        help="New cash balance (non-negative).",
    ),
    note: str | None = typer.Option(
        None,
        "--note",
        help="Reason for update.",
    ),
) -> None:
    """Show current cash balance, or update it."""
    # A. DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # B. Read current config row
    with engine.connect() as conn:
        row = conn.execute(
            select(config_table.c.value, config_table.c.updated_at).where(
                config_table.c.key == "available_cash"
            )
        ).fetchone()

    # C. Show-mode: no amount given
    if amount is None:
        if row is None:
            print_info(
                "No cash configured. Run `bensdorp1 init`.",
                console=console,
            )
            raise typer.Exit()
        render_kv_block(
            {
                "Available cash": format_price(float(row.value)),
                "Last updated": format_timezone_pair(row.updated_at),
            },
            console,
        )
        raise typer.Exit()

    # D. Update-mode: validate non-negative
    if amount < 0.0:
        print_error(
            "Cash amount must be non-negative.",
            data={"Amount": format_price(amount)},
            console=console,
        )
        raise typer.Exit(code=1)

    # E. Determine old value for audit payload
    old_value: float = float(row.value) if row is not None else 0.0

    # F. Preview block
    console.print(Text(SEPARATOR))
    console.print(Text("Confirm cash update"))
    console.print(Text(SEPARATOR))
    console.print()
    render_kv_block(
        {
            "Current cash": format_price(old_value),
            "New cash": format_price(amount),
            "Note": note or "—",
        },
        console,
    )
    console.print()

    # G. Confirmation prompt
    try:
        confirmed = confirm_prompt("Confirm cash update?", console=console)
    except KeyboardInterrupt:
        raise typer.Exit() from None
    if not confirmed:
        raise typer.Exit()

    # H. UPSERT config row
    now = datetime.datetime.now(UTC)
    stmt = (
        sqlite_insert(config_table)
        .values(
            key="available_cash",
            value=f"{amount:.2f}",
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": f"{amount:.2f}", "updated_at": now},
        )
    )
    with engine.connect() as conn:
        conn.execute(stmt)
        conn.commit()

    # I. Backup + audit log + success message
    create_backup(engine, DATA_DIR / "backups")
    payload: dict[str, Any] = {"old": old_value, "new": amount, "note": note}
    log_event(
        engine,
        AuditEventType.CASH_UPDATED,
        payload=payload,
    )
    print_success("Cash updated.", console=console)
