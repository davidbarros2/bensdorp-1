"""Audit event type enum and log_event() writer for the audit_log table.

Depends on: bensdorp1.db.schema (audit_log table)
Used by: all commands that change state (buy, sell, fix, cash, scan, init, restore)
"""

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from bensdorp1.db.schema import audit_log


class AuditEventType(StrEnum):
    """All 17 audit event types from STATE-04.

    StrEnum members ARE strings — no .value needed for SQLite TEXT storage.
    str(AuditEventType.BUY_CONFIRMED) == "buy_confirmed"  # True
    """

    SYSTEM_INITIALIZED = "system_initialized"
    SCAN_PERFORMED = "scan_performed"
    BUY_CONFIRMED = "buy_confirmed"
    SELL_CONFIRMED = "sell_confirmed"
    SELL_MANUAL = "sell_manual"
    TRANSACTION_CORRECTED = "transaction_corrected"
    CASH_UPDATED = "cash_updated"
    CONSTITUENTS_UPDATED = "constituents_updated"
    CONSTITUENTS_DISCREPANCY = "constituents_discrepancy"
    SPLIT_APPLIED = "split_applied"
    POSITION_DELISTED_FROM_INDEX = "position_delisted_from_index"
    REGIME_CHANGE_BULL_TO_BEAR = "regime_change_bull_to_bear"
    REGIME_CHANGE_BEAR_TO_BULL = "regime_change_bear_to_bull"
    DATA_FETCH_FAILED = "data_fetch_failed"
    CATCH_UP_PERFORMED = "catch_up_performed"
    RESTORE_PERFORMED = "restore_performed"
    POSITION_CLOSED_MANUAL = "position_closed_manual"


def log_event(
    engine: Engine,
    event_type: AuditEventType,
    symbol: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Insert one structured event into the audit log.

    Uses parameterized SQL — no injection risk.
    """
    with engine.connect() as conn:
        conn.execute(
            insert(audit_log).values(
                event_type=str(event_type),  # StrEnum -> str for unambiguous storage
                occurred_at=datetime.now(UTC),
                symbol=symbol,
                payload=json.dumps(payload) if payload is not None else None,
            )
        )
        conn.commit()
