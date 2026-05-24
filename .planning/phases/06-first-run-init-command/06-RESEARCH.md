# Phase 6: First-Run Init Command - Research

**Researched:** 2026-05-24
**Domain:** Typer CLI command implementation, interactive multi-step flows, SQLite init patterns
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Guard condition is DB file existence: `(DATA_DIR / "data" / "bensdorp1.db").exists()`. No schema inspection.
- **D-02:** Guard error uses `print_error()` and mentions both recovery paths: delete file + re-init OR `bensdorp1 restore PATH`.
- **D-03:** Minimum valid cash: `> 0`. Any positive float accepted. Zero, negative, and non-numeric are all invalid.
- **D-04:** On invalid cash (≤ 0): re-prompt with `"Error: Cash must be greater than zero."`. `number_prompt()` signature unchanged (returns `float`). Positive-value guard loop wraps `number_prompt()` in the command.
- **D-05:** `init` wraps cash-entry block in `try/except KeyboardInterrupt`, prints `"Operation aborted. No changes were made."` via console, exits with `raise typer.Exit()`.
- **D-06:** No cleanup on Ctrl+C or network failure. Partial DB stays. Guard error on re-run explains recovery.
- **D-07:** Spec's "Continue? [y/n]" (Step 1) is the only escape hatch before execution. After cash confirmed, setup starts immediately.
- **D-08:** Moderate test coverage with `CliRunner` (in-process) + mocked data layer. Tests go to `tests/test_commands/test_init.py`. Four required scenarios: guard fires, happy path, cash validation, Ctrl+C during cash entry.

### Claude's Discretion

- Exact `tests/test_commands/` directory structure (`__init__.py` or not, conftest placement) — follow existing `tests/` layout.
- Whether to extract `_run_init()` helper within `init.py` or keep flat — decide based on testability needs.
- Exact guard error message wording (beyond the two recovery paths) — sentence case, plain text, `print_error()` severity prefix.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CMD-01 | `bensdorp1 init` — interactive first-run setup: creates ~/bensdorp1/ directory tree, SQLite DB, fetches constituents, downloads 220-day price history, records initial cash; refuses if DB already exists | All data-layer APIs confirmed ready; progress API confirmed; test pattern confirmed |
</phase_requirements>

---

## Summary

Phase 6 is a pure integration task: wire together already-implemented primitives (`run_migrations`, `get_constituents`, `update_price_data`, `create_backup`, `log_event`, `feedback.multi_step`, `number_prompt`, `confirm_prompt`, `print_error`) into the `init` command. No new subpackages, no new primitives, no schema changes. The spec flow in §7.1 is the canonical output contract — pixel-perfect match is required.

The primary risk is test architecture: `CliRunner` runs commands in-process, which means `input()` calls inside prompts are captured differently than real TTY input. Existing test patterns in the repo use module-level `patch` for external calls but there is no existing command test that exercises interactive prompts via `CliRunner`. The planner must address how to feed simulated user input (the `input` parameter of `CliRunner.invoke`) through multi-step prompts.

Cash storage uses the existing `config` table (key=`"available_cash"`, value=TEXT float string). No new table or column is needed. The `config` table is already in the schema (`schema.py` line 22-28); the `init` command is the first writer.

**Primary recommendation:** Implement `init.py` as a flat command function (no `_run_init()` extraction needed — `CliRunner` can test the command function directly). Keep all prompt loops inside the command body; test them by passing `input=` to `CliRunner.invoke()`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Guard check (DB exists) | CLI command | config.py | Path check is a CLI pre-condition; `DATA_DIR` resolves via config |
| Directory creation | CLI command | db/engine.py | `_build_engine()` calls `path.parent.mkdir(parents=True, exist_ok=True)` automatically; backups dir created by `create_backup()` |
| Schema initialization | db/engine.py | — | `run_migrations(engine)` is the owned API |
| Constituents fetch | data/constituents.py | — | `get_constituents(engine)` owns this entirely |
| Price download | data/prices.py | — | `update_price_data(engine, symbols)` owns this entirely |
| Cash storage | CLI command | db/schema (config table) | Direct SQLAlchemy upsert into `config` table; no dedicated helper exists yet |
| Audit event | db/audit.py | — | `log_event(engine, AuditEventType.SYSTEM_INITIALIZED, ...)` |
| Backup | db/backup.py | — | `create_backup(engine, DATA_DIR / "backups")` |
| Progress display | ui/progress.py | — | `feedback.multi_step(3)` with step() contexts |
| User prompts | ui/prompts.py | — | `confirm_prompt()`, `number_prompt()` |
| Error messages | ui/messages.py | — | `print_error()` for guard; `console.print()` for abort |

