# Phase 7: Scan Command - Research

**Researched:** 2026-05-24
**Domain:** CLI command integration — scan engine, DB schema extension, strategy pipeline assembly
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Same-day replay: print stored `scans.raw_output` verbatim; no re-fetch, no re-compute, no duplicate audit event.
**D-02:** `--force`: UPDATE (not INSERT) the existing scans row; always re-run Phase B data fetch.
**D-03:** Non-trading day: print `Info: Today is not a trading day. Showing last scan from [date].` then print most recent `raw_output`. If no prior scan, print appropriate empty-state message.
**D-04:** `--force` on same-day calls `update_price_data`; `ON CONFLICT DO NOTHING` means existing today's prices are not overwritten.
**D-05:** Add `scan_exit_triggers` table to `schema.py`: `(id, scan_id FK scans, position_id FK positions, reason TEXT, effective_stop FLOAT)`. `create_all` handles it automatically.
**D-06:** Triggers persist until position is confirmed closed by Phase 8's `sell` command. NOT removed on stock recovery.
**D-07:** Once a position has a row in `scan_exit_triggers`, freeze its `highest_close` and `trailing_stop` — no further updates.
**D-08:** Partial catch-up: walk through each missed trading day chronologically, update `highest_close` and `trailing_stop` per day.
**D-09:** On each missed day, run `is_exit_triggered`; if triggered, insert into `scan_exit_triggers` with that missed day's date.
**D-10:** System notes include: `Catch-up: updated stop levels for N missed trading days. Split detection deferred to Phase 11.`
**D-11:** Missed trading days computed via NYSE calendar between last scan date and today (exclusive of today).
**D-12:** Daily scan calls `update_price_data(engine, symbols, start=today - 10 calendar days, end=today)`. Strategy reads full 220-day history from `price_daily`.
**D-13:** Phase B progress bar always shows all symbols (503 + ^GSPC total). Use `feedback.track()` iterating over all symbols.
**D-14:** Constituents freshness (DATA-05): if `constituents_cache.fetched_at` > 7 days old, call `get_constituents(engine)` inline before Phase B.
**D-15:** Split into two files: `commands/scan.py` (Typer entry + time gate + trading-day check + idempotency check) and `commands/_scan_engine.py` (all business logic). Engine exposes `run_scan(engine, force=False) -> str`.
**D-16:** `_scan_engine.py` internal structure: `_run_preflight`, `_fetch_data`, `_update_position_stops`, `_detect_exit_triggers`, `_run_screening`, `_render_output`, `_persist_scan`.
**D-17:** Each scan UPDATEs `positions` row for open non-triggered positions with new `highest_close` and `trailing_stop`.
**D-18:** `effective_stop` NOT stored in positions — always computed at read time as `max(initial_stop, trailing_stop)`.
**D-19:** Phase 9's `portfolio` reads latest close from `price_daily`. No `last_close` column added.
**D-20:** Two separate buy-candidates tables exactly as spec §7.2 (top-10 always; affordable only where `position_size > 0`).
**D-21:** Bearish regime: show regime section + exit triggers only. Omit both buy-candidates tables. System note: `Regime: Bear market. No buy candidates generated.`
**D-22:** If all 10 candidates have `position_size = 0`, show affordable table with note: `No affordable candidates at current cash level ($X).`
**D-23:** CliRunner integration tests covering: time gate, happy path, bearish regime, idempotent same-day, `--force`, non-trading day.
**D-24:** Unit tests for complex `_scan_engine.py` logic: catch-up iteration, exit trigger detection on missed days, stop freeze.

### Claude's Discretion

- Whether `run_scan` accepts a `Console` parameter or captures internally via `Console(record=True)` — follow Phase 5 D-06 pattern (optional `console` param).
- Exact module-level constant for narrow date window (10 vs 14 calendar days) — 10 is sufficient.
- Whether catch-up runs inside the same transaction as the main scan or separately — single transaction preferred for atomicity.
- Exact wording of system notes beyond fixed templates.

### Deferred Ideas (OUT OF SCOPE)

- Full catch-up event templates (13 templates from spec §8.9) — Phase 11
- Split detection and adjustment — Phase 11 (DATA-06)
- Delisted position handling — Phase 11 (STATE-07)
- Snapshot tests for scan output — Phase 13 (TEST-04)
- Integration tests with fully mocked yfinance/Wikipedia/Slickcharts — Phase 13 (TEST-05)

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CMD-03 | `bensdorp1 scan [--force]` — end-of-day screening; refuses before 16:30 ET; idempotent (shows existing scan without `--force`); outputs exit triggers then buy candidates | Fully covered: time gate via `datetime.now(MARKET_TZ)`, idempotency via `scans.raw_output`, all output sections mapped to existing UI primitives |

Strategy requirements implemented by scan (all previously implemented in Phase 4; scan is the consumer):

| ID | Description | Research Support |
|----|-------------|------------------|
| STRAT-01 | Regime filter | `regime_filter(spx_closes)` → bool |
| STRAT-02 | Liquidity filter | `liquidity_filter(price_dfs)` → list[str] |
| STRAT-03 | Momentum filter | `momentum_filter(price_dfs)` → list[str] |
| STRAT-04 | Ranking | `rank_candidates(price_dfs, available_cash)` → list[Candidate] |
| STRAT-05 | Max 10 positions | `rank_candidates` returns at most 10 |
| STRAT-06 | Position sizing | `compute_position_size(cash, prev_close)` → int |
| STRAT-07 | Initial stop | `compute_initial_stop(entry_close)` — used at buy time, read here |
| STRAT-08 | Trailing stop | `compute_trailing_stop(highest_close)` — updated per-scan |
| STRAT-09 | Effective stop | `compute_effective_stop(initial, trailing)` — computed at read time |
| STRAT-10 | Exit triggers persist | `scan_exit_triggers` table; not deleted until Phase 8 sell |

</phase_requirements>

