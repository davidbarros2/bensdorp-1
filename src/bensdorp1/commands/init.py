"""First-run setup command: creates database, downloads history, records cash."""

import time
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.data import get_constituents, update_price_data
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import config as config_table
from bensdorp1.ui import (
    TrackContext,
    confirm_prompt,
    feedback,
    format_price,
    number_prompt,
    print_error,
    render_kv_block,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SEPARATOR: str = "=" * 64  # matches spec §7.1 exactly — 64 '=' characters
CASH_HEADER: str = "Available cash"
CASH_SEPARATOR: str = "-" * len(CASH_HEADER)  # 14 dashes, matching spec §7.1 Step 2


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _tilde_path(p: Path) -> str:
    """Replace Path.home() prefix with '~/'. Falls back to str(p) if not under home."""
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)


def _format_elapsed(seconds: float) -> str:
    """Format total elapsed time as 'Xm Ys' when >= 60s, or 'Xs' when < 60s."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _store_cash(engine: Engine, amount: float) -> None:
    """Upsert key='available_cash' into the config table.

    Value stored as f"{amount:.2f}" for deterministic float precision.
    """
    now = datetime.now(UTC)
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


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="Setup")
def init() -> None:
    """First-run setup: create data directory, download history, record cash."""
    # 1. GUARD: refuse if DB already exists
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    if db_path.exists():
        print_error(
            "System already initialized.",
            actions=[
                "Delete the file and run `bensdorp1 init` again.",
                "Run `bensdorp1 restore PATH` to replace with a backup.",
            ],
        )
        raise typer.Exit(1)

    # 2. CONSOLE
    console = Console()

    # 3. WELCOME SCREEN (Step 1 per spec §7.1)
    console.print(Text(SEPARATOR))
    console.print(Text("bensdorp1 — System #1: Trend following on S&P 500 stocks"))
    console.print(Text("First-time setup"))
    console.print(Text(SEPARATOR))
    console.print()
    console.print(Text("This is a one-time setup. It will:"))
    console.print()
    console.print(Text("  1. Create local database in ~/bensdorp1/"))
    console.print(Text("  2. Download current S&P 500 constituents list"))
    console.print(Text("  3. Download 220 days of price history for all constituents"))
    console.print(Text("  4. Register your initial available cash"))
    console.print()
    console.print(
        Text("Step 3 may take 5 to 10 minutes depending on connection speed.")
    )
    console.print()

    # 4. PRE-CONFIRMATION PROMPT
    try:
        confirmed = confirm_prompt("Continue?", console=console)
    except KeyboardInterrupt:
        console.print()
        console.print(Text("Operation aborted. No changes were made."))
        raise typer.Exit() from None
    if not confirmed:
        raise typer.Exit()
    console.print()

    # 5. CASH DECLARATION BLOCK (Step 2 per spec §7.1)
    try:
        console.print(Text(CASH_HEADER))
        console.print(Text(CASH_SEPARATOR))
        console.print(Text("Enter the amount of cash you have available for trading."))
        console.print(
            Text("This is the amount the system will use to size new positions.")
        )
        console.print()
        cash: float
        while True:
            cash = number_prompt("Available cash", "USD", console=console)
            if cash <= 0:
                console.print(Text("Error: Cash must be greater than zero."))
                continue
            console.print()
            console.print(Text(f"Available cash: {format_price(cash)}"))
            console.print()
            if confirm_prompt("Confirm?", console=console):
                break
            # user said n — loop back to re-enter
    except KeyboardInterrupt:
        console.print()
        console.print(Text("Operation aborted. No changes were made."))
        raise typer.Exit() from None
    console.print()

    # 6. SETUP EXECUTION (Step 3 per spec §7.1)
    start_time = time.monotonic()
    engine = get_engine(db_path)
    run_migrations(engine)
    console.print(Text("Setting up your system"))
    console.print()

    constituents: dict[str, str]
    with feedback.multi_step(3, console=console) as ms:
        # Step [1/3] — Fetching S&P 500 constituents
        with ms.step("Fetching S&P 500 constituents"):
            constituents = get_constituents(engine)
        # Print detail lines AFTER the with-block exits (not inside — Pitfall 1)
        console.print(Text("      Source: Wikipedia"))
        console.print(Text(f"      Stocks found: {len(constituents)}"))
        console.print()

        # Step [2/3] — Verifying against secondary source
        with ms.step("Verifying against secondary source"):
            # cross-check already happened inside get_constituents()
            # step 2 is a display beat
            pass
        console.print()

        # Step [3/3] — Downloading price history
        symbols = list(constituents.keys())
        with ms.step("Downloading price history", total=len(symbols)) as _track:
            assert isinstance(_track, TrackContext), (
                f"Expected TrackContext from ms.step(total=...), got {type(_track)!r}"
            )
            for symbol in symbols:
                update_price_data(engine, [symbol])
                _track.advance(symbol)

    elapsed = time.monotonic() - start_time

    # 7. POST-DOWNLOAD STATE
    _store_cash(engine, cash)
    log_event(
        engine,
        AuditEventType.SYSTEM_INITIALIZED,
        payload={
            "constituent_count": len(constituents),
            "cash": cash,
            "history_days": 220,
        },
    )
    create_backup(engine, DATA_DIR / "backups")

    # 8. COMPLETION SUMMARY (Step 4 per spec §7.1)
    console.print()
    console.print(Text(SEPARATOR))
    console.print(Text("Setup complete"))
    console.print(Text(SEPARATOR))
    console.print()
    render_kv_block(
        {
            "Database created": _tilde_path(db_path),
            "Backups location": _tilde_path(DATA_DIR / "backups") + "/",
            "Constituents": f"{len(constituents)} stocks",
            "History downloaded": "220 trading days",
            "Available cash": format_price(cash),
            "Total time": _format_elapsed(elapsed),
        },
        console,
    )
    console.print()
    console.print(Text("Next steps:"))
    console.print(
        Text("  1. Wait for end-of-day market close (16:00 ET / 21:00 Lisbon)")
    )
    console.print(
        Text(
            "  2. Run `bensdorp1 scan` to see today's buy candidates and exit triggers"
        )
    )
    console.print(Text("  3. Run `bensdorp1 help` to see all available commands"))
