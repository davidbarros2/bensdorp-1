# Phase 8: Confirmation Commands - Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 8 (3 new commands, 3 new tests, 2 modifications)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/bensdorp1/commands/buy.py` | command (controller) | request-response + CRUD | `src/bensdorp1/commands/init.py` | exact |
| `src/bensdorp1/commands/sell.py` | command (controller) | request-response + CRUD | `src/bensdorp1/commands/init.py` | exact |
| `src/bensdorp1/commands/fix.py` | command (controller) | request-response + CRUD | `src/bensdorp1/commands/init.py` | exact |
| `src/bensdorp1/db/engine.py` | config / migration | batch | `src/bensdorp1/db/engine.py` (self) | self-modification |
| `src/bensdorp1/db/schema.py` | model | — | `src/bensdorp1/db/schema.py` (self) | self-modification |
| `tests/test_commands/test_buy.py` | test | request-response | `tests/test_commands/test_init.py` | exact |
| `tests/test_commands/test_sell.py` | test | request-response | `tests/test_commands/test_init.py` | exact |
| `tests/test_commands/test_fix.py` | test | request-response | `tests/test_commands/test_init.py` | exact |

---

## Pattern Assignments

### `src/bensdorp1/commands/buy.py` (command, request-response + CRUD)

**Analog:** `src/bensdorp1/commands/init.py`

**Imports pattern** (analog lines 1-32, adapted for buy):
```python
"""Record confirmed buy transaction."""

import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import insert, select

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import constituents_cache, positions, scan_candidates, scans
from bensdorp1.ui import (
    confirm_prompt,
    format_price,
    print_error,
    print_success,
    print_warning,
    render_kv_block,
)
```

**Module-level constant** (analog line 38):
```python
SEPARATOR: str = "=" * 64  # matches spec §7.3 — 64 '=' characters
```

**Command decorator and signature** (analog lines 93-94, adapted):
```python
@app.command(rich_help_panel="Confirmations")
def buy(
    symbol: str = typer.Argument(..., help="Ticker symbol (e.g. NVDA)."),
    price: float = typer.Argument(..., help="Buy price per share."),
    shares: int = typer.Argument(..., help="Number of shares."),
    date: str | None = typer.Option(None, "--date", help="Buy date (YYYY-MM-DD). Defaults to today ET."),
) -> None:
    """Record a confirmed buy transaction."""
```

**DB engine + migration entry pattern** (analog lines 97-110, from scan.py lines 42-44):
```python
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()
```

**Validation + early exit pattern** (scan.py lines 29-36, adapted for constituent check):
```python
    with engine.connect() as conn:
        row = conn.execute(
            select(constituents_cache.c.symbol).where(
                constituents_cache.c.symbol == symbol.upper()
            )
        ).fetchone()
    if row is None:
        print_error(
            f"{symbol.upper()} is not a valid S&P 500 constituent.",
            actions=["Run `bensdorp1 scan` to refresh the constituents list."],
            console=console,
        )
        raise typer.Exit(code=1)
```

**KeyboardInterrupt wrapping + confirmation flow** (analog lines 130-137):
```python
    try:
        console.print(Text(SEPARATOR))
        console.print(Text("Confirm buy"))
        console.print(Text(SEPARATOR))
        console.print()
        render_kv_block({...}, console)
        console.print()
        confirmed = confirm_prompt("Confirm buy?", console=console)
    except KeyboardInterrupt:
        console.print()
        console.print(Text("Operation aborted. No changes were made."))
        raise typer.Exit() from None
    if not confirmed:
        raise typer.Exit()
```

**DB write + backup + audit log sequence** (analog lines 205-214):
```python
    with engine.connect() as conn:
        conn.execute(
            insert(positions).values(
                symbol=symbol.upper(),
                entry_date=entry_dt,
                entry_close=price,
                shares=shares,
                initial_stop=price * 0.93,
                highest_close=price,
                trailing_stop=price * 0.75,
                scan_id=signal_scan_id,
                closed_at=None,
                exit_price=None,
                realized_pnl=None,
            )
        )
        conn.commit()

    create_backup(engine, DATA_DIR / "backups")
    log_event(
        engine,
        AuditEventType.BUY_CONFIRMED,
        symbol=symbol.upper(),
        payload={
            "price": price,
            "shares": shares,
            "date": str(buy_date),
            "scan_id": signal_scan_id,
            "on_signal": on_signal,
        },
    )
    print_success("Buy recorded.", console=console)
```

