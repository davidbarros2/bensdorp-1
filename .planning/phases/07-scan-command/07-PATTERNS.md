# Phase 7: Scan Command - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 4 new/modified files
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/bensdorp1/commands/scan.py` | command (Typer entry) | request-response | `src/bensdorp1/commands/init.py` | exact |
| `src/bensdorp1/commands/_scan_engine.py` | service/engine | CRUD + batch | `src/bensdorp1/commands/init.py` (engine section, lines 167–243) | role-match |
| `src/bensdorp1/db/schema.py` | model/DDL | CRUD | `src/bensdorp1/db/schema.py` (scan_candidates table, lines 78–100) | exact |
| `tests/test_commands/test_scan.py` | test | request-response | `tests/test_commands/test_init.py` | exact |

---

## Pattern Assignments

### `src/bensdorp1/commands/scan.py` (command, request-response)

**Analog:** `src/bensdorp1/commands/init.py`

**Imports pattern** (lines 1–32 of init.py — adapt for scan):

```python
"""Daily end-of-day screening command."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.text import Text
from sqlalchemy import select
from sqlalchemy.engine import Engine

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR, MARKET_TZ
from bensdorp1.commands._scan_engine import run_scan
from bensdorp1.data import is_trading_day
from bensdorp1.db import get_engine, run_migrations
from bensdorp1.db.schema import scans
from bensdorp1.ui import print_error, print_info
```

**Typer command decorator pattern** (init.py line 93):

```python
@app.command(rich_help_panel="Daily operation")
def scan(force: bool = typer.Option(False, "--force", help="Re-run even if scan already ran today.")) -> None:
    """Run daily end-of-day screening for exit triggers and buy candidates."""
```

Note: `-> None` is mandatory (mypy strict). `rich_help_panel` matches the stub's existing panel string.

**Time-gate guard pattern** — adapt from init.py guard (lines 96–106):

```python
# Time gate: refuse before 16:30 ET (MARKET_TZ)
now_et = datetime.now(MARKET_TZ)
if now_et.hour < 16 or (now_et.hour == 16 and now_et.minute < 30):
    print_error(
        "Market has not closed yet.",
        data={
            "Market closes at": "16:00 ET",
            "Scan available after": "16:30 ET",
            "Current time": f"{now_et:%H:%M} ET",
        },
    )
    raise typer.Exit(code=1)
```

**Non-trading-day pattern** — use `is_trading_day` + `print_info` + replay:

```python
today = datetime.now(MARKET_TZ).date()
if not is_trading_day(today):
    # fetch most recent raw_output from scans table
    engine = get_engine(DATA_DIR / "data" / "bensdorp1.db")
    with engine.connect() as conn:
        row = conn.execute(
            select(scans.c.scan_date, scans.c.raw_output)
            .order_by(scans.c.scan_date.desc())
            .limit(1)
        ).fetchone()
    if row is None:
        print_info("No scans recorded yet. Run `bensdorp1 scan` on a trading day after 16:30 ET.")
    else:
        last_date = row.scan_date.date()
        print_info(f"Today is not a trading day. Showing last scan from {last_date}.")
        if row.raw_output:
            console.print(row.raw_output, markup=False, highlight=False)
    raise typer.Exit()
```

**Idempotency check pattern**:

```python
# Check for existing same-day scan
scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)
with engine.connect() as conn:
    existing = conn.execute(
        select(scans.c.raw_output)
        .where(scans.c.scan_date == scan_date_utc)
    ).fetchone()

if existing is not None and not force:
    if existing.raw_output:
        console.print(existing.raw_output, markup=False, highlight=False)
    raise typer.Exit()
```

**Engine call + print pattern** (thin delegation, matches init.py lines 169–214 structure):

```python
console = Console()
engine = get_engine(DATA_DIR / "data" / "bensdorp1.db")
run_migrations(engine)
output = run_scan(engine, force=force, console=console)
console.print(output, markup=False, highlight=False)
```

**Early exit pattern** (init.py lines 106, 135–137):

```python
raise typer.Exit(code=1)   # error exits (time gate, data errors)
raise typer.Exit()          # clean exits (non-trading day, idempotent replay)
```

---

### `src/bensdorp1/commands/_scan_engine.py` (service/engine, CRUD + batch)

**Analog:** `src/bensdorp1/commands/init.py` (lines 34–243 — engine section)

**Module docstring + imports pattern** (init.py lines 1–32 as template):

```python
"""Scan engine: data fetch, stop updates, exit trigger detection, output rendering."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from rich.console import Console
from rich.text import Text
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from bensdorp1.config import DATA_DIR, MARKET_TZ
from bensdorp1.data import (
    check_price_coverage,
    get_constituents,
    get_trading_days,
    update_price_data,
)
from bensdorp1.db import AuditEventType, create_backup, log_event
from bensdorp1.db.schema import (
    config as config_table,
    positions,
    scan_candidates,
    scan_exit_triggers,
    scans,
    price_daily,
)
from bensdorp1.strategy.positions import (
    compute_effective_stop,
    compute_trailing_stop,
    is_exit_triggered,
    update_highest_close,
)
from bensdorp1.strategy.screening import (
    Candidate,
    liquidity_filter,
    momentum_filter,
    rank_candidates,
    regime_filter,
)
from bensdorp1.ui import (
    TrackContext,
    feedback,
    format_date,
    format_days,
    format_price,
    format_pct,
    format_volume,
    print_info,
    print_warning,
    render_kv_block,
    render_table,
)
```

**Module-level constants** (init.py lines 34–41 as template):

```python
SEPARATOR: str = "=" * 64        # matches spec §7.2 exactly — same as init.py
PRICE_FETCH_WINDOW_DAYS: int = 10  # calendar days for narrow incremental fetch
```

**Public entry point signature** (console ownership per Phase 5 D-06):

```python
def run_scan(
    engine: Engine,
    *,
    force: bool = False,
    console: Console | None = None,
) -> str:
    """Run full scan pipeline. Returns rendered output string.

    The returned string is stored in scans.raw_output and printed by scan.py.
    console receives progress output (multi-step display); defaults to Console().
    """
    con = console if console is not None else Console()
    capture = Console(record=True, width=120)
    # ... render to capture ...
    raw = capture.export_text()
    return raw
