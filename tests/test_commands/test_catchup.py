"""Wave-0 scaffold for Phase 11 catch-up logic tests.

All 14 tests are failing stubs until Plans 02 and 03 implement the underlying
functions. The file is importable now because:
  - events.py (Plan 01 Task 2) is already implemented.
  - _apply_splits / _detect_delisted_positions (_scan_engine Plan 02) are
    imported lazily inside each test body — not at module top — so the file
    imports cleanly before Plan 02 lands.

Requirements:
  STATE-05 — Catch-up logic for absences >= 2 trading days
  STATE-07 — Stocks delisted from S&P 500 while held
  DATA-06  — Split detection and automatic position adjustment on every scan
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine

# events.py is implemented in Plan 01 Task 2 — safe to import at module top
from bensdorp1.commands.events import (
    render_composite,
    render_initial_stop_violated,
    render_new_highest_close,
    render_removed_from_sp500,
    render_stock_split,
    render_trailing_stop_violated,
)
from bensdorp1.commands._scan_engine import (
    _OpenPosition,
    _query_open_positions,
)
from bensdorp1.db.schema import positions


# ---------------------------------------------------------------------------
# Plan 02: Split detection (DATA-06) — 8 stubs
# ---------------------------------------------------------------------------


def test_apply_splits_math(db_engine: Engine) -> None:
    """DATA-06: _apply_splits() updates shares and price fields per D-06.

    D-06: shares = floor(shares * ratio); entry_close, highest_close,
    initial_stop, trailing_stop each /= ratio. For a 2:1 split (ratio=2.0),
    shares doubles and all price fields halve.

    Will assert:
      - open_positions[0].shares == floor(old_shares * 2)
      - open_positions[0].entry_close == approx(old_entry_close / 2)
      - positions row in DB updated accordingly
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_split_idempotent(db_engine: Engine) -> None:
    """DATA-06: Split detection is idempotent on consecutive scans (D-05 window).

    D-05: Window approach — split_date > max(entry_date, last_scan_date)
    and split_date <= today. On the second scan, last_scan_date advances
    past the split_date, so the split falls outside the window and is
    not re-applied.

    Will assert:
      - After two calls to _apply_splits() with advancing last_scan_date,
        shares and price fields are updated exactly once.
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_split_audit_event(db_engine: Engine) -> None:
    """DATA-06: Split audit event logged with before/after payload.

    _apply_splits() must call log_event(engine, AuditEventType.SPLIT_APPLIED,
    symbol=..., payload={split_date, ratio, before: {...}, after: {...}}).

    Will assert:
      - audit_log table contains one SPLIT_APPLIED event for the position
      - payload has 'before' and 'after' keys with shares and price fields
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_split_outside_window_ignored(db_engine: Engine) -> None:
    """DATA-06: No split applied when split_date <= last_scan_date (D-05).

    If yfinance returns a split that occurred before or on last_scan_date,
    the D-05 window filter excludes it — the split was already applied
    (or not applicable) in a prior scan.

    Will assert:
      - With a split_date == last_scan_date, _apply_splits() makes no DB changes
      - shares and price fields remain unchanged
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_delisted_flag_set(db_engine: Engine) -> None:
    """STATE-07: Delisted position — delisted flag set to 1 on first detection.

    When a held position's symbol is absent from the current constituents set
    and positions.delisted == 0, _detect_delisted_positions() must update
    positions.delisted = 1 in the DB.

    Will assert:
      - Before call: positions row has delisted == 0
      - After call: positions row has delisted == 1
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_delisted_event_not_repeated(db_engine: Engine) -> None:
    """STATE-07: Delisted position — POSITION_DELISTED_FROM_INDEX event logged once.

    The delisted flag prevents re-logging the event on every subsequent scan.
    If positions.delisted == 1 already, _detect_delisted_positions() must
    not log another POSITION_DELISTED_FROM_INDEX event.

    Will assert:
      - With delisted=1 already in DB, audit_log has exactly 0 new events
        for the second call to _detect_delisted_positions()
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_delisted_excluded_from_candidates(db_engine: Engine) -> None:
    """STATE-07: Delisted symbol excluded from buy candidates.

    Positions with delisted == 1 must be excluded from the buy candidate
    screening universe (they remain open for stop monitoring but cannot
    be bought again).

    Will assert:
      - _run_screening() does not include the delisted symbol in candidates
        even when it would otherwise qualify (above SMA 200, good momentum)
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_delisted_template4(db_engine: Engine) -> None:
    """STATE-07: Template 4 rendered for delisted position in catch-up summary.

    When _detect_delisted_positions() first detects a delisted position,
    it returns a list containing the render_removed_from_sp500() string for
    that position, which appears in the catch-up summary output.

    Will assert:
      - Return value of _detect_delisted_positions() contains a string with
        "Removed from S&P 500" for the delisted symbol
      - The string does NOT include a date (removal_date=None per Plan 01 decision)
    """
    raise NotImplementedError("filled in Plan 02/03")