**Off-signal warning pattern** (from RESEARCH.md Pattern 3 + ui/messages.py `print_warning` signature):
```python
    print_warning(
        f"{symbol.upper()} was not in the top 10 buy candidates of the latest scan.",
        body=["This buy will be recorded as off-signal in the audit log."],
        console=console,
    )
    console.print()
    # Two-prompt pattern: off-signal confirm first, main confirm second
    try:
        off_signal_ok = confirm_prompt("Continue?", console=console)
    except KeyboardInterrupt:
        console.print()
        console.print(Text("Operation aborted. No changes were made."))
        raise typer.Exit() from None
    if not off_signal_ok:
        raise typer.Exit()
```

---

### `src/bensdorp1/commands/sell.py` (command, request-response + CRUD)

**Analog:** `src/bensdorp1/commands/init.py` + `src/bensdorp1/commands/scan.py`

**Imports pattern** (extends buy.py imports):
```python
"""Record confirmed sell transaction."""

import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select, update

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import positions, scan_exit_triggers
from bensdorp1.data import get_trading_days
from bensdorp1.ui import (
    confirm_prompt,
    format_date,
    format_days,
    format_pct,
    format_pnl,
    format_price,
    print_error,
    print_success,
    render_kv_block,
)
```

**Command signature**:
```python
@app.command(rich_help_panel="Confirmations")
def sell(
    symbol: str = typer.Argument(..., help="Ticker symbol (e.g. AAPL)."),
    price: float = typer.Argument(..., help="Sell price per share."),
    date: str | None = typer.Option(None, "--date", help="Sell date (YYYY-MM-DD). Defaults to today ET."),
    manual: str | None = typer.Option(None, "--manual", help="Manual sell reason (skips exit trigger lookup)."),
) -> None:
    """Record a confirmed sell transaction."""
```

**Exit trigger lookup + reason mapping** (RESEARCH.md Code Examples, verified against schema.py lines 102-112):
```python
    _REASON_MAP: dict[str, str] = {
        "Trailing stop": "stop_trailing",
        "Initial stop": "stop_initial",
    }

    if manual is None:
        with engine.connect() as conn:
            trigger_row = conn.execute(
                select(scan_exit_triggers.c.reason)
                .where(scan_exit_triggers.c.position_id == position_id)
                .order_by(scan_exit_triggers.c.id.asc())  # earliest trigger — D-12
                .limit(1)
            ).fetchone()
        if trigger_row is None:
            print_error(
                f"No exit trigger on record for {symbol.upper()}.",
                body=["To record a manual sell, use: bensdorp1 sell SYMBOL PRICE --manual REASON"],
                console=console,
            )
            raise typer.Exit(code=1)
        closed_reason: str = _REASON_MAP.get(trigger_row.reason, "stop_trailing")
        closed_manual_reason: str | None = None
        display_reason: str = trigger_row.reason  # human label for preview
    else:
        closed_reason = "manual"
        closed_manual_reason = manual
        display_reason = "Manual"
```

**P&L calculation + combined display** (RESEARCH.md Code Examples):
```python
    realized_pnl: float = (price - entry_close) * shares
    realized_pnl_pct: float = (price / entry_close - 1) * 100
    pnl_display: str = f"{format_pnl(realized_pnl)} ({format_pct(realized_pnl_pct)})"
    days_held: int = len(get_trading_days(entry_date.date(), sell_date))
```

**DB UPDATE pattern** (analog lines 83-85 adapted — `conn.commit()` required in SQLAlchemy 2.0):
```python
    with engine.connect() as conn:
        conn.execute(
            update(positions)
            .where(positions.c.id == position_id)
            .values(
                closed_at=sell_dt,
                exit_price=price,
                realized_pnl=realized_pnl,
                closed_reason=closed_reason,
                closed_manual_reason=closed_manual_reason,
            )
        )
        conn.commit()
    create_backup(engine, DATA_DIR / "backups")
    log_event(engine, AuditEventType.SELL_CONFIRMED, symbol=symbol.upper(), payload={...})
```

---

### `src/bensdorp1/commands/fix.py` (command, request-response + CRUD)

**Analog:** `src/bensdorp1/commands/init.py`

