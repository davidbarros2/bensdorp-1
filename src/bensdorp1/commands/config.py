"""Show current system configuration (CMD-12)."""

from importlib.metadata import version as pkg_version

import typer
from rich.console import Console
from sqlalchemy import select

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR, USER_TZ
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import config as config_table
from bensdorp1.ui import format_price, render_kv_block


@app.command(rich_help_panel="System")
def config() -> None:
    """Show current configuration: cash, directory, timezone, version."""
    # SP-1: DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    with engine.connect() as conn:
        cash_row = conn.execute(
            select(config_table.c.value).where(
                config_table.c.key == "available_cash"
            )
        ).fetchone()

    if cash_row is not None and cash_row.value is not None:
        cash_str = format_price(float(cash_row.value))
    else:
        cash_str = "Not configured"

    data: dict[str, str] = {
        "Cash": cash_str,
        "Data directory": str(DATA_DIR),
        "Timezone": f"{USER_TZ.key.split('/')[-1]} (BENSDORP1_USER_TZ)",
        "Version": pkg_version("bensdorp1"),
    }
    render_kv_block(data, console)
    raise typer.Exit()
