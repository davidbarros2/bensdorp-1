# Roadmap: bensdorp1

## Overview

bensdorp1 is built in fourteen horizontal layers, each completing a technical stratum before the next builds on top. The project starts with repository scaffolding and tooling, lays the database foundation, then data sourcing, then strategy logic, then the shared UI layer — and only then implements commands one group at a time. The final phases harden edge cases, validate historical accuracy, and produce the finished documentation. Every layer is independently verifiable before the next begins.

## Phases

**Phase Numbering:**
- Integer phases (1–14): Planned milestone work executed in order
- Decimal phases (e.g., 2.1): Urgent insertions created via `/gsd-phase --insert`

- [ ] **Phase 1: Project Skeleton and Tooling** - Repo, package structure, CI, help command
- [ ] **Phase 2: Database and Migrations** - SQLite schema, backup, audit log, state tables
- [ ] **Phase 3: Data Sources** - Constituents fetch, price download, NYSE calendar, rate limiting
- [ ] **Phase 4: Strategy Logic** - All filters, ranking, stop calculations, unit and property tests
- [ ] **Phase 5: UI Components** - Style guide, formatting primitives, feedback thresholds, tables
- [ ] **Phase 6: First-Run Init Command** - `init` — directory tree, DB creation, history download, cash declaration
- [ ] **Phase 7: Scan Command** - `scan` — daily screening, regime/liquidity/momentum filters, exit triggers, buy candidates
- [ ] **Phase 8: Confirmation Commands** - `buy`, `sell`, `fix` — transaction recording and correction
- [ ] **Phase 9: Consultation Commands** - `portfolio`, `detail`, `last`, `history`, `cash`, `config`, `audit`
- [ ] **Phase 10: System Commands** - `status`, `refresh`, `restore`
- [ ] **Phase 11: Catch-Up Logic** - Absence reconstruction, split detection, delisted position handling
- [ ] **Phase 12: Validation Mode** - `validate DATE` — stateless historical verification
- [ ] **Phase 13: Edge Cases and Hardening** - Snapshot tests, integration tests, adversarial inputs
- [ ] **Phase 14: Documentation and Finalization** - README, CONTRIBUTING.md, final polish

## Phase Details

### Phase 1: Project Skeleton and Tooling
**Goal**: A developer can clone the repo, install the package with `uv`, and run `bensdorp1 help` — and the CI pipeline runs clean on every push
**Depends on**: Nothing (first phase)
**Requirements**: CMD-17, REPO-01, REPO-02, REPO-03, REPO-06, REPO-07, TEST-06
**Success Criteria** (what must be TRUE):
  1. `uv pip install -e .` completes without errors and `bensdorp1 --help` prints a categorized command list
  2. `bensdorp1 help <command>` returns detailed help for any recognized command name
  3. GitHub Actions ci.yml runs pytest, ruff, and mypy strict on every push and PR; the workflow passes on a clean repo
  4. PRs are auto-closed by close-pr.yml with the no-contributions policy message; Issues and Discussions are disabled in repo settings
**Plans**: TBD

### Phase 2: Database and Migrations
**Goal**: The SQLite schema is defined, migrations run idempotently, and all state-management primitives (backup, audit log) work in isolation
**Depends on**: Phase 1
**Requirements**: STATE-01, STATE-02, STATE-03, STATE-04, STATE-06
**Success Criteria** (what must be TRUE):
  1. Running the schema migration on a fresh path creates `~/bensdorp1/data/bensdorp1.db` with all expected tables and indexes
  2. A state-changing operation triggers `sqlite3.Connection.backup()` and produces a timestamped file under `~/bensdorp1/backups/` plus updates `bensdorp1-latest.db`
  3. Each of the 17 audit event types can be inserted and queried from the audit log table without errors
  4. Sequential positions in the same symbol are allowed; simultaneous positions in the same symbol are rejected with a clear error
**Plans**: TBD

