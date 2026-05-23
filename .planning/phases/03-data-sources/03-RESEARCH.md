# Phase 3: Data Sources - Research

**Researched:** 2026-05-23
**Domain:** yfinance, pandas-market-calendars, BeautifulSoup/lxml, SQLAlchemy Core bulk inserts, pytest mocking
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Hybrid bulk + per-symbol retry. Primary download is `yfinance.download(tickers_list, auto_adjust=True)` — one bulk call for all symbols. After the bulk call, any symbol missing from the result or with fewer than expected rows is retried individually with exponential backoff: 3 retries at 1 s, 2 s, 4 s delays (DATA-09). The MultiIndex result from bulk multi-ticker downloads is flattened immediately after download.
- **D-02:** DB-first incremental model. `init` (Phase 6) pre-loads 220 trading days. At scan time, the data layer reads from `price_daily` and fetches only days not yet present in the DB. The 95% coverage check (DATA-10) runs against what's in `price_daily` before any scan proceeds.
- **D-03:** Stale cache with warning — never hard-fail on network unavailability alone. If the 7-day TTL has expired and both Wikipedia and Slickcharts are unreachable, the scan continues using the cached constituent list with a clear Warning-severity message.
- **D-04:** `^GSPC` is treated as a regular symbol in `price_daily`. The data layer always includes `^GSPC` in its download list regardless of the constituents list.
- **D-05 (Claude's discretion):** Four-module layout: `data/__init__.py`, `data/constituents.py`, `data/prices.py`, `data/calendar.py`.

### Claude's Discretion

- D-05: Four-module layout matching Phase 2's `db/` pattern (see full description in Decisions).

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | S&P 500 constituents fetched from Wikipedia (primary) and cross-checked against Slickcharts (secondary) | BeautifulSoup + lxml parser pattern; httpx.Client for HTTP |
| DATA-02 | Constituents cross-check: 0-3 silent; 4-10 warn; 11+ abort buy candidates | Symmetric difference count pattern; AuditEventType.CONSTITUENTS_DISCREPANCY |
| DATA-03 | Price data via yfinance with `auto_adjust=True` | yfinance.download() verified; auto_adjust=True explicit parameter required |
| DATA-04 | 220 trading days of price history required | nyse.valid_days() confirmed returns correct count |
| DATA-05 | Constituents cache refreshed automatically every 7 days at scan time | SQLAlchemy func.max(fetched_at) query pattern verified |
| DATA-07 | NYSE market calendar used for all trading day arithmetic | pandas_market_calendars v5 API verified; valid_days() confirmed |
| DATA-08 | Ticker normalization: period form stored in DB; hyphen form at yfinance call site only | Verified: BRK.B fails yfinance, BRK-B succeeds; replace('.', '-') pattern |
| DATA-09 | Rate-limited yfinance download with retry: 3 retries, exponential backoff (1s, 2s, 4s) | Backoff list comprehension pattern; time.sleep() |
| DATA-10 | Scan aborted if fewer than 95% of constituents have price data | GROUP BY + HAVING SQL query pattern verified in SQLAlchemy Core |
</phase_requirements>

---

## Summary

This phase builds the `src/bensdorp1/data/` subpackage — four modules covering Wikipedia/Slickcharts constituent fetching (`constituents.py`), yfinance bulk price downloads with retry (`prices.py`), NYSE calendar wrappers (`calendar.py`), and a clean public API (`__init__.py`). All technology is already installed and working in the project venv.

The two most consequential technical findings from this research: First, yfinance bulk multi-ticker downloads return a two-level `MultiIndex` (`(field, ticker)` format) even when `multi_level_index=False` is passed — the correct flattening approach is `df.stack(level=1, future_stack=True)` which produces a `(Date, Ticker)` multi-index with flat columns. Failed downloads appear as all-NaN rows in the stacked result, not as missing tickers — the retry logic must detect `Close.isna().all()` per ticker group, not check for ticker absence. Second, SQLite with `DateTime(timezone=True)` columns returns naive `datetime` objects on read-back — all read paths must normalize with `.replace(tzinfo=UTC)` before comparison.

A new dependency (`lxml>=6.1.1`) was discovered missing from `pyproject.toml` and has already been added via `uv add lxml`. Two mypy overrides need to be added for `yfinance` and `pandas_market_calendars` (both lack stubs); `lxml-stubs>=0.5.1` needs to be added to the dev dependency group.

**Primary recommendation:** Implement modules in wave order — calendar.py first (no I/O), then constituents.py (HTTP + DB), then prices.py (yfinance + DB), then __init__.py re-exports. Use `df.stack(level=1, future_stack=True)` as the canonical MultiIndex flattening pattern throughout prices.py.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Constituent fetching (Wikipedia, Slickcharts) | Data Layer (`constituents.py`) | — | Pure I/O; no CLI concerns |
| Constituent cache TTL check | Data Layer (`constituents.py`) | DB (`constituents_cache` table) | Cache state lives in DB; TTL logic in data layer |
| Price download (yfinance) | Data Layer (`prices.py`) | — | External API; data layer owns all yfinance calls |
| Price DB persistence | Data Layer (`prices.py`) | DB (`price_daily` table) | Insert/select on schema defined in Phase 2 |
| Ticker normalization (period ↔ hyphen) | Data Layer (`prices.py`) | — | CONTEXT.md D-05: sole location for normalization |
| NYSE calendar arithmetic | Data Layer (`calendar.py`) | — | Pure computation; no I/O; wraps pandas_market_calendars |
| 95% coverage check | Data Layer (`prices.py`) | — | Reads price_daily; data quality gate before scan |
| Audit event emission | DB Layer (`audit.py`) | Data Layer (calls log_event) | Data layer calls db.log_event; does not own audit_log |
| ^GSPC download | Data Layer (`prices.py`) | — | Treated as regular symbol; always appended to ticker list |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yfinance | `>=1.3.0` | Price and index data download | Only free, no-key source in project constraints |
| pandas-market-calendars | `>=5.3.2` | NYSE trading day list and arithmetic | DATA-07 locked; v5 uses zoneinfo (no pytz dependency) |
| beautifulsoup4 | `>=4.14.3` | HTML parse for Wikipedia and Slickcharts | Ships py.typed; mypy-clean without stubs |
| lxml | `>=6.1.1` | Fast HTML parser backend for BeautifulSoup | DATA-01 canonical parser; faster than html.parser on large tables |
| httpx | `>=0.28.1` | Sync HTTP client for scraping | Already in pyproject.toml; typed stubs ship with package |
| SQLAlchemy Core | `>=2.0.49,<2.1` | price_daily and constituents_cache inserts/selects | Phase 2 established this pattern; Core (not ORM) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | `>=3.0.3` | DataFrame manipulation for yfinance results | Stacking MultiIndex, NaN detection, iterrows |
| lxml-stubs | `>=0.5.1` | Type stubs for lxml (dev only) | Required for mypy strict on any file that imports lxml |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | requests | requests stubs are third-party and lag; httpx ships inline types (CLAUDE.md decision) |
| lxml | html.parser | html.parser is stdlib — zero install — but slower on 500+ row tables; lxml recommended by bs4 docs for production use |
| BeautifulSoup | pandas.read_html | pandas.read_html is simpler but less robust for Slickcharts (anti-scraping measures); also harder to mock |

**Installation:**

```bash
# lxml was the only missing dep; already added by this research session
uv add lxml
# lxml-stubs goes in dev group:
uv add --group dev lxml-stubs
```

**Version verification (VERIFIED against installed venv):**

```
yfinance:                1.3.0   [VERIFIED: venv]
pandas-market-calendars: 5.3.2   [VERIFIED: venv]
beautifulsoup4:          4.14.3  [VERIFIED: venv]
lxml:                    6.1.1   [VERIFIED: venv, just added]
httpx:                   0.28.1  [VERIFIED: venv]
sqlalchemy:              2.0.49  [VERIFIED: venv]
pandas:                  3.0.3   [VERIFIED: venv]
numpy:                   2.4.6   [VERIFIED: venv]
lxml-stubs:              0.5.1   [VERIFIED: PyPI via pip index versions]
```

---

## Package Legitimacy Audit

> Packages verified via `slopcheck install` run during this research session.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| yfinance | PyPI | ~8 yrs | Very high | github.com/ranaroussi/yfinance | [OK] | Approved |
| pandas-market-calendars | PyPI | ~8 yrs | High | github.com/rsheftel/pandas_market_calendars | [OK] | Approved |
| beautifulsoup4 | PyPI | ~14 yrs | Very high | bazaar.launchpad.net/~leonardr/beautifulsoup | [OK] | Approved |
| lxml | PyPI | ~16 yrs | Very high | github.com/lxml/lxml | [OK] | Approved |
| httpx | PyPI | ~5 yrs | Very high | github.com/encode/httpx | [OK] | Approved |
| sqlalchemy | PyPI | ~18 yrs | Very high | github.com/sqlalchemy/sqlalchemy | [OK] | Approved |
| pandas | PyPI | ~16 yrs | Very high | github.com/pandas-dev/pandas | [OK] | Approved |
| numpy | PyPI | ~18 yrs | Very high | github.com/numpy/numpy | [OK] | Approved |
| lxml-stubs | PyPI | ~5 yrs | Medium | github.com/lxml/lxml-stubs | [OK] | Approved (dev only) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

> slopcheck ran clean on all 8 packages: `8 OK`. [VERIFIED: slopcheck 0.6.1 run 2026-05-23]

---

## Architecture Patterns

### System Architecture Diagram

```
[bensdorp1 scan / init command]
         |
         v
[data/__init__.py — public API]
    |            |            |
    v            v            v
[constituents.py]  [prices.py]  [calendar.py]
    |                  |             |
    v                  v             v
[httpx.Client]    [yfinance.download()]  [mcal.get_calendar('NYSE')]
[Wikipedia HTML]  [bulk: df.stack()]     [valid_days(start, end)]
[Slickcharts HTML][per-symbol retry]     [timezone-aware DatetimeIndex]
    |                  |
    v                  v
[constituents_cache]  [price_daily]
  (DELETE + INSERT)   (INSERT OR IGNORE via sqlite_insert.on_conflict_do_nothing)
         |
         v
    [audit_log via db.log_event()]
```

Data flow: commands call data/__init__.py public functions → domain modules call external I/O → results written to SQLite via SQLAlchemy Core → audit events emitted via existing db.log_event().

### Recommended Project Structure

```
src/bensdorp1/
├── data/
│   ├── __init__.py        # re-exports: get_constituents, update_price_data, get_trading_days, ...
│   ├── constituents.py    # Wikipedia/Slickcharts fetch, discrepancy check, 7-day cache
│   ├── prices.py          # yfinance bulk+retry, price_daily persistence, 95% check
│   └── calendar.py        # NYSE calendar wrappers (pure computation, no I/O)
```

No separate `http.py` or `retry.py` — D-05 and CONTEXT.md explicitly say retry is simple enough to inline in the modules that need it.

### Pattern 1: yfinance Bulk Download with MultiIndex Flattening

**What:** Download all tickers at once, flatten the two-level column MultiIndex into (Date, Ticker) rows.
**When to use:** Primary download path in `prices.py:download_prices_bulk()`.

```python
# Source: VERIFIED in project venv, 2026-05-23
import yfinance as yf
import pandas as pd
from datetime import datetime, UTC

def _download_bulk(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Return flattened DataFrame with (Date, Ticker) index, columns: Close, Volume."""
    df = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,   # DATA-03: always explicit
        progress=False,
        group_by="column",  # default; produces (field, ticker) MultiIndex
    )
    if df.empty:
        return pd.DataFrame()
    # Stack ticker level to get (Date, Ticker) MultiIndex with flat columns
    stacked: pd.DataFrame = df.stack(level=1, future_stack=True)
    return stacked[["Close", "Volume"]]
```

**Key finding:** `multi_level_index=False` does NOT flatten when downloading multiple tickers — it still produces a 2-level MultiIndex. The `df.stack(level=1, future_stack=True)` approach is the correct flattening method. [VERIFIED: tested in venv 2026-05-23]

### Pattern 2: Detect Failed Tickers in Bulk Result

**What:** After bulk download and stack, identify tickers where all Close values are NaN (failed download).
**When to use:** After `_download_bulk()`, before writing to DB, to build the per-symbol retry list.

```python
# Source: VERIFIED in project venv, 2026-05-23
def _find_failed_tickers(stacked: pd.DataFrame, expected: set[str]) -> set[str]:
    """Return tickers with all-NaN Close or entirely absent from stacked result."""
    if stacked.empty:
        return expected
    failed: set[str] = set()
    ticker_level = stacked.index.get_level_values("Ticker")
    for ticker in expected:
        mask = ticker_level == ticker
        if not mask.any():
            failed.add(ticker)  # absent entirely
        elif stacked.loc[mask, "Close"].isna().all():
            failed.add(ticker)  # present but all NaN
    return failed
```

**Key finding:** Failed bulk downloads appear as all-NaN rows — NOT as absent tickers. yfinance includes the failed ticker in the MultiIndex with NaN values. [VERIFIED: tested in venv 2026-05-23]

### Pattern 3: Per-Symbol Retry with Exponential Backoff

**What:** Retry individual tickers that failed the bulk download.
**When to use:** `prices.py` after `_find_failed_tickers()` returns non-empty set.

```python
# Source: VERIFIED pattern, exponential backoff (1s, 2s, 4s) per DATA-09
import time

def _download_with_retry(
    ticker: str, start: str, end: str, retries: int = 3
) -> pd.DataFrame:
    """Download single ticker with exponential backoff. Returns empty DF on final failure."""
    delays = [1.0 * (2**i) for i in range(retries)]  # [1.0, 2.0, 4.0]
    for attempt, delay in enumerate(delays):
        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=True,
            multi_level_index=False,  # safe for single ticker
            progress=False,
        )
        if not df.empty and not df["Close"].isna().all():
            return df[["Close", "Volume"]]
        if attempt < len(delays) - 1:
            time.sleep(delay)
    return pd.DataFrame()
```

### Pattern 4: SQLAlchemy Core Bulk Insert with ON CONFLICT DO NOTHING

**What:** Insert price rows, skip duplicates (idempotent; handles incremental re-runs).
**When to use:** `prices.py` when writing downloaded rows to `price_daily`.

```python
# Source: VERIFIED in project venv, 2026-05-23
from datetime import datetime, UTC
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from bensdorp1.db.schema import price_daily

def _persist_price_rows(engine: Engine, rows: list[dict[str, object]]) -> None:
    """Upsert price rows into price_daily. Silently ignores duplicates."""
    if not rows:
        return
    with engine.connect() as conn:
        stmt = sqlite_insert(price_daily).values(rows).on_conflict_do_nothing(
            index_elements=["symbol", "trade_date"]
        )
        conn.execute(stmt)
        conn.commit()
```

**Critical constraint:** `trade_date` values MUST be `datetime` objects (with `tzinfo=UTC`), not strings. SQLite `DateTime(timezone=True)` rejects string inputs with `TypeError`. [VERIFIED: tested in venv 2026-05-23]

**Critical constraint:** `datetime` objects read back from SQLite have `tzinfo=None` even when stored with `tzinfo=UTC`. All read paths must normalize: `dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt`. [VERIFIED: tested in venv 2026-05-23]

### Pattern 5: Ticker Normalization (DATA-08)

**What:** Convert between period form (DB storage) and hyphen form (yfinance call site).
**When to use:** In `prices.py` only — the sole location for this conversion.

```python
# Source: VERIFIED BRK.B fails yfinance, BRK-B succeeds, 2026-05-23
def _to_yfinance(symbol: str) -> str:
    """Convert DB period form to yfinance hyphen form. BRK.B -> BRK-B."""
    return symbol.replace(".", "-")

def _to_db(symbol: str) -> str:
    """Convert yfinance hyphen form back to DB period form. BRK-B -> BRK.B."""
    return symbol.replace("-", ".")
```

`^GSPC` is unchanged by both conversions (no `.` or `-` characters). GOOGL is an S&P 500 constituent; GOOG is not — no special handling needed. [VERIFIED: confirmed ^GSPC downloads correctly with yfinance 1.3.0]

### Pattern 6: NYSE Calendar Wrappers

**What:** Provide trading-day list and arithmetic for the project.
**When to use:** `calendar.py` — the single source of truth for trading day logic.

```python
# Source: VERIFIED against pandas-market-calendars 5.3.2 in venv, 2026-05-23
import pandas_market_calendars as mcal
import pandas as pd
from datetime import date, datetime, UTC

_NYSE = mcal.get_calendar("NYSE")

def get_trading_days(start: date, end: date) -> pd.DatetimeIndex:
    """Return NYSE trading days between start and end (inclusive), UTC timezone."""
    return _NYSE.valid_days(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )  # Returns DatetimeIndex dtype=datetime64[us, UTC]

def is_trading_day(dt: date) -> bool:
    """Return True if dt is a NYSE trading day."""
    ts = pd.Timestamp(dt).normalize().tz_localize("UTC")
    days = get_trading_days(dt, dt)
    return ts in days

def n_trading_days_ago(n: int, reference: date | None = None) -> date:
    """Return the date that was N NYSE trading days before reference (default: today)."""
    ref = reference or date.today()
    # Fetch enough days to cover n + buffer
    from datetime import timedelta
    start = ref - timedelta(days=int(n * 1.5) + 30)
    days = get_trading_days(start, ref)
    if len(days) < n:
        raise ValueError(f"Not enough trading days in range for n={n}")
    return days[-n].date()
```

**Critical finding:** `nyse.valid_days()` requires string arguments (ISO date format), not `date` objects. Use `date.isoformat()`. [VERIFIED: tested in venv 2026-05-23]

**Critical finding:** pandas-market-calendars v5 removed pytz entirely. `valid_days()` returns `DatetimeIndex` with `dtype=datetime64[us, UTC]` using Python's `zoneinfo`. No `pytz` import anywhere in `calendar.py`. [VERIFIED: confirmed with pmc 5.3.2]

### Pattern 7: Wikipedia S&P 500 Constituent Scraping

**What:** Fetch the first `wikitable` from the S&P 500 Wikipedia page, extract Symbol and Security columns.
**When to use:** `constituents.py:_fetch_wikipedia()`.

```python
# Source: VERIFIED BeautifulSoup + lxml pattern, 2026-05-23
import httpx
from bs4 import BeautifulSoup

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

def _fetch_wikipedia(client: httpx.Client) -> dict[str, str]:
    """Return {symbol: company_name} from Wikipedia S&P 500 table."""
    resp = client.get(WIKIPEDIA_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", class_="wikitable")
    if table is None:
        raise ValueError("Wikipedia S&P 500 wikitable not found")
    result: dict[str, str] = {}
    for row in table.find("tbody").find_all("tr"):  # type: ignore[union-attr]
        cells = row.find_all("td")
        if len(cells) >= 2:
            symbol = cells[0].get_text(strip=True)
            name = cells[1].get_text(strip=True)
            if symbol:
                result[symbol] = name
    return result
```

**Key finding:** Wikipedia's S&P 500 table already stores tickers in period form (`BRK.B`). No conversion needed on Wikipedia data. [VERIFIED: sample HTML structure confirmed]

### Pattern 8: Constituents 7-Day Cache Check

**What:** Query `max(fetched_at)` from `constituents_cache`; return True if stale (>7 days).
**When to use:** `constituents.py:_is_cache_stale()`.

```python
# Source: VERIFIED SQLAlchemy Core + SQLite datetime behavior, 2026-05-23
from sqlalchemy import select, func
from sqlalchemy.engine import Engine
from datetime import datetime, UTC, timedelta
from bensdorp1.db.schema import constituents_cache

def _is_cache_stale(engine: Engine) -> bool:
    """Return True if constituents_cache is empty or last fetch was > 7 days ago."""
    with engine.connect() as conn:
        row = conn.execute(
            select(func.max(constituents_cache.c.fetched_at))
        ).fetchone()
    if row is None or row[0] is None:
        return True
    latest = row[0]
    # SQLite returns naive datetime even for timezone=True columns
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=UTC)
    return (datetime.now(UTC) - latest) > timedelta(days=7)
```

### Pattern 9: Constituents Full Replacement Insert

**What:** Replace all rows in `constituents_cache` atomically (DELETE + INSERT in one transaction).
**When to use:** `constituents.py` after a successful fetch.

```python
# Source: VERIFIED SQLAlchemy Core pattern, 2026-05-23
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from datetime import datetime, UTC
from bensdorp1.db.schema import constituents_cache

def _persist_constituents(engine: Engine, data: dict[str, str]) -> None:
    """Replace all constituents_cache rows with fresh data."""
    now = datetime.now(UTC)
    rows = [
        {"symbol": sym, "company_name": name, "fetched_at": now}
        for sym, name in data.items()
    ]
    with engine.connect() as conn:
        conn.execute(constituents_cache.delete())
        if rows:
            conn.execute(insert(constituents_cache), rows)
        conn.commit()
```

### Pattern 10: 95% Coverage Check (DATA-10)

**What:** Count constituent symbols with ≥220 rows in price_daily; abort if < 95% of total.
**When to use:** `prices.py:check_price_coverage()` — called before any scan proceeds.

```python
# Source: VERIFIED SQLAlchemy Core query, 2026-05-23
from sqlalchemy import select, func
from sqlalchemy.engine import Engine
from bensdorp1.db.schema import price_daily, constituents_cache

def check_price_coverage(engine: Engine, required_days: int = 220) -> tuple[int, int]:
    """Return (covered_count, total_count). Caller decides whether to abort."""
    with engine.connect() as conn:
        # Total constituent count
        total = conn.execute(
            select(func.count()).select_from(constituents_cache)
        ).scalar_one()
        # Symbols with >= required_days rows
        subq = (
            select(price_daily.c.symbol)
            .group_by(price_daily.c.symbol)
            .having(func.count(price_daily.c.id) >= required_days)
            .subquery()
        )
        covered = conn.execute(
            select(func.count()).select_from(subq)
        ).scalar_one()
    return (covered, total)
```

### Anti-Patterns to Avoid

- **Passing date strings to SQLAlchemy DateTime insert:** `trade_date='2025-01-02'` raises `TypeError`. Always pass `datetime` objects with UTC timezone.
- **Using `multi_level_index=False` to flatten multi-ticker bulk downloads:** It does not flatten when multiple tickers are requested. Use `df.stack(level=1, future_stack=True)` instead.
- **Checking for ticker absence after failed bulk download:** Failed tickers appear as all-NaN rows, not as absent tickers. Check `Close.isna().all()` per ticker group.
- **Assuming SQLite returns timezone-aware datetimes:** It does not, even for `DateTime(timezone=True)` columns. Always `.replace(tzinfo=UTC)` on read.
- **Using pytz with pandas-market-calendars v5:** v5 removed pytz. Use Python's `zoneinfo` or no explicit timezone — `valid_days()` returns UTC DatetimeIndex natively.
- **Storing BRK.B in yfinance calls:** Period form fails with "possibly delisted" error. Always call `_to_yfinance()` at the yfinance call site.
- **Importing from `_app.py` or `commands/` in `data/`:** `data/` is a pure data layer. No circular imports.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NYSE trading day list | Custom holiday calendar | `pandas_market_calendars.get_calendar('NYSE').valid_days()` | Handles early closes, special sessions, historical holidays |
| HTTP retry with backoff | Custom retry decorator | Simple for-loop with `time.sleep()` — 3 retries only, no library needed | DATA-09 specifies exactly 3 retries at 1s/2s/4s; no need for `tenacity` or `urllib3.Retry` |
| HTML parsing | String-splitting or regex | BeautifulSoup + lxml | Table structure varies; BeautifulSoup handles malformed HTML gracefully |
| SQL duplicate prevention | Check-before-insert | `sqlite_insert.on_conflict_do_nothing()` | Race-condition-safe; single SQL statement |
| Timezone conversion | Manual UTC math | `datetime.now(UTC)` and `pd.Timestamp(...).tz_localize('UTC')` | DST-safe; no pytz needed |

**Key insight:** This phase has exactly one custom algorithm worth building: the retry-on-NaN detection loop. Everything else delegates to well-tested libraries already in the stack.

---

## Common Pitfalls

### Pitfall 1: SQLite Returns Naive Datetimes from DateTime(timezone=True) Columns

**What goes wrong:** Code compares `datetime.now(UTC)` (tz-aware) against a value from `row.trade_date` (tz-naive) — raises `TypeError: can't compare offset-naive and offset-aware datetimes`.
**Why it happens:** SQLite stores datetimes as strings. SQLAlchemy reads them back as naive `datetime` objects regardless of the `timezone=True` declaration.
**How to avoid:** Always normalize after reading: `dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt`. Wrap this in a private helper `_ensure_utc(dt: datetime) -> datetime`.
**Warning signs:** `TypeError` during date comparison, or `age.days` returning unreasonably large values.

### Pitfall 2: yfinance Bulk Download Returns NaN for Failed Tickers (Not Absence)

**What goes wrong:** Code checks `if ticker not in df.columns.get_level_values(1)` to find failed tickers — misses the case where ticker is present but all-NaN.
**Why it happens:** yfinance includes the ticker in the MultiIndex even when the download fails; it fills with NaN.
**How to avoid:** After stacking, check `stacked.loc[ticker_mask, 'Close'].isna().all()` for each expected ticker.
**Warning signs:** DB coverage check shows 0 rows for tickers that "downloaded" but were actually failed.

### Pitfall 3: yfinance `multi_level_index=False` Does Not Flatten Multi-Ticker Results

**What goes wrong:** Code passes `multi_level_index=False` expecting flat columns for multi-ticker bulk download; gets `MultiIndex` anyway.
**Why it happens:** `multi_level_index=False` only affects single-ticker downloads. Multiple tickers always produce a 2-level column MultiIndex in yfinance 1.3.0.
**How to avoid:** Use `df.stack(level=1, future_stack=True)` to flatten. Set `multi_level_index=False` only for the single-ticker per-symbol retry path.
**Warning signs:** `KeyError: 'Close'` when trying to access `df['Close']` after bulk download.

### Pitfall 4: pandas-market-calendars v5 Breaking Change — pytz Removed

**What goes wrong:** Code does `from pytz import timezone; tz = timezone('America/New_York')` expecting pmc v5 to accept it — raises `AttributeError` or produces incorrect results.
**Why it happens:** pandas-market-calendars v5 (April 2025) removed pytz entirely; it now uses `zoneinfo`.
**How to avoid:** Use `zoneinfo.ZoneInfo('America/New_York')` or rely on UTC throughout. The `valid_days()` return already carries UTC timezone. The `nyse.tz` property returns `'America/New_York'` as a string for display only.
**Warning signs:** Import errors for pytz, or unexpected behavior in calendar date ranges.

### Pitfall 5: Wikipedia Table Structure Change

**What goes wrong:** Code assumes Ticker is always column 0 and Security is column 1 — a future Wikipedia edit could reorder or add columns.
**Why it happens:** Wikipedia is user-editable and the column order has changed once historically.
**How to avoid:** Check `<thead>` for column names first; locate Ticker and Security by header text, not index position. Fall back to index 0/1 if headers are ambiguous.
**Warning signs:** Symbols that look like company names, or company names that look like tickers.

### Pitfall 6: Slickcharts Bot Detection

**What goes wrong:** httpx gets 403 or a Cloudflare challenge page from slickcharts.com, and BeautifulSoup parses the error HTML silently returning zero tickers.
**Why it happens:** Slickcharts uses Cloudflare bot protection; default `python-httpx/0.28.1` User-Agent is easily detected.
**How to avoid:** Set a browser-like User-Agent header: `'Mozilla/5.0 (compatible; bensdorp1/0.1)'`. On 403, raise immediately rather than returning empty dict. Log `data_fetch_failed` audit event on any HTTP error.
**Warning signs:** Discrepancy count of 500 (all tickers flagged as different — means Slickcharts returned empty).

### Pitfall 7: `^GSPC` in Ticker Normalization

**What goes wrong:** `_to_yfinance('^GSPC')` returns `'^GSPC'` — correct, no change. But `_to_db('^GSPC')` also returns `'^GSPC'` — correct. The pitfall is forgetting to always include `^GSPC` in the download list before normalization.
**Why it happens:** `^GSPC` is not a constituent but is required. Easy to add it only to the constituents download and forget it on incremental refresh.
**How to avoid:** In `prices.py`, always append `'^GSPC'` to the ticker list before calling yfinance, regardless of the constituent list.

---

## Code Examples

### Stacking yfinance MultiIndex (Verified Pattern)

```python
# Source: VERIFIED in project venv, yfinance 1.3.0, 2026-05-23
import yfinance as yf
import pandas as pd

df = yf.download(
    ["AAPL", "MSFT", "BRK-B"],
    start="2025-01-02",
    end="2025-01-10",
    auto_adjust=True,
    progress=False,
)
# df.columns is a 2-level MultiIndex: (Price, Ticker)
stacked = df.stack(level=1, future_stack=True)
# stacked.index.names == ['Date', 'Ticker']
# stacked.columns == ['Close', 'High', 'Low', 'Open', 'Volume']

# Convert to DB rows
rows = []
for (date_idx, ticker), row in stacked[["Close", "Volume"]].iterrows():
    if pd.isna(row["Close"]):
        continue  # skip failed downloads
    rows.append({
        "symbol": ticker.replace("-", "."),  # BRK-B -> BRK.B
        "trade_date": date_idx.to_pydatetime().replace(tzinfo=UTC),
        "close": float(row["Close"]),
        "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
    })
```

### BeautifulSoup lxml Parser (Verified Pattern)

```python
# Source: VERIFIED in project venv, bs4 4.14.3 + lxml 6.1.1, 2026-05-23
from bs4 import BeautifulSoup
import httpx

def _parse_wikitable(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="wikitable")
    result: dict[str, str] = {}
    if table is None:
        return result
    for row in table.find("tbody").find_all("tr"):  # type: ignore[union-attr]
        cells = row.find_all("td")
        if len(cells) >= 2:
            symbol = cells[0].get_text(strip=True)
            name = cells[1].get_text(strip=True)
            if symbol:
                result[symbol] = name
    return result
```

### pandas-market-calendars v5 API (Verified Pattern)

```python
# Source: VERIFIED in project venv, pandas-market-calendars 5.3.2, 2026-05-23
import pandas_market_calendars as mcal
import pandas as pd
from datetime import date

_NYSE = mcal.get_calendar("NYSE")

# Get 220+ trading days ending today
from datetime import timedelta
today = date.today()
start = today - timedelta(days=350)  # ~240 trading days
days: pd.DatetimeIndex = _NYSE.valid_days(
    start_date=start.isoformat(),
    end_date=today.isoformat(),
)
# days.dtype == datetime64[us, UTC]
# len(days) == ~240 (covers 220 required)
# days[-220] is the date 220 trading days ago
```

### SQLAlchemy Core ON CONFLICT DO NOTHING (Verified Pattern)

```python
# Source: VERIFIED in project venv, SQLAlchemy 2.0.49, 2026-05-23
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from bensdorp1.db.schema import price_daily

with engine.connect() as conn:
    stmt = (
        sqlite_insert(price_daily)
        .values(rows)  # list of dicts with datetime trade_date values
        .on_conflict_do_nothing(index_elements=["symbol", "trade_date"])
    )
    conn.execute(stmt)
    conn.commit()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `df['Adj Close']` for adjusted data | `df['Close']` with `auto_adjust=True` | yfinance 0.2+ | Simpler column access; all columns already adjusted |
| `df.stack(level=1)` | `df.stack(level=1, future_stack=True)` | pandas 2.1+ | Suppresses `FutureWarning` about default behavior change |
| `mcal.get_calendar('NYSE').tz` returning pytz object | Returns string `'America/New_York'` | pmc v5 (Apr 2025) | Cannot use as pytz timezone; use `zoneinfo.ZoneInfo` if needed |
| `requests` for HTTP | `httpx` | Project decision (CLAUDE.md) | Typed stubs included; modern async-capable design |

**Deprecated/outdated:**
- `pytz` with pandas-market-calendars: removed in v5; replaced by stdlib `zoneinfo`
- `df['Adj Close']`: replaced by `df['Close']` when `auto_adjust=True` (yfinance auto-renames)
- `yf.download(..., group_by='ticker')`: still works but `df.stack()` on default column layout is more predictable

---

## pyproject.toml Changes Required

Three changes needed before Wave 0 is complete:

**1. lxml runtime dependency (ALREADY DONE by this research session):**
```toml
# Already in [project.dependencies]:
"lxml>=6.1.1",
```

**2. lxml-stubs dev dependency (Wave 0 task):**
```toml
[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-cov>=7.1.0",
    "hypothesis>=6.130",
    "ruff>=0.15",
    "mypy>=2.1.0",
    "lxml-stubs>=0.5.1",   # ADD: type stubs for lxml
]
```

**3. mypy overrides for untyped third-party modules (Wave 0 task):**
```toml
[[tool.mypy.overrides]]
module = "yfinance"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "pandas_market_calendars"
ignore_missing_imports = true
```

Note: `bs4` (beautifulsoup4) ships `py.typed` — no override needed. `httpx` ships inline types — no override needed. `lxml` needs `lxml-stubs` in dev deps, not an `ignore_missing_imports` override. [VERIFIED: mypy 2.1.0 tested on each module 2026-05-23]

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 3 |
|-----------|-------------------|
| `yfinance>=1.3.0` with `auto_adjust=True` explicit | Must always pass `auto_adjust=True` to `yf.download()` |
| MultiIndex fix: `df.stack(level=1, future_stack=True)` | Use this pattern, not `multi_level_index=False`, for multi-ticker bulk downloads |
| `pandas-market-calendars>=5.3.2` (v5 uses zoneinfo) | No pytz imports in calendar.py |
| `beautifulsoup4>=4.14.3` — import as `bs4`; pair with `lxml` | Use `"lxml"` as parser string in BeautifulSoup constructor |
| `pathlib.Path` throughout | No string path concatenation in data/ |
| `-> None` on every function | All module-level functions need explicit return annotations |
| No circular imports | `data/` must NOT import from `_app.py` or `commands/` |
| PEP 735 `[dependency-groups]` | New dev deps go in `[dependency-groups]`, NOT `[tool.uv.dev-dependencies]` |
| mypy strict throughout | Need overrides for yfinance and pandas_market_calendars |
| SQLAlchemy Core (not ORM) | `insert()`, `select()`, `delete()` — no `Session`, no mapped classes |
| ruff lint rules: E, F, I, UP, B, C4, PT | No TC rules selected — SQLAlchemy imports stay at module level (safe) |
| No extensibility design | Implement exactly what DATA-01 through DATA-10 require; no pluggable scrapers |
| Single-user, no concurrency | Simple threading.Lock not needed in data layer |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Slickcharts ticker list is accessible via plain HTTP GET with a browser User-Agent | Pitfall 6, Pattern 7 | If Cloudflare blocks all Python clients, Slickcharts cross-check fails entirely; DATA-02 discrepancy check would always show max discrepancy (500) |
| A2 | Wikipedia's S&P 500 table keeps Symbol in column 0 and Security in column 1 | Pattern 7 | Wikipedia table structure has changed once historically; header-based lookup would be more robust |
| A3 | `^GSPC` normalize: `.replace(".", "-")` returns `"^GSPC"` (no-op) | Pattern 5 | ^GSPC has no `.` so this is safe — but verify if other index tickers with `.` are ever needed |

**If this table is empty for verified claims:** All code patterns above were verified against the installed project venv (versions listed). The three assumptions are about external service behavior that cannot be verified without live HTTP calls to Wikipedia/Slickcharts.

---

## Open Questions

1. **Slickcharts HTML table structure**
   - What we know: Slickcharts has a table of S&P 500 components at `/sp500`
   - What's unclear: The exact CSS class of the table element (not verified offline); Slickcharts may use different column ordering than Wikipedia
   - Recommendation: When implementing `constituents.py`, make a real GET to Slickcharts during development to confirm the table class and column order. The `class_='wikitable'` pattern that works for Wikipedia will NOT work for Slickcharts. [ASSUMED]

2. **yfinance rate limiting behavior in 1.3.0**
   - What we know: yfinance 1.3.0 uses `curl_cffi` internally (confirmed via pip show), which provides better anti-bot bypass than requests. The DATA-09 retry spec (3 retries, 1s/2s/4s) is the project's specified behavior.
   - What's unclear: Whether yfinance 1.3.0 has built-in rate limiting / automatic retry that might interact with the manual backoff logic
   - Recommendation: Implement the manual retry loop as specified; if yfinance raises an exception (rather than returning empty DF), the loop should also catch `Exception` and retry.

3. **Wikipedia page URL stability**
   - What we know: `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies` is the canonical URL
   - What's unclear: Wikipedia occasionally moves pages; no redirect handling tested
   - Recommendation: Use `follow_redirects=True` in httpx.Client (already the default). [ASSUMED]

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All modules | ✓ | 3.12.13 (via uv) | — |
| yfinance | prices.py | ✓ | 1.3.0 | — |
| pandas-market-calendars | calendar.py | ✓ | 5.3.2 | — |
| beautifulsoup4 | constituents.py | ✓ | 4.14.3 | — |
| lxml | constituents.py | ✓ | 6.1.1 (just added) | html.parser (slower) |
| httpx | constituents.py | ✓ | 0.28.1 | — |
| SQLAlchemy | prices.py, constituents.py | ✓ | 2.0.49 | — |
| pandas | prices.py | ✓ | 3.0.3 | — |
| numpy | prices.py | ✓ | 2.4.6 | — |
| lxml-stubs | mypy strict | ✗ | — | Add in Wave 0 |
| Network (Wikipedia) | constituents.py | ✓ (dev only) | — | Cached data |
| Network (Slickcharts) | constituents.py | ✓ (dev only) | — | Wikipedia-only with warning |
| Network (yfinance) | prices.py | ✓ (dev only) | — | Mocked in tests |

**Missing dependencies with no fallback:**
- `lxml-stubs` (dev group) — required for mypy strict to pass on any file importing lxml; add via `uv add --group dev lxml-stubs` in Wave 0

**Missing dependencies with fallback:**
- All network dependencies — tests fully mock HTTP and yfinance; no network required for CI

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (8.3+ pinned in pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_data_*.py -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Wikipedia fetch returns {symbol: name} dict | unit (mocked HTTP) | `pytest tests/test_data_constituents.py::test_fetch_wikipedia -x` | ❌ Wave 0 |
| DATA-01 | Slickcharts fetch returns set of symbols | unit (mocked HTTP) | `pytest tests/test_data_constituents.py::test_fetch_slickcharts -x` | ❌ Wave 0 |
| DATA-02 | 0-3 discrepancy: uses primary silently | unit | `pytest tests/test_data_constituents.py::test_discrepancy_silent -x` | ❌ Wave 0 |
| DATA-02 | 4-10 discrepancy: warns, uses primary | unit | `pytest tests/test_data_constituents.py::test_discrepancy_warn -x` | ❌ Wave 0 |
| DATA-02 | 11+ discrepancy: aborts buy candidates | unit | `pytest tests/test_data_constituents.py::test_discrepancy_abort -x` | ❌ Wave 0 |
| DATA-03 | yfinance called with auto_adjust=True | unit (mock) | `pytest tests/test_data_prices.py::test_download_auto_adjust -x` | ❌ Wave 0 |
| DATA-04 | 220 rows fetched for a symbol | unit (mock) | `pytest tests/test_data_prices.py::test_220_days_fetched -x` | ❌ Wave 0 |
| DATA-05 | Cache refreshes when >7 days old | unit (db_engine fixture) | `pytest tests/test_data_constituents.py::test_cache_stale_refresh -x` | ❌ Wave 0 |
| DATA-05 | Cache skips fetch when ≤7 days old | unit (db_engine fixture) | `pytest tests/test_data_constituents.py::test_cache_fresh_skip -x` | ❌ Wave 0 |
| DATA-07 | NYSE calendar excludes weekends/holidays | unit | `pytest tests/test_data_calendar.py::test_excludes_holidays -x` | ❌ Wave 0 |
| DATA-07 | n_trading_days_ago(220) returns correct date | unit | `pytest tests/test_data_calendar.py::test_n_trading_days_ago -x` | ❌ Wave 0 |
| DATA-08 | BRK.B stored in DB as BRK.B | unit (db_engine fixture) | `pytest tests/test_data_prices.py::test_ticker_normalization_period -x` | ❌ Wave 0 |
| DATA-08 | yfinance called with BRK-B (hyphen) | unit (mock) | `pytest tests/test_data_prices.py::test_ticker_normalization_yfinance -x` | ❌ Wave 0 |
| DATA-09 | Failed symbol retried 3x with backoff | unit (mock + time.sleep mock) | `pytest tests/test_data_prices.py::test_retry_backoff -x` | ❌ Wave 0 |
| DATA-10 | 95%+ coverage: scan proceeds | unit (db_engine fixture) | `pytest tests/test_data_prices.py::test_coverage_check_pass -x` | ❌ Wave 0 |
| DATA-10 | <95% coverage: raises / returns error | unit (db_engine fixture) | `pytest tests/test_data_prices.py::test_coverage_check_fail -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_data_*.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** `uv run pytest tests/ -q && uv run python -m mypy src/ && uv run ruff check src/` — all green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_data_calendar.py` — covers DATA-07 (NYSE calendar wrappers)
- [ ] `tests/test_data_constituents.py` — covers DATA-01, DATA-02, DATA-05
- [ ] `tests/test_data_prices.py` — covers DATA-03, DATA-04, DATA-08, DATA-09, DATA-10
- [ ] `tests/test_data_init.py` (optional) — covers `data/__init__.py` re-exports and public API surface
- [ ] `pyproject.toml`: add `lxml-stubs>=0.5.1` to dev dependency group
- [ ] `pyproject.toml`: add mypy overrides for `yfinance` and `pandas_market_calendars`

*(Existing `conftest.py` with `db_engine` fixture is reusable for all data tests — no new conftest needed)*

---

## Security Domain

> `security_enforcement: true` and `security_asvs_level: 1` in .planning/config.json.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in data layer |
| V3 Session Management | No | No sessions; CLI is single-user |
| V4 Access Control | No | Single-user tool; no authorization needed |
| V5 Input Validation | Yes (limited) | Ticker symbols are untrusted input from web scraping — validate format before DB insert |
| V6 Cryptography | No | No secrets or encryption in data layer |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via ticker symbol | Tampering | SQLAlchemy Core parameterized queries — `insert().values(rows)` never uses f-strings |
| Malicious HTML from Wikipedia/Slickcharts (XSS in scraping context) | Tampering | BeautifulSoup `get_text(strip=True)` strips all HTML tags; no raw HTML stored in DB |
| Ticker symbol with unusual characters (e.g., `;DROP TABLE`) | Tampering | SQLAlchemy parameterized queries prevent injection; validate ticker format with regex `r'^[A-Z.\-\^]{1,10}$'` before insert |
| Slickcharts / Wikipedia returning malformed data with 503/403 | DoS | `resp.raise_for_status()` + `D-03` stale cache fallback — never crash on network errors |
| yfinance returning unexpected data types | Tampering | `float(row['Close'])` and `int(row['Volume'])` explicit casts before DB insert; `pd.notna()` guard |

**Security note for DATA-01:** Ticker symbols scraped from external sources must be treated as untrusted input. Before inserting into `constituents_cache.symbol`, validate that the value matches the expected S&P 500 ticker pattern: uppercase letters, digits, `.`, `-`, `^`, max 10 characters. Reject malformed symbols silently with a log entry.

---

## Sources

### Primary (HIGH confidence)

- VERIFIED in project venv (yfinance 1.3.0, pandas-market-calendars 5.3.2, beautifulsoup4 4.14.3, lxml 6.1.1, httpx 0.28.1, sqlalchemy 2.0.49, pandas 3.0.3, numpy 2.4.6) — all API patterns tested by running Python code in the actual project environment, 2026-05-23
- `src/bensdorp1/db/schema.py` — price_daily and constituents_cache table definitions
- `src/bensdorp1/db/engine.py` — engine singleton pattern to mirror
- `src/bensdorp1/db/audit.py` — log_event() and AuditEventType pattern
- `tests/conftest.py` — db_engine fixture pattern to reuse
- `pyproject.toml` — verified dependency list; lxml added during research

### Secondary (MEDIUM confidence)

- `CLAUDE.md` project instructions — yfinance MultiIndex fix, auto_adjust requirement, pmc v5 pytz removal, mypy strict configuration
- `.planning/phases/03-data-sources/03-CONTEXT.md` — all locked decisions D-01 through D-05
- `.planning/REQUIREMENTS.md` — DATA-01 through DATA-10 definitions

### Tertiary (LOW confidence)

- [ASSUMED] Slickcharts HTML table structure (class name, column positions) — requires live HTTP GET to verify; not testable offline
- [ASSUMED] Wikipedia page URL stability at `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies` — confirmed working but not guaranteed permanent

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages installed and API-tested in project venv
- Architecture: HIGH — mirrors Phase 2 db/ patterns; all SQLAlchemy Core insert/select patterns verified
- yfinance API: HIGH — tested MultiIndex behavior, NaN detection, ticker normalization, ^GSPC download
- calendar.py API: HIGH — tested valid_days(), tz behavior, membership checks in pmc 5.3.2
- Pitfalls: HIGH — all pitfalls discovered by running code that failed, then fixing it
- Test patterns: HIGH — mirrors existing test_db_audit.py and test_db_schema.py patterns
- Slickcharts scraping: LOW — table structure not verified offline

**Research date:** 2026-05-23
**Valid until:** 2026-06-23 (stable libraries; yfinance API changes faster — re-verify if > 30 days)
