# Phase 11: Catch-Up Logic - Research

**Researched:** 2026-05-30
**Domain:** Scan engine extension — catch-up reconstruction, split detection, delisting, event templates
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Positions with no notable events during absence (stop did not trigger, no new highest close, no split, not delisted) are **silent** — counted in the "State has been updated for N open positions" summary line but get no per-position entry.

**D-02:** Positions with multiple notable events across missed days → **Template 13 composite** format: one entry per position with a bullet list of events. Not a flat list with repeated symbol names.

**D-03:** For Template 3 (trailing stop updated) inside a composite → show **initial → final only** regardless of how many intermediate new highs occurred. Reduces noise for multi-day trending positions.

**D-04:** Catch-up summary block appears **before** the regular scan output (market regime, exit triggers, buy candidates), with `===` separator. The existing `catch_up_notes` placeholder in System notes is replaced by this full block.

**D-05:** Split idempotency via **window approach**: on each scan, check splits where `split_date > max(entry_date, last_scan_date)` and `split_date <= today`. Since the window advances with each scan, a prior scan's split falls outside the next scan's window — no re-application needed.

**D-06:** Split math: `shares = floor(shares × ratio)`, and for all price fields divide by ratio: `entry_close /= ratio`, `highest_close /= ratio`, `initial_stop /= ratio`, `trailing_stop /= ratio`.

**D-07:** Split detection runs on **every scan**, not catch-up only.

**D-08:** Template 6 (dividend) — implement fully. Fetch `Ticker.dividends` for held positions during catch-up window only.

**D-09:** Template 7 (market delist) — best-effort. Trigger only when price data is completely absent across ALL missed trading days. Partial gaps do NOT trigger Template 7.

**D-10:** Templates 8-9 (regime change) — detect from existing `price_daily` data: compute SPX SMA 200 for each missed day using data already in DB. No new data fetch.

**D-11:** Add `positions.delisted INTEGER NOT NULL DEFAULT 0` via `run_migrations()` ALTER TABLE pattern (not Alembic). Schema.py updated to include the column.

**events.py location:** `src/bensdorp1/commands/events.py` — pure formatting functions (string templates).

**Split application ordering:** `_apply_splits()` runs at the start of `_update_position_stops` before the missed-days walk.

**Dividend fetch scope:** `Ticker.dividends` fetched only during catch-up (missed_days >= 1). Normal no-absence scans skip dividend events.

**Template 7 data-gap threshold:** "completely absent" = zero price_daily rows across ALL missed trading days for the symbol.

### Claude's Discretion

See above — all discretion items resolved as part of locked decisions in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

- Full yfinance-based market delist confirmation (cross-checking against exchange delisting notices) — Phase 13
- Snapshot tests for catch-up summary output — Phase 13
- `bensdorp1 validate DATE` with catch-up reconstruction — Phase 12
- Dividend tracking in `portfolio` and `detail` commands — out of scope for v1
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATE-05 | Catch-up logic for absences >= 2 trading days: reconstruct state (highest_close, trailing_stop) for all open positions over the missed days; surface 13 defined event templates | Covered by _scan_engine.py extension, events.py module, catch-up summary rendering |
| STATE-07 | Stocks delisted from S&P 500 while held — keep position open, continue stop monitoring, exclude from buy candidates | Covered by _detect_delisted_positions(), positions.delisted schema column, exclusion from buy candidate screening |
| DATA-06 | Split detection and automatic position adjustment (shares, entry_price, stops) on every scan for held positions | Covered by _apply_splits() using yfinance Ticker.splits, D-05 window approach |
</phase_requirements>

---

## Summary

Phase 11 extends the existing `run_scan()` pipeline in `_scan_engine.py` with three interconnected behaviors: catch-up state reconstruction with explicit output, split detection/adjustment on every scan, and delisted-from-index detection. All three behaviors build on infrastructure already in place — audit event types, trading day computation, stop arithmetic, and the scan engine pipeline — so this phase is primarily an extension of existing code rather than greenfield development.

The critical design insight is that the existing `_update_position_stops()` function already performs the silent missed-days walk. Phase 11 augments it: `_apply_splits()` is called first (before the walk begins), then the walk itself accumulates per-position events for the catch-up summary, and `_render_output()` is extended to emit the catch-up block before the regular scan sections. The `positions.delisted` column is added via the existing `run_migrations()` ALTER TABLE pattern (not a separate Alembic migration).

The 13 event templates in `events.py` are pure string-formatting functions — no I/O, no DB access — making them simple to implement and easy to test in isolation. The most complex integration point is the catch-up summary rendering, which must correctly collapse multi-event positions into the Template 13 composite format and build the retroactive-triggers table from whichever missed-day triggers are still pending.

