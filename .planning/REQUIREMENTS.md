# Requirements: bensdorp1

**Defined:** 2026-05-23
**Core Value:** Every trading day, show the user exactly which positions triggered a stop and which stocks are top buy candidates, so they need less than 5 minutes of decision time.

## v1 Requirements

This is a single-version project. All requirements below are v1. There is no v2 roadmap.

### Strategy

- [ ] **STRAT-01**: Regime filter — buy candidates only generated when SPX close > SPX SMA 200 (200-day simple moving average of adjusted close)
- [ ] **STRAT-02**: Liquidity filter — restrict universe to top 25% of S&P 500 constituents by 20-day average volume
- [ ] **STRAT-03**: Momentum filter — stock close today > stock close 200 trading days ago (NYSE trading days only)
- [ ] **STRAT-04**: Ranking — candidates ranked descending by ROC 200: `(close_today / close_t-200) - 1`; top 10 selected
- [ ] **STRAT-05**: Maximum 10 open positions at any time
- [ ] **STRAT-06**: Position sizing — `shares = floor((available_cash * 0.10) / prev_close)` using user-declared cash
- [ ] **STRAT-07**: Initial stop — `entry_close * 0.93`, set once on entry day, never changes
- [ ] **STRAT-08**: Trailing stop — `highest_close_since_day_after_entry * 0.75`, updated daily
- [ ] **STRAT-09**: Effective stop — `max(initial_stop, trailing_stop)`; trigger when daily close <= effective_stop
- [ ] **STRAT-10**: Exit triggers persist across daily scans until confirmed closed by user

### Data

- [ ] **DATA-01**: S&P 500 constituents fetched from Wikipedia (primary) and cross-checked against Slickcharts (secondary)
- [ ] **DATA-02**: Constituents cross-check: 0-3 discrepancy → use primary silently; 4-10 → warn; 11+ → abort buy candidates, continue exit monitoring
- [ ] **DATA-03**: Price data via yfinance with `auto_adjust=True` (adjusted close for all calculations)
- [ ] **DATA-04**: 220 trading days of price history required (200 for calculations + 20-day buffer)
- [ ] **DATA-05**: Constituents cache refreshed automatically every 7 days at scan time
- [ ] **DATA-06**: Split detection and automatic position adjustment (shares, entry_price, stops) on every scan for held positions
- [ ] **DATA-07**: NYSE market calendar used for all trading day arithmetic — never calendar days
- [ ] **DATA-08**: Ticker normalization: period form (`BRK.B`) stored in DB; hyphen form (`BRK-B`) used only at yfinance call site
- [ ] **DATA-09**: Rate-limited yfinance download with retry: 3 retries, exponential backoff (1s, 2s, 4s) per symbol
- [ ] **DATA-10**: Scan aborted if fewer than 95% of constituents have price data

### Commands — Setup

- [ ] **CMD-01**: `bensdorp1 init` — interactive first-run setup: creates ~/bensdorp1/ directory tree, SQLite DB, fetches constituents, downloads 220-day price history, records initial cash; refuses if DB already exists
- [ ] **CMD-02**: `bensdorp1 restore PATH` — replaces current DB with backup; validates schema; two confirmation prompts; creates pre-restore backup automatically

### Commands — Daily Operation

- [ ] **CMD-03**: `bensdorp1 scan [--force]` — end-of-day screening; refuses before 16:30 ET; idempotent (shows existing scan without `--force`); outputs exit triggers then buy candidates
- [ ] **CMD-04**: `bensdorp1 last` — shows most recent scan output; does not re-run anything
- [ ] **CMD-05**: `bensdorp1 history [--limit N] [--since DATE]` — compact table of past scans

### Commands — Confirmations

