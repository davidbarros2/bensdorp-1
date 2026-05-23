# Phase 3: Data Sources - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 8 (4 source + 4 test)
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/bensdorp1/data/__init__.py` | package-init | re-export | `src/bensdorp1/db/__init__.py` | exact |
| `src/bensdorp1/data/calendar.py` | utility | transform (pure) | `src/bensdorp1/db/engine.py` | role-match (module-level singleton + pure functions) |
| `src/bensdorp1/data/constituents.py` | service | request-response + CRUD | `src/bensdorp1/db/audit.py` + `src/bensdorp1/db/backup.py` | role-match |
| `src/bensdorp1/data/prices.py` | service | request-response + CRUD | `src/bensdorp1/db/backup.py` + `src/bensdorp1/db/audit.py` | role-match |
| `pyproject.toml` | config | — | `pyproject.toml` (self) | exact |
| `tests/test_data_calendar.py` | test | unit | `tests/test_db_engine.py` | exact |
| `tests/test_data_constituents.py` | test | unit (mocked HTTP + db_engine) | `tests/test_db_audit.py` | exact |
| `tests/test_data_prices.py` | test | unit (mocked yfinance + db_engine) | `tests/test_db_audit.py` + `tests/test_db_backup.py` | exact |

---

## Pattern Assignments

### `src/bensdorp1/data/__init__.py` (package-init, re-export)

**Analog:** `src/bensdorp1/db/__init__.py`

**Full file pattern** (lines 1-13) — copy structure verbatim, substituting data/ symbols:

```python
"""Public surface of the bensdorp1.data subpackage."""

from bensdorp1.data.calendar import get_trading_days, is_trading_day, n_trading_days_ago
from bensdorp1.data.constituents import get_constituents, refresh_constituents
from bensdorp1.data.prices import check_price_coverage, update_price_data

__all__ = [
    "check_price_coverage",
    "get_constituents",
    "get_trading_days",
    "is_trading_day",
    "n_trading_days_ago",
    "refresh_constituents",
    "update_price_data",
]
```

**Rule:** `__all__` must list every public symbol in sorted order. No star-imports. No re-export of private helpers (prefix `_`).

---

### `src/bensdorp1/data/calendar.py` (utility, transform)

**Analog:** `src/bensdorp1/db/engine.py`

**Module-level singleton pattern** (engine.py lines 15-16) — apply to `_NYSE` calendar object:

```python
# engine.py lines 15-16
_engine: Engine | None = None
_engine_lock: threading.Lock = threading.Lock()
```

For calendar.py, the singleton is simpler — no lock needed (calendar is read-only, no mutation):

```python
import pandas_market_calendars as mcal  # type: ignore[import-untyped]

_NYSE = mcal.get_calendar("NYSE")  # module-level; created once at import
```

**Docstring pattern** (engine.py lines 1-6):

```python
"""Lazy-cached SQLAlchemy engine singleton with BENSDORP1_HOME resolution.

Depends on: bensdorp1.db.schema (metadata)
Used by: all commands that need a DB connection (via run_migrations in init command)
"""
```

Mirror structure for calendar.py:

```python
"""NYSE trading-day wrappers using pandas_market_calendars v5.

No I/O — pure computation over the NYSE holiday calendar.
Depends on: pandas_market_calendars>=5.3.2 (zoneinfo-based, no pytz)
Used by: data/prices.py, commands/scan.py (Phase 7), commands/init.py (Phase 6)
"""
```

**Return annotation pattern** (engine.py lines 50-66) — every function has explicit return type; `-> None` where applicable:

```python
def get_engine(path: Path | None = None) -> Engine:
def run_migrations(engine: Engine) -> None:
def _reset_engine_for_testing(replacement: Engine | None = None) -> None:
```

**Core function body pattern** — use RESEARCH.md Pattern 6 (verified against pmc 5.3.2):

```python
# From RESEARCH.md Pattern 6 (VERIFIED 2026-05-23)
def get_trading_days(start: date, end: date) -> pd.DatetimeIndex:
    """Return NYSE trading days between start and end (inclusive), UTC timezone."""
    return _NYSE.valid_days(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )

