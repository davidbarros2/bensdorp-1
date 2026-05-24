# Phase 6: First-Run Init Command - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 4
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/bensdorp1/commands/init.py` | command | request-response + CRUD | `src/bensdorp1/commands/help.py` + existing stub | exact (same module role, same Exit/app pattern) |
| `tests/test_commands/test_init.py` | test | CRUD + event-driven | `tests/test_db_audit.py` + `tests/test_ui/test_prompts.py` | role-match |
| `tests/test_commands/__init__.py` | config | — | `tests/test_ui/__init__.py` | exact (empty file) |
| `tests/test_cli.py` | test | request-response | `tests/test_cli.py` (existing, update only) | exact |

---

## Pattern Assignments

### `src/bensdorp1/commands/init.py` (command, request-response + CRUD)

**Primary analog:** `src/bensdorp1/commands/help.py` (lines 1-23)
**Secondary analog:** `src/bensdorp1/commands/init.py` stub (lines 1-10) — replace entirely

**Imports pattern** — derived from stub + all referenced modules:
```python
import time
import typer
from pathlib import Path
from datetime import UTC, datetime

from rich.console import Console
from rich.text import Text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bensdorp1._app import app
from bensdorp1.config import DATA_DIR
from bensdorp1.db import AuditEventType, create_backup, get_engine, log_event, run_migrations
from bensdorp1.db.schema import config as config_table
from bensdorp1.ui import (
    confirm_prompt,
    feedback,
    format_price,
    number_prompt,
    print_error,
)
```

Key import notes:
- `db` public surface (`db/__init__.py` lines 1-13): `AuditEventType`, `create_backup`, `get_engine`, `log_event`, `run_migrations` are all re-exported — import from `bensdorp1.db`, not submodules.
- `config_table` (the SQLAlchemy `Table` object for `config`) must be imported directly from `bensdorp1.db.schema` — it is NOT re-exported via `bensdorp1.db`.
- `sqlite_insert` is in `sqlalchemy.dialects.sqlite` — same as `prices.py` line 28.
- `format_price` and `feedback` are in `bensdorp1.ui` public surface (`ui/__init__.py` lines 7-82) — import from `bensdorp1.ui` only.
- Do NOT deep-import from `bensdorp1.ui.styles`, `bensdorp1.ui.progress`, etc. (`ui/__init__.py` docstring line 3-4).

**Command decorator pattern** (`help.py` lines 7-8, stub lines 6-7):
```python
@app.command(rich_help_panel="Setup")
def init() -> None:
    """First-run setup: create data directory, download history, record cash."""
```

**Early exit pattern** (`help.py` line 23, stub line 10):
```python
raise typer.Exit()       # clean exit, code 0
raise typer.Exit(1)      # error exit, code 1
```
Never use `sys.exit()`. Always `raise typer.Exit(code)`.

**Guard condition pattern** (D-01, D-02 — no analog, spec-defined):
```python
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
```

`print_error()` signature (`messages.py` lines 86-104):
```python
def print_error(
    title: str,
    *,
    data: dict[str, str] | None = None,
    body: list[str] | None = None,
    impact: dict[str, str] | None = None,
    actions: list[str] | None = None,
    console: Console | None = None,
) -> None:
```
The `actions=` kwarg prints a numbered "Recommended actions:" block (lines 78-83 of messages.py).

**Cash entry loop pattern** (D-03/D-04/D-05 — spec-defined):
```python
console = Console()
try:
    while True:
        cash = number_prompt("Available cash", "USD", console=console)
        if cash <= 0:
            console.print(Text("Error: Cash must be greater than zero."))
            continue
        console.print()
        console.print(Text(f"Available cash: {format_price(cash)}"))
        console.print()
        if confirm_prompt("Confirm?", console=console):
            break
        # user said n — loop back
except KeyboardInterrupt:
    console.print()
    console.print(Text("Operation aborted. No changes were made."))
    raise typer.Exit()
