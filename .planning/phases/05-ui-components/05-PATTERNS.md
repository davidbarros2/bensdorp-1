# Phase 5: UI Components - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 16 new files
**Analogs found:** 14 / 16

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/bensdorp1/config.py` | config | transform | `src/bensdorp1/db/engine.py` (env-resolution pattern) | role-match |
| `src/bensdorp1/ui/__init__.py` | provider | request-response | `src/bensdorp1/db/__init__.py` | exact |
| `src/bensdorp1/ui/styles.py` | utility | transform | `src/bensdorp1/data/calendar.py` (module-level singleton) | role-match |
| `src/bensdorp1/ui/tables.py` | utility | transform | `src/bensdorp1/strategy/screening.py` (pure function) | role-match |
| `src/bensdorp1/ui/messages.py` | utility | request-response | `src/bensdorp1/db/audit.py` (Enum + function) | role-match |
| `src/bensdorp1/ui/prompts.py` | utility | request-response | `src/bensdorp1/commands/help.py` (user interaction) | partial |
| `src/bensdorp1/ui/progress.py` | utility | event-driven | none — no event-driven context managers exist | none |
| `src/bensdorp1/ui/empty_states.py` | utility | request-response | `src/bensdorp1/ui/messages.py` (thin wrapper pattern) | role-match |
| `tests/test_ui/__init__.py` | test | — | `tests/test_strategy/__init__.py` | exact |
| `tests/test_ui/test_config.py` | test | — | `tests/test_db_engine.py` (env-var + monkeypatch tests) | exact |
| `tests/test_ui/test_styles.py` | test | — | `tests/test_strategy/test_positions.py` (pure function asserts) | exact |
| `tests/test_ui/test_messages.py` | test | — | `tests/test_db_audit.py` (enum + function tests) | role-match |
| `tests/test_ui/test_tables.py` | test | — | `tests/test_strategy/test_screening.py` (construct + assert) | role-match |
| `tests/test_ui/test_prompts.py` | test | — | `tests/test_db_engine.py` (monkeypatch pattern) | role-match |
| `tests/test_ui/test_progress.py` | test | — | `tests/test_db_engine.py` (monkeypatch + module-level state) | partial |
| `tests/test_ui/test_empty_states.py` | test | — | `tests/test_db_audit.py` (function output test) | role-match |

---

## Pattern Assignments

### `src/bensdorp1/config.py` (config, transform)

**Analog:** `src/bensdorp1/db/engine.py` — env-var resolution pattern; and `src/bensdorp1/data/calendar.py` — module-level constant created once at import.

**Env-resolution pattern** (`src/bensdorp1/db/engine.py` lines 22-33):
```python
import os
from pathlib import Path

home_env = os.environ.get("BENSDORP1_HOME")
base = Path(home_env) if home_env else Path.home() / "bensdorp1"
```

**Module-level singleton pattern** (`src/bensdorp1/data/calendar.py` line 14):
```python
_NYSE = mcal.get_calendar("NYSE")  # module-level; created once at import
```

**Core pattern for config.py** (from D-08 decision):
```python
# src/bensdorp1/config.py
import os
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_NAME: str = "bensdorp1"
MARKET_TZ: ZoneInfo = ZoneInfo("America/New_York")
USER_TZ: ZoneInfo = ZoneInfo(os.environ.get("BENSDORP1_USER_TZ", "Europe/Lisbon"))
DATA_DIR: Path = Path(os.environ.get("BENSDORP1_HOME", str(Path.home() / PROJECT_NAME)))
```

**No I/O rule:** `config.py` must be read-only at import time — no function calls that produce side effects. Follow the `calendar.py` model (`_NYSE = mcal.get_calendar(...)` — one expression, module level).

---

### `src/bensdorp1/ui/__init__.py` (provider, request-response)

**Analog:** `src/bensdorp1/db/__init__.py` (lines 1-13) — exact re-export pattern.

**Re-export pattern** (`src/bensdorp1/db/__init__.py` lines 1-13):
```python
"""Public surface of the bensdorp1.db subpackage."""

from bensdorp1.db.audit import AuditEventType, log_event
from bensdorp1.db.backup import create_backup
from bensdorp1.db.engine import get_engine, run_migrations