### Phase 3: Data Sources
**Goal**: The data layer can fetch S&P 500 constituents, cross-check them, download price history, and apply all data-quality rules reliably
**Depends on**: Phase 2
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, DATA-09, DATA-10
**Success Criteria** (what must be TRUE):
  1. Constituents are fetched from Wikipedia and cross-checked against Slickcharts; discrepancy rules (0-3 silent, 4-10 warn, 11+ abort buy candidates) are enforced and logged
  2. `yfinance` returns 220 trading days of adjusted-close price history for a constituent symbol; all arithmetic uses NYSE trading days exclusively
  3. Tickers are stored in period form (`BRK.B`) and converted to hyphen form (`BRK-B`) only at the yfinance call site; this conversion is the sole place normalization occurs
  4. A failed download retries with exponential backoff (1 s, 2 s, 4 s); if fewer than 95% of constituents have price data, the scan is aborted with a clear error
**Plans**: TBD

### Phase 4: Strategy Logic
**Goal**: All System #1 filters, ranking, and stop calculations are implemented as pure functions with >95% unit-test coverage and full property-based test coverage
**Depends on**: Phase 3
**Requirements**: STRAT-01, STRAT-02, STRAT-03, STRAT-04, STRAT-05, STRAT-06, STRAT-07, STRAT-08, STRAT-09, STRAT-10, TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. Regime filter returns zero buy candidates when SPX close <= SPX SMA 200 and non-zero candidates when it is above (unit tests cover both branches)
  2. Liquidity filter correctly restricts the universe to the top 25% by 20-day average volume; momentum filter selects only stocks whose close today > close 200 NYSE trading days ago; ranking orders by ROC 200 and selects the top 10
  3. Position sizing computes `floor((cash * 0.10) / prev_close)` shares; initial stop is `entry_close * 0.93` (immutable); trailing stop is `highest_close_since_day_after_entry * 0.75` (monotonically non-decreasing); effective stop is `max(initial, trailing)`
  4. Hypothesis property tests verify: effective_stop >= initial_stop always, trailing stop never decreases, no buy candidates are generated when regime filter is off, and maximum 10 positions are ever open simultaneously
  5. `pytest --cov=strategy` reports >95% line coverage; `pytest --cov` on all modules reports >90%
**Plans**: TBD

### Phase 5: UI Components
**Goal**: All 31 style-guide rules are implemented as shared primitives that every command will call — tables, severity prefixes, feedback thresholds, timezone display, and numerical formatting
**Depends on**: Phase 1
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09, UI-10
**Success Criteria** (what must be TRUE):
  1. Severity prefix functions emit correctly colored ANSI output (Error red, Warning yellow, Info cyan, Success green) and fall back to plain text in non-color terminals; no decorative unicode icons appear anywhere
  2. Table renderer produces minimalist output (no borders, 2-space column separation, left-aligned text, right-aligned numbers, sentence case headers) for any provided dataset
  3. Feedback threshold logic triggers the correct output mode: silent for <1 s operations, braille spinner for 1–6 s, progress bar for 6–30 s, progress bar with ETA for >30 s
  4. Every timestamp rendered by any primitive displays both ET and the user's configured local timezone (default Lisbon) side by side
  5. Numerical formatting helpers produce: prices as `$X,XXX.XX`, percentages as `±X.X%`, P&L as `±$X,XXX.XX`, volumes as `X,XXX,XXX`, durations as `N days` / `1 day`
**Plans**: TBD
**UI hint**: yes

### Phase 6: First-Run Init Command
**Goal**: A developer can run `bensdorp1 init` on a clean machine, complete the interactive setup, and end with a populated database ready for daily scanning
**Depends on**: Phase 5
**Requirements**: CMD-01
**Success Criteria** (what must be TRUE):
  1. `bensdorp1 init` creates `~/bensdorp1/data/`, `~/bensdorp1/backups/`, fetches constituents, downloads 220 trading days of price history with a progress bar, and records the user-declared cash amount — all in a single uninterrupted flow
  2. Re-running `bensdorp1 init` on an already-initialized system prints a clear error and exits without modifying the database
  3. The `system_initialized` audit event is written with correct metadata after successful init
