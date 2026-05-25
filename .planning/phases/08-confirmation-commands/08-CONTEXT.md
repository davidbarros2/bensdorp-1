# Phase 8: Confirmation Commands - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `buy`, `sell`, and `fix` commands — the three state-changing confirmation commands that record trades and correct transactions.

**Specifically delivers:**
- `src/bensdorp1/commands/buy.py` — full `buy SYMBOL PRICE SHARES [--date DATE]` implementation
- `src/bensdorp1/commands/sell.py` — full `sell SYMBOL PRICE [--date DATE] [--manual REASON]` implementation
- `src/bensdorp1/commands/fix.py` — full interactive `fix SYMBOL [--date DATE]` implementation
- `src/bensdorp1/db/schema.py` — `closed_reason` and `closed_manual_reason` columns added to `positions` via `run_migrations`
- `tests/test_commands/test_buy.py`, `tests/test_commands/test_sell.py`, `tests/test_commands/test_fix.py` — CliRunner integration tests

**Does NOT include:** `portfolio`, `detail`, `cash`, `config` (Phase 9); `status`, `refresh`, `restore` (Phase 10); split detection (Phase 11).

</domain>

<decisions>
## Implementation Decisions

### Schema additions
- **D-01:** Add `closed_reason TEXT` (nullable) and `closed_manual_reason TEXT` (nullable) to the `positions` table via explicit `ALTER TABLE` statements in `run_migrations`. Wrap each in a try/except `OperationalError` for idempotency — SQLite raises `OperationalError: duplicate column name` if the column already exists. Place these after the existing `metadata.create_all(bind=engine)` call.
- **D-02:** The existing `positions.scan_id` column (FK to `scans.id`, nullable) already serves as `confirmed_signal_scan_id` — no new column needed. A NULL `scan_id` means off-signal.
- **D-03:** No `confirmed_at` column needed — `positions.entry_date` records when the buy was made.

### Buy command
- **D-04:** Validation order: (1) check symbol is a valid constituent (query `constituents_cache`); (2) check no open position exists for symbol (query `positions WHERE closed_at IS NULL AND symbol = ?`); (3) validate price > 0 and shares > 0.
- **D-05:** Off-signal check: find the most recent scan with `scans.scan_date <= DATE` (or today if no `--date`). If SYMBOL appears in `scan_candidates` for that scan with `rank <= 10`, it is on-signal; link `positions.scan_id` to that scan's id. If not found, show the off-signal warning and continue prompt before the main confirmation.
- **D-06:** Off-signal warning shown before the main `[y/n]` confirmation (per spec §7.3 Step 2):
  ```
  Warning: SYMBOL was not in the top 10 buy candidates of the latest scan.

  This buy will be recorded as off-signal in the audit log.

  Continue? [y/n]: _
  ```
  If user answers `n`, abort. If `y`, proceed to main confirmation.
- **D-07:** If no scan has ever been run (`scans` table empty), treat as off-signal. Show warning; allow buy to proceed.
- **D-08:** Main confirmation header (spec §7.3 Step 3):
  ```
  ================================================================
  Confirm buy
  ================================================================

  Symbol:        NVDA
  Buy price:     $432.50
  Shares:        23
  Buy value:     $9,947.50
  Date:          2026-05-22
  Signal scan:   2026-05-21 (NVDA was rank 1)

  Confirm buy? [y/n]: _
  ```
  `Signal scan` line shows only when on-signal; omit when off-signal.
- **D-09:** On confirmation (`y`): insert into `positions` with `closed_at = NULL` (open position), compute `initial_stop = price * 0.93`, set `highest_close = price`, `trailing_stop = price * 0.75` as initial values. Call `create_backup(engine, DATA_DIR / "backups")`. Log `AuditEventType.BUY_CONFIRMED` with payload `{symbol, price, shares, date, scan_id, on_signal: bool}`.
- **D-10:** `--date DATE` accepts ISO format `YYYY-MM-DD`. If not provided, defaults to today (ET date). DATE is stored as `entry_date` on the position.
- **D-11:** `buy_value = price * shares`; shown as `format_price(buy_value)` in the confirmation preview.