---

## Standard Stack

No new packages required. Phase 6 installs zero external dependencies. All required libraries are already in `pyproject.toml`.

### Existing Packages Used

| Library | Already in deps | Purpose in this phase |
|---------|----------------|----------------------|
| typer | Yes | `@app.command()` decorator, `raise typer.Exit()` |
| rich | Yes | `Console` for output; `Text()` to block markup injection |
| sqlalchemy | Yes | INSERT into `config` table for cash storage |
| (all data/db/ui modules) | Yes | Already implemented in Phases 2–5 |

### No New Packages

No `npm install` or `pip install` equivalent needed. No Package Legitimacy Audit section required.

---

## Architecture Patterns

### System Architecture Diagram

```
bensdorp1 init
      |
      v
[Guard: DB file exists?] --YES--> print_error() + raise typer.Exit(1)
      |
      NO
      |
      v
[Step 1: Welcome screen]
      |
      v
[confirm_prompt("Continue?")]
      |
     NO ------> raise typer.Exit(0)
      |
     YES
      |
      v
[Step 2: Cash declaration loop]
  number_prompt() --> validate > 0 --> re-prompt if ≤ 0
  confirm_prompt("Confirm?")
  try/except KeyboardInterrupt --> print abort + raise typer.Exit(0)
      |
      v
[Step 3: Setup execution]
  get_engine(DB_PATH) --> run_migrations(engine)
  with feedback.multi_step(3) as ms:
    [1/3] get_constituents(engine) --> SpinnerContext
    [2/3] verify secondary           --> SpinnerContext  (calls refresh_constituents internally)
    [3/3] update_price_data()        --> TrackContext(total=len(symbols))
  _store_cash(engine, amount)         --> INSERT/REPLACE into config
  log_event(engine, SYSTEM_INITIALIZED, ...)
  create_backup(engine, DATA_DIR / "backups")
      |
      v
[Step 4: Completion summary]
  print_success() or direct console.print() with === border
```

### Recommended Project Structure

No new directories required beyond:
```
tests/
└── test_commands/       # NEW directory
    ├── __init__.py      # Empty (matches test_ui/__init__.py and test_strategy/__init__.py pattern)
    └── test_init.py     # CLI + unit tests for init command
```

### Pattern 1: Command with interactive flow

The existing pattern from `_app.py` and `commands/help.py` shows all commands use `@app.command()` with `-> None` return type and `raise typer.Exit()` for early exits.

```python
# Source: src/bensdorp1/commands/init.py (to be implemented)
# Pattern derived from: src/bensdorp1/_app.py + CONTEXT.md code_context
from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
import typer

@app.command(rich_help_panel="Setup")
def init() -> None:
    """First-run setup: create data directory, download history, record cash."""
    # Guard
    db_path = DATA_DIR / "data" / "bensdorp1.db"
    if db_path.exists():
        print_error(
            "System already initialized.",
            actions=[
                "Delete the file and run `bensdorp1 init` again.",
                "Run `bensdorp1 restore PATH` to replace with a backup.",
            ],
        )
        raise typer.Exit(1)
    # ... flow continues
```

[VERIFIED: codebase] — `@app.command(rich_help_panel="Setup")` already in the stub; `raise typer.Exit()` is the project-wide pattern.

### Pattern 2: MultiStepContext usage

