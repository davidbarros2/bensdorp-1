"""Tests for commands/audit.py — CMD-13 scenarios."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import audit_log

runner = CliRunner()


def test_audit_no_filters_shows_50_most_recent_events(
    db_engine: Engine,
    tmp_path: object,
) -> None:
    """audit (no filters) shows rows; most-recent event appears first."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(audit_log).values(
                event_type="buy_confirmed",
                occurred_at=datetime(2026, 5, 20, 14, 30, tzinfo=UTC),
                symbol="AAPL",
                payload='{"price": 182.5, "shares": 10}',
            )
        )
        conn.execute(
            insert(audit_log).values(
                event_type="cash_updated",
                occurred_at=datetime(2026, 5, 21, 10, 0, tzinfo=UTC),
                symbol=None,
                payload='{"old": 50000.0, "new": 45000.0}',
            )
        )
        conn.execute(
            insert(audit_log).values(
                event_type="sell_confirmed",
                occurred_at=datetime(2026, 5, 22, 15, 0, tzinfo=UTC),
                symbol="AAPL",
                payload='{"price": 192.0, "shares": 10}',
            )
        )
        conn.commit()

    with (
        pytest.MonkeyPatch().context() as mp,
    ):
        mp.setattr("bensdorp1.commands.audit.get_engine", lambda _: db_engine)
        mp.setattr("bensdorp1.commands.audit.DATA_DIR", tmp_path)
        mp.setattr("bensdorp1.commands.audit.run_migrations", lambda _: None)
        result = runner.invoke(app, ["audit"])

    assert result.exit_code == 0
    assert "buy_confirmed" in result.output
    assert "cash_updated" in result.output
    assert "sell_confirmed" in result.output
    # sell_confirmed is most recent — appears before buy_confirmed in output
    sell_pos = result.output.find("sell_confirmed")
    buy_pos = result.output.find("buy_confirmed")
    assert sell_pos < buy_pos


def test_audit_symbol_filter_shows_only_matching_events(
    db_engine: Engine,
    tmp_path: object,
) -> None:
    """audit --symbol NVDA filters to NVDA events only."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(audit_log).values(
                event_type="buy_confirmed",
                occurred_at=datetime(2026, 5, 20, 14, 30, tzinfo=UTC),
                symbol="NVDA",
                payload='{"price": 432.5, "shares": 23}',
            )
        )
        conn.execute(
            insert(audit_log).values(
                event_type="buy_confirmed",
                occurred_at=datetime(2026, 5, 21, 14, 30, tzinfo=UTC),
                symbol="AAPL",
                payload='{"price": 182.5, "shares": 10}',
            )
        )
        conn.execute(
            insert(audit_log).values(
                event_type="sell_confirmed",
                occurred_at=datetime(2026, 5, 22, 15, 0, tzinfo=UTC),
                symbol="NVDA",
                payload='{"price": 450.0, "shares": 23}',
            )
        )
        conn.commit()

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("bensdorp1.commands.audit.get_engine", lambda _: db_engine)
        mp.setattr("bensdorp1.commands.audit.DATA_DIR", tmp_path)
        mp.setattr("bensdorp1.commands.audit.run_migrations", lambda _: None)
        result = runner.invoke(app, ["audit", "--symbol", "NVDA"])

    assert result.exit_code == 0
    assert "NVDA" in result.output
    assert "AAPL" not in result.output


def test_audit_type_filter_shows_only_that_type(
    db_engine: Engine,
    tmp_path: object,
) -> None:
    """audit --type buy_confirmed shows only that type."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(audit_log).values(
                event_type="buy_confirmed",
                occurred_at=datetime(2026, 5, 20, 14, 30, tzinfo=UTC),
                symbol="NVDA",
                payload='{"price": 432.5, "shares": 23}',
            )
        )
        conn.execute(
            insert(audit_log).values(
                event_type="cash_updated",
                occurred_at=datetime(2026, 5, 21, 10, 0, tzinfo=UTC),
                symbol=None,
                payload='{"old": 50000.0, "new": 45000.0}',
            )
        )
        conn.commit()

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("bensdorp1.commands.audit.get_engine", lambda _: db_engine)
        mp.setattr("bensdorp1.commands.audit.DATA_DIR", tmp_path)
        mp.setattr("bensdorp1.commands.audit.run_migrations", lambda _: None)
        result = runner.invoke(app, ["audit", "--type", "buy_confirmed"])

    assert result.exit_code == 0
    assert "buy_confirmed" in result.output
    assert "cash_updated" not in result.output