**Plans**: TBD

### Phase 7: Scan Command
**Goal**: Running `bensdorp1 scan` after 16:30 ET produces a complete daily screening report — exit triggers for open positions followed by ranked buy candidates — and is idempotent by default
**Depends on**: Phase 6
**Requirements**: CMD-03
**Success Criteria** (what must be TRUE):
  1. `bensdorp1 scan` run before 16:30 ET is refused with a clear time-gate error; run after 16:30 ET it executes the full screening pipeline
  2. Exit triggers for all open positions are listed first; buy candidates (when regime is on) are listed below, ranked by ROC 200, with position sizing computed per candidate
  3. Running `bensdorp1 scan` a second time on the same trading day shows the existing scan output without re-running; `bensdorp1 scan --force` re-runs and overwrites
  4. A `scan_performed` audit event is written with the correct trading date, regime state, candidate count, and exit trigger count
**Plans**: TBD

### Phase 8: Confirmation Commands
**Goal**: Users can record a buy, a sell, and correct a transaction — each with a confirmation prompt, impact preview, and full audit trail
**Depends on**: Phase 7
**Requirements**: CMD-06, CMD-07, CMD-08
**Success Criteria** (what must be TRUE):
  1. `bensdorp1 buy SYMBOL PRICE SHARES` validates constituent membership, rejects a duplicate open position in the same symbol, shows an off-signal warning if the symbol was not in the top 10 candidates, and creates an open position after `[y/n]` confirmation
  2. `bensdorp1 sell SYMBOL PRICE` computes realized P&L, closes the position, and writes both a `sell_confirmed` (or `sell_manual` with `--manual REASON`) audit event
  3. `bensdorp1 fix SYMBOL` interactively corrects the last transaction, displays a before/after diff with position impact, preserves the original record in the audit log, and writes a `transaction_corrected` event
**Plans**: TBD

### Phase 9: Consultation Commands
**Goal**: Users can inspect every aspect of their current portfolio and history — positions, cash, configuration, past scans, and the audit log — without triggering any state changes
**Depends on**: Phase 8
**Requirements**: CMD-04, CMD-05, CMD-09, CMD-10, CMD-11, CMD-12, CMD-13
**Success Criteria** (what must be TRUE):
  1. `bensdorp1 portfolio` lists all open positions with symbol, entry date, days held, entry price, shares, last close, highest close, effective stop, distance-to-stop %, and unrealized P&L — or prints "No open positions." when empty
  2. `bensdorp1 last` shows the most recent scan output instantly without re-running any data fetch; `bensdorp1 history` prints a compact table of past scans filterable by `--limit` and `--since`
  3. `bensdorp1 detail SYMBOL` shows the full position history including per-day highest-close updates, any splits applied, and the originating scan signal
  4. `bensdorp1 cash` prints current cash; `bensdorp1 cash AMOUNT` updates it after confirmation and writes a `cash_updated` event; `bensdorp1 config` prints cash, base directory, timezone, and version
  5. `bensdorp1 audit` returns audit events in most-recent-first order, filtered correctly by any combination of `--symbol`, `--since`, `--until`, `--type`, and `--limit`
**Plans**: TBD

### Phase 10: System Commands
**Goal**: Users can inspect system health, force a constituents refresh, and safely restore a database backup
**Depends on**: Phase 9
**Requirements**: CMD-02, CMD-14, CMD-15
**Success Criteria** (what must be TRUE):
  1. `bensdorp1 status` prints a diagnostic dashboard showing data freshness, backup recency, DB integrity, and an operational summary — all sourced from live state, not cached
  2. `bensdorp1 refresh` re-fetches and re-verifies S&P 500 constituents from both Wikipedia and Slickcharts, applies discrepancy rules, and writes a `constituents_updated` audit event
  3. `bensdorp1 restore PATH` validates the target file's schema, shows two confirmation prompts, creates a pre-restore backup automatically, replaces the active DB, and writes a `restore_performed` audit event
**Plans**: TBD