```python
# Source: src/bensdorp1/ui/progress.py (verified)
with feedback.multi_step(3) as ms:
    with ms.step("Fetching S&P 500 constituents"):
        # SpinnerContext (no total) — unknown duration
        constituents = get_constituents(engine)
    # After context exits, MultiStepContext prints "[1/3] Fetching S&P 500 constituents... done."
    console.print("      Source: Wikipedia")
    console.print(f"      Stocks found: {len(constituents)}")

    with ms.step("Verifying against secondary source"):
        # SpinnerContext — secondary cross-check is internal to get_constituents
        pass  # cross-check already happened in step 1; step 2 is a display beat

    symbols = list(constituents.keys())
    with ms.step("Downloading price history", total=len(symbols)) as track:
        # TrackContext — one advance() per symbol downloaded
        # BUT: update_price_data() does a bulk download, not per-symbol callbacks
        # See Pitfall 2 below for the resolution.
        update_price_data(engine, symbols)
```

[VERIFIED: codebase] — `MultiStepContext.step()` signature confirmed in `progress.py`.

### Pattern 3: Cash storage in config table

```python
# Source: db/schema.py (verified) — config table has key, value, updated_at columns
from datetime import UTC, datetime
from sqlalchemy import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from bensdorp1.db.schema import config as config_table

def _store_cash(engine: Engine, amount: float) -> None:
    with engine.connect() as conn:
        stmt = (
            sqlite_insert(config_table)
            .values(key="available_cash", value=str(amount), updated_at=datetime.now(UTC))
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": str(amount), "updated_at": datetime.now(UTC)},
            )
        )
        conn.execute(stmt)
        conn.commit()
```

[VERIFIED: codebase] — `config` table schema confirmed in `schema.py`; `sqlite_insert` with `on_conflict_do_update` is already used in `prices.py`.

### Pattern 4: CliRunner test with simulated input

```python
# Source: tests/test_cli.py (existing pattern), typer.testing docs [ASSUMED for input=]
from typer.testing import CliRunner
from bensdorp1.cli import app
from unittest.mock import patch

runner = CliRunner()

def test_init_happy_path(tmp_path):
    with patch("bensdorp1.commands.init.DATA_DIR", tmp_path), \
         patch("bensdorp1.commands.init.get_constituents", return_value={"AAPL": "Apple"}), \
         patch("bensdorp1.commands.init.update_price_data"), \
         patch("bensdorp1.commands.init.run_migrations"), \
         patch("bensdorp1.commands.init.create_backup"), \
         patch("bensdorp1.commands.init.log_event"):
        # Simulate: "y" for Continue, "50000" for cash, "y" for Confirm
        result = runner.invoke(app, ["init"], input="y\n50000\ny\n")
    assert result.exit_code == 0
```

[ASSUMED] — `CliRunner.invoke(input=)` feeds a string to `stdin` for `input()` calls; this is standard Typer/Click testing behavior but not directly verified against this specific version.

### Pattern 5: `_tilde_path()` helper

```python
# Source: CONTEXT.md §Specific Ideas (canonical)
def _tilde_path(p: Path) -> str:
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)
```

[VERIFIED: codebase] — `Path.home()` and `Path.relative_to()` are stdlib; the exact function is spec-canonical from CONTEXT.md.

### Anti-Patterns to Avoid

