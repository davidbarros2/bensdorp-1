# Domain Pitfalls

**Domain:** Python CLI trading signal tool (bensdorp1)
**Stack:** yfinance, pandas_market_calendars, SQLite + SQLAlchemy Core, Typer, Rich, Pydantic v2, httpx, beautifulsoup4, pandas, NumPy, mypy strict, ruff, pytest + Hypothesis
**Researched:** 2026-05-23

---

## Critical Pitfalls

Mistakes in this category cause silent incorrect signals, data corruption, or CI that never passes.

---

### Pitfall 1: yfinance Returns Empty DataFrame Without Raising

**What goes wrong:** When yfinance cannot fetch data for a ticker — because the symbol is delisted, the session cookie has expired, or Yahoo's API returns a malformed response — it does not raise an exception. It returns an empty DataFrame and prints a warning to stdout (e.g., `No data found, symbol may be delisted`). Downstream code that accesses `df["Close"]` on an empty frame produces `KeyError` or silently produces `NaN`-filled series, corrupting signal calculations.

**Why it happens:** yfinance is a scraper over Yahoo Finance's unofficial API. The library treats data absence as a non-fatal condition by design, so it logs and returns empty rather than raising.

**Consequences:** ROC 200, momentum filter, and trailing stop calculations all silently fail or produce `NaN`. A stock with no data passes all filters as `NaN > threshold` evaluates to `False`, effectively hiding the ticker — correct but only by accident, and only for boolean comparisons. Any arithmetic on `NaN` propagates silently.

**Warning signs:**
- `df.empty` is `True` after `yf.download()`
- `df["Close"].isna().all()` is `True`
- Console shows `No data found` lines during batch downloads
- Calculated ROC values contain `NaN` for specific tickers

**Prevention strategy:**
```python
# After every download, assert shape before use
def fetch_history(ticker: str, period: int) -> pd.DataFrame:
    df = yf.download(ticker, period=f"{period}d", auto_adjust=True, progress=False)
    if df.empty:
        raise DataUnavailableError(f"No price data returned for {ticker!r}")
    if len(df) < period * 0.8:  # allow for holidays / weekends
        raise InsufficientHistoryError(
            f"{ticker}: got {len(df)} rows, expected ~{period}"
        )
    return df
```

**Phase that must address it:** Phase that builds the data-fetching layer (price history download). The guard function must be in place before any strategy calculation module is written.

---

### Pitfall 2: yfinance Multi-Ticker Download Produces Unexpected MultiIndex Columns

**What goes wrong:** When `yf.download()` is called with a list of tickers, the returned DataFrame has a two-level MultiIndex on columns: `(price_field, ticker)` or `(ticker, price_field)` depending on version. As of yfinance 0.2.51+, the column order within each level is alphabetical (`Close, High, Low, Open, Volume`) rather than OHLCV. Code written against one version breaks silently on another version by accessing the wrong column.

**Why it happens:** The yfinance maintainers changed the default MultiIndex format in 0.2.51 without a major version bump. The project has no stable API contract for column ordering.

**Consequences:** Accessing `df["Close"]` on a multi-ticker download returns a DataFrame of close prices (correct) only if `Close` is the first level. Accessing `df[ticker]["Close"]` works but requires knowing the level order. Silent wrong-column access is the real danger.

**Warning signs:**
- `df.columns` is a `MultiIndex` when you expected flat columns
- Column order is `['Close', 'High', 'Low', 'Open', 'Volume']` instead of `['Open', 'High', 'Low', 'Close', 'Volume']`
- `df["Close"]` returns a DataFrame instead of a Series

**Prevention strategy:**
```python
# Always download one ticker at a time, or explicitly select after download
df = yf.download(ticker, auto_adjust=True, progress=False)
# If multi-ticker is needed, flatten explicitly:
close = df.xs("Close", axis=1, level=0)  # always access by name, never by position
```
Pin yfinance to a tested version in `pyproject.toml` with `==` not `>=`.

**Phase that must address it:** Phase that establishes the data-fetching layer. Pin version in pyproject.toml immediately.

---

### Pitfall 3: yfinance Rate Limiting After ~950 Tickers (Yahoo 429)

**What goes wrong:** Yahoo Finance's unofficial API enforces a limit of approximately 360 requests per hour per session. As of November 2024, the limit is actively enforced and results in `YFRateLimitError` (raised since yfinance 0.2.52) after roughly 950 ticker fetches in a loop. Before 0.2.52, the error was a bare `requests` exception or a silent empty return.

