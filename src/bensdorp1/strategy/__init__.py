"""Public surface of the bensdorp1.strategy subpackage.

All exported names are pure functions — no I/O, no DB access (D-02).
"""

from bensdorp1.strategy.positions import (
    compute_effective_stop,
    compute_initial_stop,
    compute_position_size,
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

__all__ = [
    "Candidate",
    "compute_effective_stop",
    "compute_initial_stop",
    "compute_position_size",
    "compute_trailing_stop",
    "is_exit_triggered",
    "liquidity_filter",
    "momentum_filter",
    "rank_candidates",
    "regime_filter",
    "update_highest_close",
]