- **Using `typer.prompt()` or `typer.confirm()`:** The project uses `input()` directly via `ui/prompts.py` functions. Never use Typer's built-in prompt utilities (Phase 5 decision).
- **Using `sys.exit()`:** Always `raise typer.Exit()` or `raise typer.Exit(1)`. [VERIFIED: codebase] — every command uses this pattern.
- **Rich markup injection in error messages:** Always pass user-controlled strings through `Text()` or use `markup=False`. [VERIFIED: codebase] — established in Phase 5.
- **Printing the expanded absolute path in completion summary:** The spec requires `~/bensdorp1/data/bensdorp1.db`, not `/home/user/bensdorp1/data/bensdorp1.db`. Use `_tilde_path()`.
- **Deep-importing from ui submodules:** Import only from `bensdorp1.ui` (the public surface), never from `bensdorp1.ui.progress` etc. [VERIFIED: codebase] — stated in `ui/__init__.py` docstring.
- **Treating the `---` separator as full-width:** The `---` under "Available cash" is 14 characters (matching the header text length), not full console width. Rule 6.2 is explicit.
- **Calling `get_constituents()` twice for steps 1 and 2:** `get_constituents()` internally calls `refresh_constituents()` if stale. Step 2 ("Verifying against secondary source") represents the cross-check that already happened inside step 1's call. The implementation should call `get_constituents()` once and use step 2 as a display-only beat.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Directory creation | `os.makedirs()` calls | `_build_engine()` + `create_backup()` | `_build_engine()` calls `path.parent.mkdir(parents=True, exist_ok=True)`; `create_backup()` calls `backups_dir.mkdir(parents=True, exist_ok=True)` |
| DB backup | Manual file copy | `create_backup(engine, backups_dir)` | Uses `sqlite3.Connection.backup()` API; file copy can corrupt live DB |
| Schema creation | Raw `CREATE TABLE` SQL | `run_migrations(engine)` | Already idempotent with `checkfirst=True` |
| Constituents fetch | HTTP requests directly | `get_constituents(engine)` | Cross-check, caching, and audit log already handled |
| Price download | yfinance calls directly | `update_price_data(engine, symbols)` | Rate limiting, retry, normalization, persistence all handled |
| Spinner/progress | Custom loop with print | `feedback.multi_step(3)` | Phase 5 implementation is spec-compliant and tested |
| Confirmation prompt | `input("y/n")` inline | `confirm_prompt(message, console=console)` | Re-prompt on invalid, Ctrl+C handling already implemented |
| Number prompt | `float(input(...))` inline | `number_prompt(label, unit, console=console)` | Non-numeric re-prompt already implemented |
| Cash formatting | f-string | `format_price(amount)` from `ui/styles.py` | Consistent `$X,XXX.XX` format |

**Key insight:** Every non-trivial operation in this phase has a pre-built primitive. The init command is ~95% integration, ~5% new logic (the positive-cash guard loop, the `_store_cash()` helper, the `_tilde_path()` helper, and the output text blocks).

---

## Common Pitfalls

### Pitfall 1: `MultiStepContext.step()` prints the label twice

**What goes wrong:** `ms.step("description")` prints `[N/TOTAL] description` when entering, then prints `[N/TOTAL] description... done.` when exiting. If the command also prints detail lines (e.g., "Stocks found: 503") inside the `with` block before the context exits, they appear between the header line and the `done.` line in the terminal.

**Why it happens:** The progress header is printed at `__enter__`; the done line is printed at `__exit__`. Detail lines printed before exit appear inline with the Live display.

**How to avoid:** Print detail lines (Source, Stocks found) AFTER the `with ms.step(...)` block exits, not inside it. The CONTEXT.md `## Specific Ideas` section shows this pattern explicitly.

**Warning signs:** Test output shows detail lines appearing before `done.` text.

### Pitfall 2: `update_price_data()` does not accept a per-symbol callback

**What goes wrong:** Step 3 uses `TrackContext(total=len(symbols))`, which requires calling `.advance(label)` once per symbol. But `update_price_data()` does not expose a callback hook — it downloads in bulk internally.

**Why it happens:** `update_price_data()` was designed for batch use, not streaming progress.

**How to avoid:** Two options:
1. Pass `update_price_data()` a progress callback (requires signature change — violates phase boundary "no changes to data/").
2. Use a SpinnerContext for step 3 (not a TrackContext), since `update_price_data()` is a single call. The spec says step 3 "uses the progress bar layout from rule 6.21", which implies a TrackContext — but this is only achievable if the download loop is driven from the command. Given the no-data-changes constraint, **use SpinnerContext for step 3** and document this deviation in a code comment.

