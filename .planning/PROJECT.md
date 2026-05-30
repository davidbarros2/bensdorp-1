# bensdorp1

## What This Is

`bensdorp1` is a single-user command-line interface for screening and monitoring stock positions based on System #1 (Trend Following on S&P 500 Stocks) from Laurens Bensdorp's "Trading Retirement Accounts". It generates daily buy candidates and monitors open positions for exit triggers — it does not execute trades. The user executes all trades manually via their broker; the CLI records confirmations and maintains state.

## Core Value

Every trading day, show the user exactly which positions triggered a stop and which stocks are top buy candidates, so they need less than 5 minutes of decision time.

## Requirements

### Validated

**State management (Phase 2 — Database and Migrations)**
- [x] SQLite database at ~/bensdorp1/data/bensdorp1.db — schema defined, 8 tables including scan_exit_triggers (Validated in Phase 2 + Phase 7)
- [x] Automatic backup after every state-changing operation — `create_backup()` via `sqlite3.Connection.backup()` (Validated in Phase 2)
- [x] Timestamped snapshots in ~/bensdorp1/backups/ (never auto-deleted) — `shutil.copy2` for latest.db (Validated in Phase 2)
- [x] Structured audit log with 17 event types — `AuditEventType` StrEnum + `log_event()` (Validated in Phase 2)
- [x] Maximum 10 open positions at any time — enforced by partial unique index `ix_positions_open_symbol` (Validated in Phase 2)

**First-run setup (Phase 6 — First-Run Init Command)**
- [x] `init` — DB creation, constituents fetch, 220-day price history download, cash declaration, `system_initialized` audit event (Validated in Phase 6)

### Active

**Strategy logic**
- [ ] Regime filter: buy candidates only generated when SPX close > SPX SMA 200
- [ ] Liquidity filter: restrict universe to top 25% of S&P 500 by 20-day average volume
- [ ] Momentum filter: stock close today > stock close 200 trading days ago
- [ ] Ranking: top 10 candidates by ROC 200 (rate of change over 200 trading days)
- [ ] Position sizing: 10% of declared available cash; shares = floor(position_size_usd / prev_close)
- [ ] Initial stop: entry_close * 0.93 (set once at entry, never changes)
- [ ] Trailing stop: highest_close_since_day_after_entry * 0.75 (updated daily)
- [ ] Effective stop: max(initial_stop, trailing_stop); trigger when close <= effective_stop
- [ ] Maximum 10 open positions at any time

**Data sourcing**
- [ ] S&P 500 constituents from Wikipedia (primary) + Slickcharts (secondary) with cross-check
- [ ] Price data via yfinance with auto_adjust=True (adjusted close for all calculations)
- [ ] NYSE market calendar via pandas_market_calendars for trading day arithmetic
- [ ] Constituents cache refreshed every 7 days; force-refresh via `refresh` command
- [ ] Automatic stock split detection and adjustment for held positions

**Commands (17 total)**
- [x] `init` — first-run setup (Validated in Phase 6)
- [x] `scan [--force]` — daily end-of-day screening; exit triggers + buy candidates (Validated in Phase 7)
- [ ] `last` — show most recent scan output
- [ ] `history [--limit N] [--since D]` — compact table of past scans
- [ ] `buy SYMBOL PRICE SHARES [--date D]` — confirm a buy; creates open position
- [ ] `sell SYMBOL PRICE [--date D] [--manual REASON]` — confirm a sell; closes position
- [ ] `fix SYMBOL [--date D]` — interactive correction of a recorded transaction
- [ ] `portfolio` — list all open positions with stop levels and unrealized P&L
- [ ] `detail SYMBOL` — full history of a single open position
- [ ] `cash [AMOUNT] [--note REASON]` — show or update available cash
- [ ] `config` — show current configuration
- [ ] `audit [filters]` — query the structured audit log
- [ ] `status` — system diagnostics dashboard
- [ ] `refresh` — force constituents re-fetch
- [ ] `restore PATH` — replace DB from a backup file
- [ ] `validate DATE` — stateless historical verification mode (no state changes)
- [ ] `help [COMMAND]` — command reference

**UI and output**
- [ ] All 31 style guide rules implemented (section 6 of spec)
- [ ] Severity prefixes: Error (red), Warning (yellow), Info (cyan), Success (green)
- [ ] Tables: minimalist, left-align text, right-align numbers, no borders
- [ ] Feedback thresholds: silent <1s, spinner 1-6s, progress bar 6-30s, with ETA >30s
- [ ] Timezone display: always show ET and Lisbon (user local) side by side
- [ ] No decorative unicode icons; no bold/italic/underline; sentence case throughout

