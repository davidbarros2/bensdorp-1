"""Tests for STATE-01: schema creation, idempotency, table presence, and index presence.

All tests use the db_engine fixture from conftest.py which provides a fresh
file-based SQLite engine with all tables already created via metadata.create_all().
"""

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


def test_all_tables_created(db_engine: Engine) -> None:
    """STATE-01: run_migrations() creates exactly the 8 expected tables."""
    insp = inspect(db_engine)
    tables = set(insp.get_table_names())
    expected = {
        "config",
        "positions",
        "audit_log",
        "scans",
        "scan_candidates",
        "scan_exit_triggers",
        "constituents_cache",
        "price_daily",
    }
    assert expected == tables


def test_create_all_idempotent(db_engine: Engine) -> None:
    """STATE-01: calling metadata.create_all() a second time does not raise."""
    from bensdorp1.db.schema import metadata

    # First call already happened in the fixture; second call must be silent
    metadata.create_all(db_engine, checkfirst=True)


def test_partial_index_exists(db_engine: Engine) -> None:
    """STATE-01 / STATE-06: partial unique index on open positions is created."""
    insp = inspect(db_engine)
    index_names = {idx["name"] for idx in insp.get_indexes("positions")}
    assert "ix_positions_open_symbol" in index_names


def test_price_daily_unique_index_exists(db_engine: Engine) -> None:
    """Composite unique index on (symbol, trade_date) prevents duplicate price rows."""
    insp = inspect(db_engine)
    indexes = insp.get_indexes("price_daily")
    names = {i["name"] for i in indexes}
    assert "ix_price_daily_symbol_date" in names


def test_audit_log_indexes_exist(db_engine: Engine) -> None:
    """All three audit_log indexes are created for fast filtering."""
    insp = inspect(db_engine)
    names = {i["name"] for i in insp.get_indexes("audit_log")}
    expected_indexes = {
        "ix_audit_log_occurred_at",
        "ix_audit_log_symbol",
        "ix_audit_log_event_type",
    }
    assert expected_indexes.issubset(names)


def test_positions_columns(db_engine: Engine) -> None:
    """positions table has exactly 14 columns (Phase 8 adds closed_reason cols)."""
    insp = inspect(db_engine)
    cols = {c["name"] for c in insp.get_columns("positions")}
    assert {
        "id",
        "symbol",
        "entry_date",
        "entry_close",
        "shares",
        "initial_stop",
        "highest_close",
        "trailing_stop",
        "scan_id",
        "closed_at",
        "exit_price",
        "realized_pnl",
        "closed_reason",
        "closed_manual_reason",
    } == cols