**Resolution:** Use SpinnerContext for step 3 (no total). The spec shows a progress bar for step 3, but that requires a per-symbol callback that doesn't exist without modifying `data/`. The CONTEXT.md code_context says: "Step 3 (price download) uses `ms.step("Downloading price history", total=len(symbols))` to get a `TrackContext`; call `.advance(symbol)` per symbol." This implies the download loop should be driven from `init.py` by iterating over symbols and calling `update_price_data()` for each one individually — but that would bypass the bulk download optimization.

**Correct resolution:** The planner must decide: drive per-symbol from `init.py` (expensive, enables TrackContext) OR call `update_price_data()` once with all symbols (fast, requires SpinnerContext). The CONTEXT.md explicitly says to call `.advance(symbol)` per symbol, which means the intent is per-symbol iteration from the command. This aligns with TrackContext. The planner should implement a per-symbol loop in `init.py` that calls `update_price_data(engine, [symbol])` for each constituent and calls `track.advance(symbol)` after each.

[ASSUMED] — per-symbol loop approach is inferred from CONTEXT.md language; exact performance implications are not verified.

### Pitfall 3: CliRunner captures `input()` only if passed as `input=` kwarg

**What goes wrong:** `runner.invoke(app, ["init"])` with no `input=` argument causes `input()` calls inside prompts to raise `EOFError` in CI, because there is no stdin attached.

**Why it happens:** `CliRunner` by default provides no stdin. All `input()` calls in prompt functions need their stdin provided by `runner.invoke(..., input="...")`.

**How to avoid:** All `runner.invoke` calls for interactive commands MUST pass `input=` with newline-delimited simulated responses matching the exact prompt order.

**Warning signs:** Tests pass locally (with real stdin) but fail in CI with `EOFError` or `StopIteration`.

### Pitfall 4: `test_stub_exits_cleanly` in test_cli.py will break

**What goes wrong:** `test_cli.py` line 41-57 has a parametrized test that asserts `"Not yet implemented."` in the output for `init`. Once Phase 6 replaces the stub, this test will fail.

**Why it happens:** The stub test was written for all 16 stubs; it must be updated once any stub is replaced.

**How to avoid:** Phase 6 must update `test_cli.py` to remove `"init"` from the `test_stub_exits_cleanly` parametrize list (and the `test_help_subcommand_shows_help` list can stay — that tests help text, not behavior).

**Warning signs:** CI fails on `test_stub_exits_cleanly[init]` after implementation.

### Pitfall 5: Cash stored as TEXT in config table — float parsing needed on read

**What goes wrong:** The `config` table stores `value` as `Text`. When other commands later read cash, they must cast `float(row.value)`. If `_store_cash()` stores `str(amount)` directly, it works; but if something stores a repr like `50000.000000001` due to float precision, later display differs from what the user confirmed.

**How to avoid:** Store `str(round(amount, 2))` or use `f"{amount:.2f}"` as the stored value to ensure deterministic precision.

### Pitfall 6: `create_backup()` requires explicit `backups_dir` argument

**What goes wrong:** The existing `db/__init__.py` re-export of `create_backup` matches the actual signature: `create_backup(engine, backups_dir)`. The backups dir is NOT inferred from config automatically.

**How to avoid:** Call `create_backup(engine, DATA_DIR / "backups")`.

[VERIFIED: codebase] — `backup.py` signature confirmed: `def create_backup(engine: Engine, backups_dir: Path) -> Path`.

---

## Code Examples

Verified patterns from the codebase:

### Welcome screen separator (rule 6.2)

```python
# Source: spec §7.1 (canonical output); rule 6.2 says === spanning full content width
SEPARATOR = "=" * 64  # spec shows exactly 64 = characters in the welcome banner
console.print(SEPARATOR)
console.print("bensdorp1 — System #1: Trend following on S&P 500 stocks")
console.print("First-time setup")
console.print(SEPARATOR)
```

Note: The spec shows `================================================================` (64 `=` chars based on the line "bensdorp1 — System #1: Trend following on S&P 500 stocks" being 55 chars). The exact width should match the spec exactly; count the `=` chars in §7.1 verbatim output.

