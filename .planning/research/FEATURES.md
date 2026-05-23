# Feature Landscape

**Domain:** Personal-use systematic trading signal CLI (single-strategy, single-user, no automation)
**Researched:** 2026-05-23
**Strategy reference:** Laurens Bensdorp System #1 — Trend Following on S&P 500 Stocks

---

## Table Stakes

Features a user would immediately notice as missing. Without these the tool is unusable or
untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Daily scan output: exit triggers first | Users execute sells before placing new buys. Exit triggers must appear before buy candidates — wrong order forces re-reading. | Low | Always render "Positions Triggered" section above "Buy Candidates" |
| Stop levels per open position (both initial and trailing) | A trailing stop changes every day. If the user cannot instantly read the current effective stop they cannot verify it against their broker. | Low | Show initial stop, trailing stop, effective stop (the max), and the % distance to effective stop |
| Position entry metadata | User must be able to confirm the right trade is tracked. Entry date, entry price, shares, and position size in USD are non-negotiable. | Low | Displayed in `portfolio` and `detail` commands |
| Regime filter status at top of scan | The most important single bit of information: is the market in a buy regime? If SPX < SMA 200, no buy candidates are generated. If this is not shown prominently, users will be confused by an empty candidates list. | Low | Show "Regime: ON (SPX 5,432 > SMA 200 5,218)" or "Regime: OFF" as first line of scan output |
| Cash balance before position sizing | User needs to know how much cash the tool thinks they have before trusting the share calculations. | Low | Show available cash and the 10% position size threshold before the candidates table |
| Scan guard with clear message | Refuse scan before 16:30 ET with a clear explanation (market not closed). Silent refusal or cryptic error loses user trust. | Low | "Market data not final: scan is available after 16:30 ET (21:30 Lisbon). Current time: 14:22 ET." |
| Transaction confirmation round-trip | The tool records what the user tells it, not what it calculated. Confirm back: "Recorded: BUY AAPL 12 shares @ $187.50 on 2024-03-15. Effective stop set at $174.38." | Low | After `buy` and `sell` commands |
| Last-scan replay | Users often run the scan, go place trades, then want to re-read the output without re-running the whole computation. Essential for a sub-5-minute workflow. | Low | `last` command shows the most recent scan output verbatim |
| Structured audit log | Systematic traders keep records. If a dispute arises ("did I miss that stop trigger?") the audit log is the ground truth. Must be queryable. | Medium | Append-only SQLite rows; `audit` command with date and event-type filters |
| Automatic state backup | Single user, single machine, SQLite file. If it corrupts, everything is lost. Backup after every write prevents catastrophe. | Low | Timestamped copies in ~/bensdorp1/backups/; never auto-deleted |
| `status` diagnostics | "Is the data fresh? When did I last scan? How many days of price history do I have?" — needed any time something feels wrong. | Low | Last scan date, last constituents refresh, price data staleness, DB size, backup count |
| Split detection on held positions | Adjusted-close prices from yfinance handle history correctly, but the shares count recorded at entry is raw. A 3-for-1 split makes the stored share count wrong. The tool must detect and correct this. | Medium | Compare stored shares * entry_price against current market cap equivalent; alert user to verify |
| `fix` command for entry correction | Users mistype prices and share counts. Without a correction mechanism the entire position history becomes untrustworthy. | Low | Interactive re-entry of price, shares, or date for a recorded transaction |
| Help per command | Non-coder user. `help buy` must show argument order and an example, not just a usage string. | Low | `help [COMMAND]` with a worked example for each command |

---

## Differentiators