**Primary recommendation:** Extend `_scan_engine.py` through targeted function additions (`_apply_splits`, `_detect_delisted_positions`, updated `_run_preflight`, updated `_render_output`) and create `events.py` as a pure formatting module. Add the schema column via `run_migrations()`. Test with `test_catchup.py` using the established `db_engine` fixture pattern and mocked yfinance calls.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Catch-up state reconstruction (silent) | `_scan_engine._update_position_stops` | `strategy.positions` (arithmetic) | Already owns the missed-days walk; Phase 11 adds event accumulation |
| Catch-up summary rendering (explicit) | `_scan_engine._render_output` | `commands.events` (templates) | Output layer owns rendering; events.py supplies formatted strings |
| Split detection + DB update | `_scan_engine._apply_splits` | `db.schema` (positions table) | New function, called before the missed-days walk |
| Split math | `strategy.positions` (existing) | — | `compute_trailing_stop`, `update_highest_close` already handle arithmetic |
| Delisting detection | `_scan_engine._detect_delisted_positions` | `db.schema` (positions.delisted) | New function, reads constituents set, writes positions.delisted flag |
| Event templates (13) | `commands.events` | — | Pure formatting, no I/O |
| Schema migration | `db.engine.run_migrations` | `db.schema` | Existing ALTER TABLE pattern; adds `positions.delisted` column |
| Audit logging | `db.audit.log_event` | — | Existing infrastructure; three new event types already registered |

---

## Standard Stack

No new external packages in this phase. All libraries already in `pyproject.toml`.

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yfinance | `>=1.3.0` | `Ticker.splits`, `Ticker.dividends` data access | Only data source permitted by CLAUDE.md |
| sqlalchemy | `>=2.0.49,<2.1` | Parameterized queries for position updates | Already used throughout |
| pandas | `>=3.0.3` | DatetimeIndex for split/dividend series | Already used throughout |

### No New Packages

This phase requires zero new dependencies. `yfinance.Ticker.splits` and `yfinance.Ticker.dividends` are native to the already-installed yfinance `>=1.3.0`. [VERIFIED: CLAUDE.md §Verified Library Versions]

---

## Package Legitimacy Audit

No new packages to install. Section not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
bensdorp1 scan
    |
    v
_run_preflight()
  |- compute missed_days (already exists)
  |- [NEW] _detect_delisted_positions() → positions.delisted flag + POSITION_DELISTED_FROM_INDEX event
  `- return (constituents, missed_days, catch_up_events[], freshness_days)
    |
    v
_fetch_data()  [unchanged — already fetches price data]
    |
    v
_load_price_dfs()  [unchanged]
    |
    v
_query_open_positions()  [unchanged — now reads positions.delisted column]
    |
    v
_update_position_stops()  [extended]
  |- [NEW] _apply_splits() at start
  |    |- yf.Ticker(symbol).splits → pd.Series
  |    |- filter: split_date in (max(entry_date,last_scan_date), today]
  |    |- apply math: shares*ratio, price fields/ratio
  |    |- UPDATE positions (DB + in-memory _OpenPosition)
  |    `- log_event(SPLIT_APPLIED)
  |
  |- missed-days walk [extended to accumulate per-position events]
  |    |- Template 1/2: stop violated
  |    |- Template 3: new highest close
  |    |- Template 5: split (if applied during catch-up window)
  |    |- Template 6: dividend (if missed_days >= 1)
  |    `- Template 13: composite (if multiple events)
  |
  `- Template 8/9: regime change (from price_daily SPX data)
    |
    v
_render_output()  [extended]
  |- [NEW] catch-up summary block (BEFORE regular sections)
  |    |- "You were absent for N trading days..."
  |    |- per-position entries (only positions with notable events)
  |    `- retroactive triggers table
  |
  |- regular scan sections (unchanged order)
  |    |- Market regime
  |    |- Exit triggers
  |    |- Pending exit triggers
  |    `- Buy candidates (excludes positions.delisted symbols)
  |
  `- System notes [split notifications from _apply_splits()]
    |
    v
_persist_scan()  [unchanged]
    |
    v
log_event(CATCH_UP_PERFORMED)  [NEW — only when missed_days >= 2]
log_event(SCAN_PERFORMED)  [unchanged]
create_backup()  [unchanged]
```

### Recommended Project Structure

No new directories needed. New and modified files:

```
src/bensdorp1/
├── commands/
│   ├── events.py              # NEW — 13 catch-up event template functions
│   └── _scan_engine.py        # MODIFIED — _apply_splits, _detect_delisted_positions,
│                              #            updated _run_preflight, _update_position_stops,
│                              #            _render_output, _query_open_positions
└── db/
    ├── schema.py              # MODIFIED — positions.delisted column
    └── engine.py              # MODIFIED — run_migrations() adds delisted column

tests/test_commands/
└── test_catchup.py            # NEW — unit + integration tests
```

### Pattern 1: _apply_splits() — Split Detection with Window Approach (D-05)

**What:** Fetch yfinance splits for each open position, filter to the window `(max(entry_date, last_scan_date), today]`, apply math and update DB atomically.

