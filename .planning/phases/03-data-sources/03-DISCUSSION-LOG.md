# Phase 3: Data Sources - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 3-Data Sources
**Areas discussed:** Download strategy, Scan-time data freshness, Constituents unavailability, SPX handling

---

## Download Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid (bulk + per-symbol retry) | Bulk `yfinance.download(tickers)` first; retry missing/incomplete symbols individually with 1s/2s/4s backoff | ✓ |
| Per-symbol only | Loop each ticker individually; full retry granularity, slow (20–40 min for 500 stocks) | |
| Bulk only, no retry | Single bulk call; no per-symbol retry | |

**User's choice:** Hybrid (bulk + per-symbol retry)
**Notes:** User confirmed the recommendation without modification. CLAUDE.md MultiIndex fix applies after bulk download.

---

## Scan-time Data Freshness

| Option | Description | Selected |
|--------|-------------|----------|
| DB-first, incremental | Read from `price_daily`; fetch only days not yet in DB. 95% check against DB coverage. | ✓ |
| Always re-fetch all 220 days | Fresh fetch from yfinance on every scan; slow but always current | |
| DB-only, no incremental update | Never fetch at scan time; only `init` downloads data | |

**User's choice:** DB-first, incremental
**Notes:** `init` (Phase 6) pre-loads 220 days. Scan adds only missing days (handles multi-day absences naturally).

---

## Constituents Unavailability

| Option | Description | Selected |
|--------|-------------|----------|
| Stale cache + warn | Use cached list; print Warning with staleness age. No hard cutoff. | ✓ |
| Hard fail | Abort scan if constituents can't be refreshed | |
| Stale cache silently | Use cache with no warning | |

**Staleness cutoff sub-question:**

| Option | Description | Selected |
|--------|-------------|----------|
| No limit — always prefer stale | As long as cache exists, use it | ✓ |
| Hard-fail if >30 days old | Past 30 days considered too stale | |
| Hard-fail if >14 days old | More conservative 2-week cutoff | |

**User's choice:** Stale cache + warn, no hard cutoff
**Notes:** Exit triggers for open positions must not be blocked by temporary network issues. User controls freshness via `bensdorp1 refresh`.

---

## SPX Handling

**Delegated to Claude.** User said "I'll let you decide what you think is best."

**Decision made:** `^GSPC` treated as a regular symbol in `price_daily`. Always included in downloads regardless of constituents list. No separate table or download path.

**Rationale:** Simplest consistent approach — one table, one code path. Phase 4 queries `price_daily WHERE symbol = '^GSPC'` like any other symbol.

---

## Claude's Discretion

- **Module structure** — Four-module layout: `constituents.py`, `prices.py`, `calendar.py`, `__init__.py`. Retry logic inlined (no separate `http.py`).
- **SPX handling** — `^GSPC` treated as regular symbol in `price_daily`; always included in downloads.

## Deferred Ideas

None — discussion stayed within phase scope.
