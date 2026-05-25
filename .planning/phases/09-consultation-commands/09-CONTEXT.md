# Phase 9: Consultation Commands - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the 7 read-only (and one state-changing) consultation commands: `last`, `history`, `portfolio`, `detail`, `cash`, `config`, `audit`. Users can inspect every aspect of their portfolio and history without triggering scans.

**Specifically delivers:**
- `src/bensdorp1/commands/last.py` — shows most recent `scans.raw_output` verbatim
- `src/bensdorp1/commands/history.py` — compact scan table with `--limit` / `--since` filters
- `src/bensdorp1/commands/portfolio.py` — open positions table with live computed metrics
- `src/bensdorp1/commands/detail.py` — single-position deep view with per-day stop history
- `src/bensdorp1/commands/cash.py` — show or update available cash
- `src/bensdorp1/commands/config.py` — show current system configuration
- `src/bensdorp1/commands/audit.py` — filtered audit log query
- `tests/test_commands/test_portfolio.py`, `test_last.py`, `test_history.py`, `test_detail.py`, `test_cash.py`, `test_config.py`, `test_audit.py` — CliRunner integration tests

**Does NOT include:** `status`, `refresh`, `restore` (Phase 10); split detection (Phase 11); snapshot tests (Phase 13).

</domain>

<decisions>
## Implementation Decisions

### `detail` — per-day stop history
- **D-01:** Reconstruct per-day highest-close history from `price_daily`. Walk every NYSE trading day from `entry_date + 1` to the most recent price in `price_daily` for the symbol. For each day, compute the running maximum: `highest_close_on_day_D = max(entry_close, closes[entry_date+1..D])`. Show as a table of `(Date, Close, Highest close, Trailing stop, Effective stop)` for every day. No schema changes — `price_daily` has continuous coverage guaranteed by `init` (220-day load) + incremental `scan` updates.
- **D-02:** `detail` splits section — omit entirely in Phase 9. The spec says "any splits applied"; since split detection is Phase 11, there is nothing to show. Phase 11 adds the splits block. No placeholder line.

### `audit --type` flag
- **D-03:** Use `Optional[AuditEventType]` as the Typer type annotation for `--type`. Typer validates automatically, renders valid choices in `--help`, and enables shell autocomplete. No runtime validation code needed.

### `cash` command
- **D-04:** Signature: `amount: Optional[float] = typer.Argument(None)`, `note: Optional[str] = typer.Option(None, "--note")`. `--note` is optional on updates. `amount=0.0` is valid (spec: "non-negative"). When `amount` is provided, show confirmation prompt → update `config` table → log `cash_updated` audit event with old value, new value, and optional note.

### `history` table format
- **D-05:** "Top 3 buy candidates" column shows a comma-separated list: `"AAPL, MSFT, NVDA"`. Fewer than 3 → fewer symbols shown. Bear day (no candidates) → `"—"`. Single column, not three separate columns.

### `portfolio` table
- **D-06:** Use abbreviated column headers to fit a 120-char terminal: `Symbol`, `Entry date`, `Days`, `Entry $`, `Shares`, `Last $`, `High $`, `Stop $`, `Dist %`, `P&L`. Right-align all numeric columns; left-align Symbol.
- **D-07 (Claude discretion):** `Last $` (last close) comes from the most recent `price_daily` row for the symbol where `trade_date <= today`. If no price data exists for a symbol (edge case), show `N/A` for Last $, High $, Stop $, Dist %, and P&L — log a warning. `effective_stop = max(initial_stop, trailing_stop)` computed at read time (not stored), per Phase 7 D-18.
- **D-08 (Claude discretion):** `Distance to stop %` = `(last_close - effective_stop) / last_close * 100`. Positive means stop is below current price (normal). Show with sign always (e.g., `+12.3%`). `Unrealized P&L = (last_close - entry_close) * shares` — use `format_pnl()` from `ui`.

### Code organization
- **D-09 (Claude discretion):** Single file per command — all 7 commands. `last` and `config` are trivial (1 DB query). `portfolio` and `detail` have more logic but are DB reads + computation with no data fetch — single file keeps them consistent with Phase 8's buy/sell/fix pattern (D-25). No engine split.
- **D-10 (Claude discretion):** `detail SYMBOL` validates that an open position exists for SYMBOL; if closed or not found, `print_error("No open position for SYMBOL.", actions=["To see history of a closed position: bensdorp1 audit --symbol SYMBOL"])` and exit code 1.