**Why it happens:** Yahoo tightened limits in November 2024. The S&P 500 has 503 tickers. A fresh `init` downloads 220 days of history for all 503, totaling 503 individual requests — just within the hourly budget if spread across 10+ minutes but dangerous if batched rapidly.

**Consequences:** `init` command appears to complete but many tickers have no history in the database. `scan` the next day fails because price history is missing for half the universe.

**Warning signs:**
- `YFRateLimitError` exception during `init`
- Many tickers in database with fewer than 220 rows of price history
- Gap in ticker coverage in audit log after `init`

**Prevention strategy:**
```python
import time

BATCH_SIZE = 50
BATCH_DELAY_SECONDS = 8  # stay under 360/hr = 6/min; 50 tickers / 8s = 6.25/min

for i in range(0, len(tickers), BATCH_SIZE):
    batch = tickers[i : i + BATCH_SIZE]
    for ticker in batch:
        try:
            fetch_and_store(ticker)
        except YFRateLimitError:
            time.sleep(60)  # back off a full minute
            fetch_and_store(ticker)  # retry once
    time.sleep(BATCH_DELAY_SECONDS)
```
Show a progress bar (Rich) with ETA during `init` since this will exceed 30 seconds.

**Phase that must address it:** `init` command implementation. The progress bar threshold (>30s shows ETA) from the spec is directly relevant here.

---

### Pitfall 4: yfinance Adjusted Close Inconsistency Around Split/Dividend Events

**What goes wrong:** `auto_adjust=True` instructs yfinance to adjust OHLCV for splits and dividends. However, the adjustment is applied retrospectively only to data returned in the current fetch. If you store prices on Monday and re-fetch on Friday after a split, the new adjusted prices do not match the stored values. Monday's stored "close" of $100 might now correspond to a post-split adjusted price of $50 — but the stored value is still $100.