def is_trading_day(dt: date) -> bool:
    """Return True if dt is a NYSE trading day."""
    ts = pd.Timestamp(dt).normalize().tz_localize("UTC")
    days = get_trading_days(dt, dt)
    return ts in days

def n_trading_days_ago(n: int, reference: date | None = None) -> date:
    """Return the date that was N NYSE trading days before reference (default: today)."""
    ref = reference or date.today()
    from datetime import timedelta
    start = ref - timedelta(days=int(n * 1.5) + 30)
    days = get_trading_days(start, ref)
    if len(days) < n:
        raise ValueError(f"Not enough trading days in range for n={n}")
    return days[-n].date()
```

---

### `src/bensdorp1/data/constituents.py` (service, request-response + CRUD)

**Analogs:** `src/bensdorp1/db/audit.py` (SQLAlchemy Core insert pattern) + `src/bensdorp1/db/backup.py` (Engine parameter pattern, module docstring style)

**Module docstring pattern** (backup.py lines 1-11):

```python
"""SQLite backup primitive using sqlite3.Connection.backup().

...

Used by: every state-changing command (buy, sell, fix, cash) after each write.
"""
```

Mirror for constituents.py:

```python
"""Wikipedia/Slickcharts S&P 500 constituent fetching with 7-day cache.

DATA-01: Wikipedia primary source; Slickcharts cross-check secondary.
DATA-02: Symmetric difference > 10 aborts buy candidates; 4-10 warns; 0-3 silent.
DATA-05: constituents_cache TTL is 7 days; stale cache continues scan with warning.

Depends on: bensdorp1.db.schema (constituents_cache), bensdorp1.db.audit (log_event)
Used by: commands/scan.py (Phase 7), commands/refresh.py (Phase 10)
"""
```

**Imports pattern** — combine audit.py and backup.py import styles:

```python
import re
from datetime import UTC, datetime, timedelta

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Engine

from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.schema import constituents_cache
```

**SQLAlchemy Core insert pattern** (audit.py lines 44-63) — parameterized, no f-strings, always `conn.commit()`:

```python
# audit.py lines 54-63
with engine.connect() as conn:
    conn.execute(
        insert(audit_log).values(
            event_type=str(event_type),
            occurred_at=datetime.now(UTC),
            symbol=symbol,
            payload=json.dumps(payload) if payload is not None else None,
        )
    )
    conn.commit()
```

For constituents, the pattern adapts to DELETE + INSERT in one transaction (RESEARCH.md Pattern 9):

```python
# From RESEARCH.md Pattern 9 (VERIFIED 2026-05-23)
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

**SQLite naive datetime normalization pattern** (RESEARCH.md Pattern 8) — apply on every datetime read:

```python
# From RESEARCH.md Pattern 8 (VERIFIED 2026-05-23)
def _ensure_utc(dt: datetime) -> datetime:
    """Normalize naive datetime from SQLite read to UTC-aware."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
```

**Engine parameter style** (backup.py lines 21-32) — Engine always first positional arg, no global state:

```python
# backup.py lines 21-32
def create_backup(engine: Engine, backups_dir: Path) -> Path:
```

All public functions in constituents.py follow the same convention:

```python
def get_constituents(engine: Engine) -> dict[str, str]: ...
def refresh_constituents(engine: Engine) -> None: ...
```

**HTTP fetch pattern** (RESEARCH.md Pattern 7, VERIFIED 2026-05-23):

```python
WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_TICKER_RE = re.compile(r"^[A-Z.\-\^]{1,10}$")  # security: validate before insert

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
            if symbol and _TICKER_RE.match(symbol):
                result[symbol] = name
    return result
```

**Error handling pattern** — use `raise_for_status()` + catch `httpx.HTTPError` → emit audit event → fall through to stale cache (D-03, never hard-fail):

```python
try:
    wiki_data = _fetch_wikipedia(client)
except (httpx.HTTPError, ValueError) as exc:
    log_event(engine, AuditEventType.DATA_FETCH_FAILED, payload={"error": str(exc)})
    wiki_data = None
```

