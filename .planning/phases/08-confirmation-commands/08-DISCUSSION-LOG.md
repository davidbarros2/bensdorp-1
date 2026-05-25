# Phase 8: Confirmation Commands - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 8-confirmation-commands
**Areas discussed:** Schema additions, Sell closing reason, Fix recalculation scope, Buy signal check

---

## Schema Additions

| Option | Description | Selected |
|--------|-------------|----------|
| ALTER TABLE in run_migrations | Add explicit ALTER TABLE statements, wrapped in try/except for idempotency. | ✓ |
| Store reason in audit_log payload only | Skip columns; infer from audit events at query time. | |
| Separate migration file | New module for migration logic. | |

**User's choice:** ALTER TABLE in run_migrations (recommended option)
**Notes:** Existing `scan_id` on positions already serves as `confirmed_signal_scan_id`. `confirmed_at` not needed — `entry_date` covers it.

---

## Sell Closing Reason

| Option | Description | Selected |
|--------|-------------|----------|
| Require --manual REASON | Error if no exit trigger found; user must use --manual. | ✓ |
| Default to manual, allow sell | If no trigger, infer manual and allow sell without error. | |
| Show warning, ask to continue | Warn about missing trigger, ask [y/n] to proceed. | |

**User's choice:** Require --manual REASON (recommended option)
**Notes:** Keeps strategy-driven exits and manual exits cleanly separated in the audit log.

---

## Fix Recalculation Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Buy: price+shares+date \| Sell: price+date+manual_reason | Full field edit per type; price change recalculates initial_stop. | ✓ |
| Buy: price+date only | Exclude shares editing. | |
| Only works on open positions | Restrict to open positions only. | |

**User's choice:** Full field edit per transaction type (recommended option)

| Fix target | Description | Selected |
|------------|-------------|----------|
| Open position buy, or last closed sell if no open | Most flexible — covers typo corrections on sells. | ✓ |
| Open position only | Simpler, avoids editing closed positions. | |
| Last transaction regardless of type | Same as option 1 but more explicit framing. | |

**User's choice:** Open position buy, or last closed sell if no open (recommended option)

---

## Buy Signal Check

| Option | Description | Selected |
|--------|-------------|----------|
| Most recent scan with scan_date <= DATE | Handles --date and no-date uniformly; tolerates weekends/holidays. | ✓ |
| Exact scan date match only | Only link if scan_date == DATE; breaks for weekends and holidays. | |

**User's choice:** Most recent scan before or on DATE (recommended option)

---

## Claude's Discretion

- **Code organization**: Single file per command (no engine split). These commands do no data fetching — thin DB read + confirmation + DB write. Single file keeps complexity low without sacrificing testability.
- **No shared helper for confirm/preview pattern**: Three similar flows but not abstracted — three specific, readable files.
- **fix trailing_stop/highest_close**: These are market-history fields; never changed by fix regardless of what field was edited.

## Deferred Ideas

- `portfolio` and `detail` commands — Phase 9
- Split detection on buy confirmation — Phase 11 (DATA-06)
- Snapshot tests for command output — Phase 13 (TEST-04)
