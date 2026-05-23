"""Single source of truth for all DDL.

Defines the shared MetaData singleton and all 7 Table objects.
No imports from the db/ package. engine.py, backup.py, and audit.py import from here.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
)

metadata: MetaData = MetaData()

config: Table = Table(
    "config",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=True),
    Column("updated_at", DateTime, nullable=False),
)

scans: Table = Table(
    "scans",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scan_date", DateTime, nullable=False, unique=True),
    Column("regime_active", Boolean, nullable=False),
    Column("candidate_count", Integer, nullable=False),
    Column("exit_trigger_count", Integer, nullable=False),
    Column("raw_output", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
)

positions: Table = Table(
    "positions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False),
    Column("entry_date", DateTime, nullable=False),
    Column("entry_close", Float, nullable=False),
    Column("shares", Integer, nullable=False),
    Column("initial_stop", Float, nullable=False),
    Column("highest_close", Float, nullable=False),
    Column("trailing_stop", Float, nullable=False),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=True),
    Column("closed_at", DateTime, nullable=True),
    Column("exit_price", Float, nullable=True),
    Column("realized_pnl", Float, nullable=True),
)
Index(
    "ix_positions_open_symbol",
    positions.c.symbol,
    unique=True,
    sqlite_where=(positions.c.closed_at == None),  # noqa: E711
)

audit_log: Table = Table(
    "audit_log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", DateTime, nullable=False),
    Column("symbol", Text, nullable=True),
    Column("payload", Text, nullable=True),
)
Index("ix_audit_log_occurred_at", audit_log.c.occurred_at)
Index("ix_audit_log_symbol", audit_log.c.symbol)
Index("ix_audit_log_event_type", audit_log.c.event_type)

scan_candidates: Table = Table(
    "scan_candidates",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=False),
    Column("symbol", Text, nullable=False),
    Column("rank", Integer, nullable=False),
    Column("roc200", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("suggested_shares", Integer, nullable=False),
)

constituents_cache: Table = Table(
    "constituents_cache",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False, unique=True),
    Column("company_name", Text, nullable=True),
    Column("fetched_at", DateTime, nullable=False),
)

price_daily: Table = Table(
    "price_daily",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False),
    Column("trade_date", DateTime, nullable=False),
    Column("close", Float, nullable=False),
    Column("volume", Integer, nullable=True),
)
Index(
    "ix_price_daily_symbol_date",
    price_daily.c.symbol,
    price_daily.c.trade_date,
    unique=True,
)