### Sell command
- **D-12:** When `sell SYMBOL PRICE` is called (no `--manual`): look up the most recent `scan_exit_triggers` row for this position (join `positions` on `position_id`). If found, infer `closed_reason` from `scan_exit_triggers.reason` (`"Trailing stop"` → `"stop_trailing"`, `"Initial stop"` → `"stop_initial"`). Use the **earliest** trigger row to get the original trigger reason.
- **D-13:** If `sell SYMBOL PRICE` is called but **no `scan_exit_triggers` row exists** for this position, print error:
  ```
  Error: No exit trigger on record for SYMBOL.

  To record a manual sell, use: bensdorp1 sell SYMBOL PRICE --manual REASON
  ```
  Exit with code 1. Do not proceed.
- **D-14:** `sell SYMBOL PRICE --manual REASON` → `closed_reason = "manual"`, `closed_manual_reason = REASON`, audit event `AuditEventType.SELL_MANUAL`.
- **D-15:** Normal sell (exit trigger found) → `closed_reason = "stop_initial"` or `"stop_trailing"`, `closed_manual_reason = NULL`, audit event `AuditEventType.SELL_CONFIRMED`.
- **D-16:** Confirmation preview (spec §7.4):
  - `sell_value = sell_price * shares`
  - `entry_value = entry_close * shares`
  - `days_held = NYSE trading days between entry_date and sell date` (use NYSE calendar)
  - `realized_pnl = (sell_price - entry_close) * shares`
  - `realized_pnl_pct = (sell_price / entry_close - 1) * 100`
  - Format: `±$X,XXX.XX (±X.X%)` — sign always shown
- **D-17:** On confirmation: UPDATE `positions` SET `closed_at`, `exit_price`, `realized_pnl`, `closed_reason`, `closed_manual_reason` WHERE id = position_id. Call `create_backup`. Log audit event with payload `{symbol, sell_price, shares, entry_price, realized_pnl, realized_pnl_pct, closed_reason, closed_manual_reason}`.
- **D-18:** Validation before showing preview: (1) open position for SYMBOL must exist; (2) sell price > 0; (3) `--date DATE` if provided must be >= `entry_date`.

### Fix command
- **D-19:** Fix targets: if an open position exists for SYMBOL, fix targets its buy (`entry_close`, `shares`, `entry_date`). If no open position, fix targets the most recent closed sell (`exit_price`, `closed_at`, `closed_manual_reason` if manual). If neither exists, print `Error: No transaction found for SYMBOL.` and exit code 1.
- **D-20:** Editable fields per transaction type:
  - **Buy**: `date` (entry_date), `price` (entry_close), `shares`
  - **Sell**: `date` (closed_at), `price` (exit_price), `manual_reason` (closed_manual_reason, only if it was a manual sell)
  - Field-by-field input with current value shown as default (press Enter to keep, per spec §7.5 Step 2).