# ---------------------------------------------------------------------------
# Plan 03 part A: Catch-up walk integration (STATE-05) — 2 stubs
# ---------------------------------------------------------------------------


def test_catchup_stop_reconstruction(db_engine: Engine) -> None:
    """STATE-05: Catch-up walk updates highest_close/trailing_stop for all missed days.

    When _update_position_stops() is called with missed_days=[day1, day2] and
    price data exists for each day, the position's highest_close and trailing_stop
    must be updated for each day in chronological order before today.

    Will assert:
      - After walk with mock price data, position in DB has updated highest_close
        reflecting the highest close seen across all missed days and today
      - trailing_stop = highest_close * 0.75
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_split_in_catchup_template(db_engine: Engine) -> None:
    """STATE-05: Split applied during absence shows Template 5 in catch-up summary.

    When a split occurs during the catch-up window (between last_scan_date and
    today), the catch-up summary must include the Template 5 stock-split entry
    for that position via render_stock_split().

    Will assert:
      - catch-up event list returned by _update_position_stops includes a string
        with "Stock split" and the ratio for the position that had a split
    """
    raise NotImplementedError("filled in Plan 02/03")


# ---------------------------------------------------------------------------
# Plan 03 part B: Rendering (STATE-05) — 4 stubs
# ---------------------------------------------------------------------------


def test_catchup_summary_rendering(db_engine: Engine) -> None:
    """STATE-05: Catch-up summary renders with correct per-position entries.

    When run_scan() is called after a 2+ day absence with an open position
    that had a notable event (stop violated or new highest close), the output
    string must contain the catch-up summary block with per-position entries.

    Will assert:
      - Output contains "Catch-up summary" header with === separator
      - Output contains "You were absent for N trading days"
      - Per-position event strings appear in the output
      - Regular scan sections appear after the catch-up block
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_composite_template(db_engine: Engine) -> None:
    """STATE-05: Template 13 composite for multiple events per position (D-02).

    When a position has multiple notable events across missed days (e.g.
    new highest close on day 1, then stop violated on day 2), the catch-up
    summary must use Template 13 composite format: one entry per position
    with a bulleted list of events, not repeated symbol names.

    Will assert:
      - Output contains "{SYMBOL}  Multiple events during your absence:"
      - Output contains exactly one entry for the symbol (not repeated)
      - Individual event strings appear as bullet items
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_template3_initial_final_only(db_engine: Engine) -> None:
    """STATE-05: Template 3 shows initial->final stop only in composite (D-03).

    When a position reaches new highest closes on multiple missed days
    (e.g. days 1, 2, 3 of a 3-day absence), the composite entry must show
    only the initial trailing stop (before any new highest close) and the
    final trailing stop (after all missed days), not one bullet per day.

    Will assert:
      - Composite entry for a position with 3 consecutive new highest closes
        contains exactly one "Trailing stop updated from $X to $Y" bullet
      - The $X is the trailing stop before any new high (initial)
      - The $Y is the trailing stop after all new highs (final)
    """
    raise NotImplementedError("filled in Plan 02/03")


def test_catch_up_audit_event(db_engine: Engine) -> None:
    """STATE-05: CATCH_UP_PERFORMED audit event logged when missed_days >= 1.

    After a catch-up scan completes, run_scan() must log a CATCH_UP_PERFORMED
    audit event with the number of missed days and the date range.

    Will assert:
      - audit_log table contains one CATCH_UP_PERFORMED event after run_scan()
        completes with a 2+ day absence scenario
      - Event payload includes 'missed_days_count' and date range fields
    """
    raise NotImplementedError("filled in Plan 02/03")
