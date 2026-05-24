"""Daily end-of-day screening command."""

from datetime import UTC, datetime

import typer
from rich.console import Console
from sqlalchemy import select

from bensdorp1._app import app
from bensdorp1.commands._scan_engine import run_scan
from bensdorp1.config import DATA_DIR, MARKET_TZ
from bensdorp1.data import is_trading_day
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import scans
from bensdorp1.ui import print_error, print_info


@app.command(rich_help_panel="Daily operation")
def scan(
    force: bool = typer.Option(
        False, "--force", help="Re-run even if scan already ran today."
    ),
) -> None:
    """Run daily end-of-day screening for exit triggers and buy candidates."""
    # 1. TIME GATE: refuse before 16:30 ET (MARKET_TZ) — runs BEFORE any DB access
    now_et = datetime.now(MARKET_TZ)
    if now_et.hour < 16 or (now_et.hour == 16 and now_et.minute < 30):
        print_error(
            "Market has not closed yet.",
            data={
                "Market closes at": "16:00 ET",
                "Scan available after": "16:30 ET",
                "Current time": f"{now_et:%H:%M} ET",
            },
        )
        raise typer.Exit(code=1)

    # 2. TRADING-DAY CHECK
    today = datetime.now(MARKET_TZ).date()
    if not is_trading_day(today):
        db_path = DATA_DIR / "data" / "bensdorp1.db"
        engine = get_engine(db_path)
        run_migrations(engine)
        with engine.connect() as conn:
            row = conn.execute(
                select(scans.c.scan_date, scans.c.raw_output)
                .order_by(scans.c.scan_date.desc())
                .limit(1)
            ).fetchone()
        console = Console()
        if row is None:
            print_info(
                "No scans recorded yet."
                " Run `bensdorp1 scan` on a trading day after 16:30 ET."
            )
        else:
            last_date = row.scan_date.date()
            print_info(
                f"Today is not a trading day. Showing last scan from {last_date}."
            )
            if row.raw_output is not None:
                console.print(row.raw_output, markup=False, highlight=False)
        raise typer.Exit()

    # 3. IDEMPOTENCY CHECK (trading days only)
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)

    scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)
    with engine.connect() as conn:
        existing = conn.execute(
            select(scans.c.raw_output).where(scans.c.scan_date == scan_date_utc)
        ).fetchone()

    console = Console()
    if existing is not None and not force:
        if existing.raw_output is not None:
            console.print(existing.raw_output, markup=False, highlight=False)
        raise typer.Exit()

    # 4. ENGINE DELEGATION
    output = run_scan(engine, force=force, console=console)
    console.print(output, markup=False, highlight=False)