```

`number_prompt()` signature (`prompts.py` lines 69-89): returns `float`, handles non-numeric re-prompt internally, accepts `console=`.
`confirm_prompt()` signature (`prompts.py` lines 15-44): returns `bool`, handles `[y/n]` loop, accepts `console=`. Note: `confirm_prompt` already handles `KeyboardInterrupt` internally and returns `False` — but D-05 requires the `init` command to catch it at the cash-entry block level to print the abort message and exit. Wrap the entire `try/except KeyboardInterrupt` around the cash loop to intercept before `confirm_prompt` can swallow it OR raise directly from `number_prompt`'s `input()` call.

**MultiStepContext usage pattern** (`progress.py` lines 272-305):
```python
with feedback.multi_step(3, console=console) as ms:
    with ms.step("Fetching S&P 500 constituents"):
        constituents = get_constituents(engine)
    # Print detail lines AFTER the `with` block exits (not inside):
    console.print(Text("      Source: Wikipedia"))
    console.print(Text(f"      Stocks found: {len(constituents)}"))

    with ms.step("Verifying against secondary source"):
        pass  # cross-check happened inside get_constituents(); step 2 is a display beat

    symbols = list(constituents.keys())
    with ms.step("Downloading price history", total=len(symbols)) as track:
        for symbol in symbols:
            update_price_data(engine, [symbol])
            track.advance(symbol)
```

`MultiStepContext.step()` signature (`progress.py` lines 272-305): `step(description: str, total: int | None = None)` — `total=None` yields `SpinnerContext`; `total=N` yields `TrackContext`. After each `with ms.step(...)` block exits, the done line `[N/TOTAL] description... done.` is printed automatically (line 303-305).

**_tilde_path helper** (spec-canonical from CONTEXT.md §Specific Ideas):
```python
def _tilde_path(p: Path) -> str:
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)
```

**_store_cash helper** (D-03, RESEARCH.md Pattern 3):
```python
def _store_cash(engine: Engine, amount: float) -> None:
    with engine.connect() as conn:
        stmt = (
            sqlite_insert(config_table)
            .values(
                key="available_cash",
                value=f"{amount:.2f}",
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": f"{amount:.2f}", "updated_at": datetime.now(UTC)},
            )
        )
        conn.execute(stmt)
        conn.commit()
```

`config` table columns (`schema.py` lines 22-28): `key` (Text, PK), `value` (Text, nullable), `updated_at` (DateTime with timezone).
`sqlite_insert` with `on_conflict_do_update` used in `prices.py` lines 28, 213-218 — same pattern.
Store value as `f"{amount:.2f}"` (not `str(amount)`) for deterministic float precision (RESEARCH.md Pitfall 5).

**log_event call** (`audit.py` lines 44-63):
```python
log_event(
    engine,
    AuditEventType.SYSTEM_INITIALIZED,
    payload={"constituent_count": len(constituents), "cash": cash, "history_days": 220},
)
```

**create_backup call** (`backup.py` lines 21-62):
```python
create_backup(engine, DATA_DIR / "backups")
```
`create_backup` requires explicit `backups_dir` — it is NOT inferred from config (RESEARCH.md Pitfall 6). Returns `Path` (can be ignored with `_`).

**Completion summary pattern** (spec §7.1 Step 4 — using `_render_kv_block`):
```python
from bensdorp1.ui.styles import _render_kv_block  # one allowed private import; add comment

SEPARATOR = "=" * 64
console.print()
console.print(Text(SEPARATOR))
console.print(Text("Setup complete"))
console.print(Text(SEPARATOR))
console.print()
_render_kv_block(
    {
        "Database created": _tilde_path(db_path),
        "Backups location": _tilde_path(DATA_DIR / "backups") + "/",
        "Constituents": f"{len(constituents)} stocks",
        "History downloaded": "220 trading days",
        "Available cash": format_price(cash),
        "Total time": _format_elapsed(elapsed),
    },
    console,
)
```

`_render_kv_block` signature (`styles.py` lines 146-163): `(data: dict[str, str], console: Console, indent: str = "") -> None`. Aligns values at `max_key_len + 1 + 2` columns. Uses `markup=False, highlight=False` internally (injection-safe).

**Console ownership** (CONTEXT.md code_context line 99, `styles.py` line 20):
```python
# _default_console singleton is defined in ui/styles.py line 20:
_console: Console = Console()
# All UI functions accept console: Console | None = None
# Tests inject Console(record=True, width=80)
```
The `init` command creates its own `Console()` or uses the default; tests pass `Console(record=True)` explicitly.

---

### `tests/test_commands/test_init.py` (test, CRUD + interactive)

**Primary analog:** `tests/test_ui/test_prompts.py` (monkeypatch for `input()`)
**Secondary analog:** `tests/test_db_audit.py` (db_engine fixture, unittest.mock.patch)
**Tertiary analog:** `tests/test_cli.py` (CliRunner invocation pattern)

**Module-level imports pattern** (`test_prompts.py` lines 1-6, `test_db_audit.py` lines 1-11):
```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from bensdorp1.cli import app
```

**runner singleton** (`test_cli.py` line 6):
```python
runner = CliRunner()
```

**CliRunner invocation with input** (RESEARCH.md Pattern 4):
```python
result = runner.invoke(app, ["init"], input="y\n50000\ny\n")
assert result.exit_code == 0
```
All `input()` calls in the command are fed by the `input=` newline-delimited string. Order must exactly match the prompt sequence.

**patch for module-level names** (`test_data_constituents.py` lines 8, 14-16):
```python
from unittest.mock import MagicMock, patch

