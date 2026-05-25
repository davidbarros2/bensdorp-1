# Phase 9: Consultation Commands - Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 14 (7 command files + 7 test files)
**Analogs found:** 14 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/bensdorp1/commands/last.py` | command | request-response (read-only) | `src/bensdorp1/commands/scan.py` | role-match (raw_output read) |
| `src/bensdorp1/commands/history.py` | command | request-response (read-only) | `src/bensdorp1/commands/fix.py` | role-match (render_table) |
| `src/bensdorp1/commands/portfolio.py` | command | request-response (read-only) | `src/bensdorp1/commands/sell.py` | role-match (positions query + computed metrics) |
| `src/bensdorp1/commands/detail.py` | command | request-response (read-only) | `src/bensdorp1/commands/sell.py` + `src/bensdorp1/commands/fix.py` | role-match |
| `src/bensdorp1/commands/cash.py` | command | CRUD (read + conditional write) | `src/bensdorp1/commands/buy.py` | exact (write-backup-log pattern) |
| `src/bensdorp1/commands/config.py` | command | request-response (read-only) | `src/bensdorp1/commands/fix.py` | role-match (render_kv_block) |
| `src/bensdorp1/commands/audit.py` | command | request-response (read-only, filtered) | `src/bensdorp1/commands/fix.py` | role-match (render_table) |
| `tests/test_commands/test_last.py` | test | request-response | `tests/test_commands/test_buy.py` | exact |
| `tests/test_commands/test_history.py` | test | request-response | `tests/test_commands/test_buy.py` | exact |
| `tests/test_commands/test_portfolio.py` | test | request-response | `tests/test_commands/test_sell.py` | exact (seeded DB) |
| `tests/test_commands/test_detail.py` | test | request-response | `tests/test_commands/test_sell.py` | exact (seeded DB) |
| `tests/test_commands/test_cash.py` | test | CRUD | `tests/test_commands/test_buy.py` | exact (mock + confirm flow) |
| `tests/test_commands/test_config.py` | test | request-response | `tests/test_commands/test_buy.py` | exact |
| `tests/test_commands/test_audit.py` | test | request-response | `tests/test_commands/test_sell.py` | exact (seeded DB) |

---

## Pattern Assignments

### `src/bensdorp1/commands/last.py` (command, read-only)

**Analog:** `src/bensdorp1/commands/scan.py` (lines 1-63)

**Imports pattern** (scan.py lines 1-16):
```python
import typer
from rich.console import Console

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import scans
from bensdorp1.ui import print_info
```

**DB entry triad** (buy.py lines 44-48 — canonical source):
```python
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

**raw_output read + verbatim print** (scan.py lines 44-63):
```python
with engine.connect() as conn:
    row = conn.execute(
        select(scans.c.scan_date, scans.c.raw_output)
        .order_by(scans.c.scan_date.desc())
        .limit(1)
    ).fetchone()
console = Console()
if row is None:
    print_info(
        "No scans recorded yet."
        " Run `bensdorp1 scan` on a trading day after 16:30 ET."
    )
else:
    if row.raw_output is not None:
        console.print(row.raw_output, markup=False, highlight=False)
```

**Empty state guard pattern** (buy.py lines 75-81):
```python
if row is None:
    print_info("No scans recorded yet.", console=console)
    raise typer.Exit()
```

**Exit pattern** (scan.py line 63):
```python
raise typer.Exit()
```

---

### `src/bensdorp1/commands/history.py` (command, read-only)

**Analog:** `src/bensdorp1/commands/fix.py` (for render_table usage, lines 336-341); `src/bensdorp1/commands/scan.py` (for scans table query)

**Imports pattern** (copy from buy.py lines 1-29, adjust):
```python
import datetime
from datetime import UTC
from typing import Optional

import typer
from rich.console import Console

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import scan_candidates, scans
from bensdorp1.ui import format_date, print_error, print_info, render_table
```