**State management**
- [ ] SQLite database at ~/bensdorp1/data/bensdorp1.db
- [ ] Automatic backup after every state-changing operation
- [ ] Timestamped snapshots in ~/bensdorp1/backups/ (never auto-deleted)
- [ ] Structured audit log with 17 event types (full taxonomy in spec section 9)
- [ ] Catch-up logic: reconstruct state for any absence ≥ 2 trading days
- [ ] 13 catch-up event templates with fixed wording

**Testing**
- [x] Unit test coverage > 95% on strategy/ modules — 100% on screening.py + positions.py (Validated in Phase 4)
- [x] Unit test coverage > 90% overall — 96.17% across all modules (Validated in Phase 4)
- [x] Property-based tests for strategy invariants (pytest + Hypothesis) — 4 invariants, 1700 examples (Validated in Phase 4)
- [ ] Snapshot tests for all command outputs
- [ ] CI pipeline: tests, lint (ruff), type check (mypy strict) on every push/PR

**Repository**
- [ ] MIT License, public, open-source
- [ ] Issues and Discussions disabled; PRs auto-closed via workflow
- [ ] README with installation, usage, CI badge, license badge
- [ ] CONTRIBUTING.md explicitly stating no contributions accepted
- [ ] GitHub Actions: ci.yml + close-pr.yml

### Out of Scope

- Broker integration of any kind — this is a signal generator, not a trading bot
- Automated order execution — user executes all trades manually
- Backtest engine — `validate` mode is stateless verification only, not portfolio simulation
- Performance dashboards, cumulative P&L, closed positions history view — out of spec
- Multi-user support — single user only
- Web UI or mobile app — CLI only
- Mean-reversion strategies, short-selling — System #1 only, long-only
- Tax reporting, commission tracking, multi-currency — out of scope
- Partial fills — positions are all-in / all-out only
- Strategies other than System #1 — maintenance-only after v1
- Themes, localization, translations — English only, no visual customization

## Context

- Source strategy: Laurens Bensdorp, "Trading Retirement Accounts", System #1 (Trend Following on S&P 500 Stocks)
- "Relative strength" in the book = ROC over 200 trading days (confirmed by TuringTrader open-source implementation `Bensdorp_30MinStockTrader.cs`)
- All price calculations use adjusted close (yfinance `auto_adjust=True`)
- "200 trading days ago" uses NYSE trading calendar only (not calendar days)
- Trailing stop tracking starts the day AFTER entry (entry day close is the `entry_close`, not tracked)
- Target user: single non-coder in Lisbon, executing trades via broker manually
- Single-version project: v1 is the only version; post-v1 is maintenance-only

## Constraints

- **Language**: Python 3.11+ — specified in requirements
- **Package manager**: uv — specified in requirements
- **Database**: SQLite only, no external services — zero-config requirement
- **Market data**: yfinance only — free, no API key
- **Data directory**: ~/bensdorp1/ default; overridable via BENSDORP1_HOME env var
- **Timezone**: Eastern Time internally; Lisbon for user display (BENSDORP1_USER_TZ override)
- **Scan guard**: refuse scan if before 16:30 ET (market close + 30min buffer)
- **Max positions**: 10 simultaneous open positions (strategy rule)
- **No extensibility**: do not design for hypothetical future features; v1 is complete

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Typer for CLI framework | Type-hint based, modern, good auto-help, built on Click | — Pending |
| SQLAlchemy Core (not ORM) | Safe SQL composition without ORM complexity | — Pending |
| yfinance for market data | Free, no API key, sufficient for EOD data | — Pending |
| pandas_market_calendars for NYSE | Handles trading days, holidays, early closures | — Pending |
| Pydantic v2 for validation | Declarative, clear errors, works with Typer | — Pending |
| ruff for lint/format | Replaces flake8, isort, partially black; very fast | — Pending |
| mypy strict mode | Catches type errors early; mandatory for correctness | — Pending |
| Wikipedia as primary constituents source | More stable, parseable table; Slickcharts as cross-check only | — Pending |
| Adjusted close for all prices | Splits and dividends handled automatically by yfinance | — Pending |
| 14-phase development decomposition | Matches natural dependency boundaries (skeleton → data → strategy → UI → commands) | — Pending |
| `confirm_prompt` re-raises `KeyboardInterrupt` (Phase 6) | Callers' `except KeyboardInterrupt` blocks must fire; swallowing breaks Ctrl+C UX at nested prompts | Adopted — all prompt callers now rely on re-raise |
| `render_kv_block` promoted to public `bensdorp1.ui` surface (Phase 6) | Private `_render_kv_block` was deep-imported by `init.py`; promoting removes coupling to internal implementation detail | Adopted — exported via `ui/__init__.py` |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-30 — Phase 10 complete (System Commands — `bensdorp1 status`, `refresh`, `restore` implemented, 375 tests, 91% coverage, mypy strict clean)*
