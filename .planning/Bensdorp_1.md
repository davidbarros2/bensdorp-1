# bensdorp1 — Specification

> Project specification document for development by Claude Code via the get-shit-done (GSD) framework. This is the single source of truth for the v1 implementation.

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [Trading strategy specification](#2-trading-strategy-specification)
3. [Tech stack and architecture](#3-tech-stack-and-architecture)
4. [Data sources](#4-data-sources)
5. [Command reference](#5-command-reference)
6. [UI/UX style guide](#6-uiux-style-guide)
7. [Specific flows](#7-specific-flows)
8. [Behaviors and edge cases](#8-behaviors-and-edge-cases)
9. [Audit log specification](#9-audit-log-specification)
10. [Backup and recovery](#10-backup-and-recovery)
11. [Testing and validation strategy](#11-testing-and-validation-strategy)
12. [GitHub repository specification](#12-github-repository-specification)
13. [Development methodology](#13-development-methodology)
14. [Glossary](#14-glossary)

---

## 1. Project overview

### 1.1 Objective

`bensdorp1` is a command-line interface (CLI) for screening and monitoring stock positions based on System #1 (Trend Following on S&P 500 Stocks) from Laurens Bensdorp's book "Trading Retirement Accounts: Automated Systems to Make Money in Bull and Sideways Markets, Preserve Your Wealth in Bear Markets, and Guard Against Inflation".

The CLI has two distinct capabilities:

- Generating daily buy candidates based on the strategy rules.
- Monitoring open positions for exit triggers based on stop-loss and trailing-stop rules.

The CLI does not execute trades. All actual trading is performed manually by the user via their broker. The CLI records the user's confirmed buy and sell transactions, maintains state of open positions, and produces signals to act upon.

### 1.2 Target user

A single user, non-coder, who manually executes trades via their broker based on the signals produced by the CLI. The CLI is for personal use only.

### 1.3 Philosophy: v1 set-and-forget

This is a single-version project. There is no MVP and no roadmap for future versions. Once development of v1 is complete, the project enters maintenance-only mode. All features described in this specification are part of v1.

All decisions in this document assume a fully featured v1 with no extensibility considerations beyond what is explicitly listed.

### 1.4 In-scope

- Single-user CLI built in Python.
- Local SQLite database for all state.
- Daily screening of S&P 500 stocks per Bensdorp System #1 rules.
- Open position monitoring with stop-loss and trailing-stop tracking.
- Manual confirmation of user-executed transactions.
- Audit log of all signals, transactions, and system events.
- Automatic backups on every state change.
- Validation mode for manual verification of implementation correctness.
- Catch-up logic for periods of user absence.
- Automatic adjustment for stock splits.
- Cross-checking of S&P 500 constituents against multiple sources.

### 1.5 Out-of-scope (explicit)

The following are explicitly NOT part of this project. The Claude Code agent must not implement any of these:

- Broker integration of any kind (Interactive Brokers, Robinhood, etc.).
- Automated order execution.
- Partial fills handling (transactions are all-in or all-out).
- Backtest engine (validation mode is stateless verification, not portfolio simulation).
- Performance tracking dashboards.
- Cumulative P&L reports across multiple positions or time periods.
- Closed positions history view.
- Multi-user support.
- Web UI or mobile app.
- Mean-reversion strategies (long or short).
- Short-selling.
- Trade journal or trade log features.
- Tax reporting.
- Commission tracking.
- Multi-currency support.
- Strategies other than System #1.
- Translation or localization (English only).
- Themes or visual customization beyond what is described in the style guide.

### 1.6 Open-source policy

The project is open-source under the MIT License. The public can view, fork, and clone the repository.

No contributions of any kind are accepted: no pull requests, no feature requests, no bug reports through Issues. This is intentional and clearly stated in the `CONTRIBUTING.md` and `README.md`.

Repository settings reflect this policy. See section 12 for details.

---

## 2. Trading strategy specification

This section specifies the exact rules of System #1. Source: Bensdorp, Laurens. "Trading Retirement Accounts", Chapter on System #1: Trend Following on S&P 500 Stocks.

### 2.1 Overview

System #1 is a long-only trend following strategy on S&P 500 stocks. Objective: make money during bull markets by holding strong-trending stocks until their trend reverses.

The system has low trade frequency and minimal maintenance. It will lose money when trends reverse and during bear markets — this is a necessary characteristic of the strategy and not a bug.

Expected characteristics from the book:
- About 60% of trades are losing trades.
- The average winning trade is approximately 7.8 times larger than the average losing trade.
- Low maintenance: a few minutes per day.

### 2.2 Trading universe

All stocks currently in the S&P 500 index.

### 2.3 Filters

**Liquidity filter:** trade only stocks that are currently in the top 25% by 20-day average volume. Calculated as:
- 20-day simple moving average of daily volume for each S&P 500 constituent.
- Rank all current constituents descending by that average.
- Keep only those in the top 25% (e.g. roughly top 125 out of ~503 constituents).

### 2.4 Setup conditions

A stock is eligible for entry if ALL of the following are true:

1. **Regime filter:** Close of the S&P 500 index (ticker `^GSPC`) today is above its 200-day simple moving average (SMA 200).
2. **Per-stock momentum filter:** The close of the stock today is higher than its close 200 trading days ago.

If condition 1 (regime filter) is false, no new positions are entered. Existing positions continue to be monitored normally.

### 2.5 Ranking

When more than 10 candidate stocks pass the filters and setup conditions, candidates are ranked by **Rate of Change (ROC) over 200 trading days**:

```
ROC_200 = (close_today / close_200_trading_days_ago) - 1
```

Candidates are ranked descending by `ROC_200`. The top 10 are selected for the day's buy candidates.

This ranking metric is the "relative strength" referenced in the book. The implementation must use ROC over 200 trading days. This interpretation is confirmed by the independent open-source implementation in TuringTrader's `Bensdorp_30MinStockTrader.cs` file (Weekly Rotation strategy), which uses the same ranking metric.

### 2.6 Position sizing

- Maximum 10 open positions at any time.
- Each new position uses 10% of the available cash declared by the user.
- Available cash is declared at initialization and updated manually via the `cash` command. The system does not track real-time portfolio value; it relies solely on the user-declared cash.
- Position size is computed as:
  ```
  position_size_usd = available_cash * 0.10
  shares = floor(position_size_usd / expected_open_price)
  ```
- The "expected open price" for sizing recommendations is the previous day's close (as a proxy, since the system runs after close and the next day's open is unknown).
- The user is responsible for executing with the actual size they choose. The CLI records what the user actually executed.

### 2.7 Entry execution

When a buy candidate is selected, the entry is at the next trading day's market open price. The CLI generates buy candidates at the end of day; the user executes the order at the next session's open.

The CLI records the user-reported actual fill price when the user confirms the buy via `bensdorp1 buy SYMBOL PRICE SHARES`.

### 2.8 Exit rules

Two stop levels are tracked for every open position:

**Initial stop loss:** set at 7% below the closing price on the day the position was opened (entry day close).
```
initial_stop = entry_close * 0.93
```

**Trailing stop:** set at 25% below the highest closing price observed since the position was opened (excluding the entry day close — tracking starts from the day after entry).
```
trailing_stop = highest_close_since_entry * 0.75
```

The **effective stop** on any given day is the higher of `initial_stop` and `trailing_stop`:
```
effective_stop = max(initial_stop, trailing_stop)
```

**Trigger condition:** the stop is triggered if the daily close is less than or equal to the `effective_stop`.

**Exit execution:** exit is at the next trading day's market open price. The CLI generates the exit trigger at end of day; the user executes the sell at the next session's open.

### 2.9 Specific formulas (canonical reference)

| Metric | Formula | Notes |
|---|---|---|
| SMA 200 (SPX) | Mean of close prices over the last 200 trading days, inclusive of today | Used for regime filter |
| ROC 200 (stock) | `(close_today / close_t-200) - 1` | `t-200` = 200 trading days ago |
| 20-day average volume | Mean of daily volume over the last 20 trading days, inclusive of today | Used for liquidity filter |
| Top 25% by volume | Sort descending by 20-day average volume, keep first 25% | Of currently-S&P-500-listed stocks |
| Initial stop | `entry_close * 0.93` | Computed once on entry day |
| Trailing stop | `max_close_since_entry_day_plus_1 * 0.75` | Updated daily; max excludes entry day close |
| Effective stop | `max(initial_stop, trailing_stop)` | |

All prices used for calculations are **adjusted close prices** (adjusted for splits and dividends), as provided by yfinance via the `Close` column when `auto_adjust=True` is set.

### 2.10 Strategy clarifications and decisions

The following clarifications resolve ambiguities in the book's prose and are part of the canonical specification:

- **"Relative strength"** in the book refers to ROC over 200 trading days. See 2.5.
- **"200 trading days ago"** counts trading days only, not calendar days. Use the NYSE trading calendar.
- **Highest close since entry** is calculated starting from the close on the day **after** entry (entry day close is the `entry_close`, not part of the highest tracking). Update daily by `max(highest_close_so_far, close_today)`.
- **Position sizing base** is the user-declared available cash, not portfolio equity. The system does not track equity.
- **Multiple positions in the same symbol** are not allowed at the same time. Once a position is closed, the same symbol can be entered again later if it qualifies; this is treated as a new, independent position with its own history.
- **Stocks delisted from S&P 500 while held** are kept in the portfolio until a normal stop triggers. Buy candidates do not include them once they are out of the index.
- **Exit triggers persist** across daily scans until the position is confirmed as closed. If a stop was triggered on a previous day and the user has not yet recorded the sell, the exit trigger continues to appear in subsequent scans with an indication of when it was first triggered.

---

## 3. Tech stack and architecture

### 3.1 Stack choices

**Language:** Python 3.11 or later.

**CLI framework:** Typer. Reason: type-hint based, modern, built on Click, excellent auto-help, good for non-trivial CLIs.

**Output rendering:** Rich. Reason: handles tables, colors, progress bars, spinners with consistent rendering across terminals and a clean fallback for unsupported terminals.

**Database:** SQLite via the built-in `sqlite3` module. Reason: zero-config, file-based, atomic transactions, no external service needed.

**Database access layer:** SQLAlchemy Core (not the full ORM). Reason: provides safe SQL composition and connection management without the complexity of the ORM.

**Data validation:** Pydantic v2. Reason: declarative validation, clear error messages, integrates well with Typer.

**Market data:** yfinance. Reason: free, no API key, sufficient for end-of-day data on S&P 500.

**Market calendar:** `pandas_market_calendars`. Reason: handles NYSE trading days, holidays, early closures.

**Timezone handling:** Python standard library `zoneinfo` module. Reason: built-in since Python 3.9, no external dependency.

**Numerical computation:** pandas, NumPy. Used for time series manipulation, rolling windows, ranking.

**HTTP requests:** httpx. Used for fetching S&P 500 constituents from Wikipedia and Slickcharts.

**HTML parsing:** beautifulsoup4. Used for parsing the constituents tables.

**Testing:** pytest, pytest-cov (coverage), Hypothesis (property-based testing).

**Linting and formatting:** ruff. Reason: fast, replaces flake8, isort, and partially black.

**Type checking:** mypy in strict mode.

**Package manager:** uv. Reason: fast, modern Python package manager from Astral.

### 3.2 Folder structure

```
bensdorp1/
├── data/
│   └── bensdorp1.db            # main SQLite database
├── backups/
│   ├── bensdorp1-latest.db     # always the most recent snapshot, overwritten
│   ├── bensdorp1-{ts}.db       # historical snapshots, never deleted
│   └── ...
└── logs/
    └── bensdorp1.log           # internal application log
```

This folder is created in the user's home directory by default: `~/bensdorp1/`. On Windows: `C:\Users\<username>\bensdorp1\`. The location can be overridden via an environment variable `BENSDORP1_HOME` (advanced use).

### 3.3 Project layout (source code)

```
bensdorp1/
├── src/
│   └── bensdorp1/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py                  # Typer app entry point
│       ├── commands/               # one module per command
│       │   ├── __init__.py
│       │   ├── init.py
│       │   ├── scan.py
│       │   ├── last.py
│       │   ├── history.py
│       │   ├── buy.py
│       │   ├── sell.py
│       │   ├── fix.py
│       │   ├── portfolio.py
│       │   ├── detail.py
│       │   ├── cash.py
│       │   ├── config.py
│       │   ├── audit.py
│       │   ├── status.py
│       │   ├── refresh.py
│       │   ├── restore.py
│       │   ├── validate.py
│       │   └── help.py
│       ├── strategy/
│       │   ├── __init__.py
│       │   ├── indicators.py       # SMA, ROC, volume average
│       │   ├── filters.py          # regime, momentum, liquidity
│       │   ├── ranking.py
│       │   ├── stops.py
│       │   └── sizing.py
│       ├── data/
│       │   ├── __init__.py
│       │   ├── constituents.py     # Wikipedia + Slickcharts fetch and cross-check
│       │   ├── prices.py           # yfinance integration
│       │   ├── calendar.py         # NYSE calendar
│       │   └── cache.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.py           # table definitions
│       │   ├── migrations.py       # versioned schema setup
│       │   └── queries.py
│       ├── audit/
│       │   ├── __init__.py
│       │   ├── events.py           # event taxonomy
│       │   └── logger.py
│       ├── backup/
│       │   ├── __init__.py
│       │   └── manager.py
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── styles.py           # colors, alignment constants
│       │   ├── tables.py
│       │   ├── messages.py         # template-based message formatting
│       │   ├── prompts.py
│       │   ├── progress.py
│       │   └── empty_states.py
│       ├── templates/
│       │   ├── __init__.py
│       │   ├── events.py           # the 13 catch-up event templates
│       │   └── messages.py         # other reusable message templates
│       └── config.py               # PROJECT_NAME constant, paths
├── tests/
│   ├── unit/
│   ├── property/
│   ├── snapshot/
│   └── fixtures/
├── pyproject.toml
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CHANGELOG.md
├── .gitignore
└── .github/
    ├── ISSUE_TEMPLATE/
    │   └── config.yml              # disables issue creation
    ├── PULL_REQUEST_TEMPLATE.md
    └── workflows/
        ├── ci.yml                  # tests on push/PR
        └── close-pr.yml            # auto-closes PRs with policy message
```

### 3.4 Database schema

The schema below uses SQLite syntax. Tables are created via `db/schema.py` on first run. The database file is `data/bensdorp1.db`.

```sql
-- System metadata: version, init timestamp, etc.
CREATE TABLE system_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- User configuration: cash and other settings
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL  -- ISO 8601 with timezone
);

-- Current S&P 500 constituents list
CREATE TABLE constituents (
    symbol TEXT PRIMARY KEY,
    company_name TEXT,
    added_at TEXT NOT NULL    -- when the system first saw this stock as a constituent
);

-- History of constituents changes
CREATE TABLE constituents_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT NOT NULL,       -- date the change was detected
    symbol TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('added', 'removed')),
    detected_at TEXT NOT NULL       -- timestamp of detection
);

-- Cached price data
CREATE TABLE prices (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,       -- YYYY-MM-DD
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,             -- adjusted close
    volume INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX idx_prices_date ON prices(trade_date);

-- Scans (one row per scan run)
CREATE TABLE scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date TEXT NOT NULL UNIQUE,  -- YYYY-MM-DD, the trading day the scan represents
    run_at TEXT NOT NULL,            -- ISO 8601 timestamp of the run
    spx_close REAL NOT NULL,
    spx_sma_200 REAL NOT NULL,
    regime TEXT NOT NULL CHECK(regime IN ('bull', 'bear')),
    constituents_count INTEGER NOT NULL
);

-- Buy candidates from each scan (ranked)
CREATE TABLE scan_buy_candidates (
    scan_id INTEGER NOT NULL,
    rank_position INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    close REAL NOT NULL,
    roc_200 REAL NOT NULL,
    volume_avg_20 INTEGER NOT NULL,
    affordable INTEGER NOT NULL,     -- 1 if affordable with current cash, 0 otherwise
    PRIMARY KEY (scan_id, rank_position),
    FOREIGN KEY (scan_id) REFERENCES scans(id)
);

-- Exit triggers from each scan
CREATE TABLE scan_exit_triggers (
    scan_id INTEGER NOT NULL,
    position_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    trigger_reason TEXT NOT NULL CHECK(trigger_reason IN ('initial_stop', 'trailing_stop')),
    close REAL NOT NULL,
    effective_stop REAL NOT NULL,
    delisted INTEGER NOT NULL DEFAULT 0,  -- 1 if also delisted from S&P 500
    PRIMARY KEY (scan_id, position_id),
    FOREIGN KEY (scan_id) REFERENCES scans(id),
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

-- Open positions (current state)
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    entry_price REAL NOT NULL,
    shares INTEGER NOT NULL,
    initial_stop REAL NOT NULL,
    highest_close REAL,             -- NULL until day 2; updated daily
    trailing_stop REAL,             -- NULL until day 2
    status TEXT NOT NULL CHECK(status IN ('open', 'closed')),
    closed_date TEXT,
    closed_price REAL,
    closed_reason TEXT,             -- 'stop_initial', 'stop_trailing', 'manual'
    closed_manual_reason TEXT,
    realized_pnl REAL,
    confirmed_signal_scan_id INTEGER,  -- the scan that generated the buy signal followed; NULL if off-signal
    confirmed_at TEXT NOT NULL,
    FOREIGN KEY (confirmed_signal_scan_id) REFERENCES scans(id)
);

CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_status ON positions(status);

-- Audit log: all events
CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,   -- ISO 8601 with timezone
    event_date TEXT NOT NULL,        -- trading day this event refers to (YYYY-MM-DD)
    symbol TEXT,                     -- nullable; not all events are symbol-specific
    position_id INTEGER,             -- nullable
    data_json TEXT NOT NULL,         -- structured event payload as JSON
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

CREATE INDEX idx_audit_type ON audit_events(event_type);
CREATE INDEX idx_audit_date ON audit_events(event_date);
CREATE INDEX idx_audit_symbol ON audit_events(symbol);
```

### 3.5 Project name parametrization

The project name `bensdorp1` must be defined in exactly one location:

```python
# src/bensdorp1/config.py
PROJECT_NAME = "bensdorp1"
```

All other references to the project name in the source code MUST use this constant. The folder structure (`~/bensdorp1/`), the CLI command (`bensdorp1 ...`), the package name, and any user-facing strings derive from this constant.

The package name in `pyproject.toml` is the only other place where the name appears literally. Renaming the project is therefore a two-location change: `PROJECT_NAME` and `pyproject.toml` (plus renaming the source folder `src/bensdorp1/`). This should be doable in under 5 minutes.

---

## 4. Data sources

### 4.1 S&P 500 constituents

**Primary source:** Wikipedia. URL: `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies`. Parse the first wikitable on the page.

**Secondary source:** Slickcharts. URL: `https://www.slickcharts.com/sp500`. Parse the constituents table.

**Update frequency:** automatic check at every `scan` invocation. If the cached list is older than 7 days, re-fetch.

**Cross-check rules:**

| Discrepancy (symbols difference) | Action |
|---|---|
| 0–3 | Use primary source. Normal delay between sources. |
| 4–10 | Use primary source. Log warning to audit. |
| 11+ | Abort buy candidate generation for the day. Continue exit triggers monitoring. Warn the user with the standard warning format (see section 6 and section 7.2). |

**Storage:** the current list is in the `constituents` table; changes are recorded in `constituents_history`.

**Handling for stocks with multiple share classes (e.g. `GOOG`/`GOOGL`, `BRK.A`/`BRK.B`):** include all listed share classes as separate tickers. The S&P 500 typically has 503-505 distinct tickers for ~500 companies. Symbols with periods in them (`BRK.B`) must be normalized to the form yfinance accepts (`BRK-B`).

### 4.2 Price data

**Source:** yfinance.

**Data fetched per symbol:** OHLCV daily bars, adjusted (set `auto_adjust=True`).

**Required history depth:** at least 220 trading days from today (200 for ROC and SMA calculations, plus 20-day buffer for the 20-day volume average and small safety margin).

**Fetch strategy:**
- On `init`: fetch the full 220-day history for all current constituents.
- On every `scan`: fetch only the latest day's data for all symbols (incremental update).
- On catch-up scenarios: fetch the missing days for all symbols.

**Rate limiting and failures:**
- yfinance has unofficial rate limits. Use a delay of 100ms between symbol fetches in the initial bulk download.
- Retry strategy: 3 retries with exponential backoff (1s, 2s, 4s) on transient failures.
- If any symbol fails after retries, log to audit and proceed. The scan continues with partial data, but if the partial data covers fewer than 95% of constituents, the scan is aborted with a clear error.

**Caching:** all fetched data is stored in the `prices` table. The cache is the canonical source for all calculations.

**Splits and adjustments:** yfinance returns adjusted close prices, which automatically account for splits and dividends. The system uses adjusted close exclusively. For position tracking, the system also fetches and tracks splits via yfinance's `splits` accessor; when a split is detected for a held position, the system applies the split ratio to the recorded `shares` and `entry_price`, and logs the adjustment to audit (event type `split_applied`).

### 4.3 Market calendar

**Source:** `pandas_market_calendars`, using the `NYSE` exchange.

**Used for:**
- Determining if today is a trading day.
- Computing "200 trading days ago".
- Detecting holidays.
- Computing the next trading day for "next day open" semantics in exit and entry signals.

### 4.4 Timezone handling

**Internal timezone:** Eastern Time (US). All timestamps and dates internally are in `America/New_York` (the NYSE timezone). The standard library `zoneinfo` is used.

**User display timezone:** the user's local timezone is auto-detected via `time.tzname` or `zoneinfo.ZoneInfo("Europe/Lisbon")` (the default, since the target user is in Lisbon). It can be overridden via an environment variable `BENSDORP1_USER_TZ`.

**Daylight saving:** automatically handled by `zoneinfo`. No manual switching required between WET and WEST.

**All output that includes times** shows both ET and the user's local time, side by side, per UI rule 26.

---

## 5. Command reference

The CLI entry point is `bensdorp1` (defined as a console script in `pyproject.toml`). All commands are sub-commands of `bensdorp1`.

### 5.1 Commands overview

```
SETUP
  bensdorp1 init                              First-time setup

DAILY OPERATION
  bensdorp1 scan [--force]                    Run the daily scan
  bensdorp1 last                              Show the latest scan
  bensdorp1 history [--limit N] [--since D]   List past scans

CONFIRMATIONS
  bensdorp1 buy SYMBOL PRICE SHARES [--date D]            Confirm a buy
  bensdorp1 sell SYMBOL PRICE [--date D] [--manual REASON] Confirm a sell
  bensdorp1 fix SYMBOL [--date D]             Fix the last transaction of the symbol

POSITIONS
  bensdorp1 portfolio                         List open positions
  bensdorp1 detail SYMBOL                     Show detail of an open position

CONFIGURATION
  bensdorp1 cash                              Show current cash
  bensdorp1 cash AMOUNT [--note REASON]       Update cash
  bensdorp1 config                            Show configuration

AUDIT
  bensdorp1 audit [filters]                   Show audit log

SYSTEM
  bensdorp1 status                            Full system diagnostics
  bensdorp1 refresh                           Force constituents re-check
  bensdorp1 restore PATH                      Restore from a backup

VALIDATION
  bensdorp1 validate DATE                     Validate implementation (stateless)

HELP
  bensdorp1 help                              List commands
  bensdorp1 help COMMAND                      Detailed help for a command
```

### 5.2 Per-command specification

The following subsections specify the exact behavior of each command. Output formatting follows the UI/UX style guide in section 6. Specific flows that are interactive are detailed in section 7.

#### 5.2.1 `bensdorp1 init`

- **Args:** none.
- **Flags:** none.
- **Behavior:** Interactive setup. See flow in section 7.1.
- **Side effects:** Creates `~/bensdorp1/` directory tree, creates SQLite database with full schema, fetches constituents, downloads price history, records initial cash, logs `system_initialized` event to audit.
- **Validations:**
  - Refuses if `~/bensdorp1/data/bensdorp1.db` already exists. Error message must direct the user to either delete the directory manually or use `bensdorp1 restore`.
  - Initial cash must be a positive number.
- **Errors:**
  - Database already exists: `Error: System already initialized at PATH.`
  - Cash invalid: `Error: Cash must be a positive number.`
  - Network failure: `Error: Could not download required data. Check your internet connection and try again.`
  - Insufficient disk space: `Error: Insufficient disk space. Approximately X MB required, Y MB available.`

#### 5.2.2 `bensdorp1 scan [--force]`

- **Args:** none.
- **Flags:**
  - `--force`: re-run the scan even if one has already been performed today.
- **Behavior:** End-of-day screening. See flow in section 7.2.
- **Output:** Two main tables — exit triggers (for open positions whose stop was hit) and buy candidates (top 10 ranked by ROC 200, plus a separate top 10 affordable). Plus catch-up summary if applicable. Plus persistent alerts for unconfirmed exit triggers from previous scans.
- **Side effects:** Creates a scan record, logs `scan_performed` to audit, may update constituents if stale, may detect and apply splits.
- **Validations:**
  - Today must be a trading day. If not, show the last scan instead with a clear message.
  - Market must have closed. The system uses NYSE close time (16:00 ET) plus a 30-minute buffer. If invoked before that buffer, refuse with a clear "try again at X" message (in user's local time).
  - Without `--force`: if a scan for today already exists, show the existing result instead of re-running.
- **Errors:**
  - Not a trading day: `Info: Today is not a trading day. Last trading day was YYYY-MM-DD.`
  - Market not closed yet: `Info: Market is still open. End-of-day data not available until HH:MM ET (HH:MM Lisbon).`
  - Data fetch failed for >5% of constituents: `Error: Could not fetch reliable data. Try again later.`

#### 5.2.3 `bensdorp1 last`

- **Args:** none.
- **Flags:** none.
- **Behavior:** Shows the most recently completed scan, including all its output (exit triggers, buy candidates, warnings). Idempotent — does not re-run anything.
- **Empty state:** If no scan has ever been performed, show empty state message directing to `bensdorp1 scan`.

#### 5.2.4 `bensdorp1 history [--limit N] [--since DATE]`

- **Args:** none.
- **Flags:**
  - `--limit N`: number of scans to show. Default: 20.
  - `--since DATE`: show scans on or after DATE (`YYYY-MM-DD`).
- **Behavior:** Lists past scans in a compact table: scan date, regime, count of exit triggers, count of buy candidates, top 3 buy candidates by symbol.
- **Empty state:** If no scans match the filters, show empty state.

#### 5.2.5 `bensdorp1 buy SYMBOL PRICE SHARES [--date DATE]`

- **Args:**
  - `SYMBOL`: ticker (case-insensitive on input, normalized to uppercase).
  - `PRICE`: positive number, in USD.
  - `SHARES`: positive integer.
- **Flags:**
  - `--date DATE`: trade date (`YYYY-MM-DD`). Default: today.
- **Behavior:** Records the user-confirmed buy. Creates an open position.
- **Validations:**
  - `SYMBOL` must be a current S&P 500 constituent. Error otherwise.
  - User must not already have an open position in `SYMBOL`. Error otherwise.
  - `PRICE` must be positive.
  - `SHARES` must be positive integer.
  - `DATE` must not be in the future.
  - `DATE` must not predate the earliest available price data.
  - If a scan exists for `DATE` and `SYMBOL` was in the top 10 of that scan's buy candidates, the position is recorded with a link to that scan (`confirmed_signal_scan_id`). Otherwise, the position is recorded as off-signal (`confirmed_signal_scan_id` is NULL) and a warning is shown to the user before the confirmation prompt.
- **Output:** Confirmation prompt per UI rule 17. On success, summary of the recorded buy.
- **Side effects:** Creates a row in `positions` (status `open`); logs `buy_confirmed` event to audit.

#### 5.2.6 `bensdorp1 sell SYMBOL PRICE [--date DATE] [--manual REASON]`

- **Args:**
  - `SYMBOL`: ticker.
  - `PRICE`: positive number, in USD.
- **Flags:**
  - `--date DATE`: trade date. Default: today.
  - `--manual REASON`: text reason for an extraordinary close (not driven by a stop trigger). Mandatory when this flag is used.
- **Behavior:** Records the user-confirmed sell. Closes the open position.
- **Validations:**
  - `SYMBOL` must have an open position. Error otherwise.
  - `PRICE` must be positive.
  - `DATE` must not be in the future.
  - If `--manual` is used, `REASON` must be non-empty text.
- **Output:** Confirmation prompt showing the position being closed, the proposed close details, and computed realized P&L. On success, summary.
- **Side effects:** Updates the position row to `status='closed'` with `closed_date`, `closed_price`, `closed_reason`, `closed_manual_reason`, `realized_pnl`. Logs `sell_confirmed` or `sell_manual` event to audit.

#### 5.2.7 `bensdorp1 fix SYMBOL [--date DATE]`

- **Args:**
  - `SYMBOL`: ticker.
- **Flags:**
  - `--date DATE`: target transaction date. Default: last transaction of the symbol.
- **Behavior:** Interactive correction of a previously recorded transaction. See flow in section 7.5.
- **Validations:**
  - At least one transaction must exist for `SYMBOL`. Error otherwise.
  - If `--date` is provided, a transaction must exist for that date. Error otherwise.
- **Side effects:** Updates the transaction record (in `positions` or related tables) with the corrections. The original entry is preserved as a row-level snapshot in the audit log (event type `transaction_corrected` with `before` and `after` payloads).

#### 5.2.8 `bensdorp1 portfolio`

- **Args:** none.
- **Flags:** none.
- **Behavior:** Lists all open positions in a table.
- **Columns:** Symbol, Entry date, Days held, Entry price, Shares, Last close, Highest close, Effective stop, Distance to stop (%), P&L unrealized.
- **Empty state:** "No open positions." Message directing to `bensdorp1 scan` if no scan has been run, otherwise just the empty state message.

#### 5.2.9 `bensdorp1 detail SYMBOL`

- **Args:** `SYMBOL` of an open position.
- **Flags:** none.
- **Behavior:** Detailed view of a single open position.
- **Output includes:** All fields from `portfolio` plus full history of highest close updates (per-day for the lifetime of the position), any splits applied, the scan that generated the signal (if applicable), and timestamp of confirmation.
- **Validations:** Position must exist and be open.

#### 5.2.10 `bensdorp1 cash [AMOUNT] [--note REASON]`

- **Args:**
  - `AMOUNT` (optional): new cash value. If omitted, the command shows the current cash.
- **Flags:**
  - `--note REASON`: optional textual reason for the update.
- **Behavior:**
  - Without `AMOUNT`: shows current cash and the timestamp of the last update.
  - With `AMOUNT`: prompts for confirmation (per UI rule 17), then updates.
- **Validations:** `AMOUNT` must be non-negative number.
- **Side effects:** Updates `config` table; logs `cash_updated` to audit (with old value, new value, and optional reason).

#### 5.2.11 `bensdorp1 config`

- **Args:** none.
- **Flags:** none.
- **Behavior:** Shows current configuration: cash amount, base directory, timezone, version, etc.

#### 5.2.12 `bensdorp1 audit [filters]`

- **Args:** none.
- **Flags:**
  - `--symbol SYMBOL`: filter to events related to this ticker.
  - `--since DATE`: events on or after DATE.
  - `--until DATE`: events on or before DATE.
  - `--type TYPE`: filter to a specific event type (see section 9 for the taxonomy).
  - `--limit N`: number of events to show. Default: 50.
- **Behavior:** Shows the audit log filtered as specified, most recent first.
- **Empty state:** If no events match, show empty state with an indication of which filters were applied.

#### 5.2.13 `bensdorp1 status`

- **Args:** none.
- **Flags:** none.
- **Behavior:** Diagnostic dashboard showing the overall health of the system. Sections include:
  - Data status: last fetch, last constituents update, count of constituents, count of cached price-days.
  - Backup status: last backup, location, file size, snapshots stored.
  - Database status: file size, integrity check result.
  - Operational status: last scan date, count of open positions, count of pending exit triggers.

#### 5.2.14 `bensdorp1 refresh`

- **Args:** none.
- **Flags:** none.
- **Behavior:** Forces a re-fetch and re-verification of the S&P 500 constituents list from both sources. Useful if `status` indicates a discrepancy that should re-check sooner than the next scan.
- **Output:** Summary of what changed (additions, removals, or "no changes").

#### 5.2.15 `bensdorp1 restore PATH`

- **Args:** `PATH` to a backup `.db` file.
- **Flags:** none.
- **Behavior:** Replaces the current database with the contents of the backup file. Requires two confirmations.
- **Validations:**
  - `PATH` must exist and be readable.
  - The file must be a valid SQLite database with the expected schema (verified by running an integrity check and a schema-version check).
- **Side effects:** Before replacing, the current database is automatically backed up to `backups/bensdorp1-pre-restore-{timestamp}.db`. Then the file is replaced. Logs `restore_performed` to audit (in the new state, after restore).

#### 5.2.16 `bensdorp1 validate DATE`

- **Args:** `DATE` (`YYYY-MM-DD`).
- **Flags:** none.
- **Behavior:** Stateless mode. Pretends "today" is `DATE` and shows what the buy candidates would have been on that day. Does not access the user's state (positions, cash) and does not modify anything.
- **Validations:**
  - `DATE` must be at least 1 trading day in the past.
  - `DATE` must not be more than 3 years in the past.
  - Sufficient price history must be available for the calculation (220 trading days before `DATE`).
- **Output:** The buy candidates that would have been generated on `DATE`, in the same format as `bensdorp1 last`, but with a clear "validation mode" banner at the top and no exit triggers section (validation mode is stateless).
- **Side effects:** None. The command does not write to the database.

#### 5.2.17 `bensdorp1 help [COMMAND]`

- **Args:** `COMMAND` (optional).
- **Flags:** none.
- **Behavior:**
  - Without `COMMAND`: shows the categorized command list per section 5.1.
  - With `COMMAND`: shows detailed help for that command (description, arguments, flags, validations, common errors).

---

## 6. UI/UX style guide

These 31 rules govern all user-facing output. Every command, message, table, and prompt must adhere to these rules without exception.

### 6.1 Capitalization

Sentence case throughout. Only the first letter of a sentence is capitalized.

Exceptions:
- Proper nouns: Wikipedia, Slickcharts, NYSE, S&P 500.
- Acronyms: CLI, USD, ET, OK, SKIPPED.
- Tickers: AAPL, NVDA.
- Commands in backticks: `bensdorp1 scan`.
- Literal system values: "OK", "SKIPPED", "PENDING".

### 6.2 Separators

Hierarchical:
- `===` (multiple `=`, spanning the full content width) for screen titles.
- `---` (multiple `-`, spanning the width of the section header text) for subsection headers.

Always one blank line before and after every separator.

### 6.3 Spacing

- One blank line before and after every section.
- Never two consecutive blank lines in the middle of output.
- Headers have one blank line after them before content.
- Tables and lists begin immediately under their header without an intervening blank line.

### 6.4 Key:value alignment

When multiple key:value pairs appear in the same block, all values must align vertically at the same column.

- The column is determined by the longest key in the block, plus 2 spaces after its colon.
- Every key ends with a colon.
- A single isolated key:value pair does not need artificial alignment; it appears with 2 spaces after the colon.

### 6.5 Indentation

2 spaces per level. Used for:
- Bullet lists indentation.
- Numbered list indentation.
- Sub-items under a parent.
- Indented blocks under a header.

### 6.6 List continuation lines

When a list entry has content that spans multiple lines (URLs, sub-explanations), the continuation lines align with the start of the text after the bullet or number, NOT with the bullet or number itself.

### 6.7 Numbered lists vs bullets

- Numbered lists (`1.`, `2.`, `3.`) for sequential or ordered actions (e.g., "Recommended actions:", "Next steps:").
- Bullets (`-`) for non-sequential items.

### 6.8 Tables

Minimalist style:
- Header row only, no separator between header and rows.
- No vertical or horizontal borders.
- Columns separated by 2 or more spaces (depending on content alignment).

### 6.9 Cell alignment in tables

- Text columns (Symbol, Status, Reason, etc.): left-aligned.
- Numerical columns (Close, ROC, Volume, P&L, Rank, Shares): right-aligned.
- Headers follow the same alignment as their column.

### 6.10 Numerical formatting

| Type | Format | Example |
|---|---|---|
| Price in USD | `$X,XXX.XX` | `$1,432.50` |
| Percentage | `±X.X%` (sign always explicit) | `+185.3%`, `-12.4%` |
| Volume (shares) | `X,XXX,XXX` | `52,341,200` |
| Share quantity | `X,XXX` | `23`, `1,247` |
| P&L in USD | `±$X,XXX.XX` (sign always explicit) | `+$1,432.50`, `-$543.20` |
| Days held | `N days` or `1 day` | `47 days`, `1 day` |

Thousands separator: comma (`,`). Decimal separator: period (`.`). USD convention.

Signs:
- Percentages and P&L: always show sign (`+` or `-`).
- Absolute prices and volumes: no sign (always positive).

### 6.11 Empty states

Never show an empty table. Always replace with an explicit message explaining the situation, including why it is empty when relevant.

### 6.12 Critical message structure

Every error, warning, or important info message follows this fixed structure:

```
Severity: Title statement (one sentence ending in period).

[Optional data block: key:value pairs.]

[Optional impact block (with --- subsection header).]

[Optional descriptive sentences, one per line.]

[Optional Recommended actions: numbered list.]
```

### 6.13 Severities

Four severity levels, each with a textual prefix and a color:

| Severity | Prefix | Color (ANSI) |
|---|---|---|
| Error | `Error:` | red |
| Warning | `Warning:` | yellow |
| Info | `Info:` | cyan |
| Success | `Success:` | green |

Colors are applied to the prefix. When the terminal does not support color, the prefix remains as text-only. The rest of the message uses default terminal color.

### 6.14 Tone

- Factual, non-apologetic, neutral.
- No "we", "us", "the system" — use direct or passive voice.
- No "Sorry", "Oops", or similar apologies.
- Specific actions with exact commands. No vague suggestions like "contact support".
- Name the cause when known. Avoid "Something went wrong".

### 6.15 Y/N prompts

Display: `[y/n]`.

Accepts: `y`, `Y`, `n`, `N`.

No default. Pressing Enter without input re-prompts.

### 6.16 Other prompts

- Free text: `Enter <thing>: `.
- Numbers: `<thing> in <unit>: ` (e.g., `Available cash in USD: `).
- Symbols (tickers): `Symbol: ` — accepts any case, normalizes to uppercase in the display.
- Dates: `<thing> (YYYY-MM-DD): `.

### 6.17 Confirmations for destructive actions

All of the following require an explicit confirmation prompt (per rule 6.15) before executing:

- `bensdorp1 buy`
- `bensdorp1 sell`
- `bensdorp1 sell ... --manual`
- `bensdorp1 fix`
- `bensdorp1 cash AMOUNT`
- `bensdorp1 restore`

The confirmation prompt shows a summary of what is about to happen, with affected values and computed impacts.

### 6.18 Cancellation

- Ctrl+C is always respected, at any prompt.
- When interrupted, show: `Operation aborted. No changes were made.`
- Responding `n` to a confirmation has the same effect.

### 6.19 Empty states in consultations

Commands that return a list (positions, history, audit, etc.) and have no results to display must show an explicit message, never blank output.

### 6.20 Feedback thresholds

| Operation duration | Feedback |
|---|---|
| Less than 1s | None. Silent execution. |
| 1-6s | Spinner with contextual text. |
| 6-30s | Progress bar with step, count, elapsed time. |
| More than 30s | Same as above plus estimated remaining time. |

### 6.21 Progress display layout (long operations)

```
[N/TOTAL] Description of the current step...

Progress:   ████████████░░░░░░░░  127/503  (25%)
Current:    GOOGL — additional context
Elapsed:    1m 42s
Remaining:  ~5m 12s
```

### 6.22 Spinners (short operations)

Unicode braille-style spinner cycling through frames: `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`.

### 6.23 Multi-step operations

When an operation has multiple distinct phases:
- Format each phase header as `[N/TOTAL] <description>`.
- Completed phases remain visible in the output with `done.` appended.
- Only the current phase has a dynamic progress bar.

### 6.24 Date format (output)

ISO 8601: `YYYY-MM-DD`.

### 6.25 Time format (output)

24-hour: `HH:MM`.

### 6.26 Timezone display

Always show both Eastern Time (the market timezone) and the user's local time, side by side:

```
Market closes at 16:00 ET (21:00 Lisbon)
```

The user's local timezone label is the city name (e.g., "Lisbon"). Daylight saving is automatic via `zoneinfo`.

### 6.27 Relative durations

Always show the absolute date first, then a relative duration in parentheses for quick context:

```
Last scan:    2026-05-21 (2 days ago)
Entry date:   2026-04-15 (37 days ago)
```

Relative durations follow these brackets:
- Less than 1 minute: `just now`
- 1-59 minutes: `N minutes ago`
- 1-23 hours: `N hours ago`
- 1-30 days: `N days ago`
- 1-11 months: `N months ago`
- 1+ years: `N years ago`

### 6.28 Date format (input)

All date inputs are in ISO 8601: `YYYY-MM-DD`. No other formats are accepted. Error messages on invalid input must show the expected format.

### 6.29 Color palette

ANSI standard colors, used semantically and consistently:

| Use | ANSI color |
|---|---|
| Error | red |
| Warning | yellow |
| Info | cyan |
| Success | green |
| Muted / secondary | bright_black (gray) |
| Default | terminal default |

No custom RGB colors. No variants within a severity (no bright_red vs red). Fallback to text-only when terminal does not support color.

Color is never the sole carrier of information; severities always have textual prefixes.

### 6.30 Symbols and icons

No decorative unicode icons (✓, ✗, ⚠, ℹ, etc.) in output. Severity is conveyed by textual prefix and color.

Allowed exceptions:
- Progress bar characters: `█` and `░`.
- Arrows in range descriptions when contextually useful: `2026-05-14 → 2026-05-21`.

### 6.31 Visual emphasis

No bold, italic, or underline. Plain text only, colors from the palette only.

URLs appear in plain text, no underline.

---

## 7. Specific flows

### 7.1 First-run init flow

Triggered by `bensdorp1 init`.

**Step 1 — Welcome and pre-confirmation:**

```
================================================================
bensdorp1 — System #1: Trend following on S&P 500 stocks
First-time setup
================================================================

This is a one-time setup. It will:

  1. Create local database in ~/bensdorp1/
  2. Download current S&P 500 constituents list
  3. Download 220 days of price history for all constituents
  4. Register your initial available cash

Step 3 may take 5 to 10 minutes depending on connection speed.

Continue? [y/n]: _
```

**Step 2 — Cash declaration:**

```
Available cash
--------------
Enter the amount of cash you have available for trading.
This is the amount the system will use to size new positions.

Available cash in USD: _
```

After numeric input, the system formats and confirms:

```
Available cash: $50,000.00

Confirm? [y/n]: _
```

**Step 3 — Setup execution with multi-phase progress:**

```
Setting up your system

[1/3] Fetching S&P 500 constituents...
```

Once that step completes, the line is updated to `done.` and the next phase starts:

```
[1/3] Fetching S&P 500 constituents... done.
      Source: Wikipedia
      Stocks found: 503

[2/3] Verifying against secondary source...
```

And so on. Phase 3 (price history) uses the progress bar layout from rule 6.21.

**Step 4 — Completion summary:**

```
================================================================
Setup complete
================================================================

Database created:        ~/bensdorp1/data/bensdorp1.db
Backups location:        ~/bensdorp1/backups/
Constituents:            503 stocks
History downloaded:      220 trading days
Available cash:          $50,000.00
Total time:              7m 23s

Next steps:
  1. Wait for end-of-day market close (16:00 ET / 21:00 Lisbon)
  2. Run `bensdorp1 scan` to see today's buy candidates and exit triggers
  3. Run `bensdorp1 help` to see all available commands
```

### 7.2 Daily scan flow

Triggered by `bensdorp1 scan`.

**Phase A — pre-flight checks (silent unless there is an issue):**

The system performs the following checks before running the scan:

1. Is today a trading day? If not, show `Info` message with the last trading day's scan.
2. Has the market closed (16:00 ET + 30 min buffer)? If not, show `Info` message indicating when to come back.
3. Is the constituents list older than 7 days? If so, refresh in-line as part of the scan.
4. Has the user been absent (no scan in N >= 2 trading days)? If so, trigger catch-up flow (see 7.6) before the regular scan output.

**Phase B — data fetch (progress bar visible to user):**

```
Running daily scan

[1/2] Fetching latest market data...

Progress:   ████████████░░░░░░░░  127/503  (25%)
Current:    GOOGL
Elapsed:    18s
Remaining:  ~52s
```

When done:

```
[1/2] Fetching latest market data... done.
      Constituents fetched: 503/503

[2/2] Computing signals... done.
```

**Phase C — output (the main result):**

```
================================================================
Scan for 2026-05-21
================================================================

Market regime
-------------
S&P 500 close:           5,234.50
S&P 500 SMA 200:         4,987.20
Regime:                  Bull market (close above SMA 200)

Exit triggers
-------------
Symbol  Reason            Close     Effective stop  Days held
------  ----------------  --------  --------------  ---------
AAPL    Trailing stop      $178.20         $179.50    47 days
MSFT    Initial stop       $315.00         $321.45     3 days

Both exit triggers will execute at the next market open (2026-05-22).
Confirm sells with `bensdorp1 sell SYMBOL PRICE` after execution.

Buy candidates (top 10)
-----------------------
Rank  Symbol         Close    ROC 200d  Volume (avg 20d)
   1  NVDA         $432.50   +185.3%        52,341,200
   2  TSLA         $215.20   +124.7%        98,234,100
   3  AMZN         $178.90    +98.4%        34,567,800
   4  ...

Buy candidates affordable (cash: $42,500.00)
--------------------------------------------
Rank  Symbol         Close    ROC 200d  Shares to buy
   1  NVDA         $432.50   +185.3%               98
   2  TSLA         $215.20   +124.7%              197
   3  AMZN         $178.90    +98.4%              237
   4  ...

System notes
------------
No catch-up actions needed.
Constituents list verified successfully.
```

If there are pending exit triggers from previous scans not yet confirmed:

```
Pending exit triggers from previous scans
-----------------------------------------
The following exit triggers were generated in previous scans and have not 
yet been confirmed as closed:

Symbol  Triggered on   Reason           Original stop
------  -------------  ---------------  -------------
AAPL    2026-05-18     Trailing stop          $179.50

Run `bensdorp1 sell AAPL PRICE` to confirm the exit.
```

### 7.3 Buy confirmation flow

Triggered by `bensdorp1 buy SYMBOL PRICE SHARES [--date DATE]`.

**Step 1 — Validation:** the system checks that the symbol is a valid constituent, that no open position exists for it, and that the values are valid.

**Step 2 — Off-signal warning (only if applicable):**

If the symbol was not in the top 10 buy candidates of the latest scan, before showing the confirmation prompt, show:

```
Warning: NVDA was not in the top 10 buy candidates of the latest scan.

This buy will be recorded as off-signal in the audit log.

Continue? [y/n]: _
```

If `n`, abort.

**Step 3 — Confirmation prompt:**

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

**Step 4 — Result:**

```
Success: Buy recorded.

Position opened for NVDA.
Run `bensdorp1 detail NVDA` to see the position.
```

### 7.4 Sell confirmation flow (normal and manual)

Triggered by `bensdorp1 sell SYMBOL PRICE [--date DATE] [--manual REASON]`.

**Normal sell (without --manual):**

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

**Manual sell (with --manual REASON):**

The REASON value is shown in the prompt:

```
================================================================
Confirm sell (manual)
================================================================

Symbol:           AAPL
Sell price:       $178.20
Sell value:       $8,910.00
Shares sold:      50
Entry price:      $182.50
Entry value:      $9,125.00
Days held:        47 days
Realized P&L:     -$215.00 (-2.4%)
Closing reason:   Manual
Manual reason:    Personal liquidity

Confirm sell? [y/n]: _
```

**Result:**

```
Success: Sell recorded.

Position closed for AAPL.
```

### 7.5 Fix transaction flow

Triggered by `bensdorp1 fix SYMBOL [--date DATE]`.

**Step 1 — Identification:**

```
================================================================
Fix transaction
================================================================

Last transaction for NVDA found:

Type:     Buy
Date:     2026-05-20
Price:    $432.50
Shares:   23

Is this the transaction you want to fix? [y/n]: _
```

**Step 2 — Field-by-field input:**

```
Enter new values (press Enter to keep current value):

Date    [2026-05-20]:  _
Price   [$432.50]:     _
Shares  [23]:          _
```

For sell transactions, additional fields include `Reason` (if manual sell).

**Step 3 — Confirmation:**

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
Trailing stop:     $324.38 → $324.56
P&L unrealized:    +$245.00 → +$239.25

This correction will be recorded in the audit log.
The original entry will be preserved as a historical record.

Confirm correction? [y/n]: _
```

**Step 4 — Result:**

```
Success: Transaction corrected.

The correction has been recorded in the audit log.
Run `bensdorp1 detail NVDA` to see the updated position.
```

If the user makes no changes:

```
Info: No changes detected.

Nothing to update.
```

### 7.6 Catch-up flow

Triggered automatically as part of `bensdorp1 scan` when the system detects an absence of N >= 2 trading days since the last scan.

**Phase A — silent state reconstruction:**

The system fetches the missing days' data for all open positions and updates the internal state (`highest_close`, `trailing_stop`) for each position.

**Phase B — explicit reporting:**

After data is updated, before the regular scan output, show:

```
================================================================
Catch-up summary
================================================================

You were absent for 5 trading days (2026-05-16 to 2026-05-21).

State has been updated for 2 open positions.

AAPL  Trailing stop violated on 2026-05-18 (close $178.20 < stop $179.50)
      Position remained open during your absence.
      An exit trigger from that day is still pending.

MSFT  New highest close reached on 2026-05-17 ($325.40).
      Trailing stop updated from $240.00 to $244.05.
      No exit trigger.

The following retroactive exit triggers are still pending. They will 
also appear in today's scan output below.

Symbol  Triggered on   Reason
------  -------------  ---------------
AAPL    2026-05-18     Trailing stop

Confirm sells with `bensdorp1 sell SYMBOL PRICE` as soon as you execute 
them at market open.
```

Then the regular scan output follows.

---

## 8. Behaviors and edge cases

### 8.1 Scan idempotency

If `bensdorp1 scan` is invoked more than once on the same trading day (without `--force`), the second invocation does not re-fetch data or re-compute signals. It shows the existing scan output exactly as the first invocation. The audit log is not duplicated.

To force a re-run (rare; only useful if data was corrected after the first run), use `bensdorp1 scan --force`.

### 8.2 Constituents discrepancy handling

When the cross-check between Wikipedia and Slickcharts reveals discrepancies:

| Diff size | Behavior |
|---|---|
| 0-3 stocks | Silent; use primary, log to audit. |
| 4-10 stocks | Warning shown; use primary; log to audit. |
| 11+ stocks | Buy candidates aborted; exit triggers monitoring continues; clear warning shown; log to audit. |

When buy candidates are aborted due to constituents discrepancy, the warning message is exactly:

```
Warning: S&P 500 constituents update failed.

Primary source (Wikipedia):     N1 stocks
Secondary source (Slickcharts): N2 stocks
Discrepancy:                    D stocks (max allowed: 3)

Impact on today's scan
----------------------
Exit triggers monitoring:   OK
Buy candidates generation:  SKIPPED

Buy candidates were skipped because the constituents list cannot be 
verified.
The last known good list from YYYY-MM-DD is too outdated to use safely 
for today's ranking.

Recommended actions:
  1. Visually compare sources online:
       https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
       https://www.slickcharts.com/sp500
  2. Run `bensdorp1 status` for full diagnostic
  3. Try again later (sources usually re-sync within hours)
```

### 8.3 Splits

Detected automatically by checking yfinance splits data for held positions on every scan.

When a split is detected for a held position:
1. Apply the split ratio to `shares` and `entry_price`.
2. Apply the split ratio to `highest_close`, `initial_stop`, `trailing_stop`.
3. Log `split_applied` event to audit with `before` and `after` payloads.
4. Show notification in the scan output (in the System notes section).

Example notification:

```
NVDA  Split applied: 2:1 (effective 2026-05-19)
      Shares: 23 → 46
      Entry price: $432.50 → $216.25
```

### 8.4 Stocks delisted from S&P 500

If a held position's symbol is no longer in the S&P 500 constituents list:

1. The position is kept open. Continue normal stop monitoring.
2. The symbol is excluded from buy candidates generation.
3. The exit trigger output (when triggered) includes a note that the stock is delisted from the index.
4. Log `position_delisted_from_index` event to audit when first detected.

### 8.5 Holidays and weekends

Detected via `pandas_market_calendars`.

- `bensdorp1 scan` invoked on a non-trading day shows the most recent scan with a note that no new scan is needed today.
- "200 trading days ago" is computed using the trading calendar.
- "Next market open" is the next trading day, computed via the calendar.

### 8.6 Persistent exit triggers

Once an exit trigger is generated for a position, it persists across daily scans until the position is confirmed as closed (via `bensdorp1 sell`) or marked manually closed.

In every subsequent scan output, pending exit triggers are shown in a dedicated section (separate from "today's new exit triggers") with the date of original trigger.

If a stop was triggered on a past day and the close has since recovered above the stop, the trigger still persists (Bensdorp's rule: once triggered, exit at next open).

### 8.7 Multiple positions in the same symbol over time

Allowed sequentially. A position is created on `buy` and is the only open position for that symbol. When the position is closed, the symbol becomes available again. A new buy on the same symbol later creates a new, independent position with its own ID, history, and audit trail.

The `positions` table holds all positions, both open and closed. The `bensdorp1 detail SYMBOL` command only shows the currently open position; closed positions can be inspected via `bensdorp1 audit --symbol SYMBOL`.

### 8.8 Delayed transaction confirmations

If the user runs `bensdorp1 buy NVDA PRICE SHARES` two days after the corresponding scan signal, the transaction is accepted but linked to the original scan signal. The audit records the delay (timestamp of the scan vs timestamp of confirmation).

If the user uses `--date DATE` to backdate a transaction to an earlier date, the system records that date as the transaction date, validates that the date is in the past and within available history, and accepts.

### 8.9 Catch-up event templates

Thirteen possible events during catch-up. Each has a template with fixed wording.

**Per-position events:**

1. **Initial stop violated**
   ```
   {SYMBOL}  Initial stop violated on {DATE} (close ${CLOSE} < stop ${STOP}).
             Position remained open during your absence.
             An exit trigger from that day is still pending.
   ```

2. **Trailing stop violated**
   ```
   {SYMBOL}  Trailing stop violated on {DATE} (close ${CLOSE} < stop ${STOP}).
             Position remained open during your absence.
             An exit trigger from that day is still pending.
   ```

3. **New highest close reached**
   ```
   {SYMBOL}  New highest close reached on {DATE} (${CLOSE}).
             Trailing stop updated from ${OLD_STOP} to ${NEW_STOP}.
             No exit trigger.
   ```

4. **Stock removed from S&P 500**
   ```
   {SYMBOL}  Removed from S&P 500 on {DATE}.
             Position remains open. Stop monitoring continues.
   ```

5. **Stock split occurred**
   ```
   {SYMBOL}  Stock split {RATIO} on {DATE}.
             Shares adjusted: {OLD_SHARES} → {NEW_SHARES}.
             Entry price adjusted: ${OLD_PRICE} → ${NEW_PRICE}.
   ```

6. **Stock had dividend**
   ```
   {SYMBOL}  Dividend paid on {DATE}: ${AMOUNT} per share.
             No impact on strategy (using adjusted prices).
   ```

7. **Stock delisted entirely**
   ```
   {SYMBOL}  Delisted from the market on {DATE}.
             Position cannot be tracked further.
             Manual action required: close position via 
             `bensdorp1 sell {SYMBOL} PRICE --manual "Delisted"`.
   ```

**Market regime events:**

8. **Market regime changed: bull to bear**
   ```
   Market regime changed on {DATE}: bull → bear.
   S&P 500 close fell below SMA 200.
   No new positions can be entered until regime returns to bull.
   ```

9. **Market regime changed: bear to bull**
   ```
   Market regime changed on {DATE}: bear → bull.
   S&P 500 close rose above SMA 200.
   Buy candidates resume.
   ```

**System events:**

10. **Constituents list updated**
    ```
    S&P 500 constituents updated on {DATE}: +{N_ADDED} added, -{N_REMOVED} removed.
    ```

11. **Data fetch failure on specific days**
    ```
    Data fetch failed for {N_DAYS} days during your absence: {DATES}.
    State may be incomplete for these days. Run `bensdorp1 refresh` to retry.
    ```

12. **Trading holidays detected**
    ```
    {N} trading holiday(s) occurred during your absence: {DATES}.
    No market activity on these days.
    ```

13. **Position with multiple events (composite)**
    ```
    {SYMBOL}  Multiple events during your absence:
              - {EVENT_1}
              - {EVENT_2}
              - {EVENT_3}
    ```

All templates use the standard formatting from section 6 (key:value alignment, sentence per line, etc.).

---

## 9. Audit log specification

### 9.1 Event types

Every event in the audit log has a `event_type`. The complete taxonomy:

| Event type | Description |
|---|---|
| `system_initialized` | The `init` command completed successfully. |
| `scan_performed` | A daily scan was run. |
| `buy_confirmed` | A buy transaction was recorded. |
| `sell_confirmed` | A normal sell was recorded. |
| `sell_manual` | A manual sell was recorded. |
| `transaction_corrected` | A `fix` command was executed. |
| `cash_updated` | The cash value was changed. |
| `constituents_updated` | The S&P 500 list changed. |
| `constituents_discrepancy` | A discrepancy was detected between sources. |
| `split_applied` | A stock split was applied to a held position. |
| `position_delisted_from_index` | A held position's symbol was removed from S&P 500. |
| `regime_change_bull_to_bear` | Market regime change detected. |
| `regime_change_bear_to_bull` | Market regime change detected. |
| `data_fetch_failed` | A specific data fetch attempt failed. |
| `catch_up_performed` | A catch-up reconstruction was completed. |
| `restore_performed` | A restore from backup was performed. |
| `position_closed_manual` | A position was closed via `--manual`. |

### 9.2 What is recorded per event type

Every audit event row has the columns from `audit_events` (see section 3.4). The `data_json` column contains a structured payload specific to each event type. All amounts are stored unrounded to maintain precision.

**For `buy_confirmed`:**
```json
{
  "symbol": "NVDA",
  "price": 432.50,
  "shares": 23,
  "trade_date": "2026-05-22",
  "buy_value": 9947.50,
  "signal_scan_id": 142,
  "signal_rank": 1,
  "off_signal": false
}
```

**For `sell_confirmed`:**
```json
{
  "symbol": "AAPL",
  "price": 178.20,
  "shares": 50,
  "trade_date": "2026-05-22",
  "sell_value": 8910.00,
  "entry_price": 182.50,
  "entry_value": 9125.00,
  "realized_pnl": -215.00,
  "realized_pnl_pct": -0.024,
  "days_held": 47,
  "reason": "trailing_stop",
  "trigger_scan_id": 142
}
```

**For `transaction_corrected`:**
```json
{
  "target_event_id": 234,
  "target_event_type": "buy_confirmed",
  "before": { ... },
  "after": { ... }
}
```

**For `scan_performed`:**
```json
{
  "scan_id": 142,
  "scan_date": "2026-05-21",
  "regime": "bull",
  "spx_close": 5234.50,
  "spx_sma_200": 4987.20,
  "constituents_count": 503,
  "buy_candidates_count": 10,
  "exit_triggers_count": 2,
  "constituents_freshness_days": 3
}
```

(Detailed payloads for the remaining event types should follow the same pattern: include all relevant context fields.)

### 9.3 Audit query semantics

The `bensdorp1 audit` command applies filters with AND logic. Results are sorted by `event_timestamp` descending (most recent first).

Display format:

```
================================================================
Audit log
================================================================

Filters: --symbol NVDA --since 2026-05-01

Timestamp                  Event type           Symbol  Summary
-------------------------  -------------------  ------  -------
2026-05-22 09:15:23 ET     buy_confirmed        NVDA    Buy 23 shares at $432.50
2026-05-21 22:30:01 ET     scan_performed               Scan for 2026-05-21 (regime: bull)
2026-05-20 22:30:15 ET     scan_performed               Scan for 2026-05-20 (regime: bull)

Showing 3 events. Use `--limit N` to see more.
```

Each row's "Summary" is a one-line human-readable description derived from the event type and its payload.

---

## 10. Backup and recovery

### 10.1 Automatic backup behavior

After every operation that changes state, the system automatically:

1. Creates a consistent copy of `data/bensdorp1.db` to `backups/bensdorp1-latest.db` (overwriting the previous latest).
2. Creates a timestamped snapshot at `backups/bensdorp1-{YYYY-MM-DD-HHMMSS}.db`.

Operations that trigger automatic backup:
- `init` (creates the initial state).
- `buy`, `sell`, `fix` (confirmed transactions).
- `cash AMOUNT` (cash update).
- `scan` (daily state changes, including catch-up).
- `restore` (creates a pre-restore backup).
- Automatic split application (during scan).
- Automatic constituents update (during scan).

The backup is created using SQLite's online backup API to ensure consistency without blocking ongoing reads.

### 10.2 File structure

```
~/bensdorp1/backups/
├── bensdorp1-latest.db                   # always the most recent, overwritten
├── bensdorp1-2026-05-20-093015.db        # historical snapshot, never deleted
├── bensdorp1-2026-05-21-093020.db
├── bensdorp1-2026-05-21-184530.db
├── bensdorp1-pre-restore-2026-05-22-101205.db  # pre-restore backup
└── ...
```

Historical snapshots are never deleted automatically. The user can manually delete old ones if disk space is a concern (documented in README).

### 10.3 Restore process

Triggered by `bensdorp1 restore PATH`.

**Step 1 — validation of the backup file:**

```
================================================================
Restore from backup
================================================================

Backup file:           {PATH}
File size:             12.4 MB
Created:               2026-05-20 09:30:15
Schema version:        1
Integrity check:       OK
```

**Step 2 — first confirmation (informational):**

```
This will replace your current state with the backup contents.

Before replacing, a backup of the current state will be created at:
~/bensdorp1/backups/bensdorp1-pre-restore-{timestamp}.db

Proceed? [y/n]: _
```

**Step 3 — second confirmation (destructive action):**

```
Are you absolutely sure? This cannot be undone. [y/n]: _
```

**Step 4 — execution and result:**

```
Success: Restore completed.

Current state replaced with backup from 2026-05-20 09:30:15.
The previous state was backed up to:
~/bensdorp1/backups/bensdorp1-pre-restore-2026-05-22-101205.db

Run `bensdorp1 status` to verify the restored state.
```

The restore action is logged to the audit log in the new (restored) state.

---

## 11. Testing and validation strategy

### 11.1 Automated testing

The project must achieve and maintain:

- Unit test coverage > 95% on strategy logic modules (`strategy/`).
- Unit test coverage > 90% on all source modules.
- All tests must pass on every commit via CI.

**Unit tests** (`tests/unit/`):
- Pure functions in `strategy/` (indicators, filters, ranking, stops, sizing).
- Database queries (`db/queries.py`).
- Audit event creation.
- Data parsing (constituents, prices).
- Date and timezone utilities.

**Property-based tests** (`tests/property/`):
- Invariants such as:
  - If SPX is below its SMA 200, the buy candidates list is always empty.
  - Trailing stop is always <= 75% of the highest close since entry.
  - Effective stop is always >= the initial stop and >= the trailing stop.
  - Number of buy candidates never exceeds 10.
  - Ranking is always monotonically descending by ROC.
  - All confirmed buys lead to exactly one open position; all confirmed sells close exactly one position.

**Snapshot tests** (`tests/snapshot/`):
- Capture exact output of every command for representative inputs.
- Stored in versioned text files in `tests/snapshot/snapshots/`.
- Re-generated with explicit user action when intentional output changes occur.

**Integration tests** (`tests/integration/`):
- End-to-end flows from CLI invocation to database state, using mocked external services (yfinance, Wikipedia, Slickcharts).

### 11.2 Human validation procedures

Claude Code must explicitly request human validation only when judgment is required. For each human validation point, Claude Code must provide step-by-step instructions in layman terms.

Required human validation checkpoints:

1. **First-run UX validation (after section 7.1 implementation):**
   - "Run `bensdorp1 init`. Walk through the setup. Confirm that the screens look correct and the flow feels natural. Report any text, layout, or behavior issues."

2. **Daily scan output validation (after section 7.2 implementation):**
   - "Run `bensdorp1 scan` on a normal trading day (after market close). Inspect the output. Confirm that all sections are present, formatted correctly per the style guide, and contain plausible values. Compare 2-3 candidate stocks against Yahoo Finance manually to verify the ROC and SMA calculations."

3. **Transaction flow validation (after section 7.3, 7.4, 7.5 implementation):**
   - "Record a fake buy, then a fake sell. Confirm the prompts, the audit log entries, and that the position appears in `portfolio` between buy and sell."

4. **Style guide visual validation:**
   - "Browse all commands and inspect their output. Confirm consistency with the style guide rules."

For every checkpoint, Claude Code provides:
- The exact commands to run.
- What to look at in the output.
- Specific things to check.
- A simple yes/no for the outcome.

### 11.3 Validation mode

The `bensdorp1 validate DATE` command (specified in section 5.2.16) provides a stateless mode for manual verification of the implementation. The user runs the command for a chosen past date, examines the output, and compares manually (with the help of an external AI or spreadsheet) against the expected calculations from the book's rules.

This is a manual, optional exercise to gain confidence before committing real capital. It is documented in the README.

### 11.4 External cross-check

After v1 is complete, the user may translate the strategy rules to C# and run them in the TuringTrader backtest engine (existing open-source tool with prior Bensdorp implementations). Comparing TuringTrader's backtest results to the strategy's documented behavior gives additional confidence about the strategy itself (though not directly about the implementation).

This is documented in the README as a recommended (but optional) post-v1 validation step. The Claude Code implementation does not need to integrate with TuringTrader.

---

## 12. GitHub repository specification

### 12.1 Required files at repository root

| File | Content |
|---|---|
| `README.md` | Project description, installation instructions, basic usage, link to docs, badge for CI status, badge for license, clear statement that contributions are not accepted. |
| `LICENSE` | MIT License, with the current year and copyright holder. |
| `CONTRIBUTING.md` | Clear, polite statement that no contributions are accepted: no pull requests, no feature requests, no issues. Encourages forks for personal use. |
| `CODE_OF_CONDUCT.md` | Standard Contributor Covenant. Optional given no contributions, but good practice. |
| `SECURITY.md` | Statement that this is a personal project, vulnerabilities should not be reported publicly, with link to private contact (or statement that no support is offered). |
| `CHANGELOG.md` | Initially blank or with a single "v1.0.0 — Initial release" entry. Maintained going forward only for bug-fix releases within v1. |
| `.gitignore` | Standard Python `.gitignore` plus exclusions for `~/bensdorp1/` paths and local config. |
| `pyproject.toml` | Package configuration, dependencies, build system, console script entry point. |

### 12.2 `.github/` directory

| File | Content |
|---|---|
| `.github/ISSUE_TEMPLATE/config.yml` | Disables issue creation (`blank_issues_enabled: false` with no templates). |
| `.github/PULL_REQUEST_TEMPLATE.md` | Auto-closing message stating PRs will be closed. |
| `.github/workflows/ci.yml` | Runs tests, lint, type check on every push and PR. |
| `.github/workflows/close-pr.yml` | Workflow that auto-closes any PR with a polite message referring to CONTRIBUTING.md. |

### 12.3 Repository settings

Configured via the GitHub web interface or `gh` CLI:

| Setting | Value |
|---|---|
| Visibility | Public |
| Issues | Disabled |
| Discussions | Disabled |
| Wiki | Disabled |
| Projects | Disabled |
| Pull requests | Cannot be disabled in GitHub UI for public repos; auto-closed via workflow per 12.2 |
| Sponsorships | Disabled |
| Branch protection | `main` branch protected: requires CI to pass for any merge. |

### 12.4 Branch strategy

- `main` is the default and only long-lived branch.
- Feature work happens on short-lived feature branches (`feature/<phase>-<description>`), opened by the developer (Claude Code), merged to `main` after CI passes.
- No release branches. Tags are used for versioning.

### 12.5 Release process

For v1:
- Tag the final commit as `v1.0.0`.
- Create a GitHub release with `v1.0.0` as the title, with the full changelog as the description.
- The release is the canonical version. Bug-fix releases within v1 use `v1.0.1`, `v1.0.2`, etc.

---

## 13. Development methodology

### 13.1 GSD phases recommended decomposition

Claude Code, via GSD, should decompose the project into the following phases. Each phase should produce a working, tested increment of the system.

| Phase | Scope |
|---|---|
| **Phase 1: Project skeleton and tooling** | Repository setup (section 12), `pyproject.toml`, base folder structure, CI pipeline, linting, testing infrastructure. No business logic yet. |
| **Phase 2: Database and migrations** | SQLite schema (section 3.4), migration setup, audit event taxonomy (section 9). |
| **Phase 3: Data sources** | Constituents fetch + cross-check, price data fetch via yfinance, calendar integration, timezone handling (section 4). |
| **Phase 4: Strategy logic** | Indicators, filters, ranking, stop calculations, position sizing (section 2). All as pure functions with full unit test coverage and property-based tests. |
| **Phase 5: UI components** | Style guide implementation: tables, prompts, progress bars, message templates, color palette, all formatters (section 6). |
| **Phase 6: First-run init** | The `init` command and its flow (section 7.1). End-to-end testable. |
| **Phase 7: Scan command** | The `scan` command, its flow (section 7.2), and the dependencies on phases 3, 4, 5. |
| **Phase 8: Confirmation commands** | `buy`, `sell`, `fix` and their flows (sections 7.3, 7.4, 7.5). |
| **Phase 9: Consultation commands** | `portfolio`, `detail`, `last`, `history`, `audit`, `cash`, `config`. |
| **Phase 10: System commands** | `status`, `refresh`, `restore`. |
| **Phase 11: Catch-up logic** | Catch-up flow (section 7.6) and the 13 event templates (section 8.9). |
| **Phase 12: Validation mode** | The `validate` command (section 5.2.16). |
| **Phase 13: Edge cases and hardening** | Idempotency, splits, delisting, persistent triggers, delayed transactions (section 8). Comprehensive snapshot and integration tests. |
| **Phase 14: Documentation and finalization** | README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG. v1.0.0 tag and release. |

### 13.2 Per-phase self-validation

At the end of every phase, Claude Code must:

- Run all tests and confirm 100% pass rate.
- Run linting and type checking with zero errors.
- Run the relevant snapshot tests and confirm no unexpected diffs.
- Update the CHANGELOG (internal, pre-release notes file) with a phase-completion entry.

### 13.3 Human validation checkpoints

Claude Code must request human validation only at phase boundaries that involve user-visible behavior changes. Required checkpoints:

- After **Phase 6**: human validates the `init` flow visually.
- After **Phase 7**: human validates a daily scan output.
- After **Phase 8**: human validates buy/sell/fix flows.
- After **Phase 9**: human validates consultation commands.
- After **Phase 11**: human validates catch-up flow (a contrived absence scenario).
- After **Phase 14**: final human validation of the complete v1.

For all other phases, Claude Code's automated tests are sufficient and no human validation is required.

### 13.4 Definition of done for v1

v1 is considered done when ALL of the following are true:

- All 17 commands implemented and working as specified.
- Test coverage targets met (95% on strategy, 90% overall).
- All snapshot tests pass.
- All 31 style guide rules verifiably applied.
- All 13 catch-up event templates implemented.
- All audit event types implemented.
- Repository setup matches section 12 exactly.
- README provides clear installation and usage instructions for a non-coder.
- Tag `v1.0.0` published as a GitHub release.
- Human validation checkpoints completed.

After v1.0.0, the project enters maintenance-only mode. Only critical bug fixes will be applied. No new features.

---

## 14. Glossary

| Term | Definition |
|---|---|
| **Buy candidate** | A stock that passes all filters and setup conditions and is among the top 10 ranked by ROC 200. Source of potential buy signals. |
| **Exit trigger** | An open position whose daily close has hit or breached its effective stop. Generates a recommendation to sell at the next market open. |
| **Effective stop** | `max(initial_stop, trailing_stop)`. The actual stop level used for evaluating exit triggers. |
| **Initial stop** | `entry_close * 0.93`. Set on entry day, never changes. |
| **Trailing stop** | `highest_close_since_entry * 0.75`. Updated daily as the highest close is updated. |
| **Highest close since entry** | The maximum daily close from the day after entry up to (and including) the most recent trading day. |
| **ROC 200** | Rate of change over 200 trading days: `(close_today / close_t-200) - 1`. The ranking metric. |
| **SMA 200** | 200-day simple moving average of close prices. Used as the regime filter for the S&P 500 index. |
| **Regime** | The market state, derived from whether SPX close is above (bull) or below (bear) its SMA 200. |
| **Liquidity filter** | Restriction to the top 25% of S&P 500 constituents by 20-day average volume. |
| **Position size** | 10% of declared available cash, in USD. |
| **Catch-up** | The process of reconstructing state after the user has been absent for multiple trading days. |
| **Off-signal buy** | A buy confirmation for a stock that was not in the top 10 buy candidates of the latest scan. Allowed but logged distinctly. |
| **Persistent exit trigger** | An exit trigger from a past scan that has not yet been confirmed by the user as closed. Continues to appear in subsequent scans. |
| **Manual close** | Closing a position via `bensdorp1 sell ... --manual REASON`, indicating an extraordinary reason outside the strategy rules. |
| **Validation mode** | Running `bensdorp1 validate DATE` in a stateless way to verify implementation correctness without modifying the system state. |
| **Scan** | The daily run of the screening logic. One scan per trading day. |
| **All-in / All-out** | The strategy semantics that positions are entered with full size and exited with full size; no partial executions. |

---

End of specification.