**DB entry triad** (buy.py lines 44-48):
```python
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

**Option signature** (new — no existing analog for `--since`/`--limit`):
```python
@app.command(rich_help_panel="Daily operation")
def history(
    limit: int = typer.Option(20, "--limit", help="Maximum rows to show."),
    since: Optional[str] = typer.Option(None, "--since", help="Show scans on or after YYYY-MM-DD."),
) -> None:
```

**Date parsing guard** (buy.py lines 55-62 — same try/except structure):
```python
try:
    since_date = datetime.date.fromisoformat(since)
except ValueError:
    print_error(
        f"Invalid --since value {since!r}. Expected YYYY-MM-DD.",
        console=console,
    )
    raise typer.Exit(code=1) from None
since_dt = datetime.datetime(since_date.year, since_date.month, since_date.day, tzinfo=UTC)
```

**Parameterized SELECT with optional WHERE** (SQLAlchemy 2.0 `.where(*filters)` splatting):
```python
filters = []
if since is not None:
    filters.append(scans.c.scan_date >= since_dt)

with engine.connect() as conn:
    scan_rows = conn.execute(
        select(scans)
        .where(*filters)
        .order_by(scans.c.scan_date.desc())
        .limit(limit)
    ).fetchall()
```

**Per-scan top-3 candidate sub-query + render_table** (RESEARCH.md Pattern 4):
```python
    rows: list[list[str]] = []
    for scan in scan_rows:
        cand_rows = conn.execute(
            select(scan_candidates.c.symbol)
            .where(scan_candidates.c.scan_id == scan.id)
            .order_by(scan_candidates.c.rank.asc())
            .limit(3)
        ).fetchall()
        top3 = ", ".join(r.symbol for r in cand_rows) if cand_rows else "—"
        regime_label = "Bull" if scan.regime_active else "Bear"
        rows.append([
            format_date(scan.scan_date.date()),
            regime_label,
            str(scan.exit_trigger_count),
            str(scan.candidate_count),
            top3,
        ])

render_table(
    columns=[
        ("Date", "left"),
        ("Regime", "left"),
        ("Exits", "right"),
        ("Candidates", "right"),
        ("Top candidates", "left"),
    ],
    rows=rows,
    console=console,
)
```

**render_table signature** (fix.py lines 336-341):
```python
render_table(
    columns=[("Field", "left"), ("Before", "left"), ("After", "left")],
    rows=diff_rows,
    console=console,
)
```

---

### `src/bensdorp1/commands/portfolio.py` (command, read-only + computation)

**Analog:** `src/bensdorp1/commands/sell.py` (positions query pattern); `src/bensdorp1/commands/fix.py` (render_table)

**Imports pattern** (sell.py lines 1-32, adjusted):
```python
import datetime
from datetime import UTC

import typer
from rich.console import Console

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.data import get_trading_days
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import positions, price_daily
from bensdorp1.ui import format_date, format_pct, format_pnl, format_price, print_info, render_table
```

**Open positions query** (sell.py lines 90-100 — `closed_at == None` idiom):
```python
with engine.connect() as conn:
    open_positions = conn.execute(
        select(positions).where(positions.c.closed_at == None)  # noqa: E711
    ).fetchall()
```

**Latest price sub-query per symbol** (RESEARCH.md Pattern 6):
```python
    price_row = conn.execute(
        select(price_daily.c.close)
        .where(
            (price_daily.c.symbol == pos.symbol)
            & (price_daily.c.trade_date <= datetime.datetime(
                today_utc.year, today_utc.month, today_utc.day, tzinfo=UTC
            ))
        )
        .order_by(price_daily.c.trade_date.desc())
        .limit(1)
    ).fetchone()