```

**Multi-step progress pattern** (init.py lines 175–199 — exact copy structure):

```python
with feedback.multi_step(2, console=con) as ms:
    # Step [1/2] — Fetch latest market data
    with ms.step("Fetching latest market data", total=len(all_symbols)) as track:
        assert isinstance(track, TrackContext)
        update_price_data(
            engine,
            all_symbols,
            start=date.today() - timedelta(days=PRICE_FETCH_WINDOW_DAYS),
            end=date.today(),
        )
        for symbol in all_symbols:
            track.advance(symbol)
    # Print detail AFTER with-block exits (Pitfall 4 — never inside the block)
    con.print(Text(f"      Constituents fetched: {len(symbols)}/{len(all_symbols)}"))
    con.print()

    # Step [2/2] — Compute signals
    with ms.step("Computing signals") as spinner:
        # spinner is SpinnerContext (no total=)
        spinner.tick()
        # ... strategy pipeline calls ...
```

**DB write pattern** (init.py lines 204–214 — adapt for scan):

```python
# INSERT or UPDATE scans row
now_utc = datetime.now(UTC)
scan_date_utc = datetime(today.year, today.month, today.day, tzinfo=UTC)
stmt = (
    sqlite_insert(scans)
    .values(
        scan_date=scan_date_utc,
        regime_active=regime_active,
        candidate_count=len(candidates),
        exit_trigger_count=len(new_triggers),
        raw_output=raw_output,
        created_at=now_utc,
    )
    .on_conflict_do_update(
        index_elements=["scan_date"],
        set_={
            "regime_active": regime_active,
            "candidate_count": len(candidates),
            "exit_trigger_count": len(new_triggers),
            "raw_output": raw_output,
        },
    )
)
with engine.connect() as conn:
    result = conn.execute(stmt)
    conn.commit()
    scan_id = result.inserted_primary_key[0]  # works for both INSERT and upsert
