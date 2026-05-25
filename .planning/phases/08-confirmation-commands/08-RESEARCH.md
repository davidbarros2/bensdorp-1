# Phase 8: Confirmation Commands - Research

**Researched:** 2026-05-25
**Domain:** Python CLI command implementation — SQLite DB writes, interactive confirmation flows, P&L calculation
**Confidence:** HIGH (all findings verified directly from codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Add `closed_reason TEXT` (nullable) and `closed_manual_reason TEXT` (nullable) to `positions` via explicit `ALTER TABLE` statements in `run_migrations`. Wrap each in `try/except OperationalError` for idempotency.
- **D-02:** `positions.scan_id` (FK to `scans.id`, nullable) already serves as `confirmed_signal_scan_id`. NULL = off-signal.
- **D-03:** No `confirmed_at` column. `positions.entry_date` is the buy date.
- **D-04:** Buy validation order: (1) constituent check, (2) no open position for symbol, (3) price > 0 and shares > 0.
- **D-05:** Off-signal check: query most recent scan with `scan_date <= DATE`, look for symbol in `scan_candidates` with `rank <= 10`. If found, link `positions.scan_id`. If not found, show off-signal warning.
- **D-06:** Off-signal warning shown before main `[y/n]` confirmation. Two separate `confirm_prompt` calls.
- **D-07:** No scans ever run (empty `scans` table) → treat as off-signal.
- **D-08:** Main confirmation header using `render_kv_block`. `Signal scan` line only when on-signal.
- **D-09:** On confirmation: `initial_stop = price * 0.93`, `highest_close = price`, `trailing_stop = price * 0.75`. Call `create_backup`. Log `AuditEventType.BUY_CONFIRMED`.
- **D-10:** `--date DATE` ISO `YYYY-MM-DD`. Default: today (ET date). Stored as `entry_date`.
- **D-11:** `buy_value = price * shares`, shown as `format_price(buy_value)`.
- **D-12:** Normal sell: query earliest `scan_exit_triggers` row for position. `"Trailing stop"` → `"stop_trailing"`, `"Initial stop"` → `"stop_initial"`.
- **D-13:** If no `scan_exit_triggers` row for position: print error and exit code 1.
- **D-14:** `sell --manual REASON` → `closed_reason = "manual"`, `closed_manual_reason = REASON`, audit event `SELL_MANUAL`.
- **D-15:** Normal sell → `closed_reason = "stop_initial"` or `"stop_trailing"`, `closed_manual_reason = NULL`, audit event `SELL_CONFIRMED`.
- **D-16:** Sell confirmation fields: `sell_value`, `entry_value`, `days_held` (NYSE trading days), `realized_pnl`, `realized_pnl_pct`. Format: `±$X,XXX.XX (±X.X%)`.
- **D-17:** On confirmation: UPDATE `positions`, call `create_backup`, log audit event.
- **D-18:** Sell validation: (1) open position exists, (2) sell price > 0, (3) `--date DATE` >= `entry_date`.
- **D-19:** Fix target: open position → targets buy fields. Closed position (no open) → targets most recent closed sell. Neither → error, exit 1.
- **D-20:** Editable buy fields: `date`, `price`, `shares`. Editable sell fields: `date`, `price`, `manual_reason` (only if manual).
- **D-21:** Recalculation on buy fix: `price` change → `initial_stop = new_price * 0.93`. Closed position + price/shares change → `realized_pnl = (exit_price - new_price) * new_shares`.
- **D-22:** `trailing_stop` and `highest_close` NOT changed by fix.
- **D-23:** Show before/after diff for changed fields only. No-changes path: print Info and exit without writing.
- **D-24:** Audit event `TRANSACTION_CORRECTED` with `{"before": {...}, "after": {...}}`. Call `create_backup` after UPDATE.
- **D-25 (Claude's discretion):** Single file per command, no engine split.
- **D-26 (Claude's discretion):** All three commands follow the same flow structure. No shared helper.

### Claude's Discretion

- D-25: Single-file commands (no engine split).
- D-26: No shared helper module; duplication acceptable.

### Deferred Ideas (OUT OF SCOPE)

- `portfolio` command (Phase 9)
- `detail SYMBOL` command (Phase 9)
- Split detection on buy confirmation (Phase 11, DATA-06)
- Delisted stock handling on sell (Phase 11, STATE-07)
- Snapshot tests for buy/sell/fix output (Phase 13, TEST-04)
- Integration tests with mocked DB (Phase 13, TEST-05)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CMD-06 | `bensdorp1 buy SYMBOL PRICE SHARES [--date DATE]` — record confirmed buy; validate constituent membership; prevent duplicate open positions; link to scan signal; off-signal warning if not in top 10 | D-04 through D-11; constituent validation via `constituents_cache` table; partial unique index `ix_positions_open_symbol` enforces no-duplicate-open; `scan_candidates` rank query for signal link |
| CMD-07 | `bensdorp1 sell SYMBOL PRICE [--date DATE] [--manual REASON]` — record confirmed sell; compute realized P&L; close position | D-12 through D-18; P&L via `format_pnl` + `format_pct`; trading days via `get_trading_days`; exit trigger lookup in `scan_exit_triggers`; UPDATE `positions` to close |
| CMD-08 | `bensdorp1 fix SYMBOL [--date DATE]` — interactive correction of last transaction; before/after diff; audit trail | D-19 through D-24; field-by-field input; `render_table` for diff; `TRANSACTION_CORRECTED` event with before/after payload |
</phase_requirements>

---

## Summary

Phase 8 implements three state-changing commands: `buy`, `sell`, and `fix`. All three commands are currently stubs that print "Not yet implemented." The CONTEXT.md decisions are fully locked and prescriptive — the implementation path is well-defined. This research confirms every code-level detail the planner needs: exact function signatures, enum member names, table column names, and test patterns.

The codebase is fully operational through Phase 7. All infrastructure (schema, engine, audit, backup, UI primitives) is already in place and tested. Phase 8 is pure application of existing patterns with two additions: (1) two new columns on `positions` via `run_migrations` ALTER TABLE, and (2) business logic for buy/sell/fix flows.

**Primary recommendation:** Follow the single-file, validate-preview-confirm-write-backup-log pattern established by `init.py`, using only the public surfaces of `bensdorp1.db` and `bensdorp1.ui`. No new shared helper modules. Test with CliRunner + real SQLite in-memory DB.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Buy command: constituent validation | CLI command (buy.py) | Database (constituents_cache) | Business rule enforced at command entry; DB provides the lookup table |
| Buy command: duplicate open position check | Database (partial unique index) | CLI command | `ix_positions_open_symbol` partial unique index is the canonical enforcement; CLI reads before attempting insert |
| Buy command: signal scan lookup | CLI command (buy.py) | Database (scan_candidates, scans) | CLI reads scan_candidates to determine on/off-signal status |
| Buy command: position insertion | Database (positions) | CLI command (buy.py) | DB owns state; CLI drives the write |
| Sell command: exit trigger lookup | CLI command (sell.py) | Database (scan_exit_triggers) | CLI reads triggers to infer close reason |
| Sell command: P&L calculation | CLI command (sell.py) | — | Pure arithmetic over position data already loaded by CLI |
| Sell command: trading days count | CLI command (sell.py) | data.calendar (get_trading_days) | calendar module is the authoritative NYSE day counter |
| Fix command: field-by-field prompting | CLI command (fix.py) | UI (text_prompt, number_prompt) | Interactive session is command-layer responsibility |
| Fix command: before/after diff rendering | CLI command (fix.py) | UI (render_table) | Logic is in command; render_table handles layout |
| Schema migration | db/engine.py (run_migrations) | — | All DDL changes go through run_migrations |
| Backup after writes | db/backup.py (create_backup) | — | Called at end of every state-changing command |
| Audit logging | db/audit.py (log_event) | — | Called at end of every state-changing command |

---

## Standard Stack

All libraries are already in `pyproject.toml`. No new packages needed for this phase.

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | `>=0.21.1` | CLI framework, `@app.command`, `typer.Exit`, `typer.Option`, `typer.Argument` | Project standard; all commands use it |
| sqlalchemy | `>=2.0.49,<2.1` | Parameterized DB queries; `select`, `insert`, `update`, `text` | Project standard; all DB ops |
| rich | `>=14.0` | `Console`, `Text` for output | Project standard; all UI output |

### Supporting (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas-market-calendars | `>=5.3.2` | NYSE trading day count via `get_trading_days` | `days_held` calculation in sell |
| pandas | `>=3.0.3` | `pd.DatetimeIndex` from `get_trading_days` | Consumed by `len(get_trading_days(...))` |

### New Package: None

No new packages required. This phase is pure implementation using existing dependencies.

## Package Legitimacy Audit

> Not applicable — this phase installs no new packages.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed:** none
**Packages flagged:** none

---

## Architecture Patterns

### System Architecture Diagram

```
CLI entry                   Validation                  DB reads
─────────                   ──────────                  ────────
buy SYMBOL PRICE SHARES  →  1. constituents_cache     →  symbol exists?
                         →  2. positions (open)        →  no duplicate?
                         →  3. price/shares > 0
                            ↓ (pass)
                         →  4. scans + scan_candidates →  on-signal check
                            ↓
                         UI output: off-signal warning (if applicable)
                         confirm_prompt("Continue?")
                            ↓ (y)
                         UI output: confirmation header (render_kv_block)
                         confirm_prompt("Confirm buy?")
                            ↓ (y)
DB writes               ←  insert positions           →  create_backup
                        ←  log_event(BUY_CONFIRMED)
                            ↓
                         print_success("Buy recorded.")
```

```
sell SYMBOL PRICE        →  1. positions (open)         →  open position exists?
[--manual REASON]        →  2. price > 0
                         →  3. date >= entry_date
                            ↓ (pass, no --manual)
                         →  4. scan_exit_triggers       →  trigger row exists?
                            ↓ (must exist)
                         UI output: confirmation header (render_kv_block)
                         confirm_prompt("Confirm sell?")
                            ↓ (y)
DB writes               ←  update positions (close)    →  create_backup
                        ←  log_event(SELL_CONFIRMED or SELL_MANUAL)
                            ↓
                         print_success("Sell recorded.")
```

```
fix SYMBOL               →  1. positions (open)         →  open position exists?
[--date DATE]               ↓ if not →
                         →  1b. positions (closed)      →  most recent closed?
                            ↓ (transaction found)
                         UI output: identification block (render_kv_block)
                         confirm_prompt("Is this the transaction?")
                            ↓ (y)
                         field-by-field prompts (text_prompt / number_prompt)
                            ↓
                         if no changes → print_info("No changes detected.") → exit
                            ↓ (changes exist)
                         UI output: before/after diff (render_table)
                         UI output: impact block (render_kv_block, only if derived values changed)
                         confirm_prompt("Confirm correction?")
                            ↓ (y)
DB writes               ←  update positions (in-place)  →  create_backup
                        ←  log_event(TRANSACTION_CORRECTED, payload=before/after)
                            ↓
                         print_success("Transaction corrected.")
```

### Recommended Project Structure

No new directories. All three files land in the existing `commands/` directory:

```
src/bensdorp1/commands/
├── buy.py         # REPLACE stub — full CMD-06 implementation
├── sell.py        # REPLACE stub — full CMD-07 implementation
├── fix.py         # REPLACE stub — full CMD-08 implementation
└── (others unchanged)

src/bensdorp1/db/
└── engine.py      # ADD ALTER TABLE statements in run_migrations()

tests/test_commands/
├── test_buy.py    # NEW — CliRunner integration tests
├── test_sell.py   # NEW — CliRunner integration tests
└── test_fix.py    # NEW — CliRunner integration tests
```

### Pattern 1: Command Entry with run_migrations

Every buy/sell/fix command follows this entry pattern (verified from scan.py and init.py):

```python
# Source: src/bensdorp1/commands/scan.py and init.py
@app.command(rich_help_panel="Confirmations")
def buy(
    symbol: str = typer.Argument(..., help="Ticker symbol (e.g. NVDA)."),
    price: float = typer.Argument(..., help="Buy price per share."),
    shares: int = typer.Argument(..., help="Number of shares."),
    date: str | None = typer.Option(None, "--date", help="Buy date (YYYY-MM-DD). Defaults to today ET."),
) -> None:
    """Record a confirmed buy transaction."""
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    engine = get_engine(db_path)
    run_migrations(engine)
    console = Console()
    # ... validation and confirmation flow ...
```

Note: `run_migrations` picks up the new `ALTER TABLE` additions automatically on first call after this phase is deployed.

### Pattern 2: Validation with Early Exit

Error path from scan.py and init.py — use `print_error` + `raise typer.Exit(code=1)`:

```python
# Source: src/bensdorp1/commands/scan.py
from bensdorp1.ui import print_error
from bensdorp1.db.schema import constituents_cache
from sqlalchemy import select

with engine.connect() as conn:
    row = conn.execute(
        select(constituents_cache.c.symbol).where(
            constituents_cache.c.symbol == symbol.upper()
        )
    ).fetchone()

if row is None:
    print_error(
        f"Symbol {symbol.upper()} is not a valid S&P 500 constituent.",
        actions=["Run `bensdorp1 scan` to refresh constituents."],
        console=console,
    )
    raise typer.Exit(code=1)
```

### Pattern 3: Confirmation Flow with KeyboardInterrupt Handling

Canonical from init.py — `try/except KeyboardInterrupt` wraps ALL interactive sections:

```python
# Source: src/bensdorp1/commands/init.py
SEPARATOR: str = "=" * 64

try:
    console.print(Text(SEPARATOR))
    console.print(Text("Confirm buy"))
    console.print(Text(SEPARATOR))
    console.print()
    render_kv_block({...}, console)
    console.print()
    confirmed = confirm_prompt("Confirm buy?", console=console)
except KeyboardInterrupt:
    console.print()
    console.print(Text("Operation aborted. No changes were made."))
    raise typer.Exit() from None
if not confirmed:
    raise typer.Exit()
```

### Pattern 4: DB Write + Backup + Audit Log

Canonical sequence — always in this order after user confirms:

```python
# Source: src/bensdorp1/commands/init.py (log_event + create_backup pattern)
with engine.connect() as conn:
    result = conn.execute(
        insert(positions).values(
            symbol=symbol.upper(),
            entry_date=entry_dt,
            entry_close=price,
            shares=shares,
            initial_stop=price * 0.93,
            highest_close=price,
            trailing_stop=price * 0.75,
            scan_id=scan_id_or_none,
            closed_at=None,
            exit_price=None,
            realized_pnl=None,
        )
    )
    conn.commit()

create_backup(engine, DATA_DIR / "backups")
log_event(
    engine,
    AuditEventType.BUY_CONFIRMED,
    symbol=symbol.upper(),
    payload={...},
)
print_success("Buy recorded.", body=["Position opened for SYMBOL.", ...], console=console)
```

### Pattern 5: run_migrations ALTER TABLE (D-01)

The ALTER TABLE additions must go in `db/engine.py` after `metadata.create_all`:

```python
# Source: CONTEXT.md §D-01 (prescriptive pattern)
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

def run_migrations(engine: Engine) -> None:
    metadata.create_all(engine, checkfirst=True)
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

### Pattern 6: CliRunner Test

Canonical from test_init.py and test_scan.py — use `CliRunner` from `typer.testing`, patch module-level names at the command module:

```python
# Source: tests/test_commands/test_init.py
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from bensdorp1.cli import app

runner = CliRunner()

def test_buy_happy_path(tmp_path: Path) -> None:
    mock_engine = MagicMock()
    with (
        patch("bensdorp1.commands.buy.DATA_DIR", tmp_path),
        patch("bensdorp1.commands.buy.get_engine", return_value=mock_engine),
        patch("bensdorp1.commands.buy.run_migrations"),
        patch("bensdorp1.commands.buy.create_backup"),
        patch("bensdorp1.commands.buy.log_event"),
    ):
        result = runner.invoke(app, ["buy", "NVDA", "432.50", "23"], input="y\ny\n")
    assert result.exit_code == 0
```

For tests that need real DB operations (INSERT, SELECT, UPDATE), use the shared `db_engine` fixture from `conftest.py` and call the command's internal helper functions directly — or use `patch` to inject the `db_engine` into `get_engine`.

### Anti-Patterns to Avoid

- **Using `typer.echo` or `print()` for output:** All output must go through `console.print(Text(...))` or the `ui.*` functions. `typer.echo` bypasses Rich capture in tests.
- **String interpolation in SQL:** Never compose SQL strings with `f"{symbol}"`. Always use SQLAlchemy `bindparam` or `.values(col=value)` syntax.
- **`sys.exit()` instead of `raise typer.Exit()`:** The project standard is `raise typer.Exit()` (exit 0) and `raise typer.Exit(code=1)` (exit 1). `sys.exit()` causes test harness problems with CliRunner.
- **Calling `confirm_prompt` outside try/except:** `confirm_prompt` re-raises `KeyboardInterrupt`. Any interactive section must be wrapped in `try/except KeyboardInterrupt`.
- **Using `positions.c.entry_close` as "entry price" variable name:** The column is `entry_close` (not `entry_price`). Confusing the column name is a common mistake.
- **Using `positions.closed_at IS NOT NULL` for open position check without parameterized WHERE:** Use `where(positions.c.closed_at == None)` (SQLAlchemy translates to `IS NULL`).
- **Forgetting `conn.commit()` after writes:** SQLAlchemy 2.0 requires explicit `conn.commit()` in `engine.connect()` context managers.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NYSE trading day count between dates | Custom calendar arithmetic | `get_trading_days(entry_date, sell_date)` from `bensdorp1.data` | Already verified, tested, handles holidays |
| P&L dollar formatting | `f"${pnl:,.2f}"` inline | `format_pnl(value)` from `bensdorp1.ui` | Handles sign prefix correctly; consistent with style guide |
| Percentage formatting | `f"{pct:.1f}%"` inline | `format_pct(value)` from `bensdorp1.ui` | Always shows sign (`+`/`-`); consistent with style guide |
| Price formatting | `f"${price:,.2f}"` inline | `format_price(value)` from `bensdorp1.ui` | Consistent formatting |
| KV block alignment | Manual padding | `render_kv_block(data, console)` from `bensdorp1.ui` | Correct alignment per rule 6.4; markup injection protected |
| Before/after diff table | Custom table formatting | `render_table(columns, rows, console=console)` from `bensdorp1.ui` | Minimalist style per rules 6.8/6.9/6.31 |
| `[y/n]` prompt | `input("y/n?")` inline | `confirm_prompt(message, console=console)` from `bensdorp1.ui` | Handles Ctrl+C, re-prompts on invalid input |
| Audit log insertion | Direct `insert(audit_log)` | `log_event(engine, event_type, symbol, payload)` from `bensdorp1.db` | Handles timestamps, JSON serialization |
| Database backup | `shutil.copy` | `create_backup(engine, DATA_DIR / "backups")` from `bensdorp1.db` | Uses sqlite3.Connection.backup() for consistency; handles latest.db |

**Key insight:** All non-trivial operations (calendar arithmetic, formatting, prompting, logging, backup) have already been implemented and tested in earlier phases. Phase 8 is about wiring them together correctly.

---

## Critical Codebase Facts

### Schema: Verified Column Names

The `positions` table columns (verified from `src/bensdorp1/db/schema.py`):

| Column | Type | Nullable | Phase 8 Notes |
|--------|------|----------|---------------|
| `id` | Integer PK | No | Auto-increment |
| `symbol` | Text | No | Store uppercase |
| `entry_date` | DateTime(timezone=True) | No | = buy date; always UTC |
| `entry_close` | Float | No | = buy price (confusingly named `entry_close`) |
| `shares` | Integer | No | |
| `initial_stop` | Float | No | = `entry_close * 0.93` |
| `highest_close` | Float | No | = `entry_close` at buy time |
| `trailing_stop` | Float | No | = `entry_close * 0.75` at buy time |
| `scan_id` | Integer FK scans.id | Yes | NULL = off-signal |
| `closed_at` | DateTime(timezone=True) | Yes | NULL = open position |
| `exit_price` | Float | Yes | NULL when open |
| `realized_pnl` | Float | Yes | NULL when open |
| `closed_reason` | Text | Yes | **NEW — added via ALTER TABLE** |
| `closed_manual_reason` | Text | Yes | **NEW — added via ALTER TABLE** |

The partial unique index `ix_positions_open_symbol` (on `symbol WHERE closed_at IS NULL`) enforces the no-duplicate-open-position rule at the database level. The CLI should also check before inserting to give a user-friendly error — not just rely on the SQLite integrity error.

### Schema: scan_candidates Columns

From `src/bensdorp1/db/schema.py`:
- `id`, `scan_id` (FK scans.id), `symbol` (Text), `rank` (Integer), `roc200` (Float), `close` (Float), `suggested_shares` (Integer)
- Unique index on `(scan_id, rank)` and `(scan_id, symbol)`

For the on-signal check (D-05): query `scan_candidates WHERE scan_id = ? AND symbol = ? AND rank <= 10`.

### Schema: scan_exit_triggers Reason Values

Verified from `src/bensdorp1/commands/_scan_engine.py` (lines 580-583):

```python
reason: str = (
    "Trailing stop" if pos.trailing_stop >= pos.initial_stop else "Initial stop"
)
```

The `reason` column stores exactly the strings `"Trailing stop"` or `"Initial stop"`. The `sell` command maps these to `closed_reason` values: `"Trailing stop"` → `"stop_trailing"`, `"Initial stop"` → `"stop_initial"` (D-12).

### AuditEventType Enum: All Phase 8 Members Exist

Verified from `src/bensdorp1/db/audit.py` — all four required enum members already exist:

| Member | String value |
|--------|-------------|
| `AuditEventType.BUY_CONFIRMED` | `"buy_confirmed"` |
| `AuditEventType.SELL_CONFIRMED` | `"sell_confirmed"` |
| `AuditEventType.SELL_MANUAL` | `"sell_manual"` |
| `AuditEventType.TRANSACTION_CORRECTED` | `"transaction_corrected"` |

No changes to `audit.py` needed.

### UI Public Surface: All Phase 8 Functions Exist

Verified from `src/bensdorp1/ui/__init__.py`:

| Function | Use in Phase 8 |
|----------|----------------|
| `confirm_prompt(message, *, console)` | All three confirmation prompts |
| `render_kv_block(data, console)` | Buy/sell/fix preview blocks |
| `render_table(columns, rows, *, console)` | Fix before/after diff |
| `format_price(value)` → `"$X,XXX.XX"` | All price display |
| `format_pnl(value)` → `"+/-$X,XXX.XX"` | P&L dollar amount |
| `format_pct(value)` → `"+/-X.X%"` | P&L percentage |
| `format_days(n)` → `"N days"` / `"1 day"` | Days held |
| `format_date(d)` → `"YYYY-MM-DD"` | Date display |
| `print_error(title, *, data, body, actions, console)` | Validation errors |
| `print_warning(title, *, body, console)` | Off-signal warning |
| `print_success(title, *, body, console)` | Completion messages |
| `print_info(title, *, body, console)` | No-changes message in fix |
| `text_prompt(label, *, console)` | Fix: free-text field input |
| `number_prompt(label, unit, *, console)` | Fix: numeric field input |

`format_pnl` exists in `ui/__init__.py` and `ui/styles.py`. It formats the dollar value only (e.g. `"+$215.00"`). The combined P&L display for sell (`"-$215.00 (-2.4%)"`) requires composing `format_pnl` + `format_pct`:

```python
# Compose combined P&L string (verified: format_pnl and format_pct both exist)
pnl_display = f"{format_pnl(realized_pnl)} ({format_pct(realized_pnl_pct)})"
```

### calendar.py: days_held Calculation

The `get_trading_days(start, end)` function (verified from `src/bensdorp1/data/calendar.py`) returns an inclusive `pd.DatetimeIndex`. For `days_held`:

```python
from bensdorp1.data import get_trading_days
from datetime import date

days_held: int = len(get_trading_days(entry_date, sell_date))
```

Note: `get_trading_days` is inclusive of both endpoints. For "days held" semantics (47 trading days between entry and sell), this is the correct calculation.

### Engine.py: run_migrations Current State

Current `run_migrations` (verified from `src/bensdorp1/db/engine.py`):

```python
def run_migrations(engine: Engine) -> None:
    """Create all tables idempotently. Called only from bensdorp1 init (Phase 6)."""
    metadata.create_all(engine, checkfirst=True)
```

Phase 8 adds `closed_reason` and `closed_manual_reason` columns via ALTER TABLE after the `create_all` call. The docstring should also be updated to reflect that all commands call it, not just `init`.

### Print_warning Signature

From `src/bensdorp1/ui/messages.py` (verified):

```python
def print_warning(
    title: str,
    *,
    data: dict[str, str] | None = None,
    body: list[str] | None = None,
    impact: dict[str, str] | None = None,
    actions: list[str] | None = None,
    console: Console | None = None,
) -> None:
```

For the off-signal warning (D-06), use:

```python
print_warning(
    f"{symbol} was not in the top 10 buy candidates of the latest scan.",
    body=["This buy will be recorded as off-signal in the audit log."],
    console=console,
)
console.print()
confirmed = confirm_prompt("Continue?", console=console)
```

### Existing Stub Signatures to Replace

All three command stubs have `def buy() -> None`, `def sell() -> None`, `def fix() -> None` with no parameters. The full signatures will be:

```python
# buy.py
def buy(
    symbol: str = typer.Argument(...),
    price: float = typer.Argument(...),
    shares: int = typer.Argument(...),
    date: str | None = typer.Option(None, "--date"),
) -> None: ...

# sell.py
def sell(
    symbol: str = typer.Argument(...),
    price: float = typer.Argument(...),
    date: str | None = typer.Option(None, "--date"),
    manual: str | None = typer.Option(None, "--manual"),
) -> None: ...

# fix.py
def fix(
    symbol: str = typer.Argument(...),
    date: str | None = typer.Option(None, "--date"),
) -> None: ...
```

mypy `disallow_untyped_decorators = false` is already set for `bensdorp1.commands.*` in `pyproject.toml` — the `@app.command()` decorator does not require a type override.

---

## Common Pitfalls

### Pitfall 1: Partial Unique Index vs. User Error

**What goes wrong:** The `ix_positions_open_symbol` partial unique index raises a `sqlalchemy.exc.IntegrityError` if you try to insert a second open position for the same symbol. If the CLI doesn't check first, the user sees an ugly traceback.

**Why it happens:** Relying on the DB constraint without a pre-check.

**How to avoid:** Always check for an open position with `SELECT ... WHERE closed_at IS NULL AND symbol = ?` before attempting the INSERT. On collision, print `print_error("An open position for SYMBOL already exists.")` and `raise typer.Exit(code=1)`.

**Warning signs:** `IntegrityError: UNIQUE constraint failed` appearing in test output.

### Pitfall 2: scan_exit_triggers Query for sell — Most Recent vs. Earliest

**What goes wrong:** D-12 says "use the earliest trigger row to get the original trigger reason." If you query with `ORDER BY id DESC LIMIT 1` you get the latest, not the earliest.

**Why it happens:** Natural tendency to query "latest" rather than "original."

**How to avoid:** Query `ORDER BY scan_exit_triggers.c.id ASC LIMIT 1` or `ORDER BY triggered_date ASC LIMIT 1` to get the original trigger reason.

### Pitfall 3: entry_date vs. entry_close Naming

**What goes wrong:** The `positions` table column for buy price is named `entry_close`, not `entry_price`. Using `entry_price` in a SQL query produces `OperationalError: no such column`.

**Why it happens:** The column name comes from the trading domain (daily close price at entry), but commands use "price" in their UI.

**How to avoid:** Always reference `positions.c.entry_close` for the buy price, `positions.c.entry_date` for the date. Map at the boundary: `entry_close` (DB) = "price" (UI).

### Pitfall 4: DateTime vs. date Objects for days_held

**What goes wrong:** `get_trading_days(start, end)` accepts `date` objects. If you pass a `datetime` (timezone-aware, from the DB), it may fail or produce wrong results.

**Why it happens:** DB stores `DateTime(timezone=True)` which returns timezone-aware `datetime`. `get_trading_days` uses `isoformat()` internally.

**How to avoid:** Always call `.date()` on datetime objects before passing to `get_trading_days`:

```python
entry_d: date = position_row.entry_date.date()
sell_d: date = sell_date_param  # date from --date or today
days_held = len(get_trading_days(entry_d, sell_d))
```

### Pitfall 5: On-Signal Check — Most Recent Scan Date Logic

**What goes wrong:** D-05 says "find the most recent scan with `scan_date <= DATE`." If you query `ORDER BY scan_date DESC LIMIT 1` without the `<= DATE` filter, you might get a scan from the future (if `--date` is in the past).

**Why it happens:** The `--date` parameter allows backdating buys.

**How to avoid:**

```python
with engine.connect() as conn:
    scan_row = conn.execute(
        select(scans.c.id, scans.c.scan_date)
        .where(scans.c.scan_date <= buy_date_utc)
        .order_by(scans.c.scan_date.desc())
        .limit(1)
    ).fetchone()
```

### Pitfall 6: fix Command — Closed Position Date Column

**What goes wrong:** When fix targets a closed position (sell), the sell date is in `positions.c.closed_at`, not a separate column. `exit_price` is the sell price, `closed_manual_reason` is the manual reason.

**Why it happens:** The positions table doubles as both open and closed position storage.

**How to avoid:** Map explicitly: for sell fix, editable fields are `closed_at` (date), `exit_price` (price), `closed_manual_reason` (reason if `closed_reason == "manual"`).

### Pitfall 7: Separator Width

**What goes wrong:** The spec §7.3 shows `================================================================` which is 64 `=` characters. init.py and _scan_engine.py both define `SEPARATOR: str = "=" * 64`. Using a different width breaks visual consistency.

**Why it happens:** Counting by eye.

**How to avoid:** Import or duplicate `SEPARATOR = "=" * 64` — same constant used in all three command files.

---

## Code Examples

### Buy: On-Signal Query

```python
# Source: Derived from bensdorp1/db/schema.py column definitions (VERIFIED)
from sqlalchemy import select
from bensdorp1.db.schema import scan_candidates, scans

# Step 1: find most recent scan on or before buy_date
with engine.connect() as conn:
    scan_row = conn.execute(
        select(scans.c.id, scans.c.scan_date)
        .where(scans.c.scan_date <= buy_date_utc)
        .order_by(scans.c.scan_date.desc())
        .limit(1)
    ).fetchone()

if scan_row is None:
    on_signal = False
    signal_scan_id: int | None = None
else:
    # Step 2: check if symbol appears with rank <= 10
    with engine.connect() as conn:
        candidate_row = conn.execute(
            select(scan_candidates.c.rank)
            .where(
                (scan_candidates.c.scan_id == scan_row.id)
                & (scan_candidates.c.symbol == symbol.upper())
                & (scan_candidates.c.rank <= 10)
            )
        ).fetchone()
    on_signal = candidate_row is not None
    signal_scan_id = int(scan_row.id) if on_signal else None
    signal_rank = int(candidate_row.rank) if candidate_row is not None else None
```

### Sell: Trigger Lookup and Reason Mapping

```python
# Source: Derived from scan_exit_triggers column definitions (VERIFIED)
from bensdorp1.db.schema import scan_exit_triggers

with engine.connect() as conn:
    trigger_row = conn.execute(
        select(scan_exit_triggers.c.reason)
        .where(scan_exit_triggers.c.position_id == position_id)
        .order_by(scan_exit_triggers.c.id.asc())
        .limit(1)
    ).fetchone()

if trigger_row is None:
    # D-13: error path
    print_error(
        f"No exit trigger on record for {symbol}.",
        body=["To record a manual sell, use: bensdorp1 sell SYMBOL PRICE --manual REASON"],
        console=console,
    )
    raise typer.Exit(code=1)

_REASON_MAP: dict[str, str] = {
    "Trailing stop": "stop_trailing",
    "Initial stop": "stop_initial",
}
closed_reason = _REASON_MAP.get(trigger_row.reason, "stop_trailing")
```

### Sell: P&L Combined Display

```python
# Source: ui/styles.py format_pnl and format_pct (VERIFIED they exist)
from bensdorp1.ui import format_pnl, format_pct

realized_pnl: float = (sell_price - entry_price) * shares
realized_pnl_pct: float = (sell_price / entry_price - 1) * 100
pnl_display: str = f"{format_pnl(realized_pnl)} ({format_pct(realized_pnl_pct)})"
# Result: "-$215.00 (-2.4%)" or "+$432.50 (+5.1%)"
```

### Fix: Field-by-Field Input with Default

```python
# Source: Spec §7.5 Step 2 — field prompt format with current value as default
# text_prompt and number_prompt exist in ui (VERIFIED from ui/__init__.py)
import datetime

# Date field: show current, accept Enter to keep
raw_date = input(f"Date    [{format_date(current_date)}]:  ").strip()
new_date = datetime.date.fromisoformat(raw_date) if raw_date else current_date

# Price field
raw_price = input(f"Price   [{format_price(current_price)}]:  ").strip()
# strip leading "$" and commas before float()
clean_price = raw_price.lstrip("$").replace(",", "")
new_price = float(clean_price) if clean_price else current_price

# Shares field
raw_shares = input(f"Shares  [{current_shares}]:  ").strip()
new_shares = int(raw_shares) if raw_shares else current_shares
```

Note: The spec's field prompts use raw `input()` with format `Field   [current]:  `. This is different from `text_prompt` and `number_prompt` (which have different prompt formats). Use raw `input()` for the fix field loop, wrapped in the outer `try/except KeyboardInterrupt`.

### Fix: Before/After Diff Table

```python
# Source: ui/tables.py render_table signature (VERIFIED)
from bensdorp1.ui import render_table

# Build diff rows for changed fields only
diff_rows: list[list[str]] = []
if new_price != current_price:
    diff_rows.append(["Price", format_price(current_price), format_price(new_price)])
if new_shares != current_shares:
    diff_rows.append(["Shares", str(current_shares), str(new_shares)])
if new_date != current_date:
    diff_rows.append(["Date", format_date(current_date), format_date(new_date)])

render_table(
    columns=[("Field", "left"), ("Before", "left"), ("After", "left")],
    rows=diff_rows,
    console=console,
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `typer.confirm()` for prompts | `confirm_prompt()` from `ui/prompts.py` | Phase 5 | Consistent Ctrl+C handling; re-prompts on invalid input |
| `sys.exit()` for exit | `raise typer.Exit(code=N)` | Phase 6 | CliRunner-compatible; no SystemExit propagation in tests |
| Direct `metadata.create_all` in commands | `run_migrations(engine)` from `db/engine.py` | Phase 6 | Idempotent; picks up ALTER TABLE automatically |

**Deprecated/outdated:**
- The stub implementations in `buy.py`, `sell.py`, `fix.py`: these contain `typer.echo("Not yet implemented.")` — this is intentionally temporary and will be replaced entirely.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The spec's fix flow uses raw `input()` calls (not `text_prompt`/`number_prompt`) for field-by-field input because the prompt format `"Field   [current]:  "` doesn't match either helper's format | Code Examples — Fix | If wrong, use `text_prompt`/`number_prompt` instead; low risk since `input()` is always valid and tested |
| A2 | `days_held` semantics: `len(get_trading_days(entry_date, sell_date))` gives the inclusive count (both endpoints included) which matches spec's "47 trading days" display | Critical Codebase Facts — calendar.py | If off-by-one, days_held would be N±1; visible in sell confirmation |

---

## Open Questions

1. **fix — `--date DATE` parameter semantics**
   - What we know: The parameter is specified as `fix SYMBOL [--date DATE]` in the spec.
   - What's unclear: The CONTEXT.md does not clarify what `--date` does for fix. The CONTEXT.md D-19/D-20 don't mention `--date` filtering behavior.
   - Recommendation: The planner should treat `--date DATE` in `fix` as unused in this phase (the spec §7.5 doesn't show it in the flow). If the fix command signature includes `--date`, it can accept it silently without using it — or the planner can ask before coding.

2. **Sell confirmation — "Closing reason" display label**
   - What we know: The spec §7.4 shows `Closing reason:   Trailing stop` (human-readable label), but `closed_reason` DB value is `"stop_trailing"`. The display is the human label, not the DB value.
   - What's unclear: For normal sells, use the original `scan_exit_triggers.reason` string (`"Trailing stop"` or `"Initial stop"`) for display, not the mapped `closed_reason` value.
   - Recommendation: Display `trigger_row.reason` in the confirmation preview; store `closed_reason` as the mapped value.

---

## Environment Availability

> Step 2.6: SKIPPED (no new external dependencies — phase uses only packages already installed and tested through Phase 7)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (if present) / default discovery |
| Quick run command | `uv run pytest tests/test_commands/test_buy.py tests/test_commands/test_sell.py tests/test_commands/test_fix.py -x` |
| Full suite command | `uv run pytest --cov=bensdorp1 --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CMD-06 | buy: constituent validation rejects unknown symbol | integration | `uv run pytest tests/test_commands/test_buy.py::test_invalid_constituent -x` | ❌ Wave 0 |
| CMD-06 | buy: duplicate open position rejected | integration | `uv run pytest tests/test_commands/test_buy.py::test_duplicate_open_position -x` | ❌ Wave 0 |
| CMD-06 | buy: off-signal warning shown when not in top 10 | integration | `uv run pytest tests/test_commands/test_buy.py::test_off_signal_warning -x` | ❌ Wave 0 |
| CMD-06 | buy: happy path on-signal creates position | integration | `uv run pytest tests/test_commands/test_buy.py::test_happy_path_on_signal -x` | ❌ Wave 0 |
| CMD-06 | buy: abort on off-signal `n` answer | integration | `uv run pytest tests/test_commands/test_buy.py::test_off_signal_abort -x` | ❌ Wave 0 |
| CMD-07 | sell: no exit trigger returns error code 1 | integration | `uv run pytest tests/test_commands/test_sell.py::test_no_exit_trigger -x` | ❌ Wave 0 |
| CMD-07 | sell: happy path normal sell closes position | integration | `uv run pytest tests/test_commands/test_sell.py::test_happy_path_normal -x` | ❌ Wave 0 |
| CMD-07 | sell: --manual creates manual sell record | integration | `uv run pytest tests/test_commands/test_sell.py::test_manual_sell -x` | ❌ Wave 0 |
| CMD-08 | fix: no transaction found returns error code 1 | integration | `uv run pytest tests/test_commands/test_fix.py::test_no_transaction -x` | ❌ Wave 0 |
| CMD-08 | fix: no changes → Info message, no DB write | integration | `uv run pytest tests/test_commands/test_fix.py::test_no_changes -x` | ❌ Wave 0 |
| CMD-08 | fix: price change updates initial_stop in DB | integration | `uv run pytest tests/test_commands/test_fix.py::test_price_change_updates_stop -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_commands/ -x --tb=short`
- **Per wave merge:** `uv run pytest --cov=bensdorp1 --cov-report=term-missing`
- **Phase gate:** Full suite green + mypy strict + ruff before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_commands/test_buy.py` — covers CMD-06 scenarios
- [ ] `tests/test_commands/test_sell.py` — covers CMD-07 scenarios
- [ ] `tests/test_commands/test_fix.py` — covers CMD-08 scenarios

*(Existing test infrastructure is sufficient — no new fixtures or framework installs needed. The `db_engine` fixture in `conftest.py` is reusable for unit-level DB assertions.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user CLI, no auth |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | Single-user tool |
| V5 Input Validation | yes | SQLAlchemy parameterized queries; explicit price/shares > 0 checks; ISO date parse with `datetime.date.fromisoformat()` |
| V6 Cryptography | no | No encryption needed |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via symbol/reason inputs | Tampering | SQLAlchemy parameterized queries (`.values(col=value)`, never f-string SQL) |
| Rich markup injection in user-supplied strings | Tampering | `console.print(..., markup=False, highlight=False)` or wrap in `Text()`; `render_kv_block` already uses `markup=False` |
| Negative/zero price bypass | Tampering | Explicit `price > 0` and `shares > 0` validation before ANY DB write or confirmation display |
| Invalid ISO date crash | DoS | `datetime.date.fromisoformat(raw)` raises `ValueError` — catch and print error, re-prompt or exit code 1 |

---

## Project Constraints (from CLAUDE.md)

| Directive | Applies to Phase 8 |
|-----------|-------------------|
| Python 3.11+ | Yes — all type hints must be 3.11-compatible (`X \| Y` union syntax OK) |
| `uv` as package manager | Yes — tests run via `uv run pytest` |
| SQLite only, no external services | Yes — all DB ops use existing SQLite engine |
| yfinance only for market data | N/A — phase 8 does no data fetching |
| mypy strict mode | Yes — all command files must pass `uv run mypy src/bensdorp1/commands/buy.py sell.py fix.py --strict` |
| `disallow_untyped_decorators = false` for `bensdorp1.commands.*` | Yes — already in pyproject.toml; `@app.command()` decorator does not need an override |
| ruff format with `line-ending = "lf"` | Yes — enforced by CI |
| No extensibility design | Yes — no abstract base classes, no plugin hooks |
| `raise typer.Exit()` not `sys.exit()` | Yes — enforced in all command exit paths |
| `Text()` wrapping for all `console.print()` calls | Yes — all string literals passed to `console.print` must be wrapped |
| SQLAlchemy parameterized queries only | Yes — no f-string SQL anywhere |
| `engine.connect()` context manager with explicit `conn.commit()` | Yes — all DB writes use this pattern |

---

## Sources

### Primary (HIGH confidence)
- `src/bensdorp1/db/schema.py` — exact column names, types, and indexes for all 7 tables
- `src/bensdorp1/db/audit.py` — AuditEventType enum members verified
- `src/bensdorp1/db/engine.py` — run_migrations current implementation verified
- `src/bensdorp1/db/backup.py` — create_backup signature verified
- `src/bensdorp1/ui/__init__.py` — public UI surface: all 20 exported names verified
- `src/bensdorp1/ui/styles.py` — format_pnl, format_pct, format_price, render_kv_block implementations verified
- `src/bensdorp1/ui/messages.py` — print_warning, print_error, print_info, print_success signatures verified
- `src/bensdorp1/ui/prompts.py` — confirm_prompt, text_prompt, number_prompt signatures verified
- `src/bensdorp1/commands/init.py` — canonical patterns: SEPARATOR, KeyboardInterrupt handling, confirm_prompt usage, render_kv_block, create_backup, log_event call sequence
- `src/bensdorp1/commands/scan.py` — canonical patterns: DB path, get_engine, run_migrations call at entry
- `src/bensdorp1/commands/_scan_engine.py` — exact reason strings in scan_exit_triggers: `"Trailing stop"` and `"Initial stop"`
- `src/bensdorp1/data/calendar.py` — get_trading_days signature and inclusive semantics
- `tests/test_commands/test_init.py` — CliRunner test patterns (patch at module level, MagicMock engine)
- `.planning/phases/08-confirmation-commands/08-CONTEXT.md` — all locked decisions D-01 through D-26
- `.planning/Bensdorp_1.md` §7.3, §7.4, §7.5 — exact UI output formats
- `CLAUDE.md` — library versions, pyproject.toml structure, mypy strict configuration

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` CMD-06, CMD-07, CMD-08, UI-07 — one-line requirement descriptions

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; no new dependencies
- Schema facts: HIGH — read directly from schema.py
- Architecture: HIGH — all patterns verified from existing command implementations
- Pitfalls: HIGH — derived from actual code structure and test patterns
- UI format: HIGH — verified against Bensdorp_1.md spec and ui/ implementation

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (stable codebase; no fast-moving dependencies in this phase)
