# Architecture Patterns

**Domain:** Python CLI trading signal tool (single-user, SQLite, yfinance, pandas strategy)
**Researched:** 2026-05-23
**Confidence:** HIGH (all major patterns verified against official docs and authoritative sources)

---

## Recommended Architecture

```
bensdorp1/
  src/
    bensdorp1/
      __init__.py
      main.py              # Typer app assembly, @app.callback, ctx.obj init
      cli/                 # Command handlers — thin, call services, render output
        scan.py
        buy.py
        sell.py
        portfolio.py
        init_.py
        cash.py
        history.py
        last.py
        fix.py
        detail.py
        config_.py
        audit.py
        status.py
        refresh.py
        restore.py
        validate.py
        help_.py
      services/            # Business logic — no I/O, no Typer, pure orchestration
        scan_service.py
        position_service.py
        cash_service.py
        audit_service.py
        backup_service.py
        catchup_service.py
        constituent_service.py
      strategy/            # Pure functions — no DB, no network, fully deterministic
        filters.py         # regime_filter(), liquidity_filter(), momentum_filter()
        ranking.py         # rank_by_roc200(), top_n_candidates()
        stops.py           # initial_stop(), trailing_stop(), effective_stop()
        sizing.py          # position_size_shares()
        indicators.py      # sma(), roc(), highest_close_since()
      data/                # External data access — all yfinance and web fetching
        prices.py          # PriceStore: bulk download, incremental update, cache read
        constituents.py    # ConstituentFetcher: Wikipedia scrape, Slickcharts cross-check
        calendar.py        # CalendarService: NYSE schedule, trading day arithmetic
      db/                  # Database layer — schema, queries, engine factory
        engine.py          # create_engine(), PRAGMA event listeners, NullPool
        schema.py          # Table definitions (SQLAlchemy Core Table objects)
        migrations.py      # Schema creation and future-proof schema checks
        queries/
          positions.py
          prices.py
          audit.py
          constituents.py
          scans.py
      ui/                  # Output rendering — Rich tables, spinners, progress bars
        tables.py
        spinner.py
        progress.py
        format.py          # number/date/currency formatters
      models.py            # Pydantic v2 models: ScanResult, Position, Candidate, etc.
      config.py            # Settings from env vars (BENSDORP1_HOME, timezone)
  tests/
    unit/
      strategy/
      services/
      data/
    integration/
    snapshots/             # Output snapshot files for command rendering tests
```

**Why src layout:** The src layout prevents accidental import of the uninstalled package during test runs. Tests always import the installed package via `pip install -e .`, which guarantees that what you test is what ships. This matters for a project with strict mypy and >90% coverage requirements.

---

## Component Boundaries

| Component | Responsibility | Communicates With | What It Must NOT Do |
|-----------|---------------|-------------------|---------------------|
| `cli/` | Parse CLI args, call one service, render output | `services/`, `ui/`, `models.py` | Contain business logic; touch DB directly |
| `services/` | Orchestrate operations, enforce invariants | `db/`, `data/`, `strategy/`, `models.py` | Render output; know about Typer |
| `strategy/` | Pure calculations on pandas Series/DataFrames | Nothing — only stdlib, pandas, numpy | I/O of any kind; side effects |
| `data/` | Fetch and cache external data | `db/` (for price cache), network | Strategy calculations |
| `db/` | SQL queries, schema, engine | sqlite3 (via SQLAlchemy Core) | Business logic |
| `ui/` | Format and print output | stdlib only | Data fetching or computation |
| `models.py` | Validate and type data boundaries | Pydantic v2 | DB queries or network |
| `config.py` | Read environment and paths | stdlib only | Side effects on import |

The golden rule: **cli calls services; services call strategy and db; strategy calls nothing.**

---

## Data Flow

### Scan Flow (the hot path, runs daily)