**When to use:** Called at the start of `_update_position_stops` on every scan.

```python
# Source: CONTEXT.md D-05, D-06; yfinance Ticker.splits documented in CONTEXT.md canonical refs
def _apply_splits(
    engine: Engine,
    open_positions: list[_OpenPosition],
    last_scan_date: date | None,
    today: date,
    split_notifications: list[str],
) -> list[_OpenPosition]:
    """Apply any stock splits that occurred since last scan.

    D-05: window approach — check split_date > max(entry_date, last_scan_date)
    and split_date <= today. Advances with each scan, so a split applied in a
    prior scan falls outside the next scan's window (no re-application).
    D-06: shares = floor(shares * ratio); price fields /= ratio.

    Modifies open_positions in-place via index replacement (same pattern as
    _update_position_stops). Returns updated list.
    """
    import math
    import yfinance as yf

    updated = list(open_positions)
    for idx, pos in enumerate(updated):
        window_start: date = max(
            pos.entry_date.date(),
            last_scan_date if last_scan_date is not None else pos.entry_date.date(),
        )
        try:
            splits: pd.Series = yf.Ticker(_to_yfinance(pos.symbol)).splits
        except Exception:
            continue  # data unavailable — skip split check for this position

        if splits.empty:
            continue

        # Filter to window: split_date > window_start and split_date <= today
        # splits.index is UTC-aware DatetimeIndex
        applicable = splits[
            (splits.index.date > window_start) & (splits.index.date <= today)
        ].sort_index()

        for split_date_ts, ratio in applicable.items():
            if ratio <= 0:
                continue
            split_date: date = split_date_ts.date()

            before = {
                "shares": pos.shares,
                "entry_close": pos.entry_close,
                "highest_close": pos.highest_close,
                "initial_stop": pos.initial_stop,
                "trailing_stop": pos.trailing_stop,
            }

            new_shares = math.floor(pos.shares * ratio)
            new_entry_close = pos.entry_close / ratio
            new_highest_close = pos.highest_close / ratio
            new_initial_stop = pos.initial_stop / ratio
            new_trailing_stop = pos.trailing_stop / ratio

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

            log_event(
                engine,
                AuditEventType.SPLIT_APPLIED,
                symbol=pos.symbol,
                payload={
                    "split_date": split_date.isoformat(),
                    "ratio": ratio,
                    "before": before,
                    "after": {
                        "shares": new_shares,
                        "entry_close": new_entry_close,
                        "highest_close": new_highest_close,
                        "initial_stop": new_initial_stop,
                        "trailing_stop": new_trailing_stop,
                    },
                },
            )

            # Build split notification for System notes (spec §8.3)
            ratio_str = f"{int(ratio)}:1" if ratio == int(ratio) else f"{ratio}:1"
            split_notifications.append(
                render_split_notification(
                    pos.symbol, ratio_str, split_date, pos.shares, new_shares,
                    pos.entry_close, new_entry_close
                )
            )

            # Update in-memory snapshot (same pattern as _update_position_stops)
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
```

**Note:** `_OpenPosition` NamedTuple will need `entry_close`, `shares`, and `delisted` fields added — the current definition only has `id`, `symbol`, `entry_date`, `initial_stop`, `highest_close`, `trailing_stop`. Phase 11 must extend `_OpenPosition` and the `_query_open_positions()` SELECT to include these new fields.

### Pattern 2: Schema Migration via run_migrations() (D-11)

**What:** The project does not use Alembic. Migrations are ALTER TABLE statements wrapped in try/except OperationalError inside `run_migrations()` in `db/engine.py`. [VERIFIED: existing pattern in engine.py lines 81-89]

```python
# Source: engine.py existing pattern (lines 81-89)
for stmt in [
    "ALTER TABLE positions ADD COLUMN closed_reason TEXT",
    "ALTER TABLE positions ADD COLUMN closed_manual_reason TEXT",
    # Phase 11 adds:
    "ALTER TABLE positions ADD COLUMN delisted INTEGER NOT NULL DEFAULT 0",
]:
    try:
        conn.execute(text(stmt))
        conn.commit()
    except OperationalError:
        pass  # column already exists — idempotent
```

**schema.py** must also be updated to add `Column("delisted", Integer, nullable=False, default=0)` to the `positions` Table definition so that `metadata.create_all()` creates it on fresh DBs.

### Pattern 3: events.py — Pure Template Functions

**What:** 13 functions, each accepting typed parameters and returning a formatted string. No I/O, no DB access.

**When to use:** Called from `_render_output()` and from the missed-days walk event accumulation.

