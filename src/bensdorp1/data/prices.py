"""yfinance bulk price download with per-symbol retry and price_daily persistence.

DATA-03: yfinance.download() always called with auto_adjust=True.
DATA-04: Default lookback is 220 NYSE trading days; computed as today minus 350
    calendar days as a buffer over weekends + holidays.
DATA-08: Ticker normalization — period form (BRK.B) stored in DB; hyphen form
    (BRK-B) used only at yfinance call site. This module is the SOLE location
    for the conversion.
DATA-09: Per-symbol retry exactly 3 attempts; sleeps 1s, 2s between them.
DATA-10: check_price_coverage returns (covered, total); caller enforces the 0.95
    threshold.
D-04: ^GSPC is always included in the download list (not a constituent but
    required for regime filter).
DATA-06: Split detection deferred to Phase 11 (Catch-Up Logic).
Depends on: bensdorp1.db.schema (price_daily, constituents_cache),
    bensdorp1.db.audit (log_event, AuditEventType).
Used by: commands/init.py (Phase 6), commands/scan.py (Phase 7).
"""

# DATA-06: Split detection deferred to Phase 11 (Catch-Up Logic)

import time
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.schema import constituents_cache, price_daily

SPX_TICKER: str = "^GSPC"
DEFAULT_LOOKBACK_DAYS: int = 350
# Sleep durations between successive attempts: applied BEFORE attempts 2 and 3.
# A 3-attempt retry loop sleeps len(BACKOFF_DELAYS) times (between attempts, not after the last).
BACKOFF_DELAYS: list[float] = [1.0, 2.0]
DEFAULT_REQUIRED_TRADING_DAYS: int = 220


def _to_yfinance(symbol: str) -> str:
    """Convert DB period form to yfinance hyphen form. BRK.B -> BRK-B."""
    return symbol.replace(".", "-")


def _to_db(symbol: str) -> str:
    """Convert yfinance hyphen form back to DB period form. BRK-B -> BRK.B."""
    return symbol.replace("-", ".")


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize naive datetime from SQLite read to UTC-aware."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _default_date_range() -> tuple[date, date]:
    """Return (start, end) covering DEFAULT_LOOKBACK_DAYS calendar days back to today.

    DEFAULT_LOOKBACK_DAYS = 350 calendar days covers ~240 NYSE trading days —
    sufficient buffer over the 220 required by DATA-04.
    """
    today = date.today()
    start = today - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    return (start, today)