- [ ] **CMD-06**: `bensdorp1 buy SYMBOL PRICE SHARES [--date DATE]` — records user-confirmed buy; validates constituent membership; prevents duplicate open positions; links to scan signal if applicable; off-signal warning if not in top 10
- [ ] **CMD-07**: `bensdorp1 sell SYMBOL PRICE [--date DATE] [--manual REASON]` — records user-confirmed sell; computes realized P&L; closes position
- [ ] **CMD-08**: `bensdorp1 fix SYMBOL [--date DATE]` — interactive correction of last transaction; preserves original in audit log; shows before/after diff and position impact

### Commands — Positions

- [ ] **CMD-09**: `bensdorp1 portfolio` — lists all open positions: symbol, entry date, days held, entry price, shares, last close, highest close, effective stop, distance to stop %, unrealized P&L
- [ ] **CMD-10**: `bensdorp1 detail SYMBOL` — full history of single open position including per-day highest close updates, splits applied, originating scan signal

### Commands — Configuration

- [ ] **CMD-11**: `bensdorp1 cash [AMOUNT] [--note REASON]` — shows current cash (no args) or updates it (with amount); confirmation prompt for updates
- [ ] **CMD-12**: `bensdorp1 config` — shows current configuration: cash, base directory, timezone, version

### Commands — Audit and System

- [ ] **CMD-13**: `bensdorp1 audit [--symbol SYMBOL] [--since DATE] [--until DATE] [--type TYPE] [--limit N]` — queries audit log with AND-filter logic; most recent first
- [ ] **CMD-14**: `bensdorp1 status` — diagnostic dashboard: data status, backup status, DB health, operational summary
- [ ] **CMD-15**: `bensdorp1 refresh` — forces re-fetch and re-verification of S&P 500 constituents from both sources

### Commands — Validation and Help

- [ ] **CMD-16**: `bensdorp1 validate DATE` — stateless historical verification: shows what buy candidates would have been on DATE; no state changes; validation mode banner
- [x] **CMD-17**: `bensdorp1 help [COMMAND]` — categorized command list or detailed help for a specific command

### State Management

- [x] **STATE-01**: SQLite database at ~/bensdorp1/data/bensdorp1.db (overridable via BENSDORP1_HOME env var)
- [x] **STATE-02**: Automatic backup after every state-changing operation using sqlite3.Connection.backup() API (not file copy)
- [x] **STATE-03**: Timestamped backup snapshots in ~/bensdorp1/backups/ — never auto-deleted; bensdorp1-latest.db always the most recent
- [x] **STATE-04**: Structured audit log with all 17 event types (system_initialized, scan_performed, buy_confirmed, sell_confirmed, sell_manual, transaction_corrected, cash_updated, constituents_updated, constituents_discrepancy, split_applied, position_delisted_from_index, regime_change_bull_to_bear, regime_change_bear_to_bull, data_fetch_failed, catch_up_performed, restore_performed, position_closed_manual)
- [ ] **STATE-05**: Catch-up logic for absences ≥ 2 trading days: reconstruct state (highest_close, trailing_stop) for all open positions over the missed days; surface 13 defined event templates
- [x] **STATE-06**: Multiple positions in same symbol allowed sequentially; no simultaneous open positions in same symbol
- [ ] **STATE-07**: Stocks delisted from S&P 500 while held — keep position open, continue stop monitoring, exclude from buy candidates

### UI and Output

- [ ] **UI-01**: All 31 style guide rules from spec section 6 implemented without exception
- [ ] **UI-02**: Severity prefixes with ANSI color: Error (red), Warning (yellow), Info (cyan), Success (green); text fallback in non-color terminals
- [ ] **UI-03**: Tables: minimalist (no borders, 2-space column separation), left-align text, right-align numbers, header alignment matches column
- [ ] **UI-04**: Feedback thresholds: silent <1s; spinner (braille: ⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏) 1-6s; progress bar 6-30s; progress bar + ETA >30s
- [ ] **UI-05**: Dual timezone on every timestamp: ET and user's local (default Lisbon; overridable via BENSDORP1_USER_TZ)
- [ ] **UI-06**: No decorative unicode icons (no ✓ ✗ ⚠ ℹ); no bold/italic/underline; sentence case throughout; plain text + color only
- [ ] **UI-07**: Confirmation prompts for all destructive/state-changing actions (buy, sell, fix, cash update, restore): show summary of impact before [y/n]
- [ ] **UI-08**: Empty states always explicit — never blank output; "No open positions." etc.
- [ ] **UI-09**: Critical message structure: Severity prefix + title, optional data block, optional impact section, optional recommended actions (numbered)
- [ ] **UI-10**: Numerical formatting: prices $X,XXX.XX; percentages ±X.X% (sign always); volumes X,XXX,XXX; P&L ±$X,XXX.XX (sign always); days "N days" / "1 day"

