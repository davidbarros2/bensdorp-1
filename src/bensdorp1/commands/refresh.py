"""Force re-fetch of S&P 500 constituents — CMD-15."""

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select
from sqlalchemy.engine import Engine

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.data import refresh_constituents
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import constituents_cache
from bensdorp1.ui import SpinnerContext, print_success, render_table


def _read_symbols(engine: Engine) -> set[str]:
    """Return all symbols currently in constituents_cache."""
    with engine.connect() as conn:
        rows = conn.execute(select(constituents_cache.c.symbol)).fetchall()
    return {row.symbol for row in rows}


@app.command(rich_help_panel="System")
def refresh() -> None:
    """Force re-fetch and re-verification of S&P 500 constituents."""
    # 1. DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # 2. Snapshot BEFORE
    symbols_before = _read_symbols(engine)

    # 3. Fetch (wrapped with spinner)
    with SpinnerContext("Fetching S&P 500 constituents...", console=console):
        refresh_constituents(engine)

    # 4. Snapshot AFTER
    symbols_after = _read_symbols(engine)

    # 5. Compute diff
    added = sorted(symbols_after - symbols_before)
    removed = sorted(symbols_before - symbols_after)
    total_after = len(symbols_after)

    # 6. Branch on diff
    if not added and not removed:
        print_success(
            f"Constituents up to date. {total_after} tickers, no changes.",
            console=console,
        )
        raise typer.Exit()

    # Changes found — print summary + table
    console.print()
    console.print(
        Text(
            f"Added: {len(added)} tickers, Removed: {len(removed)} ticker(s).",
        ),
        markup=False,
        highlight=False,
    )
    max_len = max(len(added), len(removed))
    rows: list[list[str]] = []
    for i in range(max_len):
        rows.append(
            [
                added[i] if i < len(added) else "",
                removed[i] if i < len(removed) else "",
            ]
        )
    render_table(
        columns=[("Added", "left"), ("Removed", "left")],
        rows=rows,
        console=console,
    )
    raise typer.Exit()
