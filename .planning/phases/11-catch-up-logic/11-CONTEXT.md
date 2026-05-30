# Phase 11: Catch-Up Logic - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 11 adds three interconnected behaviors to `bensdorp1 scan`:

1. **Catch-up reconstruction + output** — when absent ≥ 2 trading days, the silent state reconstruction (already in Phase 7's `_update_position_stops`) is augmented with the full "Catch-up summary" banner per spec §7.6 and all 13 event templates (spec §8.9)
2. **Split detection** — on every scan (not catch-up only), check yfinance splits for held positions; adjust stored position values (`shares`, `entry_close`, `highest_close`, `initial_stop`, `trailing_stop`) when a split is detected
3. **Delisted-from-index handling** — detect held positions whose symbol is no longer in S&P 500 constituents; keep monitoring, exclude from buy candidates, log `position_delisted_from_index` event once

**Specifically delivers:**
- `src/bensdorp1/commands/events.py` — 13 catch-up event template rendering functions
- `_scan_engine.py` modifications: `_apply_splits()`, `_detect_delisted_positions()`, updated `_run_preflight()`, updated `_render_output()` with catch-up summary block
- Alembic migration: `positions.delisted INTEGER NOT NULL DEFAULT 0` column
- `tests/test_commands/test_catchup.py` — unit + integration tests for all new behaviors

**Does NOT include:** `bensdorp1 validate DATE` (Phase 12), snapshot tests (Phase 13), regime change audit events on non-catch-up scans (already in Phase 7 scan_performed payload).

</domain>

<decisions>
## Implementation Decisions

### Catch-up summary output

- **D-01:** Positions with no notable events during absence (stop didn't trigger, no new highest close, no split, not delisted) are **silent** — counted in the "State has been updated for N open positions" summary line but get no per-position entry. Matches spec §7.6 example exactly.
- **D-02:** Positions with multiple notable events across missed days → **Template 13 composite** format: one entry per position with a bullet list of events. Not a flat list with repeated symbol names.
- **D-03:** For the trailing stop updated message (Template 3) within a composite entry → show **initial → final only** ("Trailing stop updated from $240.00 to $252.75.") regardless of how many intermediate new highs occurred during the absence. Reduces noise for multi-day trending positions.
- **D-04:** Catch-up summary section appears **before** the regular scan output (market regime, exit triggers, buy candidates), with a `===` separator — exactly as spec §7.6 shows. Current "System notes" catch_up_notes placeholder is replaced by this full block. Then the regular scan output follows.

### Split detection

- **D-05:** Idempotency via **window approach**: on each scan, check splits where `split_date > max(entry_date, last_scan_date)` and `split_date <= today`. Since the window advances with each scan, a split applied in a prior scan falls outside the next scan's window — no re-application, no extra tracking state needed.
- **D-06:** Split math: `shares = floor(shares × ratio)`, and for all price-based fields divide by ratio: `entry_close /= ratio`, `highest_close /= ratio`, `initial_stop /= ratio`, `trailing_stop /= ratio`. yfinance `.splits` returns ratio as float (e.g., 2.0 for a 2:1 split).
- **D-07:** Split detection runs on **every scan**, not catch-up only. A split on a normal no-absence scan day still needs to be applied before today's stop computation.

### Template scope

- **D-08:** **Template 6 (dividend)** — implement fully. Fetch `Ticker.dividends` for held positions during the catch-up window only (between last_scan_date and today). Show "Dividend paid on {DATE}: ${AMOUNT} per share. No impact on strategy (using adjusted prices)." yfinance returns pre-tax dividends per share.
- **D-09:** **Template 7 (market delist)** — best-effort implementation. If price data is completely absent from `price_daily` for a held position's symbol across the expected catch-up window dates, show Template 7 with a note: "Verify via broker — data unavailable from yfinance." This covers the bankruptcy/full-delist case without false positives on isolated data gaps (which would show a partial absence, not total absence).
- **D-10:** **Templates 8-9 (regime change)** — detect from existing `price_daily` data: compute SPX SMA 200 for each missed trading day using the data already in the DB. A regime transition is logged when the regime flips between consecutive missed days. No new data fetch needed.

### Schema change

- **D-11:** Add `positions.delisted INTEGER NOT NULL DEFAULT 0` column via **Alembic migration**. The flag is set to 1 when the position's symbol is first detected absent from the current constituents list (preventing re-logging `POSITION_DELISTED_FROM_INDEX` on every subsequent scan). Schema.py must be updated to include the column.

### Claude's Discretion

- **events.py location:** `src/bensdorp1/commands/events.py` — per spec's directory tree (§3.2). These are pure formatting functions (string templates), not strategy logic, so they live alongside commands rather than in `strategy/`.
- **Split application ordering:** a new `_apply_splits()` function runs at the start of `_update_position_stops` (before the missed-days walk), applying all detected splits in chronological order to each open position. This ensures adjusted position values are used for all subsequent stop computations. The in-memory `_OpenPosition` snapshot and DB row are both updated atomically per split.
- **Dividend fetch scope:** `Ticker.dividends` is fetched only during catch-up (missed_days ≥ 1). Normal no-absence scans skip dividend events entirely (nothing to show for today-only scans).
- **Template 7 data-gap threshold:** "completely absent" means zero price_daily rows for the symbol across ALL missed trading days. A single partial gap (some days missing, others present) should NOT trigger Template 7 — show the normal stop/trigger events for available days and note "Data unavailable for N days" using Template 11 (data fetch failure).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary specification (authoritative)

- `.planning/Bensdorp_1.md` §7.6 — Catch-up flow: Phase A (silent reconstruction) + Phase B (explicit reporting), exact output format with separator and per-position entries
- `.planning/Bensdorp_1.md` §8.3 — Splits: detection mechanism (`yfinance.splits`), adjustment formula, `split_applied` audit event, notification in System notes
- `.planning/Bensdorp_1.md` §8.4 — Stocks delisted from S&P 500: keep position open, exclude from buy candidates, `position_delisted_from_index` audit event when first detected
- `.planning/Bensdorp_1.md` §8.9 — All 13 catch-up event templates with exact wording (mandatory — copy template strings verbatim)
- `.planning/Bensdorp_1.md` §9.1 — Audit event taxonomy: `split_applied`, `position_delisted_from_index`, `catch_up_performed` event types
- `.planning/REQUIREMENTS.md` STATE-05, STATE-07, DATA-06

### Existing scan engine (read before modifying)

- `src/bensdorp1/commands/_scan_engine.py` — full scan pipeline; `_run_preflight()` already detects missed_days and populates catch_up_notes; `_update_position_stops()` already walks missed days; `_render_output()` already has a `catch_up_notes` parameter in System notes
- `src/bensdorp1/commands/scan.py` — thin Typer wrapper; no changes needed here
- `src/bensdorp1/db/schema.py` — `positions` table definition; Phase 11 adds `delisted` column
- `src/bensdorp1/db/audit.py` — `AuditEventType.SPLIT_APPLIED`, `POSITION_DELISTED_FROM_INDEX`, `CATCH_UP_PERFORMED` already exist; `log_event()` call pattern
- `src/bensdorp1/strategy/positions.py` — `update_highest_close()`, `compute_trailing_stop()`, `compute_effective_stop()` — reuse these for the missed-days walk (unchanged)

### Data layer

- `src/bensdorp1/data/prices.py` — `update_price_data()` is already called before Phase 11's logic runs; yfinance calls use `auto_adjust=True` throughout (adjusted prices only)
- `src/bensdorp1/data/__init__.py` — `get_trading_days(start, end)` — use for missed_days computation (already used in `_run_preflight`)

### Prior phase context

- `.planning/phases/10-system-commands/10-CONTEXT.md` — D-16: single-file pattern; established patterns for audit event logging, confirm_prompt flow
- `.planning/phases/07-scan-command/07-CONTEXT.md` — original catch-up detection design decisions (D-07 through D-11 from that phase)

### Technology

- `CLAUDE.md` §Verified Library Versions — yfinance >=1.3.0
- yfinance `Ticker.splits` returns a `pd.Series` with DatetimeIndex (UTC-aware) and float values (split ratio). A 2:1 split has ratio 2.0. Access via `yf.Ticker(symbol).splits`.
- yfinance `Ticker.dividends` returns a `pd.Series` with DatetimeIndex and float values (dividend per share, in adjusted terms when `auto_adjust=True`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `_run_preflight()` in `_scan_engine.py` — already computes `missed_days` (pd.DatetimeIndex) and passes them down; Phase 11 extends the return value to include split events and per-position catch-up events
- `_update_position_stops()` — already walks missed days + today; Phase 11 calls `_apply_splits()` at the start of this function before the day loop begins
- `get_trading_days(start, end)` from `bensdorp1.data` — reused for the catch-up date range
- `update_highest_close()`, `compute_trailing_stop()`, `compute_effective_stop()` from `strategy.positions` — unchanged; used in both the existing missed-days walk and in split-adjusted stop recomputation
- `log_event()` with `AuditEventType.SPLIT_APPLIED` / `POSITION_DELISTED_FROM_INDEX` / `CATCH_UP_PERFORMED` — call pattern established in `db/audit.py`
- `render_table()`, `render_kv_block()` from `bensdorp1.ui` — used in catch-up summary section
- `SEPARATOR` constant (`"=" * 64`) — reuse for catch-up summary header (matches spec §7.6 format)

### Established Patterns

- `_OpenPosition` NamedTuple in `_scan_engine.py` — replace in-memory list element after split application (same pattern as `_update_position_stops` does for stop updates at line 529)
- Console ownership: `capture` Console (record=True, width=120) for captured output, `con` for live progress — catch-up summary goes to `capture`
- `Text()` wrapping for all strings passed to `console.print()` — mandatory per markup safety rules
- SQLAlchemy parameterized queries only — no string interpolation
- CliRunner from `typer.testing` for all CLI tests

### Integration Points

- **Where Phase 11 inserts into pipeline:** After `_fetch_data()` (step 2) and `_load_price_dfs()` (step 3), but BEFORE `_query_open_positions()` (step 4) would be ideal — however split application happens after open positions are queried. The order in `run_scan()` needs: (1) query open positions, (2) apply splits, (3) walk missed days + today. Steps 4 and 5 in the current pipeline cover this, but step 5 (`_update_position_stops`) needs to call `_apply_splits()` first.
- **Schema migration:** `db/migrations/` directory (Alembic); pattern established in Phase 2
- **Catch-up summary in `_render_output()`:** New parameter `catch_up_events: list[str]` replaces `catch_up_notes: list[str]`. The catch-up block is rendered BEFORE section 1 (header) only when `len(catch_up_events) > 0`.

</code_context>

<specifics>
## Specific Ideas

### Catch-up summary example (spec §7.6 verbatim format)

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

### Split notification in System notes (spec §8.3 verbatim format)

```
NVDA  Split applied: 2:1 (effective 2026-05-19)
      Shares: 23 → 46
      Entry price: $432.50 → $216.25
```

### Template 7 best-effort output

```
SIVB  Delisted from the market — no price data available.
      Verify via broker. Manual action required:
      `bensdorp1 sell SIVB PRICE --manual "Delisted"`
```

</specifics>

<deferred>
## Deferred Ideas

- Full yfinance-based market delist confirmation (cross-checking against exchange delisting notices) — Phase 13 edge cases
- Snapshot tests for catch-up summary output — Phase 13
- `bensdorp1 validate DATE` with catch-up reconstruction — Phase 12
- Dividend tracking in `portfolio` and `detail` commands — out of scope for v1

None beyond the above — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-Catch-Up Logic*
*Context gathered: 2026-05-30*