### Tests
- **D-11 (Claude discretion):** CliRunner integration tests with real SQLite temp DB seeded per-test (established pattern from Phase 8 D-25). `portfolio` and `detail` tests seed `price_daily` rows. `audit` tests seed `audit_log` rows with different event types. Tests confirm empty-state messages, filter behavior, and column presence in output.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary specification (authoritative)
- `.planning/Bensdorp_1.md` §5.2.3 — `last` command: behavior, empty state
- `.planning/Bensdorp_1.md` §5.2.4 — `history` command: flags, table columns, empty state
- `.planning/Bensdorp_1.md` §5.2.8 — `portfolio` command: exact 10 columns, empty state logic
- `.planning/Bensdorp_1.md` §5.2.9 — `detail` command: output fields, validations
- `.planning/Bensdorp_1.md` §5.2.10 — `cash` command: optional AMOUNT, --note flag, confirmation, side effects
- `.planning/Bensdorp_1.md` §5.2.11 — `config` command: fields to show
- `.planning/Bensdorp_1.md` §5.2.12 — `audit` command: all 5 flags (--symbol, --since, --until, --type, --limit), AND-filter logic, most-recent-first ordering
- `.planning/Bensdorp_1.md` §6 — 31 UI/UX style guide rules (all output must comply)
- `.planning/REQUIREMENTS.md` CMD-04, CMD-05, CMD-09, CMD-10, CMD-11, CMD-12, CMD-13

### Existing implementations to read before coding
- `src/bensdorp1/db/schema.py` — `positions`, `scans`, `scan_candidates`, `scan_exit_triggers`, `audit_log`, `config`, `price_daily`, `constituents_cache` table definitions; know exact column names before writing queries
- `src/bensdorp1/db/audit.py` — `AuditEventType` StrEnum (17 event types); use for `--type` annotation and `cash_updated` log call
- `src/bensdorp1/db/backup.py` — `create_backup(engine, backups_dir)` — call after `cash` update (state-changing)
- `src/bensdorp1/db/engine.py` — `get_engine()`, `run_migrations()`
- `src/bensdorp1/data/calendar.py` — NYSE calendar for `days_held` (trading days between entry_date and today) and per-day history walk in `detail`
- `src/bensdorp1/commands/buy.py` — canonical pattern for DB write + confirmation + backup + audit log (reference for `cash` update flow)
- `src/bensdorp1/commands/scan.py` — `last` reads `scans.raw_output` from the same table scan writes to; understand the raw_output storage pattern
- `src/bensdorp1/ui/__init__.py` — `print_error`, `print_info`, `print_success`, `render_kv_block`, `render_table`, `format_price`, `format_pnl`, `confirm_prompt`
- `src/bensdorp1/config.py` — `DATA_DIR`, `USER_TZ`, `MARKET_TZ`

### Prior phase context
- `.planning/phases/08-confirmation-commands/08-CONTEXT.md` — D-25/D-26: single file per command, no engine split; D-09: `create_backup` call pattern; confirm_prompt usage
- `.planning/phases/07-scan-command/07-CONTEXT.md` — D-18: `effective_stop` computed at read time; D-19: `last_close` from `price_daily`; D-01: `last` shows `raw_output` verbatim
- `.planning/phases/06-first-run-init-command/06-CONTEXT.md` — `confirm_prompt` re-raises `KeyboardInterrupt`; `raise typer.Exit()` not `sys.exit()`; CliRunner test pattern

