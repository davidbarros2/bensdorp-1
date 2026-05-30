# Phase 11: Catch-Up Logic - Pattern Map

**Mapped:** 2026-05-30
**Files analyzed:** 5 (2 new, 3 modified)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/bensdorp1/commands/events.py` | utility (pure formatters) | transform | `src/bensdorp1/ui/styles.py` | role-match |
| `src/bensdorp1/commands/_scan_engine.py` | service (pipeline) | CRUD + event-driven | self (existing file) | exact — extension only |
| `src/bensdorp1/db/schema.py` | config (DDL) | CRUD | self (existing file) | exact — column addition |
| `src/bensdorp1/db/engine.py` | config (migration runner) | CRUD | self (existing file) | exact — ALTER TABLE addition |
| `tests/test_commands/test_catchup.py` | test | CRUD + event-driven | `tests/test_commands/test_scan_engine.py` | exact |

---

## Pattern Assignments

### `src/bensdorp1/commands/events.py` (utility, transform)

**Analog:** `src/bensdorp1/ui/styles.py`

**Imports pattern** (styles.py lines 1-13; adapt for events.py):
```python
"""Catch-up event template rendering functions (spec §8.9).

All 13 templates are pure string-formatting functions — no I/O, no DB access.
Callers wrap results in Text() before passing to capture.print().
"""

from __future__ import annotations

from datetime import date

from bensdorp1.ui import format_price
```

**Core pattern — pure formatter functions** (styles.py lines 39-58 as model):
```python
# Each function takes typed parameters, returns a plain str.
# No Rich markup in return values — callers use Text(result) for safety.

def format_price(value: float) -> str:
    """Format a USD price: $X,XXX.XX (rule 6.10)."""
    return f"${value:,.2f}"
```

Translate to events.py as 13 analogous functions with typed params and docstring citing the spec template number:

```python
def render_initial_stop_violated(
    symbol: str, trigger_date: date, close: float, stop: float
) -> str:
    """Template 1. Spec §8.9."""
    return (
        f"{symbol}  Initial stop violated on {trigger_date.isoformat()} "
        f"(close {format_price(close)} < stop {format_price(stop)}).\n"
        f"      Position remained open during your absence.\n"
        f"      An exit trigger from that day is still pending."
    )


def render_trailing_stop_violated(
    symbol: str, trigger_date: date, close: float, stop: float
) -> str:
    """Template 2. Spec §8.9."""
    ...


def render_new_highest_close(
    symbol: str, trigger_date: date, close: float, old_stop: float, new_stop: float
) -> str:
    """Template 3. D-03: show initial->final trailing stop only for composites.
    Spec §8.9."""
    ...


def render_composite(symbol: str, events: list[str]) -> str:
    """Template 13. One entry per position; events is a list of formatted strings.
    Spec §8.9."""
    bullets = "\n".join(f"      - {e}" for e in events)
    return f"{symbol}  Multiple events during your absence:\n{bullets}"
```

**No error handling needed** — pure formatters; no I/O, no DB, no exceptions expected.

**Module-level constants pattern** (from `_scan_engine.py` lines 71-72):
```python
# events.py does NOT need SEPARATOR — that belongs to the scan engine caller.
# All format_price calls go through bensdorp1.ui.format_price (no re-implementation).
```

---

### `src/bensdorp1/commands/_scan_engine.py` (service, CRUD + event-driven) — MODIFIED

**Analog:** self (existing file, extend in-place)

**_OpenPosition extension** (current definition lines 84-93; add three new fields):
```python
class _OpenPosition(NamedTuple):
    """Snapshot of an open position row from the DB."""

    id: int
    symbol: str
    entry_date: datetime
    initial_stop: float
    highest_close: float
    trailing_stop: float
    # Phase 11 additions:
    entry_close: float    # needed for split math (D-06)
    shares: int           # needed for split math (D-06)
    delisted: int         # 0 or 1; needed for _detect_delisted_positions (D-11)
```

**_query_open_positions extension pattern** (current lines 427-452; extend SELECT):
```python
def _query_open_positions(engine: Engine) -> list[_OpenPosition]:
    """Return all open positions (closed_at IS NULL)."""
    open_pos: list[_OpenPosition] = []
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                positions.c.id,
                positions.c.symbol,
                positions.c.entry_date,
                positions.c.initial_stop,
                positions.c.highest_close,
                positions.c.trailing_stop,
                positions.c.entry_close,   # Phase 11: add
                positions.c.shares,        # Phase 11: add
                positions.c.delisted,      # Phase 11: add
            ).where(positions.c.closed_at == None)  # noqa: E711
        ).fetchall()
    for row in rows:
        open_pos.append(
            _OpenPosition(
                id=row.id,
                symbol=row.symbol,
                entry_date=row.entry_date,
                initial_stop=row.initial_stop,
                highest_close=row.highest_close,
                trailing_stop=row.trailing_stop,
                entry_close=row.entry_close,   # Phase 11: add
                shares=row.shares,             # Phase 11: add
                delisted=row.delisted,         # Phase 11: add (defaults to 0)
            )
        )
    return open_pos
