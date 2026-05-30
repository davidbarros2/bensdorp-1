"""Replace current database with a backup file — CMD-02."""

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text
from sqlalchemy.engine import URL, create_engine

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import AuditEventType, get_engine, log_event, run_migrations
from bensdorp1.ui import (
    confirm_prompt,
    format_timezone_pair,
    print_error,
    print_success,
    render_kv_block,
)

EXPECTED_TABLES: frozenset[str] = frozenset(
    {
        "config",
        "scans",
        "positions",
        "audit_log",
        "scan_candidates",
        "scan_exit_triggers",
        "constituents_cache",
        "price_daily",
    }
)


@app.command(rich_help_panel="Setup")
def restore(
    path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to the backup .db file to restore."
    ),
) -> None:
    """Replace the active database with a backup file."""
    # 1. DB entry triad
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    # 2. PATH resolution + existence check
    resolved = path.resolve()
    if not resolved.exists() or not resolved.is_file():
        print_error(f"File not found: {resolved}", console=console)
        raise typer.Exit(code=1)

    # 3. Validation via secondary engine (dispose in finally — Windows safety)
    integrity_ok = False
    schema_valid = False
    existing_tables: frozenset[str] = frozenset()
    val_url = URL.create("sqlite+pysqlite", database=str(resolved))
    val_engine = create_engine(val_url)
    try:
        with val_engine.connect() as conn:
            rows = conn.execute(sa_text("PRAGMA integrity_check")).fetchall()
            integrity_ok = len(rows) == 1 and rows[0][0] == "ok"
        inspector = sa_inspect(val_engine)
        existing_tables = frozenset(inspector.get_table_names())
        schema_valid = EXPECTED_TABLES.issubset(existing_tables)
    except Exception:
        integrity_ok = False
        schema_valid = False
    finally:
        val_engine.dispose()  # CRITICAL on Windows (prevents [WinError 32])

    if not integrity_ok or not schema_valid:
        missing = sorted(EXPECTED_TABLES - existing_tables)
        print_error(
            "Backup file failed schema validation.",
            data={
                "Path": str(resolved),
                "Integrity OK": str(integrity_ok),
                "Missing tables": (
                    ", ".join(missing) if missing else "(could not inspect)"
                ),
            },
            console=console,
        )
        raise typer.Exit(code=1)

    # 4. File info block
    size_bytes = resolved.stat().st_size
    if size_bytes >= 1024 * 1024:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        size_str = f"{size_bytes / 1024:.1f} KB"
    mtime = datetime.fromtimestamp(resolved.stat().st_mtime, tz=UTC)
    console.print()
    console.print(Text("Validating backup file..."), markup=False, highlight=False)
    console.print()
    render_kv_block(
        {
            "Path": str(resolved),
            "Size": size_str,
            "Modified": format_timezone_pair(mtime),
        },
        console,
    )
    console.print()

    # 5. First confirmation
    try:
        confirmed = confirm_prompt(
            "Replace active database with this file?", console=console
        )
    except KeyboardInterrupt:
        raise typer.Exit() from None
    if not confirmed:
        raise typer.Exit()

    # 6. Second confirmation
    try:
        confirmed2 = confirm_prompt(
            "A pre-restore backup will be created first. "
            "This will overwrite your current database. Are you sure?",
            console=console,
        )
    except KeyboardInterrupt:
        raise typer.Exit() from None
    if not confirmed2:
        raise typer.Exit()

    # 7. Pre-restore backup
    backups_dir = DATA_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    pre_restore_path = backups_dir / f"bensdorp1-pre-restore-{ts}.db"
    shutil.copy2(db_path, pre_restore_path)

    # 8. File copy + error recovery
    try:
        shutil.copy2(resolved, db_path)
    except Exception as exc:
        print_error(
            "Failed to copy backup file to active database.",
            data={
                "Error": str(exc),
                "Pre-restore backup saved at": str(pre_restore_path),
            },
            console=console,
        )
        raise typer.Exit(code=1) from exc

    # 9. Log RESTORE_PERFORMED to the restored DB
    payload: dict[str, Any] = {
        "restored_from": str(resolved),
        "pre_restore_backup": str(pre_restore_path),
    }
    log_event(engine, AuditEventType.RESTORE_PERFORMED, payload=payload)

    # 10. Success message
    print_success(
        "Database restored. Run `bensdorp1 status` to verify.", console=console
    )