```

**Audit event + backup pattern** (init.py lines 204–214 — exact structure):

```python
log_event(
    engine,
    AuditEventType.SCAN_PERFORMED,
    payload={
        "scan_id": scan_id,
        "scan_date": today.isoformat(),
        "regime": "bull" if regime_active else "bear",
        "spx_close": spx_close,
        "spx_sma_200": spx_sma_200,
        "constituents_count": len(symbols),
        "buy_candidates_count": len(candidates),
        "exit_triggers_count": len(new_triggers),
        "constituents_freshness_days": freshness_days,
    },
)
create_backup(engine, DATA_DIR / "backups")
```

**Render output pattern** — render to `capture`, not `con` (two-console strategy per Research open question 1):

```python
# Header — exact spec §7.2 format
capture.print(Text(SEPARATOR))
capture.print(Text(f"Scan for {format_date(today)}"))
capture.print(Text(SEPARATOR))
capture.print()

# Market regime section — render_kv_block with plain number format for index values
capture.print(Text("Market regime"))
capture.print(Text("-" * len("Market regime")))
render_kv_block(
    {
        "S&P 500 close": f"{spx_close:,.2f}",        # no $ — spec §7.2 uses plain number
        "S&P 500 SMA 200": f"{spx_sma_200:,.2f}",   # no $ — spec §7.2 uses plain number
        "Regime": regime_label,                       # "Bull market (...)" or "Bear market (...)"
    },
    capture,
)
capture.print()

# Exit triggers table — render_table from ui/tables.py
render_table(
    columns=[
        ("Symbol", "left"),
        ("Reason", "left"),
        ("Close", "right"),
        ("Effective stop", "right"),
        ("Days held", "right"),
    ],
    rows=[...],   # one list per triggered position
    console=capture,
)
```

**Catch-up stop update loop pattern** — triggered positions are frozen (D-07/D-08):

```python
triggered_position_ids: set[int] = set()  # D-07: freeze tracking

for missed_day in missed_days:  # DatetimeIndex from get_trading_days()
    for pos in open_positions:
        if pos.id in triggered_position_ids:
            continue  # frozen — skip (Pitfall 8)
        close = _get_close_for_day(engine, pos.symbol, missed_day)
        if close is None:
            continue
        new_hc = update_highest_close(pos.highest_close, close)
        new_ts = compute_trailing_stop(new_hc)
        eff_stop = compute_effective_stop(pos.initial_stop, new_ts)
        if is_exit_triggered(close, eff_stop):
            triggered_position_ids.add(pos.id)
            # INSERT into scan_exit_triggers (D-09: use missed_day as trigger date)
            # scan_id = today's scan_id (Research open question 3 resolution)
        else:
            # UPDATE positions set highest_close, trailing_stop
            with engine.connect() as conn:
                conn.execute(
                    update(positions)
                    .where(positions.c.id == pos.id)
                    .values(highest_close=new_hc, trailing_stop=new_ts)
                )
                conn.commit()
```

**Available cash query pattern** (from Research §Cash Available for Scan):

```python
def _get_available_cash(engine: Engine) -> float:
    with engine.connect() as conn:
        row = conn.execute(
            select(config_table.c.value)
            .where(config_table.c.key == "available_cash")
        ).fetchone()
    if row is None:
        return 0.0
    return float(row.value)