```python
# Source: spec §8.9 verbatim wording
def render_initial_stop_violated(
    symbol: str, date: date, close: float, stop: float
) -> str:
    """Template 1."""
    return (
        f"{symbol}  Initial stop violated on {date.isoformat()} "
        f"(close {format_price(close)} < stop {format_price(stop)}).\n"
        f"      Position remained open during your absence.\n"
        f"      An exit trigger from that day is still pending."
    )


def render_trailing_stop_violated(
    symbol: str, date: date, close: float, stop: float
) -> str:
    """Template 2."""
    ...


def render_new_highest_close(
    symbol: str, date: date, close: float, old_stop: float, new_stop: float
) -> str:
    """Template 3. D-03: initial->final trailing stop only for composite."""
    ...


def render_composite(symbol: str, events: list[str]) -> str:
    """Template 13."""
    bullets = "\n".join(f"              - {e}" for e in events)
    return (
        f"{symbol}  Multiple events during your absence:\n{bullets}"
    )
```

### Pattern 4: _detect_delisted_positions() — Delisted-from-Index Detection

**What:** After open positions are queried, compare their symbols against the current constituents set. For positions whose symbol is absent and `delisted == 0`, set `delisted = 1`, log `POSITION_DELISTED_FROM_INDEX`, emit Template 4 event.

**When to use:** Called from `_run_preflight()` after constituents are loaded.

```python
# Source: CONTEXT.md D-11, spec §8.4
def _detect_delisted_positions(
    engine: Engine,
    open_positions: list[_OpenPosition],
    constituents: dict[str, str],
) -> list[str]:
    """Return list of catch-up event strings for newly delisted positions.

    Sets positions.delisted = 1 for first-time detection only (idempotent
    across subsequent scans — flag prevents re-logging on every scan).
    """
    events: list[str] = []
    constituent_symbols: set[str] = set(constituents.keys())
    for pos in open_positions:
        if pos.symbol not in constituent_symbols and pos.delisted == 0:
            with engine.connect() as conn:
                conn.execute(
                    update(positions)
                    .where(positions.c.id == pos.id)
                    .values(delisted=1)
                )
                conn.commit()
            log_event(
                engine,
                AuditEventType.POSITION_DELISTED_FROM_INDEX,
                symbol=pos.symbol,
                payload={"position_id": pos.id},
            )
            events.append(render_removed_from_sp500(pos.symbol, date=None))
    return events
```

### Anti-Patterns to Avoid

- **String formatting in _scan_engine.py:** All template strings must live in `events.py`, not inline in the scan engine. The engine calls events functions and passes results to the renderer.
- **Re-applying splits:** Do not use a boolean flag or extra DB column for split tracking. The D-05 window approach (`split_date > max(entry_date, last_scan_date)`) is self-advancing and idempotent without extra state.
- **Alembic:** This project does not use Alembic. All schema changes go through `run_migrations()` in `engine.py`. Do not create an `alembic.ini` or migrations/ directory.
- **Calling yfinance inside the missed-days walk:** Split and dividend fetches happen once per position at scan start (`_apply_splits()`), not per day in the walk. Fetching inside the day loop would repeat network calls unnecessarily.
- **Markup in console.print():** All strings passed to `capture.print()` must be wrapped in `Text()`. This is mandatory per the existing codebase convention (scan engine comments confirm this). Template strings from `events.py` contain no Rich markup so `Text(event_str)` is safe.
- **Blank _OpenPosition.delisted during tests:** The `db_engine` fixture calls `metadata.create_all()`, which uses the schema.py definition. If `delisted` is added to `positions` Table in schema.py, fresh test DBs will include it automatically. But existing tests that insert positions rows without `delisted` will fail if the column is `NOT NULL` without a default — always include `DEFAULT 0` in both the schema Column and the ALTER TABLE statement.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trading day arithmetic for catch-up window | Custom calendar logic | `get_trading_days(start, end)` from `bensdorp1.data` | Already correct, handles holidays, NYSE calendar |
| Stop computation during catch-up walk | Inline formulas | `update_highest_close()`, `compute_trailing_stop()`, `compute_effective_stop()` from `strategy.positions` | Strategy invariants must be centralized; Phase 11 must not duplicate arithmetic |
| Split ratio detection | Raw yfinance download parsing | `yf.Ticker(symbol).splits` — returns `pd.Series` with DatetimeIndex and float ratios | Correct and tested yfinance API for splits |
| Dividend fetch | Raw download parsing | `yf.Ticker(symbol).dividends` — returns `pd.Series` with DatetimeIndex | Correct yfinance API for dividends |
| Idempotent schema column add | Checking column existence before ALTER | `try/except OperationalError` pattern (existing `run_migrations()`) | SQLite raises `OperationalError: duplicate column name` on re-add; try/except is the established project pattern |
| Audit event writing | Direct SQL insert | `log_event(engine, AuditEventType.X, symbol=..., payload=...)` | Established abstraction in `db/audit.py` |

**Key insight:** Every reusable asset cited in CONTEXT.md `code_context` section is available and tested. Phase 11 composes existing pieces; almost nothing needs to be written from scratch except `events.py` templates and the new scan engine functions.

---

## Common Pitfalls

### Pitfall 1: _OpenPosition Missing Fields for Split Math

