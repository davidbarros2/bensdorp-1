"""Show system health diagnostic dashboard (CMD-14)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import func, select
from sqlalchemy import text as sa_text
from sqlalchemy.engine import Engine

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.data.calendar import n_trading_days_ago
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import (
    constituents_cache,
    positions,
    price_daily,
    scan_exit_triggers,
    scans,
)
from bensdorp1.ui import format_date, format_timezone_pair, render_kv_block

# ---------------------------------------------------------------------------
# Thresholds (days)
# ---------------------------------------------------------------------------

# Constituents: OK (<=7 days) → STALE (<=14 days) → OUTDATED (>14 days)
_STALE_DAYS_CONSTITUENTS = 7
_OUTDATED_DAYS_CONSTITUENTS = 14

# Backup: OK (<=3 days) → STALE (<=7 days) → OUTDATED (>7 days)
_STALE_DAYS_BACKUP = 3
_OUTDATED_DAYS_BACKUP = 7

# Severity ordering: OK < STALE < OUTDATED (used in both data and backup sections)


# ---------------------------------------------------------------------------
# Section helpers
# ---------------------------------------------------------------------------


def _constituents_section(engine: Engine) -> dict[str, str]:
    """Return Data status section kv dict."""
    with engine.connect() as conn:
        row = conn.execute(
            select(
                func.count(constituents_cache.c.id),
                func.max(constituents_cache.c.fetched_at),
            )
        ).fetchone()

        price_count_row = conn.execute(select(func.count(price_daily.c.id))).scalar()

    ticker_count: int = row[0] if row is not None else 0
    last_fetched_raw: datetime | None = row[1] if row is not None else None

    price_count: int = price_count_row if price_count_row is not None else 0

    if ticker_count == 0 or last_fetched_raw is None:
        constituents_value = "0 tickers (cache empty)  [OUTDATED]"
    else:
        # Coerce SQLite-returned naive datetime to UTC-aware
        last_fetched: datetime = last_fetched_raw
        if last_fetched.tzinfo is None:
            last_fetched = last_fetched.replace(tzinfo=UTC)

        age = datetime.now(UTC) - last_fetched
        if age <= timedelta(days=_STALE_DAYS_CONSTITUENTS):
            label = "OK"
        elif age <= timedelta(days=_OUTDATED_DAYS_CONSTITUENTS):
            label = "STALE"
        else:
            label = "OUTDATED"

        constituents_value = (
            f"{ticker_count} tickers, last updated {format_date(last_fetched.date())}"
            f"  [{label}]"
        )

    return {
        "Constituents": constituents_value,
        "Price cache": f"{price_count:,} rows",
    }


def _backup_section(backups_dir: Path) -> dict[str, str]:
    """Return Backup status section kv dict."""
    no_backups: dict[str, str] = {
        "Last backup": "No backups found",
        "Location": str(backups_dir),
        "Snapshots": "0",
    }

    if not backups_dir.exists():
        return no_backups

    # Count all .db files in the directory (including bensdorp1-latest.db)
    db_files = sorted(
        backups_dir.glob("*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not db_files:
        return no_backups

    newest = db_files[0]
    mtime: datetime = datetime.fromtimestamp(newest.stat().st_mtime, tz=UTC)
    now = datetime.now(UTC)
    age_days = (now - mtime).days
    if age_days <= _STALE_DAYS_BACKUP:
        label = "OK"
    elif age_days <= _OUTDATED_DAYS_BACKUP:
        label = "STALE"
    else:
        label = "OUTDATED"

    return {
        "Last backup": f"{format_timezone_pair(mtime)}  [{label}]",
        "Location": str(newest),
        "Snapshots": str(len(db_files)),  # includes bensdorp1-latest.db
    }


def _database_section(db_path: Path, engine: Engine) -> dict[str, str]:
    """Return Database status section kv dict."""
    size_bytes = db_path.stat().st_size if db_path.exists() else 0
    if size_bytes >= 1024 * 1024:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        size_str = f"{size_bytes / 1024:.1f} KB"

    with engine.connect() as conn:
        rows = conn.execute(sa_text("PRAGMA integrity_check")).fetchall()

    integrity_ok = len(rows) == 1 and rows[0][0] == "ok"

    return {
        "File size": size_str,
        "Integrity check": "OK" if integrity_ok else "FAILED",
    }


def _operational_section(engine: Engine) -> dict[str, str]:
    """Return Operational status section kv dict."""
    with engine.connect() as conn:
        last_scan_raw = conn.execute(select(func.max(scans.c.scan_date))).scalar()

        open_count_raw = conn.execute(
            select(func.count(positions.c.id)).where(positions.c.closed_at.is_(None))
        ).scalar()

        pending_count_raw = conn.execute(
            select(func.count(scan_exit_triggers.c.id))
            .join(positions, scan_exit_triggers.c.position_id == positions.c.id)
            .where(positions.c.closed_at.is_(None))
        ).scalar()

    open_count: int = open_count_raw if open_count_raw is not None else 0
    pending_count: int = pending_count_raw if pending_count_raw is not None else 0

    if last_scan_raw is None:
        last_scan_value = "Never  [STALE]"
    else:
        # Coerce SQLite-returned naive datetime to UTC-aware
        last_scan_dt: datetime = last_scan_raw
        if isinstance(last_scan_dt, datetime) and last_scan_dt.tzinfo is None:
            last_scan_dt = last_scan_dt.replace(tzinfo=UTC)

        today = datetime.now(UTC).date()
        try:
            boundary = n_trading_days_ago(1, reference=today)
            scan_date = (
                last_scan_dt.date()
                if isinstance(last_scan_dt, datetime)
                else last_scan_dt
            )
            label = "OK" if scan_date >= boundary else "STALE"
        except (ValueError, TypeError):
            # TypeError: SQLite may return the aggregate as a raw str;
            # comparing str >= date raises TypeError at runtime.
            label = "STALE"

        scan_date_display = (
            format_date(last_scan_dt.date())
            if isinstance(last_scan_dt, datetime)
            else str(last_scan_dt)
        )
        last_scan_value = f"{scan_date_display}  [{label}]"

    return {
        "Last scan": last_scan_value,
        "Open positions": str(open_count),
        "Pending exits": str(pending_count),
    }


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="System")
def status() -> None:
    """Show a diagnostic dashboard of system health."""
    # SP-1: DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    backups_dir = DATA_DIR / "backups"

    data_section = _constituents_section(engine)
    backup_section = _backup_section(backups_dir)
    database_section = _database_section(db_path, engine)
    operational_section = _operational_section(engine)

    # Data status
    console.print(Text("Data status"), markup=False, highlight=False)
    console.print(Text("-----------"), markup=False, highlight=False)
    render_kv_block(data_section, console)
    console.print()

    # Backup status
    console.print(Text("Backup status"), markup=False, highlight=False)
    console.print(Text("-------------"), markup=False, highlight=False)
    render_kv_block(backup_section, console)
    console.print()

    # Database status
    console.print(Text("Database status"), markup=False, highlight=False)
    console.print(Text("---------------"), markup=False, highlight=False)
    render_kv_block(database_section, console)
    console.print()

    # Operational status
    console.print(Text("Operational status"), markup=False, highlight=False)
    console.print(Text("------------------"), markup=False, highlight=False)
    render_kv_block(operational_section, console)

    raise typer.Exit()