```

**Computed metrics** (RESEARCH.md Pattern 6, D-07/D-08):
```python
last_close = price_row.close
effective_stop = max(pos.initial_stop, pos.trailing_stop)
dist_pct = (last_close - effective_stop) / last_close * 100.0
unrealized_pnl = (last_close - pos.entry_close) * pos.shares
days = len(get_trading_days(pos.entry_date.date(), today_utc))
```

**N/A fallback for missing price** (D-07):
```python
if price_row is None:
    history_rows.append([
        pos.symbol,
        format_date(pos.entry_date.date()),
        str(len(get_trading_days(pos.entry_date.date(), today_utc))),
        format_price(pos.entry_close),
        str(pos.shares),
        "N/A", "N/A", "N/A", "N/A", "N/A",
    ])
    continue
```

**render_table with 10 columns** (D-06):
```python
render_table(
    columns=[
        ("Symbol", "left"),
        ("Entry date", "left"),
        ("Days", "right"),
        ("Entry $", "right"),
        ("Shares", "right"),
        ("Last $", "right"),
        ("High $", "right"),
        ("Stop $", "right"),
        ("Dist %", "right"),
        ("P&L", "right"),
    ],
    rows=history_rows,
    console=console,
)
```

---

### `src/bensdorp1/commands/detail.py` (command, read-only + computation)

**Analog:** `src/bensdorp1/commands/sell.py` (position validation pattern); `src/bensdorp1/commands/fix.py` (render_kv_block + render_table combined)

**Imports pattern**:
```python
import datetime
from datetime import UTC, date, timedelta

import typer
from rich.console import Console
from rich.text import Text

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.data import get_trading_days
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import positions, price_daily, scans
from bensdorp1.ui import (
    format_date,
    format_price,
    print_error,
    print_info,
    render_kv_block,
    render_table,
)
```

**SYMBOL argument + open position validation** (sell.py lines 51-108 — same structure):
```python
@app.command(rich_help_panel="Portfolio")
def detail(
    symbol: str = typer.Argument(..., help="Ticker symbol of an open position."),
) -> None:
    ...
    with engine.connect() as conn:
        pos_row = conn.execute(
            select(positions).where(
                (positions.c.symbol == symbol.upper()) & (positions.c.closed_at == None)  # noqa: E711
            )
        ).fetchone()

    if pos_row is None:
        print_error(
            f"No open position for {symbol.upper()}.",
            actions=["To see history of a closed position: bensdorp1 audit --symbol " + symbol.upper()],
            console=console,
        )
        raise typer.Exit(code=1)
```

**Position summary kv block** (fix.py lines 122-143 — render_kv_block usage):
```python
render_kv_block(
    {
        "Symbol": pos_row.symbol,
        "Entry date": format_date(pos_row.entry_date.date()),
        "Entry price": format_price(pos_row.entry_close),
        "Shares": str(pos_row.shares),
        "Initial stop": format_price(pos_row.initial_stop),
    },
    console,
)
```

**Section separator** (fix.py lines 117-119 — Text separator pattern):
```python
console.print(Text("Stop history"))
console.print(Text("-" * 12))
```

**Per-day stop history walk** (RESEARCH.md Pattern 3 + D-01):
```python
with engine.connect() as conn:
    price_rows = conn.execute(
        select(price_daily.c.trade_date, price_daily.c.close)
        .where(
            (price_daily.c.symbol == symbol.upper())
            & (price_daily.c.trade_date > pos_row.entry_date)
        )
        .order_by(price_daily.c.trade_date.asc())
    ).fetchall()

close_map: dict[date, float] = {
    r.trade_date.date(): r.close for r in price_rows
}

if not close_map:
    print_info("No price history available yet for this position.", console=console)
    raise typer.Exit()

last_price_date = max(close_map.keys())
trading_days = get_trading_days(
    pos_row.entry_date.date() + timedelta(days=1), last_price_date
)

history_rows: list[list[str]] = []
running_max = pos_row.entry_close

