"""No I/O — pure stop arithmetic.

STRAT-06 through STRAT-09.
Used by: commands/scan.py (Phase 7), commands/buy.py (Phase 8).
D-02: no imports from bensdorp1.db or bensdorp1.data.
"""

import math


def compute_position_size(available_cash: float, prev_close: float) -> int:
    """Return shares to buy: floor((cash * 0.10) / prev_close).

    Returns 0 when result < 1 (D-06).
    """
    return math.floor((available_cash * 0.10) / prev_close)


def compute_initial_stop(entry_close: float) -> float:
    """Return initial stop: entry_close * 0.93. Immutable (STRAT-07)."""
    return entry_close * 0.93


def update_highest_close(current: float, new_close: float) -> float:
    """Return new highest close: max(current, new_close).

    Stateless; Phase 7 persists the result (D-08).
    """
    return max(current, new_close)


def compute_trailing_stop(highest_close: float) -> float:
    """Return trailing stop: highest_close * 0.75.

    Stateless; Phase 7 persists the result (D-08, STRAT-08).
    """
    return highest_close * 0.75


def compute_effective_stop(initial_stop: float, trailing_stop: float) -> float:
    """Return effective stop: max(initial_stop, trailing_stop) (STRAT-09)."""
    return max(initial_stop, trailing_stop)


def is_exit_triggered(close: float, effective_stop: float) -> bool:
    """Return True when close <= effective_stop (exit signal).

    STRAT-09: trigger when daily close is at or below effective stop.
    """
    return close <= effective_stop
