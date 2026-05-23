"""No I/O — pure filter math over pre-fetched DataFrames.

STRAT-01: Regime filter — buy candidates only when SPX close > SPX SMA 200.
STRAT-02: Liquidity filter — restrict universe to top 25% by 20-day average volume.
STRAT-03: Momentum filter — stock close today > stock close 200 trading days ago.
STRAT-04: Ranking — top 10 candidates by ROC 200 (rate of change over 200 days).
STRAT-05: Max 10 open positions — enforced by rank_candidates returning at most 10.

Depends on: pandas>=3.0.3
Used by: commands/scan.py (Phase 7)

D-02: This module has zero imports from bensdorp1.db or bensdorp1.data.
All DataFrames are passed in by the caller (Phase 7 scan command).
"""

from __future__ import annotations

import math
from typing import TypedDict

import pandas as pd


class Candidate(TypedDict):
    """A single buy candidate produced by rank_candidates."""

    symbol: str
    roc_200: float
    prev_close: float
    position_size: int


def regime_filter(spx_closes: pd.Series[float]) -> bool:
    """Return True when SPX is in bull regime (close today > SMA 200).

    STRAT-01: SMA 200 is the simple mean of the last 200 closes including today.
    D-09: Raises ValueError if fewer than 200 rows provided.

    Args:
        spx_closes: Chronological Series of SPX adjusted closes; last entry = today.

    Returns:
        True when today_close > sma_200 (regime on); False otherwise.

    Raises:
        ValueError: If len(spx_closes) < 200.
    """
    if len(spx_closes) < 200:
        raise ValueError(
            f"regime_filter: need >= 200 closes; got {len(spx_closes)}"
        )
    sma200: float = float(spx_closes.iloc[-200:].mean())
    today_close: float = float(spx_closes.iloc[-1])
    return today_close > sma200


def liquidity_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]:
    """Return symbols in the top 25% by 20-day average volume (T-1 through T-20).

    STRAT-02: 75th percentile threshold computed across all symbols in price_dfs.
    D-04: Volume window excludes today (iloc[:-1].iloc[-20:]).
    D-05: Returns [] when price_dfs is empty.
    D-07: Raises ValueError if any symbol has fewer than 21 rows.

    NaN volume behavior: symbols with NaN in the 20-day window produce a NaN
    mean, which fails the >= threshold check — symbol is excluded (conservative).

    Args:
        price_dfs: Mapping of symbol -> DataFrame with columns [close, volume],
                   indexed chronologically; last row = today.

    Returns:
        List of symbols at or above the 75th percentile of 20-day average volume.

    Raises:
        ValueError: If any symbol's DataFrame has fewer than 21 rows.
    """
    if not price_dfs:
        return []
    avg_volumes: dict[str, float] = {}
    for symbol, df in price_dfs.items():
        if len(df) < 21:
            raise ValueError(
                f"liquidity_filter: {symbol} needs >= 21 rows; got {len(df)}"
            )
        excl_today: pd.DataFrame = df.iloc[:-1]
        last_20: pd.DataFrame = excl_today.iloc[-20:]
        avg_volumes[symbol] = float(last_20["volume"].mean())
    threshold: float = float(
        pd.Series(list(avg_volumes.values()), dtype=float).quantile(0.75)
    )
    return [sym for sym, vol in avg_volumes.items() if vol >= threshold]


def momentum_filter(price_dfs: dict[str, pd.DataFrame]) -> list[str]:
    """Return symbols where today's close is strictly above the close 200 rows ago.

    STRAT-03: close_today > close_t200 (strict greater-than; equal excluded).
    D-03: '200 trading days ago' = T-200 exclusive of today (iloc[-200]).
    D-07: Raises ValueError if any symbol has fewer than 200 rows.

    Args:
        price_dfs: Mapping of symbol -> DataFrame with column [close],
                   indexed chronologically; last row = today.

    Returns:
        List of symbols where close_today > close at index -200.

    Raises:
        ValueError: If any symbol's DataFrame has fewer than 200 rows.
    """
    result: list[str] = []
    for symbol, df in price_dfs.items():
        if len(df) < 200:
            raise ValueError(
                f"momentum_filter: {symbol} needs >= 200 rows; got {len(df)}"
            )
        close_today: float = float(df["close"].iloc[-1])
        close_t200: float = float(df["close"].iloc[-200])
        if close_today > close_t200:
            result.append(symbol)
    return result


def rank_candidates(
    price_dfs: dict[str, pd.DataFrame],
    available_cash: float,
) -> list[Candidate]:
    """Return up to 10 buy candidates sorted descending by ROC 200.

    STRAT-04: Candidates ranked by rate of change over 200 days.
    STRAT-05: At most 10 candidates returned.
    D-06: position_size = floor((available_cash * 0.10) / prev_close); returns 0
          when result is less than 1 share.
    D-07: Raises ValueError if any symbol has fewer than 200 rows.

    Args:
        price_dfs: Mapping of symbol -> DataFrame with column [close],
                   indexed chronologically; last row = today.
        available_cash: Total available cash for position sizing.

    Returns:
        List of at most 10 Candidate dicts sorted descending by roc_200.

    Raises:
        ValueError: If any symbol's DataFrame has fewer than 200 rows.
    """
    if not price_dfs:
        return []
    results: list[Candidate] = []
    for symbol, df in price_dfs.items():
        if len(df) < 200:
            raise ValueError(
                f"rank_candidates: {symbol} need >= 200 rows; got {len(df)}"
            )
        prev_close: float = float(df["close"].iloc[-1])
        close_t200: float = float(df["close"].iloc[-200])
        roc_200: float = (prev_close / close_t200) - 1.0
        shares: int = math.floor((available_cash * 0.10) / prev_close)
        results.append(
            {
                "symbol": symbol,
                "roc_200": roc_200,
                "prev_close": prev_close,
                "position_size": shares,
            }
        )
    return sorted(results, key=lambda x: x["roc_200"], reverse=True)[:10]
