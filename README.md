# bensdorp1

[![CI](https://github.com/davidbarros2/bensdorp-1/actions/workflows/ci.yml/badge.svg)](https://github.com/davidbarros2/bensdorp-1/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A single-user command-line tool for screening and monitoring stock positions based on **System #1 (Trend Following on S&P 500 Stocks)** from Laurens Bensdorp's *Trading Retirement Accounts*.

Every trading day it shows exactly which open positions triggered a stop and which stocks are the top buy candidates — so decision time is under 5 minutes. **It does not execute trades.** All orders are placed manually via your broker; the CLI records confirmations and maintains state.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
# Clone and install
git clone https://github.com/davidbarros2/bensdorp-1.git
cd bensdorp-1
uv sync

# First-time setup (creates database, fetches constituents, downloads price history)
uv run bensdorp1 init
```

## Usage

```
bensdorp1 <command> [options]
```

| Command | Description |
|---------|-------------|
| `init` | First-run setup: database, constituents, 220-day price history, cash |
| `scan [--force]` | Daily end-of-day screening: exit triggers and buy candidates |
| `last` | Show the most recent scan output |
| `history` | Compact table of past scans (`--limit N`, `--since DATE`) |
| `buy SYMBOL PRICE SHARES` | Confirm a buy; creates an open position |
| `sell SYMBOL PRICE` | Confirm a sell; closes a position |
| `fix SYMBOL` | Interactive correction of a recorded transaction |
| `portfolio` | All open positions with stop levels and unrealized P&L |
| `detail SYMBOL` | Full history of a single open position |
| `cash [AMOUNT]` | Show or update available cash |
| `config` | Show current configuration |
| `audit` | Query the structured audit log |
| `status` | System diagnostics dashboard |
| `refresh` | Force-refresh S&P 500 constituents |
| `restore PATH` | Replace the database from a backup file |
| `validate DATE` | Stateless historical verification (no state changes) |
| `help [COMMAND]` | Command reference |

## Strategy

System #1 is a long-only trend-following strategy applied to S&P 500 constituents:

- **Regime filter** — buy candidates only generated when SPX close > SPX SMA 200
- **Liquidity filter** — restricted to the top 25% of the S&P 500 by 20-day average volume
- **Momentum filter** — stock close today > stock close 200 trading days ago
- **Ranking** — top 10 candidates by ROC 200 (rate of change over 200 trading days)
- **Position sizing** — 10% of declared available cash; shares = floor(size / prev close)
- **Initial stop** — entry close × 0.93 (set once, never changes)
- **Trailing stop** — highest close since the day after entry × 0.75 (updated daily)
- **Effective stop** — max(initial stop, trailing stop); triggered when close ≤ effective stop
- **Max positions** — 10 simultaneous open positions

## Data

- S&P 500 constituents: Wikipedia (primary) + Slickcharts (cross-check); cached 7 days
- Price data: [yfinance](https://github.com/ranaroussi/yfinance) with adjusted close (`auto_adjust=True`)
- Market calendar: [pandas-market-calendars](https://github.com/rsheftel/pandas_market_calendars) (NYSE)

## Data directory

Data is stored at `~/bensdorp1/` by default. Override with `BENSDORP1_HOME`.

Timezone display shows Eastern Time (ET) and Lisbon side by side. Override the display timezone with `BENSDORP1_USER_TZ`.

## Contributing

This is a personal, single-user tool. No contributions are accepted. Issues and pull requests are disabled.

## License

[MIT](LICENSE)