with patch("bensdorp1.commands.init.DATA_DIR", tmp_path), \
     patch("bensdorp1.commands.init.get_constituents", return_value={"AAPL": "Apple"}), \
     patch("bensdorp1.commands.init.update_price_data"), \
     patch("bensdorp1.commands.init.run_migrations"), \
     patch("bensdorp1.commands.init.create_backup"), \
     patch("bensdorp1.commands.init.log_event"):
    result = runner.invoke(app, ["init"], input="y\n50000\ny\n")
```

**db_engine fixture usage** (`test_db_audit.py` lines 17-20, `conftest.py` lines 33-49):
```python
def test_something(db_engine: Engine) -> None:
    # db_engine is a fresh SQLite engine at tmp_path/test.db
    # metadata.create_all already called; _reset_engine_for_testing called in teardown
```

**record_console fixture** (`conftest.py` lines 23-29):
```python
def test_something(record_console: Console) -> None:
    # record_console = Console(record=True, width=80)
    output = record_console.export_text()
    assert "some text" in output
```

**monkeypatch for input()** (`test_prompts.py` lines 13-16):
```python
def test_something(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "y")
```

**Iterator-based multi-call monkeypatch** (`test_prompts.py` lines 37-50):
```python
inputs = iter(["", "maybe", "y"])

def counting_input(_: str) -> str:
    nonlocal call_count
    call_count += 1
    return next(inputs)

monkeypatch.setattr("builtins.input", counting_input)
```

**Four required test scenarios** (D-08):

1. Guard fires when DB file already exists — pass `tmp_path` as `DATA_DIR`; pre-create `tmp_path / "data" / "bensdorp1.db"`; assert `result.exit_code == 1` and both recovery path strings in `result.output`.
2. Happy path — patch all data-layer calls; simulate `"y\n50000\ny\n"`; assert `exit_code == 0`.
3. Cash validation — simulate `"y\n0\n-100\nabc\n50000\ny\n"`; assert no exit until valid cash entered.
4. Ctrl+C during cash entry — raise `KeyboardInterrupt` from `input()` mock; assert `"Operation aborted. No changes were made."` in output and clean exit.

---

### `tests/test_commands/__init__.py` (config, empty)

**Analog:** `tests/test_ui/__init__.py` and `tests/test_strategy/__init__.py`

Both are empty files. Create `tests/test_commands/__init__.py` as an empty file (0 bytes). No docstring, no imports.

---

### `tests/test_cli.py` (test, update only)

**Analog:** `tests/test_cli.py` lines 34-58 (the parametrized `test_stub_exits_cleanly` test)

**Change required** (RESEARCH.md Pitfall 4): Remove `"init"` from the parametrize list in `test_stub_exits_cleanly` (line 37). The `test_help_subcommand_shows_help` parametrize list (line 62) can remain unchanged — it tests `--help` output, not stub behavior.

Current parametrize list (`test_cli.py` lines 36-53):
```python
@pytest.mark.parametrize(
    "cmd",
    [
        "init",      # <-- REMOVE this entry
        "restore",
        ...
    ],
)
def test_stub_exits_cleanly(cmd: str) -> None:
    result = runner.invoke(app, [cmd])
    assert result.exit_code == 0
    assert "Not yet implemented." in result.output
```

After Phase 6, invoking `init` with no input will raise `EOFError` (no stdin for `input()` call) or will prompt and the test will fail on `"Not yet implemented."` not being in output. Remove `"init"` from the list.

---

## Shared Patterns

### Console ownership (applies to init.py and test_init.py)
**Source:** `src/bensdorp1/ui/styles.py` line 20, `tests/conftest.py` lines 23-29
```python
# Production: module-level default console
_console: Console = Console()

# All ui/ functions: accept console= kwarg, default to _console
def print_error(title: str, *, console: Console | None = None) -> None: ...

