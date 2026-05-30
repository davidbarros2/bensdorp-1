"""Catch-up event template rendering functions (spec §8.9).

Pure formatters — no I/O, no DB, no Rich markup in return values.
Each function accepts typed parameters and returns a plain str.
All dollar values are rendered via format_price(); no inline dollar-sign f-strings.
"""

from __future__ import annotations

from datetime import date

from bensdorp1.ui import format_price

# ---------------------------------------------------------------------------
# Per-position event templates (spec §8.9 Templates 1-7)
# ---------------------------------------------------------------------------


def render_initial_stop_violated(
    symbol: str,
    trigger_date: date,
    close: float,
    stop: float,
) -> str:
    """Template 1 — Initial stop violated during catch-up absence (spec §8.9)."""
    return (
        f"{symbol}  Initial stop violated on {trigger_date.isoformat()} "
        f"(close {format_price(close)} < stop {format_price(stop)}).\n"
        f"      Position remained open during your absence.\n"
        f"      An exit trigger from that day is still pending."
    )


def render_trailing_stop_violated(
    symbol: str,
    trigger_date: date,
    close: float,
    stop: float,
) -> str:
    """Template 2 — Trailing stop violated during catch-up absence (spec §8.9)."""
    return (
        f"{symbol}  Trailing stop violated on {trigger_date.isoformat()} "
        f"(close {format_price(close)} < stop {format_price(stop)}).\n"
        f"      Position remained open during your absence.\n"
        f"      An exit trigger from that day is still pending."
    )


def render_new_highest_close(
    symbol: str,
    trigger_date: date,
    close: float,
    old_stop: float,
    new_stop: float,
) -> str:
    """Template 3 — New highest close reached during absence (spec §8.9).

    D-03: In a composite entry, show initial->final trailing stop only.
    The caller is responsible for collapsing multiple Template 3 events
    into a single call showing the initial old_stop and final new_stop.
    """
    return (
        f"{symbol}  New highest close reached on {trigger_date.isoformat()} "
        f"({format_price(close)}).\n"
        f"      Trailing stop updated from {format_price(old_stop)} to "
        f"{format_price(new_stop)}.\n"
        f"      No exit trigger."
    )


def render_removed_from_sp500(
    symbol: str,
    removal_date: date | None,
) -> str:
    """Template 4 — Stock removed from S&P 500 during absence (spec §8.9).

    Open Question 2 resolution: when removal_date is None (detected at scan
    time with no exact removal date available), the " on {DATE}" clause is
    omitted — best-effort detection per 11-RESEARCH.md.
    """
    if removal_date is not None:
        date_clause = f" on {removal_date.isoformat()}"
    else:
        date_clause = ""
    return (
        f"{symbol}  Removed from S&P 500{date_clause}.\n"
        f"      Position remains open. Stop monitoring continues."
    )


def render_stock_split(
    symbol: str,
    ratio_str: str,
    split_date: date,
    old_shares: int,
    new_shares: int,
    old_price: float,
    new_price: float,
) -> str:
    """Template 5 — Stock split occurred during absence (spec §8.9).

    Uses unicode arrow per spec verbatim wording.
    """
    return (
        f"{symbol}  Stock split {ratio_str} on {split_date.isoformat()}.\n"
        f"      Shares adjusted: {old_shares} → {new_shares}.\n"
        f"      Entry price adjusted: {format_price(old_price)} → "
        f"{format_price(new_price)}."
    )


def render_dividend(
    symbol: str,
    div_date: date,
    amount: float,
) -> str:
    """Template 6 — Dividend paid during absence (spec §8.9)."""
    return (
        f"{symbol}  Dividend paid on {div_date.isoformat()}: "
        f"{format_price(amount)} per share.\n"
        f"      No impact on strategy (using adjusted prices)."
    )


