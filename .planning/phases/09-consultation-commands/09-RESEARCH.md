# Phase 9: Consultation Commands - Research

**Researched:** 2026-05-25
**Domain:** Python CLI read-only query commands — SQLAlchemy SELECT, computed metrics, Rich table output
**Confidence:** HIGH

## Summary

Phase 9 implements 7 commands that let users inspect portfolio state and history without
triggering any state changes, plus one state-changing command (`cash` with an AMOUNT
argument). All infrastructure is already in place: schema, UI primitives, audit machinery,
backup primitive, and the CliRunner test pattern — all established by Phases 2-8.

Every command follows the same two-part shape: (1) query the DB using parameterized
SQLAlchemy SELECTs, (2) render using existing `render_table`/`render_kv_block`/`print_info`
primitives from `bensdorp1.ui`. No new dependencies are required. No schema migrations are
required. The one state-changing path (`cash AMOUNT`) follows the buy/sell write-backup-log
sequence exactly.

The only non-trivial logic is in `detail`: reconstructing per-day stop history by walking
`price_daily` rows from `entry_date + 1` to the most recent available price. This is a pure
computation loop with no I/O calls — it uses the NYSE calendar (already in `data.calendar`)
for trading-day enumeration and applies the strategy stop formulas (already proven in Phase 4).
`portfolio` has a secondary non-trivial piece: joining `positions` with the most recent
`price_daily` row per symbol, then computing `effective_stop`, `distance_to_stop`, and
`unrealized_pnl` at read time.

**Primary recommendation:** Implement each command as a single file in
`src/bensdorp1/commands/` — replacing the existing stubs — following the established
Phase 8 patterns exactly. No engine split, no shared helper module.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** `detail` reconstructs per-day highest-close history from `price_daily`. Walk every
NYSE trading day from `entry_date + 1` to the most recent price in `price_daily` for the
symbol. For each day, compute `highest_close_on_day_D = max(entry_close, closes[entry+1..D])`.
Show as a table of (Date, Close, Highest close, Trailing stop, Effective stop) for every day.
No schema changes.

**D-02:** `detail` splits section — omit entirely in Phase 9. No placeholder line. Phase 11
adds the splits block.

**D-03:** `audit --type` uses `Optional[AuditEventType]` as the Typer type annotation. Typer
validates automatically, renders valid choices in `--help`, and enables shell autocomplete.
No runtime validation code needed.

**D-04:** `cash` signature: `amount: Optional[float] = typer.Argument(None)`,
`note: Optional[str] = typer.Option(None, "--note")`. `--note` is optional on updates.
`amount=0.0` is valid (spec: "non-negative").

**D-05:** `history` "Top 3 buy candidates" column shows a comma-separated list:
`"AAPL, MSFT, NVDA"`. Fewer than 3 → fewer symbols shown. Bear day (no candidates) → `"—"`.
Single column, not three separate columns.

**D-06:** `portfolio` abbreviated column headers to fit a 120-char terminal: Symbol, Entry date,
Days, Entry $, Shares, Last $, High $, Stop $, Dist %, P&L. Right-align all numeric columns;
left-align Symbol.

**D-09 (Claude discretion, resolved):** Single file per command — all 7 commands. No engine
split.

**D-10 (Claude discretion, resolved):** `detail SYMBOL` validates that an open position exists
for SYMBOL; if closed or not found, `print_error(...)` and exit code 1.

**D-11 (Claude discretion, resolved):** CliRunner integration tests with real SQLite temp DB
seeded per-test.

### Claude's Discretion

**D-07:** `Last $` (last close) comes from the most recent `price_daily` row for the symbol
where `trade_date <= today`. If no price data exists for a symbol (edge case), show `N/A` for
Last $, High $, Stop $, Dist %, and P&L — log a warning.
`effective_stop = max(initial_stop, trailing_stop)` computed at read time (not stored).

**D-08:** `Distance to stop %` = `(last_close - effective_stop) / last_close * 100`. Positive
means stop is below current price (normal). Show with sign always (e.g., `+12.3%`). Unrealized
P&L = `(last_close - entry_close) * shares` — use `format_pnl()` from ui.

### Deferred Ideas (OUT OF SCOPE)

- Split history in `detail` — Phase 11
- Delisted position handling in `portfolio` — Phase 11
- Snapshot tests for all command outputs — Phase 13
- Integration tests with mocked yfinance/DB — Phase 13
- Closed position detail (full history) — audit --symbol serves this

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CMD-04 | `bensdorp1 last` — shows most recent scan output; does not re-run anything | `scans.raw_output` read via SELECT ORDER BY scan_date DESC LIMIT 1; `console.print(raw_output, markup=False)` |
| CMD-05 | `bensdorp1 history [--limit N] [--since DATE]` — compact table of past scans | JOIN scans + scan_candidates WHERE rank <= 3; filter by since/limit; render_table 5-col |
| CMD-09 | `bensdorp1 portfolio` — lists all open positions with 10 computed metrics | JOIN positions + price_daily (latest close per symbol); compute effective_stop, dist%, pnl at read time |
| CMD-10 | `bensdorp1 detail SYMBOL` — full history of single open position including per-day stop history | Walk price_daily rows day-by-day using get_trading_days; compute running max for each day |
| CMD-11 | `bensdorp1 cash [AMOUNT] [--note REASON]` — shows current cash or updates it with confirmation | Read config table; update flow: confirm_prompt → UPDATE → create_backup → log_event(CASH_UPDATED) |
| CMD-12 | `bensdorp1 config` — shows cash, base directory, timezone, version | Read config table + importlib.metadata.version("bensdorp1"); render_kv_block |
| CMD-13 | `bensdorp1 audit [--symbol] [--since] [--until] [--type] [--limit]` — AND-filter audit log query | WHERE clause built with optional conditions; Optional[AuditEventType] Typer annotation; ORDER BY occurred_at DESC |

