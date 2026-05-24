# Phase 7: Scan Command - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 07-scan-command
**Areas discussed:** Idempotency design, Exit trigger persistence, Catch-up boundary, Data fetch scope, Code organization, Position updates, Buy candidates layout, Test scope

---

## Idempotency Design

| Option | Description | Selected |
|--------|-------------|----------|
| Replay raw_output verbatim | Store rendered console text in scans.raw_output; same-day re-run prints it | ✓ |
| Re-render from scan_candidates + positions | Query structured records and re-render dynamically | |

**User's choice:** Replay raw_output verbatim

| Option | Description | Selected |
|--------|-------------|----------|
| Overwrite in-place | UPDATE existing scans row with same scan_date | ✓ |
| Insert new row | Keep original + add fresh row | |

**User's choice:** Overwrite in-place

| Option | Description | Selected |
|--------|-------------|----------|
| Always re-fetch from yfinance on --force | Re-runs Phase B regardless | ✓ |
| Re-use today's prices if already present | Skip yfinance download for same-day --force | |

**User's choice:** Always re-fetch

| Option | Description | Selected |
|--------|-------------|----------|
| Info message + last scan output | Print note + raw_output from latest scan | ✓ |
| Info message only | Print note and exit; user runs `last` explicitly | |

**User's choice:** Info message + last scan output (non-trading day)

---

## Exit Trigger Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| New scan_exit_triggers table | New table; no ALTER TABLE; create_all handles it | ✓ |
| Add columns to positions | exit_triggered_at + exit_reason via ALTER TABLE | |
| Re-compute every scan, no persistence | Always re-derive, no "triggered on" date | |

**User's choice:** New scan_exit_triggers table

| Option | Description | Selected |
|--------|-------------|----------|
| Only when position confirmed closed by sell | STRAT-10: persists until user acts | ✓ |
| When stop condition no longer met | Dynamic removal if stock recovers | |

**User's choice:** Only when sell command closes the position

| Option | Description | Selected |
|--------|-------------|----------|
| Stop updating stops once exit triggered | Freeze highest_close/trailing_stop | ✓ |
| Keep updating stops until closed | Continue stop math after trigger | |

**User's choice:** Stop updating once triggered

---

## Catch-Up Boundary (Phase 7 vs Phase 11)

| Option | Description | Selected |
|--------|-------------|----------|
| Partial catch-up: update stops for missed days | Walk price_daily per missed day; system note | ✓ |
| Warn and proceed with stale stops | Warning + proceed; stops may be wrong | |
| Block until Phase 11 | Error; unusable without Phase 11 | |

**User's choice:** Partial catch-up (stop math only; split detection and 13 templates deferred to Phase 11)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — check for triggers on each missed day | Accurate "triggered on" date even for absences | ✓ |
| No — only current day matters | Simpler; may miss triggers during absence | |

**User's choice:** Check for triggers on each missed day

---

## Data Fetch Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Narrow range: last 7-10 days only | Incremental; fast (~70s per spec) | ✓ |
| Full default range: 350 calendar days | Always re-download all history; slow | |

**User's choice:** Narrow range (10 calendar days)

| Option | Description | Selected |
|--------|-------------|----------|
| All 503 symbols always | Full progress bar every scan; matches spec §7.2 | ✓ |
| Only symbols with new data | Unpredictable count; contradicts spec | |

**User's choice:** All 503 symbols always in progress bar

| Option | Description | Selected |
|--------|-------------|----------|
| Re-fetch always on --force | update_price_data always called; ON CONFLICT DO NOTHING | ✓ |
| Skip re-fetch on same-day --force | Faster; reuses stored prices | |

**User's choice:** Re-fetch always on --force

---

## Code Organization

| Option | Description | Selected |
|--------|-------------|----------|
| scan.py + _scan_engine.py | Thin Typer entry + private business logic module | ✓ |
| Everything in scan.py | Single flat file like init.py | |
| scan.py + bensdorp1/scan_service.py | Top-level service module (new pattern) | |

**User's choice:** scan.py + _scan_engine.py

---

## Position Updates on Every Scan

| Option | Description | Selected |
|--------|-------------|----------|
| Write back to positions table | UPDATE row per scan with new highest_close/trailing_stop | ✓ |
| Compute dynamically at query time | Never write stops back; always re-derive | |

**User's choice:** Write back to positions table

| Option | Description | Selected |
|--------|-------------|----------|
| No — portfolio reads price_daily directly | No last_close column on positions | ✓ |
| Yes — add last_close column to positions | Avoids price_daily join in Phase 9 | |

**User's choice:** portfolio reads price_daily directly (no last_close on positions)

---

## Buy Candidates Table Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Follow spec: two separate tables | All 10 with ROC/Volume + affordable with Shares | ✓ |
| Merge into one table | Single table with all columns | |

**User's choice:** Two separate tables exactly as spec §7.2

| Option | Description | Selected |
|--------|-------------|----------|
| Show regime + exit triggers only, omit candidates | Bearish = no buy sections | ✓ |
| Show empty buy candidates tables | Keep headers with empty tables | |

**User's choice:** Omit buy candidates entirely when regime is bearish

---

## Test Scope

| Option | Description | Selected |
|--------|-------------|----------|
| CliRunner integration + unit tests for complex logic | 6 CliRunner scenarios + dedicated engine unit tests | ✓ |
| CliRunner integration tests only | Same style as Phase 6 | |
| Minimal — happy path + time-gate only | Deferred to Phase 13 | |

**User's choice:** CliRunner integration tests + unit tests for catch-up loop and exit trigger logic

---

## Claude's Discretion

- Whether `_scan_engine.run_scan` accepts a `Console` parameter — follow Phase 5 D-06 console ownership pattern (optional param, module-level default)
- Exact number of calendar days for narrow date window (10 vs 14) — 10 chosen
- Whether catch-up and main scan share a single DB transaction or separate commits
- Exact wording of system notes beyond fixed templates

## Deferred Ideas

- Full catch-up event templates (13 from spec §8.9) — Phase 11
- Split detection — Phase 11 (DATA-06)
- Delisted position handling — Phase 11 (STATE-07)
- Snapshot tests for scan output — Phase 13 (TEST-04)
- Integration tests with mocked external services — Phase 13 (TEST-05)