def render_market_delist(
    symbol: str,
    delist_date: date | None,
) -> str:
    """Template 7 — Stock delisted entirely from market (spec §8.9).

    D-09 / CONTEXT.md §specifics: best-effort implementation. When
    delist_date is None (data completely absent, exact date unknown),
    the " on {DATE}" clause is omitted and a broker-verification note
    is added. The sell hint uses the specific symbol for clarity.
    """
    if delist_date is not None:
        date_clause = f" on {delist_date.isoformat()}"
    else:
        date_clause = ""
    return (
        f"{symbol}  Delisted from the market{date_clause}.\n"
        f"      Verify via broker. Manual action required:\n"
        f"      `bensdorp1 sell {symbol} PRICE --manual \"Delisted\"`"
    )


# ---------------------------------------------------------------------------
# Market regime event templates (spec §8.9 Templates 8-9)
# ---------------------------------------------------------------------------


def render_regime_bull_to_bear(change_date: date) -> str:
    """Template 8 — Market regime changed: bull to bear (spec §8.9)."""
    return (
        f"Market regime changed on {change_date.isoformat()}: bull → bear.\n"
        f"S&P 500 close fell below SMA 200.\n"
        f"No new positions can be entered until regime returns to bull."
    )


def render_regime_bear_to_bull(change_date: date) -> str:
    """Template 9 — Market regime changed: bear to bull (spec §8.9)."""
    return (
        f"Market regime changed on {change_date.isoformat()}: bear → bull.\n"
        f"S&P 500 close rose above SMA 200.\n"
        f"Buy candidates resume."
    )


# ---------------------------------------------------------------------------
# System event templates (spec §8.9 Templates 10-12)
# ---------------------------------------------------------------------------


def render_constituents_updated(
    change_date: date,
    n_added: int,
    n_removed: int,
) -> str:
    """Template 10 — Constituents list updated during absence (spec §8.9)."""
    return (
        f"S&P 500 constituents updated on {change_date.isoformat()}: "
        f"+{n_added} added, -{n_removed} removed."
    )


def render_data_fetch_failed(
    n_days: int,
    dates_list: list[str],
) -> str:
    """Template 11 — Data fetch failure on specific days during absence (spec §8.9)."""
    dates_str = ", ".join(dates_list)
    return (
        f"Data fetch failed for {n_days} days during your absence: {dates_str}.\n"
        f"State may be incomplete for these days. "
        f"Run `bensdorp1 refresh` to retry."
    )


def render_trading_holidays(
    n: int,
    dates_list: list[str],
) -> str:
    """Template 12 — Trading holidays detected during absence (spec §8.9)."""
    dates_str = ", ".join(dates_list)
    holiday_word = "holiday" if n == 1 else "holiday(s)"
    return (
        f"{n} trading {holiday_word} occurred during your absence: {dates_str}.\n"
        f"No market activity on these days."
    )


# ---------------------------------------------------------------------------
# Composite event template (spec §8.9 Template 13)
# ---------------------------------------------------------------------------


def render_composite(symbol: str, events_list: list[str]) -> str:
    """Template 13 — Position with multiple events during absence (spec §8.9).

    D-02: One entry per position with a bullet list of events.
    Continuation lines are indented 6 spaces to match spec §7.6 alignment.
    """
    bullets = "\n".join(f"      - {e}" for e in events_list)
    return f"{symbol}  Multiple events during your absence:\n{bullets}"


# ---------------------------------------------------------------------------
# Split notification (spec §8.3) — System notes variant
# ---------------------------------------------------------------------------


def render_split_notification(
    symbol: str,
    ratio_str: str,
    split_date: date,
    old_shares: int,
    new_shares: int,
    old_price: float,
    new_price: float,
) -> str:
    """Spec §8.3 System-notes split notification format.

    Used by _apply_splits() for the System notes section of scan output.
    Template 5 (render_stock_split) is the catch-up summary variant.
    Uses unicode arrow per spec §8.3 verbatim example.
    """
    return (
        f"{symbol}  Split applied: {ratio_str} (effective {split_date.isoformat()})\n"
        f"      Shares: {old_shares} → {new_shares}\n"
        f"      Entry price: {format_price(old_price)} → {format_price(new_price)}"
    )