</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Scan output retrieval (last) | DB / Storage | CLI | Query is read-only; raw_output blob printed verbatim |
| Scan history listing (history) | DB / Storage | CLI | JOIN across scans + scan_candidates; no computation |
| Open position metrics (portfolio) | CLI / computation | DB | DB provides raw data; effective_stop, dist%, pnl computed in command code |
| Per-day stop reconstruction (detail) | CLI / computation | DB | Walk price_daily rows; computation is strategy logic already proven in Phase 4 |
| Cash read/update | DB / Storage | CLI | Config table holds cash; update follows write-backup-log pattern |
| Config display | CLI | DB | Config table + importlib.metadata; render_kv_block only |
| Audit log query | DB / Storage | CLI | Parameterized WHERE clause; minimal rendering |

---

## Standard Stack

### Core (all already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | >=0.21.1 | Command registration, argument/option parsing, `Optional[AuditEventType]` annotation | Project standard (CLAUDE.md) |
| rich | >=14.0 | Console output (via ui module) | Project standard (CLAUDE.md) |
| sqlalchemy | >=2.0.49,<2.1 | Parameterized SELECT queries against all 7 tables | Project standard (CLAUDE.md) |
| importlib.metadata | stdlib | `version("bensdorp1")` for `config` command | stdlib; no install needed |
| json | stdlib | Parse `audit_log.payload` JSON for Details column | stdlib |

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas_market_calendars | >=5.3.2 | `get_trading_days(start, end)` for `detail` day-walk and `days_held` in `portfolio` | `detail` per-day history; `portfolio` days column |
| zoneinfo | stdlib (3.9+) | Timezone conversion for timestamps in `audit` and `cash` show-mode | Dual-timezone display per UI rule 6.26 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `get_trading_days` from calendar.py | `pandas_market_calendars` directly | calendar.py wrapper is the project's already-tested interface — use it |
| `importlib.metadata.version` | Hard-coded string | Hard-coded version drifts; importlib.metadata reads pyproject.toml at runtime |
| Subquery for latest price_daily per symbol | Python-side groupby | SQL subquery is cleaner and avoids fetching all rows into memory |

**Installation:** No new packages needed. All dependencies are installed. [VERIFIED: pyproject.toml]

---

## Package Legitimacy Audit

No new packages are introduced in this phase. All dependencies are existing project
dependencies verified in prior phases.

| Package | Disposition |
|---------|-------------|
| (none new) | N/A |

---

## Architecture Patterns

### System Architecture Diagram

```
CLI invocation
     |
     v
@app.command() function (commands/last.py, history.py, portfolio.py, etc.)
     |
     +---> DB entry triad: get_engine → run_migrations → Console()
     |
     +---> SELECT query (parameterized, engine.connect() context manager)
     |         |
     |         v
     |      Raw DB rows (positions, scans, scan_candidates, audit_log, config, price_daily)
     |
     +---> Computation layer (portfolio, detail only)
     |         |
     |         v
     |      effective_stop, dist%, unrealized_pnl, per-day running max
     |
     +---> Render: render_table / render_kv_block / print_info (empty state) / console.print
     |
     v
Terminal output (no state change for read-only commands)

cash AMOUNT path only:
     +---> confirm_prompt
     +---> UPDATE config table + conn.commit()
     +---> create_backup(engine, DATA_DIR / "backups")
     +---> log_event(engine, AuditEventType.CASH_UPDATED, payload={...})
     +---> print_success(...)
```

### Recommended Project Structure

No new directories. All 7 command files replace existing stubs in:

```
src/bensdorp1/commands/
├── last.py          # replaces stub — CMD-04
├── history.py       # replaces stub — CMD-05
├── portfolio.py     # replaces stub — CMD-09
├── detail.py        # replaces stub — CMD-10
├── cash.py          # replaces stub — CMD-11
├── config.py        # replaces stub — CMD-12
└── audit.py         # replaces stub — CMD-13

tests/test_commands/
├── test_last.py     # new — CMD-04 integration tests
├── test_history.py  # new — CMD-05 integration tests
├── test_portfolio.py # new — CMD-09 integration tests
├── test_detail.py   # new — CMD-10 integration tests
├── test_cash.py     # new — CMD-11 integration tests
├── test_config.py   # new — CMD-12 integration tests
└── test_audit.py    # new — CMD-13 integration tests
```

### Pattern 1: Read-Only Command — DB Query + Render

All 6 read-only commands (last, history, portfolio, detail, config, audit) share this skeleton:

```python
# Source: established in buy.py, sell.py, fix.py (Phase 8)
@app.command(rich_help_panel="<panel>")
def <command>(<args>) -> None:
    """<docstring>."""
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    with engine.connect() as conn:
        rows = conn.execute(
            select(<table>.c.<cols>)
            .where(<filters>)
            .order_by(<order>)
            .limit(<limit>)
        ).fetchall()

    if not rows:
        print_info("<Empty state message>.", console=console)
        raise typer.Exit()

    render_table(
        columns=[("<Header>", "left"), ("<Num Header>", "right"), ...],
        rows=[[row.col1, str(row.col2), ...] for row in rows],
        console=console,
    )
```

### Pattern 2: cash Command — Show vs Update Branch

