# Phase 7: Scan Command - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `bensdorp1 scan [--force]` (`commands/scan.py` + `commands/_scan_engine.py`) — the daily end-of-day screening pipeline. On each run it:

1. Pre-flight checks (time gate, trading day, constituents freshness, catch-up detection)
2. Fetches latest market data for all 503 symbols + ^GSPC (incremental update to price_daily)
3. Updates stop levels for all open non-triggered positions (and missed days if catch-up applies)
4. Runs strategy filters (regime, liquidity, momentum, ranking) from strategy/screening.py
5. Detects new exit triggers; persists them in scan_exit_triggers table
6. Renders full output: regime, exit triggers (today + pending), buy candidates, system notes
7. Stores scan record (scans + scan_candidates tables; raw_output for idempotent replay)
8. Writes scan_performed audit event

**Specifically delivers:**
- `src/bensdorp1/commands/scan.py` — Typer entry point, time-gate, idempotency check, delegates to engine
- `src/bensdorp1/commands/_scan_engine.py` — all business logic: data assembly, catch-up loop, stop updates, exit trigger detection, output rendering, DB writes
- `src/bensdorp1/db/schema.py` — new `scan_exit_triggers` table added
- `tests/test_commands/test_scan.py` — CliRunner integration tests + unit tests for complex logic