**Imports pattern**:
```python
"""Interactively correct the last transaction for a symbol."""

import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select, update

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import (
    AuditEventType,
    create_backup,
    get_engine,
    log_event,
    run_migrations,
)
from bensdorp1.db.schema import positions
from bensdorp1.ui import (
    confirm_prompt,
    format_date,
    format_price,
    print_error,
    print_info,
    print_success,
    render_kv_block,
    render_table,
)
```

**Command signature**:
```python
@app.command(rich_help_panel="Confirmations")
def fix(
    symbol: str = typer.Argument(..., help="Ticker symbol to correct."),
    date: str | None = typer.Option(None, "--date", help="(Reserved; unused in Phase 8.)"),
) -> None:
    """Interactively correct the last transaction for a symbol."""
```

**No-changes early exit pattern** (unique to fix — uses `print_info`):
```python
    if not any_changes:
        print_info("No changes detected. Nothing to update.", console=console)
        raise typer.Exit()
```

**Before/after diff table** (RESEARCH.md Code Examples, `render_table` from ui/__init__.py line 48):
```python
    diff_rows: list[list[str]] = []
    if new_price != current_price:
        diff_rows.append(["Price", format_price(current_price), format_price(new_price)])
    if new_shares != current_shares:
        diff_rows.append(["Shares", str(current_shares), str(new_shares)])
    if new_date != current_date:
        diff_rows.append(["Date", format_date(current_date), format_date(new_date)])

    render_table(
        columns=[("Field", "left"), ("Before", "left"), ("After", "left")],
        rows=diff_rows,
        console=console,
    )
```

**Field-by-field input pattern** (RESEARCH.md Code Examples — raw `input()` per Assumption A1, wrapped in outer try/except KeyboardInterrupt):
```python
    try:
        raw_date = input(f"Date    [{format_date(current_date)}]:  ").strip()
        new_date = datetime.date.fromisoformat(raw_date) if raw_date else current_date

        raw_price = input(f"Price   [{format_price(current_price)}]:  ").strip()
        clean_price = raw_price.lstrip("$").replace(",", "")
        new_price = float(clean_price) if clean_price else current_price

        raw_shares = input(f"Shares  [{current_shares}]:  ").strip()
        new_shares = int(raw_shares) if raw_shares else current_shares
    except KeyboardInterrupt:
        console.print()
        console.print(Text("Operation aborted. No changes were made."))
        raise typer.Exit() from None
```

**Audit payload before/after** (unique to fix — full before/after dict per D-24):
```python
    log_event(
        engine,
        AuditEventType.TRANSACTION_CORRECTED,
        symbol=symbol.upper(),
        payload={
            "before": {
                "entry_close": current_price,
                "shares": current_shares,
                "entry_date": str(current_date),
                "initial_stop": current_initial_stop,
            },
            "after": {
                "entry_close": new_price,
                "shares": new_shares,
                "entry_date": str(new_date),
                "initial_stop": new_initial_stop,
            },
        },
    )
```

---

### `src/bensdorp1/db/engine.py` (migration — ADD ALTER TABLE)

**Analog:** `src/bensdorp1/db/engine.py` (self-modification, lines 69-74)

**Current `run_migrations`** (lines 69-74):
```python
def run_migrations(engine: Engine) -> None:
    """Create all tables idempotently. Called only from bensdorp1 init (Phase 6).

    Uses checkfirst=True so calling this multiple times never raises.
    """
    metadata.create_all(engine, checkfirst=True)
```

**Target pattern after Phase 8 addition** — add these imports at top of file and extend the function (CONTEXT.md D-01, RESEARCH.md Pattern 5):
```python
# New imports needed at top of engine.py:
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

# Updated run_migrations:
def run_migrations(engine: Engine) -> None:
    """Create all tables and apply incremental migrations idempotently.

    Called by all state-changing commands on entry. Uses checkfirst=True for
    create_all and try/except OperationalError for ALTER TABLE (SQLite raises
    'duplicate column name' if column already exists).
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
```

---

### `src/bensdorp1/db/schema.py` (model — awareness only, no DDL change)

**Analog:** `src/bensdorp1/db/schema.py` (self, lines 42-57)