```python
# Source: buy.py write path (Phase 8) + config read pattern
@app.command(rich_help_panel="System")
def cash(
    amount: Optional[float] = typer.Argument(None),
    note: Optional[str] = typer.Option(None, "--note"),
) -> None:
    """Show current cash balance, or update it."""
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()

    with engine.connect() as conn:
        row = conn.execute(
            select(config.c.value, config.c.updated_at)
            .where(config.c.key == "cash")
        ).fetchone()

    if amount is None:
        # Show-mode: render_kv_block with current cash + last updated
        ...
        raise typer.Exit()

    # Update-mode: validate amount >= 0.0
    if amount < 0.0:
        print_error("Cash amount must be non-negative.", console=console)
        raise typer.Exit(code=1)

    old_value = float(row.value) if row is not None else 0.0

    # Confirmation flow (same pattern as buy.py)
    try:
        ...
        confirmed = confirm_prompt("Confirm cash update?", console=console)
    except KeyboardInterrupt:
        raise typer.Exit() from None
    if not confirmed:
        raise typer.Exit()

    # Write + backup + log
    with engine.connect() as conn:
        conn.execute(
            update(config)
            .where(config.c.key == "cash")
            .values(value=str(amount), updated_at=datetime.now(UTC))
        )
        conn.commit()
    create_backup(engine, DATA_DIR / "backups")
    log_event(
        engine,
        AuditEventType.CASH_UPDATED,
        payload={"old": old_value, "new": amount, "note": note},
    )
    print_success("Cash updated.", console=console)
```

### Pattern 3: detail Per-Day Stop History Walk

```python
# Source: D-01 (CONTEXT.md), strategy formulas from Phase 4
# Requires: get_trading_days from data.calendar, price_daily table

with engine.connect() as conn:
    price_rows = conn.execute(
        select(price_daily.c.trade_date, price_daily.c.close)
        .where(
            (price_daily.c.symbol == symbol.upper())
            & (price_daily.c.trade_date > entry_date)
        )
        .order_by(price_daily.c.trade_date.asc())
    ).fetchall()

# Build close dict: trade_date -> close
close_map: dict[date, float] = {
    r.trade_date.date(): r.close for r in price_rows
}

# Walk every NYSE trading day from entry_date+1 to latest available
trading_days = get_trading_days(entry_date + timedelta(days=1), last_price_date)

history_rows: list[list[str]] = []
running_max = entry_close  # initial_stop is based on entry_close

for day in trading_days:
    day_date = day.date()
    day_close = close_map.get(day_date)
    if day_close is None:
        continue  # gap in price data — skip day
    running_max = max(running_max, day_close)
    trailing_stop = running_max * 0.75
    effective_stop = max(initial_stop, trailing_stop)
    history_rows.append([
        format_date(day_date),
        format_price(day_close),
        format_price(running_max),
        format_price(trailing_stop),
        format_price(effective_stop),
    ])

render_table(
    columns=[
        ("Date", "left"),
        ("Close", "right"),
        ("Highest close", "right"),
        ("Trailing stop", "right"),
        ("Effective stop", "right"),
    ],
    rows=history_rows,
    console=console,
)
```

### Pattern 4: history — Subquery for Top-3 Candidates

```python
# Source: D-05 (CONTEXT.md), scan_candidates table (schema.py)
# JOIN scans to scan_candidates, aggregate top-3 by rank per scan

# Option A: Python-side aggregation (simpler, fine for small result sets)
with engine.connect() as conn:
    scan_rows = conn.execute(
        select(scans)
        .where(<since_filter>)
        .order_by(scans.c.scan_date.desc())
        .limit(limit)
    ).fetchall()

    # For each scan, fetch top-3 candidates
    rows: list[list[str]] = []
    for scan in scan_rows:
        cand_rows = conn.execute(
            select(scan_candidates.c.symbol)
            .where(scan_candidates.c.scan_id == scan.id)
            .order_by(scan_candidates.c.rank.asc())
            .limit(3)
        ).fetchall()
        top3 = ", ".join(r.symbol for r in cand_rows) if cand_rows else "—"
        regime_label = "Bull" if scan.regime_active else "Bear"
        rows.append([
            format_date(scan.scan_date.date()),
            regime_label,
            str(scan.exit_trigger_count),
            str(scan.candidate_count),
            top3,
        ])

render_table(
    columns=[
        ("Date", "left"),
        ("Regime", "left"),
        ("Exits", "right"),
        ("Candidates", "right"),
        ("Top candidates", "left"),
    ],
    rows=rows,
    console=console,
)
```

### Pattern 5: audit — Optional[AuditEventType] Annotation

```python
# Source: D-03 (CONTEXT.md), AuditEventType StrEnum (db/audit.py)
# Typer validates the --type flag automatically when Optional[AuditEventType] is used

from typing import Optional
from bensdorp1.db.audit import AuditEventType

@app.command(rich_help_panel="System")
def audit(
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    since: Optional[str] = typer.Option(None, "--since"),
    until: Optional[str] = typer.Option(None, "--until"),
    type_: Optional[AuditEventType] = typer.Option(None, "--type"),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    ...
    filters = []
    if symbol:
        filters.append(audit_log.c.symbol == symbol.upper())
    if since:
        filters.append(audit_log.c.occurred_at >= parse_date(since))
    if until:
        filters.append(audit_log.c.occurred_at <= parse_date_end(until))
    if type_:
        filters.append(audit_log.c.event_type == str(type_))

    with engine.connect() as conn:
        rows = conn.execute(
            select(audit_log)
            .where(*filters)   # AND-filter: all conditions must match
            .order_by(audit_log.c.occurred_at.desc())
            .limit(limit)
        ).fetchall()
```