### Available cash subsection header (rule 6.2)

```python
# Source: spec §7.1 Step 2 (canonical output)
# "Available cash" = 14 characters; --- spans the header text width
console.print()
console.print("Available cash")
console.print("-" * 14)
console.print("Enter the amount of cash you have available for trading.")
console.print("This is the amount the system will use to size new positions.")
```

### Cash prompt and confirmation loop

```python
# Source: CONTEXT.md D-03, D-04, D-05
from bensdorp1.ui import number_prompt, confirm_prompt, format_price

try:
    while True:
        cash = number_prompt("Available cash", "USD", console=console)
        if cash <= 0:
            console.print("Error: Cash must be greater than zero.")
            continue
        console.print()
        console.print(f"Available cash: {format_price(cash)}")
        console.print()
        if confirm_prompt("Confirm?", console=console):
            break
        # If user says n, loop back to re-enter cash
except KeyboardInterrupt:
    console.print()
    console.print("Operation aborted. No changes were made.")
    raise typer.Exit()
```

### Completion summary (spec §7.1 Step 4)

```python
# Source: spec §7.1 Step 4 (canonical output)
# Use _render_kv_block for aligned key:value pairs
from bensdorp1.ui.styles import _render_kv_block

console.print()
console.print(SEPARATOR)
console.print("Setup complete")
console.print(SEPARATOR)
console.print()
_render_kv_block({
    "Database created": _tilde_path(db_path),
    "Backups location": _tilde_path(DATA_DIR / "backups") + "/",
    "Constituents": f"{len(constituents)} stocks",
    "History downloaded": "220 trading days",
    "Available cash": format_price(cash),
    "Total time": _format_total_time(elapsed),
}, console)
console.print()
console.print("Next steps:")
console.print("  1. Wait for end-of-day market close (16:00 ET / 21:00 Lisbon)")
console.print("  2. Run `bensdorp1 scan` to see today's buy candidates and exit triggers")
console.print("  3. Run `bensdorp1 help` to see all available commands")
```

Note: `_render_kv_block` from `ui/styles.py` is a private helper, not exported via `ui/__init__.py`. The command should either use it directly by importing from `bensdorp1.ui.styles` (breaking the "import only from `bensdorp1.ui`" rule) or replicate the alignment manually, or use the `data=` kwarg of `print_success()`. The cleanest solution: emit completion as a plain `console.print()` block using a manually aligned string, matching the spec exactly.

[ASSUMED] — the resolution between using `_render_kv_block` vs. manual kv alignment is a planner decision.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `typer.prompt()` / `typer.confirm()` | `input()` directly via `ui/prompts.py` | Phase 5 | Prompts.py already implements all prompt logic |
| Stub `init.py` (one-liner) | Full interactive flow | Phase 6 | Replace entirely |
| No cash in DB | `config` table, key=`available_cash` | Phase 6 (first writer) | Phase 9 `cash` command will read and update this row |

**Deprecated/outdated:**
- `test_cli.py` `test_stub_exits_cleanly[init]`: Will be invalid once Phase 6 lands; must be removed/updated.

---

## Open Questions

1. **Step 2 progress bar vs. SpinnerContext**
   - What we know: `update_price_data()` does bulk download without per-symbol callback. CONTEXT.md says "call `.advance(symbol)` per symbol". Spec shows a progress bar for step 3.
   - What's unclear: Should `init.py` drive a per-symbol loop (calling `update_price_data(engine, [symbol])` 503 times) to enable TrackContext, or call once (fast, but forces SpinnerContext)?
   - Recommendation: Use per-symbol iteration from `init.py` to match spec and CONTEXT.md intent. Accept the per-symbol overhead (each call is retried, but this is a one-time setup with no time constraint). The planner should make this explicit in the task.