def _download_bulk(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Return flattened DataFrame with (Date, Ticker) index, columns: Close[, Volume].

    Uses df.stack(level=1, future_stack=True) to flatten the multi-ticker
    MultiIndex result (multi_level_index=False does NOT flatten multi-ticker
    bulk downloads per RESEARCH Pitfall 3).
    Returns empty DataFrame if Close is absent; Volume column may be absent
    if yfinance omits it (e.g., certain index instruments).
    """
    df = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if df is None or df.empty:
        return pd.DataFrame()
    stacked: pd.DataFrame = df.stack(level=1, future_stack=True)  # type: ignore[assignment]
    available = [c for c in ["Close", "Volume"] if c in stacked.columns]
    if "Close" not in available:
        return pd.DataFrame()
    return stacked[available]


def _find_failed_tickers(
    stacked: pd.DataFrame, expected: set[str]
) -> set[str]:
    """Return tickers with all-NaN Close or entirely absent from stacked result.

    Failed bulk downloads appear as all-NaN rows — NOT as absent tickers
    (RESEARCH Pitfall 2). Both cases are detected here.
    """
    if stacked.empty:
        return set(expected)
    failed: set[str] = set()
    ticker_level = stacked.index.get_level_values("Ticker")
    for ticker in expected:
        mask = ticker_level == ticker
        if not mask.any():
            failed.add(ticker)
        elif stacked.loc[mask, "Close"].isna().all():
            failed.add(ticker)
    return failed


def _download_with_retry(
    ticker: str, start: str, end: str, retries: int = 3
) -> pd.DataFrame:
    """Download single ticker with exponential backoff. Returns empty DF on failure.

    Uses multi_level_index=False — safe for single-ticker downloads only
    (RESEARCH Pitfall 3: this flag is valid only for single-ticker calls).
    Sleeps between attempts, NOT after the final attempt.
    """
    delays = BACKOFF_DELAYS[:retries]
    for attempt, delay in enumerate(delays):
        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=True,
            multi_level_index=False,
            progress=False,
        )
        if df is not None and not df.empty and not df["Close"].isna().all():
            result: pd.DataFrame = df[["Close", "Volume"]]
            return result
        if attempt < len(delays) - 1:
            time.sleep(delay)
    return pd.DataFrame()


def _stacked_to_rows(stacked: pd.DataFrame) -> list[dict[str, object]]:
    """Convert stacked (Date, Ticker) MultiIndex DataFrame to list of price row dicts.

    Skips rows with NaN Close. Converts all values with explicit casts per
    RESEARCH Security Domain — never trust pandas dtype directly.
    """
    rows: list[dict[str, object]] = []
    for idx, row in stacked.iterrows():
        if pd.isna(row["Close"]):
            continue
        # idx is a tuple (date_idx, ticker_yf) from the (Date, Ticker) MultiIndex
        idx_tuple = idx if isinstance(idx, tuple) else (idx, "")
        date_idx = idx_tuple[0]
        ticker_yf = idx_tuple[1]
        if hasattr(date_idx, "to_pydatetime"):
            dt: datetime = date_idx.to_pydatetime()
        else:
            ts = pd.Timestamp(str(date_idx))
            dt = ts.to_pydatetime()
        vol_raw = row["Volume"] if "Volume" in row.index else None
        rows.append(
            {
                "symbol": _to_db(str(ticker_yf)),
                "trade_date": _ensure_utc(dt),
                "close": float(row["Close"]),
                "volume": int(vol_raw) if vol_raw is not None and pd.notna(vol_raw) else None,  # type: ignore[arg-type]
            }
        )
    return rows


def _per_symbol_to_rows(
    ticker_db: str, df: pd.DataFrame
) -> list[dict[str, object]]:
    """Convert single-ticker flat DataFrame to list of price row dicts.

    ticker_db is already in DB period form (caller passes _to_db(ticker_yf)).
    Skips rows with NaN Close. Explicit casts per RESEARCH Security Domain.
    """
    rows: list[dict[str, object]] = []
    for date_idx, row in df.iterrows():
        if pd.isna(row["Close"]):
            continue
        if hasattr(date_idx, "to_pydatetime"):
            dt: datetime = date_idx.to_pydatetime()
        else:
            ts = pd.Timestamp(str(date_idx))
            dt = ts.to_pydatetime()
        rows.append(
            {
                "symbol": ticker_db,
                "trade_date": _ensure_utc(dt),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
            }
        )
    return rows


def _persist_price_rows(engine: Engine, rows: list[dict[str, object]]) -> None:
    """Upsert price rows into price_daily. Silently ignores duplicates.

    Uses ON CONFLICT DO NOTHING on (symbol, trade_date) unique index —
    idempotent re-runs do not duplicate rows.
    """
    if not rows:
        return
    with engine.connect() as conn:
        stmt = sqlite_insert(price_daily).values(rows).on_conflict_do_nothing(
            index_elements=["symbol", "trade_date"]
        )
        conn.execute(stmt)
        conn.commit()


def update_price_data(
    engine: Engine,
    symbols: list[str],
    start: date | None = None,
    end: date | None = None,
) -> None:
    """Download prices for symbols (+^GSPC always); persist into price_daily.

    On any ticker exhausting 3 retries, emit DATA_FETCH_FAILED audit event.
    Symbols are DB period form (BRK.B); _to_yfinance converts to hyphen form
    only at yfinance call site. Default date range: today minus ~350 calendar
    days through today (covers 220 trading days with buffer).
    """
    if start is None and end is None:
        start, end = _default_date_range()
    elif start is None or end is None:
        raise ValueError(
            "update_price_data requires both start and end, or neither."
        )

    # D-04: ^GSPC ALWAYS included regardless of constituents list
    db_set: set[str] = set(symbols) | {SPX_TICKER}
    yf_tickers = sorted({_to_yfinance(s) for s in db_set})
    expected_yf = set(yf_tickers)

    stacked = _download_bulk(yf_tickers, start.isoformat(), end.isoformat())
    rows = _stacked_to_rows(stacked)

    failed_yf = _find_failed_tickers(stacked, expected_yf)
    for ticker in sorted(failed_yf):
        df = _download_with_retry(ticker, start.isoformat(), end.isoformat())
        if df.empty:
            log_event(
                engine,
                AuditEventType.DATA_FETCH_FAILED,
                symbol=_to_db(ticker),
                payload={
                    "retries": len(BACKOFF_DELAYS),
                    "attempt_delays": BACKOFF_DELAYS,
                },
            )
        else:
            rows.extend(_per_symbol_to_rows(_to_db(ticker), df))

    try:
        _persist_price_rows(engine, rows)
    except Exception as exc:
        log_event(
            engine,
            AuditEventType.DATA_FETCH_FAILED,
            payload={"source": "persist_price_rows", "error": str(exc)},
        )


def check_price_coverage(
    engine: Engine,
    required_days: int = DEFAULT_REQUIRED_TRADING_DAYS,
) -> tuple[int, int]:
    """Return (covered_count, total_count) for the 95% coverage gate (DATA-10).

    covered_count = symbols in price_daily with >= required_days rows.
    total_count = symbols in constituents_cache.
    ^GSPC is NOT counted toward total or covered (it is not a constituent).
    """
    with engine.connect() as conn:
        total: int = conn.execute(
            select(func.count()).select_from(constituents_cache)
        ).scalar_one()
        # Only count constituent symbols (those in constituents_cache).
        # ^GSPC is in price_daily but NOT in constituents_cache, so it is
        # naturally excluded by the JOIN (DATA-10: constituent-only coverage).
        subq = (
            select(price_daily.c.symbol)
            .join(
                constituents_cache,
                price_daily.c.symbol == constituents_cache.c.symbol,
            )
            .group_by(price_daily.c.symbol)
            .having(func.count(price_daily.c.id) >= required_days)
            .subquery()
        )
        covered: int = conn.execute(
            select(func.count()).select_from(subq)
        ).scalar_one()
    return (covered, total)