for day in trading_days:
    day_date = day.date()
    day_close = close_map.get(day_date)
    if day_close is None:
        continue  # gap in price data — skip (D-01)
    running_max = max(running_max, day_close)
    trailing_stop = running_max * 0.75
    effective_stop = max(pos_row.initial_stop, trailing_stop)
    history_rows.append([
        format_date(day_date),
        format_price(day_close),
        format_price(running_max),
        format_price(trailing_stop),
        format_price(effective_stop),
    ])
```

**Stop history render_table** (fix.py lines 336-341 — render_table pattern):
```python
render_table(
    columns=[
        ("Date", "left"),
        ("Close", "right"),
        ("Highest close", "right"),
        ("Trailing stop", "right"),
        ("Effective stop", "right"),
    ],
    rows=history_rows,
    console=console,
)
```

---

### `src/bensdorp1/commands/cash.py` (command, CRUD)

**Analog:** `src/bensdorp1/commands/buy.py` — exact (write-backup-log sequence)

**Imports pattern** (buy.py lines 1-29, adjusted):
```python
import datetime
from datetime import UTC
from typing import Any, Optional

import typer
from rich.console import Console

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import config as config_table
from bensdorp1.ui import confirm_prompt, format_price, print_error, print_info, print_success, render_kv_block
```

**Argument + option signature** (D-04):
```python
@app.command(rich_help_panel="System")
def cash(
    amount: Optional[float] = typer.Argument(None, help="New cash balance (non-negative)."),
    note: Optional[str] = typer.Option(None, "--note", help="Reason for update."),
) -> None:
```

**Config table read** (SQLAlchemy SELECT — no prior analog; see schema.py lines 22-28):
```python
with engine.connect() as conn:
    row = conn.execute(
        select(config_table.c.value, config_table.c.updated_at)
        .where(config_table.c.key == "cash")
    ).fetchone()
```

**Show-mode branch** (D-04; render_kv_block from fix.py lines 143-145):
```python
if amount is None:
    if row is None:
        print_info("No cash configured. Run `bensdorp1 init`.", console=console)
        raise typer.Exit()
    render_kv_block(
        {
            "Available cash": format_price(float(row.value)),
            "Last updated":   format_timezone_pair(row.updated_at),
        },
        console,
    )
    raise typer.Exit()
```

**Non-negative validation** (buy.py lines 98-104 — same pattern):
```python
if amount < 0.0:
    print_error("Cash amount must be non-negative.", console=console)
    raise typer.Exit(code=1)
```

**Confirmation prompt** (buy.py lines 162-185 — exact pattern):
```python
try:
    confirmed = confirm_prompt("Confirm cash update?", console=console)
except KeyboardInterrupt:
    raise typer.Exit() from None
if not confirmed:
    raise typer.Exit()
```

**Write + backup + log** (buy.py lines 187-220 — exact sequence):
```python
with engine.connect() as conn:
    conn.execute(
        update(config_table)
        .where(config_table.c.key == "cash")
        .values(value=str(amount), updated_at=datetime.datetime.now(UTC))
    )
    conn.commit()

create_backup(engine, DATA_DIR / "backups")
log_event(
    engine,
    AuditEventType.CASH_UPDATED,
    payload={"old": old_value, "new": amount, "note": note},
)
print_success("Cash updated.", console=console)
```

---

### `src/bensdorp1/commands/config.py` (command, read-only)

**Analog:** `src/bensdorp1/commands/fix.py` (render_kv_block usage, lines 143-145)

**Imports pattern**:
```python
from importlib.metadata import version as pkg_version

import typer
from rich.console import Console

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR, USER_TZ
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import config as config_table
from bensdorp1.ui import format_price, print_info, render_kv_block
```

**Config read + render_kv_block** (fix.py lines 143-145 — render_kv_block pattern):
```python
with engine.connect() as conn:
    cash_row = conn.execute(
        select(config_table.c.value)
        .where(config_table.c.key == "cash")
    ).fetchone()