**Important:** The parameter is named `type_` (trailing underscore) in Python to avoid
shadowing the built-in `type`. Typer option string is `"--type"`. [VERIFIED: typer docs]

### Pattern 6: portfolio — Latest Price Join (Python-side)

```python
# Source: D-07, D-08 (CONTEXT.md), D-19 (Phase 7 CONTEXT)
# effective_stop computed at read time (not stored) per D-18 (Phase 7)

with engine.connect() as conn:
    open_positions = conn.execute(
        select(positions).where(positions.c.closed_at == None)  # noqa: E711
    ).fetchall()

    today_utc = datetime.now(UTC).date()
    history_rows: list[list[str]] = []

    for pos in open_positions:
        # Latest price for this symbol on or before today
        price_row = conn.execute(
            select(price_daily.c.close)
            .where(
                (price_daily.c.symbol == pos.symbol)
                & (price_daily.c.trade_date <= datetime(today_utc.year, today_utc.month, today_utc.day, tzinfo=UTC))
            )
            .order_by(price_daily.c.trade_date.desc())
            .limit(1)
        ).fetchone()

        if price_row is None:
            # D-07: no price data edge case
            history_rows.append([
                pos.symbol,
                format_date(pos.entry_date.date()),
                str(days_held(pos.entry_date.date(), today_utc)),
                format_price(pos.entry_close),
                str(pos.shares),
                "N/A", "N/A", "N/A", "N/A", "N/A",
            ])
            continue

        last_close = price_row.close
        effective_stop = max(pos.initial_stop, pos.trailing_stop)
        dist_pct = (last_close - effective_stop) / last_close * 100.0
        unrealized_pnl = (last_close - pos.entry_close) * pos.shares
        days = days_held(pos.entry_date.date(), today_utc)

        history_rows.append([
            pos.symbol,
            format_date(pos.entry_date.date()),
            str(days),
            format_price(pos.entry_close),
            str(pos.shares),
            format_price(last_close),
            format_price(pos.highest_close),
            format_price(effective_stop),
            format_pct(dist_pct),
            format_pnl(unrealized_pnl),
        ])
```

### Pattern 7: days_held Computation

```python
# Source: sell.py (Phase 8) — len(get_trading_days(entry_date, sell_date))
# For portfolio: entry_date.date() to today
from bensdorp1.data import get_trading_days

def _days_held(entry_date: date, as_of: date) -> int:
    """Count NYSE trading days from entry_date through as_of (inclusive)."""
    return len(get_trading_days(entry_date, as_of))
```

Note: `sell.py` uses `len(get_trading_days(entry_date.date(), sell_date))`. The same formula
applies for `portfolio` where `as_of = today`. The function counts inclusive (entry day counts
as day 1). Verify this matches the spec's "days held" definition before implementing — sell.py
is the canonical reference. [VERIFIED: sell.py lines 178]

### Anti-Patterns to Avoid

- **String interpolation in SQL:** Never `conn.execute(text(f"... WHERE symbol = '{symbol}'"))`.
  Always use SQLAlchemy parameterized form. [VERIFIED: Phase 8 Shared Pattern 7]
- **`console.print("literal string")` without Text():** Always `console.print(Text("..."))`.
  [VERIFIED: Phase 8 Shared Pattern 6]
- **`sys.exit()`:** Always `raise typer.Exit()` or `raise typer.Exit(code=1)`. [VERIFIED: 06-CONTEXT.md]
- **Printing abort message twice:** `confirm_prompt` already prints "Operation aborted. No
  changes were made." Callers must NOT repeat it. Just `raise typer.Exit() from None`.
  [VERIFIED: Phase 8 PATTERNS.md Shared Pattern 3 correction]
- **Referencing `positions.c.entry_price`:** The column is `entry_close`, not `entry_price`.
  [VERIFIED: schema.py line 47]
- **Mutable WHERE clause construction using `and_()` accumulation:** Simpler to build a list of
  conditions and splat into `.where(*filters)` — SQLAlchemy 2.0 accepts multiple positional
  conditions in `.where()` as AND. [VERIFIED: SQLAlchemy 2.0 behavior, verified in project]
- **Blank output on empty state:** Always `print_info("No open positions.")` — never fall
  through to `render_table` with empty rows. [VERIFIED: UI-08, Phase 8 PATTERNS.md]
- **Using `format_pnl` for percentage:** `format_pnl` formats dollar amounts. Use `format_pct`
  for the `Dist %` column. [VERIFIED: ui/styles.py]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NYSE trading-day count | Custom calendar logic | `get_trading_days(start, end)` from `data.calendar` | Handles holidays; already tested; DATA-07 |
| Timezone display | `datetime.strftime` with tz string | `format_timezone_pair(dt)` from `ui` | Rule 6.26; tested for ET + user tz |
| Price formatting | f-string | `format_price(value)` from `ui` | Rule 6.10; thousands separator |
| Percentage with sign | f-string | `format_pct(value)` from `ui` | Rule 6.10; explicit sign |
| P&L dollar with sign | f-string | `format_pnl(value)` from `ui` | Rule 6.10; explicit sign |
| Date formatting | `datetime.strftime` | `format_date(d)` from `ui` | Rule 6.24; ISO 8601 |
| Audit validation | Runtime type check | `Optional[AuditEventType]` Typer annotation | Typer validates and shows choices in --help |
| Package version | Hard-coded string | `importlib.metadata.version("bensdorp1")` | Reads pyproject.toml at runtime; never stale |
| DB backup | File copy | `create_backup(engine, DATA_DIR / "backups")` | sqlite3.Connection.backup() API — safe concurrent copy |

**Key insight:** The Phase 5 UI module eliminates all formatting boilerplate. Every display
concern is already solved. The commands are pure query + render wrappers.