2. **`system_initialized` audit payload schema**
   - What we know: The spec section 9.2 does not define an explicit JSON payload for `system_initialized` (only notes "include all relevant context fields"). The CONTEXT.md says `log_event(engine, AuditEventType.system_initialized, metadata={...})`.
   - What's unclear: Exact payload keys. Reasonable fields: `constituent_count`, `cash`, `history_days`, `db_path`.
   - Recommendation: Use `payload={"constituent_count": len(constituents), "cash": cash, "history_days": 220}`. Flag as Claude's discretion.

3. **`_render_kv_block` access in completion summary**
   - What we know: `_render_kv_block` is in `ui/styles.py` and is private (underscore-prefixed). It is used internally in `messages.py`. The `ui/__init__.py` docstring says "all commands consume only names exported here — never deep-import from ui.styles".
   - What's unclear: Whether the completion summary should use `print_success()` with `data=` kwarg (which calls `_render_kv_block` indirectly) or build a manually-aligned block.
   - Recommendation: Use `print_success(title, data={...})` with a custom `data` dict. The `print_success()` path calls `_render_kv_block` internally, satisfying the no-deep-import rule. However, the spec's completion summary starts with `===` banners, not a severity prefix. The planner should likely emit the `===` banners manually and use `_render_kv_block` for the kv block, accepting the one private-import exception with a comment.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 6 is code-only changes. No new external dependencies. All runtime services (SQLite, yfinance, Wikipedia, Slickcharts) were verified in prior phases.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_commands/ -x` |
