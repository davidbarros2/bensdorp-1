"""Lazy-cached SQLAlchemy engine singleton with BENSDORP1_HOME resolution.

Depends on: bensdorp1.db.schema (metadata)
Used by: all commands that need a DB connection (via run_migrations in init command)
"""

import os
import threading
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL, Engine, create_engine
from sqlalchemy.exc import OperationalError

from bensdorp1.db.schema import metadata

_engine: Engine | None = None
_engine_lock: threading.Lock = threading.Lock()


def _resolve_db_path(override: Path | None) -> Path:
    """Resolve the DB file path from override, env var, or default.

    Priority:
      1. override — returned as-is
      2. BENSDORP1_HOME env var — base is Path(env_value)
      3. default — base is Path.home() / "bensdorp1"

    The final path is always base / "data" / "bensdorp1.db".
    """
    if override is not None:
        return override
    home_env = os.environ.get("BENSDORP1_HOME")
    base = Path(home_env) if home_env else Path.home() / "bensdorp1"
    return base / "data" / "bensdorp1.db"


def _build_engine(path: Path) -> Engine:
    """Build a SQLAlchemy Engine for the given SQLite file path.

    Creates the parent directory if it does not exist before building the URL,
    so first-run users never see a cryptic OperationalError from SQLite.

    Uses URL.create() — not f-string URL construction — for correct Windows
    path handling (backslashes in str(Path) are handled by the pysqlite driver).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    url = URL.create("sqlite+pysqlite", database=str(path))
    return create_engine(url)


def get_engine(path: Path | None = None) -> Engine:
    """Return the cached engine, creating it on first call.

    Thread-safe via double-checked locking. The path argument is only
    consulted on first call; subsequent calls return the cached engine
    regardless of path.

    Args:
        path: Explicit DB file path (used in tests). If None, resolves
              BENSDORP1_HOME env var, defaulting to ~/bensdorp1/data/bensdorp1.db.
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = _build_engine(_resolve_db_path(path))
    return _engine


def run_migrations(engine: Engine) -> None:
    """Create all tables and apply incremental schema migrations idempotently.

    Called by all state-changing commands (buy, sell, fix, init) at command entry.
    Uses checkfirst=True so the base schema creation never raises on an existing DB.
    ALTER TABLE statements are wrapped in try/except OperationalError for idempotency —
    SQLite raises OperationalError: duplicate column name if the column already exists.
    """
    metadata.create_all(engine, checkfirst=True)
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE positions ADD COLUMN closed_reason TEXT",
            "ALTER TABLE positions ADD COLUMN closed_manual_reason TEXT",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except OperationalError:
                pass  # column already exists — idempotent


def _reset_engine_for_testing(replacement: Engine | None = None) -> None:
    """Test helper: dispose and replace the cached engine singleton.

    Call with no arguments to clear the cache (engine set to None).
    Call with a replacement Engine to inject a test engine.

    CRITICAL on Windows: always dispose before discarding the engine to
    release file handles (prevents [WinError 32] during tmp_path cleanup).
    """
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = replacement
