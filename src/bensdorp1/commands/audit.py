"""Query the audit log with optional filters — CMD-13."""

import datetime
import json
from datetime import UTC
from typing import Any

import typer
from rich.console import Console
from sqlalchemy import select

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.audit import AuditEventType
from bensdorp1.db.schema import audit_log
from bensdorp1.ui import (
    format_price,
    format_timezone_pair,
    print_error,
    print_info,
    render_table,
)


def _format_details(payload_str: str | None) -> str:
    """Parse JSON payload and extract key fields for display.

    Returns "—" for NULL payload.
    Returns truncated raw string if JSON is unparseable.
    Recognises cash_updated (old/new) and buy/sell (price/shares) payloads.
    """
    if payload_str is None:
        return "—"
    try:
        data: Any = json.loads(payload_str)
    except (json.JSONDecodeError, TypeError):
        return payload_str[:60]
    if isinstance(data, dict):
        if "old" in data and "new" in data:
            return (
                f"{format_price(float(data['old']))} →"
                f" {format_price(float(data['new']))}"
            )
        if "price" in data and "shares" in data:
            return f"{data['shares']} shares @ {format_price(float(data['price']))}"
    return str(data)[:60]


@app.command(rich_help_panel="System")
def audit(
    symbol: str | None = typer.Option(
        None, "--symbol", help="Filter by ticker symbol."
    ),
    since: str | None = typer.Option(
        None, "--since", help="On or after YYYY-MM-DD."
    ),
    until: str | None = typer.Option(
        None, "--until", help="On or before YYYY-MM-DD."
    ),
    type_: AuditEventType | None = typer.Option(  # noqa: B008
        None, "--type", help="Filter by event type."
    ),
    limit: int = typer.Option(50, "--limit", help="Maximum rows to show."),
) -> None:
    """Query the audit log with optional filters."""
    # DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # Parse --since / --until into UTC datetimes
    since_dt: datetime.datetime | None = None
    until_dt: datetime.datetime | None = None

    if since is not None:
        try:
            since_date = datetime.date.fromisoformat(since)
        except ValueError:
            print_error(
                f"Invalid --since/--until value {since!r}. Expected YYYY-MM-DD.",
                console=console,
            )
            raise typer.Exit(code=1) from None
        since_dt = datetime.datetime(
            since_date.year, since_date.month, since_date.day, tzinfo=UTC
        )

    if until is not None:
        try:
            until_date = datetime.date.fromisoformat(until)
        except ValueError:
            print_error(
                f"Invalid --since/--until value {until!r}. Expected YYYY-MM-DD.",
                console=console,
            )
            raise typer.Exit(code=1) from None
        until_dt = datetime.datetime(
            until_date.year, until_date.month, until_date.day, 23, 59, 59, tzinfo=UTC
        )

    # Build AND-filter list
    filters: list[Any] = []
    if symbol is not None:
        filters.append(audit_log.c.symbol == symbol.upper())
    if since_dt is not None:
        filters.append(audit_log.c.occurred_at >= since_dt)
    if until_dt is not None:
        filters.append(audit_log.c.occurred_at <= until_dt)
    if type_ is not None:
        filters.append(audit_log.c.event_type == str(type_))

    with engine.connect() as conn:
        result_rows = conn.execute(
            select(audit_log)
            .where(*filters)
            .order_by(audit_log.c.occurred_at.desc())
            .limit(limit)
        ).fetchall()

    if not result_rows:
        print_info("No audit events match the given filters.", console=console)
        raise typer.Exit()

    render_table(
        columns=[
            ("Date", "left"),
            ("Type", "left"),
            ("Symbol", "left"),
            ("Details", "left"),
        ],
        rows=[
            [
                format_timezone_pair(row.occurred_at),
                str(row.event_type),
                row.symbol or "—",
                _format_details(row.payload),
            ]
            for row in result_rows
        ],
        console=console,
    )
