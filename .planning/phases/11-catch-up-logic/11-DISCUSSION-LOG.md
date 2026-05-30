# Phase 11: Catch-Up Logic - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 11-catch-up-logic
**Areas discussed:** Catch-up summary detail, Split detection idempotency, Template 6 & 7 scope, Schema/split frequency confirmations

---

## Catch-up summary detail

### Q: Positions with no notable events

| Option | Description | Selected |
|--------|-------------|----------|
| Silent — counted only | Counted in "State updated for N positions" but no per-position entry. Matches spec §7.6 example. | ✓ |
| Brief entry for each | Show "NVDA  No notable events during your absence." for zero-event positions. | |

**User's choice:** Silent — counted only
**Notes:** User confirmed this matches spec intent.

### Q: Multiple notable events per position

| Option | Description | Selected |
|--------|-------------|----------|
| Template 13 composite | One entry per position with a bullet list of events. | ✓ |
| One entry per event | Separate entry per event, repeating symbol name. | |

**User's choice:** Template 13 composite

### Q: Stop update granularity in composite

| Option | Description | Selected |
|--------|-------------|----------|
| Initial → final only | "Trailing stop updated from $240.00 to $252.75." One line regardless of intermediate steps. | ✓ |
| Each step | Show every intermediate new high. | |

**User's choice:** Initial → final only

### Q: Catch-up summary placement

| Option | Description | Selected |
|--------|-------------|----------|
| Before regular scan output | Full catch-up block with === separator, regular scan follows. Matches spec §7.6. | ✓ |
| After (in System notes) | Keep at bottom. No refactoring needed. | |

**User's choice:** Before regular scan output (confirmed)

---

## Split detection idempotency

### Q: Tracking mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Window approach | Check splits where split_date > max(entry_date, last_scan_date). No extra state needed. | ✓ |
| Audit log query | Query SPLIT_APPLIED events per position to find applied split dates. | |
| New tracking column | Add positions.last_split_check_date column. | |

**User's choice:** Window approach
**Notes:** Naturally idempotent — window advances with each scan, old splits fall outside.

### Q: Split math formula

| Option | Description | Selected |
|--------|-------------|----------|
| Multiply shares, divide prices | shares = floor(shares × ratio); prices /= ratio for entry_close, highest_close, initial_stop, trailing_stop. | ✓ |
| You decide | Let Claude work out the formula. | |

**User's choice:** Multiply shares, divide prices (confirmed)

---

## Template 6 & 7 scope

### Q: Template 6 — dividends

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, implement fully | Fetch Ticker.dividends during catch-up window, show informational message. | ✓ |
| Defer to Phase 13 | Skip for Phase 11. | |

**User's choice:** Yes, implement fully

### Q: Template 7 — market delist

| Option | Description | Selected |
|--------|-------------|----------|
| Best-effort: missing price data flag | If price data absent for held position across full catch-up window, show Template 7 with "Verify via broker." | ✓ |
| Defer to Phase 13 | Show "data_unavailable" note instead. | |
| Full implementation | Cross-reference exchange delisting data. | |

**User's choice:** Best-effort: missing price data flag

---

## Schema and split frequency confirmations

### Q: positions.delisted column

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add via migration | Add positions.delisted INTEGER NOT NULL DEFAULT 0 in a new Alembic migration. | ✓ |
| Use audit log instead | Query audit_log for POSITION_DELISTED_FROM_INDEX to know if already logged. | |

**User's choice:** Yes, add via migration

### Q: Split detection frequency

| Option | Description | Selected |
|--------|-------------|----------|
| Every scan | Check splits on every scan, even without absence. | ✓ |
| Catch-up only | Skip split detection on normal day scans. | |

**User's choice:** Every scan (confirmed spec §8.3)

---

## Claude's Discretion

- **events.py location:** `src/bensdorp1/commands/events.py` — per spec directory tree; formatting functions, not strategy logic
- **Split application ordering:** `_apply_splits()` runs before the missed-days walk so adjusted values are used throughout stop computation
- **Dividend fetch scope:** only during catch-up (missed_days ≥ 1); no dividend events on normal scans
- **Template 7 data-gap threshold:** "completely absent" = zero price_daily rows for the symbol across ALL missed trading days; partial gaps use Template 11 (data fetch failure) instead
- **Templates 8-9 (regime change):** detect from existing price_daily data — compute SPX SMA 200 per missed day using DB data; no new data fetch

## Deferred Ideas

- Full yfinance-based market delist confirmation (exchange notices) — Phase 13 edge cases
- Snapshot tests for catch-up output — Phase 13
- Dividend tracking in portfolio/detail commands — out of scope for v1