These separate a good implementation from a bare-minimum one. Users may not name them but they
notice their presence.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dual timezone display on every timestamp | The user is in Lisbon. Scan runs on US market time. Showing "16:45 ET / 21:45 Lisbon" on every time-sensitive output eliminates timezone arithmetic errors on the user's part. | Low | Single helper function applied consistently everywhere |
| Catch-up logic with explicit event log | If the user misses two or more trading days, the tool reconstructs what *would* have triggered on each missed day and records those events as catch-up entries in the audit log with clear labeling ("catch-up for 2024-03-14"). Prevents state drift. | High | 13 defined catch-up event templates; each generates audit entries but no live scan output |
| `validate DATE` stateless verification | User can run `validate 2024-01-15` to check what the tool *would have* produced on that date using only historical data, without touching any state. Essential for building confidence that the strategy logic is correct. | High | Completely stateless: reads price history, applies all filters, shows what the scan output would have been |
| Scan time elapsed + data freshness indicator | "Scan completed in 4.2s. Price data as of 2024-03-15 16:00 ET." Tells the user data is from today's close, not yesterday's. | Low | Append to every scan completion line |
| `history` with compact tabular format | Systematic traders review patterns over weeks. A compact history view (one row per scan: date, regime, exit count, buy count) lets the user see whether the strategy is active or dormant. | Low | `history --limit 20` default; `--since 2024-01-01` for range |
| `detail SYMBOL` per-position deep view | Full timeline: entry, every stop update, any corrections, current stop levels, unrealized P&L. Turns the tool from a scanner into a personal trading record. | Medium | Reconstructed from audit log events for that symbol |
| Position count vs maximum in scan header | "Positions: 7/10 open. Slots available: 3." Tells user immediately whether buying is constrained by the 10-position maximum before they read the candidates list. | Low | Shown before buy candidates section |
| Explicit "no triggers today" and "no candidates today" messages | Silence is ambiguous. An empty result set could mean no triggers or a bug. Explicit "No exit triggers today." and "No buy candidates (regime filter active / no stocks pass momentum filter)." eliminate ambiguity. | Low | Always render section headers even when empty, with reason |
| `cash` history via audit log | Every cash update is a logged event with timestamp and optional note. `cash` with no arguments shows current balance and last three changes. Prevents "where did my cash go" confusion after buys and sells. | Low | Cash changes are audit events; `cash` reads from log, not a separate table |
| Constituents cross-check warning | Wikipedia and Slickcharts sometimes disagree. If the cross-check finds a discrepancy, warn once at scan time: "Constituents: 502 symbols (1 discrepancy detected — run `refresh` to investigate)." Builds trust in the universe. | Medium | Flag in `status` and as a warning prefix in scan output |
| NO_COLOR compliance | Piping output to files, log rotation, or color-blind use. Respecting `NO_COLOR` env var costs nothing and signals professional implementation quality. | Low | Check `NO_COLOR` in env before any ANSI output; `--no-color` flag as override |
| Spinner / progress bar calibrated to operation length | Silent on fast ops (<1s), spinner on medium (1-6s), progress bar with ETA on long (>6s). A user waiting 45 seconds for initial price history download with no feedback will think the tool crashed. | Low | Implemented once in a shared output helper, used everywhere |

---

## Anti-Features

Things that could plausibly creep into scope but must not. Each one has a stated rejection reason.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Cumulative P&L and closed positions history | Out of spec explicitly. Adds complexity and misleads users into performance analysis that the tool is not designed for. Closed trade data is incomplete (no commission, no tax). | The audit log records all buys and sells. A user who wants P&L can export the audit log and compute it externally. |
| Broker integration or order sending | Makes the tool a trading bot, creates regulatory surface area, and destroys the intentional friction of manual confirmation. | The tool generates signals; the human makes the decision. |
| Backtest engine | The `validate` command is stateless point-in-time verification only. A full backtest requires portfolio simulation, position overlap logic, and commission modeling — a different product entirely. | If the user wants a backtest, TuringTrader's open-source implementation of the strategy already exists. |
| Alerts / push notifications | The user checks the tool once per day. Push alerts encourage over-monitoring and create a dependency on a notification infrastructure. | The daily workflow is: run scan, read output, act. No alerts needed. |
| Interactive position entry wizard | Wizards feel helpful but they accumulate state across steps and break on interruption. For a CLI, explicit positional arguments are more reliable and scriptable. | `buy SYMBOL PRICE SHARES [--date D]` is explicit and correctable via `fix`. |
| Configurable strategies or parameter overrides | System #1 has fixed parameters. Allowing the user to change 0.93 or 0.75 invites mistakes. The strategy is a law, not a preference. | Hard-code all strategy constants with comments citing the book page/rule. |
| CSV or Excel export of any kind | Adds an output surface to maintain, creates stale file confusion ("which export is current?"), and is never as useful as expected. | The audit log and SQLite DB are the exportable artifacts. Power users can query SQLite directly. |
| Web UI or dashboard | Out of spec. Adds authentication, serving, and maintenance overhead. | CLI only. The output format should be clean enough to screenshot. |
| Multi-account or portfolio tracking | One cash pool, one position set. Multiple accounts would require routing logic and position attribution that the strategy doesn't support. | Single-account, declared cash only. |
| Partial fill handling | The strategy is all-in / all-out. Partial fills imply fractional positions, which require averaging logic and complicate stop calculations. | Reject partial fills at the CLI level: shares must be a whole integer, and the tool assumes the fill is complete. |
| Sector / industry concentration warnings | Not part of System #1 rules. Adding risk overlays that are not in the strategy creates confusion about what the tool is enforcing. | Trust the strategy's built-in diversification via 10-position maximum and momentum ranking. |
| Commission tracking | Complicates position sizing and P&L calculations without adding actionable insight for a retirement account trader. | Out of scope. User declares gross cash. |
| "Smart" suggestions or deviation from rules | Any feature that says "you might want to consider..." or "the strategy would suggest..." but is not part of the mechanical rules is a liability. Systematic traders follow rules, they don't negotiate with them. | Output facts (what triggered, what ranks), not opinions. |
| Data retention policy or log pruning | Never auto-delete backups or trim the audit log. The cost of storage is zero. The cost of missing an audit entry when something goes wrong is high. | Append-only, forever. |

---

## Feature Dependencies

