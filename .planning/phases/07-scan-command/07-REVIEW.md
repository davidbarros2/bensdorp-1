---
phase: 07-scan-command
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/bensdorp1/commands/_scan_engine.py
  - src/bensdorp1/commands/scan.py
  - src/bensdorp1/db/schema.py
  - tests/test_commands/test_scan.py
  - tests/test_commands/test_scan_engine.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-05-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

The scan command wires a well-structured pipeline: time-gate → trading-day check → idempotency → engine delegation. The `_scan_engine.py` module follows the D-series design spec carefully. However, four critical bugs were found:

1. The non-trading-day branch opens the database without ever calling `run_migrations`, so the first run on a weekend crashes with an `OperationalError` (table not found).
2. `_detect_exit_triggers` fetches **all** `scan_exit_triggers` rows across all positions when checking for duplicates, not filtering by the current position set. On a database with many historical triggers for positions that have since been closed (and thus absent from `open_positions`), this is merely wasteful. But if the sell command does not delete `scan_exit_triggers` rows (only nulls them or leaves them), a re-triggered re-opened position will permanently be skipped. More concretely, the `existing_position_ids` set is populated from ALL rows in the table, so if a position row is ever re-used (ID recycled by SQLite `autoincrement` is not possible, but a manually restored DB could do it), a new trigger is silently suppressed.
3. `_detect_exit_triggers` always records `triggered_date = today` and `close_at_trigger = today's price` even when the stop was actually hit on a missed catch-up day. The docstring says "D-09: triggered_date stores the actual day the stop was hit" — the implementation contradicts this guarantee, storing the wrong date and a potentially incorrect (or 0.0) close price when the true trigger day was a missed trading day.
4. The `scan.py` non-trading-day branch queries the DB through the engine singleton but also calls `get_engine(db_path)` on line 42 without ever calling `run_migrations`. On a fresh install where `scan` is first invoked on a weekend, the `scans` table does not exist and the query at line 43–48 crashes with `OperationalError: no such table: scans`.

Five warnings cover: the idempotency check on `force` re-runs inserts a duplicate `scan_exit_triggers` row for positions that triggered in a prior `--force`-replaced scan; the SMA-200 calculation uses a different window in `_run_screening` vs `regime_filter`; `_get_close_for_day` iterates with `df.iterrows()` on every call (O(n) per call, called once per position per day — correctness concern for very large DataFrames); the `_persist_scan_placeholder` ON-CONFLICT path returns `None` for `inserted_primary_key` and falls back to a second query, but the second connection opens a new transaction and the placeholder may not be visible if isolation level is SERIALIZABLE (not an issue for SQLite default, but fragile); and `scan.py` creates `console = Console()` twice in different branches (lines 49 and 75), making the non-trading-day branch use a separate console from the one passed to `run_scan`.

---

## Critical Issues

### CR-01: Non-trading-day branch queries DB without running migrations

**File:** `src/bensdorp1/commands/scan.py:41-48`
**Issue:** When `is_trading_day(today)` returns `False`, the code calls `get_engine(db_path)` and immediately executes a SELECT against `scans` without ever calling `run_migrations(engine)`. On a fresh install where the user first runs `bensdorp1 scan` on a weekend, the `scans` table does not exist and SQLAlchemy raises `OperationalError: no such table: scans`. This is a silent data-loss / crash path that is never exercised by the test suite (the test at `test_non_trading_day` mocks `get_engine` and therefore never hits real SQLite).

**Fix:**
```python
# 2. TRADING-DAY CHECK
today = datetime.now(MARKET_TZ).date()
if not is_trading_day(today):
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)          # <- add this line
    with engine.connect() as conn:
        ...
```

---

### CR-02: `_detect_exit_triggers` records wrong `triggered_date` and `close_at_trigger` for catch-up triggers

**File:** `src/bensdorp1/commands/_scan_engine.py:568-576`
**Issue:** When a position's stop is hit on a missed catch-up day (e.g., the stop crossed on Monday but the scan runs Wednesday), `_update_position_stops` adds the position to `triggered_position_ids`. `_detect_exit_triggers` then inserts a `scan_exit_triggers` row with `triggered_date = today` (Wednesday midnight UTC) and `close_at_trigger = _get_close_for_day(..., today)`. If Wednesday's price data is not yet in the narrow 10-day fetch (or if the symbol was suspended that day), `close_at_trigger` silently becomes `0.0`.

The function docstring explicitly states: "D-09: triggered_date stores the actual day the stop was hit." The implementation violates this contract. The user sees the wrong trigger date in the output, which is directly displayed (`format_date(tr.triggered_date.date())`) and stored in the DB.