```

**In-memory snapshot replacement pattern** (current lines 529-536; use same pattern for splits):
```python
# EXISTING pattern in _update_position_stops — copy exactly for split updates:
open_positions[idx] = _OpenPosition(
    id=pos.id,
    symbol=pos.symbol,
    entry_date=pos.entry_date,
    initial_stop=pos.initial_stop,
    highest_close=new_hc,
    trailing_stop=new_ts,
    # Phase 11: also carry through new fields
    entry_close=pos.entry_close,
    shares=pos.shares,
    delisted=pos.delisted,
)
```

**DB UPDATE pattern** (current lines 521-527; use for _apply_splits):
```python
# EXISTING pattern — parameterized SQLAlchemy update, always conn.commit() after:
with engine.connect() as conn:
    conn.execute(
        update(positions)
        .where(positions.c.id == pos.id)
        .values(highest_close=new_hc, trailing_stop=new_ts)
    )
    conn.commit()
```

**_run_preflight return tuple extension** (current lines 262-304; extend return type):
```python
def _run_preflight(
    engine: Engine,
    con: Console,
    today: date,
) -> tuple[dict[str, str], pd.DatetimeIndex, list[str], int, date | None]:
    # Phase 11: return tuple gains last_scan_date as 5th element
    # Existing: (constituents, missed_days, catch_up_notes, freshness_days)
    # Phase 11: (constituents, missed_days, catch_up_notes, freshness_days, last_scan_date)
    ...
    last_scan_date: date | None = None
    if row is not None:
        last_scan_date = row.scan_date.date()
        ...
    return constituents, missed_days, catch_up_notes, freshness_days, last_scan_date
```

**_render_output catch-up block pattern** (current section 1/header at line 803; new block precedes it):
```python
def _render_output(
    capture: Console,
    today: date,
    regime_active: bool,
    spx_close: float,
    spx_sma_200: float,
    today_triggers: list[_TriggerRow],
    pending_triggers: list[_TriggerRow],
    candidates: list[Candidate],
    cash: float,
    catch_up_events: list[str],  # Phase 11: renamed from catch_up_notes; now full events
    avg_volumes: dict[str, int],
    missed_days: list[date],     # Phase 11: added for summary header line
    open_positions_count: int,   # Phase 11: added for "N open positions" line
) -> None:
    # Phase 11: catch-up summary block BEFORE section 1
    if catch_up_events:
        capture.print(Text(SEPARATOR))
        capture.print(Text("Catch-up summary"))
        capture.print(Text(SEPARATOR))
        capture.print()
        # ... per-position entries from catch_up_events
        # ... retroactive triggers table
        capture.print()

    # 1. Header (unchanged)
    capture.print(Text(SEPARATOR))
    ...
```

**System notes bear-market note pattern** (current lines 984-985; catch_up_notes still used for this):
```python
# D-21: Bear market — add note to system notes
catch_up_events.append("Regime: Bear market. No buy candidates generated.")
```

**log_event audit pattern** (current lines 234-248; copy for CATCH_UP_PERFORMED and SPLIT_APPLIED):
```python
log_event(
    engine,
    AuditEventType.CATCH_UP_PERFORMED,   # or SPLIT_APPLIED, POSITION_DELISTED_FROM_INDEX
    symbol=None,                          # or pos.symbol for per-position events
    payload={
        "missed_days": len(missed_days),
        "start_date": missed_days[0].isoformat(),
        "end_date": missed_days[-1].isoformat(),
    },
)
```

**console.print Text() wrapping** (pattern throughout `_render_output`, e.g. line 804):
```python
# MANDATORY: All strings to capture.print() MUST be wrapped in Text()
capture.print(Text(SEPARATOR))
capture.print(Text(f"Scan for {format_date(today)}"))
# Template strings from events.py are plain str — wrap in Text() at call site:
capture.print(Text(event_str))
```

---

### `src/bensdorp1/db/schema.py` (config, DDL) — MODIFIED

**Analog:** self (existing file, add one Column to `positions` table)

**Column addition pattern** (existing columns lines 43-59; append `delisted`):
```python
positions: Table = Table(
    "positions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", Text, nullable=False),
    Column("entry_date", DateTime(timezone=True), nullable=False),
    Column("entry_close", Float, nullable=False),
    Column("shares", Integer, nullable=False),
    Column("initial_stop", Float, nullable=False),
    Column("highest_close", Float, nullable=False),
    Column("trailing_stop", Float, nullable=False),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=True),
    Column("closed_at", DateTime(timezone=True), nullable=True),
    Column("exit_price", Float, nullable=True),
    Column("realized_pnl", Float, nullable=True),
    Column("closed_reason", Text, nullable=True),
    Column("closed_manual_reason", Text, nullable=True),
    # Phase 11: delisted flag — server_default=text("0") ensures Core inserts
    # without specifying this column do NOT violate NOT NULL (Pitfall 4):
    Column("delisted", Integer, nullable=False, server_default=text("0")),
)
```

**Required new import** — `text` from sqlalchemy (already imported for ALTER TABLE in engine.py; add to schema.py import block if not already present):
```python
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    MetaData, Table, Text,
    text,   # Phase 11: needed for server_default=text("0")
)
```

---

### `src/bensdorp1/db/engine.py` (config, migration runner) — MODIFIED

**Analog:** self (existing file, add one ALTER TABLE statement)

**run_migrations extension pattern** (current lines 71-89; copy exactly, add new stmt):
```python
def run_migrations(engine: Engine) -> None:
    """Create all tables and apply incremental schema migrations idempotently."""
    metadata.create_all(engine, checkfirst=True)
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE positions ADD COLUMN closed_reason TEXT",
            "ALTER TABLE positions ADD COLUMN closed_manual_reason TEXT",
            # Phase 11:
            "ALTER TABLE positions ADD COLUMN delisted INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except OperationalError:
                pass  # column already exists — idempotent