A secondary issue: yfinance has a documented case (issue #2070) where split-adjusted OHLC and dividend-adjusted amounts are inconsistent with each other, producing small but systematic errors in returns calculations.

**Why it happens:** Yahoo recomputes adjusted prices from the current date backward each time. The reference point changes with each corporate action.

**Consequences:** Trailing stop levels calculated from stale stored prices diverge from recalculated values. Entry close stored at time of buy differs from the retroactively adjusted value. Effective stop comparisons become wrong.

**Warning signs:**
- Stored price for a held position differs by a round factor (2x, 3x) from yfinance re-fetch
- Position P&L shows impossible values after a known split date
- `audit` log shows split detection event but stored stops not updated

**Prevention strategy:**
- Store prices as-fetched at time of fetch. Never re-derive historical prices from a new fetch.
- Implement the spec's split detection: on each `scan`, compare last stored close against yfinance's current adjusted close for all held positions. If ratio differs by more than 1% from 1.0, treat as split event, update `entry_close` and stop levels proportionally, and log to audit.
- Never store raw close and adjusted close in separate columns — use only adjusted throughout.

```python
def detect_split(stored_close: float, current_adjusted_close: float) -> float | None:
    ratio = current_adjusted_close / stored_close
    # Common split ratios: 0.5 (2:1), 0.333 (3:1), 0.25 (4:1)
    for expected in [0.5, 0.333, 0.25, 2.0, 3.0, 4.0]:
        if abs(ratio - expected) < 0.02:
            return ratio
    return None
```

**Phase that must address it:** Position management / `scan` command phase. Split detection must be built in the same phase as trailing stop tracking.

---

### Pitfall 5: Ticker Symbol Mismatch Between Wikipedia and yfinance (Period vs. Hyphen)

**What goes wrong:** Wikipedia's S&P 500 table lists tickers in standard exchange format, which uses periods for share class separators: `BRK.B`, `BF.B`. Yahoo Finance uses hyphens: `BRK-B`, `BF-B`. yfinance accepts both formats but internally normalizes to the hyphen form when constructing API URLs. If you pass `BRK.B` to yfinance, it works. But if you store `BRK.B` in the database and later use it as a key in any lookup or display context, you have two representations of the same ticker in flight simultaneously.

**Why it happens:** Exchange ticker conventions differ from Yahoo Finance's URL convention. Wikipedia follows exchange convention.

**Consequences:**
- Duplicate ticker entries if normalization is not applied before INSERT
- `buy BRK.B` and `buy BRK-B` treated as different positions
- Cross-checks between Wikipedia and Slickcharts produce false mismatches (Slickcharts also uses the period form)

**Warning signs:**
- Database contains both `BRK.B` and `BRK-B`
- Cross-check between Wikipedia and Slickcharts shows "missing" tickers
- `portfolio` command shows duplicate rows for the same company

**Prevention strategy:**
```python
# Canonical form: always store period-form (exchange convention).
# Normalize at the yfinance call site only, not in the database.
def to_yahoo_symbol(ticker: str) -> str:
    return ticker.replace(".", "-")

def to_canonical_symbol(yahoo_ticker: str) -> str:
    return yahoo_ticker.replace("-", ".")

# All DB storage uses canonical (period) form.
# All yfinance calls use to_yahoo_symbol() at call time.
```
Apply normalization in a single utility module imported everywhere. Enforce with a Pydantic validator on any model that holds a ticker field.

**Phase that must address it:** Data layer / constituents fetching phase. Must be established before any ticker is stored in the database.

---

## Moderate Pitfalls

---

### Pitfall 6: pandas_market_calendars schedule() Returns Empty DataFrame Silently

**What goes wrong:** `mcal.get_calendar("NYSE").schedule(start_date, end_date)` returns an empty DataFrame (not an exception) when no trading days exist in the range — for example, when `start_date == end_date` and that date is a holiday. Code that does `schedule.index[-1]` to find the last trading day then raises `IndexError`.

**Why it happens:** The library changed this behavior in v0.19: previously it raised, now it returns empty. The change was intentional but creates a silent footgun.

**Consequences:** "200 trading days ago" calculation fails when the date boundary lands on an edge case. `scan` could silently compute ROC against the wrong date.

**Warning signs:**
- `IndexError` when accessing `schedule.index`
- Empty DataFrame returned from `schedule()`
- ROC 200 calculation returns `NaN` for all tickers on certain dates

**Prevention strategy:**
```python
def get_trading_schedule(start: date, end: date) -> pd.DatetimeIndex:
    cal = mcal.get_calendar("NYSE")
    schedule = cal.schedule(start_date=start, end_date=end)
    if schedule.empty:
        raise NoTradingDaysError(f"No NYSE trading days between {start} and {end}")
    return mcal.date_range(schedule, frequency="1D")
```
Always assert the result is non-empty immediately after calling `schedule()`.

**Phase that must address it:** Trading day arithmetic utilities phase (early, before any strategy logic).

---

### Pitfall 7: pandas_market_calendars pytz Removal in v5.0

**What goes wrong:** Version 5.0 removed `pytz` and switched to `zoneinfo` (stdlib). Any code that imports `pytz` and passes a `pytz` timezone object into pandas_market_calendars functions raises `TypeError`. If the project or any dependency uses `pytz` for Eastern Time handling, these are incompatible with v5.0+.

**Why it happens:** Python 3.9 added `zoneinfo` to stdlib; the library modernized accordingly. Breaking change without major version bump.

**Consequences:** Scan-time timezone conversions fail. The "refuse scan before 16:30 ET" guard breaks if it uses pytz.

**Warning signs:**
- `TypeError: Only zoneinfo.ZoneInfo objects are supported` at runtime
- Tests pass in CI but fail locally due to pytz version mismatch

**Prevention strategy:**
```python
# Use zoneinfo exclusively throughout the codebase
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
LISBON = ZoneInfo("Europe/Lisbon")

# Never import pytz anywhere in the project
```
Add a ruff rule or simple grep in CI: `ruff check --select` or a pre-commit hook that rejects `import pytz`.

**Phase that must address it:** Project skeleton / dependency setup phase. Set zoneinfo as the standard before writing any timezone-aware code.

---

### Pitfall 8: SQLite WAL Mode + Transaction Upgrade = Immediate Lock Despite busy_timeout

**What goes wrong:** Setting `busy_timeout=5000` does not protect against all locking scenarios. Specifically: if a connection opens a read transaction (implicit `BEGIN`) and then issues a write statement within the same transaction, SQLite attempts to upgrade it to a write transaction. If any other connection (even a read-only one holding the shared-memory lock during checkpoint) exists at that moment, the upgrade fails with `SQLITE_BUSY` immediately — `busy_timeout` has no effect because the error is not a contention timeout, it is a transaction-state conflict.

For a single-user, single-process CLI this is rare but can occur if:
- Two CLI subcommands are accidentally run in parallel (e.g., `bensdorp scan &` then `bensdorp buy`)
- A background thread reads the DB while the main thread writes
- SQLAlchemy's connection pool holds an idle connection open during a long operation

**Why it happens:** SQLAlchemy Core by default uses a connection pool even for SQLite. The pool can hold a connection in a deferred read state while another part of the application attempts a write, creating the upgrade scenario within a single process.

**Consequences:** `bensdorp scan` or `bensdorp buy` raises `OperationalError: database is locked` in what appears to be a single-user scenario with no concurrent access.

**Warning signs:**
- `sqlite3.OperationalError: database is locked` with no other process running
- Error occurs only on write commands, not read-only commands
- Error occurs intermittently, not consistently

**Prevention strategy:**
```python
# Use StaticPool for SQLite (no connection pool) and always begin writes immediately
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///path/to/bensdorp1.db",
    connect_args={"check_same_thread": False, "timeout": 10},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.execute("PRAGMA synchronous=NORMAL")  # safe with WAL
    cursor.close()
```
Use `StaticPool` (single shared connection) for a single-user CLI. If a background thread ever accesses the DB, use explicit `BEGIN IMMEDIATE` for all write transactions.

**Phase that must address it:** Database initialization / SQLAlchemy setup phase (Phase 1 skeleton).

---

### Pitfall 9: SQLite Date Storage — Ordering and Comparison Breaks Without Strict ISO 8601

**What goes wrong:** SQLite has no native date type. Python's `sqlite3` adapter (and SQLAlchemy's) stores Python `datetime.date` and `datetime.datetime` as ISO 8601 text strings by default (`YYYY-MM-DD`). This works correctly for sorting and comparison only if the format is strictly zero-padded. If any code path stores `2026-5-3` instead of `2026-05-03`, `ORDER BY date_col` returns wrong results because text comparison orders `2026-5-3` after `2026-9-30` (because `"5" > "9"` is False but `"5" < "9"` is True — actually `"5"` sorts after `"9"` lexicographically: ord('5')=53, ord('9')=57, so `"5" < "9"` — date arithmetic via `WHERE date_col >= ?` works, but boundary scans fail).