cash_str = format_price(float(cash_row.value)) if cash_row is not None else "Not configured"
render_kv_block(
    {
        "Cash":           cash_str,
        "Data directory": str(DATA_DIR),
        "Timezone":       f"{USER_TZ.key.split('/')[-1]} (BENSDORP1_USER_TZ)",
        "Version":        pkg_version("bensdorp1"),
    },
    console,
)
```

---

### `src/bensdorp1/commands/audit.py` (command, read-only, filtered)

**Analog:** `src/bensdorp1/commands/fix.py` (render_table, lines 336-341); `src/bensdorp1/commands/buy.py` (DB entry triad)

**Imports pattern**:
```python
import json
import datetime
from datetime import UTC
from typing import Optional

import typer
from rich.console import Console

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.audit import AuditEventType
from bensdorp1.db.schema import audit_log
from bensdorp1.ui import format_date, format_timezone_pair, print_error, print_info, render_table
```

**Command signature with Optional[AuditEventType]** (D-03):
```python
@app.command(rich_help_panel="System")
def audit(
    symbol: Optional[str] = typer.Option(None, "--symbol", help="Filter by ticker symbol."),
    since: Optional[str] = typer.Option(None, "--since", help="On or after YYYY-MM-DD."),
    until: Optional[str] = typer.Option(None, "--until", help="On or before YYYY-MM-DD."),
    type_: Optional[AuditEventType] = typer.Option(None, "--type", help="Filter by event type."),
    limit: int = typer.Option(50, "--limit", help="Maximum rows to show."),
) -> None:
```

**AND-filter WHERE clause construction** (SQLAlchemy 2.0 `.where(*filters)` — RESEARCH.md Pattern 5):
```python
filters = []
if symbol:
    filters.append(audit_log.c.symbol == symbol.upper())
if since_dt is not None:
    filters.append(audit_log.c.occurred_at >= since_dt)
if until_dt is not None:
    filters.append(audit_log.c.occurred_at <= until_dt)
if type_ is not None:
    filters.append(audit_log.c.event_type == str(type_))

with engine.connect() as conn:
    rows = conn.execute(
        select(audit_log)
        .where(*filters)
        .order_by(audit_log.c.occurred_at.desc())
        .limit(limit)
    ).fetchall()
```

**payload JSON parsing for Details column** (RESEARCH.md Pitfall 7):
```python
def _format_details(payload_str: Optional[str]) -> str:
    if payload_str is None:
        return "—"
    try:
        data = json.loads(payload_str)
    except (json.JSONDecodeError, TypeError):
        return payload_str[:60]
    # Extract key fields per event type
    if "old" in data and "new" in data:
        return f"{format_price(float(data['old']))} → {format_price(float(data['new']))}"
    if "price" in data and "shares" in data:
        return f"{data['shares']} shares @ {format_price(float(data['price']))}"
    return str(data)[:60]