```

---

### `src/bensdorp1/db/schema.py` (model/DDL, CRUD)

**Analog:** `src/bensdorp1/db/schema.py` — `scan_candidates` table definition (lines 78–100) and its companion `Index` calls (lines 89–100)

**Existing scan_candidates pattern to copy** (lines 78–100):

```python
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
Index(
    "ix_scan_candidates_scan_rank",
    scan_candidates.c.scan_id,
    scan_candidates.c.rank,
    unique=True,
)
Index(
    "ix_scan_candidates_scan_symbol",
    scan_candidates.c.scan_id,
    scan_candidates.c.symbol,
    unique=True,
)
```

**New scan_exit_triggers table** — insert after `scan_candidates` block, before `constituents_cache`:

```python
scan_exit_triggers: Table = Table(
    "scan_exit_triggers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=False),
    Column("position_id", Integer, ForeignKey("positions.id"), nullable=False),
    Column("reason", Text, nullable=False),        # "Trailing stop" | "Initial stop"
    Column("effective_stop", Float, nullable=False),
)
Index(
    "ix_scan_exit_triggers_position",
    scan_exit_triggers.c.position_id,
)
```

Note: The `Table(name, metadata, *columns)` positional call style is consistent throughout schema.py (lines 22, 30, 43, 65, 78, 102, 111). The `Index(name, *cols)` pattern follows immediately after each table. `create_all(checkfirst=True)` in `run_migrations` picks up the new table automatically — no manual migration step.

---

### `tests/test_commands/test_scan.py` (test, request-response + unit)

**Analog:** `tests/test_commands/test_init.py`

**File header + runner pattern** (test_init.py lines 1–11):

```python
"""Tests for commands/scan.py and commands/_scan_engine.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from bensdorp1.cli import app

runner = CliRunner()
```

**CliRunner invocation pattern** (test_init.py lines 20–24):

```python
result = runner.invoke(app, ["scan"])           # basic invoke
result = runner.invoke(app, ["scan", "--force"]) # with flag
assert result.exit_code == 0
assert result.exit_code == 1
```

**Module-level patch pattern** (test_init.py lines 37–54 — adapt patch targets for scan):

```python
def test_happy_path_bull(tmp_path: Path) -> None:
    mock_engine = MagicMock()
    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
        patch("bensdorp1.commands.scan.is_trading_day", return_value=True),
        patch("bensdorp1.commands.scan.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.scan.run_migrations"),
        patch(
            "bensdorp1.commands.scan.run_scan",
            return_value="Scan for 2026-05-21\nBull market\n",
        ),
    ):
        mock_dt.now.return_value = datetime(2026, 5, 21, 17, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan"])
    assert result.exit_code == 0
    assert "Scan for 2026-05-21" in result.output
```

**Time-gate test pattern** (test_init.py guard test lines 14–24 as template):

```python
def test_time_gate(tmp_path: Path) -> None:
    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
    ):
        # Mock datetime.now() to return 15:00 ET — before 16:30 gate
        mock_dt.now.return_value = datetime(2026, 5, 21, 15, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan"])
    assert result.exit_code == 1
    assert "16:30 ET" in result.output
```

**db_engine fixture usage for unit tests** (test_init.py lines 79–93):

```python
def test_catchup_stop_updates(db_engine: Engine) -> None:
    """Given price_daily rows for 3 missed days, assert correct stop updates per day."""
    from bensdorp1.commands._scan_engine import _update_position_stops

    # insert fixture positions + price_daily rows directly into db_engine
    # then call the private function under test
    # assert via SELECT from positions table
```

**Patch-heavy integration test pattern** (test_init.py lines 28–53 — full mock stack):

```python
def test_idempotent_same_day(tmp_path: Path) -> None:
    """Second call returns raw_output, no re-fetch; single scans row."""
    mock_engine = MagicMock()
    stored_output = "Scan for 2026-05-21\n..."

    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
        patch("bensdorp1.commands.scan.is_trading_day", return_value=True),
        patch("bensdorp1.commands.scan.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.scan.run_migrations"),
        patch("bensdorp1.commands.scan.run_scan") as mock_run_scan,
    ):
        # Mock the scans query to return existing row
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.fetchone.return_value = MagicMock(
            raw_output=stored_output
        )
        mock_dt.now.return_value = datetime(2026, 5, 21, 17, 0, tzinfo=MARKET_TZ)
        result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0
    assert stored_output in result.output
    mock_run_scan.assert_not_called()  # no re-compute
```

---

## Shared Patterns

### Console Ownership (Phase 5 D-06)

**Source:** `src/bensdorp1/commands/init.py` lines 108–109 and `src/bensdorp1/ui/styles.py` line 20

**Apply to:** `scan.py` (creates `Console()` for progress), `_scan_engine.py` (`run_scan` accepts `console: Console | None = None`)

```python
# Pattern: all engine functions accept optional console; tests pass Console(record=True)
con = console if console is not None else Console()
capture = Console(record=True, width=120)  # separate capture console for raw_output
```

**Two-console strategy (scan-specific):**
- `con` — receives multi-step progress (transient Live displays, shown to terminal)
- `capture` — receives final rendered output sections (stored in `scans.raw_output` and printed verbatim on replay)

### All Output Through Console (never `print()`)

**Source:** `src/bensdorp1/commands/init.py` lines 112–125 and Research Anti-Pattern 4

**Apply to:** All output in `_scan_engine.py` and `scan.py`

```python
# CORRECT — appears in Console(record=True).export_text()
capture.print(Text(SEPARATOR))
capture.print(Text("Scan for 2026-05-21"))

# WRONG — bypasses Rich, invisible to record=True capture
print("Scan for 2026-05-21")
```

### Error Handling / Early Exit

**Source:** `src/bensdorp1/commands/init.py` lines 96–107, 131–137

**Apply to:** `scan.py` — time gate (exit 1), non-trading day (exit 0), idempotent replay (exit 0)

```python
raise typer.Exit(code=1)   # error: time gate, data errors
raise typer.Exit()          # clean: non-trading day, idempotent replay
```

### SQLite Upsert

**Source:** `src/bensdorp1/commands/init.py` lines 70–85 (`_store_cash`)

**Apply to:** `_scan_engine.py` — `scans` table INSERT/UPDATE for `--force` idempotency (D-02)

```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

stmt = (
    sqlite_insert(table)
    .values(...)
    .on_conflict_do_update(
        index_elements=["unique_column"],
        set_={...},
    )
)
with engine.connect() as conn:
    conn.execute(stmt)
    conn.commit()
```

### Multi-Step Progress: Print Detail AFTER Block, Not Inside

**Source:** `src/bensdorp1/commands/init.py` lines 179–189 and `src/bensdorp1/ui/progress.py` lines 285–300

**Apply to:** `_scan_engine.py` — Phase B progress (step 1 and 2)

```python
with ms.step("Fetching latest market data", total=len(all_symbols)) as track:
    # ... work happens here ...
    track.advance(symbol)
# Print detail AFTER the with-block exits — MultiStepContext printed "[1/2] ... done." already
con.print(Text(f"      Constituents fetched: {n}/{total}"))
con.print()
```

### Parameterized DB Queries

**Source:** `src/bensdorp1/db/audit.py` lines 44–63

**Apply to:** All `_scan_engine.py` DB operations (SELECT, INSERT, UPDATE)

```python
# Always use SQLAlchemy bound parameters — never string interpolation
with engine.connect() as conn:
    conn.execute(
        select(positions.c.id, positions.c.symbol, ...)
        .where(positions.c.closed_at == None)  # noqa: E711
    )
    conn.commit()
```

### Markup Safety

**Source:** `src/bensdorp1/ui/messages.py` lines 55–58 and `src/bensdorp1/ui/styles.py` lines 157–163

**Apply to:** All symbol names, company names, and user-derived strings in `_scan_engine.py`

```python
# Wrap caller-supplied strings in Text() to prevent Rich markup injection
capture.print(Text(symbol))                     # symbol from DB
render_kv_block(data, capture)                  # render_kv_block uses markup=False internally
render_table(columns, rows, console=capture)    # render_table uses Text(cell) per row
```

### Engine Teardown in Tests (Windows-critical)

**Source:** `tests/conftest.py` lines 33–49

**Apply to:** `tests/test_commands/test_scan.py` — all tests using `db_engine` fixture

```python
# Use the db_engine fixture from conftest.py — NEVER create Engine directly in tests
# The fixture calls _reset_engine_for_testing() in teardown (dispose() for Windows)
def test_something(db_engine: Engine) -> None:
    # db_engine is already migrated and scoped to tmp_path
    ...
```

---

## No Analog Found

No files in this phase lack a codebase analog. All four files have direct analogs from prior phases.

---

## Metadata

**Analog search scope:** `src/bensdorp1/commands/`, `src/bensdorp1/db/`, `tests/test_commands/`, `tests/`
**Files read:** 12 source files
**Pattern extraction date:** 2026-05-24