### Phase 11: Catch-Up Logic
**Goal**: After any absence of 2 or more trading days, the system reconstructs open position state (highest close, trailing stop) for every missed day and surfaces the correct catch-up event messages
**Depends on**: Phase 10
**Requirements**: STATE-05, STATE-07, DATA-06
**Success Criteria** (what must be TRUE):
  1. Running `bensdorp1 scan` after a 3-day absence triggers catch-up for all open positions: `highest_close` and `trailing_stop` are updated for each missed trading day using historical close data
  2. All 13 catch-up event templates (with fixed wording) are surfaced at scan time for the user to review; a `catch_up_performed` audit event is written
  3. Split detection runs on every scan for all held positions; when a split is detected, shares, entry price, and stop levels are adjusted and a `split_applied` audit event is written
  4. A position in a stock delisted from the S&P 500 remains open, continues stop monitoring on every scan, and is excluded from buy candidates; a `position_delisted_from_index` event is written
**Plans**: TBD

### Phase 12: Validation Mode
**Goal**: A developer or user can run `bensdorp1 validate DATE` to see what buy candidates System #1 would have produced on any historical date, with no changes to database state
**Depends on**: Phase 11
**Requirements**: CMD-16
**Success Criteria** (what must be TRUE):
  1. `bensdorp1 validate DATE` runs the full screening pipeline against historical data for DATE, shows a "validation mode — no state changes" banner, and outputs ranked buy candidates for that date
  2. After `bensdorp1 validate DATE` completes, the database is bit-for-bit identical to before the command ran — verified by comparing DB checksums before and after
  3. Validation mode respects all the same filters (regime, liquidity, momentum, ranking) as the live scan; results are comparable to the live scan output format
**Plans**: TBD

### Phase 13: Edge Cases and Hardening
**Goal**: All command outputs are snapshot-tested, end-to-end flows are integration-tested with mocked external services, and the system handles adversarial inputs gracefully
**Depends on**: Phase 12
**Requirements**: TEST-04, TEST-05
**Success Criteria** (what must be TRUE):
  1. Snapshot tests for all command outputs pass with `Console(width=120)` pinned; any output change requires an explicit snapshot update (no silent regressions)
  2. Integration tests cover all end-to-end command flows using mocked yfinance, Wikipedia, and Slickcharts responses; tests pass fully offline
  3. Adversarial inputs (invalid dates, unknown symbols, malformed prices, out-of-range values) produce the correct severity-prefixed error messages and non-zero exit codes — never a Python traceback
**Plans**: TBD

### Phase 14: Documentation and Finalization
**Goal**: The public repository is complete and self-explanatory — a new user can discover, install, and use the tool using only the README
**Depends on**: Phase 13
**Requirements**: REPO-04, REPO-05
**Success Criteria** (what must be TRUE):
  1. README contains installation instructions (uv), usage examples for the most common commands, a CI badge, a license badge, and an explicit "no contributions" statement
  2. CONTRIBUTING.md clearly states that no PRs, issues, or feature requests are accepted, and explains why (personal tool, maintenance-only)
  3. The CI pipeline passes clean: all tests green, ruff reports zero lint errors, mypy strict reports zero type errors
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Project Skeleton and Tooling | 0/TBD | Not started | - |
| 2. Database and Migrations | 0/TBD | Not started | - |
| 3. Data Sources | 0/TBD | Not started | - |
| 4. Strategy Logic | 0/TBD | Not started | - |
| 5. UI Components | 0/TBD | Not started | - |
| 6. First-Run Init Command | 0/TBD | Not started | - |
| 7. Scan Command | 0/TBD | Not started | - |
| 8. Confirmation Commands | 0/TBD | Not started | - |
| 9. Consultation Commands | 0/TBD | Not started | - |
| 10. System Commands | 0/TBD | Not started | - |
| 11. Catch-Up Logic | 0/TBD | Not started | - |
| 12. Validation Mode | 0/TBD | Not started | - |
| 13. Edge Cases and Hardening | 0/TBD | Not started | - |
| 14. Documentation and Finalization | 0/TBD | Not started | - |
