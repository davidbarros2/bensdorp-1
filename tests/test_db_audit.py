"""Tests for audit.py: AuditEventType StrEnum and log_event().

Covers STATE-04: all 17 event types insertable and queryable by their string value.
"""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.schema import audit_log


@pytest.mark.parametrize("event_type", list(AuditEventType))
def test_all_event_types_insertable(
    db_engine: Engine, event_type: AuditEventType
) -> None:
    log_event(db_engine, event_type)
    with db_engine.connect() as conn:
        row = conn.execute(
            select(audit_log).where(audit_log.c.event_type == str(event_type))
        ).fetchone()
    assert row is not None


def test_log_event_with_symbol(db_engine: Engine) -> None:
    log_event(db_engine, AuditEventType.BUY_CONFIRMED, symbol="AAPL")
    with db_engine.connect() as conn:
        row = conn.execute(
            select(audit_log).where(audit_log.c.symbol == "AAPL")
        ).fetchone()
    assert row is not None
    assert row.symbol == "AAPL"  # type: ignore[union-attr]


def test_log_event_with_payload(db_engine: Engine) -> None:
    log_event(
        db_engine,
        AuditEventType.SCAN_PERFORMED,
        payload={"regime_active": True, "candidate_count": 5},
    )
    with db_engine.connect() as conn:
        row = conn.execute(
            select(audit_log).where(audit_log.c.event_type == "scan_performed")
        ).fetchone()
    assert row is not None
    decoded = json.loads(row.payload)  # type: ignore[union-attr]
    assert decoded["regime_active"] is True
    assert decoded["candidate_count"] == 5


def test_log_event_without_symbol_or_payload(db_engine: Engine) -> None:
    log_event(db_engine, AuditEventType.REGIME_CHANGE_BULL_TO_BEAR)
    with db_engine.connect() as conn:
        row = conn.execute(
            select(audit_log).where(
                audit_log.c.event_type == "regime_change_bull_to_bear"
            )
        ).fetchone()
    assert row is not None
    assert row.symbol is None  # type: ignore[union-attr]
    assert row.payload is None  # type: ignore[union-attr]


def test_log_event_inserts_multiple_rows(db_engine: Engine) -> None:
    log_event(db_engine, AuditEventType.DATA_FETCH_FAILED)
    log_event(db_engine, AuditEventType.DATA_FETCH_FAILED)
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(audit_log).where(audit_log.c.event_type == "data_fetch_failed")
        ).fetchall()
    assert len(rows) == 2


def test_audit_event_type_str_value(db_engine: Engine) -> None:
    assert str(AuditEventType.SYSTEM_INITIALIZED) == "system_initialized"
    assert str(AuditEventType.POSITION_CLOSED_MANUAL) == "position_closed_manual"
    assert str(AuditEventType.BUY_CONFIRMED) == "buy_confirmed"