---

## Summary

Phase 7 is the central integration phase for `bensdorp1`. It wires together all previously built subsystems — data fetch (`prices.py`), strategy filters (`screening.py`, `positions.py`), DB schema (`schema.py`), calendar (`calendar.py`), UI primitives (`progress.py`, `tables.py`, `messages.py`, `styles.py`) — into a complete daily scan pipeline.

The codebase already has all the building blocks. Phase 7's job is to assemble them correctly and add the one missing schema object (`scan_exit_triggers` table). The split between `scan.py` (thin Typer layer) and `_scan_engine.py` (testable business logic) mirrors the Phase 6 init pattern exactly.

The scan has three logical phases: pre-flight checks (time gate, trading-day, idempotency, constituents freshness, catch-up detection); data fetch and stop updates (incremental price download, position stop math, exit trigger detection); and output rendering followed by persistence (render to string stored in `raw_output`, then persist scan/candidates/triggers, then audit log, then backup).

**Primary recommendation:** Implement `_scan_engine.run_scan(engine, force, console) -> str`. The function assembles price DataFrames from `price_daily` for all constituents + ^GSPC, runs strategy pipeline, renders all output sections to a `Console(record=True)` capture buffer, stores raw output in `scans.raw_output`, and returns the string. `scan.py` is a 30-line Typer wrapper that calls `run_scan` and prints the result.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Time gate (16:30 ET check) | CLI layer (`scan.py`) | — | Pure datetime check; belongs in entry point before any DB access |
| Trading-day check | CLI layer (`scan.py`) | `data/calendar.py` | Gate before engine; `is_trading_day()` is already a public API |
| Idempotency check | CLI layer (`scan.py`) | DB (`scans` table) | Determines whether to call engine at all |
| Constituents freshness + refresh | Engine (`_scan_engine.py`) | `data/constituents.py` | Business logic; engine owns pre-flight |
| Price data fetch | Engine (`_scan_engine.py`) | `data/prices.py` | Engine orchestrates; `update_price_data` does the I/O |
| Price DataFrame assembly | Engine (`_scan_engine.py`) | DB (`price_daily` table) | SQL query; engine assembles `dict[str, DataFrame]` |
| Catch-up stop updates | Engine (`_scan_engine.py`) | `strategy/positions.py` | Pure functions called by engine; positions owned by engine |
| Exit trigger detection | Engine (`_scan_engine.py`) | `strategy/positions.py` | `is_exit_triggered()` called per position per day |
| Strategy filters (regime/liquidity/momentum/rank) | Engine (`_scan_engine.py`) | `strategy/screening.py` | Pure functions; engine passes DataFrames |
| Output rendering | Engine (`_scan_engine.py`) | `ui/` primitives | Engine renders; `scan.py` prints |
| scan_exit_triggers persistence | Engine (`_scan_engine.py`) | DB (`scan_exit_triggers` table) | New table; engine inserts on trigger detection |
| Scan record persistence | Engine (`_scan_engine.py`) | DB (`scans`, `scan_candidates`) | Engine writes after rendering |
| Backup | Engine (`_scan_engine.py`) | `db/backup.py` | Last step after all writes |
| Audit event | Engine (`_scan_engine.py`) | `db/audit.py` | Last step with final counts |

---

## Standard Stack

No new packages are installed in this phase. All dependencies are already in `pyproject.toml` from Phases 1–6.

### Core (already installed)
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| typer | `>=0.21.1` | CLI entry point + `--force` flag | Established in Phase 1 |
| rich | `>=14.0` | Output rendering, Console(record=True) capture | Established in Phase 5 |
| sqlalchemy | `>=2.0.49,<2.1` | DB reads/writes for all 4 tables | Established in Phase 2 |
| pandas | `>=3.0.3` | DataFrame assembly from price_daily | Established in Phase 3 |
| pandas-market-calendars | `>=5.3.2` | Trading-day check, missed-day enumeration | Established in Phase 3 |

### No Package Legitimacy Audit Required

This phase installs zero new external packages. All dependencies were verified and locked in prior phases.

---

## Architecture Patterns

### System Architecture Diagram

```
bensdorp1 scan [--force]
        |
        v
scan.py (Typer layer)
  |-- datetime.now(MARKET_TZ) >= 16:30?  --[NO]--> print_error + Exit(1)
  |-- is_trading_day(today)?              --[NO]--> fetch last raw_output + print + Exit(0)
  |-- scans row for today exists?
  |     AND --force not set?              --[YES]--> print raw_output + Exit(0)
  |
  v
_scan_engine.run_scan(engine, force, console)
  |
  |-- [Pre-flight]
  |     |-- get_constituents(engine) if stale
  |     |-- check_price_coverage(engine) -> (covered, total); abort if < 95%
  |     |-- detect catch-up: get_trading_days(last_scan_date+1, yesterday)
  |
  |-- [Phase B: Data fetch with multi_step progress]
  |     |-- update_price_data(engine, symbols, start=today-10d, end=today)
  |     |    (feedback.multi_step(2) -> step(1) with feedback.track(total=504))
  |
  |-- [Catch-up stop updates per missed day]
  |     |-- for each missed_day in missed_days:
  |     |     for each open non-triggered position:
  |     |       close = price_daily[symbol][missed_day]
  |     |       highest_close = update_highest_close(hc, close)
  |     |       trailing_stop = compute_trailing_stop(highest_close)
  |     |       effective_stop = compute_effective_stop(initial_stop, trailing_stop)
  |     |       if is_exit_triggered(close, effective_stop):
  |     |           INSERT scan_exit_triggers (with missed_day as trigger date)
  |     |           freeze position (no further stop updates)
  |     |       else: UPDATE positions (highest_close, trailing_stop)
  |
  |-- [Today's stop updates]
  |     |-- same loop as catch-up, but for today only
  |
  |-- [Strategy pipeline] (feedback.multi_step step 2)
  |     |-- assemble price_dfs: dict[str, DataFrame] from price_daily (>=221 rows each)
  |     |-- regime_filter(spx_closes) -> bool
  |     |-- [if bull]: liquidity_filter(price_dfs) -> list[str]
  |     |              momentum_filter(filtered_dfs) -> list[str]
  |     |              rank_candidates(momentum_dfs, cash) -> list[Candidate] (top 10)
  |
  |-- [Render output to Console(record=True)]
  |     |-- Header: "Scan for YYYY-MM-DD"
  |     |-- Market regime section (render_kv_block)
  |     |-- Today's exit triggers (render_table)
  |     |-- Pending exit triggers from prior scans (render_table)
  |     |-- [if bull] Buy candidates top 10 (render_table)
  |     |-- [if bull] Buy candidates affordable (render_table or note)
  |     |-- System notes
  |
  |-- [Persist]
  |     |-- INSERT/UPDATE scans row (raw_output = captured string)
  |     |-- INSERT scan_candidates rows
  |     |-- log_event(SCAN_PERFORMED, payload={...})
  |     |-- create_backup(engine, DATA_DIR / "backups")
  |
  v
scan.py prints raw_output to stdout
```