### Testing and CI

- [ ] **TEST-01**: Unit test coverage > 95% on strategy/ modules
- [ ] **TEST-02**: Unit test coverage > 90% on all source modules
- [ ] **TEST-03**: Property-based tests using Hypothesis for all strategy invariants (effective_stop >= initial_stop, trailing_stop monotonic, no candidates when regime off, etc.)
- [ ] **TEST-04**: Snapshot tests for all command outputs; Console(width=120) pinned in all snapshot tests
- [ ] **TEST-05**: Integration tests for end-to-end flows with mocked external services (yfinance, Wikipedia, Slickcharts)
- [x] **TEST-06**: CI pipeline: pytest + ruff + mypy strict on every push and PR via GitHub Actions

### Repository

- [x] **REPO-01**: MIT License, public open-source repository
- [x] **REPO-02**: Issues disabled (config.yml); Discussions disabled; Wiki disabled
- [ ] **REPO-03**: PRs auto-closed via GitHub Actions workflow (close-pr.yml) with policy message
- [ ] **REPO-04**: CONTRIBUTING.md explicitly stating no contributions accepted (no PRs, no issues, no feature requests)
- [ ] **REPO-05**: README with installation, usage, CI badge, license badge, clear "no contributions" statement
- [ ] **REPO-06**: Branch protection on main: CI must pass for any merge
- [x] **REPO-07**: GitHub Actions ci.yml: runs tests, lint, type check on push and PR

## v2 Requirements