### Technology
- `CLAUDE.md` §Verified Library Versions — typer >=0.21.1, sqlalchemy >=2.0.49
- `CLAUDE.md` §mypy Strict Mode Configuration — all command files must pass mypy strict

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ui.render_table(headers, rows, console)` — use for `portfolio` (10-col), `history` (6-col), `detail` per-day history table, `audit` results
- `ui.render_kv_block(data, console)` — use for `detail` position summary section and `config` output
- `ui.format_price(value)` → `"$X,XXX.XX"` — for all price columns
- `ui.format_pnl(value)` → `"±$X,XXX.XX (±X.X%)"` — for P&L columns in `portfolio` and `detail`
- `ui.print_error(title, actions=[], data={})` — for validation errors (no position, no scans, invalid date range)
- `ui.print_info(title)` — for empty states ("No open positions.", "No scans recorded.", etc.)
- `ui.confirm_prompt(prompt, console)` — for `cash` update confirmation
- `db.log_event(engine, event_type, symbol, payload)` — for `cash_updated` event
- `db.create_backup(engine, backups_dir)` — call after `cash` update
- `data.calendar` — NYSE calendar for days_held + detail's per-day history walk
- `db.schema.positions`, `scans`, `scan_candidates`, `audit_log`, `config`, `price_daily` — SQLAlchemy Table objects

### Established Patterns
- `_app.py`: `app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)`. `-> None` on all command functions. `raise typer.Exit()` early exits, `raise typer.Exit(code=1)` error exits.
- Console ownership: `console = Console()` at command entry; pass to all UI calls. Tests use `Console(record=True)`.
- `Text()` wrapping for all strings passed to `console.print()` — markup safety.
- CliRunner from `typer.testing` for all CLI tests — no subprocess. Real SQLite temp file DB seeded per test.
- SQLAlchemy parameterized queries only — no string interpolation.
- `engine.connect()` context manager for all DB reads; `conn.commit()` after writes.
- Empty states: always `print_info("No open positions.")` — never blank output (UI-08).

### Integration Points
- `commands/last.py` reads `scans` table (most recent row by `scan_date`); prints `raw_output` verbatim
- `commands/history.py` reads `scans` + `scan_candidates` (top-3 by rank); filters by `--since` and `--limit`
- `commands/portfolio.py` reads `positions` (WHERE closed_at IS NULL) + `price_daily` (latest close per symbol)
- `commands/detail.py` reads `positions`, `price_daily` (all closes since entry_date), `scans` (originating scan), `scan_exit_triggers`
- `commands/cash.py` reads + writes `config` table; calls `create_backup` + `log_event`
- `commands/config.py` reads `config` table + `importlib.metadata.version("bensdorp1")`
- `commands/audit.py` reads `audit_log` with AND-filter WHERE clause; `Optional[AuditEventType]` on `--type`

</code_context>

<specifics>
## Specific Ideas

### `portfolio` table column abbreviations (D-06)
```
Symbol   Entry date    Days  Entry $    Shares   Last $   High $    Stop $    Dist %    P&L
------   ----------  ------  --------  -------  -------  -------  --------  --------  --------
AAPL     2026-03-15      48  $182.50       50   $178.20  $185.00   $138.75    +22.2%  -$215.00
```
Use `render_table()`. Right-align all numeric columns. `Dist %` = distance of last close above effective stop, shown with `+` sign always.

### `detail` per-day history table
```
Stop history
------------
Date         Close     Highest close  Trailing stop  Effective stop
----------  --------  -------------  -------------  --------------
2026-03-15  $182.50        $182.50        $136.88          $169.73
2026-03-16  $185.00        $185.00        $138.75          $169.73
2026-03-17  $183.20        $185.00        $138.75          $169.73
```
Reconstruct day-by-day from `price_daily`. Entry day close = `entry_close`; highest_close on day D = `max(entry_close, closes[entry+1..D])`. `trailing_stop = highest_close * 0.75`. `effective_stop = max(initial_stop, trailing_stop)`.

### `history` compact table
```
Date          Regime  Exits  Candidates  Top candidates
----------  --------  -----  ----------  ---------------
2026-05-21      Bull      1          10  NVDA, AAPL, MSFT
2026-05-20      Bull      0           8  NVDA, TSLA, MSFT
2026-05-19      Bear      2           0  —
```

### `audit` output (most-recent-first, AND-filter)
```
Date                    Type               Symbol  Details
--------------------  -----------------  --------  ----------
2026-05-25 14:30 ET   cash_updated              —  $50,000 → $45,000
2026-05-22 09:15 ET   buy_confirmed          NVDA  23 shares @ $432.50
```
Show `occurred_at` in dual timezone (ET + Lisbon). Parse `payload` JSON for the Details column (key fields only, not full JSON dump).

### `cash` show-mode output (no AMOUNT)
```
Available cash:    $45,000.00
Last updated:      2026-05-25 14:30 ET / 19:30 Lisbon
```
Use `render_kv_block`. Last-updated comes from `config.updated_at`.

### `config` output
```
Cash:            $45,000.00
Data directory:  /home/user/bensdorp1
Timezone:        Lisbon (BENSDORP1_USER_TZ)
Version:         0.1.0
```
Use `render_kv_block`. Version from `importlib.metadata.version("bensdorp1")`.

</specifics>

<deferred>
## Deferred Ideas

- Split history in `detail` — Phase 11 (DATA-06: split detection)
- Delisted position handling in `portfolio` — Phase 11 (STATE-07)
- Snapshot tests for all command outputs — Phase 13 (TEST-04)
- Integration tests with mocked yfinance/DB — Phase 13 (TEST-05)
- Closed position detail (full history) — audit --symbol serves this; no dedicated command per requirements

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 9-Consultation Commands*
*Context gathered: 2026-05-25*