---

## Common Pitfalls

### Pitfall 1: `config.c.key` vs Python `config` built-in

**What goes wrong:** SQLAlchemy `Table` object named `config` shadows the Python built-in
`config`. Import it as `from bensdorp1.db.schema import config as config_table` or use an
alias to avoid confusion.

**Why it happens:** `schema.py` exports `config: Table` — the same name as a common Python
concept and a hypothetical stdlib reference.

**How to avoid:** Alias at import: `from bensdorp1.db.schema import config as config_table`.

**Warning signs:** mypy reports "Name 'config' already defined" or confusion with
`bensdorp1.config` (the config module).

### Pitfall 2: `positions.c.closed_at == None` SQLAlchemy idiom

**What goes wrong:** Python `== None` raises a lint warning (E711), but SQLAlchemy requires
`== None` (not `is None`) to generate `IS NULL` SQL.

**Why it happens:** SQLAlchemy overloads `==` for column comparisons. `is None` would test
Python identity, not generate SQL.

**How to avoid:** Use `# noqa: E711` comment as established in schema.py line 63 and
buy.py line 86.

**Warning signs:** Query returns all rows including closed positions.

### Pitfall 3: `Optional[AuditEventType]` — Typer parameter name conflict

**What goes wrong:** Using `type` as the parameter name in the `audit` command function
shadows the Python built-in.

**Why it happens:** `--type` is the natural CLI flag name.

**How to avoid:** Always use `type_: Optional[AuditEventType] = typer.Option(None, "--type")`.
Typer accepts `"--type"` as the option name regardless of Python parameter name.

### Pitfall 4: `detail` — price_daily gaps

**What goes wrong:** Not all NYSE trading days have a `price_daily` row (data gaps, weekends
already filtered by trading day list, but occasionally missing closes for valid trading days).

**Why it happens:** yfinance data is not always complete; D-01 says "skip day" for gaps.

**How to avoid:** Build a dict `{date: close}` from fetched price rows. When walking trading
days, skip any day not in the dict (`if day_date not in close_map: continue`). Do not crash
or insert a row with None/0.

**Warning signs:** KeyError on close_map lookup, or a row with `$0.00` close.

### Pitfall 5: `history --since` date parsing

**What goes wrong:** Passing `--since 2026-01-01` provides a string; the command must parse
it to a `datetime` for the SQLAlchemy WHERE comparison. Naive datetime will not compare
correctly against UTC-stored `scan_date`.

**Why it happens:** `scan_date` is stored as `DateTime(timezone=True)` — UTC in SQLite.
A naive `datetime.fromisoformat("2026-01-01")` has no tzinfo; comparison may silently fail.

**How to avoid:** Parse: `datetime(year, month, day, tzinfo=UTC)` after
`datetime.date.fromisoformat(since_str)`. Then use in WHERE: `scans.c.scan_date >= since_dt`.

**Warning signs:** `--since 2026-01-01` returns no rows even when scans exist after that date.

### Pitfall 6: `cash` command — `config` table row may not exist

**What goes wrong:** If the user runs `bensdorp1 cash` before `bensdorp1 init`, the `config`
table row for `"cash"` may not exist. SELECT returns `None`.

**Why it happens:** `init` writes the cash row; the consultation commands don't check for init.

**How to avoid:** For show-mode: if row is None, `print_info("No cash configured. Run \`bensdorp1 init\`.")`. For update-mode: handle the case where the row does not exist by using UPSERT (INSERT OR REPLACE) or checking and branching between INSERT and UPDATE.

**Warning signs:** `AttributeError: 'NoneType' object has no attribute 'value'` when cash
row is missing.

### Pitfall 7: `audit` payload JSON parsing for Details column

**What goes wrong:** `audit_log.payload` is stored as a JSON string (or NULL). Directly
displaying the raw JSON is ugly. The Details column should show key fields only.

**Why it happens:** `log_event()` stores `json.dumps(payload)`. The display format is not
stored — it must be derived.

**How to avoid:** Parse with `json.loads(row.payload)` when `row.payload is not None`. Show
only the most relevant fields per event type. For `cash_updated`: `$old → $new`. For
`buy_confirmed`: `N shares @ $price`. Fall back to showing the raw JSON if the payload
structure is unexpected.

**Warning signs:** `{"price": 432.5, "shares": 23, ...}` shown verbatim in the Details
column, which is unreadable.

### Pitfall 8: `format_pnl` sign for negative P&L

**What goes wrong:** `format_pnl(-215.00)` produces `"-$215.00"` (the sign comes from the
minus sign in the f-string). Verify that the output is `"-$215.00"` not `"−$215.00"` (unicode minus).

**Why it happens:** `format_pnl` in `ui/styles.py` uses `sign = "+" if value >= 0 else "-"`.
For negative values: `f"-${abs(value):,.2f}"` → `"-$215.00"`. This is correct ASCII minus.

**How to avoid:** Use `format_pnl()` as-is — do not format P&L directly in command code.

---

## Code Examples

### Verified Pattern: DB Entry Triad (all 7 commands)

```python
# Source: buy.py lines 45-48 (Phase 8) — identical in all commands
db_path = DATA_DIR / "data" / "bensdorp1.db"
engine = get_engine(db_path)
run_migrations(engine)
console = Console()
```

### Verified Pattern: Empty State Guard

```python
# Source: scan.py lines 51-56 (Phase 7)
if not rows:
    print_info("No open positions.", console=console)
    raise typer.Exit()
```

### Verified Pattern: WHERE clause with None guard (SQLAlchemy 2.0)