The cause is that `_update_position_stops` does not return which day each position triggered; it only accumulates IDs. The day information is lost.

**Fix:** Track the trigger day alongside the position ID.

```python
# In _update_position_stops — change triggered_position_ids to a dict
# mapping position id -> (trigger_date, close_at_trigger)

def _update_position_stops(
    engine: Engine,
    open_positions: list[_OpenPosition],
    missed_days: list[date],
    today: date,
    price_dfs: dict[str, pd.DataFrame],
    triggered_position_ids: dict[int, tuple[date, float]],   # was set[int]
) -> None:
    ...
    if is_exit_triggered(close, eff_stop):
        triggered_position_ids[pos.id] = (day, close)        # store day + close
    ...

# In _detect_exit_triggers — receive the same dict and use the stored values
def _detect_exit_triggers(
    ...,
    triggered_position_ids: dict[int, tuple[date, float]],
    ...
) -> list[_TriggerRow]:
    ...
    trigger_day, close_at_trigger = triggered_position_ids[pos.id]
    triggered_date_utc = datetime(
        trigger_day.year, trigger_day.month, trigger_day.day, tzinfo=UTC
    )
    ...
```

All call sites in `run_scan` and tests must be updated to pass a `dict` instead of a `set`.

---

### CR-03: `_detect_exit_triggers` queries all rows from `scan_exit_triggers` without filtering — suppresses re-triggers on `--force` re-run

**File:** `src/bensdorp1/commands/_scan_engine.py:548-552`
**Issue:** The "already triggered" check fetches every row from `scan_exit_triggers` with no WHERE clause:

```python
existing_rows = conn.execute(
    select(scan_exit_triggers.c.position_id)
).fetchall()
```

When `--force` replaces a same-day scan: the prior scan's exit trigger rows remain in the table (the `_persist_scan` function only deletes `scan_candidates`, not `scan_exit_triggers`). On a `--force` re-run, any position that triggered in the now-replaced scan will still appear in `existing_position_ids` and will therefore be silently skipped — it never appears in `new_trigger_rows` for the fresh run, so it is invisible to the user and not written to the fresh scan's `exit_trigger_count`.

**Fix:** Filter `existing_position_ids` to only rows NOT associated with the current `scan_id` (the placeholder just created). Alternatively, delete the prior scan's `scan_exit_triggers` rows in `_persist_scan` when `force=True`:

```python
# In _persist_scan, add before re-inserting scan_candidates:
if force:
    with engine.connect() as conn:
        conn.execute(
            delete(scan_exit_triggers).where(
                scan_exit_triggers.c.scan_id == scan_id
            )
        )
        conn.commit()
```

And in `_detect_exit_triggers`, scope the duplicate check:
```python
existing_rows = conn.execute(
    select(scan_exit_triggers.c.position_id).where(
        scan_exit_triggers.c.scan_id != scan_id   # exclude current scan
    )
).fetchall()
```

---

### CR-04: `_run_screening` raises uncaught `ValueError` from `regime_filter` / `momentum_filter` / `liquidity_filter` — unhandled exception escapes `run_scan`

**File:** `src/bensdorp1/commands/_scan_engine.py:673-720`
**Issue:** `regime_filter` raises `ValueError` if fewer than 200 SPX closes are provided. `liquidity_filter` and `momentum_filter` raise `ValueError` if any symbol has fewer than 21 or 201 rows respectively. `_run_screening` does not catch these. `run_scan` only catches `RuntimeError` (line 247):

```python
except RuntimeError as exc:
    return str(exc)
```

A `ValueError` from any strategy filter propagates out of `run_scan` as an unhandled exception, crashing the CLI with a raw traceback rather than a user-friendly message. This is especially likely after a fresh install or partial price fetch where some symbols have insufficient history.

**Fix:**
```python
# In run_scan:
except (RuntimeError, ValueError) as exc:
    return str(exc)
```

Or, more surgically, catch `ValueError` in `_run_screening` and re-raise as `RuntimeError`:
```python
try:
    regime_active: bool = regime_filter(spx_closes)
    ...
except ValueError as exc:
    raise RuntimeError(str(exc)) from exc
```

---

## Warnings

### WR-01: `scan.py` idempotency check at line 76 does not guard against `existing.raw_output is None`