```

**No other changes** to engine.py. The `text` and `OperationalError` imports are already present (lines 4-5, 11).

---

### `tests/test_commands/test_catchup.py` (test, unit + integration) — NEW

**Analog:** `tests/test_commands/test_scan_engine.py`

**File header and imports pattern** (test_scan_engine.py lines 1-53):
```python
"""Unit tests for catch-up logic: _apply_splits, _detect_delisted_positions,
catch-up summary rendering, and event templates.

All DB tests use the db_engine fixture (fresh in-memory SQLite per test).
All yfinance calls are mocked via unittest.mock.patch.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from rich.console import Console
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from bensdorp1.commands._scan_engine import (
    _apply_splits,
    _detect_delisted_positions,
    _OpenPosition,
    _render_output,
)
from bensdorp1.commands.events import (
    render_initial_stop_violated,
    render_trailing_stop_violated,
    render_new_highest_close,
    render_composite,
    # ... all 13
)
from bensdorp1.db.schema import positions, audit_log
```

**db_engine fixture usage pattern** (test_scan_engine.py lines 119-132):
```python
def test_apply_splits_math(db_engine: Engine) -> None:
    """_apply_splits applies D-06 math: shares*ratio, price fields/ratio."""
    entry_dt = datetime(2026, 1, 2, tzinfo=UTC)
    with db_engine.connect() as conn:
        r = conn.execute(
            insert(positions).values(
                symbol="NVDA",
                entry_date=entry_dt,
                entry_close=432.50,
                shares=23,
                initial_stop=400.0,
                highest_close=432.50,
                trailing_stop=324.37,
                closed_at=None,
                # delisted defaults to 0 via server_default
            )
        )
        conn.commit()
        pos_id: int = int(r.inserted_primary_key[0])
    ...
```

**yfinance mock pattern** (from test_scan.py; adapt for Ticker.splits):
```python
# Mock yfinance Ticker.splits — returns pd.Series with UTC DatetimeIndex
with patch("bensdorp1.commands._scan_engine.yf.Ticker") as mock_ticker:
    mock_instance = MagicMock()
    split_date = datetime(2026, 5, 19, tzinfo=UTC)
    mock_instance.splits = pd.Series(
        [2.0],
        index=pd.DatetimeIndex([split_date]),
    )
    mock_ticker.return_value = mock_instance

    result = _apply_splits(db_engine, open_positions, last_scan_date, today, [])
```

**assert pattern for DB-modified values** (test_scan_engine.py lines 183-186):
```python
with db_engine.connect() as conn:
    row = conn.execute(
        select(positions).where(positions.c.id == pos_id)
    ).fetchone()
assert row is not None
assert row.shares == 46      # 23 * 2
assert row.entry_close == pytest.approx(216.25)   # 432.50 / 2
```

**Audit event assertion pattern** (test_scan_engine.py implicit; use audit_log query):
```python
with db_engine.connect() as conn:
    rows = conn.execute(
        select(audit_log).where(
            audit_log.c.event_type == "split_applied"
        )
    ).fetchall()
assert len(rows) == 1
import json
payload = json.loads(rows[0].payload)
assert payload["ratio"] == 2.0
assert payload["before"]["shares"] == 23
assert payload["after"]["shares"] == 46
```

**Pure function unit test pattern** (test_scan_engine.py lines 60-79 for _get_close_for_day):
```python
# events.py functions need no DB — test directly with typed params
def test_render_initial_stop_violated_format() -> None:
    """Template 1 includes symbol, date, close, stop in expected format."""
    result = render_initial_stop_violated(
        symbol="AAPL",
        trigger_date=date(2026, 5, 18),
        close=178.20,
        stop=179.50,
    )
    assert "AAPL" in result
    assert "2026-05-18" in result
    assert "$178.20" in result
    assert "$179.50" in result
    assert "still pending" in result
```

---

## Shared Patterns

### Audit Event Logging
**Source:** `src/bensdorp1/db/audit.py` — `log_event()` (lines 44-63)
**Apply to:** `_apply_splits()`, `_detect_delisted_positions()`, catch-up summary completion in `run_scan()`

```python
# Established call signature — use verbatim for all three new event types:
log_event(
    engine,
    AuditEventType.SPLIT_APPLIED,           # or POSITION_DELISTED_FROM_INDEX or CATCH_UP_PERFORMED
    symbol=pos.symbol,                        # None for CATCH_UP_PERFORMED
    payload={                                 # JSON-serializable dict
        "split_date": split_date.isoformat(),
        "ratio": ratio,
        "before": {"shares": pos.shares, ...},
        "after": {"shares": new_shares, ...},
    },
)
```

All three event types (`SPLIT_APPLIED`, `POSITION_DELISTED_FROM_INDEX`, `CATCH_UP_PERFORMED`) are already registered in `AuditEventType` StrEnum (audit.py lines 30-39).

### Parameterized DB UPDATE
**Source:** `src/bensdorp1/commands/_scan_engine.py` lines 521-527
**Apply to:** `_apply_splits()` (updating shares/prices), `_detect_delisted_positions()` (setting delisted=1)

```python
# Always use SQLAlchemy parameterized update — never string interpolation:
with engine.connect() as conn:
    conn.execute(
        update(positions)
        .where(positions.c.id == pos.id)
        .values(key=value, ...)
    )
    conn.commit()
```

### Console Output (Text wrapping)
**Source:** `src/bensdorp1/commands/_scan_engine.py` lines 804-807 (throughout `_render_output`)
**Apply to:** All new `capture.print()` calls in the catch-up summary block

```python
# MANDATORY: Rich markup safety — ALL strings to capture.print() need Text():
from rich.text import Text
capture.print(Text(SEPARATOR))
capture.print(Text("Catch-up summary"))
capture.print(Text(event_string_from_events_py))   # events.py returns plain str
```

### DB Test Data Insertion
**Source:** `tests/test_commands/test_scan_engine.py` lines 152-181
**Apply to:** All `test_catchup.py` tests that need open positions in the DB

```python
# positions rows must include entry_close, shares, and (after Phase 11) delisted.
# The delisted column has server_default=text("0") so omitting it is safe.
with db_engine.connect() as conn:
    r = conn.execute(
        insert(positions).values(
            symbol="AAPL",
            entry_date=datetime(2026, 1, 2, tzinfo=UTC),
            entry_close=100.0,
            shares=10,
            initial_stop=93.0,
            highest_close=100.0,
            trailing_stop=75.0,
            closed_at=None,
        )
    )
    conn.commit()
    pos_id: int = int(r.inserted_primary_key[0])
```

### run_scan() Call-site Threading
**Source:** `src/bensdorp1/commands/_scan_engine.py` lines 142-145 (preflight call) and 200-212 (_render_output call)
**Apply to:** All new parameters added to `_run_preflight()` and `_render_output()` must also be updated at their call sites in `run_scan()`

```python
# Preflight call site (line 142) — extend unpacking for new last_scan_date:
constituents, missed_days, catch_up_notes, freshness_days, last_scan_date = _run_preflight(
    engine, con, today
)

# _render_output call site (line 200) — extend for new parameters:
_render_output(
    capture,
    today,
    regime_active,
    spx_close,
    spx_sma_200,
    new_trigger_rows,
    pending_trigger_rows,
    candidates,
    available_cash,
    catch_up_events,      # renamed from catch_up_notes
    avg_volumes,
    [d.date() for d in missed_days],   # Phase 11: added
    len(open_positions),               # Phase 11: added
)
```

---

## No Analog Found

No files in this phase lack a codebase analog. All five files either extend themselves or use `ui/styles.py` as a close role-match.

---

## Metadata

**Analog search scope:** `src/bensdorp1/commands/`, `src/bensdorp1/db/`, `src/bensdorp1/ui/`, `tests/test_commands/`
**Files scanned:** 8 source files, 2 test files read in detail
**Pattern extraction date:** 2026-05-30