**What goes wrong:** `_apply_splits()` needs `pos.entry_close` and `pos.shares` to compute split-adjusted values, but the current `_OpenPosition` NamedTuple (lines 84-93 of `_scan_engine.py`) does NOT include `entry_close`, `shares`, or `delisted`.

**Why it happens:** `_OpenPosition` was defined for Phase 7 stop monitoring only — it only needed `initial_stop`, `highest_close`, `trailing_stop`.

**How to avoid:** The Phase 11 plan must extend `_OpenPosition` to add `entry_close: float`, `shares: int`, `delisted: int` fields AND update `_query_open_positions()` to SELECT those columns from the `positions` table.

**Warning signs:** `AttributeError: _OpenPosition has no attribute 'entry_close'` at runtime or in tests.

### Pitfall 2: Naive vs UTC-aware DatetimeIndex from yfinance.splits

**What goes wrong:** `yf.Ticker(symbol).splits` returns a `pd.Series` with a UTC-aware `DatetimeIndex`. Comparing `.index.date > window_start` where `window_start` is a `datetime.date` works correctly (date objects are tz-naive by definition), but comparing against a UTC-aware Timestamp can silently fail in edge cases.

**Why it happens:** pandas comparison between DatetimeIndex and date uses `.normalize()` internally, but off-by-one errors can appear around midnight UTC on the split effective date.

**How to avoid:** Always extract `.date()` from each Timestamp when comparing: `splits.index.normalize().date` or iterate with `split_date_ts.date()`. Use `sort_index()` before applying splits in chronological order.

**Warning signs:** A split that should apply gets skipped, or a split is applied twice in the same scan.

### Pitfall 3: catch_up_notes vs catch_up_events Parameter Rename

**What goes wrong:** `_render_output()` currently accepts `catch_up_notes: list[str]` and renders them in System notes. Phase 11 replaces this with `catch_up_events: list[str]` (or similar) rendered as a full block BEFORE the regular scan sections.

**Why it happens:** Callers of `_render_output()` in `run_scan()` and in tests pass `catch_up_notes`. All callers must be updated.

**How to avoid:** The plan must update both the function signature AND all call sites (`run_scan()`, test helpers). The old System notes behavior ("No catch-up actions needed.") must also be updated.

**Warning signs:** `TypeError: _render_output() got an unexpected keyword argument` in tests after renaming.

### Pitfall 4: Delisted Flag in Test DBs

**What goes wrong:** Existing tests that insert positions rows without specifying `delisted` break if the column is `NOT NULL` with no default at the Python/SQLAlchemy level.

**Why it happens:** `metadata.create_all()` uses the Column definition. If `Column("delisted", Integer, nullable=False, default=0)` is added but tests insert via raw `insert(positions).values(symbol=..., ...)` without `delisted=0`, SQLite may raise an IntegrityError or use NULL.

**How to avoid:** SQLAlchemy's `Column(default=0)` provides a server-default only on ORM inserts. For Core inserts without specifying the column, use `server_default=text("0")` in the Column definition. Or use `DEFAULT 0` in the ALTER TABLE statement which applies at the SQLite level and is respected for existing rows.

**Correct column definition:**
```python
Column("delisted", Integer, nullable=False, server_default=text("0"))
```

**Warning signs:** `IntegrityError: NOT NULL constraint failed: positions.delisted` on tests that insert positions without specifying the new column.

### Pitfall 5: Catch-Up Summary for 1 Missed Day (N=1 vs N>=2)

**What goes wrong:** The catch-up block (spec §7.6) is triggered for "N >= 2 trading days" absences. If `len(missed_days) == 1`, that is a normal 1-day gap (user just missed yesterday) and does NOT trigger the catch-up summary banner. However, split detection and delisting detection still run on every scan regardless of missed_days count (D-07).

**Why it happens:** Confusing the catch-up summary trigger threshold (N>=2) with the existing missed-days walk (which already handles N=1 silently in Phase 7).

**How to avoid:** The catch-up summary block, CATCH_UP_PERFORMED audit event, and Template outputs are only emitted when `len(missed_days) >= 1` (since missed_days = trading days between last_scan+1 and yesterday inclusive, a value of 1 means user missed exactly 1 day). Check CONTEXT.md §7.6 again: "absence of N >= 2 trading days" — "trading days since last scan" includes missed_days + today, so the trigger is `len(missed_days) >= 1` (at least 1 day was missed between last scan and today, meaning at least 2 trading days elapsed total). Confirm exact threshold interpretation against spec §7.6.

**Warning signs:** Catch-up summary shown for normal consecutive-day scans, or catch-up summary absent after a 2-day absence.

### Pitfall 6: Template 3 Initial→Final Stop Wording (D-03)

**What goes wrong:** If AAPL hits a new highest close on days 1, 2, and 3 of a 3-day absence, three Template 3 events are generated individually. D-03 requires that in a composite entry, only initial→final trailing stop values are shown.

**Why it happens:** Naive accumulation pushes one Template 3 per new-highest-close day into the events list.