None. This is a single-version project. v1 is the only version. Post-v1 is maintenance-only for critical bug fixes.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Broker integration (IBKR, Robinhood, etc.) | Signal generator only; trading is manual by design |
| Automated order execution | User executes all trades manually via broker |
| Backtest engine | `validate` is stateless verification, not portfolio simulation |
| Performance dashboards, cumulative P&L | Not in spec; misleading without broker integration |
| Closed positions history view | Accessible via `audit --symbol`; no dedicated command |
| Multi-user support | Single user only; personal tool |
| Web UI or mobile app | CLI only |
| Mean-reversion strategies | System #1 (trend following) only |
| Short-selling | Long-only strategy |
| Tax reporting, commission tracking | Out of scope; user's broker handles this |
| Multi-currency | USD only; NYSE-traded stocks |
| Partial fills | All-in / all-out only |
| Configurable strategy parameters | 0.93 and 0.75 are strategy rules, not preferences |
| CSV/Excel export | Stale file risk; audit log is the record |
| Trade journal / trade log | Out of spec |
| Localization / translations | English only |
| Themes / visual customization | Style guide is fixed |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STRAT-01 | Phase 4: Strategy Logic | Pending |
| STRAT-02 | Phase 4: Strategy Logic | Pending |
| STRAT-03 | Phase 4: Strategy Logic | Pending |
| STRAT-04 | Phase 4: Strategy Logic | Pending |
| STRAT-05 | Phase 4: Strategy Logic | Pending |
| STRAT-06 | Phase 4: Strategy Logic | Pending |
| STRAT-07 | Phase 4: Strategy Logic | Pending |
| STRAT-08 | Phase 4: Strategy Logic | Pending |
| STRAT-09 | Phase 4: Strategy Logic | Pending |
| STRAT-10 | Phase 4: Strategy Logic | Pending |
| DATA-01 | Phase 3: Data Sources | Pending |
| DATA-02 | Phase 3: Data Sources | Pending |
| DATA-03 | Phase 3: Data Sources | Pending |
| DATA-04 | Phase 3: Data Sources | Pending |
| DATA-05 | Phase 3: Data Sources | Pending |
| DATA-06 | Phase 11: Catch-Up Logic | Pending |
| DATA-07 | Phase 3: Data Sources | Pending |
| DATA-08 | Phase 3: Data Sources | Pending |
| DATA-09 | Phase 3: Data Sources | Pending |
| DATA-10 | Phase 3: Data Sources | Pending |
| CMD-01 | Phase 6: First-Run Init Command | Pending |
| CMD-02 | Phase 10: System Commands | Pending |
| CMD-03 | Phase 7: Scan Command | Pending |
| CMD-04 | Phase 9: Consultation Commands | Pending |
| CMD-05 | Phase 9: Consultation Commands | Pending |
| CMD-06 | Phase 8: Confirmation Commands | Pending |
| CMD-07 | Phase 8: Confirmation Commands | Pending |
| CMD-08 | Phase 8: Confirmation Commands | Pending |
| CMD-09 | Phase 9: Consultation Commands | Pending |
| CMD-10 | Phase 9: Consultation Commands | Pending |
| CMD-11 | Phase 9: Consultation Commands | Pending |
| CMD-12 | Phase 9: Consultation Commands | Pending |
| CMD-13 | Phase 9: Consultation Commands | Pending |
| CMD-14 | Phase 10: System Commands | Pending |
| CMD-15 | Phase 10: System Commands | Pending |
| CMD-16 | Phase 12: Validation Mode | Pending |
| CMD-17 | Phase 1: Project Skeleton and Tooling | Complete |
| STATE-01 | Phase 2: Database and Migrations | Complete |
| STATE-02 | Phase 2: Database and Migrations | Complete |
| STATE-03 | Phase 2: Database and Migrations | Complete |
| STATE-04 | Phase 2: Database and Migrations | Complete |
| STATE-05 | Phase 11: Catch-Up Logic | Pending |
| STATE-06 | Phase 2: Database and Migrations | Complete |
| STATE-07 | Phase 11: Catch-Up Logic | Pending |
| UI-01 | Phase 5: UI Components | Pending |
| UI-02 | Phase 5: UI Components | Pending |
| UI-03 | Phase 5: UI Components | Pending |
| UI-04 | Phase 5: UI Components | Pending |
| UI-05 | Phase 5: UI Components | Pending |
| UI-06 | Phase 5: UI Components | Pending |
| UI-07 | Phase 5: UI Components | Pending |
| UI-08 | Phase 5: UI Components | Pending |
| UI-09 | Phase 5: UI Components | Pending |
| UI-10 | Phase 5: UI Components | Pending |
| TEST-01 | Phase 4: Strategy Logic | Pending |
| TEST-02 | Phase 4: Strategy Logic | Pending |
| TEST-03 | Phase 4: Strategy Logic | Pending |
| TEST-04 | Phase 13: Edge Cases and Hardening | Pending |
| TEST-05 | Phase 13: Edge Cases and Hardening | Pending |
| TEST-06 | Phase 1: Project Skeleton and Tooling | Complete |
| REPO-01 | Phase 1: Project Skeleton and Tooling | Complete |
| REPO-02 | Phase 1: Project Skeleton and Tooling | Complete |
| REPO-03 | Phase 1: Project Skeleton and Tooling | Complete |
| REPO-04 | Phase 14: Documentation and Finalization | Pending |
| REPO-05 | Phase 14: Documentation and Finalization | Pending |
| REPO-06 | Phase 1: Project Skeleton and Tooling | Complete |
| REPO-07 | Phase 1: Project Skeleton and Tooling | Complete |

**Coverage:**

- v1 requirements: 57 total
- Mapped to phases: 57
- Unmapped: 0

---
*Requirements defined: 2026-05-23*
*Last updated: 2026-05-23 — traceability populated during roadmap creation*