**Does NOT include:** split detection (Phase 11), full catch-up event templates (Phase 11), delisted stock handling (Phase 11), `last`/`history` commands (Phase 9), `buy`/`sell` commands (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Idempotency
- **D-01:** Same-day replay: when scan already ran today (scans row with today's scan_date exists) and `--force` is not set, print the stored `scans.raw_output` verbatim and exit. No re-fetch, no re-compute, no duplicate audit event.
- **D-02:** `--force` behavior: overwrite the existing scans row in-place (same scan_date, UPDATE not INSERT) + always run Phase B data fetch from yfinance. One scan record per trading day.
- **D-03:** Non-trading day: print `Info: Today is not a trading day. Showing last scan from [date].` then print the most recent `raw_output`. If no prior scan exists, print `Info: No scans recorded yet. Run \`bensdorp1 scan\` on a trading day after 16:30 ET.`
- **D-04:** `--force` on same-day calls `update_price_data` (Phase B runs with progress bar); `ON CONFLICT DO NOTHING` on `price_daily` means existing today's prices are not overwritten — this is safe because market is closed (required before any scan can run).

### Exit Trigger Persistence
- **D-05:** Add a new `scan_exit_triggers` table to `schema.py`: `(id, scan_id FK scans, position_id FK positions, reason TEXT, effective_stop FLOAT)`. First-trigger date = earliest scan's `scan_date` for that position. New table means `create_all` handles it automatically — no ALTER TABLE, existing DBs remain compatible after re-running `run_migrations`.
- **D-06:** Triggers persist until the position is confirmed closed by Phase 8's `sell` command (STRAT-10: "exit triggers persist across daily scans until confirmed closed by user"). A trigger is NOT removed if the stock recovers above the stop on a subsequent scan.
- **D-07:** Once a position has a row in `scan_exit_triggers`, freeze its `highest_close` and `trailing_stop` — no further updates on subsequent scans. The exit price is effectively fixed.

### Partial Catch-Up (Phase 7 scope)
- **D-08:** When the user has been absent ≥ 2 trading days, Phase 7 runs a partial catch-up for non-triggered open positions: walk through each missed trading day in chronological order, update `highest_close` and `trailing_stop` per day using `price_daily` data already downloaded in Phase B.
- **D-09:** On each missed day, also run `is_exit_triggered(close, effective_stop)`. If triggered, insert into `scan_exit_triggers` with that missed day's date as the trigger date. This gives accurate "Triggered on [date]" display even if the user was away.
- **D-10:** System notes section includes: `Catch-up: updated stop levels for N missed trading days. Split detection deferred to Phase 11.` Full catch-up event templates (§8.9) and split detection are Phase 11 territory — Phase 7 only handles stop math.
- **D-11:** Missed trading days are computed via the NYSE calendar (same calendar module from Phase 3): trading days between last scan date and today (exclusive of today).

### Data Fetch Scope
- **D-12:** Daily scan calls `update_price_data(engine, symbols, start=today - 10 calendar days, end=today)`. Narrow window adds only new rows efficiently. Strategy filters read full 220-day history from `price_daily` (stored by init). `ON CONFLICT DO NOTHING` makes this idempotent.
- **D-13:** Phase B progress bar always shows all symbols (503 + ^GSPC total). Use `feedback.track()` iterating over all symbols regardless of how many had new data — matches spec §7.2 layout exactly.
- **D-14:** Constituents freshness (DATA-05): if `constituents_cache.fetched_at` is > 7 days old, call `get_constituents(engine)` inline before Phase B. Show as a pre-flight note; no separate progress step needed (spinner from Phase 5 suffices).

### Code Organization
- **D-15:** Split into two files: `commands/scan.py` (Typer entry: argument parsing, time gate, trading-day check, idempotency check) and `commands/_scan_engine.py` (all business logic). The engine module exposes `run_scan(engine, force=False) -> str` which returns the rendered output. `scan.py` calls `run_scan` and prints to console. This keeps the Typer layer thin and the engine fully unit-testable without CliRunner.
- **D-16:** `_scan_engine.py` internal structure: separate functions for `_run_preflight`, `_fetch_data`, `_update_position_stops`, `_detect_exit_triggers`, `_run_screening`, `_render_output`, `_persist_scan`. The render step captures output to a string (stored in `raw_output`); the same string is printed.

### Position State Updates (Every Scan)
- **D-17:** Each scan UPDATEs the `positions` row for open non-triggered positions with new `highest_close` and `trailing_stop`. This keeps positions always reflecting current stop state. Phase 9's `portfolio` command reads these values directly.
- **D-18:** `effective_stop` is NOT stored in positions — always computed at read time as `max(initial_stop, trailing_stop)`. It is a pure function (no state), so no column needed.
- **D-19:** Phase 9's `portfolio` command reads the latest close price from `price_daily` (not positions). No `last_close` column is added to positions.

### Buy Candidates Output Layout
- **D-20:** Two separate buy-candidates tables exactly as spec §7.2:
  1. `Buy candidates (top 10)` — Rank, Symbol, Close, ROC 200d, Volume (avg 20d); always top 10 from `rank_candidates`
  2. `Buy candidates affordable (cash: $X)` — Rank, Symbol, Close, ROC 200d, Shares to buy; only candidates where `position_size > 0`
- **D-21:** Bearish regime (SPX below SMA 200): show regime section + exit triggers only. Omit both buy-candidates tables entirely. System notes: `Regime: Bear market. No buy candidates generated.`
- **D-22:** If all 10 candidates have position_size = 0 (cash too low to buy any), show the affordable table with a note: `No affordable candidates at current cash level ($X).`

### Test Scope
- **D-23:** CliRunner integration tests (in `tests/test_commands/test_scan.py`) covering:
  1. Time gate — before 16:30 ET: assert error exit + message
  2. Happy path — regime on, ≥1 open position with exit trigger, ≥1 buy candidate: assert full output sections present
  3. Bearish regime — no buy candidates tables in output
  4. Idempotent same-day — second call returns same output, no re-fetch, single scans row
  5. `--force` — overwrites in-place, re-fetches (update_price_data called again)
  6. Non-trading day — Info message + last scan output
- **D-24:** Dedicated unit tests for `_scan_engine.py` complex logic (not via CliRunner):
  - Catch-up day iteration: given price_daily rows for 3 missed days, assert correct highest_close/trailing_stop updates per day
  - Exit trigger detection on missed days: assert scan_exit_triggers row inserted with correct scan_date
  - Stop freeze: once in scan_exit_triggers, assert no further updates to highest_close/trailing_stop

### Claude's Discretion
- Whether `_run_scan` accepts a `Console` parameter for testability or captures output internally via Rich's `Console(record=True)` — follow the console ownership pattern from Phase 5 (D-06: optional `console` param)
- Exact module-level constant for the narrow date window (10 vs 14 calendar days) — 10 is sufficient (covers 2 weeks including holidays)
- Whether catch-up runs inside the same transaction as the main scan or in a separate commit — single transaction preferred for atomicity
- Exact wording of system notes (beyond the fixed templates) — sentence case, plain text, Info prefix as established

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary specification (authoritative)
- `.planning/Bensdorp_1.md` §7.2 — Complete daily scan flow: exact output layout for all sections (Phase A pre-flight, Phase B data fetch, Phase C output). Canonical source. Read in full.
- `.planning/Bensdorp_1.md` §8.1 — Idempotency behavior spec
- `.planning/Bensdorp_1.md` §8.2 — Constituents discrepancy handling (warning format, abort buy candidates, continue exit monitoring)
- `.planning/Bensdorp_1.md` §8.5 — Holidays and weekends behavior
- `.planning/Bensdorp_1.md` §8.6 — Persistent exit triggers (once triggered, persists until sell confirmed)
- `.planning/Bensdorp_1.md` §6 — 31 UI/UX style guide rules (all output must comply)
- `.planning/REQUIREMENTS.md` CMD-03 — scan command requirement (one-line spec: scan, time gate, idempotent, --force)
- `.planning/REQUIREMENTS.md` STRAT-01 through STRAT-10 — all strategy requirements implemented by scan

### Existing implementations to read before coding
- `src/bensdorp1/commands/scan.py` — current stub (one-liner; replace entirely)
- `src/bensdorp1/db/schema.py` — scans, positions, scan_candidates, price_daily tables; add scan_exit_triggers here
- `src/bensdorp1/strategy/screening.py` — `regime_filter`, `liquidity_filter`, `momentum_filter`, `rank_candidates` — these are the exact functions scan calls
- `src/bensdorp1/strategy/positions.py` — `update_highest_close`, `compute_trailing_stop`, `compute_effective_stop`, `is_exit_triggered` — used in stop updates + catch-up + exit detection
- `src/bensdorp1/data/prices.py` — `update_price_data(engine, symbols, start, end)` — call with narrow 10-day window; understand `ON CONFLICT DO NOTHING` behavior
- `src/bensdorp1/data/__init__.py` — `get_constituents(engine)`, `check_price_coverage(engine)`, `update_price_data` public API
- `src/bensdorp1/db/engine.py` — `get_engine()`, `run_migrations()` — run_migrations picks up new scan_exit_triggers table automatically
- `src/bensdorp1/db/audit.py` — `log_event(engine, AuditEventType.scan_performed, ...)` — audit event at end of scan
- `src/bensdorp1/config.py` — `DATA_DIR`, `MARKET_TZ`, `USER_TZ` constants
- `src/bensdorp1/ui/progress.py` — `feedback.multi_step(2)` for Phase B (2 steps: fetch + compute); `feedback.track()` for 503-symbol progress
- `src/bensdorp1/ui/messages.py` — `print_error()`, `print_info()` — time gate error, non-trading-day info, discrepancy warning
- `src/bensdorp1/ui/tables.py` — `render_table()` — buy candidates tables (two separate tables)

### Prior phase context
- `.planning/phases/06-first-run-init-command/06-CONTEXT.md` — CliRunner test pattern, mocked data layer approach, `raise typer.Exit()` for early exits, console ownership
- `.planning/phases/05-ui-components/05-CONTEXT.md` — D-03 feedback API, D-06 console ownership, D-07 severity prefix API

### Technology
- `CLAUDE.md` §Verified Library Versions — typer >=0.21.1, rich >=14.0
- `CLAUDE.md` §mypy Strict Mode Configuration — scan.py and _scan_engine.py must pass mypy strict
- `CLAUDE.md` §Ruff Configuration — formatter and linter apply

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `strategy/screening.py`: `regime_filter(spx_closes)` → bool; `liquidity_filter(price_dfs)` → list[str]; `momentum_filter(price_dfs)` → list[str]; `rank_candidates(price_dfs, available_cash)` → list[Candidate]. All take pre-fetched DataFrames; scan assembles them from price_daily.
- `strategy/positions.py`: `update_highest_close(current, new_close)` → float; `compute_trailing_stop(highest_close)` → float; `compute_effective_stop(initial, trailing)` → float; `is_exit_triggered(close, effective_stop)` → bool. Pure functions — call for each position per scan day.
- `data/prices.py`: `update_price_data(engine, symbols, start, end)` — call with `start=date.today()-timedelta(10)`. Upserts price_daily; ^GSPC always included. Returns None; progress must be driven by scan.
- `db/schema.py`: `scans` table has `raw_output TEXT nullable` — this is where idempotent replay text is stored. `scan_candidates` table stores buy candidates per scan. New `scan_exit_triggers` table to be added.
- `ui/progress.py`: `feedback.multi_step(2)` for [1/2] Fetching + [2/2] Computing. Step [1/2] drives `feedback.track(total=len(symbols))` per-symbol.
- `data/calendar.py`: NYSE calendar for trading day checks and missed-day enumeration.

### Established Patterns
- `_app.py`: `app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)`. `-> None` on all command functions. `raise typer.Exit()` for early exits.
- Console ownership: all UI functions accept `console: Console | None = None`; tests pass `Console(record=True)`.
- CliRunner from `typer.testing` for all CLI tests — no subprocess.
- Mocked data layer in tests: patch `bensdorp1.data.update_price_data`, `bensdorp1.data.get_constituents`, `bensdorp1.strategy.screening.*` to control test inputs.
- Test directory: `tests/test_commands/` (created in Phase 6); follow same `__init__.py` + conftest pattern.

### Integration Points
- `commands/scan.py` imports: `bensdorp1._app` (app), `bensdorp1.config` (DATA_DIR, MARKET_TZ), `bensdorp1.commands._scan_engine` (run_scan)
- `commands/_scan_engine.py` imports: `bensdorp1.db` (get_engine, run_migrations, log_event, AuditEventType), `bensdorp1.data` (get_constituents, update_price_data, check_price_coverage), `bensdorp1.strategy` (all screening + position functions), `bensdorp1.ui` (feedback, render_table, print_error, print_info, print_success)
- Scan creates a scans row with `scan_date = today's trading date` (not datetime.now — the trading date is a date, not a timestamp; store as date-at-midnight UTC for consistency)
- Scan links `scan_candidates` rows to the scan via `scan_id FK`

### Data Assembly for Strategy Functions
The scan assembles `price_dfs: dict[str, pd.DataFrame]` from `price_daily` before calling filter functions. Each DataFrame has columns `[close, volume]` indexed chronologically. Query needs at least 221 rows per symbol (201 for momentum/ranking + 20 for liquidity). SPX DataFrame (^GSPC, close only) passed separately to `regime_filter`.

</code_context>

<specifics>
## Specific Ideas

### Scan output header format (from spec §7.2)
```
================================================================
Scan for 2026-05-21
================================================================
```
Use the `=` × 64 pattern from Phase 6 (same as init welcome screen). Date in ISO format (YYYY-MM-DD), Eastern Time date.

### Exit triggers table format (from spec §7.2)
```
Exit triggers
-------------
Symbol  Reason            Close     Effective stop  Days held
------  ----------------  --------  --------------  ---------
AAPL    Trailing stop      $178.20         $179.50    47 days
MSFT    Initial stop       $315.00         $321.45     3 days
```
Use `render_table()` from ui/tables.py. Reasons: exactly `"Trailing stop"` or `"Initial stop"` (sentence case, no trailing periods).

### Pending triggers table format (from spec §7.2)
```
Pending exit triggers from previous scans
-----------------------------------------
Symbol  Triggered on   Reason           Original stop
------  -------------  ---------------  -------------
AAPL    2026-05-18     Trailing stop          $179.50
```
"Triggered on" date = `scans.scan_date` from the earliest `scan_exit_triggers` row for that position.

### Phase B multi-step output (from spec §7.2)
```
Running daily scan

[1/2] Fetching latest market data...
Progress:   ████████████░░░░░░░░  127/503  (25%)
Current:    GOOGL
Elapsed:    18s
Remaining:  ~52s

[1/2] Fetching latest market data... done.
      Constituents fetched: 503/503

[2/2] Computing signals... done.
```
Use `feedback.multi_step(2)`. Step 1 (`ms.step("Fetching latest market data", total=len(all_symbols))`) wraps the per-symbol `update_price_data` loop. After step 1 exits, print `      Constituents fetched: 503/503`. Step 2 (`ms.step("Computing signals")`) wraps all strategy filter calls.

### Market regime section (from spec §7.2)
```
Market regime
-------------
S&P 500 close:           5,234.50
S&P 500 SMA 200:         4,987.20
Regime:                  Bull market (close above SMA 200)
```
Use `render_kv_block()` from ui (the public function promoted in Phase 6). Values: `format_price()` for closes, plain text for regime label.

### Time-gate error behavior (from spec, CMD-03)
Refuse scan if before 16:30 ET. Use `print_error()` with title and `data={"Market closes at": "16:00 ET", "Scan available after": "16:30 ET", "Current time": "HH:MM ET"}`. Exit with `raise typer.Exit(code=1)`.

### scan_performed audit event metadata
Log with `payload={"scan_date": date.isoformat(), "regime_active": bool, "candidate_count": int, "exit_trigger_count": int}` as per spec §9 (Audit log specification).

</specifics>

<deferred>
## Deferred Ideas

- Full catch-up event templates (13 templates from spec §8.9) — Phase 11
- Split detection and adjustment — Phase 11 (DATA-06)
- Delisted position handling (log `position_delisted_from_index`, exclude from candidates) — Phase 11 (STATE-07)
- Snapshot tests for scan output with Console(width=120) — Phase 13 (TEST-04)
- Integration tests with fully mocked yfinance/Wikipedia/Slickcharts — Phase 13 (TEST-05)

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 7-Scan Command*
*Context gathered: 2026-05-24*
