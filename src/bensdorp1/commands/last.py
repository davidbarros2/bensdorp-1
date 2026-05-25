"""Show the most recent scan output without re-running."""

import typer
from rich.console import Console
from sqlalchemy import select

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import scans
from bensdorp1.ui import print_info


@app.command(rich_help_panel="Daily operation")
def last() -> None:
    """Show the most recent scan output without re-running."""
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    with engine.connect() as conn:
        row = conn.execute(
            select(scans.c.scan_date, scans.c.raw_output)
            .order_by(scans.c.scan_date.desc())
            .limit(1)
        ).fetchone()

    if row is None:
        print_info(
            "No scans recorded yet."
            " Run `bensdorp1 scan` on a trading day after 16:30 ET.",
            console=console,
        )
    elif row.raw_output is None:
        print_info(
            "A scan record exists but has no output"
            " (the prior scan may have failed)."
            " Re-run `bensdorp1 scan --force` to retry.",
            console=console,
        )
    else:
        console.print(row.raw_output, markup=False, highlight=False)

    raise typer.Exit()