**How to avoid:** When collapsing per-position events into a composite (Template 13), detect multiple Template 3 events and replace them with a single merged Template 3 showing the initial trailing stop (from the start of the absence) and the final trailing stop (after all missed days). The events accumulation logic must track "was there at least one new highest close?" rather than adding a separate string per day.

**Warning signs:** Composite output shows three "Trailing stop updated from $X to $Y" bullets for the same position.

### Pitfall 7: last_scan_date for Split Window Start

**What goes wrong:** `_apply_splits()` needs `last_scan_date` (the date of the most recent prior scan) to compute the split window start. This value is already computed in `_run_preflight()` (via `scans.c.scan_date.desc().limit(1)` query), but it is not currently returned or passed to `_update_position_stops()`.

**Why it happens:** `_run_preflight()` currently returns `(constituents, missed_days, catch_up_notes, freshness_days)`. The `last_scan_date` is used locally but not propagated.

**How to avoid:** Extend `_run_preflight()` return tuple to include `last_scan_date: date | None`, and thread it through `run_scan()` → `_update_position_stops()` → `_apply_splits()`.

---

## Code Examples

### yfinance Ticker.splits Access

```python
# Source: CONTEXT.md §Canonical References — Technology section
import yfinance as yf

splits = yf.Ticker("NVDA").splits
# pd.Series with DatetimeIndex (UTC-aware) and float values
# e.g. pd.Series([2.0], index=DatetimeIndex(['2024-06-10 00:00:00+00:00']))
# A 2:1 split has ratio 2.0

# Filter to window
applicable = splits[
    (splits.index.date > window_start) & (splits.index.date <= today)
].sort_index()
```

### yfinance Ticker.dividends Access

```python
# Source: CONTEXT.md §Canonical References — Technology section
import yfinance as yf

dividends = yf.Ticker("AAPL").dividends
# pd.Series with DatetimeIndex and float dividend-per-share values
# When auto_adjust=True is used for price data, dividends are in adjusted terms

# Filter to catch-up window
div_in_window = dividends[
    (dividends.index.date > last_scan_date) & (dividends.index.date <= today)
]
```

### Catch-Up Summary Output Format (spec §7.6 verbatim)

```
================================================================
Catch-up summary
================================================================

You were absent for 5 trading days (2026-05-16 to 2026-05-21).

State has been updated for 2 open positions.

AAPL  Trailing stop violated on 2026-05-18 (close $178.20 < stop $179.50)
      Position remained open during your absence.
      An exit trigger from that day is still pending.

MSFT  New highest close reached on 2026-05-17 ($325.40).
      Trailing stop updated from $240.00 to $244.05.
      No exit trigger.

The following retroactive exit triggers are still pending. They will
also appear in today's scan output below.

Symbol  Triggered on   Reason
------  -------------  ---------------
AAPL    2026-05-18     Trailing stop

Confirm sells with `bensdorp1 sell SYMBOL PRICE` as soon as you execute
them at market open.
```

### Split Notification in System Notes (spec §8.3 verbatim)

```
NVDA  Split applied: 2:1 (effective 2026-05-19)
      Shares: 23 → 46
      Entry price: $432.50 → $216.25
```

### All 13 Template Signatures for events.py

Template parameters to implement (spec §8.9):

| Template | Function Name | Key Parameters |
|----------|---------------|----------------|
| 1 | `render_initial_stop_violated` | symbol, date, close, stop |
| 2 | `render_trailing_stop_violated` | symbol, date, close, stop |
| 3 | `render_new_highest_close` | symbol, date, close, old_stop, new_stop |
| 4 | `render_removed_from_sp500` | symbol, date (may be None — detected at scan time) |
| 5 | `render_stock_split` | symbol, ratio_str, date, old_shares, new_shares, old_price, new_price |
| 6 | `render_dividend` | symbol, date, amount |
| 7 | `render_market_delist` | symbol, date |
| 8 | `render_regime_bull_to_bear` | date |
| 9 | `render_regime_bear_to_bull` | date |
| 10 | `render_constituents_updated` | date, n_added, n_removed |
| 11 | `render_data_fetch_failed` | n_days, dates_list |
| 12 | `render_trading_holidays` | n, dates_list |
| 13 | `render_composite` | symbol, events_list |

---

## Runtime State Inventory

> Not a rename/refactor phase — omit standard runtime state categories. However, one persistent state concern applies:

**Existing open positions in production DB:** The `positions.delisted` column will be `0` (DEFAULT) for all existing rows after the `run_migrations()` ALTER TABLE runs. This is correct behavior — positions that were previously open but whose symbol is delisted from the index will be detected and flagged on the first Phase 11 scan. No data migration needed; the DEFAULT 0 means "not yet known to be delisted."