More concretely: `WHERE scan_date >= '2026-05-01'` will miss `'2026-5-1'` stored as a non-padded string. This causes the `history` command to return incomplete results.

**Why it happens:** Python's `str(datetime.date(2026, 5, 3))` produces `'2026-05-03'` (correctly padded), but manual string construction like `f"{year}-{month}-{day}"` does not. SQLAlchemy's `Date` type coerces correctly, but `text()` queries with string interpolation bypass this.

**Consequences:** `history` command returns wrong date ranges. `validate` command comparisons fail on boundary dates. Backup filenames with non-padded dates sort incorrectly in the filesystem.

**Warning signs:**
- `history --since 2026-05-01` returns fewer rows than expected
- `scan_date` column contains values like `'2026-5-3'` (visible via `sqlite3` CLI)
- Test for date ordering fails on single-digit months

**Prevention strategy:**
```python
# Use SQLAlchemy Column(Date) — never store raw strings in date columns
# When constructing dates for comparison, always use datetime.date objects
from datetime import date

scan_date = date.today()  # always zero-padded when stored via SQLAlchemy Date type

# In text() queries, pass date objects as parameters, not formatted strings
stmt = text("SELECT * FROM scans WHERE scan_date >= :since")
result = conn.execute(stmt, {"since": date(2026, 5, 1)})
```
Add a Hypothesis test that generates `date` objects with single-digit months/days and verifies round-trip storage and query ordering.

**Phase that must address it:** Database schema definition phase. Add a test immediately.

---

### Pitfall 10: SQLite Backup Corrupts When shutil.copy() is Used With WAL Mode

**What goes wrong:** The spec requires "automatic backup after every state-changing operation." The naive implementation uses `shutil.copy(db_path, backup_path)`. In WAL mode, uncommitted or uncheckpointed changes live in a separate `-wal` file. Copying only the `.db` file while the `-wal` file has pending writes produces a backup that is internally inconsistent — it appears to open but returns data from an inconsistent state.

**Why it happens:** WAL mode's architecture separates the main database file from the write-ahead log. A file-level copy is not an atomic snapshot.

**Consequences:** `restore PATH` appears to succeed but the restored database is missing recent transactions. The user loses the last N scans and position updates silently.