| Full suite command | `uv run pytest --cov=bensdorp1 --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CMD-01 (guard) | Re-run when DB exists → error + exit 1 | unit | `uv run pytest tests/test_commands/test_init.py::test_guard_fires_when_db_exists -x` | Wave 0 |
| CMD-01 (happy path) | Full flow completes → DB created, audit event written | integration | `uv run pytest tests/test_commands/test_init.py::test_happy_path -x` | Wave 0 |
| CMD-01 (cash validation) | Invalid cash inputs → re-prompt | unit | `uv run pytest tests/test_commands/test_init.py::test_cash_validation -x` | Wave 0 |
| CMD-01 (abort) | Ctrl+C during cash → abort message, no DB | unit | `uv run pytest tests/test_commands/test_init.py::test_ctrl_c_during_cash -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_commands/ -x`
- **Per wave merge:** `uv run pytest --cov=bensdorp1 --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_commands/__init__.py` — empty file (matches `test_ui/__init__.py` pattern)
- [ ] `tests/test_commands/test_init.py` — covers all 4 required scenarios (D-08)
- [ ] Update `tests/test_cli.py` — remove `"init"` from `test_stub_exits_cleanly` parametrize list

---

## Security Domain

`security_enforcement: true` (from config.json). ASVS Level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | CLI is single-user, no auth |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | No access control layer |
| V5 Input Validation | Yes | Cash input validated >0; non-numeric rejected by `number_prompt()`; path display uses `_tilde_path()` not raw user input |
| V6 Cryptography | No | No crypto in this phase |

### Known Threat Patterns for init command

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Markup injection via cash amount in display | Tampering | `format_price(cash)` returns a safe formatted string; `console.print(Text(...))` blocks markup |
| Path traversal in display | Information Disclosure | `_tilde_path()` only replaces home prefix; never passes user-controlled paths to file operations |
| Directory traversal in DATA_DIR | Elevation of Privilege | `DATA_DIR` is from env var resolved at import time; `init.py` never takes a path argument |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `CliRunner.invoke(input=...)` feeds `input()` calls correctly for multi-prompt flows | Architecture Patterns (Pattern 4) | Tests pass locally but fail in CI; need to verify test approach |
| A2 | Per-symbol loop (`update_price_data(engine, [symbol])` × 503) is the intended step 3 approach | Common Pitfalls (Pitfall 2) | Wrong approach changes plan task count and performance |
| A3 | `system_initialized` audit payload should include `constituent_count`, `cash`, `history_days` | Open Questions (Q2) | Payload schema may differ from what other phases expect when querying audit |
| A4 | `_render_kv_block` may be imported directly from `ui/styles` with a comment justification | Open Questions (Q3) | Strict no-deep-import rule violation could cause lint/review rejection |

---

## Project Constraints (from CLAUDE.md)

The following directives from CLAUDE.md apply to this phase:

1. **Language:** Python 3.11+ only.
2. **Package manager:** `uv` — all commands use `uv run`.
3. **No extensibility:** No abstractions for hypothetical future commands; `init.py` is a concrete implementation only.
4. **mypy strict:** `init.py` must pass `mypy --strict`. All functions typed with `-> None`. `DATA_DIR / "data" / "bensdorp1.db"` is a `Path` expression (no type issues). `create_backup` returns `Path` (can be ignored with `_`).
5. **ruff:** Formatter and linter apply. Line endings LF (per memory note about ruff LF config).
6. **Typer patterns:** `rich_markup_mode="rich"`, `pretty_exceptions_enable=False` (already in `_app.py`). `raise typer.Exit()` not `sys.exit()`.
7. **Console ownership:** All UI functions accept `console: Console | None = None`; tests pass `Console(record=True)` explicitly.
8. **No UI modifications:** Phase 6 must not modify any file in `ui/`, `db/`, `data/`, or `strategy/`.

---

## Sources

### Primary (HIGH confidence)

- Codebase: `src/bensdorp1/commands/init.py` — current stub confirmed
- Codebase: `src/bensdorp1/config.py` — `DATA_DIR` path construction verified
- Codebase: `src/bensdorp1/db/engine.py` — `run_migrations()`, `get_engine()`, `_reset_engine_for_testing()` signatures verified
- Codebase: `src/bensdorp1/db/audit.py` — `log_event()` signature and `AuditEventType.SYSTEM_INITIALIZED` verified
- Codebase: `src/bensdorp1/db/backup.py` — `create_backup(engine, backups_dir)` signature verified
- Codebase: `src/bensdorp1/db/schema.py` — `config` table (key/value/updated_at) verified
- Codebase: `src/bensdorp1/data/__init__.py` — `get_constituents()`, `update_price_data()` public API verified
- Codebase: `src/bensdorp1/ui/progress.py` — `MultiStepContext`, `SpinnerContext`, `TrackContext`, `feedback` namespace verified
- Codebase: `src/bensdorp1/ui/prompts.py` — `confirm_prompt()`, `number_prompt()` signatures verified
- Codebase: `src/bensdorp1/ui/messages.py` — `print_error()` signature verified
- Codebase: `src/bensdorp1/ui/styles.py` — `format_price()`, `_render_kv_block()` verified
- Codebase: `tests/conftest.py` — `db_engine` and `record_console` fixtures verified
- Codebase: `tests/test_cli.py` — `CliRunner` pattern and stub test (to-be-updated) verified
- Spec: `.planning/Bensdorp_1.md` §7.1 — exact output format for all 4 steps
- Spec: `.planning/Bensdorp_1.md` §5.2.1 — error messages, side effects, validations
- Spec: `.planning/Bensdorp_1.md` §6.2 — separator rules (`===` and `---`)
- Context: `.planning/phases/06-first-run-init-command/06-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- None required — all claims verified directly against codebase.

### Tertiary (LOW confidence / ASSUMED)

- A1: `CliRunner.invoke(input=)` multi-prompt behavior — standard Click/Typer pattern, not verified against specific version in this session.
- A2: Per-symbol loop as intended step 3 approach — inferred from CONTEXT.md language.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all primitives verified by direct codebase reads
- Architecture: HIGH — data flow confirmed by reading every called function
- Pitfalls: HIGH (Pitfalls 1, 2, 4, 6) / MEDIUM (Pitfall 3, 5) — Pitfall 2 is the only true ambiguity
- Test patterns: MEDIUM — `CliRunner` `input=` behavior is standard but not verified against exact typer version

**Research date:** 2026-05-24
**Valid until:** Phase 6 completion (this is a narrow, well-scoped phase; no external dependencies change)