### Recommended Project Structure (additions only)
```
src/bensdorp1/commands/
├── scan.py              # Thin Typer layer (replace stub)
└── _scan_engine.py      # NEW: all business logic

src/bensdorp1/db/
└── schema.py            # ADD scan_exit_triggers table

tests/test_commands/
└── test_scan.py         # NEW: CliRunner + unit tests
```

### Pattern 1: Console Ownership in Engine Functions

Established in Phase 5 (D-06) and used in Phase 6 (init.py):

```python
# Source: src/bensdorp1/commands/init.py (Phase 6 reference)
def run_scan(
    engine: Engine,
    *,
    force: bool = False,
    console: Console | None = None,
) -> str:
    con = console if console is not None else Console()
    capture = Console(record=True)
    # ... render to capture ...
    return capture.export_text()
```

Tests pass `Console(record=True)` for the outer console; a second `Console(record=True)` inside the function captures the output string. Alternatively, render everything to `capture` and pass `capture` as both the render console and the source of `export_text()`.

### Pattern 2: CliRunner Test with Module-Level Patches

Established in Phase 6 (`tests/test_commands/test_init.py`):

```python
# Source: tests/test_commands/test_init.py
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from bensdorp1.cli import app

runner = CliRunner()

def test_time_gate(tmp_path: Path) -> None:
    with (
        patch("bensdorp1.commands.scan.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.scan.datetime") as mock_dt,
    ):
        # mock datetime.now() to return 15:00 ET
        mock_dt.now.return_value = ...
        result = runner.invoke(app, ["scan"])
    assert result.exit_code == 1
    assert "16:30 ET" in result.output
```

### Pattern 3: Price DataFrame Assembly from price_daily

The engine must query `price_daily` to build `dict[str, pd.DataFrame]` for all filter functions. Each DataFrame needs `[close, volume]` columns and at least 221 rows (201 for momentum/ranking + 20 for liquidity window).

```python
# Conceptual pattern — VERIFIED from existing filter signatures
from sqlalchemy import select, desc
from bensdorp1.db.schema import price_daily

def _load_price_dfs(
    engine: Engine,
    symbols: list[str],
    rows_needed: int = 221,
) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    with engine.connect() as conn:
        for symbol in symbols:
            rows = conn.execute(
                select(price_daily.c.trade_date, price_daily.c.close, price_daily.c.volume)
                .where(price_daily.c.symbol == symbol)
                .order_by(price_daily.c.trade_date)
                .limit(rows_needed)  # or fetch all and tail
            ).fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=["trade_date", "close", "volume"])
                result[symbol] = df
    return result
```

Note: Filter functions require the DataFrame indexed chronologically with last row = today. The query should `ORDER BY trade_date DESC LIMIT N` then reverse, or use a subquery. The simpler approach: fetch all rows ordered ascending, take the last 221 rows with `df.tail(221)`.

### Pattern 4: scan_exit_triggers Table DDL

```python
# Add to src/bensdorp1/db/schema.py after scan_candidates definition
scan_exit_triggers: Table = Table(
    "scan_exit_triggers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scan_id", Integer, ForeignKey("scans.id"), nullable=False),
    Column("position_id", Integer, ForeignKey("positions.id"), nullable=False),
    Column("reason", Text, nullable=False),       # "Trailing stop" | "Initial stop"
    Column("effective_stop", Float, nullable=False),
)
Index(
    "ix_scan_exit_triggers_position",
    scan_exit_triggers.c.position_id,
)
```

`create_all(checkfirst=True)` in `run_migrations()` picks this up automatically — no ALTER TABLE, no manual migration step needed.

### Pattern 5: Idempotent scan_date Storage

The `scans.scan_date` column is `DateTime(timezone=True)` with `unique=True`. Per the context, scan_date stores the trading date as date-at-midnight UTC:

```python
# Store today's ET trading date as midnight UTC
from datetime import date, datetime, UTC, timezone
import zoneinfo

def _trading_date_utc(tz: zoneinfo.ZoneInfo) -> datetime:
    """Return today's date in tz, stored as midnight UTC datetime."""
    today = datetime.now(tz).date()
    return datetime(today.year, today.month, today.day, tzinfo=UTC)
```

The idempotency check queries `scans.scan_date == _trading_date_utc(MARKET_TZ)`.

### Anti-Patterns to Avoid