**Warning signs:**
- Restored database reports no records for recent operations
- SQLite integrity check fails on restored file: `PRAGMA integrity_check`
- Backup file is smaller than expected (missing WAL content)

**Prevention strategy:**
```python
import sqlite3

def backup_database(source_path: str, dest_path: str) -> None:
    # Use the SQLite Online Backup API — handles WAL correctly
    src = sqlite3.connect(source_path)
    dst = sqlite3.connect(dest_path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
```
Never use `shutil.copy()`, `shutil.copy2()`, or `os.rename()` for SQLite files in WAL mode.

**Phase that must address it:** Database layer phase, alongside the backup-on-write feature.

---

### Pitfall 11: Wikipedia S&P 500 Table Column Name Instability

**What goes wrong:** Wikipedia's "List of S&P 500 companies" page uses a `wikitable sortable` table. The column header for the ticker symbol has historically been both `"Symbol"` and `"Ticker symbol"` depending on which editor last touched the page. Code that does `df["Symbol"]` breaks silently (returns `KeyError`) when a Wikipedia editor renames the column. This has happened in the past and community scrapers explicitly document it.

**Why it happens:** Wikipedia is a wiki — any editor can rename column headers. There is no schema stability guarantee.

**Consequences:** `refresh` command fails silently or raises an unhandled exception. If the failure is swallowed, the constituents cache retains the 7-day-old stale list and gives no warning.

**Warning signs:**
- `KeyError: 'Symbol'` during constituents fetch
- `refresh` command completes but constituent count is 0 or unchanged despite known index changes
- Column names in fetched table do not match expected schema

**Prevention strategy:**
```python
SYMBOL_COLUMN_CANDIDATES = ["Symbol", "Ticker symbol", "Ticker"]
SECURITY_COLUMN_CANDIDATES = ["Security", "Company"]

def extract_column(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for name in candidates:
        if name in df.columns:
            return df[name]
    raise ColumnNotFoundError(
        f"Expected one of {candidates}, got columns: {list(df.columns)}"
    )
```
Log the actual column names found on each fetch to the audit log so regressions are detectable.

**Phase that must address it:** Constituents fetching phase. Both Wikipedia and Slickcharts parsers need defensive column extraction from day one.

---

### Pitfall 12: Slickcharts Requires User-Agent Header (Blocks Python Defaults)

**What goes wrong:** Slickcharts blocks requests with the default `python-requests` or `httpx` user-agent strings, returning HTTP 403 or an HTML page with a Cloudflare challenge instead of the data table. `pd.read_html()` on this HTML produces either an empty list or a table full of Cloudflare challenge text.

**Why it happens:** Slickcharts uses bot-detection based on the User-Agent header.

**Consequences:** Cross-check between Wikipedia and Slickcharts silently fails. The cross-check is the primary validation that Wikipedia data is correct, so its failure removes a key safeguard.

**Warning signs:**
- `requests.get(slickcharts_url).status_code == 403`
- `pd.read_html()` returns an empty list or raises `ValueError: No tables found`
- Returned HTML contains "Cloudflare" or "Just a moment"
- Cross-check always shows 100% match (because both sources fail and empty lists vacuously agree)

**Prevention strategy:**
```python
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

resp = httpx.get("https://www.slickcharts.com/sp500", headers=HEADERS, timeout=15)
resp.raise_for_status()
tables = pd.read_html(resp.text)
if not tables:
    raise ScrapingError("Slickcharts: no tables found in response")
```
Check `len(tables[0])` after parsing — a successful parse should have ~503 rows. Treat < 400 rows as a parsing failure.

**Phase that must address it:** Constituents fetching phase. Same phase as Wikipedia parser.

---

### Pitfall 13: Rich Output Breaks When stdout is Piped (e.g., grep, less, CI logs)

**What goes wrong:** When the CLI's stdout is piped (`bensdorp portfolio | grep AAPL`), Rich auto-detects a non-TTY environment and strips ANSI escape codes — which is correct behavior. However, Rich also defaults terminal width to 80 columns in non-TTY mode. If tables are formatted assuming a wider terminal, they wrap at 80 characters in CI logs and piped output, making them unreadable. Additionally, on Windows CI (GitHub Actions), Rich has a known bug (#3412) where terminal width auto-detection returns incorrect values.

**Why it happens:** Rich reads `os.get_terminal_size()` which returns `(80, 24)` as a fallback when not attached to a TTY. CI environments trigger this fallback constantly.

