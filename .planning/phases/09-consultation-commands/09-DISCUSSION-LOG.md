# Phase 9: Consultation Commands - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 9-Consultation Commands
**Areas discussed:** detail history source, audit --type strictness, detail splits section, cash --note optional, history table format, portfolio columns

---

## `detail` per-day history source

| Option | Description | Selected |
|--------|-------------|----------|
| Reconstruct from price_daily | Walk NYSE trading days since entry_date, query closes, recompute running-max. No schema changes. | ✓ |
| Add position_stop_history table | New table logging per-position-per-day stop data. Requires migration + retroactive scan engine change. | |

**User's choice:** Reconstruct from price_daily
**Notes:** Avoids touching Phase 7's completed scan engine. price_daily has continuous coverage guaranteed by init (220-day load) + incremental scan updates.

---

## `audit --type` validation

| Option | Description | Selected |
|--------|-------------|----------|
| Typer Enum annotation | `Optional[AuditEventType]` annotation. Auto-validates, --help shows choices, shell autocomplete. | ✓ |
| Freetext + runtime validation | Accept str, validate against AuditEventType at runtime. More flexible but more code. | |

**User's choice:** Typer Enum annotation
**Notes:** Zero extra code, better UX, consistent with Typer idioms in the project.

---

## `detail` splits section

| Option | Description | Selected |
|--------|-------------|----------|
| Omit entirely | No splits section in Phase 9. Phase 11 adds it when split detection is built. | ✓ |
| Placeholder line | Show "Splits applied: None recorded." Phase 11 replaces. | |

**User's choice:** Omit entirely
**Notes:** A placeholder implies the feature works. Since splits aren't tracked yet, nothing to show. Phase 11 adds the section naturally.

---

## `cash --note` flag requirement

| Option | Description | Selected |
|--------|-------------|----------|
| Optional (spec default) | Cash can be updated without a note. [--note REASON] bracket notation = optional. | ✓ |
| Required on updates | Force a note whenever cash changes. Audit discipline but friction. | |

**User's choice:** Optional
**Notes:** Matches spec §5.2.10 notation. User can add notes for their own records.

---

## `history` top-3 candidates display

| Option | Description | Selected |
|--------|-------------|----------|
| Comma-separated single cell | "AAPL, MSFT, NVDA" in one column. "—" on bear days. | ✓ |
| Three separate columns | Candidate 1, Candidate 2, Candidate 3. Sparse on bear days. | |

**User's choice:** Comma-separated single cell
**Notes:** Natural compact format, handles variable candidate count gracefully.

---

## `portfolio` table column headers

| Option | Description | Selected |
|--------|-------------|----------|
| Abbreviated headers | Short labels fit in 120-char terminal without wrapping. | ✓ |
| Full spec labels | "Entry date", "Days held", "Entry price" etc. May wrap. | |

**User's choice:** Abbreviated headers
**Notes:** Abbreviated: Symbol, Entry date, Days, Entry $, Shares, Last $, High $, Stop $, Dist %, P&L.

---

## Claude's Discretion

- `portfolio` last_close: query most recent `price_daily` row per symbol (≤ today); show "N/A" if no data
- `portfolio` effective_stop: `max(initial_stop, trailing_stop)` computed at read time, not stored
- `portfolio` distance_to_stop: `(last_close - effective_stop) / last_close * 100`, sign always shown
- Code organization: single file per command for all 7 commands (no engine split)
- `detail` closed position: `print_error` + suggest `audit --symbol SYMBOL`
- `config` fields: cash, DATA_DIR, USER_TZ, version from `importlib.metadata`
- Test approach: CliRunner with real SQLite temp DB seeded per test (established Phase 8 pattern)
- `audit` payload display: parse JSON payload, show key fields in Details column (not raw JSON)

## Deferred Ideas

- Split history in `detail` → Phase 11
- Delisted position handling in `portfolio` → Phase 11
- Snapshot tests for consultation command outputs → Phase 13
- Full integration tests with mocked external services → Phase 13