- **Calling `update_price_data` inside the per-symbol progress track loop:** `update_price_data` does bulk download. For Phase 7's narrow window, call it once for all symbols, not once per symbol. The progress feedback tracks per-symbol reporting, not per-symbol download.
- **Building price_dfs from constituents only:** ^GSPC must be included in `price_daily` queries (for `regime_filter`). The SPX DataFrame is assembled separately and passed to `regime_filter`.
- **Assuming `positions.closed_at IS NULL` is the only open-position filter:** also exclude positions that already have a row in `scan_exit_triggers` for the stop-freeze logic (D-07). Query: `positions WHERE closed_at IS NULL` = open; then check `scan_exit_triggers` for trigger state.
- **Rendering to `_default_console` in engine functions:** engine functions must accept `console` parameter to be testable without Rich's transient Live display interfering with CliRunner output capture.
- **Using `print()` instead of `console.print(Text(...)):`** plain `print()` bypasses Rich and does not appear in `Console(record=True)` export. All output must go through the console object.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NYSE trading day check | Custom date arithmetic | `is_trading_day(dt)` from `data/calendar.py` | Already implemented; handles holidays |
| Missed day enumeration | Loop with `timedelta` | `get_trading_days(start, end)` from `data/calendar.py` | Returns UTC `DatetimeIndex` of NYSE trading days |
| Ticker form conversion | String replace logic | `_to_yfinance()` / `_to_db()` inside `prices.py` | These are private; `update_price_data` handles conversion internally |
| Price upsert with dedup | Custom INSERT logic | `update_price_data(engine, symbols, start, end)` | Already uses `ON CONFLICT DO NOTHING` |
| Stop arithmetic | Custom math | `update_highest_close`, `compute_trailing_stop`, `compute_effective_stop`, `is_exit_triggered` from `strategy/positions.py` | Already implemented, tested with Hypothesis |
| Strategy filters | Custom filter code | `regime_filter`, `liquidity_filter`, `momentum_filter`, `rank_candidates` from `strategy/screening.py` | Already implemented, tested |
| Audit event write | Direct SQL INSERT | `log_event(engine, AuditEventType.SCAN_PERFORMED, payload={...})` | Handles UTC timestamp, JSON serialization |
| DB backup | File copy | `create_backup(engine, DATA_DIR / "backups")` | Uses sqlite3 online backup API; safe during concurrent reads |
| KV-block formatting | Manual string padding | `render_kv_block(data, console)` from `ui/styles.py` | Handles alignment, markup safety, `markup=False` |
| Table rendering | ASCII table code | `render_table(columns, rows, console=console)` from `ui/tables.py` | Already spec-compliant (no borders, right-aligned numbers) |
| Multi-step progress | Custom Rich Live | `feedback.multi_step(2, console=console)` from `ui/progress.py` | Already implements rule 6.23 exactly |

---

## Exact API Reference

### `strategy/screening.py` — All Pure Functions

```python
# VERIFIED from src/bensdorp1/strategy/screening.py

class Candidate(TypedDict):
    symbol: str
    roc_200: float
    prev_close: float
    position_size: int    # 0 if unaffordable

def regime_filter(spx_closes: pd.Series[float]) -> bool:
    """Raises ValueError if len < 200."""

def liquidity_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]:
    """Raises ValueError if any symbol has < 21 rows."""

def momentum_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]:
    """Raises ValueError if any symbol has < 201 rows."""

def rank_candidates(
    price_dfs: dict[str, pd.DataFrame],
    available_cash: float,
) -> list[Candidate]:
    """Returns at most 10 candidates. Raises ValueError if any symbol < 201 rows."""
```

**Critical:** `price_dfs` passed to `liquidity_filter` must have `["close", "volume"]` columns. `price_dfs` passed to `momentum_filter` and `rank_candidates` must have at least `["close"]`. The scan engine must assemble a single `dict[str, DataFrame]` with both columns and pass it to all three (liquidity uses both; momentum/rank use only close).