**Consequences:** Snapshot tests for command output fail in CI because table line-wrapping differs between local terminal (e.g., 220 columns) and CI (80 columns). The `last` and `portfolio` commands produce unreadable output when piped.

**Warning signs:**
- Snapshot tests pass locally but fail in CI
- `portfolio` output wraps mid-row in CI logs
- `Console().width` returns 80 in test environment

**Prevention strategy:**
```python
# Create a single shared Console instance with explicit width for tests
# In production, let Rich auto-detect; in tests, pin width
import os
from rich.console import Console

def make_console(force_width: int | None = None) -> Console:
    return Console(
        width=force_width or None,  # None = auto-detect
        highlight=False,
        markup=False,  # don't accidentally interpret user data as Rich markup
    )

# In tests:
console = make_console(force_width=120)

# In snapshot tests, always render to string with fixed width:
console = Console(width=120, file=io.StringIO())
```
Set `COLUMNS=120` in the CI environment or use `Console(width=120)` for snapshot tests explicitly. Do not use `force_terminal=True` in tests — it enables color codes that pollute text snapshots.

**Phase that must address it:** UI / output layer phase. Snapshot test infrastructure must standardize on a fixed width from the start.

---

### Pitfall 14: mypy Strict + SQLAlchemy Core — Row Type Inference Requires Explicit Casts

**What goes wrong:** SQLAlchemy Core's `Connection.execute()` returns a `CursorResult`. Calling `.scalar()` returns `Any`. Calling `.fetchone()` returns `Row[Any] | None`. In `mypy --strict`, using the result of `.scalar()` as a typed value requires either an explicit cast or a type assertion. Without it, every downstream use of a DB-fetched value is typed as `Any`, and `mypy --strict` will flag usages of `Any` in typed contexts (via `warn_return_any`).

Additionally, the SQLAlchemy mypy plugin is deprecated as of SQLAlchemy 2.0 and removed in 2.1. It will not work with mypy >= 1.11.

**Why it happens:** PEP 484 cannot express the relationship between a SQL column's declared type and the Python type returned by `.scalar()` without runtime reflection. SQLAlchemy's new ORM typing (via `Mapped[]`) solves this for ORM but not for Core.

**Consequences:** Either every DB access site requires `cast()` or `assert`, or the codebase accumulates `# type: ignore[return-value]` comments, defeating the purpose of strict mode.

**Warning signs:**
- mypy reports `error: Returning Any from function declared to return "float"` on DB fetch sites
- `# type: ignore` comments proliferating around DB access code

**Prevention strategy:**
```python
from typing import cast
from sqlalchemy import select, text
from sqlalchemy.engine import Connection

def fetch_cash_balance(conn: Connection) -> float:
    result = conn.execute(
        text("SELECT amount FROM cash_ledger ORDER BY id DESC LIMIT 1")
    )
    value = result.scalar()
    if value is None:
        raise DatabaseIntegrityError("Cash ledger is empty")
    return cast(float, value)
```
Create a typed DB access helper module (`db/queries.py`) that wraps all raw SQLAlchemy calls with explicit `cast()` and None checks. Never use raw `.scalar()` outside this module. This isolates all the `cast()` noise in one place and keeps the rest of the codebase clean.

Do not install or configure the SQLAlchemy mypy plugin — it is deprecated and breaks with mypy >= 1.11.

**Phase that must address it:** Database layer phase. Establish the typed query helper module before writing any command-layer code that reads from the DB.

---

### Pitfall 15: Hypothesis — assume() Overuse Causes Unsatisfiable Strategy and Test Timeouts

**What goes wrong:** When writing property tests for strategy invariants (e.g., "effective stop is always >= initial stop"), the natural impulse is to use `assume()` to discard inputs that violate preconditions (e.g., "assume trailing stop > initial stop"). If the precondition filters out more than ~90% of generated inputs, Hypothesis raises `FailedHealthCheck: Data generation is extremely slow`. This causes CI to fail not because of a logic error but because the strategy is too constrained.

**Why it happens:** `assume()` tells Hypothesis to discard invalid examples. Hypothesis counts discards and aborts if the discard rate is too high.

**Consequences:** CI fails with a health check error that looks like a test failure but is actually a strategy design error. Tests with high discard rates also run very slowly because Hypothesis generates many examples before finding a valid one.