```python
# Source: buy.py line 86, schema.py line 63
.where(positions.c.closed_at == None)  # noqa: E711  — generates IS NULL
```

### Verified Pattern: render_table signature

```python
# Source: ui/tables.py lines 18-41
render_table(
    columns=[("Symbol", "left"), ("Entry date", "left"), ("Days", "right"), ...],
    rows=[["AAPL", "2026-03-15", "48", ...], ...],
    console=console,
)
```

### Verified Pattern: render_kv_block signature

```python
# Source: ui/styles.py lines 146-163, buy.py lines 167-179
render_kv_block(
    {
        "Available cash":  "$45,000.00",
        "Last updated":    "14:30 ET (19:30 Lisbon)",
    },
    console,
)
```

### Verified Pattern: format_timezone_pair for audit timestamps

```python
# Source: ui/styles.py lines 86-95
# Input: a timezone-aware datetime (UTC stored in DB)
display = format_timezone_pair(row.occurred_at)
# Output: "14:30 ET (19:30 Lisbon)"
```

### Verified Pattern: importlib.metadata for version

```python
# Source: Python stdlib
from importlib.metadata import version as pkg_version
ver = pkg_version("bensdorp1")  # reads from installed package metadata
```

### Verified Pattern: CliRunner test with real SQLite DB

```python
# Source: tests/conftest.py db_engine fixture; test_buy.py test_happy_path_on_signal
from typer.testing import CliRunner
from bensdorp1.cli import app

runner = CliRunner()

def test_something(db_engine: Engine, tmp_path: Path) -> None:
    with (
        patch("bensdorp1.commands.portfolio.get_engine", return_value=db_engine),
        patch("bensdorp1.commands.portfolio.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.portfolio.run_migrations"),
    ):
        result = runner.invoke(app, ["portfolio"])
    assert result.exit_code == 0
```

---

## Runtime State Inventory

Not applicable — this is not a rename/refactor/migration phase. All state is in SQLite;
no runtime state outside the DB is affected.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Stub commands (raise typer.Exit after "Not yet implemented.") | Full implementations | Phase 9 (this phase) | Replaces all 7 stubs |
| N/A | `Optional[AuditEventType]` Typer annotation | Phase 9 (new) | Typer auto-validates; no manual validation code needed |

**Existing stubs to replace:**
- `src/bensdorp1/commands/last.py` — stub (4 lines)
- `src/bensdorp1/commands/history.py` — stub (4 lines)
- `src/bensdorp1/commands/portfolio.py` — stub (4 lines)
- `src/bensdorp1/commands/detail.py` — stub (4 lines, also missing SYMBOL arg)
- `src/bensdorp1/commands/cash.py` — stub (4 lines, missing all args)
- `src/bensdorp1/commands/config.py` — stub (4 lines)
- `src/bensdorp1/commands/audit.py` — stub (4 lines, missing all flags)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `days_held` in `portfolio` uses `len(get_trading_days(entry_date, today))` inclusive | Pattern 7 | Days count off by 1 vs spec expectation — verify against sell.py line 178 |
| A2 | `history --since DATE` filter uses `>=` (on-or-after) per spec §5.2.4 | Pattern 4 | Shows fewer scans than expected |
| A3 | `audit --until DATE` filter uses `<=` end-of-day — the UTC datetime is midnight on the date | Pattern 5 | Scans on `until` date may be excluded if compared at midnight |
| A4 | `config` table's `"cash"` key stores value as TEXT (not FLOAT) | Pattern 2 | Needs `float(row.value)` conversion — crash if not TEXT |
| A5 | For `detail`, the entry day itself (entry_date) is NOT included in the per-day history table — history starts from entry_date + 1 trading day | Pattern 3 | D-01 says "from entry_date + 1" — if implementation starts from entry_date, the running max starts equal to entry_close (same result but table has one extra row) |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

(A1, A5 are low-risk — verify against existing sell.py and D-01 wording before coding.)

---

## Open Questions

1. **`days_held` in `portfolio`: inclusive of entry day?**
   - What we know: `sell.py` line 178 uses `len(get_trading_days(entry_date.date(), sell_date))` — this is inclusive on both ends.
   - What's unclear: The spec says "days held" — does day 1 mean the entry day or the first day after?
   - Recommendation: Use same formula as `sell.py`: `len(get_trading_days(entry_date.date(), today))`. This means on the same day as entry, `days_held = 1`.

2. **`audit --until DATE`: end-of-day or start-of-day?**
   - What we know: Spec §5.2.12 says "events on or before DATE." `occurred_at` is UTC datetime.
   - What's unclear: Should `--until 2026-05-25` include events at 23:59 ET on that date?
   - Recommendation: Use `datetime(year, month, day, 23, 59, 59, tzinfo=UTC)` for the upper bound, or compare against `date + 1 day` with strict `<`. Either is defensible; pick the more natural one.

3. **`config` table — `updated_at` for cash key when no update has been done since init**
   - What we know: `init` writes the cash row with `updated_at = datetime.now(UTC)`.
   - What's unclear: Does `cash` show-mode show `updated_at` as "last updated" even when it was set during init (not a cash update)?
   - Recommendation: Yes — show whatever `updated_at` is in the row. The label "Last updated" is accurate since init is the first update.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All commands | Yes | 3.14.5 | — |