**Current `positions` table** (lines 42-57) — no `closed_reason` or `closed_manual_reason` columns:
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
)
```

**NOTE:** The `closed_reason` and `closed_manual_reason` columns are added via `ALTER TABLE` in `run_migrations` (not in schema.py DDL). SQLAlchemy's `Table` object does NOT need to declare these columns for the `INSERT`/`UPDATE` statements used by buy/sell/fix — SQLite accepts extra columns in the physical table that aren't in the `Table` object. The commands use raw `.values(closed_reason=..., closed_manual_reason=...)` kwargs which bypass the `Table` column list. No change to `schema.py` is needed unless the planner wants to add `Column("closed_reason", Text, nullable=True)` declarations for IDE autocompletion; if added, they must be wrapped in `CheckConstraint` or will conflict on re-`create_all` if the DB already has the columns.

**Decision for planner:** Leave `schema.py` unchanged (D-01 puts the columns only in `run_migrations`). The commands reference `positions.c.closed_reason` only in `.values(...)` kwargs — SQLAlchemy does not validate kwargs against `Table.columns`.

---

### `tests/test_commands/test_buy.py` (test)

**Analog:** `tests/test_commands/test_init.py`

**File header + runner** (analog lines 1-11):
```python
"""Tests for commands/buy.py — CMD-06 scenarios."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app

runner = CliRunner()
```

**Mocked-engine test pattern** (analog lines 28-53):
```python
def test_happy_path_on_signal(tmp_path: Path) -> None:
    """Happy path: on-signal buy creates position and exits 0."""
    mock_engine = MagicMock()

    with (
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup"),
        patch("bensdorp1.commands.buy.log_event"),
    ):
        result = runner.invoke(app, ["buy", "NVDA", "432.50", "23"], input="y\n")

    assert result.exit_code == 0
    assert "Buy recorded" in result.output
```

**Real DB test pattern** (analog lines 79-92 — uses `db_engine` fixture from conftest.py):
```python
def test_duplicate_open_position_rejected(db_engine: Engine) -> None:
    """A second open position for the same symbol is rejected with exit code 1."""
    from bensdorp1.db import _reset_engine_for_testing  # inject real engine
    # Pre-populate constituents_cache and an existing open position, then invoke
    # runner.invoke and assert exit_code == 1 and error message in output.
```

**Ctrl+C test pattern** (analog lines 95-109):
```python
def test_ctrl_c_aborts(tmp_path: Path) -> None:
    """Ctrl+C during confirmation prints abort message and exits 0."""
    with (
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.confirm_prompt", side_effect=KeyboardInterrupt),
        ...
    ):
        result = runner.invoke(app, ["buy", "NVDA", "432.50", "23"], input="")

    assert result.exit_code == 0
    assert "Operation aborted. No changes were made." in result.output
```

---

### `tests/test_commands/test_sell.py` (test)

**Analog:** `tests/test_commands/test_init.py`

Same structure as `test_buy.py`. Patch targets use `"bensdorp1.commands.sell.*"` module path.

**No-trigger error test pattern**:
```python
def test_no_exit_trigger_returns_error(tmp_path: Path) -> None:
    """sell exits code 1 with error when no scan_exit_triggers row exists."""
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    # First fetchone: open position found; second fetchone: trigger not found
    mock_conn.execute.return_value.fetchone.side_effect = [
        MagicMock(id=1, entry_close=182.50, shares=50, entry_date=...),  # position
        None,  # no trigger
    ]
    with (
        patch("bensdorp1.commands.sell.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.sell.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.sell.run_migrations"),
    ):
        result = runner.invoke(app, ["sell", "AAPL", "178.20"])

    assert result.exit_code == 1
    assert "No exit trigger on record" in result.output
```

---

### `tests/test_commands/test_fix.py` (test)

**Analog:** `tests/test_commands/test_init.py`

Same structure. Patch targets use `"bensdorp1.commands.fix.*"` module path.

**No-changes path test**:
```python
def test_no_changes_exits_with_info(tmp_path: Path) -> None:
    """fix exits 0 with info message when user makes no field changes."""
    # Invoke runner with input that accepts every prompt default (empty Enter presses)
    result = runner.invoke(app, ["fix", "NVDA"], input="y\n\n\n\nn\n")
    assert result.exit_code == 0
    assert "No changes detected" in result.output
```

---

## Shared Patterns

### 1. Command Entry Triad (DB path + engine + migrations)
**Source:** `src/bensdorp1/commands/scan.py` lines 42-44 and `src/bensdorp1/commands/init.py` lines 97, 169-170
**Apply to:** `buy.py`, `sell.py`, `fix.py`
```python
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

### 2. Validation → Early Exit
**Source:** `src/bensdorp1/commands/scan.py` lines 29-36
**Apply to:** all three commands (different validation predicates)
```python
if <condition_fails>:
    print_error("<message>", actions=["<hint>"], console=console)
    raise typer.Exit(code=1)
```

### 3. KeyboardInterrupt Wrapper
**Source:** `src/bensdorp1/commands/init.py` lines 130-137, 161-165
**Apply to:** every `try` block containing `confirm_prompt` or `input()` in all three commands
```python
try:
    ...interactive section...
except KeyboardInterrupt:
    console.print()
    console.print(Text("Operation aborted. No changes were made."))
    raise typer.Exit() from None
```
Note: `confirm_prompt` already prints the abort message internally (see `src/bensdorp1/ui/prompts.py` lines 41-43). The outer `except KeyboardInterrupt` must NOT print the message again — only print a blank line and `raise typer.Exit() from None`.

**Correction:** `confirm_prompt` re-raises `KeyboardInterrupt` after printing the message. The caller's `except KeyboardInterrupt` block must therefore NOT print the abort message again — it should only `raise typer.Exit() from None`. The abort message is already printed by the prompt itself. To avoid duplication, callers should use:
```python
try:
    confirmed = confirm_prompt("...", console=console)
except KeyboardInterrupt:
    raise typer.Exit() from None
```

### 4. DB Write + Backup + Log (always in this order)
**Source:** `src/bensdorp1/commands/init.py` lines 205-214
**Apply to:** confirmed write path of all three commands
```python
with engine.connect() as conn:
    conn.execute(<insert or update>)
    conn.commit()                    # explicit commit required — SQLAlchemy 2.0
create_backup(engine, DATA_DIR / "backups")
log_event(engine, AuditEventType.<EVENT>, symbol=symbol.upper(), payload={...})
print_success("<message>", console=console)
```

### 5. SEPARATOR Constant
**Source:** `src/bensdorp1/commands/init.py` line 38
**Apply to:** all three commands (confirmation header)
```python
SEPARATOR: str = "=" * 64  # 64 characters — matches spec §7.3, §7.4, §7.5
```

### 6. Text() Wrapping
**Source:** `src/bensdorp1/commands/init.py` throughout (e.g. lines 113-116)
**Apply to:** every `console.print(...)` call in all three commands
```python
console.print(Text("some string"))   # CORRECT — markup injection safe
console.print("some string")         # WRONG — do not use
```

### 7. SQLAlchemy Parameterized Queries
**Source:** `src/bensdorp1/commands/init.py` lines 72-85; `src/bensdorp1/db/audit.py` lines 54-63
**Apply to:** every DB query in all three commands
```python
conn.execute(
    select(table.c.col).where(table.c.other_col == value)   # CORRECT
)
# NEVER: conn.execute(text(f"SELECT ... WHERE col = '{value}'"))
```

### 8. CliRunner Test + Module-Level Patch
**Source:** `tests/test_commands/test_init.py` lines 1-12, 28-53
**Apply to:** all three test files
```python
from typer.testing import CliRunner
from bensdorp1.cli import app

runner = CliRunner()

# Patch at the COMMAND MODULE level, not at the definition module:
patch("bensdorp1.commands.buy.get_engine", ...)    # CORRECT
patch("bensdorp1.db.engine.get_engine", ...)       # WRONG (not where buy.py imports it)
```

### 9. db_engine Fixture for Real-DB Tests
**Source:** `tests/conftest.py` lines 33-49
**Apply to:** tests that need real INSERT/SELECT/UPDATE verification
```python
def test_something(db_engine: Engine) -> None:
    # db_engine is a real SQLite file-based engine with schema applied
    # engine singleton is reset to this engine before the test
    # disposes and resets after the test (Windows file handle safety)
    ...
```

---

## No Analog Found

All files have clear analogs. No file requires falling back to RESEARCH.md-only patterns.

| File | Role | Data Flow | Notes |
|------|------|-----------|-------|
| — | — | — | All 8 files have analogs |

---

## Metadata

**Analog search scope:** `src/bensdorp1/commands/`, `src/bensdorp1/db/`, `src/bensdorp1/ui/`, `tests/test_commands/`, `tests/conftest.py`
**Files read:** 14 source files
**Pattern extraction date:** 2026-05-25