**Important:** `rank_candidates` uses `df["close"].iloc[-1]` as `prev_close` (today's close), not yesterday's. The spec says "previous day's close" for sizing recommendations but the implementation uses today's close. Do not change this — it is a tested invariant.

### `strategy/positions.py` — All Pure Functions

```python
# VERIFIED from src/bensdorp1/strategy/positions.py

def update_highest_close(current: float, new_close: float) -> float:
    """max(current, new_close)"""

def compute_trailing_stop(highest_close: float) -> float:
    """highest_close * 0.75"""

def compute_effective_stop(initial_stop: float, trailing_stop: float) -> float:
    """max(initial_stop, trailing_stop)"""

def is_exit_triggered(close: float, effective_stop: float) -> bool:
    """close <= effective_stop"""

def compute_initial_stop(entry_close: float) -> float:
    """entry_close * 0.93  (for reference; used at buy time, read here)"""

def compute_position_size(available_cash: float, prev_close: float) -> int:
    """floor((cash * 0.10) / prev_close); 0 if prev_close <= 0"""
```

### `data/__init__.py` — Public Data API

```python
# VERIFIED from src/bensdorp1/data/__init__.py

from bensdorp1.data.calendar import get_trading_days, is_trading_day, n_trading_days_ago
from bensdorp1.data.constituents import get_constituents, refresh_constituents
from bensdorp1.data.prices import check_price_coverage, update_price_data
```

```python
def get_trading_days(start: date, end: date) -> pd.DatetimeIndex:
    """NYSE trading days between start and end (inclusive), UTC timezone."""

def is_trading_day(dt: date) -> bool:
    """True if dt is a NYSE trading day."""

def n_trading_days_ago(n: int, reference: date | None = None) -> date:
    """Date N NYSE trading days before reference (exclusive of reference)."""

def get_constituents(engine: Engine) -> dict[str, str]:
    """Return {symbol: company_name}; refreshes from Wikipedia if > 7 days stale."""

def update_price_data(
    engine: Engine,
    symbols: list[str],
    start: date | None = None,
    end: date | None = None,
) -> None:
    """Download + upsert. ON CONFLICT DO NOTHING. Both start+end required or neither."""

def check_price_coverage(
    engine: Engine,
    required_days: int = 220,
) -> tuple[int, int]:
    """Return (covered_count, total_count). ^GSPC excluded from count."""
```

### `db/schema.py` — Exact Column Types

```python
# VERIFIED from src/bensdorp1/db/schema.py

scans: Table  # columns:
# id: Integer PK autoincrement
# scan_date: DateTime(timezone=True) UNIQUE NOT NULL
# regime_active: Boolean NOT NULL
# candidate_count: Integer NOT NULL
# exit_trigger_count: Integer NOT NULL
# raw_output: Text nullable   <-- idempotent replay text stored here
# created_at: DateTime(timezone=True) NOT NULL

positions: Table  # columns:
# id: Integer PK autoincrement
# symbol: Text NOT NULL
# entry_date: DateTime(timezone=True) NOT NULL
# entry_close: Float NOT NULL
# shares: Integer NOT NULL
# initial_stop: Float NOT NULL
# highest_close: Float NOT NULL   <-- updated per scan
# trailing_stop: Float NOT NULL   <-- updated per scan
# scan_id: Integer FK scans.id nullable
# closed_at: DateTime(timezone=True) nullable  <-- NULL = open position
# exit_price: Float nullable
# realized_pnl: Float nullable

scan_candidates: Table  # columns:
# id: Integer PK autoincrement
# scan_id: Integer FK scans.id NOT NULL
# symbol: Text NOT NULL
# rank: Integer NOT NULL
# roc200: Float NOT NULL
# close: Float NOT NULL
# suggested_shares: Integer NOT NULL

price_daily: Table  # columns:
# id: Integer PK autoincrement
# symbol: Text NOT NULL
# trade_date: DateTime(timezone=True) NOT NULL
# close: Float NOT NULL
# volume: Integer nullable
# UNIQUE INDEX on (symbol, trade_date)

constituents_cache: Table  # columns:
# id: Integer PK
# symbol: Text UNIQUE NOT NULL
# company_name: Text nullable
# fetched_at: DateTime(timezone=True) NOT NULL
```

**New table to add:**
```python
scan_exit_triggers: Table  # columns:
# id: Integer PK autoincrement
# scan_id: Integer FK scans.id NOT NULL   <-- the scan that first detected the trigger
# position_id: Integer FK positions.id NOT NULL
# reason: Text NOT NULL                    # "Trailing stop" | "Initial stop"
# effective_stop: Float NOT NULL
```

Note: `scan_id` in `scan_exit_triggers` refers to the scan on which the trigger was first detected (which may be a catch-up scan date). "Triggered on" date displayed to the user is derived by querying `scans.scan_date` for that `scan_id`.

### `db/audit.py` — AuditEventType Values

```python
# VERIFIED from src/bensdorp1/db/audit.py

class AuditEventType(StrEnum):
    SCAN_PERFORMED = "scan_performed"   # <-- used at end of scan
    DATA_FETCH_FAILED = "data_fetch_failed"
    CONSTITUENTS_UPDATED = "constituents_updated"
    CONSTITUENTS_DISCREPANCY = "constituents_discrepancy"
    # (17 total; only these 4 are used by scan)

def log_event(
    engine: Engine,
    event_type: AuditEventType,
    symbol: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None: ...
```

**scan_performed payload** (from spec §9.2):
```python
payload = {
    "scan_id": scan_id,           # int
    "scan_date": date.isoformat(), # "2026-05-21"
    "regime": "bull" | "bear",
    "spx_close": float,
    "spx_sma_200": float,
    "constituents_count": int,
    "buy_candidates_count": int,
    "exit_triggers_count": int,
    "constituents_freshness_days": int,
}
```

### `db/engine.py` — Engine Management

```python
# VERIFIED from src/bensdorp1/db/engine.py

def get_engine(path: Path | None = None) -> Engine:
    """Lazy singleton. path only consulted on first call."""

def run_migrations(engine: Engine) -> None:
    """metadata.create_all(checkfirst=True). Picks up scan_exit_triggers automatically."""

def _reset_engine_for_testing(replacement: Engine | None = None) -> None:
    """Test helper. dispose() + replace. CRITICAL on Windows for tmp_path cleanup."""
```

### `db/backup.py` — Backup API

```python
# VERIFIED from src/bensdorp1/db/backup.py

def create_backup(engine: Engine, backups_dir: Path) -> Path:
    """Creates timestamped backup + updates bensdorp1-latest.db. Returns backup path."""
```

Note: `create_backup` takes `backups_dir` as a required argument, unlike `log_event` which takes `engine` only. The scan engine must pass `DATA_DIR / "backups"`.

### `ui/progress.py` — Multi-Step API

```python
# VERIFIED from src/bensdorp1/ui/progress.py

feedback: _FeedbackNamespace  # module-level instance

# Usage for Phase B (2 steps):
with feedback.multi_step(2, console=console) as ms:
    with ms.step("Fetching latest market data", total=len(all_symbols)) as track:
        # track is a TrackContext
        for symbol in all_symbols:
            update_price_data(engine, [symbol], ...)  # or single bulk call
            track.advance(symbol)
    # After block exits, MultiStepContext prints "[1/2] Fetching latest market data... done."
    console.print(Text(f"      Constituents fetched: {len(symbols)}/{len(all_symbols)}"))
    console.print()

    with ms.step("Computing signals") as spinner:
        # spinner is a SpinnerContext (no total=)
        spinner.tick()
        # ... run all filter functions ...
    # After block exits, prints "[2/2] Computing signals... done."
```

### `ui/tables.py` — render_table Signature

```python
# VERIFIED from src/bensdorp1/ui/tables.py

Justify = Literal["left", "right"]

def render_table(
    columns: list[tuple[str, Justify]],
    rows: list[list[str]],
    *,
    console: Console | None = None,
) -> None: ...
```

Example for exit triggers table:
```python
render_table(
    columns=[
        ("Symbol", "left"),
        ("Reason", "left"),
        ("Close", "right"),
        ("Effective stop", "right"),
        ("Days held", "right"),
    ],
    rows=[
        ["AAPL", "Trailing stop", "$178.20", "$179.50", "47 days"],
        ["MSFT", "Initial stop",  "$315.00", "$321.45",  "3 days"],
    ],
    console=console,
)
```

### `ui/styles.py` — Formatters

```python
# VERIFIED from src/bensdorp1/ui/styles.py

def format_price(value: float) -> str: ...    # "$1,432.50"
def format_pct(value: float) -> str: ...      # "+185.3%"
def format_volume(value: int) -> str: ...     # "52,341,200"
def format_days(n: int) -> str: ...           # "47 days", "1 day"
def format_date(d: date) -> str: ...          # "2026-05-21"
def format_timezone_pair(dt: datetime) -> str: ...  # "16:30 ET (21:30 Lisbon)"
def render_kv_block(data: dict[str, str], console: Console, indent: str = "") -> None: ...
```

### `config.py` — Constants

```python
# VERIFIED from src/bensdorp1/config.py

MARKET_TZ: ZoneInfo = ZoneInfo("America/New_York")
USER_TZ: ZoneInfo = ZoneInfo(os.environ.get("BENSDORP1_USER_TZ", "Europe/Lisbon"))
DATA_DIR: Path = Path(os.environ.get("BENSDORP1_HOME", str(Path.home() / "bensdorp1")))
```

---

## Common Pitfalls

### Pitfall 1: Price DataFrame Column Names Are Lowercase

**What goes wrong:** `price_daily` stores `close` (lowercase). Filter functions expect `df["close"]` and `df["volume"]`. yfinance returns `df["Close"]` (capitalized). If the DataFrame is assembled directly from yfinance output without the prices.py pipeline, filter functions will raise `KeyError`.

**Why it happens:** The prices.py pipeline normalizes column names; the schema stores lowercase. Direct yfinance fetch bypasses this.

**How to avoid:** Always load price DataFrames from `price_daily` (the DB), not from yfinance directly in the scan engine. The price_daily table has lowercase `close` and `volume` columns.

**Warning signs:** `KeyError: 'close'` in filter functions during test.

### Pitfall 2: price_daily Rows Are UTC DatetimesZ, Not date Objects

**What goes wrong:** `price_daily.trade_date` is stored as `DateTime(timezone=True)` — a UTC-aware datetime. When assembling DataFrames, comparing dates requires timezone awareness or normalization.

**Why it happens:** SQLAlchemy returns timezone-aware datetime objects from UTC columns.

**How to avoid:** When filtering `price_daily` for a specific date, use range queries:
```python
from datetime import datetime, UTC
start_of_day = datetime(d.year, d.month, d.day, tzinfo=UTC)
end_of_day = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)
```
Or normalize to date and use `.date()` on the fetched datetime.

### Pitfall 3: scans.scan_date Is a DateTime, Not a date

**What goes wrong:** `scans.scan_date` is `DateTime(timezone=True)`. Idempotency check must compare datetimes, not dates. Querying `WHERE scan_date = today_as_date` will silently fail to match.

**Why it happens:** SQLAlchemy DateTime column stores midnight UTC datetimes. Date-only comparison may miss due to type mismatch.

**How to avoid:** Store `scan_date` as midnight UTC for the ET trading date (example in Pattern 5 above). Query with an explicit range or with the same midnight-UTC datetime used for insertion.

### Pitfall 4: MultiStepContext.step() Prints the Step Header Twice

**What goes wrong:** `MultiStepContext.step()` prints `[N/TOTAL] description` at the START of the `with` block (line 286 in progress.py). If the caller also prints it manually, the header appears twice.

**Why it happens:** The `MultiStepContext` API prints the header automatically when `step()` enters.

**How to avoid:** Never manually print `[N/TOTAL] description` before a `ms.step()` call. The context manager handles the header; the caller only prints detail lines AFTER the block exits.

### Pitfall 5: engine Singleton Is Cached — Tests Must Reset It

**What goes wrong:** `get_engine()` caches the engine globally. A test that calls `get_engine()` leaves state that bleeds into the next test.

**Why it happens:** Thread-safety singleton with double-checked locking in `engine.py`.

**How to avoid:** In tests, use the `db_engine` fixture from `tests/conftest.py`, which calls `_reset_engine_for_testing(engine)` before yield and `_reset_engine_for_testing()` in teardown. Never call `get_engine()` directly in tests — pass the fixture engine as an argument or patch `bensdorp1.commands.scan.get_engine`.

### Pitfall 6: update_price_data Needs Both start and end, or Neither

**What goes wrong:** `update_price_data(engine, symbols, start=today-10d)` without `end` raises `ValueError("requires both start and end, or neither")`.

**Why it happens:** Explicit validation in prices.py line 237–239.

**How to avoid:** Always pass both: `update_price_data(engine, symbols, start=date.today() - timedelta(days=10), end=date.today())`.

### Pitfall 7: Windows tmp_path Cleanup Requires engine.dispose()

**What goes wrong:** On Windows, the SQLite file remains locked after the test if the engine is not disposed. pytest's `tmp_path` cleanup fails with `[WinError 32] The process cannot access the file`.

**Why it happens:** SQLAlchemy connection pool holds the file handle open.

**How to avoid:** Use the existing `db_engine` fixture which calls `_reset_engine_for_testing()` (which calls `engine.dispose()`) in teardown. Never create engines in tests without this teardown.

### Pitfall 8: Catch-Up Scanning Skips Triggered Positions

**What goes wrong:** During catch-up, if a position was triggered on day 2 of 5 missed days, days 3–5 should NOT update its `highest_close`/`trailing_stop` (D-07: freeze on trigger). If the loop processes all days unconditionally, the stop may un-trigger.

**Why it happens:** Simple day iteration without per-position trigger state tracking.

**How to avoid:** Maintain a `triggered_position_ids: set[int]` set. On each day, skip positions already in this set. When a position triggers, add it to the set and insert into `scan_exit_triggers`.

---

## Output Layout Reference (from spec §7.2)

### Exact Section Order

```
================================================================
Scan for YYYY-MM-DD
================================================================

Market regime
-------------
S&P 500 close:           5,234.50
S&P 500 SMA 200:         4,987.20
Regime:                  Bull market (close above SMA 200)

Exit triggers
-------------
Symbol  Reason            Close     Effective stop  Days held
------  ----------------  --------  --------------  ---------
AAPL    Trailing stop      $178.20         $179.50    47 days
MSFT    Initial stop       $315.00         $321.45     3 days

Both exit triggers will execute at the next market open (YYYY-MM-DD).
Confirm sells with `bensdorp1 sell SYMBOL PRICE` after execution.

[--- IF pending triggers exist ---]
Pending exit triggers from previous scans
-----------------------------------------
The following exit triggers were generated in previous scans and have not
yet been confirmed as closed:

Symbol  Triggered on   Reason           Original stop
------  -------------  ---------------  -------------
AAPL    2026-05-18     Trailing stop          $179.50

Run `bensdorp1 sell AAPL PRICE` to confirm the exit.
[--- END IF ---]

[--- IF bull regime ---]
Buy candidates (top 10)
-----------------------
Rank  Symbol         Close    ROC 200d  Volume (avg 20d)
   1  NVDA         $432.50   +185.3%        52,341,200
   ...

Buy candidates affordable (cash: $42,500.00)
--------------------------------------------
Rank  Symbol         Close    ROC 200d  Shares to buy
   1  NVDA         $432.50   +185.3%               98
   ...
[--- END IF ---]

System notes
------------
No catch-up actions needed.
Constituents list verified successfully.
```

### Regime Section Values

- `S&P 500 close`: `format_price(spx_today_close)` — note: no dollar sign in the spec example (`5,234.50`), but `format_price` returns `$5,234.50`. Check spec §7.2 carefully: it shows `5,234.50` without `$`. **Resolution:** The spec example uses plain number format for index values; use `f"{spx_close:,.2f}"` (no `$`) for SPX close and SMA. Use `format_price` only for USD stock prices.

- `Regime`: `"Bull market (close above SMA 200)"` or `"Bear market (close below SMA 200)"` — exact sentence case per spec.

### Exit Triggers — Reason Values

From D-05 and spec §7.2:
- `"Trailing stop"` — when `trailing_stop > initial_stop` (trailing stop is the binding constraint)
- `"Initial stop"` — when `initial_stop >= trailing_stop` (initial stop is the binding constraint)

The reason is derived from which stop is the effective stop:
```python
effective = compute_effective_stop(initial_stop, trailing_stop)
reason = "Trailing stop" if trailing_stop >= initial_stop else "Initial stop"
```

### Days Held Calculation

```python
# entry_date is stored as DateTime(timezone=True) in positions table
entry_date_utc = position_row.entry_date  # datetime
today_utc = datetime.now(UTC).date()
entry_date_only = entry_date_utc.date()
days_held = (today_utc - entry_date_only).days
```

Use `format_days(days_held)` → `"47 days"` / `"1 day"`.

---

## Cash Available for Scan

The scan must read `available_cash` from the `config` table:

```python
from sqlalchemy import select
from bensdorp1.db.schema import config as config_table

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

This value is passed to `rank_candidates(price_dfs, available_cash)` and used for the affordable table header `"Buy candidates affordable (cash: $X)"`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_commands/test_scan.py -x` |
| Full suite command | `uv run pytest --cov=bensdorp1 --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CMD-03 (time gate) | Before 16:30 ET → exit 1 + message | integration | `uv run pytest tests/test_commands/test_scan.py::test_time_gate -x` | Wave 0 |
| CMD-03 (idempotent) | Same-day second call shows raw_output, no re-fetch | integration | `uv run pytest tests/test_commands/test_scan.py::test_idempotent_same_day -x` | Wave 0 |
| CMD-03 (--force) | Re-fetches and overwrites; single scans row | integration | `uv run pytest tests/test_commands/test_scan.py::test_force_reruns_scan -x` | Wave 0 |
| CMD-03 (non-trading day) | Info message + last raw_output | integration | `uv run pytest tests/test_commands/test_scan.py::test_non_trading_day -x` | Wave 0 |
| CMD-03 (happy path bull) | Full output: regime + exit triggers + both candidate tables | integration | `uv run pytest tests/test_commands/test_scan.py::test_happy_path_bull -x` | Wave 0 |
| STRAT-01 (bear regime) | No buy candidates tables in output | integration | `uv run pytest tests/test_commands/test_scan.py::test_bearish_regime -x` | Wave 0 |
| D-08/D-09 (catch-up) | Correct highest_close/trailing_stop per missed day | unit | `uv run pytest tests/test_commands/test_scan.py::test_catchup_stop_updates -x` | Wave 0 |
| D-07 (stop freeze) | No updates after trigger insertion | unit | `uv run pytest tests/test_commands/test_scan.py::test_stop_freeze_after_trigger -x` | Wave 0 |
| D-09 (missed-day trigger) | scan_exit_triggers row has correct date | unit | `uv run pytest tests/test_commands/test_scan.py::test_exit_trigger_on_missed_day -x` | Wave 0 |
| D-05 (schema) | scan_exit_triggers table created by run_migrations | unit | `uv run pytest tests/test_commands/test_scan.py::test_schema_has_exit_triggers_table -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_commands/test_scan.py -x`
- **Per wave merge:** `uv run pytest --cov=bensdorp1 --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_commands/test_scan.py` — all scan test scenarios (file does not yet exist)
- [ ] `tests/test_commands/__init__.py` — EXISTS (created in Phase 6)
- [ ] `tests/conftest.py` — EXISTS with `db_engine` and `record_console` fixtures

*(conftest.py and `__init__.py` are already present from Phase 6; no additional fixtures needed beyond the existing `db_engine`)*

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | Package management + test runner | Already confirmed running | >= 0.7 | — |
| SQLite | DB backend | Built into Python | 3.x | — |
| NYSE calendar (pandas-market-calendars) | Trading day checks | Installed in Phase 3 | >= 5.3.2 | — |
| yfinance | Price data fetch | Installed in Phase 3 | >= 1.3.0 | — |

No missing dependencies. All tools were verified in prior phases.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | CLI is single-user, no auth |
| V3 Session Management | no | Stateless CLI, no sessions |
| V4 Access Control | no | Single-user tool |
| V5 Input Validation | yes | `--force` is a boolean flag (Typer handles); scan_date is computed internally, not from user input |
| V6 Cryptography | no | No secrets, no encryption |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via symbol strings | Tampering | SQLAlchemy parameterized queries — all DB writes use bound parameters; never string interpolation |
| Rich markup injection in rendered output | Tampering | All user-sourced strings (symbol names from DB, company names) passed through `Text(str)` or `markup=False` |
| Path traversal in DATA_DIR | Tampering | `DATA_DIR` from env var or default; backup path uses `DATA_DIR / "backups"` (Path join, not string concat) |
| Large scan output in raw_output column | Denial of service | Text column in SQLite; no practical limit for ~100-line output strings |

---

## Assumptions Log

All claims in this research were verified directly from the codebase source files. No web searches were needed. No assumed claims.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | — | — | — |

**All claims in this research were verified or cited from the actual source files — no user confirmation needed.**

---

## Open Questions (RESOLVED)

1. **`run_scan` console capture strategy**
   - What we know: Phase 5 D-06 established `console: Console | None = None` pattern; tests pass `Console(record=True)`.
   - What's unclear: Does `run_scan` use its `console` param for progress output AND capture the rendered result via a second internal `Console(record=True)`, or does it use a single `Console(record=True)` passed in for both progress and capture?
   - Recommendation: Use two consoles — one passed in (or defaulting to `Console()`) for progress display to the terminal, and one internal `Console(record=True)` for rendering the scan output to a string. This matches the separation between "live progress" (transient) and "final output" (persistent string).

2. **Phase B progress: one bulk call vs per-symbol**
   - What we know: `update_price_data` does bulk download + per-symbol retry. Calling it once for all 503 symbols minimizes network overhead.
   - What's unclear: How to show per-symbol progress when the single bulk call has no per-symbol callback.
   - Recommendation: Call `update_price_data(engine, symbols, start, end)` once (bulk, fast), then call `track.advance(symbol)` for each symbol after the bulk call completes. This matches D-13: "iterate over all symbols regardless of how many had new data."

3. **scan_exit_triggers.scan_id semantics for catch-up**
   - What we know: During catch-up, triggers detected on missed days need to store the scan_date of the missed day, not today's scan.
   - What's unclear: Should a catch-up trigger create a synthetic scans row for the missed day, or use today's scan_id with a separate `trigger_date` column?
   - Recommendation: Use today's scan_id (the scan currently being run) for the `scan_exit_triggers.scan_id` FK. The display shows "Triggered on" = the missed day's date, which is stored as a separate field or computed from the audit log. This avoids creating synthetic scan rows. **If the planner wants per-day accuracy:** add a `triggered_date` column to `scan_exit_triggers` (a `DateTime(timezone=True)` storing the missed day's date).

---

## Sources

### Primary (HIGH confidence)
- `src/bensdorp1/strategy/screening.py` — exact signatures and behavior of all 4 filter functions
- `src/bensdorp1/strategy/positions.py` — exact signatures for all stop arithmetic functions
- `src/bensdorp1/data/prices.py` — `update_price_data` signature, ON CONFLICT behavior, ^GSPC inclusion
- `src/bensdorp1/data/calendar.py` — `get_trading_days`, `is_trading_day`, `n_trading_days_ago` signatures
- `src/bensdorp1/data/constituents.py` — `get_constituents` behavior (stale TTL, never raises on network error)
- `src/bensdorp1/db/schema.py` — exact column names, types, constraints for all tables
- `src/bensdorp1/db/audit.py` — `AuditEventType` enum values, `log_event` signature
- `src/bensdorp1/db/engine.py` — `get_engine`, `run_migrations`, `_reset_engine_for_testing` APIs
- `src/bensdorp1/db/backup.py` — `create_backup` signature (requires `backups_dir` param)
- `src/bensdorp1/ui/progress.py` — `feedback.multi_step`, `MultiStepContext.step`, `TrackContext.advance` APIs
- `src/bensdorp1/ui/tables.py` — `render_table` signature
- `src/bensdorp1/ui/styles.py` — all formatters, `render_kv_block` signature
- `src/bensdorp1/ui/messages.py` — `print_error`, `print_info`, `print_warning` signatures
- `src/bensdorp1/commands/init.py` — Phase 6 implementation reference for console ownership, multi-step pattern, separator constant
- `tests/test_commands/test_init.py` — Phase 6 CliRunner test pattern with module-level patches
- `tests/conftest.py` — `db_engine` fixture, `_reset_engine_for_testing` teardown pattern
- `.planning/Bensdorp_1.md` §7.2, §8.1, §8.2, §8.5, §8.6, §9.2 — authoritative spec for output layout and behavior
- `.planning/phases/07-scan-command/07-CONTEXT.md` — all locked decisions D-01 through D-24

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — requirement IDs and traceability (supplementary to spec)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages were already installed and verified in prior phases; no new deps
- Architecture: HIGH — all function signatures verified directly from source; patterns verified from Phase 6
- Pitfalls: HIGH — derived from actual implementation constraints and Windows-specific behaviors already encountered in Phase 6
- Output layout: HIGH — verified against spec §7.2 and context decisions verbatim

**Research date:** 2026-05-24
**Valid until:** 2026-07-24 (stable stack; no external API changes expected)