---

### `src/bensdorp1/data/prices.py` (service, request-response + CRUD)

**Analogs:** `src/bensdorp1/db/audit.py` (insert pattern) + `src/bensdorp1/db/backup.py` (Engine parameter, module docstring)

**Module docstring pattern** — mirror backup.py style:

```python
"""yfinance bulk price download with per-symbol retry and price_daily persistence.

DATA-03: yfinance.download() called with auto_adjust=True always.
DATA-04: 220 trading days required per constituent.
DATA-08: Ticker normalization: period form (BRK.B) in DB; hyphen form (BRK-B) at yfinance call site.
DATA-09: Per-symbol retry: 3 retries, exponential backoff 1s/2s/4s.
DATA-10: 95% coverage check before scan proceeds.
DATA-04: ^GSPC always included; not a constituent but required for regime filter.

Depends on: bensdorp1.db.schema (price_daily, constituents_cache), bensdorp1.db.audit
Used by: commands/init.py (Phase 6), commands/scan.py (Phase 7)
"""
```

**Imports pattern:**

```python
import time
from datetime import UTC, datetime

import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.schema import constituents_cache, price_daily
```

**SQLAlchemy Core ON CONFLICT DO NOTHING** (RESEARCH.md Pattern 4, VERIFIED 2026-05-23) — the only safe pattern for idempotent price inserts:

```python
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

**Note:** `trade_date` values MUST be `datetime` objects with `tzinfo=UTC`, not strings. `float(row["Close"])` and `int(row["Volume"])` explicit casts required before insert.

**Bulk download + stack pattern** (RESEARCH.md Pattern 1 + Code Example, VERIFIED 2026-05-23):

```python
def _download_bulk(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Return flattened DataFrame with (Date, Ticker) index, columns: Close, Volume."""
    df = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if df.empty:
        return pd.DataFrame()
    stacked: pd.DataFrame = df.stack(level=1, future_stack=True)
    return stacked[["Close", "Volume"]]
```

**Failed ticker detection pattern** (RESEARCH.md Pattern 2, VERIFIED 2026-05-23):

```python
def _find_failed_tickers(stacked: pd.DataFrame, expected: set[str]) -> set[str]:
    failed: set[str] = set()
    ticker_level = stacked.index.get_level_values("Ticker")
    for ticker in expected:
        mask = ticker_level == ticker
        if not mask.any():
            failed.add(ticker)
        elif stacked.loc[mask, "Close"].isna().all():
            failed.add(ticker)
    return failed
```

**Per-symbol retry pattern** (RESEARCH.md Pattern 3, VERIFIED 2026-05-23):

```python
def _download_with_retry(
    ticker: str, start: str, end: str, retries: int = 3
) -> pd.DataFrame:
    delays = [1.0 * (2**i) for i in range(retries)]  # [1.0, 2.0, 4.0]
    for attempt, delay in enumerate(delays):
        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=True,
            multi_level_index=False,  # safe for single ticker only
            progress=False,
        )
        if not df.empty and not df["Close"].isna().all():
            return df[["Close", "Volume"]]
        if attempt < len(delays) - 1:
            time.sleep(delay)
    return pd.DataFrame()
```

**Ticker normalization pattern** (RESEARCH.md Pattern 5, VERIFIED 2026-05-23) — two private helpers, used only in prices.py:

```python
def _to_yfinance(symbol: str) -> str:
    """Convert DB period form to yfinance hyphen form. BRK.B -> BRK-B."""
    return symbol.replace(".", "-")

def _to_db(symbol: str) -> str:
    """Convert yfinance hyphen form back to DB period form. BRK-B -> BRK.B."""
    return symbol.replace("-", ".")
```

**95% coverage check** (RESEARCH.md Pattern 10, VERIFIED 2026-05-23):

```python
def check_price_coverage(engine: Engine, required_days: int = 220) -> tuple[int, int]:
    """Return (covered_count, total_count). Caller decides whether to abort."""
    with engine.connect() as conn:
        total = conn.execute(
            select(func.count()).select_from(constituents_cache)
        ).scalar_one()
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

---

### `pyproject.toml` (config)

**Analog:** `pyproject.toml` (self — additive changes only)

**lxml-stubs dev dependency** — add to existing `[dependency-groups]` dev list (pyproject.toml lines 28-35):

```toml
[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-cov>=7.1.0",
    "hypothesis>=6.130",
    "ruff>=0.15",
    "mypy>=2.1.0",
    "lxml-stubs>=0.5.1",   # ADD: type stubs for lxml (required by mypy strict)
]
```

**mypy overrides for untyped third-party modules** — append after the existing `[[tool.mypy.overrides]]` block (pyproject.toml lines 53-55):

```toml
# Existing override (lines 53-55):
[[tool.mypy.overrides]]
module = "bensdorp1.commands.*"
disallow_untyped_decorators = false

# ADD these two blocks:
[[tool.mypy.overrides]]
module = "yfinance"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "pandas_market_calendars"
ignore_missing_imports = true
```

**Note:** `bs4` ships `py.typed` — no override. `httpx` ships inline types — no override. `lxml` itself uses `lxml-stubs` in dev deps (not `ignore_missing_imports`).

---

### `tests/test_data_calendar.py` (test, unit)

**Analog:** `tests/test_db_engine.py`

**File header pattern** (test_db_engine.py lines 1-14):

```python
"""Tests for STATE-01: engine behavior — lazy caching, path resolution, migrations.

Uses the db_engine fixture from conftest.py for tests that need a live engine.
Direct function tests use tmp_path and monkeypatch without going through the fixture.
"""

from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

import bensdorp1.db.engine as engine_module
from bensdorp1.db.engine import run_migrations
```

Mirror for test_data_calendar.py — no db_engine needed (calendar.py is pure):

```python
"""Tests for DATA-07: NYSE calendar wrappers in data/calendar.py.

Pure computation — no db_engine fixture needed. Tests verify trading-day
exclusion, n_trading_days_ago arithmetic, and is_trading_day accuracy.
"""

import pytest
from datetime import date

from bensdorp1.data.calendar import get_trading_days, is_trading_day, n_trading_days_ago
```

**Test function signature pattern** (test_db_engine.py lines 16-20) — every test function annotated `-> None`:

```python
def test_build_engine_returns_engine(tmp_path: Path) -> None:
    """_build_engine() returns an sqlalchemy Engine instance."""
    engine = engine_module._build_engine(tmp_path / "t.db")
    assert isinstance(engine, Engine)
    engine.dispose()
```

**Parametrize pattern** (test_db_audit.py lines 16-25) — use for holiday/weekend exclusion tests:

```python
@pytest.mark.parametrize("event_type", list(AuditEventType))
def test_all_event_types_insertable(
    db_engine: Engine, event_type: AuditEventType
) -> None:
    log_event(db_engine, event_type)
```

---

### `tests/test_data_constituents.py` (test, unit with mocked HTTP + db_engine)

**Analog:** `tests/test_db_audit.py`

**File header and import pattern** (test_db_audit.py lines 1-15):

```python
"""Tests for audit.py: AuditEventType StrEnum and log_event().

Covers STATE-04: all 17 event types insertable and queryable by their string value.
"""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.schema import audit_log
```

Mirror for test_data_constituents.py — adds `unittest.mock` for HTTP:

```python
"""Tests for DATA-01, DATA-02, DATA-05: constituent fetching, discrepancy check, 7-day cache.

Uses db_engine fixture for cache TTL tests. HTTP calls are mocked via unittest.mock.patch.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from bensdorp1.data.constituents import get_constituents, refresh_constituents
from bensdorp1.db.schema import constituents_cache
```

**db_engine fixture usage pattern** (test_db_audit.py lines 17-25) — always typed as `Engine` parameter, no setup in test body:

```python
def test_all_event_types_insertable(
    db_engine: Engine, event_type: AuditEventType
) -> None:
    log_event(db_engine, event_type)
    with db_engine.connect() as conn:
        row = conn.execute(
            select(audit_log).where(audit_log.c.event_type == str(event_type))
        ).fetchone()
    assert row is not None
```

**Query-then-assert pattern** (test_db_audit.py lines 28-35) — use `select()` to verify DB state after function call:

```python
def test_log_event_with_symbol(db_engine: Engine) -> None:
    log_event(db_engine, AuditEventType.BUY_CONFIRMED, symbol="AAPL")
    with db_engine.connect() as conn:
        row = conn.execute(
            select(audit_log).where(audit_log.c.symbol == "AAPL")
        ).fetchone()
    assert row is not None
    assert row.symbol == "AAPL"  # type: ignore[union-attr]
```

---

### `tests/test_data_prices.py` (test, unit with mocked yfinance + db_engine)

**Analogs:** `tests/test_db_audit.py` (db_engine + query-then-assert) + `tests/test_db_backup.py` (multi-assertion tests)

**File header pattern** (test_db_backup.py lines 1-12):

```python
"""Tests for bensdorp1.db.backup.create_backup().

Covers STATE-02 (backup API used: sqlite3.Connection.backup(), not file copy)
and STATE-03 (timestamped backup + bensdorp1-latest.db updated).
"""

import re
import sqlite3
from pathlib import Path

from sqlalchemy.engine import Engine

from bensdorp1.db.backup import create_backup
```

Mirror for test_data_prices.py — adds mock for yfinance:

```python
"""Tests for DATA-03, DATA-04, DATA-08, DATA-09, DATA-10: price download, normalization, retry, coverage.

Uses db_engine fixture for DB-state assertions. yfinance.download is mocked via
unittest.mock.patch to avoid network calls in CI.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from bensdorp1.data.prices import check_price_coverage, update_price_data
from bensdorp1.db.schema import price_daily
```

**db_engine fixture usage** (test_db_backup.py lines 16-23):

```python
def test_backup_creates_timestamped_file(db_engine: Engine, tmp_path: Path) -> None:
    """Backup file exists with name matching bensdorp1-{date}T{time}_{us}Z.db."""
    backups_dir = tmp_path / "backups"
    result = create_backup(db_engine, backups_dir)

    assert result.exists()
    assert result.name.startswith("bensdorp1-")
```

Pattern for price tests — assert DB state via `select()` after mocked download:

```python
def test_ticker_normalization_period(db_engine: Engine) -> None:
    """DATA-08: BRK.B is stored in price_daily.symbol as BRK.B (period form)."""
    # ... mock yfinance, call update_price_data ...
    with db_engine.connect() as conn:
        rows = conn.execute(
            select(price_daily).where(price_daily.c.symbol == "BRK.B")
        ).fetchall()
    assert len(rows) > 0
```

---

## Shared Patterns

### Engine Parameter Convention
**Source:** `src/bensdorp1/db/audit.py` lines 44-49, `src/bensdorp1/db/backup.py` lines 21-32
**Apply to:** All public functions in `constituents.py` and `prices.py`

Every function that touches the DB takes `engine: Engine` as its first positional argument. No global engine state in `data/` modules — the engine is always passed in from the caller. This keeps `data/` modules testable via the `db_engine` fixture.

```python
# Pattern: engine always first, always typed
def get_constituents(engine: Engine) -> dict[str, str]: ...
def update_price_data(engine: Engine, symbols: list[str]) -> None: ...
def check_price_coverage(engine: Engine, required_days: int = 220) -> tuple[int, int]: ...
```

### SQLAlchemy Core Insert (Parameterized, No f-strings)
**Source:** `src/bensdorp1/db/audit.py` lines 54-63
**Apply to:** `constituents.py:_persist_constituents()`, `prices.py:_persist_price_rows()`

```python
# audit.py lines 54-63
with engine.connect() as conn:
    conn.execute(insert(audit_log).values(...))
    conn.commit()
```

Never use string interpolation in SQL. Always use `.values(dict)` or `.values(list_of_dicts)`.

### SQLite Naive Datetime Normalization
**Source:** RESEARCH.md Pattern 8, Pitfall 1 (VERIFIED 2026-05-23)
**Apply to:** Every datetime value read from `price_daily` or `constituents_cache` for comparison

```python
def _ensure_utc(dt: datetime) -> datetime:
    """Normalize naive datetime from SQLite read to UTC-aware."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
```

Define once as a private helper at the top of each module that reads DateTime columns.

### Module Docstring Structure
**Source:** `src/bensdorp1/db/audit.py` lines 1-5, `src/bensdorp1/db/backup.py` lines 1-11
**Apply to:** All four `data/` modules

Every module starts with a triple-quoted docstring that lists:
- One-line summary
- Requirement IDs covered (DATA-XX)
- `Depends on:` what it imports from
- `Used by:` what commands/phases call it

### `-> None` on Every Function
**Source:** `src/bensdorp1/db/engine.py` lines 69-74
**Apply to:** All functions in all `data/` modules

```python
def run_migrations(engine: Engine) -> None:
    """Create all tables idempotently."""
    metadata.create_all(engine, checkfirst=True)
```

Mypy strict (`disallow_incomplete_defs`) will reject any function without a return annotation.

### Test Function Signature
**Source:** `tests/test_db_audit.py` lines 16-25, `tests/test_db_engine.py` lines 16-20
**Apply to:** Every test function in all three test files

```python
def test_something(db_engine: Engine) -> None:
    """One-line description of what is being verified."""
    ...
```

Always `-> None`. Always a one-line docstring. `db_engine: Engine` only when the test writes/reads the database.

### Audit Event Emission
**Source:** `src/bensdorp1/db/audit.py` lines 44-63
**Apply to:** `constituents.py` (emits `CONSTITUENTS_UPDATED`, `DATA_FETCH_FAILED`, `CONSTITUENTS_DISCREPANCY`), `prices.py` (emits `DATA_FETCH_FAILED`)

```python
from bensdorp1.db.audit import AuditEventType, log_event

log_event(engine, AuditEventType.CONSTITUENTS_UPDATED, payload={"count": len(data)})
log_event(engine, AuditEventType.DATA_FETCH_FAILED, payload={"error": str(exc)})
log_event(engine, AuditEventType.CONSTITUENTS_DISCREPANCY, payload={"diff_count": n})
```

### pathlib.Path Throughout
**Source:** `src/bensdorp1/db/engine.py` lines 8-9, 19-33
**Apply to:** Any file path handling (not applicable to `data/` modules directly — they receive `Engine`, not paths)

```python
from pathlib import Path
# ...
base = Path(home_env) if home_env else Path.home() / "bensdorp1"
return base / "data" / "bensdorp1.db"
```

No string concatenation for paths. This convention is already established and must not be violated.

---

## No Analog Found

All files have close analogs. The following patterns have no existing codebase example and must rely on RESEARCH.md instead:

| File | Pattern | Reason | RESEARCH.md Source |
|------|---------|--------|--------------------|
| `data/prices.py` | `df.stack(level=1, future_stack=True)` MultiIndex flatten | No yfinance usage exists yet in codebase | Pattern 1, Code Examples section |
| `data/prices.py` | Per-symbol retry with `time.sleep()` | No retry logic exists yet in codebase | Pattern 3 |
| `data/constituents.py` | BeautifulSoup + lxml HTML parse | No HTTP scraping exists yet | Pattern 7, Code Examples section |
| `data/calendar.py` | `pandas_market_calendars` wrappers | No calendar usage exists yet | Pattern 6 |
| `tests/test_data_prices.py` | `unittest.mock.patch('yfinance.download')` | No yfinance mock exists yet | RESEARCH.md Validation Architecture |

---

## Metadata

**Analog search scope:** `src/bensdorp1/db/`, `tests/`
**Files read:** 10 (db/__init__.py, db/audit.py, db/engine.py, db/backup.py, db/schema.py, conftest.py, test_db_audit.py, test_db_schema.py, test_db_engine.py, test_db_backup.py)
**Pattern extraction date:** 2026-05-23