**Split history:** No historical splits are retroactively applied. The D-05 window approach means only splits occurring after `max(entry_date, last_scan_date)` are applied. Any splits that occurred while the user was running Phase 7-era scans (when split detection was deferred) and that fall before the last scan date will be permanently skipped. This is the accepted behavior per CONTEXT.md scope — Phase 11 is forward-looking only.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| yfinance | `Ticker.splits`, `Ticker.dividends` | Already installed | `>=1.3.0` | — |
| pandas | Split/dividend Series operations | Already installed | `>=3.0.3` | — |
| SQLAlchemy | Position updates | Already installed | `>=2.0.49,<2.1` | — |
| pytest | Test suite | Already installed | `>=8.3` | — |

No missing dependencies. All required libraries are already in `pyproject.toml`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_commands/test_catchup.py -x` |
| Full suite command | `uv run pytest --cov=src/bensdorp1 --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATE-05 | Catch-up walk updates highest_close/trailing_stop for all missed days | unit | `pytest tests/test_commands/test_catchup.py::test_catchup_stop_reconstruction -x` | ❌ Wave 0 |
| STATE-05 | Catch-up summary renders with correct per-position entries | unit | `pytest tests/test_commands/test_catchup.py::test_catchup_summary_rendering -x` | ❌ Wave 0 |
| STATE-05 | Template 13 composite for multiple events per position | unit | `pytest tests/test_commands/test_catchup.py::test_composite_template -x` | ❌ Wave 0 |
| STATE-05 | Template 3 shows initial→final stop only in composite (D-03) | unit | `pytest tests/test_commands/test_catchup.py::test_template3_initial_final_only -x` | ❌ Wave 0 |
| STATE-05 | CATCH_UP_PERFORMED audit event logged | unit | `pytest tests/test_commands/test_catchup.py::test_catch_up_audit_event -x` | ❌ Wave 0 |
| STATE-05 | Split applied during absence shows Template 5 in catch-up | unit | `pytest tests/test_commands/test_catchup.py::test_split_in_catchup_template -x` | ❌ Wave 0 |
| DATA-06 | _apply_splits() updates shares and price fields per D-06 | unit | `pytest tests/test_commands/test_catchup.py::test_apply_splits_math -x` | ❌ Wave 0 |
| DATA-06 | Split detection is idempotent on consecutive scans (D-05 window) | unit | `pytest tests/test_commands/test_catchup.py::test_split_idempotent -x` | ❌ Wave 0 |
| DATA-06 | Split audit event logged with before/after payload | unit | `pytest tests/test_commands/test_catchup.py::test_split_audit_event -x` | ❌ Wave 0 |
| DATA-06 | No split applied when split_date <= last_scan_date | unit | `pytest tests/test_commands/test_catchup.py::test_split_outside_window_ignored -x` | ❌ Wave 0 |
| STATE-07 | Delisted position: delisted flag set to 1 on first detection | unit | `pytest tests/test_commands/test_catchup.py::test_delisted_flag_set -x` | ❌ Wave 0 |
| STATE-07 | Delisted position: POSITION_DELISTED_FROM_INDEX event logged once | unit | `pytest tests/test_commands/test_catchup.py::test_delisted_event_not_repeated -x` | ❌ Wave 0 |
| STATE-07 | Delisted symbol excluded from buy candidates | unit | `pytest tests/test_commands/test_catchup.py::test_delisted_excluded_from_candidates -x` | ❌ Wave 0 |
| STATE-07 | Template 4 rendered for delisted position in catch-up summary | unit | `pytest tests/test_commands/test_catchup.py::test_delisted_template4 -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_commands/test_catchup.py -x`
- **Per wave merge:** `uv run pytest --cov=src/bensdorp1 --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_commands/test_catchup.py` — covers all requirements above (file does not yet exist)

*(All test infrastructure — pytest, db_engine fixture, CliRunner — is already in place. Only the test file itself is missing.)*

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | yfinance data treated as untrusted numeric input; ratio <= 0 guard in `_apply_splits()` |
| V6 Cryptography | no | — |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Split ratio manipulation (malformed yfinance response) | Tampering | Guard `ratio <= 0` before applying; catch exceptions from `yf.Ticker().splits` |
| SQL injection via symbol name | Tampering | SQLAlchemy parameterized queries only — no string interpolation (established project rule) |
| Data-gap false positives triggering Template 7 | Spoofing | Template 7 threshold requires zero rows across ALL missed days (D-09) — partial gaps excluded |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `catch_up_notes: list[str]` in System notes | Full catch-up summary block before regular scan | Phase 11 | Significant UI change — `_render_output()` signature changes |
| Split detection deferred (TODO comment in prices.py) | `_apply_splits()` on every scan | Phase 11 | DATA-06 completed |
| positions table has no delisted column | `positions.delisted INTEGER NOT NULL DEFAULT 0` | Phase 11 | STATE-07 completed |