**File:** `src/bensdorp1/commands/scan.py:76-79`
**Issue:** When `existing is not None and not force` is true, the code checks `if existing.raw_output is not None` before printing, then `raise typer.Exit()` regardless. If `existing.raw_output` is `None` (which is valid per the schema: `raw_output TEXT nullable`) — as is the case for a scan that crashed mid-flight and left a placeholder row — the user gets a silent exit with no output and no error message. They have no indication that a prior scan attempt failed.

**Fix:**
```python
if existing is not None and not force:
    if existing.raw_output is not None:
        console.print(existing.raw_output, markup=False, highlight=False)
    else:
        print_info(
            "A scan record exists for today but has no output "
            "(the prior scan may have failed). Re-run with --force to retry."
        )
    raise typer.Exit()
```

---

### WR-02: `_run_screening` computes `spx_sma_200` differently from `regime_filter`

**File:** `src/bensdorp1/commands/_scan_engine.py:694`
**Issue:** `_run_screening` computes:
```python
spx_sma_200: float = float(spx_df["close"].tail(200).mean())
```
But `regime_filter` (in `strategy/screening.py:51`) computes:
```python
sma200: float = float(spx_closes.iloc[-200:].mean())
```
where `spx_closes` is `spx_df["close"].astype(float)`. These are the same window, but `_run_screening` computes the SMA from the full `spx_df` (which is `rows_needed=221` rows tailed from the DB) while `regime_filter` receives `spx_closes` which is the same series. The actual numeric values will agree only if the DataFrame passed to `regime_filter` and the `spx_df` are the same object — which they are, making this consistent in practice. However, the SMA displayed to the user (`spx_sma_200` at line 694) is computed before any `astype(float)` cast, which `regime_filter` applies. If any close values are stored as integer in the DB, the displayed SMA and the regime decision SMA could differ by floating-point rounding. Low-probability but inconsistent.

Additionally, `regime_filter` uses `iloc[-200:]` (last 200 rows) whereas `spx_sma_200 = spx_df["close"].tail(200).mean()` is exactly equivalent. Both use the same 200-row window — no off-by-one here. The inconsistency is the cast only.

**Fix:** Compute `spx_sma_200` from the same cast series used for `regime_filter`:
```python
spx_closes: pd.Series[float] = spx_df["close"].astype(float)
spx_close: float = float(spx_closes.iloc[-1])
spx_sma_200: float = float(spx_closes.tail(200).mean())
regime_active: bool = regime_filter(spx_closes)
```

---

### WR-03: `_get_close_for_day` uses `df.iterrows()` — O(n) linear scan per call

**File:** `src/bensdorp1/commands/_scan_engine.py:466-474`
**Issue:** For each (position, day) pair in `_update_position_stops`, `_get_close_for_day` iterates every row of the DataFrame looking for the matching date. With 500 S&P 500 symbols, `rows_needed=221` rows each, and a catch-up window of several missed days, this is O(positions × days × rows_per_df). More importantly, the correctness risk: a DataFrame with multiple rows sharing the same `trade_date` (which can occur if the DB has duplicate rows that slipped past the unique index during testing) will return only the first matching row's close, silently ignoring the duplicate. The underlying `price_daily` table has a unique index on `(symbol, trade_date)` so duplicates cannot exist in production, but a test DB built with direct inserts (as all tests do) could have this.

The correct approach is a date-indexed lookup:

**Fix:**
```python
def _get_close_for_day(
    price_dfs: dict[str, pd.DataFrame],
    symbol: str,
    target_date: date,
) -> float | None:
    df = price_dfs.get(symbol)
    if df is None or df.empty:
        return None
    # Vectorized date comparison — O(n) but no Python-level loop overhead
    dates = df["trade_date"].apply(
        lambda td: td.date() if hasattr(td, "date") else date(td.year, td.month, td.day)
    )
    mask = dates == target_date
    matched = df.loc[mask, "close"]
    if matched.empty:
        return None
    return float(matched.iloc[0])
```

---

### WR-04: `_update_position_stops` computes `eff_stop` with the newly-computed `new_ts` but `_detect_exit_triggers` recomputes from the stale frozen `pos.trailing_stop`

**File:** `src/bensdorp1/commands/_scan_engine.py:505-511` and `563`
**Issue:** In `_update_position_stops`, the trigger check uses:
```python
new_hc = update_highest_close(pos.highest_close, close)   # may be higher
new_ts = compute_trailing_stop(new_hc)                     # may be higher
eff_stop = compute_effective_stop(pos.initial_stop, new_ts)
if is_exit_triggered(close, eff_stop):                     # correct eff_stop
    triggered_position_ids.add(pos.id)
```