```
User: bensdorp1 scan
     |
     v
cli/scan.py
  scan_command(ctx)
     |
     v
services/scan_service.py
  run_scan(engine, config)
     |
     +---> data/calendar.py
     |       CalendarService.last_trading_day()
     |       Returns: date
     |
     +---> data/prices.py
     |       PriceStore.ensure_fresh(tickers, as_of_date)
     |         [If cache stale] --> yfinance.download(tickers, start=last_cached+1, end=today)
     |         [Writes to db] --> db/queries/prices.py.upsert_prices()
     |       Returns: None (cache guaranteed fresh after call)
     |
     +---> db/queries/prices.py
     |       load_price_matrix(tickers, lookback=220)
     |       Returns: pd.DataFrame indexed by date, columns=tickers (adjusted close)
     |
     +---> strategy/filters.py
     |       regime_ok  = regime_filter(spx_series)
     |       liquid_tickers = liquidity_filter(volume_df, top_pct=0.25)
     |       momentum_ok = momentum_filter(close_df, lookback=200)
     |       Returns: bool, list[str], pd.Series[bool]
     |
     +---> strategy/ranking.py  [only if regime_ok]
     |       candidates = rank_by_roc200(close_df[liquid & momentum])
     |       top10 = top_n_candidates(candidates, n=10)
     |       Returns: list[Candidate]
     |
     +---> db/queries/positions.py
     |       open_positions = load_open_positions(engine)
     |       Returns: list[Position]
     |
     +---> strategy/stops.py
     |       For each position:
     |         eff_stop = effective_stop(position, close_df[symbol])
     |         triggered = close_series[-1] <= eff_stop
     |       Returns: list[StopTrigger]
     |
     +---> db/queries/scans.py
     |       save_scan_result(engine, result)   [begins transaction]
     |       Returns: ScanResult.id
     |
     +---> services/audit_service.py
     |       log_event(engine, "SCAN_COMPLETED", ...)
     |
     +---> services/backup_service.py
             create_backup(engine, config.backup_dir)
     |
     v
ui/tables.py
  render_scan_result(scan_result)
     Prints: exit triggers table + buy candidates table
```

### Init Flow (first run, heavy download)

```
User: bensdorp1 init
     |
     v
cli/init_.py
     |
     +---> db/engine.py: create_engine() + apply_schema()
     +---> services/constituent_service.py: fetch_and_store(engine)
     |       data/constituents.py: fetch_wikipedia() → cross_check_slickcharts()
     |       db/queries/constituents.py: save_constituents()
     +---> data/prices.py: PriceStore.bulk_download(tickers, days=220)
     |       [Chunked: 80 tickers/batch, sequential, with retry]
     |       [Progress bar shown — download takes 30s+]
     |       db/queries/prices.py: bulk_upsert_prices()
     +---> services/cash_service.py: set_initial_cash(engine, amount)
     +---> services/audit_service.py: log_event("INIT_COMPLETED")
     +---> services/backup_service.py: create_backup()
```

### Incremental Update Flow (daily, after first init)

```
PriceStore.ensure_fresh(tickers, as_of_date):
  last_date = db/queries/prices.py.get_max_price_date()
  if last_date == as_of_date:
      return  # cache already fresh
  missing_tickers, missing_days = identify_gaps(tickers, last_date, as_of_date)
  new_data = yfinance.download(missing_tickers, start=last_date+1, end=as_of_date+1)
  db/queries/prices.py.upsert_prices(new_data)
```

---

## SQLite-Specific Considerations

### Engine Factory

```python
# db/engine.py
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool

def make_engine(db_path: Path) -> Engine:
    engine = create_engine(
        f"sqlite:///{db_path}",
        poolclass=NullPool,   # single-user CLI: no pool needed, no connection reuse
    )
    event.listen(engine, "connect", _configure_connection)
    return engine

def _configure_connection(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    # WAL mode: persists — set once on first connect, ignored thereafter
    cursor.execute("PRAGMA journal_mode=WAL")
    # Foreign key enforcement: must be set per-connection (not persisted)
    cursor.execute("PRAGMA foreign_keys=ON")
    # NORMAL sync: safe against OS crash, faster than FULL — appropriate for backups
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Larger cache: 64MB for holding 220 days of 503 tickers in working set
    cursor.execute("PRAGMA cache_size=-65536")
    # Temp tables in memory
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()
```

**Why NullPool:** This is a single-user CLI. Each command runs, does its work, and exits. There is no benefit to keeping a connection pool alive between commands. NullPool eliminates all pool management overhead and avoids any stale-connection edge cases.

**Why WAL mode:** WAL allows reads and writes to proceed concurrently without blocking. More importantly, WAL gives significantly better write performance for the incremental price upserts, and the auto-checkpoint at 1000 pages keeps the WAL file bounded without manual intervention.