- **D-21:** Recalculation when buy fields change:
  - `price` changes → recalculate `initial_stop = new_price * 0.93` (spec §7.5 confirmation diff shows this)
  - `shares` changes → no stop recalculation (stops don't depend on shares); update `initial_stop` only if `price` also changed
  - `date` changes → update `entry_date` only; no stop recalculation
  - `price` or `shares` change on a **closed** position → recalculate `realized_pnl = (exit_price - new_price) * new_shares`
- **D-22:** `trailing_stop` and `highest_close` are NOT changed by fix — they track market history, independent of entry price.
- **D-23:** Confirmation preview shows before/after diff for changed fields only, plus "Impact on this position" block with derived values that changed (spec §7.5 Step 3). If user makes no changes (all fields kept), print `Info: No changes detected. Nothing to update.` and exit without writing.
- **D-24:** Preservation: the original values are saved in the `transaction_corrected` audit event payload as `{"before": {...}, "after": {...}}`. The DB row is updated in-place. Log `AuditEventType.TRANSACTION_CORRECTED` with full before/after payload. Call `create_backup` after the UPDATE.

### Code organization
- **D-25 (Claude discretion):** Each command is a **single file** (no engine split). Unlike `scan`, these commands do no data fetching — they are thin DB read + confirmation + DB write flows. Single file per command keeps complexity low without sacrificing testability (all business logic is testable via CliRunner with a real SQLite test DB).
- **D-26 (Claude discretion):** All three commands follow the same structure: validate → preview → `confirm_prompt` → write → `create_backup` → `log_event` → success message. No shared helper needed — duplication is acceptable for three simple flows.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary specification (authoritative)
- `.planning/Bensdorp_1.md` §7.3 — Complete buy confirmation flow (off-signal warning, confirmation prompt format, result message). Read in full.
- `.planning/Bensdorp_1.md` §7.4 — Complete sell confirmation flow (normal and manual). P&L display format. Read in full.
- `.planning/Bensdorp_1.md` §7.5 — Complete fix transaction flow (identification, field-by-field input, before/after diff, impact block). Read in full.
- `.planning/Bensdorp_1.md` §6 — 31 UI/UX style guide rules (all output must comply)
- `.planning/REQUIREMENTS.md` CMD-06, CMD-07, CMD-08 — one-line spec for each command
- `.planning/REQUIREMENTS.md` UI-07 — confirmation prompts for all destructive/state-changing actions

### Existing implementations to read before coding
- `src/bensdorp1/db/schema.py` — `positions`, `scans`, `scan_candidates`, `scan_exit_triggers` table definitions; know the exact column names before writing queries
- `src/bensdorp1/db/engine.py` — `get_engine()`, `run_migrations()` — add ALTER TABLE statements here
- `src/bensdorp1/db/audit.py` — `AuditEventType` enum (BUY_CONFIRMED, SELL_CONFIRMED, SELL_MANUAL, TRANSACTION_CORRECTED) + `log_event()`
- `src/bensdorp1/db/backup.py` — `create_backup(engine, backups_dir)` — call after every state-changing operation
- `src/bensdorp1/commands/init.py` — canonical pattern for: `confirm_prompt` usage, `KeyboardInterrupt` handling, `raise typer.Exit()`, `Text()` wrapping, `render_kv_block`, `format_price`
- `src/bensdorp1/commands/scan.py` — canonical pattern for validation, exit code 1 on error
- `src/bensdorp1/ui/__init__.py` — public UI surface: `confirm_prompt`, `print_error`, `print_info`, `print_success`, `render_kv_block`, `format_price`, `format_pnl`, `render_table`
- `src/bensdorp1/config.py` — `DATA_DIR`, `MARKET_TZ`
- `src/bensdorp1/data/calendar.py` — NYSE calendar for `days_held` calculation (trading days between two dates)

### Prior phase context
- `.planning/phases/07-scan-command/07-CONTEXT.md` — D-06: triggers persist until sell confirmed; D-07: once triggered, stop is frozen; D-15: thin Typer + engine split pattern (not used here, but explains why)
- `.planning/phases/06-first-run-init-command/06-CONTEXT.md` — `confirm_prompt` re-raises `KeyboardInterrupt` (must wrap in try/except); `raise typer.Exit()` not `sys.exit()`; CliRunner test pattern

### Technology
- `CLAUDE.md` §Verified Library Versions — typer >=0.21.1, sqlalchemy >=2.0.49
- `CLAUDE.md` §mypy Strict Mode Configuration — all command files must pass mypy strict

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ui.confirm_prompt(prompt, console)` — `[y/n]` prompt; re-raises `KeyboardInterrupt`; returns `bool`. Used in init.py for buy/sell confirmations.
- `ui.render_kv_block(data, console)` — key-value block renderer (aligned). Used for buy/sell confirmation preview and fix before/after display.
- `ui.format_price(value)` → `"$X,XXX.XX"` — use for all prices in confirmations
- `ui.print_error(title, actions=[], data={})` — for validation errors (no position found, no exit trigger, etc.)
- `ui.print_success(title)` — for success messages after confirmed operations
- `ui.print_info(title)` — for "No changes detected" in fix
- `db.create_backup(engine, backups_dir)` — call after every state-changing DB write
- `db.log_event(engine, event_type, symbol, payload)` — audit log writer
- `data.calendar` — NYSE calendar for trading day arithmetic (days_held)
- `db.schema.positions`, `db.schema.scans`, `db.schema.scan_candidates`, `db.schema.scan_exit_triggers` — SQLAlchemy Table objects for queries

### Established Patterns
- `_app.py`: `app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)`. `-> None` on all command functions. `raise typer.Exit()` for early exits, `raise typer.Exit(code=1)` for error exits.
- Console ownership: `console = Console()` at command entry; pass to all UI calls.
- `Text()` wrapping for all strings passed to `console.print()` — markup safety.
- CliRunner from `typer.testing` for all CLI tests — no subprocess. Tests use real SQLite in-memory or temp file DB.
- `try/except KeyboardInterrupt` wrapping all interactive sections; on interrupt: print "Operation aborted. No changes were made." and `raise typer.Exit()`.
- SQLAlchemy parameterized queries only — no string interpolation. `select(table).where(col == bindparam)` pattern.
- `engine.connect()` context manager for all DB operations; explicit `conn.commit()` after writes.

### Integration Points
- `commands/buy.py` imports: `bensdorp1._app` (app), `bensdorp1.config` (DATA_DIR), `bensdorp1.db` (get_engine, run_migrations, log_event, create_backup, AuditEventType), `bensdorp1.db.schema` (positions, scans, scan_candidates), `bensdorp1.ui` (confirm_prompt, render_kv_block, print_error, print_success, format_price)
- `commands/sell.py` additionally imports: `bensdorp1.db.schema` (scan_exit_triggers), `bensdorp1.data.calendar` (for days_held)
- `commands/fix.py` additionally imports: `bensdorp1.ui` (print_info for no-changes case)
- All three commands call `run_migrations(engine)` at entry — picks up the new ALTER TABLE additions automatically on first run after upgrade

</code_context>

<specifics>
## Specific Ideas

### Buy confirmation exact format (spec §7.3)
```
================================================================
Confirm buy
================================================================