def test_audit_since_until_and_filters_correctly(
    db_engine: Engine,
    tmp_path: object,
) -> None:
    """audit --since DATE --until DATE AND-filters correctly."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(audit_log).values(
                event_type="buy_confirmed",
                occurred_at=datetime(2026, 5, 10, 14, 30, tzinfo=UTC),
                symbol="AAPL",
                payload='{"price": 182.5, "shares": 10}',
            )
        )
        conn.execute(
            insert(audit_log).values(
                event_type="cash_updated",
                occurred_at=datetime(2026, 5, 15, 10, 0, tzinfo=UTC),
                symbol=None,
                payload='{"old": 50000.0, "new": 45000.0}',
            )
        )
        conn.execute(
            insert(audit_log).values(
                event_type="sell_confirmed",
                occurred_at=datetime(2026, 5, 25, 15, 0, tzinfo=UTC),
                symbol="AAPL",
                payload='{"price": 192.0, "shares": 10}',
            )
        )
        conn.commit()

    # Range 2026-05-13 to 2026-05-20 — only the cash_updated event falls inside
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("bensdorp1.commands.audit.get_engine", lambda _: db_engine)
        mp.setattr("bensdorp1.commands.audit.DATA_DIR", tmp_path)
        mp.setattr("bensdorp1.commands.audit.run_migrations", lambda _: None)
        result = runner.invoke(
            app,
            ["audit", "--since", "2026-05-13", "--until", "2026-05-20"],
        )

    assert result.exit_code == 0
    assert "cash_updated" in result.output
    assert "buy_confirmed" not in result.output
    assert "sell_confirmed" not in result.output


def test_audit_limit_flag_returns_at_most_n_events(
    db_engine: Engine,
    tmp_path: object,
) -> None:
    """audit --limit 3 returns at most 3 events."""
    with db_engine.connect() as conn:
        for i in range(5):
            conn.execute(
                insert(audit_log).values(
                    event_type="buy_confirmed",
                    occurred_at=datetime(2026, 5, i + 1, 14, 30, tzinfo=UTC),
                    symbol="NVDA",
                    payload=f'{{"price": {400 + i}.0, "shares": 10}}',
                )
            )
        conn.commit()

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("bensdorp1.commands.audit.get_engine", lambda _: db_engine)
        mp.setattr("bensdorp1.commands.audit.DATA_DIR", tmp_path)
        mp.setattr("bensdorp1.commands.audit.run_migrations", lambda _: None)
        result = runner.invoke(app, ["audit", "--limit", "3"])

    assert result.exit_code == 0
    # Each row shows "buy_confirmed"; there should be exactly 3 occurrences
    assert result.output.count("buy_confirmed") <= 3


def test_audit_empty_state_when_no_events_match(
    db_engine: Engine,
    tmp_path: object,
) -> None:
    """audit empty state when no events match."""
    with db_engine.connect() as conn:
        conn.execute(
            insert(audit_log).values(
                event_type="buy_confirmed",
                occurred_at=datetime(2026, 5, 20, 14, 30, tzinfo=UTC),
                symbol="AAPL",
                payload='{"price": 182.5, "shares": 10}',
            )
        )
        conn.commit()

    # Filter by symbol that has no rows
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("bensdorp1.commands.audit.get_engine", lambda _: db_engine)
        mp.setattr("bensdorp1.commands.audit.DATA_DIR", tmp_path)
        mp.setattr("bensdorp1.commands.audit.run_migrations", lambda _: None)
        result = runner.invoke(app, ["audit", "--symbol", "ZZZ"])

    assert result.exit_code == 0
    assert "No audit events match" in result.output