**Warning signs:**
- `hypothesis.errors.Unsatisfiable` or `FailedHealthCheck` in CI
- Tests take 30+ seconds in isolation
- `settings(max_examples=100)` on a test that still times out

**Prevention strategy:**
```python
# Bad: assume filters too many cases
@given(
    entry_close=st.floats(min_value=1.0, max_value=1000.0),
    highest_close=st.floats(min_value=1.0, max_value=1000.0),
)
def test_effective_stop(entry_close, highest_close):
    assume(highest_close >= entry_close)  # filters ~50% of inputs
    ...

# Good: build the constraint into the strategy
@given(
    entry_close=st.floats(min_value=1.0, max_value=1000.0),
    gain_pct=st.floats(min_value=0.0, max_value=5.0),
)
def test_effective_stop(entry_close, gain_pct):
    highest_close = entry_close * (1 + gain_pct)  # always >= entry_close by construction
    ...
```
For financial domain tests: express invariants as functions of base values rather than filtering independent samples. Use `@composite` strategies for complex multi-variable constraints.

**Phase that must address it:** Any phase that writes Hypothesis tests. Document the pattern in the first test module as a project convention.

---

### Pitfall 16: S&P 500 Index Change Lag — Wikipedia and Slickcharts Are Not Real-Time

**What goes wrong:** When S&P Dow Jones Indices announces a constituent change (e.g., "Company X replaces Company Y effective after close on DATE"), Wikipedia is updated by volunteers — typically within 1-3 days, sometimes within hours for high-profile changes, but occasionally delayed up to a week. Slickcharts has no documented update SLA.

For this project, the 7-day cache refresh means the constituents list could be up to 7 days stale plus the Wikipedia lag. A stock that was added to the index may not appear in the `scan` universe for up to two weeks.

**Why it happens:** Both sources are manually maintained or scrape each other. Neither has a live feed.

**Consequences:**
- A recently added S&P 500 stock is not scanned for buy signals for ~1-2 weeks
- A recently removed stock continues to be scanned as a buy candidate temporarily
- The cross-check between Wikipedia and Slickcharts may disagree for 24-72 hours around a change, causing a false alert

**Warning signs:**
- Cross-check shows 1-3 ticker mismatches between Wikipedia and Slickcharts
- Known recent index change (announced in financial news) not reflected in `refresh` output

**Prevention strategy:**
- Accept this lag as a known limitation — for a 200-day momentum strategy, a 1-2 week lag in universe membership has negligible effect on signals
- Document the lag in `status` command output: show "Constituents last updated: X days ago (next refresh in Y days)"
- Treat a 1-5 ticker discrepancy between Wikipedia and Slickcharts as a warning (not an error) — log it, proceed with the Wikipedia list, note the discrepancy in the audit log
- Treat a >10 ticker discrepancy as an error requiring `--force` to override

**Phase that must address it:** Constituents fetching phase. The cross-check validation logic must encode acceptable discrepancy thresholds.

---

## Minor Pitfalls

---

### Pitfall 17: Pydantic v2 Strict Mode Rejects int Where float Expected

**What goes wrong:** Pydantic v2 strict mode rejects `int` values for `float` fields. `model.price = 100` raises `ValidationError` because `100` is an `int`, not a `float`. This is a breaking change from Pydantic v1, where `int` was coerced to `float` automatically.

**Prevention:** Explicitly type all price/quantity fields as `float` at call sites. When passing user-supplied integer prices (e.g., from `buy SYMBOL 100 10`), call `float(value)` before passing to Pydantic models. Alternatively, use `model_config = ConfigDict(strict=False)` for models that receive user input, reserving strict mode for internal data models.

---

### Pitfall 18: ruff Flags TYPE_CHECKING Forward References as Undefined

**What goes wrong:** ruff rule F821 (undefined name) incorrectly flags symbols defined inside `if TYPE_CHECKING:` blocks when they are used as string annotations elsewhere. This can cause CI to fail on valid mypy-compatible code.

**Prevention:** Add `# noqa: F821` or configure ruff to exclude F821 for files that use `TYPE_CHECKING`. Alternatively, use `from __future__ import annotations` at the top of every module, which makes all annotations strings by default, eliminating the issue.

---

### Pitfall 19: NumPy NaN Propagation in Boolean Comparisons

