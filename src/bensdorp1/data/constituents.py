"""Wikipedia/Slickcharts S&P 500 constituent fetching with 7-day cache.

DATA-01: Wikipedia primary source; Slickcharts cross-check secondary.
DATA-02: Symmetric difference > 10 aborts buy candidates; 4-10 warns; 0-3 silent.
DATA-05: constituents_cache TTL is 7 days; stale cache continues scan with warning.

Depends on: bensdorp1.db.schema (constituents_cache), bensdorp1.db.audit (log_event,
    AuditEventType)
Used by: commands/scan.py (Phase 7), commands/refresh.py (Phase 10),
    commands/init.py (Phase 6 first-run)
"""

import re
from datetime import UTC, datetime, timedelta

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Engine

from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.schema import constituents_cache

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SLICKCHARTS_URL = "https://www.slickcharts.com/sp500"
USER_AGENT = "Mozilla/5.0 (compatible; bensdorp1/0.1)"
CACHE_TTL_DAYS = 7
_TICKER_RE = re.compile(r"^[A-Z.\-\^]{1,10}$")


def _validate_ticker(symbol: str) -> bool:
    """Return True only when symbol matches the expected S&P 500 ticker pattern."""
    return bool(_TICKER_RE.match(symbol))


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize naive datetime from SQLite read to UTC-aware."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _classify_discrepancy(diff_count: int) -> str:
    """Return 'silent', 'warn', or 'abort' based on symmetric-difference count.

    DATA-02: 0-3 silent, 4-10 warn, 11+ abort.
    """
    if diff_count <= 3:
        return "silent"
    elif diff_count <= 10:
        return "warn"
    else:
        return "abort"


def _fetch_wikipedia(client: httpx.Client) -> dict[str, str]:
    """Return {symbol: company_name} from Wikipedia S&P 500 table.

    Validates each symbol via _validate_ticker before adding to result.
    Raises ValueError if the wikitable is missing.
    """
    resp = client.get(WIKIPEDIA_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", class_="wikitable")
    if table is None:
        raise ValueError("Wikipedia S&P 500 wikitable not found")
    result: dict[str, str] = {}
    tbody = table.find("tbody")
    if tbody is None:
        raise ValueError("Wikipedia S&P 500 wikitable has no tbody")
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            symbol = cells[0].get_text(strip=True)
            name = cells[1].get_text(strip=True)
            if symbol and _validate_ticker(symbol):
                result[symbol] = name
    return result


def _fetch_slickcharts(client: httpx.Client) -> set[str]:
    """Return set of ticker symbols from Slickcharts S&P 500 table.

    Validates each symbol via _validate_ticker before adding to result.
    Raises ValueError if zero symbols are extracted.
    """
    resp = client.get(SLICKCHARTS_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    # Try class_="table" first (Bootstrap table class used by Slickcharts)
    # Fall back to first <table> in document per RESEARCH.md Open Question 1 [ASSUMED]
    table = soup.find("table", class_="table")
    if table is None:
        table = soup.find("table")
    result: set[str] = set()
    if table is not None:
        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody is not None else []
        for row in rows:
            cells = row.find_all("td")
            # Slickcharts column order: Rank, Company, Symbol, Weight, Price, Change
            # Symbol is column index 2 (zero-indexed)
            if len(cells) >= 3:
                symbol = cells[2].get_text(strip=True)
                if symbol and _validate_ticker(symbol):
                    result.add(symbol)
    if not result:
        raise ValueError("Slickcharts ticker table not found")
    return result


def _is_cache_stale(engine: Engine) -> bool:
    """Return True if constituents_cache is empty or last fetch was > 7 days ago."""
    with engine.connect() as conn:
        row = conn.execute(select(func.max(constituents_cache.c.fetched_at))).fetchone()
    if row is None or row[0] is None:
        return True
    latest = row[0]
    # SQLite returns naive datetime even for timezone=True columns
    latest = _ensure_utc(latest)
    return (datetime.now(UTC) - latest) > timedelta(days=CACHE_TTL_DAYS)


def _persist_constituents(engine: Engine, data: dict[str, str]) -> None:
    """Replace all constituents_cache rows with fresh data.

    DELETE+INSERT in a single transaction — atomic replacement.
    """
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


def _read_cached_constituents(engine: Engine) -> dict[str, str]:
    """Read all rows from constituents_cache and return {symbol: company_name}."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(constituents_cache.c.symbol, constituents_cache.c.company_name)
        ).fetchall()
    return {row.symbol: (row.company_name or "") for row in rows}


def refresh_constituents(engine: Engine) -> None:
    """Force-fetch from Wikipedia + Slickcharts; persist; emit audit events.

    Never hard-fails (D-03): on network errors, emits DATA_FETCH_FAILED and returns.
    Wikipedia is primary; Slickcharts is secondary (optional for cross-check).
    """
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        # Step 1: Fetch Wikipedia (primary — required)
        try:
            wiki_data = _fetch_wikipedia(client)
        except (httpx.HTTPError, ValueError) as exc:
            log_event(
                engine,
                AuditEventType.DATA_FETCH_FAILED,
                payload={"source": "wikipedia", "error": str(exc)},
            )
            return  # Cannot proceed without primary source

        # Step 2: Fetch Slickcharts (secondary — optional)
        slickcharts_set: set[str] | None = None
        try:
            slickcharts_set = _fetch_slickcharts(client)
        except (httpx.HTTPError, ValueError) as exc:
            log_event(
                engine,
                AuditEventType.DATA_FETCH_FAILED,
                payload={"source": "slickcharts", "error": str(exc)},
            )
            # Continue with persistence — secondary is optional

    # Step 3: Classify discrepancy (if both fetches succeeded)
    if slickcharts_set is not None:
        wiki_set = set(wiki_data.keys())
        diff_count = len(wiki_set ^ slickcharts_set)
        severity = _classify_discrepancy(diff_count)
        if severity != "silent":
            log_event(
                engine,
                AuditEventType.CONSTITUENTS_DISCREPANCY,
                payload={
                    "diff_count": diff_count,
                    "severity": severity,
                    "wikipedia_only": sorted(wiki_set - slickcharts_set),
                    "slickcharts_only": sorted(slickcharts_set - wiki_set),
                },
            )
    else:
        # Secondary unavailable — sentinel value (-1 means "not measured")
        severity = "silent"
        diff_count = -1

    # Step 4: Persist Wikipedia data (always primary per D-01)
    try:
        _persist_constituents(engine, wiki_data)
    except Exception as exc:
        log_event(
            engine,
            AuditEventType.DATA_FETCH_FAILED,
            payload={"source": "persist_constituents", "error": str(exc)},
        )
        return

    # Step 5: Emit CONSTITUENTS_UPDATED
    log_event(
        engine,
        AuditEventType.CONSTITUENTS_UPDATED,
        payload={
            "count": len(wiki_data),
            "discrepancy_count": diff_count,
            "discrepancy_severity": severity,
        },
    )


def get_constituents(engine: Engine) -> dict[str, str]:
    """Return {symbol: company_name} from cache; refresh if stale (>7 days).

    Never raises on network error (D-03): if refresh fails, returns whatever is cached.
    Returns empty dict only if cache was empty AND refresh failed.
    """
    if _is_cache_stale(engine):
        refresh_constituents(engine)
    return _read_cached_constituents(engine)