__all__ = [
    "AuditEventType",
    "create_backup",
    "get_engine",
    "log_event",
    "run_migrations",
]
```

**Also reference** `src/bensdorp1/strategy/__init__.py` (lines 1-34) — shows the docstring style for scope-scoping comments and alphabetically sorted `__all__`.

**Apply to `ui/__init__.py`:** Follow identical structure. Docstring describes the public surface. Re-export all public symbols from `styles`, `tables`, `messages`, `prompts`, `progress`, `empty_states`. `__all__` lists every exported name alphabetically.

---

### `src/bensdorp1/ui/styles.py` (utility, transform)

**Analog:** `src/bensdorp1/data/calendar.py` — module-level singleton created at import, no I/O; `src/bensdorp1/db/engine.py` — module-level `_engine: Engine | None = None` private singleton pattern.

**Module-level private singleton** (`src/bensdorp1/db/engine.py` lines 15-16):
```python
_engine: Engine | None = None
_engine_lock: threading.Lock = threading.Lock()
```

**Module-level constant at import** (`src/bensdorp1/data/calendar.py` line 14):
```python
_NYSE = mcal.get_calendar("NYSE")  # module-level; created once at import
```

**Core pattern for styles.py** (from D-06 + RESEARCH.md Pattern 1):
```python
# src/bensdorp1/ui/styles.py
from rich.console import Console
from rich.style import Style

# Module-level console singleton — tests pass Console(record=True) via console= param
_console: Console = Console()  # auto-detects TTY, respects NO_COLOR env var

# Color palette (rule 6.29)
ERROR_STYLE: Style = Style(color="red")
WARNING_STYLE: Style = Style(color="yellow")
INFO_STYLE: Style = Style(color="cyan")
SUCCESS_STYLE: Style = Style(color="green")
MUTED_STYLE: Style = Style(color="bright_black")
```

**Formatter functions** — pure functions with explicit `-> str` return types (mypy strict). No `-> None`. No side effects:
```python
def format_price(value: float) -> str:
    """Format a USD price: $X,XXX.XX."""
    return f"${value:,.2f}"