**What goes wrong:** `NaN > 0.0` evaluates to `False` in NumPy, not `NaN`. This means a stock with NaN close price passes `price > 0` (False — stock is correctly excluded) but may pass other comparisons unexpectedly. `NaN != NaN` is True. Strategy filters using `!=` or `is not None` can silently include NaN-priced stocks.

**Prevention:** Apply `df.dropna(subset=["Close"])` before any strategy filter. Add an explicit assertion that no NaN values exist in price series before calculating ROC or momentum.

---

### Pitfall 20: pandas_market_calendars schedule() Date Parameter Type Sensitivity

**What goes wrong:** `schedule(start_date, end_date)` accepts `str`, `datetime.date`, or `pd.Timestamp`. If a `datetime.datetime` with timezone is passed, behavior varies by pandas version (pandas 3.0 changed datetime64 dtype handling, fixed in pandas_market_calendars 5.3.0). Using `datetime.datetime.now()` instead of `datetime.date.today()` as a boundary causes subtle bugs.

**Prevention:** Always pass `datetime.date` objects (not `datetime.datetime`) to `schedule()`. Pin `pandas_market_calendars >= 5.3.0` to get the pandas 3.0 datetime64 fix.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Project skeleton / pyproject.toml | pytz imported transitively via old dependency | Audit `uv tree` for pytz; enforce zoneinfo-only via ruff ban |
| DB schema creation | Date columns stored as wrong type | Use `Column(Date)` exclusively; add Hypothesis round-trip test |
| Constituents fetching | Wikipedia column rename, Slickcharts 403 | Defensive column extraction; User-Agent header; row-count validation |
| Ticker normalization | BRK.B vs BRK-B stored inconsistently | Single utility function; Pydantic validator on ticker fields |
| Price history download (init) | Rate limit at ~950 requests; empty DataFrame on delisted | Batch with delay; assert non-empty after each fetch |
| Strategy calculation | NaN propagation; adjusted close inconsistency | dropna before filters; never mix raw and adjusted prices |
| Position management | Split detection; trailing stop off-by-one day | Ratio-based split detection; trailing stop starts day AFTER entry |
| Backup / restore | shutil.copy misses WAL file | Use sqlite3.backup() API exclusively |
| CLI output / snapshot tests | Rich table width mismatch between local and CI | Pin Console(width=120) in all snapshot tests |
| Hypothesis test suite | assume() overuse; slow health checks | Build constraints into strategies; use @composite |

---

## Sources

- [yfinance Rate Limiting Issue #2128](https://github.com/ranaroussi/yfinance/issues/2128)
- [yfinance YFRateLimitError Issue #2422](https://github.com/ranaroussi/yfinance/issues/2422)
- [yfinance Download Column Order Change Discussion #2330](https://github.com/ranaroussi/yfinance/discussions/2330)
- [yfinance Adjusted Close vs Total Return Issue #2070](https://github.com/ranaroussi/yfinance/issues/2070)
- [yfinance Empty DataFrame / Delisted Issue #359](https://github.com/ranaroussi/yfinance/issues/359)
- [yfinance auto_adjust=True Changes](https://softhints.com/understanding-yfinance-auto_adjust-true-what-changed-and-how-to-fix-it/)
- [pandas_market_calendars Change Log](https://pandas-market-calendars.readthedocs.io/en/latest/change_log.html)
- [SQLite Write-Ahead Logging — Official Docs](https://sqlite.org/wal.html)
- [SQLite Concurrent Writes and Locked Errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [SQLite Backup API Discussion](https://sqlite.org/forum/info/2ea989bbe9a6dfc8)
- [Rich Terminal Width Bug on Windows #3412](https://github.com/Textualize/rich/issues/3412)
- [Rich Console API Docs](https://rich.readthedocs.io/en/latest/console.html)
- [SQLAlchemy mypy Plugin Deprecation](https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html)
- [Hypothesis FailedHealthCheck Issue #2195](https://github.com/HypothesisWorks/hypothesis/issues/2195)
- [Hypothesis Rule-Based Stateful Testing](https://hypothesis.works/articles/rule-based-stateful-testing/)
- [Wikipedia S&P 500 Column Name Instability — community observation](https://en.wikipedia.org/wiki/Talk:List_of_S%26P_500_companies)
- [Slickcharts S&P 500 Scraping Gist](https://gist.github.com/philshem/f2fc94d7e49f045fe0feda8532ab2c08)
- [ruff TYPE_CHECKING F821 False Positive Issue #9753](https://github.com/astral-sh/ruff/issues/9753)