Symbol:        NVDA
Buy price:     $432.50
Shares:        23
Buy value:     $9,947.50
Date:          2026-05-22
Signal scan:   2026-05-21 (NVDA was rank 1)

Confirm buy? [y/n]: _
```
`Signal scan` line is omitted when off-signal. Use `render_kv_block` for the data block.

### Off-signal warning exact format (spec §7.3 Step 2)
```
Warning: NVDA was not in the top 10 buy candidates of the latest scan.

This buy will be recorded as off-signal in the audit log.

Continue? [y/n]: _
```
Use `print_warning` (or print with warning prefix per style guide) + separate `confirm_prompt("Continue?")`.

### Sell confirmation exact format (spec §7.4)
```
================================================================
Confirm sell
================================================================

Symbol:           AAPL
Sell price:       $178.20
Sell value:       $8,910.00
Shares sold:      50
Entry price:      $182.50
Entry value:      $9,125.00
Days held:        47 days
Realized P&L:     -$215.00 (-2.4%)
Closing reason:   Trailing stop

Confirm sell? [y/n]: _
```
For manual sell, header is "Confirm sell (manual)" and adds "Manual reason: [REASON]" line.

### Fix before/after diff exact format (spec §7.5 Step 3)
```
================================================================
Confirm correction
================================================================

Transaction:   Buy NVDA on 2026-05-20

Field    Before     After
-----    -------    -------
Price    $432.50    $432.75

Impact on this position
-----------------------
Initial stop:      $402.23 → $402.46

This correction will be recorded in the audit log.
The original entry will be preserved as a historical record.

Confirm correction? [y/n]: _
```
Only show "Impact" block if derived values changed. Use `render_table` for the diff table.

### P&L formatting
Realized P&L: `±$X,XXX.XX (±X.X%)` — sign always shown. Use `format_pnl(value)` if it exists in `ui`, otherwise format inline: `f"{'+' if pnl >= 0 else ''}{format_price(pnl)} ({pnl_pct:+.1f}%)"`.

### `run_migrations` ALTER TABLE pattern
```python
# In db/engine.py run_migrations():
with engine.connect() as conn:
    for stmt in [
        "ALTER TABLE positions ADD COLUMN closed_reason TEXT",
        "ALTER TABLE positions ADD COLUMN closed_manual_reason TEXT",
    ]:
        try:
            conn.execute(text(stmt))
            conn.commit()
        except OperationalError:
            pass  # column already exists — idempotent
```

</specifics>

<deferred>
## Deferred Ideas

- `portfolio` command — Phase 9 (depends on Phase 8 positions data being populated)
- `detail SYMBOL` command — Phase 9
- Split detection on buy confirmation — Phase 11 (DATA-06)
- Delisted stock handling on sell — Phase 11 (STATE-07)
- Snapshot tests for buy/sell/fix output — Phase 13 (TEST-04)
- Integration tests with mocked DB — Phase 13 (TEST-05)

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 8-Confirmation Commands*
*Context gathered: 2026-05-25*