```
init
  -> scan (requires price history and constituents)
    -> buy (requires a valid scan to have been run, or --date override)
    -> sell (requires an open position)
      -> fix (requires a recorded transaction)

portfolio
  -> detail SYMBOL (requires open position)

catch-up logic
  -> scan (triggered when last scan > 1 trading day ago)

validate DATE
  -> independent of all state (reads price history only)

audit [filters]
  -> populated by every state-changing command
```

---

## Day-to-Day Workflow Features (What the User Actually Does)

The spec's core value is "less than 5 minutes of decision time per trading day." The features
that deliver this are:

1. **Run `scan`.** Output appears in under 10 seconds for a normal day (no initial download).
2. **Read exit triggers first.** Zero or more positions show as triggered with their effective stop and today's close.
3. **Read regime status.** If OFF, stop reading — no buys today.
4. **Read cash and slot count.** Know immediately whether buying is possible and how many positions are open.
5. **Read buy candidates.** Ranked table, top 10 by ROC 200, with last close and suggested shares.
6. **Place trades at broker, then confirm with `buy`/`sell`.** Tool validates the symbol is open/closed correctly and echoes confirmation.
7. **Done.** Everything else (`last`, `portfolio`, `detail`, `history`) is reference, not daily workflow.

Features that interrupt this flow are anti-features. The tool should never ask questions in the
middle of `scan`.

---

## MVP Recommendation

Given the spec defines a complete v1 with all 17 commands, the MVP is v1 itself. However, the
natural implementation priority based on dependency and daily-value is:

**Build first (core loop):**
1. `init` — cannot use the tool without it
2. `scan` — the entire value proposition
3. `buy` / `sell` — confirms the user's trades
4. `portfolio` — verifies state matches broker
5. `last` — enables re-reading scan output

**Build second (trust and recovery):**
6. `fix` — corrects entry errors
7. `audit` — queries the event record
8. `detail SYMBOL` — per-position timeline
9. `cash` — cash management
10. `history` — scan history overview

**Build third (operational hygiene):**
11. `status` — diagnostics
12. `refresh` — force constituents update
13. `validate DATE` — stateless verification
14. `restore PATH` — database recovery
15. `config` — show configuration
16. `help [COMMAND]` — per-command help
17. Catch-up logic — absence handling

**Defer indefinitely:** Everything listed in Anti-Features above.

---

## Output Formatting Conventions

These are the conventions that apply across all output, based on financial CLI norms and the
project spec's 31 style guide rules.

### Numbers

| Type | Format | Example |
|------|--------|---------|
| Price (USD) | 2 decimal places, no $ prefix in table cells | `187.50` |
| Price (USD) in prose | Include $ | `$187.50` |
| Shares | Integer, no decimal | `12` |
| Percent | 1 decimal place, % suffix | `+4.2%` or `-1.8%` |
| ROC 200 | 1 decimal place, % suffix, sign always shown | `+127.3%` |
| Stop distance | 1 decimal place, % suffix, always negative for long positions | `-6.8%` |
| Cash | 2 decimal places, comma thousands separator, no $ in table | `42,500.00` |
| Large numbers | Comma thousands separator | `1,234,567` |

### Color usage

| Semantic | Color | Use |
|----------|-------|-----|
| Error | Red | Fatal conditions, data failures |
| Warning | Yellow | Non-fatal problems, staleness alerts |
| Info | Cyan | Neutral informational lines |
| Success | Green | Confirmed transactions, scans completed |
| Exit trigger | Red | Positions that triggered a stop — attention required |
| Regime OFF | Yellow | Market not in buy mode — no candidates |
| No change | Default terminal color | Most table data |

NO_COLOR env var respected throughout. Color never carries information without a text equivalent.

### Tables

- No borders, no divider lines
- Text columns: left-aligned
- Numeric columns: right-aligned
- Column headers: sentence case (not ALL CAPS, not Title Case)
- Empty tables: show the header row, then one line explaining why (e.g., "No exit triggers today.")
- No trailing whitespace on any line

### Dates and times

- Dates: ISO 8601 (2024-03-15), never MM/DD/YYYY
- Times: always show ET and Lisbon side by side: "16:45 ET / 21:45 Lisbon"
- "Today" and "yesterday" are acceptable in prose when unambiguous; ISO dates in tables

### Severity prefixes (prose output, not tables)

```
Error: ...     (red)
Warning: ...   (yellow)
Info: ...      (cyan)
Success: ...   (green)
```

---

## Sources and Confidence

| Area | Confidence | Primary Sources |
|------|------------|-----------------|
| Table stakes features | HIGH | PROJECT.md spec (authoritative), systematic trading journal conventions |
| Daily workflow priorities | HIGH | PROJECT.md core value statement, trading checklist research |
| Catch-up / reconciliation | MEDIUM | Trading reconciliation industry patterns; specific implementation is project-defined |
| Anti-features | HIGH | Explicit out-of-scope list in PROJECT.md; confirmed by scope creep analysis |
| Output formatting conventions | HIGH | no-color.org standard, Rich library docs, Bloomberg terminal accessibility research, project spec section 6 reference |
| Differentiators | MEDIUM | Inferred from systematic trading UX research; confidence increases when validated against spec section completeness |
