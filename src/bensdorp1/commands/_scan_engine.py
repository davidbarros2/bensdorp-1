"""Scan engine: data fetch, stop updates, exit trigger detection, output rendering.

Exposes a single public entry point: run_scan(engine, *, force, console) -> str.
All business logic lives here; scan.py is a thin Typer wrapper that calls run_scan
and prints the returned string.

D-15: This module never imports typer or bensdorp1._app (engine layer only).
D-16: Internal structure: _run_preflight, _fetch_data, _update_position_stops,
      _detect_exit_triggers, _run_screening, _render_output, _persist_scan.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from typing import Any, NamedTuple

import pandas as pd
import yfinance as yf
from rich.console import Console
from rich.text import Text
from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from bensdorp1.commands.events import (
    render_composite,
    render_dividend,
    render_initial_stop_violated,
    render_market_delist,
    render_new_highest_close,
    render_regime_bear_to_bull,
    render_regime_bull_to_bear,
    render_removed_from_sp500,
    render_split_notification,
    render_stock_split,
    render_trailing_stop_violated,
)
from bensdorp1.config import DATA_DIR, MARKET_TZ
from bensdorp1.data import (
    check_price_coverage,
    get_constituents,
    get_trading_days,
    update_price_data,
)
from bensdorp1.data.prices import _to_yfinance  # DATA-08: sole normalization site
from bensdorp1.db import AuditEventType, create_backup, log_event
from bensdorp1.db.schema import (
    config as config_table,
)
from bensdorp1.db.schema import (
    positions,
    price_daily,
    scan_candidates,
    scan_exit_triggers,
    scans,
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
    format_pct,
    format_price,
    format_volume,
    render_kv_block,
    render_table,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SEPARATOR: str = "=" * 64  # matches spec §7.2 exactly — same as init.py
PRICE_FETCH_WINDOW_DAYS: int = 10  # calendar days for narrow incremental fetch
# 201 rows needed for momentum_filter (iloc[-201] = T-200 return) + 20 for the
# liquidity window (20-day avg volume). One extra row is "today" excluded from
# rolling averages, giving 221 total (IN-03).
_PRICE_ROWS_NEEDED: int = 221


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


class _OpenPosition(NamedTuple):
    """Snapshot of an open position row from the DB."""

    id: int
    symbol: str
    entry_date: datetime
    initial_stop: float
    highest_close: float
    trailing_stop: float
    entry_close: float
    shares: int
    delisted: int


class _TriggerRow(NamedTuple):
    """A scan_exit_triggers row (new or existing) for display."""

    position_id: int
    symbol: str
    reason: str
    effective_stop: float
    triggered_date: datetime
    entry_date: datetime
    close_at_trigger: float


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_scan(
    engine: Engine,
    *,
    force: bool = False,
    console: Console | None = None,
) -> str:
    """Run full scan pipeline. Returns rendered output string.

    The returned string is stored in scans.raw_output and printed by scan.py.
    console receives progress output (multi-step display); defaults to Console().
    On RuntimeError (e.g. coverage below 95%), returns the error message directly.

    Args:
        engine: SQLAlchemy engine connected to the bensdorp1 database.
        force: If True, re-run even if a scan for today already exists.
        console: Progress-output console. Defaults to Console().

    Returns:
        Rendered scan output as a plain-text string.
    """
    con: Console = console if console is not None else Console()
    capture: Console = Console(record=True, width=120)

    try:
        today: date = datetime.now(MARKET_TZ).date()
        scan_date_utc: datetime = datetime(
            today.year, today.month, today.day, tzinfo=UTC
        )

        # 1. Pre-flight: constituents, coverage, catch-up detection
        constituents, missed_days, freshness_days, last_scan_date = _run_preflight(
            engine, con, today
        )
        symbols: list[str] = list(constituents.keys())
        all_symbols: list[str] = symbols + ["^GSPC"]

        # 2. Fetch latest market data (multi_step steps [1/2] and [2/2])
        _fetch_data(engine, con, all_symbols)

        # 3. Load price DataFrames from DB (after fetch so data is fresh)
        price_dfs: dict[str, pd.DataFrame] = _load_price_dfs(
            engine, all_symbols, rows_needed=_PRICE_ROWS_NEEDED
        )

        # 4. Query open positions (closed_at IS NULL)
        open_positions = _query_open_positions(engine)

        # 4b. Detect newly delisted positions (STATE-07)
        missed_list: list[date] = [d.date() for d in missed_days]
        catch_up_events: dict[str, list[str]] = {}
        split_notifications: list[str] = []
        delisted_events = _detect_delisted_positions(
            engine, open_positions, constituents
        )
        for ev in delisted_events:
            # Extract symbol from event string (first word before double space)
            sym = ev.split("  ")[0]
            catch_up_events.setdefault(sym, []).append(ev)

        # 5. Update stop levels for missed days + today; detect exit triggers
        triggered_position_ids: dict[int, tuple[date, float, float]] = {}
        _update_position_stops(
            engine,
            open_positions,
            missed_list,
            today,
            price_dfs,
            triggered_position_ids,
            last_scan_date=last_scan_date,
            catch_up_events=catch_up_events,
            split_notifications=split_notifications,
        )

        # 5b. Template 7 (D-09): detect positions with zero price rows across ALL
        # missed days (complete market delist), only during catch-up window.
        if missed_list:
            for pos in open_positions:
                closes_on_missed = [
                    _get_close_for_day(price_dfs, pos.symbol, d) for d in missed_list
                ]
                if all(c is None for c in closes_on_missed):
                    delist_ev = render_market_delist(pos.symbol, delist_date=None)
                    catch_up_events.setdefault(pos.symbol, []).append(delist_ev)

        # Persist a temporary scan placeholder so _detect_exit_triggers can
        # reference it via FK. We will update it with raw_output in _persist_scan.
        now_utc: datetime = datetime.now(UTC)
        tmp_scan_id: int = _persist_scan_placeholder(engine, scan_date_utc, now_utc)

        # 6. Detect exit triggers (insert into scan_exit_triggers)
        new_trigger_rows: list[_TriggerRow] = _detect_exit_triggers(
            engine,
            open_positions,
            triggered_position_ids,
            tmp_scan_id,
            today,
            price_dfs,
        )

        # 7. Collect pending triggers (from prior scans, not resolved today)
        pending_trigger_rows: list[_TriggerRow] = _query_pending_triggers(
            engine, open_positions, new_trigger_rows
        )

        # 8. Run strategy screening
        available_cash: float = _get_available_cash(engine)
        regime_active, spx_close, spx_sma_200, candidates = _run_screening(
            engine, con, price_dfs, available_cash
        )

        # 9. Compute 20-day avg volumes for top-10 display
        avg_volumes: dict[str, int] = _compute_avg_volumes(price_dfs)

        # 10. Render output to capture console
        _render_output(
            capture,
            today,
            regime_active,
            spx_close,
            spx_sma_200,
            new_trigger_rows,
            pending_trigger_rows,
            candidates,
            available_cash,
            catch_up_events,
            avg_volumes,
            missed_days=missed_list,
            open_positions_count=len(open_positions),
            split_notifications=split_notifications,
        )

        raw_output: str = capture.export_text()

        # 11. Persist scan record (update placeholder with full data)
        _persist_scan(
            engine,
            scan_date_utc,
            tmp_scan_id,
            regime_active,
            raw_output,
            candidates,
            new_trigger_rows,
            constituents,
            spx_close,
            spx_sma_200,
            freshness_days,
            force,
            now_utc,
        )

        # 12. Audit events + backup
        # CATCH_UP_PERFORMED: logged once per absence (Pitfall 5: len >= 1 means
        # at least 2 elapsed trading days, satisfying spec §7.6 "N >= 2" threshold)
        if len(missed_list) >= 1:
            log_event(
                engine,
                AuditEventType.CATCH_UP_PERFORMED,
                payload={
                    "missed_days": len(missed_list),
                    "start_date": missed_list[0].isoformat(),
                    "end_date": missed_list[-1].isoformat(),
                },
            )
        log_event(
            engine,
            AuditEventType.SCAN_PERFORMED,
            payload={
                "scan_id": tmp_scan_id,
                "scan_date": today.isoformat(),
                "regime": "bull" if regime_active else "bear",
                "spx_close": spx_close,
                "spx_sma_200": spx_sma_200,
                "constituents_count": len(symbols),
                "buy_candidates_count": len(candidates),
                "exit_triggers_count": len(new_trigger_rows),
                "constituents_freshness_days": freshness_days,
            },
        )
        create_backup(engine, DATA_DIR / "backups")

        return raw_output

    except RuntimeError as exc:
        return str(exc)


# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------


def _run_preflight(
    engine: Engine,
    con: Console,
    today: date,
) -> tuple[dict[str, str], pd.DatetimeIndex, int, date | None]:
    """Run pre-flight checks and return execution context.

    Returns:
        (constituents, missed_days, freshness_days, last_scan_date)

    Pitfall 7: last_scan_date is now returned so _apply_splits can compute the
    D-05 split window start. last_scan_date is None if no prior scan exists.

    Phase 11: catch_up_notes dropped — the catch-up summary block rendered by
    _render_output() replaces it entirely (D-04).
    """
    # 1. Constituents freshness check (D-14)
    constituents, freshness_days = _get_constituents_with_freshness(engine)

    # 2. Price coverage check
    covered, total = check_price_coverage(engine)
    if total > 0 and covered / total < 0.95:
        raise RuntimeError(
            f"Price coverage below 95%: {covered}/{total}. "
            "Run `bensdorp1 init` or wait for next scan."
        )

    # 3. Catch-up detection (D-08)
    missed_days: pd.DatetimeIndex = pd.DatetimeIndex([])
    last_scan_date: date | None = None

    with engine.connect() as conn:
        row = conn.execute(
            select(scans.c.scan_date).order_by(scans.c.scan_date.desc()).limit(1)
        ).fetchone()

    if row is not None:
        last_scan_date = row.scan_date.date()
        yesterday: date = today - timedelta(days=1)
        start_of_window: date = last_scan_date + timedelta(days=1)
        if start_of_window <= yesterday:
            missed_days = get_trading_days(start_of_window, yesterday)

    return constituents, missed_days, freshness_days, last_scan_date


def _get_constituents_with_freshness(engine: Engine) -> tuple[dict[str, str], int]:
    """Return (constituents_dict, freshness_days).

    Calls get_constituents(engine) which handles the staleness check and refresh
    internally. Freshness_days is computed from DB after the call.
    """
    from bensdorp1.db.schema import (  # local to avoid circular at module init
        constituents_cache as cc_table,
    )

    constituents: dict[str, str] = get_constituents(engine)

    # Compute freshness: days since most recent fetched_at in constituents_cache
    with engine.connect() as conn:
        row = conn.execute(
            select(cc_table.c.fetched_at)
            .order_by(cc_table.c.fetched_at.desc())
            .limit(1)
        ).fetchone()

    freshness_days: int = 0
    if row is not None:
        fetched_at: datetime = row.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        freshness_days = (datetime.now(UTC) - fetched_at).days

    return constituents, freshness_days


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------


def _fetch_data(
    engine: Engine,
    con: Console,
    all_symbols: list[str],
) -> None:
    """Fetch latest market data for all symbols with multi_step progress.

    Steps [1/2] Fetching and [2/2] Computing signals are both declared here so
    the multi_step context closes cleanly. Actual strategy computation is done
    in _run_screening (called after this function returns) but the step [2/2]
    header and done line are emitted here.

    Per D-12: narrow 10-day window. Per D-13: bulk call then per-symbol advance.
    """
    n_constituents: int = len(all_symbols) - 1  # exclude ^GSPC

    with feedback.multi_step(2, console=con) as ms:
        # Step [1/2] — Fetch latest market data
        with ms.step("Fetching latest market data", total=len(all_symbols)) as track:
            assert isinstance(track, TrackContext), (
                f"Expected TrackContext from ms.step(total=...), got {type(track)!r}"
            )
            update_price_data(
                engine,
                all_symbols,
                start=date.today() - timedelta(days=PRICE_FETCH_WINDOW_DAYS),
                end=date.today(),
            )
            for symbol in all_symbols:
                track.advance(symbol)

        # Print detail AFTER the with-block exits (Pitfall 4 — never inside)
        con.print(
            Text(f"      Constituents fetched: {n_constituents}/{n_constituents}")
        )
        con.print()

        # Step [2/2] — Computing signals (no-op spinner; actual work after this fn)
        with ms.step("Computing signals") as spinner:
            assert not isinstance(spinner, TrackContext)
            spinner.tick()


def _load_price_dfs(
    engine: Engine,
    symbols: list[str],
    rows_needed: int = 221,
) -> dict[str, pd.DataFrame]:
    """Load price DataFrames from price_daily for the given symbols.

    Per Pitfall 1: always load from DB (lowercase columns), not from yfinance.
    Per Pitfall 2: trade_date is UTC DateTime; callers normalize with .date().

    Args:
        engine: SQLAlchemy engine.
        symbols: List of ticker symbols (including ^GSPC).
        rows_needed: Minimum rows required; tail(rows_needed) is taken.

    Returns:
        Dict of symbol -> DataFrame with columns [trade_date, close, volume].
        Only symbols with data are included.
    """
    result: dict[str, pd.DataFrame] = {}
    with engine.connect() as conn:
        for symbol in symbols:
            rows = conn.execute(
                select(
                    price_daily.c.trade_date,
                    price_daily.c.close,
                    price_daily.c.volume,
                )
                .where(price_daily.c.symbol == symbol)
                .order_by(price_daily.c.trade_date)
            ).fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=["trade_date", "close", "volume"])
                result[symbol] = df.tail(rows_needed).reset_index(drop=True)
    return result


# ---------------------------------------------------------------------------
# Open positions query
# ---------------------------------------------------------------------------


def _query_open_positions(engine: Engine) -> list[_OpenPosition]:
    """Return all open positions (closed_at IS NULL)."""
    open_pos: list[_OpenPosition] = []
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                positions.c.id,
                positions.c.symbol,
                positions.c.entry_date,
                positions.c.initial_stop,
                positions.c.highest_close,
                positions.c.trailing_stop,
                positions.c.entry_close,
                positions.c.shares,
                positions.c.delisted,
            ).where(positions.c.closed_at == None)  # noqa: E711
        ).fetchall()
    for row in rows:
        open_pos.append(
            _OpenPosition(
                id=row.id,
                symbol=row.symbol,
                entry_date=row.entry_date,
                initial_stop=row.initial_stop,
                highest_close=row.highest_close,
                trailing_stop=row.trailing_stop,
                entry_close=row.entry_close,
                shares=row.shares,
                delisted=row.delisted,
            )
        )
    return open_pos


# ---------------------------------------------------------------------------
# Split detection (DATA-06)
# ---------------------------------------------------------------------------


def _entry_date_as_date(pos: _OpenPosition) -> date:
    """Extract the date part of pos.entry_date (handles datetime and date)."""
    ed = pos.entry_date
    return ed.date() if hasattr(ed, "date") else ed


def _apply_splits(
    engine: Engine,
    open_positions: list[_OpenPosition],
    last_scan_date: date | None,
    today: date,
    split_notifications: list[str],
    catchup_split_events: dict[str, list[str]] | None = None,
) -> list[_OpenPosition]:
    """Apply any stock splits that occurred since last scan.

    D-05: window approach — check split_date > max(entry_date, last_scan_date)
    and split_date <= today. Window advances with each scan, so a split applied
    in a prior scan falls outside the next scan's window (no re-application).
    D-06: shares = floor(shares * ratio); price fields /= ratio.
    T-11-04: ratio <= 0 guard; try/except around yf.Ticker(...).splits.

    split_notifications: System-notes notifications (§8.3 format).
    catchup_split_events: when not None, Template 5 events are appended per
        symbol for splits that occurred within the missed-days catch-up window.

    Returns the updated list (in-memory snapshots replaced at each split).
    """
    updated: list[_OpenPosition] = list(open_positions)
    for idx, pos in enumerate(updated):
        entry_d = _entry_date_as_date(pos)
        window_start: date = max(
            entry_d,
            last_scan_date if last_scan_date is not None else entry_d,
        )
        try:
            splits: Any = yf.Ticker(_to_yfinance(pos.symbol)).splits
        except Exception:
            continue  # data unavailable — skip split check for this position

        if not hasattr(splits, "empty") or splits.empty:
            continue

        # Filter: split_date > window_start AND split_date <= today (D-05)
        # splits.index is UTC-aware DatetimeIndex; extract .date() per element.
        applicable: Any = splits[
            (splits.index.map(lambda ts: ts.date()) > window_start)
            & (splits.index.map(lambda ts: ts.date()) <= today)
        ].sort_index()

        if applicable.empty:
            continue

        for split_ts, ratio in applicable.items():
            if ratio <= 0:
                continue  # T-11-04: guard against malformed / zero ratios

            split_date: date = pd.Timestamp(split_ts).date()

            before_shares: int = pos.shares
            before_entry_close: float = pos.entry_close
            before_highest_close: float = pos.highest_close
            before_initial_stop: float = pos.initial_stop
            before_trailing_stop: float = pos.trailing_stop

            new_shares: int = math.floor(pos.shares * ratio)
            new_entry_close: float = pos.entry_close / ratio
            new_highest_close: float = pos.highest_close / ratio
            new_initial_stop: float = pos.initial_stop / ratio
            new_trailing_stop: float = pos.trailing_stop / ratio

            # Persist to DB (T-11-05: parameterized query only)
            with engine.connect() as conn:
                conn.execute(
                    update(positions)
                    .where(positions.c.id == pos.id)
                    .values(
                        shares=new_shares,
                        entry_close=new_entry_close,
                        highest_close=new_highest_close,
                        initial_stop=new_initial_stop,
                        trailing_stop=new_trailing_stop,
                    )
                )
                conn.commit()

            # Audit event (T-11-07)
            log_event(
                engine,
                AuditEventType.SPLIT_APPLIED,
                symbol=pos.symbol,
                payload={
                    "split_date": split_date.isoformat(),
                    "ratio": ratio,
                    "before": {
                        "shares": before_shares,
                        "entry_close": before_entry_close,
                        "highest_close": before_highest_close,
                        "initial_stop": before_initial_stop,
                        "trailing_stop": before_trailing_stop,
                    },
                    "after": {
                        "shares": new_shares,
                        "entry_close": new_entry_close,
                        "highest_close": new_highest_close,
                        "initial_stop": new_initial_stop,
                        "trailing_stop": new_trailing_stop,
                    },
                },
            )

            # Split notification for System notes (spec §8.3)
            ratio_str: str = f"{int(ratio)}:1" if ratio == int(ratio) else f"{ratio}:1"
            split_notifications.append(
                render_split_notification(
                    pos.symbol,
                    ratio_str,
                    split_date,
                    before_shares,
                    new_shares,
                    before_entry_close,
                    new_entry_close,
                )
            )

            # Template 5 (catch-up variant) when accumulating catch-up events
            if catchup_split_events is not None:
                ev_list = catchup_split_events.setdefault(pos.symbol, [])
                ev_list.append(
                    render_stock_split(
                        pos.symbol,
                        ratio_str,
                        split_date,
                        before_shares,
                        new_shares,
                        before_entry_close,
                        new_entry_close,
                    )
                )

            # Update in-memory snapshot (carry id/symbol/entry_date/delisted)
            pos = _OpenPosition(
                id=pos.id,
                symbol=pos.symbol,
                entry_date=pos.entry_date,
                entry_close=new_entry_close,
                shares=new_shares,
                initial_stop=new_initial_stop,
                highest_close=new_highest_close,
                trailing_stop=new_trailing_stop,
                delisted=pos.delisted,
            )

        updated[idx] = pos

    return updated


# ---------------------------------------------------------------------------
# Delisting detection (STATE-07)
# ---------------------------------------------------------------------------


def _detect_delisted_positions(
    engine: Engine,
    open_positions: list[_OpenPosition],
    constituents: dict[str, str],
) -> list[str]:
    """Return catch-up event strings for newly delisted positions.

    D-11: Sets positions.delisted = 1 on first detection only (idempotent
    across subsequent scans — flag prevents re-logging). Positions already
    flagged delisted == 1 are skipped entirely.

    T-11-05: Only parameterized queries; T-11-07: POSITION_DELISTED_FROM_INDEX
    audit event with position_id payload.
    """
    events: list[str] = []
    constituent_symbols: set[str] = set(constituents.keys())

    for pos in open_positions:
        if pos.symbol in constituent_symbols:
            continue  # still in index — nothing to do
        if pos.delisted == 1:
            continue  # already flagged — D-11 set-once semantics

        # First detection: flag it
        with engine.connect() as conn:
            conn.execute(
                update(positions).where(positions.c.id == pos.id).values(delisted=1)
            )
            conn.commit()

        log_event(
            engine,
            AuditEventType.POSITION_DELISTED_FROM_INDEX,
            symbol=pos.symbol,
            payload={"position_id": pos.id},
        )

        events.append(render_removed_from_sp500(pos.symbol, removal_date=None))

    return events


# ---------------------------------------------------------------------------
# Stop updates and exit trigger detection
# ---------------------------------------------------------------------------


def _get_close_for_day(
    price_dfs: dict[str, pd.DataFrame],
    symbol: str,
    target_date: date,
) -> float | None:
    """Return close price for a symbol on a given date from in-memory DataFrame.

    Per Pitfall 2: trade_date is a UTC-aware datetime; compare via .date().
    """
    df = price_dfs.get(symbol)
    if df is None or df.empty:
        return None
    # Vectorized date comparison — avoids Python-level loop overhead (WR-03)
    dates = df["trade_date"].apply(
        lambda td: td.date() if hasattr(td, "date") else date(td.year, td.month, td.day)
    )
    mask = dates == target_date
    matched = df.loc[mask, "close"]
    if matched.empty:
        return None
    return float(matched.iloc[0])


def _update_position_stops(
    engine: Engine,
    open_positions: list[_OpenPosition],
    missed_days: list[date],
    today: date,
    price_dfs: dict[str, pd.DataFrame],
    triggered_position_ids: dict[int, tuple[date, float, float]],
    *,
    last_scan_date: date | None = None,
    catch_up_events: dict[str, list[str]] | None = None,
    split_notifications: list[str] | None = None,
) -> None:
    """Update position highest_close and trailing_stop for missed days + today.

    D-07: Once triggered, a position is frozen — no further stop updates.
    D-08: Walk each missed day chronologically, then today.
    D-17: Each scan UPDATEs the positions row for non-triggered open positions.
    D-07 (split): _apply_splits() is called first on every scan before the walk.
    D-08 (dividend): dividends fetched only when missed_days is non-empty.
    D-03: Template 3 (new highest close) collapsed to initial→final per position.
    D-10: Regime flips detected from price_daily SPX data.

    Modifies triggered_position_ids in-place to track which positions triggered.
    Accumulates per-position catch-up events in catch_up_events (if provided).
    split_notifications: caller-owned list to accumulate split System-notes entries.
    """
    # D-07: Apply splits first (before missed-days walk). When catch-up events
    # are being accumulated (missed_days non-empty), also collect Template 5
    # events directly via catchup_split_events.
    _split_notif: list[str] = (
        split_notifications if split_notifications is not None else []
    )
    catchup_split_ev: dict[str, list[str]] | None = (
        {} if (catch_up_events is not None and missed_days) else None
    )
    open_positions[:] = _apply_splits(
        engine,
        open_positions,
        last_scan_date,
        today,
        _split_notif,
        catchup_split_ev,
    )
    # Merge Template 5 split events into catch_up_events immediately
    if catchup_split_ev and catch_up_events is not None:
        for sym, evs in catchup_split_ev.items():
            catch_up_events.setdefault(sym, []).extend(evs)

    # D-10: Build SPX closes by date for regime-flip detection
    spx_df: pd.DataFrame | None = price_dfs.get("^GSPC")
    spx_closes_by_date: dict[date, float] = {}
    if spx_df is not None and not spx_df.empty:
        for _, row in spx_df.iterrows():
            td = row["trade_date"]
            d: date = td.date() if hasattr(td, "date") else td
            spx_closes_by_date[d] = float(row["close"])

    def _spx_regime_on(target_date: date) -> bool | None:
        """Return True (bull) / False (bear) / None (no data)."""
        sorted_dates = sorted(d for d in spx_closes_by_date if d <= target_date)
        if len(sorted_dates) < 200:
            return None
        closes_up_to = [spx_closes_by_date[d] for d in sorted_dates]
        sma200 = sum(closes_up_to[-200:]) / 200
        return closes_up_to[-1] > sma200

    all_days: list[date] = list(missed_days) + [today]

    # D-03: Collapse multiple Template 3 events per position → one initial→final.
    # pos.id → initial trailing_stop (before first new high during missed walk)
    initial_ts_for_new_high: dict[int, float] = {}
    had_new_high: dict[int, bool] = {}
    final_new_high_date: dict[int, date] = {}
    final_new_high_close: dict[int, float] = {}
    final_new_ts: dict[int, float] = {}

    # D-10: Track prev-day regime for regime-flip detection during missed days
    prev_regime: bool | None = None
    if missed_days and last_scan_date is not None:
        prev_regime = _spx_regime_on(last_scan_date)

    # D-08 (dividends): fetch once per position, only when missed_days non-empty
    dividends_by_symbol: dict[str, Any] = {}
    if missed_days and catch_up_events is not None:
        for pos in open_positions:
            try:
                divs: Any = yf.Ticker(_to_yfinance(pos.symbol)).dividends
                dividends_by_symbol[pos.symbol] = divs
            except Exception:
                pass

    regime_events_emitted: dict[date, str] = {}

    for day in all_days:
        # D-10: Detect regime flip (missed days only)
        if catch_up_events is not None and day in missed_days:
            cur_regime = _spx_regime_on(day)
            if cur_regime is not None and prev_regime is not None:
                if prev_regime and not cur_regime:
                    regime_events_emitted[day] = render_regime_bull_to_bear(day)
                elif not prev_regime and cur_regime:
                    regime_events_emitted[day] = render_regime_bear_to_bull(day)
            if cur_regime is not None:
                prev_regime = cur_regime

        for idx, pos in enumerate(open_positions):
            if pos.id in triggered_position_ids:
                continue  # D-07: frozen after trigger (Pitfall 8)

            close = _get_close_for_day(price_dfs, pos.symbol, day)
            if close is None:
                continue

            new_hc: float = update_highest_close(pos.highest_close, close)
            new_ts: float = compute_trailing_stop(new_hc)
            eff_stop: float = compute_effective_stop(pos.initial_stop, new_ts)

            if is_exit_triggered(close, eff_stop):
                # CR-02/WR-04: store actual trigger day, close, effective stop
                triggered_position_ids[pos.id] = (day, close, eff_stop)
                # Accumulate catch-up event (missed days only)
                if catch_up_events is not None and day in missed_days:
                    ev_list = catch_up_events.setdefault(pos.symbol, [])
                    if pos.trailing_stop >= pos.initial_stop:
                        ev_list.append(
                            render_trailing_stop_violated(
                                pos.symbol, day, close, eff_stop
                            )
                        )
                    else:
                        ev_list.append(
                            render_initial_stop_violated(
                                pos.symbol, day, close, eff_stop
                            )
                        )
            else:
                # Track new-high for D-03 collapse (missed days only)
                if (
                    new_hc > pos.highest_close
                    and catch_up_events is not None
                    and day in missed_days
                ):
                    if pos.id not in had_new_high:
                        initial_ts_for_new_high[pos.id] = pos.trailing_stop
                    had_new_high[pos.id] = True
                    final_new_high_date[pos.id] = day
                    final_new_high_close[pos.id] = new_hc
                    final_new_ts[pos.id] = new_ts

                # UPDATE positions SET highest_close, trailing_stop (D-17)
                with engine.connect() as conn:
                    conn.execute(
                        update(positions)
                        .where(positions.c.id == pos.id)
                        .values(highest_close=new_hc, trailing_stop=new_ts)
                    )
                    conn.commit()
                # Update in-memory snapshot for subsequent days
                open_positions[idx] = _OpenPosition(
                    id=pos.id,
                    symbol=pos.symbol,
                    entry_date=pos.entry_date,
                    initial_stop=pos.initial_stop,
                    highest_close=new_hc,
                    trailing_stop=new_ts,
                    entry_close=pos.entry_close,
                    shares=pos.shares,
                    delisted=pos.delisted,
                )
                pos = open_positions[idx]

    if catch_up_events is not None:
        # D-03: emit collapsed Template 3 — one per position, initial→final stop
        for pos in open_positions:
            if had_new_high.get(pos.id):
                ev_list = catch_up_events.setdefault(pos.symbol, [])
                ev_list.append(
                    render_new_highest_close(
                        pos.symbol,
                        final_new_high_date[pos.id],
                        final_new_high_close[pos.id],
                        initial_ts_for_new_high[pos.id],
                        final_new_ts[pos.id],
                    )
                )

        # D-08: emit dividend events (missed_days window only)
        missed_set: set[date] = set(missed_days)
        for pos in open_positions:
            divs = dividends_by_symbol.get(pos.symbol)
            if divs is None or (hasattr(divs, "empty") and divs.empty):
                continue
            missed_start: date = (
                last_scan_date
                if last_scan_date is not None
                else _entry_date_as_date(pos)
            )
            for div_ts, div_amount in divs.items():
                div_date: date = pd.Timestamp(div_ts).date()
                if div_date > missed_start and div_date in missed_set:
                    ev_list = catch_up_events.setdefault(pos.symbol, [])
                    ev_list.append(
                        render_dividend(pos.symbol, div_date, float(div_amount))
                    )

        # D-10: store regime events under sentinel key for Plan 03 renderer
        if regime_events_emitted:
            regime_list = catch_up_events.setdefault("_regime", [])
            for d in sorted(regime_events_emitted):
                regime_list.append(regime_events_emitted[d])


def _detect_exit_triggers(
    engine: Engine,
    open_positions: list[_OpenPosition],
    triggered_position_ids: dict[int, tuple[date, float, float]],
    scan_id: int,
    today: date,
    price_dfs: dict[str, pd.DataFrame],
) -> list[_TriggerRow]:
    """Insert scan_exit_triggers rows for newly triggered positions.

    D-09: triggered_date stores the actual day the stop was hit.
    D-06: Triggers persist until confirmed closed by Phase 8 sell command.

    Returns list of _TriggerRow for today's newly detected triggers.
    """
    # Check which positions already have a scan_exit_triggers row from a
    # *different* scan. Excluding the current scan_id means that a --force
    # re-run (which calls _persist_scan to delete prior trigger rows for
    # this scan_id before re-inserting) will not suppress re-triggers.
    with engine.connect() as conn:
        existing_rows = conn.execute(
            select(scan_exit_triggers.c.position_id).where(
                scan_exit_triggers.c.scan_id != scan_id
            )
        ).fetchall()
    existing_position_ids: set[int] = {row.position_id for row in existing_rows}

    new_trigger_rows: list[_TriggerRow] = []

    for pos in open_positions:
        if pos.id not in triggered_position_ids:
            continue
        if pos.id in existing_position_ids:
            continue  # already has a trigger row from prior scan

        # Retrieve the stored (trigger_day, close, eff_stop) from the dict.
        # These values were computed in _update_position_stops and reflect the
        # actual day the stop was hit (D-09) and the correct effective stop that
        # caused the trigger (WR-04: avoids using stale pos.trailing_stop).
        trigger_day, close_at_trigger, eff_stop = triggered_position_ids[pos.id]

        # Determine reason: which stop is the binding constraint
        reason: str = (
            "Trailing stop" if pos.trailing_stop >= pos.initial_stop else "Initial stop"
        )

        # triggered_date: midnight UTC of the actual day the stop was hit (D-09)
        triggered_date_utc: datetime = datetime(
            trigger_day.year, trigger_day.month, trigger_day.day, tzinfo=UTC
        )

        # INSERT into scan_exit_triggers
        with engine.connect() as conn:
            conn.execute(
                insert(scan_exit_triggers).values(
                    scan_id=scan_id,
                    position_id=pos.id,
                    reason=reason,
                    effective_stop=eff_stop,
                    triggered_date=triggered_date_utc,
                )
            )
            conn.commit()

        new_trigger_rows.append(
            _TriggerRow(
                position_id=pos.id,
                symbol=pos.symbol,
                reason=reason,
                effective_stop=eff_stop,
                triggered_date=triggered_date_utc,
                entry_date=pos.entry_date,
                close_at_trigger=close_at_trigger,
            )
        )

    return new_trigger_rows


def _query_pending_triggers(
    engine: Engine,
    open_positions: list[_OpenPosition],
    new_trigger_rows: list[_TriggerRow],
) -> list[_TriggerRow]:
    """Return previously triggered positions not yet confirmed as closed.

    These are scan_exit_triggers rows from prior scans that are still open.
    Excludes positions that were just newly triggered (new_trigger_rows).
    """
    new_position_ids: set[int] = {r.position_id for r in new_trigger_rows}
    pos_by_id: dict[int, _OpenPosition] = {p.id: p for p in open_positions}

    pending: list[_TriggerRow] = []
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                scan_exit_triggers.c.position_id,
                scan_exit_triggers.c.reason,
                scan_exit_triggers.c.effective_stop,
                scan_exit_triggers.c.triggered_date,
            )
        ).fetchall()

    for row in rows:
        pid: int = row.position_id
        if pid in new_position_ids:
            continue  # already in today's new triggers
        pos = pos_by_id.get(pid)
        if pos is None:
            continue  # position closed or unknown
        pending.append(
            _TriggerRow(
                position_id=pid,
                symbol=pos.symbol,
                reason=row.reason,
                effective_stop=row.effective_stop,
                triggered_date=row.triggered_date,
                entry_date=pos.entry_date,
                close_at_trigger=0.0,  # not displayed for pending triggers
            )
        )

    return pending


# ---------------------------------------------------------------------------
# Available cash
# ---------------------------------------------------------------------------


def _get_available_cash(engine: Engine) -> float:
    """Read available_cash from the config table. Returns 0.0 if not set."""
    with engine.connect() as conn:
        row = conn.execute(
            select(config_table.c.value).where(config_table.c.key == "available_cash")
        ).fetchone()
    if row is None:
        return 0.0
    return float(row.value)


# ---------------------------------------------------------------------------
# Strategy screening
# ---------------------------------------------------------------------------


def _run_screening(
    engine: Engine,
    con: Console,
    price_dfs: dict[str, pd.DataFrame],
    available_cash: float,
) -> tuple[bool, float, float, list[Candidate]]:
    """Run regime + strategy filters.

    Returns (regime_active, spx_close, spx_sma_200, candidates).

    Per Pitfall 1: price_dfs already loaded from DB with lowercase column names.
    Per Pitfall 8: triggered_position_ids already computed before this runs.
    """
    spx_df: pd.DataFrame | None = price_dfs.get("^GSPC")
    if spx_df is None or spx_df.empty:
        raise RuntimeError(
            "No SPX price data available. "
            "Run `bensdorp1 init` to download price history."
        )

    # Cast to float first so spx_close, spx_sma_200, and the value passed
    # to regime_filter all use the same typed series (WR-02: avoids rounding
    # differences between integer-stored closes and float-casted closes).
    spx_closes: pd.Series[float] = spx_df["close"].astype(float)
    spx_close: float = float(spx_closes.iloc[-1])
    spx_sma_200: float = float(spx_closes.tail(200).mean())

    # Constituents only (exclude ^GSPC from filter pipeline)
    constituent_dfs: dict[str, pd.DataFrame] = {
        sym: df for sym, df in price_dfs.items() if sym != "^GSPC"
    }

    try:
        regime_active: bool = regime_filter(spx_closes)

        candidates: list[Candidate] = []

        if regime_active:
            # Filter out symbols with insufficient data before applying strategy
            # filters (WR-05: liquidity_filter requires >= 21 rows, momentum_filter
            # requires >= 201 rows; symbols with fewer rows cause ValueError).
            constituent_dfs_liquid: dict[str, pd.DataFrame] = {
                sym: df for sym, df in constituent_dfs.items() if len(df) >= 21
            }
            # Apply strategy filters in sequence
            liquid_symbols: list[str] = liquidity_filter(constituent_dfs_liquid)
            liquid_dfs: dict[str, pd.DataFrame] = {
                sym: constituent_dfs_liquid[sym]
                for sym in liquid_symbols
                if sym in constituent_dfs_liquid
                and len(constituent_dfs_liquid[sym]) >= 201
            }
            momentum_symbols: list[str] = momentum_filter(liquid_dfs)
            momentum_dfs: dict[str, pd.DataFrame] = {
                sym: liquid_dfs[sym] for sym in momentum_symbols if sym in liquid_dfs
            }
            candidates = rank_candidates(momentum_dfs, available_cash)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    return regime_active, spx_close, spx_sma_200, candidates


# ---------------------------------------------------------------------------
# Volume computation for display
# ---------------------------------------------------------------------------


def _compute_avg_volumes(
    price_dfs: dict[str, pd.DataFrame],
) -> dict[str, int]:
    """Compute 20-day average volume (T-1 through T-20) for all symbols.

    Returns dict of symbol -> avg_volume (rounded to nearest int).
    Excludes today's row (same window as liquidity_filter).
    """
    result: dict[str, int] = {}
    for symbol, df in price_dfs.items():
        if symbol == "^GSPC":
            continue
        if len(df) < 21:
            result[symbol] = 0
            continue
        excl_today = df.iloc[:-1]
        last_20 = excl_today.iloc[-20:]
        avg = float(last_20["volume"].mean())
        result[symbol] = int(avg) if not pd.isna(avg) else 0
    return result


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def _render_output(
    capture: Console,
    today: date,
    regime_active: bool,
    spx_close: float,
    spx_sma_200: float,
    today_triggers: list[_TriggerRow],
    pending_triggers: list[_TriggerRow],
    candidates: list[Candidate],
    cash: float,
    catch_up_events: dict[str, list[str]],
    avg_volumes: dict[str, int],
    *,
    missed_days: list[date] | None = None,
    open_positions_count: int = 0,
    split_notifications: list[str] | None = None,
) -> None:
    """Render all output sections to the capture console per spec §7.2.

    Section order (D-04):
    0. Catch-up summary (BEFORE regular sections, only when missed_days non-empty)
    1. Header
    2. Market regime
    3. Exit triggers (today's)
    4. Pending exit triggers (if any)
    5. Buy candidates (if bull market)
    6. System notes

    catch_up_events: dict[str, list[str]] — per-position accumulated events.
      Sentinel key "_regime" holds regime-change event strings (not per-position).
    missed_days: calendar of missed trading days (for absence header).
    open_positions_count: total open positions count (for summary line).
    split_notifications: System-notes split entries (§8.3 format).
    """
    _missed: list[date] = missed_days if missed_days is not None else []
    _split_notif: list[str] = (
        split_notifications if split_notifications is not None else []
    )

    # 0. Catch-up summary block (D-04: BEFORE regular sections)
    # Only emitted when at least one trading day was missed (Pitfall 5).
    if _missed:
        n_days = len(_missed)
        start_str = _missed[0].isoformat()
        end_str = _missed[-1].isoformat()

        capture.print(Text(SEPARATOR))
        capture.print(Text("Catch-up summary"))
        capture.print(Text(SEPARATOR))
        capture.print()
        capture.print(
            Text(
                f"You were absent for {n_days} trading "
                f"{'day' if n_days == 1 else 'days'} "
                f"({start_str} to {end_str})."
            )
        )
        capture.print()
        capture.print(
            Text(
                f"State has been updated for {open_positions_count} open "
                f"{'position' if open_positions_count == 1 else 'positions'}."
            )
        )
        capture.print()

        # Per-position entries (D-01: silent if 0 events; D-02: composite if >=2)
        # Regime events under sentinel "_regime" are system-level, not per-position.
        position_symbols = [k for k in catch_up_events if k != "_regime"]
        for sym in position_symbols:
            evs = catch_up_events[sym]
            if not evs:
                continue  # D-01: silent
            if len(evs) == 1:
                capture.print(Text(evs[0]))
            else:
                # D-02: composite — one entry per position with bullets
                capture.print(Text(render_composite(sym, evs)))
            capture.print()

        # Regime events (Templates 8-9) — system-level, shown after per-position
        regime_evs = catch_up_events.get("_regime", [])
        for rev in regime_evs:
            capture.print(Text(rev))
            capture.print()

        # Retroactive pending-triggers table — show missed-day triggers still pending
        # Build from today_triggers (new triggers from today's scan); these originated
        # on missed days (triggered_date < today) and are "still pending" per spec §7.6.
        retro_rows: list[_TriggerRow] = [
            tr for tr in today_triggers if tr.triggered_date.date() < today
        ]
        if retro_rows:
            capture.print(
                Text(
                    "The following retroactive exit triggers are still pending. "
                    "They will\nalso appear in today's scan output below."
                )
            )
            capture.print()
            retro_table_rows: list[list[str]] = []
            for tr in retro_rows:
                retro_table_rows.append(
                    [
                        str(tr.symbol),
                        format_date(tr.triggered_date.date()),
                        str(tr.reason),
                    ]
                )
            render_table(
                columns=[
                    ("Symbol", "left"),
                    ("Triggered on", "left"),
                    ("Reason", "left"),
                ],
                rows=retro_table_rows,
                console=capture,
            )
            capture.print()
            capture.print(
                Text(
                    "Confirm sells with `bensdorp1 sell SYMBOL PRICE` as soon as "
                    "you execute\nthem at market open."
                )
            )
            capture.print()

    # System-notes list (separate from catch-up events — bear market note lives here)
    system_notes: list[str] = []

    # 1. Header
    capture.print(Text(SEPARATOR))
    capture.print(Text(f"Scan for {format_date(today)}"))
    capture.print(Text(SEPARATOR))
    capture.print()

    # 2. Market regime section
    # SPX values use plain number format per spec §7.2 (no $ sign)
    capture.print(Text("Market regime"))
    capture.print(Text("-" * len("Market regime")))
    regime_label: str = (
        "Bull market (close above SMA 200)"
        if regime_active
        else "Bear market (close below SMA 200)"
    )
    render_kv_block(
        {
            "S&P 500 close": f"{spx_close:,.2f}",
            "S&P 500 SMA 200": f"{spx_sma_200:,.2f}",
            "Regime": regime_label,
        },
        capture,
    )
    capture.print()

    # 3. Exit triggers — today's newly detected triggers
    if today_triggers:
        capture.print(Text("Exit triggers"))
        capture.print(Text("-" * len("Exit triggers")))
        exit_rows: list[list[str]] = []
        today_utc: date = datetime.now(UTC).date()
        for tr in today_triggers:
            entry_date_only: date = tr.entry_date.date()
            days_held: int = (today_utc - entry_date_only).days
            exit_rows.append(
                [
                    str(tr.symbol),
                    str(tr.reason),
                    format_price(tr.close_at_trigger),
                    format_price(tr.effective_stop),
                    format_days(days_held),
                ]
            )
        render_table(
            columns=[
                ("Symbol", "left"),
                ("Reason", "left"),
                ("Close", "right"),
                ("Effective stop", "right"),
                ("Days held", "right"),
            ],
            rows=exit_rows,
            console=capture,
        )
        capture.print()
        n_triggers: int = len(today_triggers)
        trigger_word: str = "exit trigger" if n_triggers == 1 else "exit triggers"
        both_or_this: str = "Both" if n_triggers > 1 else "This"
        capture.print(
            Text(f"{both_or_this} {trigger_word} will execute at the next market open.")
        )
        capture.print(
            Text("Confirm sells with `bensdorp1 sell SYMBOL PRICE` after execution.")
        )
        capture.print()

    # 4. Pending exit triggers from previous scans
    if pending_triggers:
        pending_title: str = "Pending exit triggers from previous scans"
        capture.print(Text(pending_title))
        capture.print(Text("-" * len(pending_title)))
        capture.print(
            Text(
                "The following exit triggers were generated in previous scans "
                "and have not yet been confirmed as closed:"
            )
        )
        capture.print()
        pending_rows: list[list[str]] = []
        for tr in pending_triggers:
            triggered_on: str = format_date(tr.triggered_date.date())
            pending_rows.append(
                [
                    str(tr.symbol),
                    triggered_on,
                    str(tr.reason),
                    format_price(tr.effective_stop),
                ]
            )
        render_table(
            columns=[
                ("Symbol", "left"),
                ("Triggered on", "left"),
                ("Reason", "left"),
                ("Original stop", "right"),
            ],
            rows=pending_rows,
            console=capture,
        )
        if len(pending_triggers) == 1:
            sym_str: str = str(pending_triggers[0].symbol)
            capture.print(
                Text(f"Run `bensdorp1 sell {sym_str} PRICE` to confirm the exit.")
            )
        else:
            capture.print(
                Text("Run `bensdorp1 sell SYMBOL PRICE` to confirm each exit.")
            )
        capture.print()

    # 5. Buy candidates (bull market only — D-21)
    if regime_active:
        # 5a. Top 10 table (all candidates, always shown in bull market)
        capture.print(Text("Buy candidates (top 10)"))
        capture.print(Text("-" * len("Buy candidates (top 10)")))
        top10_rows: list[list[str]] = []
        for idx, c in enumerate(candidates, start=1):
            vol: int = avg_volumes.get(c["symbol"], 0)
            top10_rows.append(
                [
                    str(idx),
                    str(c["symbol"]),
                    format_price(c["prev_close"]),
                    format_pct(c["roc_200"]),
                    format_volume(vol),
                ]
            )
        render_table(
            columns=[
                ("Rank", "right"),
                ("Symbol", "left"),
                ("Close", "right"),
                ("ROC 200d", "right"),
                ("Volume (avg 20d)", "right"),
            ],
            rows=top10_rows,
            console=capture,
        )
        capture.print()

        # 5b. Affordable candidates (position_size > 0 per D-20)
        affordable_header: str = (
            f"Buy candidates affordable (cash: {format_price(cash)})"
        )
        capture.print(Text(affordable_header))
        capture.print(Text("-" * len(affordable_header)))
        affordable: list[Candidate] = [c for c in candidates if c["position_size"] > 0]
        if not affordable:
            # D-22: all candidates have position_size == 0
            capture.print(
                Text(
                    "No affordable candidates at current cash level "
                    f"({format_price(cash)})."
                )
            )
        else:
            affordable_rows: list[list[str]] = []
            for idx, c in enumerate(candidates, start=1):
                if c["position_size"] > 0:
                    affordable_rows.append(
                        [
                            str(idx),
                            str(c["symbol"]),
                            format_price(c["prev_close"]),
                            format_pct(c["roc_200"]),
                            str(c["position_size"]),
                        ]
                    )
            render_table(
                columns=[
                    ("Rank", "right"),
                    ("Symbol", "left"),
                    ("Close", "right"),
                    ("ROC 200d", "right"),
                    ("Shares to buy", "right"),
                ],
                rows=affordable_rows,
                console=capture,
            )
        capture.print()
    else:
        # D-21: Bear market — add note to system notes (NOT catch-up summary)
        system_notes.append("Regime: Bear market. No buy candidates generated.")

    # 6. System notes
    capture.print(Text("System notes"))
    capture.print(Text("-" * len("System notes")))
    # Split notifications from _apply_splits (spec §8.3 format)
    for notif in _split_notif:
        system_notes.append(notif)
    if system_notes:
        for note in system_notes:
            capture.print(Text(note))
    else:
        capture.print(Text("No system notes."))
    capture.print(Text("Constituents list verified successfully."))
    capture.print()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _persist_scan_placeholder(
    engine: Engine,
    scan_date_utc: datetime,
    now_utc: datetime,
) -> int:
    """Insert a minimal scans row to obtain a scan_id for FK references.

    Returns the inserted (or existing) scan_id.
    Uses ON CONFLICT DO UPDATE so --force and same-day re-runs work (D-02).
    """
    stmt = (
        sqlite_insert(scans)
        .values(
            scan_date=scan_date_utc,
            regime_active=False,
            candidate_count=0,
            exit_trigger_count=0,
            raw_output=None,
            created_at=now_utc,
        )
        .on_conflict_do_update(
            index_elements=["scan_date"],
            set_={
                "created_at": now_utc,
            },
        )
    )
    result_scan_id: int | None = None
    with engine.connect() as conn:
        result = conn.execute(stmt)
        conn.commit()
        pk = result.inserted_primary_key
        if pk is not None:
            result_scan_id = int(pk[0])

    if result_scan_id is None:
        # ON CONFLICT path: fetch existing id
        with engine.connect() as conn:
            row = conn.execute(
                select(scans.c.id).where(scans.c.scan_date == scan_date_utc)
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to obtain scan_id after upsert.")
        result_scan_id = int(row.id)

    return result_scan_id


def _persist_scan(
    engine: Engine,
    scan_date_utc: datetime,
    scan_id: int,
    regime_active: bool,
    raw_output: str,
    candidates: list[Candidate],
    new_trigger_rows: list[_TriggerRow],
    constituents: dict[str, str],
    spx_close: float,
    spx_sma_200: float,
    freshness_days: int,
    force: bool,
    now_utc: datetime,
) -> None:
    """Finalize the scans row with full data; persist scan_candidates.

    Uses ON CONFLICT DO UPDATE so --force and same-day re-runs work (D-02).
    Deletes existing scan_candidates for this scan_id before re-inserting.
    """
    # Update the scans row with final data
    stmt = (
        sqlite_insert(scans)
        .values(
            scan_date=scan_date_utc,
            regime_active=regime_active,
            candidate_count=len(candidates),
            exit_trigger_count=len(new_trigger_rows),
            raw_output=raw_output,
            created_at=now_utc,
        )
        .on_conflict_do_update(
            index_elements=["scan_date"],
            set_={
                "regime_active": regime_active,
                "candidate_count": len(candidates),
                "exit_trigger_count": len(new_trigger_rows),
                "raw_output": raw_output,
            },
        )
    )
    with engine.connect() as conn:
        conn.execute(stmt)
        conn.commit()

    # Delete existing scan_exit_triggers for this scan_id when force=True,
    # so _detect_exit_triggers can re-trigger positions that fired in a prior
    # run of the same scan_id (CR-03: prevents silent suppression on --force).
    if force:
        with engine.connect() as conn:
            conn.execute(
                delete(scan_exit_triggers).where(
                    scan_exit_triggers.c.scan_id == scan_id
                )
            )
            conn.commit()

    # Delete existing scan_candidates for this scan_id (idempotent on --force)
    with engine.connect() as conn:
        conn.execute(
            delete(scan_candidates).where(scan_candidates.c.scan_id == scan_id)
        )
        conn.commit()

    # Insert scan_candidates rows
    if candidates:
        candidate_rows: list[dict[str, Any]] = [
            {
                "scan_id": scan_id,
                "symbol": c["symbol"],
                "rank": idx,
                "roc200": c["roc_200"],
                "close": c["prev_close"],
                "suggested_shares": c["position_size"],
            }
            for idx, c in enumerate(candidates, start=1)
        ]
        with engine.connect() as conn:
            conn.execute(insert(scan_candidates), candidate_rows)
            conn.commit()