def format_pct(value: float) -> str:
    """Format a percentage with explicit sign: ±X.X%."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"
```

**KV-alignment helper** (from RESEARCH.md Finding #6 — must live in styles.py per architecture map):
```python
def _render_kv_block(
    data: dict[str, str],
    console: Console,
    indent: str = "",
) -> None:
    if not data:
        return
    max_key_len = max(len(k) for k in data)
    for k, v in data.items():
        spaces = (max_key_len - len(k)) + 2
        console.print(f"{indent}{k}:{' ' * spaces}{v}")
```

**No bold constraint:** `Style(bold=True)` and `[bold]` markup are forbidden everywhere in `ui/`. Rule 6.31.

---

### `src/bensdorp1/ui/tables.py` (utility, transform)

**Analog:** `src/bensdorp1/strategy/screening.py` — pure functions that receive data and return/transform it. No analog uses Rich `Table` yet.

**Pure function signature pattern** (`src/bensdorp1/strategy/screening.py` line style):
```python
def regime_filter(spy_closes: pd.Series) -> bool:
    """Return True when S&P 500 is in a bull regime (close > SMA 200)."""
```

**Core pattern for tables.py** (from D-02):
```python
# src/bensdorp1/ui/tables.py
from rich.console import Console
from rich.table import Table

from bensdorp1.ui.styles import _console as _default_console


def render_table(
    columns: list[tuple[str, str]],   # (header, justify) — "left" or "right"
    rows: list[list[str]],
    *,
    console: Console | None = None,
) -> None:
    """Render a minimalist Rich Table per rules 6.8/6.9/6.31.

    No borders, no bold headers, 2-space column separation.
    """
    con = console if console is not None else _default_console
    table = Table(box=None, show_edge=False, padding=(0, 1), header_style="")
    for header, justify in columns:
        table.add_column(header, justify=justify)  # type: ignore[arg-type]
    for row in rows:
        table.add_row(*row)
    con.print(table)
```

**justify values:** `"left"` for text columns, `"right"` for number columns. Rule 6.9. Rich's `Table.add_column` `justify` parameter accepts `Literal["left", "center", "right", "full", "default"]`.

---

### `src/bensdorp1/ui/messages.py` (utility, request-response)

**Analog:** `src/bensdorp1/db/audit.py` — Enum definition + function that uses the enum. Best codebase analog for the `Severity` enum + `print_message()` pattern.

**Enum definition pattern** (`src/bensdorp1/db/audit.py` lines 18-41):
```python
from enum import StrEnum

class AuditEventType(StrEnum):
    """All 17 audit event types from STATE-04.

    StrEnum members ARE strings — no .value needed for SQLite TEXT storage.
    """
    SYSTEM_INITIALIZED = "system_initialized"
    BUY_CONFIRMED = "buy_confirmed"
    # ...
```

**Severity enum** uses standard `Enum` (not `StrEnum`) because values are display labels, not storage strings. From D-07 + RESEARCH.md Pattern 2:
```python
from enum import Enum

class Severity(Enum):
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"
    SUCCESS = "Success"

_SEVERITY_COLORS: dict[Severity, str] = {
    Severity.ERROR: "red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
    Severity.SUCCESS: "green",
}
```

**Function with optional keyword parameters** (`src/bensdorp1/db/audit.py` lines 44-63):
```python
def log_event(
    engine: Engine,
    event_type: AuditEventType,
    symbol: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
```

**Core pattern for print_message** (from D-07):
```python
def print_message(
    severity: Severity,
    title: str,
    *,
    data: dict[str, str] | None = None,
    body: list[str] | None = None,
    impact: dict[str, str] | None = None,
    actions: list[str] | None = None,
    console: Console | None = None,
) -> None:
    """Critical message structure per rule 6.12. Color on prefix only (rule 6.13)."""
    con = console if console is not None else _default_console
    color = _SEVERITY_COLORS[severity]
    prefix = severity.value  # "Error", "Warning", etc.
    con.print(f"[{color}]{prefix}:[/{color}] {title}")
    # render optional blocks: data (kv-aligned), body (plain lines),
    # impact (kv-aligned), actions (plain lines)
```

**Security:** When rendering `data`/`impact` dict values, use `Text(line)` or `console.print(..., markup=False)` to prevent Rich markup injection from untrusted string values. Do not pass user-controlled strings as Rich markup.

**Shortcut aliases** (same `-> None` pattern):
```python
def print_error(title: str, **kwargs: ...) -> None:
    print_message(Severity.ERROR, title, **kwargs)
```

---

### `src/bensdorp1/ui/prompts.py` (utility, request-response)

**Analog:** `src/bensdorp1/commands/help.py` — the only existing command that interacts with the user. No `input()` usage exists yet in the codebase.

**Typer interaction pattern** (`src/bensdorp1/commands/help.py` lines 1-23) — shows how commands accept user input; prompts.py will use `input()` directly per D-05.

**Core pattern for confirm_prompt** (from D-05):
```python
# src/bensdorp1/ui/prompts.py
from rich.console import Console
from rich.text import Text

from bensdorp1.ui.styles import _console as _default_console


def confirm_prompt(message: str, *, console: Console | None = None) -> bool:
    """Prompt user for y/n confirmation per rule 6.15.

    Accepts y Y n N. Re-prompts on empty or invalid input.
    KeyboardInterrupt → prints cancellation message → returns False.
    """
    con = console if console is not None else _default_console
    prompt_text = f"{message} [y/n] "
    while True:
        try:
            raw = input(prompt_text).strip().lower()
        except KeyboardInterrupt:
            con.print()
            con.print(Text("Operation aborted. No changes were made."))
            return False
        if raw in ("y",):
            return True
        if raw in ("n",):
            return False
        # re-prompt on empty or invalid input
```

**`-> None` annotation discipline:** All ui/ functions that print must annotate `-> None`. `confirm_prompt` returns `bool` — annotate accordingly.

---

### `src/bensdorp1/ui/progress.py` (utility, event-driven)

**No analog in codebase** — no context managers, no `Live`/`Progress` usage exists. Use RESEARCH.md patterns exclusively.

**Class-based context manager pattern** (RESEARCH.md Finding #2, verified mypy strict):
```python
import time
import types
from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

THRESHOLD_SPINNER: float = 1.0
THRESHOLD_PROGRESS: float = 6.0
THRESHOLD_ETA: float = 30.0

class TrackContext:
    def __init__(self, description: str, total: int, console: Console) -> None:
        self._description = description
        self._total = total
        self._console = console
        self._live: Live | None = None
        self._start: float = 0.0
        self._completed: int = 0

    def advance(self, current_label: str = "") -> None:
        self._completed += 1
        elapsed = time.monotonic() - self._start
        if self._live is not None:
            self._live.update(self._build_renderable(elapsed))

    def __enter__(self) -> "TrackContext":
        self._start = time.monotonic()
        self._live = Live(
            console=self._console, refresh_per_second=10, transient=True
        )
        self._live.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if self._live is not None:
            self._live.__exit__(exc_type, exc_val, exc_tb)
```

**Critical:** `__exit__` must spell out three typed params — never `*args: object`. Mypy strict fails on the splat form. [VERIFIED: RESEARCH.md Finding #2]

**Custom bar column** (RESEARCH.md Pattern 3):
```python
from rich.progress import ProgressColumn, Task
from rich.text import Text

class BlockBarColumn(ProgressColumn):
    def __init__(self, bar_width: int = 20) -> None:
        self.bar_width = bar_width
        super().__init__()

    def render(self, task: Task) -> Text:
        pct = task.completed / task.total if task.total else 0.0
        filled = int(self.bar_width * pct)
        empty = self.bar_width - filled
        return Text("█" * filled + "░" * empty)
```

**Multi-step done-line pattern** (RESEARCH.md Open Question #2): After each Live context exits (`transient=True`), the done line must be printed as a plain `console.print()` call outside the Live context:
```python
console.print(f"[{n}/{total}] {description}... done.")
```

---

### `src/bensdorp1/ui/empty_states.py` (utility, request-response)

**Analog:** `src/bensdorp1/ui/messages.py` (to be created as part of this phase) — thin wrappers that call `print_info` or `print_message`. No existing codebase analog.

**Core pattern** — thin delegation function (rule 6.11/6.19):
```python
# src/bensdorp1/ui/empty_states.py
from rich.console import Console

from bensdorp1.ui.messages import print_info


def print_empty_state(
    entity: str,
    suggestion: str | None = None,
    *,
    console: Console | None = None,
) -> None:
    """Print an explicit empty state message so output is never blank (rule 6.11)."""
    msg = f"No {entity} found."
    if suggestion:
        msg = f"{msg} {suggestion}"
    print_info(msg, console=console)
```

---

## Shared Patterns

### `console: Console | None = None` Parameter Convention (D-06)

**Source:** All ui/ functions — established by design decision D-06.
**Apply to:** Every function in `styles.py`, `tables.py`, `messages.py`, `prompts.py`, `progress.py`, `empty_states.py`.

Pattern:
```python
from rich.console import Console
from bensdorp1.ui.styles import _console as _default_console

def some_function(..., *, console: Console | None = None) -> None:
    con = console if console is not None else _default_console
    con.print(...)
```

Tests always pass `Console(record=True)` explicitly. The `_default_console` is never mutated.

---

### `-> None` Return Type Annotation (mypy strict)

**Source:** Every function in the codebase that prints — e.g., `src/bensdorp1/db/audit.py` line 44: `def log_event(...) -> None:`.
**Apply to:** All ui/ functions that print or have side effects. No function may omit return type annotations under mypy strict.

---

### Enum Pattern

**Source:** `src/bensdorp1/db/audit.py` lines 18-41 — `AuditEventType(StrEnum)`.
**Apply to:** `ui/messages.py` `Severity` enum — use `Enum` (not `StrEnum`) because values are display labels, not storage strings.

`StrEnum` is for values that ARE the string (e.g., DB storage). `Enum` is for labelled constants. `Severity.ERROR.value == "Error"` is accessed via `.value`.

---

### Docstring Convention

**Source:** `src/bensdorp1/db/audit.py` (module docstring + function docstrings), `src/bensdorp1/strategy/__init__.py` (module docstring with scope note).

Pattern:
- Module docstring: one sentence describing the module's responsibility; optionally a "Depends on:" / "Used by:" note.
- Function docstring: one-sentence summary. Optional second paragraph for constraints or spec rule references.

---

### No Circular Import Constraint

**Source:** `05-CONTEXT.md` Existing Code Insights.
**Apply to:** All `ui/` modules. Must NOT import from `commands/`, `db/`, `data/`, or `strategy/`. Only `config.py` and stdlib/Rich are allowed.

Import order for ui/ modules:
1. stdlib (`os`, `time`, `types`, `enum`, `datetime`, `zoneinfo`)
2. third-party (`rich.*`)
3. first-party: `bensdorp1.config` only (never `bensdorp1.db`, etc.)

---

## Test Patterns

### `tests/test_ui/__init__.py`

**Analog:** `tests/test_strategy/__init__.py` — single blank line (empty package marker).

Content:
```python

```
(One blank line. Ruff/mypy compliant.)

---

### Pure-Function Test Pattern

**Analog:** `tests/test_strategy/test_positions.py` — plain `assert` on return values, no fixtures, `-> None` on every test function.

**Apply to:** `tests/test_ui/test_config.py` (config constants), `tests/test_ui/test_styles.py` (formatter functions).

```python
# From tests/test_strategy/test_positions.py lines 36-39
def test_compute_position_size_normal() -> None:
    """cash=100000.0, prev_close=50.0 yields 200 shares (floor(10000/50))."""
    result = compute_position_size(100000.0, 50.0)
    assert result == 200
    assert isinstance(result, int)
```

---

### Console(record=True) Test Pattern

**No existing analog** — new pattern for Phase 5. Established by D-04 and RESEARCH.md Finding #7.

**conftest.py addition** (add to `tests/conftest.py`):
```python
import pytest
from rich.console import Console

@pytest.fixture
def record_console() -> Console:
    """Fresh Console(record=True) for each test."""
    return Console(record=True, width=80)
```

**Test pattern** (RESEARCH.md Finding #7):
```python
def test_print_info(record_console: Console) -> None:
    print_info("Test message", console=record_console)
    assert "Info: Test message" in record_console.export_text()

def test_print_info_color() -> None:
    c = Console(record=True, force_terminal=True, width=80)
    print_info("Test", console=c)
    styled = c.export_text(styles=True)
    assert "\x1b[36m" in styled  # cyan = ANSI code 36
```

**Critical:** `export_text()` clears the buffer on each call. Store the result in a variable; never call it twice per assertion block.

---

### monkeypatch Test Pattern

**Analog:** `tests/test_db_engine.py` lines 23-29 — `monkeypatch.setenv()` and `monkeypatch.setattr()`.

```python
# From tests/test_db_engine.py lines 23-29
def test_resolve_db_path_uses_bensdorp1_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine_module._reset_engine_for_testing()
    monkeypatch.setenv("BENSDORP1_HOME", str(tmp_path))
    resolved = engine_module._resolve_db_path(None)
    assert resolved == tmp_path / "data" / "bensdorp1.db"
```

**Apply to:**
- `tests/test_ui/test_config.py` — `monkeypatch.setenv("BENSDORP1_USER_TZ", ...)` to verify USER_TZ resolution. Note: `config.py` is module-level; must use `importlib.reload(config)` after patching env vars, or test via `ZoneInfo(os.environ.get(...))` inline.
- `tests/test_ui/test_prompts.py` — `monkeypatch.setattr("builtins.input", lambda _: "y")`.
- `tests/test_ui/test_progress.py` — `monkeypatch.setattr("bensdorp1.ui.progress.time", mock_time)` to control elapsed time.

---

### Parametrize Pattern

**Analog:** `tests/test_db_audit.py` lines 16-26 — `@pytest.mark.parametrize` over enum members.

```python
# From tests/test_db_audit.py lines 16-17
@pytest.mark.parametrize("event_type", list(AuditEventType))
def test_all_event_types_insertable(
    db_engine: Engine, event_type: AuditEventType
) -> None:
```

**Apply to:** `tests/test_ui/test_messages.py` — parametrize over `list(Severity)` to verify each severity prefix and color renders correctly.

---

### `pytest.raises` Pattern

**Analog:** `tests/test_strategy/test_screening.py` lines 71-75:
```python
def test_regime_filter_insufficient_rows() -> None:
    series = pd.Series([1.0] * 50, dtype=float)
    with pytest.raises(ValueError, match=r"need >= 200"):
        regime_filter(series)
```

**Apply to:** `tests/test_ui/test_config.py` — verify `ZoneInfo("invalid/zone")` raises `ZoneInfoNotFoundError`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/bensdorp1/ui/progress.py` | utility | event-driven | No context managers or Live/Progress usage exist in codebase. Use RESEARCH.md Technical Findings #2, #3, #4 exclusively. |

---

## Metadata

**Analog search scope:** `src/bensdorp1/`, `tests/`
**Files scanned:** 15 source files + 15 test files
**Key confirmed patterns:**
- Re-export `__init__.py`: `src/bensdorp1/db/__init__.py` (exact)
- Enum definition: `src/bensdorp1/db/audit.py` (StrEnum; use plain Enum for Severity)
- Module-level singleton: `src/bensdorp1/data/calendar.py` + `src/bensdorp1/db/engine.py`
- Env-var resolution: `src/bensdorp1/db/engine.py` `_resolve_db_path()`
- Pure function tests: `tests/test_strategy/test_positions.py`
- monkeypatch env: `tests/test_db_engine.py`
- parametrize over enum: `tests/test_db_audit.py`
- Empty package marker: `tests/test_strategy/__init__.py`
**Pattern extraction date:** 2026-05-24