# Tests: inject Console(record=True, width=80) and assert on export_text()
record_console = Console(record=True, width=80)
output = record_console.export_text()
assert "Error:" in output
```

### Markup injection defense (applies to all console.print calls in init.py)
**Source:** `src/bensdorp1/ui/styles.py` lines 157-163, `src/bensdorp1/ui/progress.py` line 289
```python
# Wrap all user-visible strings in Text() to block Rich markup injection:
console.print(Text(f"[{self._current}/{self._total}] {description}"))
# Use markup=False, highlight=False for kv blocks:
console.print(f"{k}:{' ' * spaces}{v}", markup=False, highlight=False)
```

### typer.Exit() for all exits (applies to init.py)
**Source:** `src/bensdorp1/commands/help.py` line 23, `src/bensdorp1/commands/init.py` stub line 10
```python
raise typer.Exit()     # exit code 0 — clean exit or user abort
raise typer.Exit(1)    # exit code 1 — error condition (guard fires, bad input)
```
Never `sys.exit()`, never `return` without exit.

### unittest.mock.patch for external calls (applies to test_init.py)
**Source:** `tests/test_data_constituents.py` lines 8, 64-71
```python
from unittest.mock import MagicMock, patch

# Patch at the import site (bensdorp1.commands.init.NAME), not the definition site:
with patch("bensdorp1.commands.init.get_constituents", return_value={...}):
    ...
```

### db_engine + _reset_engine_for_testing teardown (applies to test_init.py)
**Source:** `tests/conftest.py` lines 33-49
```python
@pytest.fixture
def db_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    db_path = tmp_path / "test.db"
    engine = engine_module._build_engine(db_path)
    engine_module._reset_engine_for_testing(engine)
    metadata.create_all(engine, checkfirst=True)
    try:
        yield engine
    finally:
        engine_module._reset_engine_for_testing()  # disposes engine; critical on Windows
```
Tests that need a real DB (e.g., verifying `_store_cash` writes to config table) use this fixture. Tests that mock all DB calls do not need it.

### sqlite_insert with on_conflict_do_update (applies to _store_cash helper in init.py)
**Source:** `src/bensdorp1/data/prices.py` lines 28, 209-218
```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

stmt = (
    sqlite_insert(price_daily)
    .values(rows)
    .on_conflict_do_nothing(index_elements=["symbol", "trade_date"])
)
conn.execute(stmt)
conn.commit()
```
`_store_cash` uses `on_conflict_do_update` (not `do_nothing`) since the config row must be overwritten if re-init is forced.

---

## No Analog Found

No files fall in this category. All four files have close analogs in the codebase.

---

## Key Observations for Planner

1. **`confirm_prompt` already handles `KeyboardInterrupt` internally** (`prompts.py` lines 36-40): it catches it, prints "Operation aborted. No changes were made.", and returns `False`. The D-05 requirement for `init` to catch `KeyboardInterrupt` during cash entry is specifically for the `number_prompt` call, which does NOT handle `KeyboardInterrupt` (its `while True` loop calls `float(raw)` with no interrupt guard). The `try/except KeyboardInterrupt` in the command wraps `number_prompt()` and the outer cash loop.

2. **`MultiStepContext` prints the step header at `__enter__` and done line at `__exit__`** (`progress.py` lines 287-305): detail lines must be printed AFTER the `with ms.step(...)` block exits, not inside it (RESEARCH.md Pitfall 1).

3. **`get_engine()` is a singleton** (`engine.py` lines 50-66): in tests, patch `DATA_DIR` AND also call `_reset_engine_for_testing()` in teardown to avoid the cached engine pointing at the wrong path across tests.

4. **`create_backup` requires `backups_dir`** (`backup.py` line 21): signature is `create_backup(engine, backups_dir: Path)`. Call as `create_backup(engine, DATA_DIR / "backups")`.

5. **`format_price` is in `bensdorp1.ui` public surface** (`ui/__init__.py` line 40): import from `bensdorp1.ui`, not `bensdorp1.ui.styles`.

6. **`_render_kv_block` is private** (`styles.py` line 146): it is not in `ui/__init__.py`'s `__all__`. The completion summary requires it for column-aligned kv pairs. Import with a comment: `# direct import of private helper; completion summary requires column alignment`.

---

## Metadata

**Analog search scope:** `src/bensdorp1/commands/`, `src/bensdorp1/ui/`, `src/bensdorp1/db/`, `src/bensdorp1/data/`, `tests/`
**Files scanned:** 22
**Pattern extraction date:** 2026-05-24