**Why NORMAL synchronous:** With WAL mode, `synchronous=NORMAL` protects against data loss from OS crashes while being faster than FULL. Since the backup system is the durability layer for application errors, this is the right tradeoff.

### Transaction Pattern

Use `engine.begin()` for all state-changing operations (the "begin once" pattern from SQLAlchemy 2.0 docs):

```python
# services/position_service.py
def record_buy(engine: Engine, buy: BuyConfirmation) -> Position:
    with engine.begin() as conn:
        pos_id = conn.execute(positions.insert(), {...}).inserted_primary_key[0]
        conn.execute(audit_log.insert(), {...})
        # auto-commits on exit; auto-rollbacks on exception
    backup_service.create_backup(engine, config.backup_dir)
    return load_position(engine, pos_id)
```

**Rule:** Backup happens OUTSIDE the transaction, after commit. Backup reflects committed state only.

### Schema Design

```sql
-- db/schema.py defines these as SQLAlchemy Core Table objects

prices (
  ticker      TEXT NOT NULL,
  trade_date  TEXT NOT NULL,   -- ISO date, Eastern Time
  close       REAL NOT NULL,
  volume      REAL NOT NULL,
  PRIMARY KEY (ticker, trade_date)
)

positions (
  id              INTEGER PRIMARY KEY,
  symbol          TEXT NOT NULL,
  status          TEXT NOT NULL,   -- 'open' | 'closed'
  entry_date      TEXT NOT NULL,
  entry_close     REAL NOT NULL,
  shares          INTEGER NOT NULL,
  initial_stop    REAL NOT NULL,
  highest_close   REAL NOT NULL,   -- updated daily
  ...
)

constituents (
  ticker          TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  fetched_at      TEXT NOT NULL    -- ISO datetime
)

scan_results (
  id              INTEGER PRIMARY KEY,
  scan_date       TEXT NOT NULL,
  regime_ok       INTEGER NOT NULL,  -- 0 | 1
  result_json     TEXT NOT NULL,     -- JSON blob for exit triggers + candidates
  created_at      TEXT NOT NULL
)

audit_log (
  id              INTEGER PRIMARY KEY,
  event_type      TEXT NOT NULL,   -- one of 17 defined types
  occurred_at     TEXT NOT NULL,
  symbol          TEXT,
  details_json    TEXT NOT NULL
)

app_state (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
  -- holds: available_cash, last_scan_date, schema_version, constituents_fetched_at
)
```