```

**render_table for audit results**:
```python
render_table(
    columns=[
        ("Date", "left"),
        ("Type", "left"),
        ("Symbol", "left"),
        ("Details", "left"),
    ],
    rows=[
        [
            format_timezone_pair(row.occurred_at),
            str(row.event_type),
            row.symbol or "—",
            _format_details(row.payload),
        ]
        for row in rows
    ],
    console=console,
)
```

---

### Test files: `tests/test_commands/test_last.py` through `test_audit.py`

**Primary analog:** `tests/test_commands/test_buy.py` (all patterns) and `tests/test_commands/test_sell.py` (seeded DB patterns)

**Module-level runner** (test_buy.py line 21):
```python
runner = CliRunner()
```

**Mock-engine test structure** (test_buy.py lines 24-41 — for simple cases without seeded data):
```python
def test_empty_state(tmp_path: Path) -> None:
    """<command> shows info message when no rows exist."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchone.return_value = None

    with (
        patch("bensdorp1.commands.<cmd>.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.<cmd>.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.<cmd>.run_migrations"),
    ):
        result = runner.invoke(app, ["<cmd>"])

    assert result.exit_code == 0
    assert "No " in result.output
```

**Real SQLite seeded-DB test structure** (test_buy.py lines 131-217 — for commands requiring real rows):
```python
def test_happy_path(db_engine: Engine, tmp_path: Path) -> None:
    """Happy path: seeds DB rows, invokes command, asserts output and DB state."""
    with db_engine.connect() as conn:
        conn.execute(insert(positions).values(
            symbol="AAPL",
            entry_date=datetime(2026, 3, 15, tzinfo=UTC),
            entry_close=182.50,
            shares=50,
            initial_stop=169.73,
            highest_close=185.00,
            trailing_stop=138.75,
            scan_id=None,
            closed_at=None,
            exit_price=None,
            realized_pnl=None,
        ))
        conn.commit()

    with (
        patch("bensdorp1.commands.<cmd>.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.<cmd>.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.<cmd>.run_migrations"),
    ):
        result = runner.invoke(app, ["<cmd>"])

    assert result.exit_code == 0
    assert "AAPL" in result.output
```

**Seeding price_daily rows** (needed for test_portfolio.py and test_detail.py):
```python
# price_daily schema: id, symbol, trade_date, close, volume
conn.execute(insert(price_daily).values(
    symbol="AAPL",
    trade_date=datetime(2026, 3, 16, tzinfo=UTC),
    close=185.00,
    volume=1000000,
))
```

**Seeding audit_log rows** (needed for test_audit.py):
```python
# audit_log schema: id, event_type, occurred_at, symbol, payload
conn.execute(insert(audit_log).values(
    event_type="buy_confirmed",
    occurred_at=datetime(2026, 5, 22, 14, 30, tzinfo=UTC),
    symbol="NVDA",
    payload='{"price": 432.5, "shares": 23}',
))
```

**Cash-update test with confirmation input** (test_buy.py line 186 — CliRunner `input=` pattern):
```python
result = runner.invoke(app, ["cash", "45000.0"], input="y\n")
assert result.exit_code == 0
assert "Cash updated" in result.output
```

**Abort test** (test_buy.py lines 249-253):
```python
result = runner.invoke(app, ["cash", "45000.0"], input="n\n")
assert result.exit_code == 0
mock_create_backup.assert_not_called()
mock_log_event.assert_not_called()
```

**Import block for all test files** (test_buy.py lines 1-21):
```python
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app
from bensdorp1.db.schema import (
    audit_log,
    positions,
    price_daily,
    scans,
    scan_candidates,
    config,  # alias as config_table at import if needed
)

runner = CliRunner()
```

---

## Shared Patterns

### SP-1: DB Entry Triad
**Source:** `src/bensdorp1/commands/buy.py` lines 44-48
**Apply to:** All 7 command files
```python
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

### SP-2: Empty State Guard
**Source:** `src/bensdorp1/commands/scan.py` lines 51-56; `src/bensdorp1/commands/fix.py` lines 94-99
**Apply to:** `last`, `history`, `portfolio`, `audit` commands
```python
if not rows:
    print_info("No <entity>.", console=console)
    raise typer.Exit()
```

### SP-3: `raise typer.Exit()` — Never `sys.exit()`
**Source:** `src/bensdorp1/commands/buy.py` lines 81, 104, 159, 185; `src/bensdorp1/commands/sell.py` lines 108, 121
**Apply to:** All 7 command files
```python
raise typer.Exit()        # clean exit
raise typer.Exit(code=1)  # error exit
```

### SP-4: `closed_at == None` SQLAlchemy Idiom
**Source:** `src/bensdorp1/commands/buy.py` line 86; `src/bensdorp1/db/schema.py` line 63
**Apply to:** `portfolio`, `detail` commands
```python
.where(positions.c.closed_at == None)  # noqa: E711  — generates IS NULL
```

### SP-5: Confirmation Flow — KeyboardInterrupt Guard
**Source:** `src/bensdorp1/commands/buy.py` lines 154-185; `src/bensdorp1/commands/sell.py` lines 184-214
**Apply to:** `cash` command (update path only)
```python
try:
    confirmed = confirm_prompt("...", console=console)
except KeyboardInterrupt:
    raise typer.Exit() from None
if not confirmed:
    raise typer.Exit()
```
**Critical:** `confirm_prompt` already prints "Operation aborted." Do NOT print it again after catching `KeyboardInterrupt` — just `raise typer.Exit() from None`.

### SP-6: Write-Backup-Log Sequence
**Source:** `src/bensdorp1/commands/buy.py` lines 187-220; `src/bensdorp1/commands/sell.py` lines 217-244
**Apply to:** `cash` command (update path)
```python
with engine.connect() as conn:
    conn.execute(update(...).where(...).values(...))
    conn.commit()

create_backup(engine, DATA_DIR / "backups")
log_event(engine, AuditEventType.<TYPE>, symbol=..., payload={...})
print_success("...", console=console)
```

### SP-7: SQLAlchemy AND-Filter Construction
**Source:** Established pattern in this project (RESEARCH.md Pattern 5)
**Apply to:** `history` (`--since`), `audit` (all 5 flags)
```python
filters: list[Any] = []
if some_filter:
    filters.append(table.c.column == value)
# ...
.where(*filters)  # SQLAlchemy 2.0 accepts multiple positional args as AND
```

### SP-8: `config` Table Import Alias
**Source:** RESEARCH.md Pitfall 1; `src/bensdorp1/db/schema.py` line 22
**Apply to:** `cash`, `config` commands
```python
from bensdorp1.db.schema import config as config_table
# Use config_table.c.key, config_table.c.value throughout
# Avoids shadowing bensdorp1.config module
```

### SP-9: Text() Wrapping for console.print() Literals
**Source:** `src/bensdorp1/commands/buy.py` line 163; `src/bensdorp1/commands/fix.py` lines 117-119
**Apply to:** All 7 command files — any literal string passed to `console.print()`
```python
console.print(Text("Stop history"))
console.print(Text("-" * 12))
# NOT: console.print("Stop history")  — markup injection risk
```

### SP-10: CliRunner Patch Pattern for Tests
**Source:** `tests/test_commands/test_buy.py` lines 32-41, 181-186
**Apply to:** All 7 test files
```python
with (
    patch("bensdorp1.commands.<cmd>.get_engine", return_value=<engine>),
    patch("bensdorp1.commands.<cmd>.DATA_DIR", tmp_path),
    patch("bensdorp1.commands.<cmd>.run_migrations"),
    # add create_backup / log_event patches for cash update test
):
    result = runner.invoke(app, ["<cmd>", ...])
assert result.exit_code == 0
```

### SP-11: format_timezone_pair for Timestamps
**Source:** `src/bensdorp1/ui/styles.py` lines 86-95
**Apply to:** `cash` (show-mode `updated_at`), `audit` (`occurred_at` column)
```python
from bensdorp1.ui import format_timezone_pair
display = format_timezone_pair(row.occurred_at)
# Output: "14:30 ET (19:30 Lisbon)"
```

### SP-12: format_pct for Percentage Columns
**Source:** `src/bensdorp1/ui/styles.py` lines 44-47
**Apply to:** `portfolio` `Dist %` column
```python
format_pct(dist_pct)  # -> "+12.3%" or "-5.1%"
# NOT format_pnl() — that is for dollar amounts only
```

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `src/bensdorp1/commands/`, `src/bensdorp1/ui/`, `src/bensdorp1/db/`, `src/bensdorp1/data/`, `tests/test_commands/`, `tests/conftest.py`
**Files scanned:** 14 source + test files read in full
**Pattern extraction date:** 2026-05-25