**Deprecated/outdated after Phase 11:**
- `catch_up_notes` parameter name in `_render_output()` — replaced by structured catch-up event data
- Comment in `data/__init__.py` docstring: "DATA-06 split detection deferred to Phase 11" — remove after implementation

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | yfinance `Ticker.splits` and `Ticker.dividends` are available in yfinance >= 1.3.0 without additional parameters | Standard Stack | Low — these APIs predate 1.0 stable; CONTEXT.md explicitly cites them as the canonical approach |
| A2 | `splits.index.date` attribute is available on a UTC-aware DatetimeIndex for element-wise date comparison | Pattern 1 code example | Low — standard pandas API; alternative is `.normalize()` or `.tz_convert(None).date` |
| A3 | The missed-days walk threshold for showing the catch-up summary is `len(missed_days) >= 1` (at least 1 day elapsed between last scan and today) | Pitfall 5 | Medium — spec says "N >= 2 trading days" which could mean the summary banner is only shown when missed_days >= 2. Planner should confirm against spec §7.6 exact wording before coding the threshold condition. |

---

## Open Questions (RESOLVED)

1. **Catch-up summary threshold: is it len(missed_days) >= 1 or >= 2?**
   - What we know: spec §7.6 says "absence of N >= 2 trading days". `missed_days` in the existing code is `get_trading_days(last_scan_date + 1, yesterday)`. If the user scanned Monday and runs again Wednesday, `missed_days = [Tuesday]` — length 1. Total trading days elapsed = 2 (Tuesday + today).
   - What's unclear: does the spec threshold of "N >= 2" mean 2 elapsed days (so len(missed_days) >= 1 triggers the summary) or 2 missed days (len(missed_days) >= 2)?
   - Recommendation: The spec example shows "absent for 5 trading days" with an explicit multi-day range. Given CONTEXT.md D-01 says "when absent >= 2 trading days," interpret this as len(missed_days) >= 1 (one missed day means two elapsed trading days). The planner should confirm this interpretation or add a code comment referencing the spec.
   - **RESOLVED:** Use `len(missed_days) >= 1` — one missed day means two elapsed trading days, satisfying the spec's "N >= 2 trading days" threshold. All plans (Plan 02 Task 2, Plan 03 Task 2) use this interpretation consistently.

2. **Template 4 (removed from S&P 500) date parameter**
   - What we know: Template 4 says `{SYMBOL}  Removed from S&P 500 on {DATE}.` but the detection happens at scan time by comparing current constituents — the exact removal date is not stored.
   - What's unclear: what date to use for the template — today's scan date, or some yfinance-derived date?
   - Recommendation: Use today's date as the detection date, with a comment that the actual removal may have occurred during the absence. The CONTEXT.md D-09 pattern for Template 7 sets a precedent for best-effort data.
   - **RESOLVED:** Use `date=None` — `render_removed_from_sp500(symbol, removal_date=None)` omits the " on {DATE}" clause when None (best-effort detection at scan time). Plans 01 Task 2 and 02 Task 2 both use `None` consistently.

---

## Sources

### Primary (HIGH confidence)
- `src/bensdorp1/commands/_scan_engine.py` — full scan pipeline read; Phase 11 integration points verified
- `src/bensdorp1/db/engine.py` — `run_migrations()` ALTER TABLE pattern verified (lines 81-89)
- `src/bensdorp1/db/schema.py` — `positions` table columns verified; `delisted` column absent
- `src/bensdorp1/db/audit.py` — `AuditEventType.SPLIT_APPLIED`, `POSITION_DELISTED_FROM_INDEX`, `CATCH_UP_PERFORMED` verified present; `log_event()` signature verified
- `.planning/Bensdorp_1.md §7.6` — catch-up flow spec read in full; verbatim output format captured
- `.planning/Bensdorp_1.md §8.3` — split behavior spec read in full
- `.planning/Bensdorp_1.md §8.4` — delisted-from-index spec read in full
- `.planning/Bensdorp_1.md §8.9` — all 13 event templates read in full; template strings are verbatim
- `.planning/Bensdorp_1.md §9.1` — audit event taxonomy verified
- `.planning/phases/11-catch-up-logic/11-CONTEXT.md` — all decisions D-01 through D-11 read in full
- `CLAUDE.md §Verified Library Versions` — yfinance `>=1.3.0`, pandas, SQLAlchemy versions verified
- `tests/conftest.py` — `db_engine` fixture pattern verified for test guidance
- `src/bensdorp1/strategy/positions.py` — reusable stop arithmetic functions verified

### Secondary (MEDIUM confidence)
- CONTEXT.md §canonical_refs — yfinance API descriptions for `Ticker.splits` and `Ticker.dividends`

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in use; no new packages
- Architecture: HIGH — existing code fully read; integration points identified precisely
- Pitfalls: HIGH — derived from direct inspection of existing _OpenPosition definition and engine.py migration pattern
- Event templates: HIGH — spec §8.9 read verbatim

**Research date:** 2026-05-30
**Valid until:** 2026-07-30 (stable stack — yfinance, pandas, SQLAlchemy APIs do not change frequently)