**Dates as ISO TEXT:** Store all dates as `TEXT` in ISO 8601 format (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`). SQLite has no native date type. TEXT sorts lexicographically which matches chronological order. This makes range queries (`WHERE trade_date BETWEEN x AND y`) work correctly without conversion.

**The prices table is the largest table** (~503 tickers × 220 days = 110,660 rows at init). The primary key index on `(ticker, trade_date)` is sufficient for all access patterns: single-ticker history, all-tickers-on-a-date, and range queries.

### SQLite Backup

Access the raw DBAPI connection from the SQLAlchemy engine for backup:

```python
# services/backup_service.py
def create_backup(engine: Engine, backup_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_path = backup_dir / f"bensdorp1_{timestamp}.db"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # engine.raw_connection() returns a bare DBAPI sqlite3.Connection
    src_conn = engine.raw_connection()
    try:
        dst_conn = sqlite3.connect(str(backup_path))
        try:
            # pages=-1: copy entire DB in one step (fine for single-user CLI)
            # No concurrent writers, so no need for incremental page copies
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    return backup_path
```

**Never auto-delete backups** (per spec). The backup directory grows unboundedly — this is intentional for a single user with years of operation. On modern systems, each backup is ~5-20MB; 365 backups/year is 2-7GB — acceptable for a personal tool.

**Why pages=-1 (full copy in one step):** In a single-user CLI, there are no concurrent writers during backup. Using pages=-1 copies the entire database atomically in one operation, which is simpler and faster than incremental page copying. The online backup API still holds only a read lock, not blocking any readers.

---

## yfinance Data Fetching Architecture

### Separation of Concerns

`data/prices.py` is the only file that calls yfinance. It exposes a clean interface to services:

```python
class PriceStore:
    def bulk_download(self, tickers: list[str], days: int) -> None: ...
    def ensure_fresh(self, tickers: list[str], as_of: date) -> None: ...
    def load_matrix(self, tickers: list[str], lookback: int) -> pd.DataFrame: ...
```

Services never call yfinance directly. This boundary makes the data layer swappable and makes services testable by injecting a fake PriceStore.

### Bulk Initial Download

```python
def bulk_download(self, tickers: list[str], days: int) -> None:
    # 220 trading days ≈ 312 calendar days to be safe with holidays
    start = (date.today() - timedelta(days=320)).isoformat()
    end = date.today().isoformat()

    CHUNK_SIZE = 80  # empirically safe; avoids YFRateLimitError at ~100+
    for i in range(0, len(tickers), CHUNK_SIZE):
        chunk = tickers[i:i + CHUNK_SIZE]
        df = yfinance.download(
            chunk,
            start=start,
            end=end,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        self._upsert_chunk(df, chunk)
        if i + CHUNK_SIZE < len(tickers):
            time.sleep(2)  # conservative delay between chunks
```

**Chunk size 80:** Community reports (GitHub issue #2614) show that 80 tickers/batch is the empirical safe zone. Larger batches trigger 429 rate-limiting. Sequential chunks with a 2-second sleep are more reliable than concurrent chunked requests.

**Retry strategy:** Wrap the yfinance call with a simple retry decorator:
- On `YFRateLimitError`: exponential backoff starting at 10s, max 3 retries
- On network timeout: retry once with 5s delay
- After 3 failures: raise with a clear message for the progress bar to surface

### Incremental Daily Update

```python
def ensure_fresh(self, tickers: list[str], as_of: date) -> None:
    last_date = self._get_max_price_date()   # from db
    if last_date is not None and last_date >= as_of:
        return  # already fresh — most common case for daily scan

    fetch_start = (last_date + timedelta(days=1)) if last_date else (as_of - timedelta(days=320))
    fetch_end = as_of + timedelta(days=1)  # yfinance end is exclusive

    df = yfinance.download(
        tickers,
        start=fetch_start.isoformat(),
        end=fetch_end.isoformat(),
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    self._upsert_prices(df)
```

For daily updates, all 503 tickers in a single call is fine — the date range is short (1-7 days), so the payload is tiny. Rate limiting is a concern only for the bulk initial download.

### Price Matrix for Calculations

Strategy functions receive a clean DataFrame, not raw yfinance output:

```python
def load_matrix(self, tickers: list[str], lookback: int) -> pd.DataFrame:
    """
    Returns: DataFrame with DatetimeIndex (trading days), columns=tickers.
    Values: adjusted close. Sorted ascending by date. No NaNs for tickers
    with sufficient history; tickers with insufficient history are excluded.
    """
    rows = conn.execute(
        select(prices.c.trade_date, prices.c.ticker, prices.c.close)
        .where(prices.c.ticker.in_(tickers))
        .where(prices.c.trade_date >= cutoff_date)
        .order_by(prices.c.trade_date)
    ).fetchall()
    df = pd.DataFrame(rows, columns=["date", "ticker", "close"])
    return df.pivot(index="date", columns="ticker", values="close")
```

The pivot produces a standard wide DataFrame that strategy functions expect. Missing data handling (stocks with fewer than 220 days of history) is filtered before passing to strategy.

### The 220-Day History Requirement

The 220-day figure comes from needing 200 trading days for the longest calculation window (SMA 200, ROC 200) plus a buffer:

```python
# data/calendar.py
def trading_days_lookback(as_of: date, n_trading_days: int) -> date:
    """Return the calendar date that is exactly n_trading_days before as_of."""
    nyse = mcal.get_calendar("NYSE")
    # Over-request to handle holidays: n_trading_days * 1.5 calendar days is safe
    start = as_of - timedelta(days=int(n_trading_days * 1.5))
    schedule = nyse.valid_days(start_date=start, end_date=as_of)
    if len(schedule) < n_trading_days:
        raise ValueError(f"Insufficient trading history: need {n_trading_days} days")
    return schedule[-n_trading_days].date()
```

**Key insight:** Always fetch 220 trading days from `pandas_market_calendars`, not 220 calendar days. NYSE has ~252 trading days/year, so 200 trading days ≈ 280 calendar days. Fetching 220 trading days requires querying roughly 308 calendar days. The 320-calendar-day buffer in the bulk download is intentionally generous.

---

## Strategy Layer: Pure Function Design

All strategy calculations live in `strategy/` as module-level functions accepting pandas Series or DataFrames and returning pandas objects or scalars. No I/O. No global state. No class instances required.

```python
# strategy/indicators.py
def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average. Returns NaN for first (window-1) elements."""
    return series.rolling(window=window).mean()

def roc(series: pd.Series, lookback: int) -> float:
    """Rate of change: (current / price_n_periods_ago) - 1."""
    if len(series) < lookback + 1:
        return float("nan")
    return (series.iloc[-1] / series.iloc[-(lookback + 1)]) - 1.0

def highest_close_since(series: pd.Series, since_idx: int) -> float:
    """Highest close from since_idx to end (inclusive)."""
    return series.iloc[since_idx:].max()

# strategy/stops.py
def initial_stop(entry_close: float) -> float:
    return entry_close * 0.93

def trailing_stop(highest_close: float) -> float:
    return highest_close * 0.75

def effective_stop(init_stop: float, trail_stop: float) -> float:
    return max(init_stop, trail_stop)

def is_stop_triggered(close: float, eff_stop: float) -> bool:
    return close <= eff_stop

# strategy/filters.py
def regime_filter(spx_close: pd.Series) -> bool:
    """True if SPX close > SMA 200."""
    if len(spx_close) < 200:
        return False
    return bool(spx_close.iloc[-1] > sma(spx_close, 200).iloc[-1])

def momentum_filter(close_series: pd.Series, lookback: int = 200) -> bool:
    """True if current close > close lookback trading days ago."""
    if len(close_series) < lookback + 1:
        return False
    return bool(close_series.iloc[-1] > close_series.iloc[-(lookback + 1)])

def liquidity_filter(
    volume_df: pd.DataFrame, top_pct: float = 0.25, window: int = 20
) -> list[str]:
    """Return tickers in the top pct by average volume over the last window days."""
    avg_vol = volume_df.iloc[-window:].mean()
    threshold = avg_vol.quantile(1.0 - top_pct)
    return list(avg_vol[avg_vol >= threshold].index)
```

**Why this shape:**
- Functions take Series/DataFrame + scalars, return Series/scalar/list. No objects.
- All inputs are immutable (pandas operations return new objects).
- Every function is independently testable with synthetic data.
- Hypothesis can generate edge-case Series (all NaN, single element, monotonic) to test invariants.

**Testable invariants for Hypothesis:**
- `effective_stop(i, t)` is always >= `initial_stop(entry_close)` — effective stop never falls below initial
- `trailing_stop(h1) >= trailing_stop(h2)` when `h1 >= h2` — monotonic
- `regime_filter(spx)` returns False when `len(spx) < 200` — never errors on insufficient data
- `liquidity_filter(df, pct)` returns exactly `ceil(n_tickers * pct)` tickers (approximately)

---

## Shared Application Context (Typer Pattern)

```python
# main.py
import typer
from bensdorp1.db.engine import make_engine
from bensdorp1.config import Settings

app = typer.Typer(invoke_without_command=True)

# Register all command groups
from bensdorp1.cli import scan, buy, sell, portfolio  # etc.
app.command()(scan.scan_command)
app.command()(buy.buy_command)
# ...

class AppContext:
    def __init__(self):
        self.settings = Settings.from_env()
        self.engine = make_engine(self.settings.db_path)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    ctx.ensure_object(AppContext)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

# Each command accesses context:
# cli/scan.py
def scan_command(ctx: typer.Context, force: bool = False):
    app_ctx: AppContext = ctx.obj
    result = scan_service.run_scan(app_ctx.engine, app_ctx.settings, force=force)
    ui.tables.render_scan_result(result)
```

**Why ctx.obj over global variables:** A module-level global engine would be initialized at import time, breaking tests that need to inject a different (in-memory) engine. With ctx.obj, commands get the engine injected, and tests construct AppContext directly with a test engine.

**Why not a DI framework (dependency-injector, etc.):** This project has 17 commands and one dependency (the engine/settings). A full DI container is overkill. ctx.obj + dataclass is sufficient and avoids adding a framework dependency for a maintenance-only project.

---

## Suggested Build Order (Phase Dependencies)

```
Phase 1: Project skeleton
  - pyproject.toml (uv), src/ layout, ruff config, mypy strict, CI yml
  - config.py, models.py stubs
  GATE: `uv run bensdorp1 --help` shows version

Phase 2: Database layer
  - db/engine.py (NullPool, PRAGMA events, WAL mode)
  - db/schema.py (all tables as Core Table objects)
  - db/migrations.py (create_all + schema_version check)
  - db/queries/ (all query functions, no business logic)
  GATE: `init` creates DB with correct schema; round-trip test passes

Phase 3: Data layer (no strategy yet)
  - data/calendar.py (NYSE, trading_days_lookback, is_trading_day)
  - data/constituents.py (Wikipedia fetch, Slickcharts cross-check)
  - data/prices.py (PriceStore: bulk_download, ensure_fresh, load_matrix)
  GATE: `init --dry-run` fetches constituents and downloads prices for 5 tickers

Phase 4: Strategy layer (pure functions)
  - strategy/indicators.py (sma, roc, highest_close_since)
  - strategy/filters.py (regime, liquidity, momentum)
  - strategy/ranking.py (rank_by_roc200, top_n)
  - strategy/stops.py (initial, trailing, effective, is_triggered)
  - strategy/sizing.py (position_size_shares)
  GATE: 95% unit test coverage; all Hypothesis property tests pass

Phase 5: Core services
  - services/audit_service.py
  - services/backup_service.py
  - services/scan_service.py (orchestrates phases 2-4)
  - services/position_service.py
  - services/cash_service.py
  - services/catchup_service.py
  GATE: scan_service integration test with real SQLite (in-memory) passes

Phase 6: UI layer
  - ui/tables.py, ui/format.py, ui/spinner.py, ui/progress.py
  - All 31 style guide rules implemented
  GATE: snapshot tests for all table renderings pass

Phase 7: Commands (thin wrappers)
  - All 17 cli/ modules
  - main.py assembly, ctx.obj pattern
  GATE: All command snapshot tests pass; `bensdorp1 init` completes end-to-end

Phase 8: Edge cases and hardening
  - Catch-up logic (multi-day absence reconstruction)
  - Stock split detection and adjustment
  - Scan guard (refuse before 16:30 ET)
  - Scan guard (refuse before 16:30 ET)
  - Validate mode (stateless historical verification)
  GATE: Catch-up test with 5-day simulated absence; validate test against known dates
```

**Why this order:**
- Phase 2 (DB) before Phase 3 (data) because prices writes to DB
- Phase 4 (strategy) isolated early because it has no dependencies — gets full test coverage before integration
- Phase 5 (services) after both DB and strategy are solid — services orchestrate, don't invent
- Phase 6 (UI) before Phase 7 (commands) because commands call UI; snapshot tests need real renderers
- Phase 8 last because it depends on every other layer being stable

---

## Catch-Up Logic Architecture

Catch-up reconstructs what would have happened on missed trading days without mutating scan history:

```
services/catchup_service.py
  detect_absence(engine) -> int  # trading days since last scan
  
  if absence >= 2:
    for each missed_trading_day in chronological order:
      historical_prices = load_matrix(as_of=missed_day)   # subset of cached data
      historical_positions = reconstruct_positions(engine, missed_day)
      triggers = check_stops(historical_positions, historical_prices)
      log catch-up events to audit_log with 13 fixed-wording templates
      update position.highest_close for each missed day
      # Note: does NOT create scan_result rows for missed days
      # Does NOT generate buy candidates for missed days (positions only)
```

**Key rule:** Catch-up handles exit triggers only. It does not generate buy candidates for missed days — the user cannot retroactively buy. Missed stop-outs are logged to the audit trail with the `CATCHUP_*` event types.

---

## Constituent Service Architecture

```
services/constituent_service.py
  fetch_and_store(engine) -> list[str]

data/constituents.py
  fetch_wikipedia() -> pd.DataFrame     # primary source
  fetch_slickcharts() -> pd.DataFrame   # secondary for cross-check
  cross_check(wiki, slick) -> list[str] # warn on mismatches, use wiki as truth
```

**Refresh cadence:** Check `constituents_fetched_at` in `app_state` table. Refresh if >7 days old OR if `--force` passed to `refresh` command. Constituents rarely change; 7 days is safe and avoids Wikipedia rate-limiting.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Strategy logic in command handlers
**What:** Putting filter/ranking logic directly in `cli/scan.py`.
**Why bad:** Untestable without Typer invocation. Impossible to test edge cases (regime off, insufficient history) without mocking the entire CLI.
**Instead:** Commands are thin wrappers. One line: `result = scan_service.run_scan(...)`.

### Anti-Pattern 2: Calling yfinance inside strategy functions
**What:** A strategy function calls `yf.download()` internally to get extra history.
**Why bad:** Makes strategy non-deterministic, non-testable, and tightly coupled to network.
**Instead:** All data is pre-loaded into the price matrix before any strategy function is called.

### Anti-Pattern 3: Opening a new engine per query
**What:** Each service method calls `create_engine()` to get a fresh engine.
**Why bad:** WAL mode PRAGMA and connection configuration is applied once per connection; a new engine is wasteful and can cause state drift.
**Instead:** One engine per CLI invocation, created in `@app.callback()`, passed through ctx.obj.

### Anti-Pattern 4: Using ORM models for price data
**What:** Defining a `Price` ORM model with per-row object materialization.
**Why bad:** 110,000 Price objects per query is a memory and performance disaster.
**Instead:** SQLAlchemy Core + `conn.execute().fetchall()` + `pd.DataFrame(rows)` is the correct pattern for bulk tabular data.

### Anti-Pattern 5: Calendar days instead of trading days for lookback
**What:** `start = today - timedelta(days=200)` for the SMA 200 window.
**Why bad:** 200 calendar days includes weekends and holidays, producing wrong SMA values.
**Instead:** Always use `pandas_market_calendars` to compute `trading_days_lookback(today, 200)`.

### Anti-Pattern 6: Storing prices in a single column as JSON
**What:** One row per ticker, `prices_json = '{"2024-01-02": 185.3, ...}'`.
**Why bad:** Cannot query by date range in SQL. Loading all tickers to filter by date is O(n) where n = total stored rows.
**Instead:** `(ticker, trade_date, close, volume)` normalized schema with composite primary key.

---

## Scalability Considerations

This is a single-user tool that does not scale — that is by design. But here are the relevant size characteristics:

| Concern | At Init | After 1 Year | After 5 Years |
|---------|---------|--------------|---------------|
| prices rows | ~110,000 | ~237,000 | ~890,000 |
| DB file size | ~15MB | ~30MB | ~120MB |
| Backup files | 1 | ~252 | ~1,260 |
| Backup disk | ~15MB | ~7.5GB | ~37GB |
| Scan duration | ~2s | ~3s | ~5s |

SQLite handles up to hundreds of millions of rows efficiently with proper indexing. The 5-year row count is entirely within SQLite's comfortable operating range. The backup disk concern is the only real operational issue, but per spec, backups are never auto-deleted — this is an intentional tradeoff for data safety.

---

## Sources

- SQLAlchemy 2.0 Connection Management: https://docs.sqlalchemy.org/en/20/core/connections.html
- SQLAlchemy SQLite Dialect & PRAGMAs: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html
- Python sqlite3.Connection.backup() API: https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup
- SQLAlchemy engine.raw_connection() for backup: https://docs.sqlalchemy.org/en/21/faq/connections.html
- Typer Context and shared state: https://pytutorial.com/python-typer-global-state-with-context/
- Typer add_typer subcommand structure: https://typer.tiangolo.com/tutorial/subcommands/add-typer/
- yfinance.download() parameters: https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
- yfinance rate limiting (GitHub issue #2614): https://github.com/ranaroussi/yfinance/issues/2614
- yfinance rate limiting best practices: https://www.slingacademy.com/article/rate-limiting-and-api-best-practices-for-yfinance/
- pandas_market_calendars usage: https://pandas-market-calendars.readthedocs.io/en/latest/usage.html
- SQLite WAL mode: https://sqlite.org/wal.html
- SQLite WAL + Python best practices: https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/
- Simon Willison on WAL mode: https://til.simonwillison.net/sqlite/enabling-wal-mode
- Hypothesis + pandas property-based testing: https://medium.com/clarityai-engineering/property-based-testing-a-practical-approach-in-python-with-hypothesis-and-pandas-6082d737c3ee
- src layout vs flat layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