| uv | Package management | Yes | 0.10.12 | — |
| SQLite (via sqlalchemy) | All DB operations | Yes | stdlib | — |
| bensdorp1 package (editable install) | importlib.metadata.version | Yes | 0.1.0 | — |
| pandas_market_calendars | `detail` day-walk, `portfolio` days_held | Yes (installed) | >=5.3.2 | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=8.3 |
| Config file | `[tool.pytest.ini_options]` in `pyproject.toml` (testpaths = ["tests"]) |
| Quick run command | `uv run pytest tests/test_commands/ -x -q` |
| Full suite command | `uv run pytest --cov=bensdorp1 --cov-report=term-missing -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CMD-04 | `last` shows raw_output of most recent scan | integration | `uv run pytest tests/test_commands/test_last.py -x` | Wave 0 |
| CMD-04 | `last` prints info message when no scans exist | integration | `uv run pytest tests/test_commands/test_last.py -x` | Wave 0 |
| CMD-05 | `history` shows compact table ordered by date desc | integration | `uv run pytest tests/test_commands/test_history.py -x` | Wave 0 |
| CMD-05 | `history --limit 2` returns only 2 rows | integration | `uv run pytest tests/test_commands/test_history.py -x` | Wave 0 |
| CMD-05 | `history --since DATE` filters correctly | integration | `uv run pytest tests/test_commands/test_history.py -x` | Wave 0 |
| CMD-05 | `history` empty state when no scans | integration | `uv run pytest tests/test_commands/test_history.py -x` | Wave 0 |
| CMD-09 | `portfolio` lists open positions table | integration | `uv run pytest tests/test_commands/test_portfolio.py -x` | Wave 0 |
| CMD-09 | `portfolio` empty state shows "No open positions." | integration | `uv run pytest tests/test_commands/test_portfolio.py -x` | Wave 0 |
| CMD-09 | `portfolio` shows N/A when price_daily missing | integration | `uv run pytest tests/test_commands/test_portfolio.py -x` | Wave 0 |
| CMD-10 | `detail SYMBOL` shows position summary + stop history table | integration | `uv run pytest tests/test_commands/test_detail.py -x` | Wave 0 |
| CMD-10 | `detail SYMBOL` exits code 1 when no open position | integration | `uv run pytest tests/test_commands/test_detail.py -x` | Wave 0 |
| CMD-10 | `detail SYMBOL` stop history rows use correct formulas | integration | `uv run pytest tests/test_commands/test_detail.py -x` | Wave 0 |
| CMD-11 | `cash` (no args) shows current cash + last updated | integration | `uv run pytest tests/test_commands/test_cash.py -x` | Wave 0 |
| CMD-11 | `cash AMOUNT` updates after confirmation + writes audit event | integration | `uv run pytest tests/test_commands/test_cash.py -x` | Wave 0 |
| CMD-11 | `cash -1.0` exits code 1 (non-negative validation) | integration | `uv run pytest tests/test_commands/test_cash.py -x` | Wave 0 |
| CMD-11 | `cash 0.0` succeeds (zero is valid) | integration | `uv run pytest tests/test_commands/test_cash.py -x` | Wave 0 |
| CMD-11 | `cash AMOUNT` n-answer aborts without state change | integration | `uv run pytest tests/test_commands/test_cash.py -x` | Wave 0 |
| CMD-12 | `config` shows cash, directory, timezone, version | integration | `uv run pytest tests/test_commands/test_config.py -x` | Wave 0 |
| CMD-13 | `audit` (no filters) shows 50 most recent events | integration | `uv run pytest tests/test_commands/test_audit.py -x` | Wave 0 |
| CMD-13 | `audit --symbol NVDA` filters to NVDA events only | integration | `uv run pytest tests/test_commands/test_audit.py -x` | Wave 0 |
| CMD-13 | `audit --type buy_confirmed` shows only that type | integration | `uv run pytest tests/test_commands/test_audit.py -x` | Wave 0 |
| CMD-13 | `audit --since DATE --until DATE` AND-filters correctly | integration | `uv run pytest tests/test_commands/test_audit.py -x` | Wave 0 |
| CMD-13 | `audit --limit 3` returns at most 3 events | integration | `uv run pytest tests/test_commands/test_audit.py -x` | Wave 0 |
| CMD-13 | `audit` empty state when no events match | integration | `uv run pytest tests/test_commands/test_audit.py -x` | Wave 0 |

### Edge Cases and Boundary Conditions

**CMD-04 (`last`):**
- No scans ever run → empty state message directing to `bensdorp1 scan`
- Most recent scan has `raw_output = NULL` → handle gracefully (show info, not crash)
- `raw_output` contains Rich markup characters → must print with `markup=False, highlight=False` (as scan.py does)

**CMD-05 (`history`):**
- No scans match `--since DATE` → empty state with which filters were applied
- Scan exists with 0 candidates (bear day) → top candidates column shows `"—"`
- Scan exists with 1 candidate → shows single symbol (not padded to 3)
- `--since` date that is in the future → returns empty (no error needed, empty state)
- `--since` with invalid date format → `print_error` + exit code 1

**CMD-09 (`portfolio`):**
- No open positions → `print_info("No open positions.")` + check if any scan has run; if not, suggest `bensdorp1 scan`
- Open position with no price_daily data → show N/A for all price-derived columns; log warning
- 10 simultaneous positions (maximum) → all 10 shown in table
- `Dist %` negative → stop is above last close (position underwater); show with `-` sign using `format_pct`
- P&L negative → `format_pnl` produces `-$XXX.XX` correctly

**CMD-10 (`detail`):**
- Symbol not in any open position → exit code 1, suggest `bensdorp1 audit --symbol SYMBOL`
- Symbol in a closed position only → same error (detail is for open positions only)
- Position entry today → no history rows (entry_date + 1 to today = 0 trading days); show empty history section gracefully
- Price gaps in `price_daily` → skip days without data (no crash)
- `originating scan signal`: if `pos.scan_id IS NULL` → show "No scan signal (off-signal entry)" for that section

**CMD-11 (`cash`):**
- `cash` before `init` (config row missing) → show info message, not crash
- `cash 0.0` → valid (spec says "non-negative"); must not reject zero
- `cash -0.01` → exit code 1 (negative)
- `cash AMOUNT --note ""` → empty note: treat as None (or accept empty string — pick one and document)
- Ctrl+C during confirmation → abort, no state change

**CMD-12 (`config`):**
- `config` before `init` (no cash row) → show `$0.00` or "Not configured" for cash; do not crash
- Version comes from `importlib.metadata` at runtime; always reflects installed version

**CMD-13 (`audit`):**
- `--type invalid_type` → Typer automatically rejects with valid choices shown (no custom code needed)
- `--since after --until` → returns empty (no error required; logical AND produces no results)
- `payload = NULL` → Details column shows `"—"` or empty string; do not attempt `json.loads(None)`
- Most-recent-first ordering must hold even when filters reduce the result set

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_commands/ -x -q`
- **Per wave merge:** `uv run pytest --cov=bensdorp1 --cov-report=term-missing -q && uv run ruff check src/ && uv run mypy src/`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps (test files to create before implementation)

