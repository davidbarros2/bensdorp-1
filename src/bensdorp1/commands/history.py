"""Show a compact table of past scans — CMD-05."""

import datetime
from datetime import UTC
from typing import Any

import typer
from rich.console import Console
from sqlalchemy import select

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import scan_candidates, scans
from bensdorp1.ui import format_date, print_error, print_info, render_table


@app.command(rich_help_panel="Daily operation")
def history(
    limit: int = typer.Option(20, "--limit", help="Maximum rows to show."),
    since: str | None = typer.Option(
        None, "--since", help="Show scans on or after YYYY-MM-DD."
    ),
) -> None:
    """Show a compact table of past scans."""
    # A. DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # B. Parse --since if provided (Pitfall 5)
    since_dt: datetime.datetime | None = None
    if since is not None:
        try:
            since_date = datetime.date.fromisoformat(since)
        except ValueError:
            print_error(
                f"Invalid --since value {since!r}. Expected YYYY-MM-DD.",
                console=console,
            )
            raise typer.Exit(code=1) from None
        since_dt = datetime.datetime(
            since_date.year, since_date.month, since_date.day, tzinfo=UTC
        )

    # C. Build optional WHERE filters (SP-7)
    filters: list[Any] = []
    if since_dt is not None:
        filters.append(scans.c.scan_date >= since_dt)

    # D. Query scans
    with engine.connect() as conn:
        scan_rows = conn.execute(
            select(scans)
            .where(*filters)
            .order_by(scans.c.scan_date.desc())
            .limit(limit)
        ).fetchall()

        if not scan_rows:
            if not filters:
                # No filters and no rows → table is empty
                print_info(
                    "No scans recorded yet."
                    " Run `bensdorp1 scan` on a trading day after 16:30 ET.",
                    console=console,
                )
            else:
                print_info("No scans match the given filters.", console=console)
            raise typer.Exit()

        # E. Build rows with per-scan top-3 sub-query (RESEARCH Pattern 4)
        rows: list[list[str]] = []
        for scan in scan_rows:
            cand_rows = conn.execute(
                select(scan_candidates.c.symbol)
                .where(scan_candidates.c.scan_id == scan.id)
                .order_by(scan_candidates.c.rank.asc())
                .limit(3)
            ).fetchall()
            top3 = ", ".join(r.symbol for r in cand_rows) if cand_rows else "—"
            regime_label = "Bull" if scan.regime_active else "Bear"
            rows.append(
                [
                    format_date(scan.scan_date.date()),
                    regime_label,
                    str(scan.exit_trigger_count),
                    str(scan.candidate_count),
                    top3,
                ]
            )

    # F. Render table (D-05: single comma-separated Top candidates column)
    render_table(
        columns=[
            ("Date", "left"),
            ("Regime", "left"),
            ("Exits", "right"),
            ("Candidates", "right"),
            ("Top candidates", "left"),
        ],
        rows=rows,
        console=console,
    )