But when `_detect_exit_triggers` computes the effective stop for display and storage:
```python
eff_stop = compute_effective_stop(pos.initial_stop, pos.trailing_stop)
```
`pos.trailing_stop` is the value from the DB snapshot loaded at query time, which has **not** been updated (because the position was frozen on trigger — the `else` branch that writes to DB was skipped). So `pos.trailing_stop` may be lower than `new_ts` that was used for the trigger decision.

This means the stored `effective_stop` in `scan_exit_triggers` and the value displayed to the user can be **lower than the actual stop that triggered the exit**. In extreme cases (large single-day move ratcheting the trailing stop up significantly, then a close below that new stop), the stored/displayed stop is materially wrong.

**Fix:** In `_update_position_stops`, store the computed `eff_stop` alongside the position id when marking as triggered (as part of the fix for CR-02's dict approach):
```python
triggered_position_ids[pos.id] = (day, close, eff_stop)
```
Then use this stored `eff_stop` in `_detect_exit_triggers`.

---

### WR-05: `liquidity_filter` raises `ValueError` for symbols with fewer than 21 rows, but `_load_price_dfs` defaults `rows_needed=221` without guaranteeing all symbols have that many rows

**File:** `src/bensdorp1/commands/_scan_engine.py:383` and `src/bensdorp1/strategy/screening.py:82`
**Issue:** `_load_price_dfs` uses `df.tail(rows_needed).reset_index(drop=True)`, which silently returns fewer than `rows_needed` rows if the DB has less data. The result is passed directly into `liquidity_filter` (via `_run_screening`), which raises `ValueError` when any symbol has fewer than 21 rows. This `ValueError` is unhandled (see CR-04).

New constituents added to the S&P 500 — which would be fetched by the narrow 10-day window but have minimal history — will reliably trigger this path after the first `init`. The intent of `rows_needed` is to tail to the window needed, not to guarantee all symbols have enough data.

**Fix:** Filter out symbols with insufficient rows before passing to the strategy filters:
```python
# In _run_screening, before liquidity_filter:
constituent_dfs = {
    sym: df for sym, df in constituent_dfs.items() if len(df) >= 21
}
# and before momentum_filter:
liquid_dfs = {
    sym: constituent_dfs[sym]
    for sym in liquid_symbols
    if sym in constituent_dfs and len(constituent_dfs[sym]) >= 201
}
```

---

## Info

### IN-01: Docstring for `_detect_exit_triggers` contradicts implementation on D-09

**File:** `src/bensdorp1/commands/_scan_engine.py:540`
**Issue:** The function docstring states "D-09: triggered_date stores the actual day the stop was hit." The implementation stores `today` for all triggers, including catch-up triggers from missed days. This is also repeated in the test comment at `test_scan.py:482-495` ("triggered_date is stored as midnight UTC of today (the scan date)"). Either the spec (D-09) needs updating to reflect the implemented behavior, or the implementation needs fixing (see CR-02). The current state leaves ambiguity for future maintainers.

**Fix:** Update the docstring to reflect the actual behavior, or fix the implementation per CR-02.

---

### IN-02: `scan.py` test `test_non_trading_day` does not call `run_migrations` before mocking `get_engine`

**File:** `tests/test_commands/test_scan.py:169-193`
**Issue:** The test patches `get_engine` with a `MagicMock` and verifies the non-trading-day output path. However, since `get_engine` is mocked, the test never exercises the crash described in CR-01 (missing `run_migrations` call). A test that passes a real db engine without prior `run_migrations` would catch that defect.

**Fix:** Add a test variant that injects a real (but empty, pre-migrations) SQLite engine to verify the non-trading-day path tolerates first-run conditions.

---

### IN-03: Magic number `rows_needed=221` in `_load_price_dfs` is not explained or tied to strategy constants

**File:** `src/bensdorp1/commands/_scan_engine.py:383`
**Issue:** The value `221` is one more than the 220 trading days used elsewhere (DEFAULT_REQUIRED_TRADING_DAYS) and one more than the 200-row minimum for `momentum_filter` plus the `+1` for iloc[-201]. The reasoning (need 201 rows for momentum, plus the `tail` trims from the full fetch) is not documented. The number appears ad-hoc.

**Fix:** Define a named constant and add a comment:
```python
# 201 rows needed for momentum_filter (iloc[-201] = T-200) + 20 for liquidity buffer
_PRICE_ROWS_NEEDED: int = 221
```
and reference it:
```python
price_dfs = _load_price_dfs(engine, all_symbols, rows_needed=_PRICE_ROWS_NEEDED)
```

---

_Reviewed: 2026-05-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