All 7 test files must be created as Wave 0 stubs before implementation waves:

- [ ] `tests/test_commands/test_last.py` — covers CMD-04 (2 scenarios minimum)
- [ ] `tests/test_commands/test_history.py` — covers CMD-05 (4 scenarios minimum)
- [ ] `tests/test_commands/test_portfolio.py` — covers CMD-09 (3 scenarios minimum)
- [ ] `tests/test_commands/test_detail.py` — covers CMD-10 (3 scenarios minimum)
- [ ] `tests/test_commands/test_cash.py` — covers CMD-11 (5 scenarios minimum)
- [ ] `tests/test_commands/test_config.py` — covers CMD-12 (1 scenario minimum)
- [ ] `tests/test_commands/test_audit.py` — covers CMD-13 (6 scenarios minimum)

*(If Wave 0 test stubs are created empty (pass), wave implementation fills them in alongside the command code.)*

---

## Security Domain

> `security_enforcement: true` in `.planning/config.json` — this section is required.
> ASVS level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user CLI; no auth |
| V3 Session Management | No | Stateless CLI invocations |
| V4 Access Control | No | Single-user tool |
| V5 Input Validation | Yes | Typer validates types; date strings parsed with `fromisoformat`; symbol uppercased |
| V6 Cryptography | No | No crypto in these commands |
| V9 Communication | No | No network calls in consultation commands |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via symbol/date inputs | Tampering | SQLAlchemy parameterized queries only — never f-string SQL |
| Rich markup injection via DB values | Tampering | `markup=False` on all `console.print()` calls; `Text()` wrapping for literals; `render_kv_block` already uses `markup=False` internally |
| Path traversal via DATA_DIR | Tampering | `DATA_DIR` is from env var resolved at import time; no user-controlled path in Phase 9 commands |
| Integer overflow in `--limit` | DoS | Typer validates `int`; no explicit cap needed for ASVS L1 |
| JSON payload injection from audit_log | Tampering | Parse with `json.loads` safely; display only extracted fields; do not `eval()` |

**Security note for `audit --type`:** `Optional[AuditEventType]` annotation means Typer
rejects invalid values before the function body executes — no runtime validation code needed.
The StrEnum values are fixed at 17; no dynamic value is accepted.

---

## Sources

### Primary (HIGH confidence)

- `src/bensdorp1/db/schema.py` — exact column names for all 7 tables [VERIFIED: codebase]
- `src/bensdorp1/db/audit.py` — AuditEventType StrEnum, all 17 values [VERIFIED: codebase]
- `src/bensdorp1/ui/__init__.py`, `ui/styles.py`, `ui/tables.py`, `ui/messages.py`, `ui/prompts.py` — full public API [VERIFIED: codebase]
- `src/bensdorp1/commands/buy.py`, `sell.py` — canonical write-backup-log pattern [VERIFIED: codebase]
- `src/bensdorp1/data/calendar.py` — `get_trading_days(start, end)` signature [VERIFIED: codebase]
- `src/bensdorp1/config.py` — DATA_DIR, MARKET_TZ, USER_TZ [VERIFIED: codebase]
- `.planning/phases/09-consultation-commands/09-CONTEXT.md` — all locked decisions [VERIFIED: codebase]
- `.planning/phases/08-confirmation-commands/08-PATTERNS.md` — shared patterns 1-9 [VERIFIED: codebase]
- `tests/conftest.py` — db_engine fixture pattern [VERIFIED: codebase]
- `tests/test_commands/test_buy.py` — CliRunner test pattern with real SQLite [VERIFIED: codebase]
- `pyproject.toml` — installed dependencies, mypy overrides [VERIFIED: codebase]

### Secondary (MEDIUM confidence)

- `.planning/Bensdorp_1.md` §5.2.3-5.2.12 — command specifications [CITED: project spec]
- `.planning/REQUIREMENTS.md` CMD-04, CMD-05, CMD-09-CMD-13 — requirement definitions [CITED: project requirements]

### Tertiary (LOW confidence)

None — all claims verified against codebase or project specification documents.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in use in prior phases
- Architecture patterns: HIGH — verified against Phase 8 buy.py/sell.py/fix.py implementations
- Pitfalls: HIGH — verified against actual code (schema column names, SQLAlchemy idioms, prompt behavior)
- Test patterns: HIGH — verified against conftest.py and test_buy.py

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (stable stack; no fast-moving dependencies)
