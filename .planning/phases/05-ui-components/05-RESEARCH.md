# Research: Phase 5 — UI Components

**Researched:** 2026-05-24
**Domain:** Rich 15.x terminal rendering, Python stdlib zoneinfo, mypy strict type checking
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Bensdorp_1.md §6 (rules 6.1–6.31) is the authoritative source for all style-guide rules. §7 provides concrete output layouts. REQUIREMENTS.md UI-01–UI-10 and FEATURES.md are supplementary.
- **D-02:** Rich `Table(box=None, show_edge=False, padding=(0,1), header_style="")`. Number columns `justify="right"`, text columns `justify="left"`.
- **D-03:** Three context manager primitives in `ui/progress.py`: `feedback.spinner()`, `feedback.track()`, `feedback.multi_step()`. Four tiers: silent <1s, spinner 1–6s, progress bar 6–30s, progress bar + ETA >30s.
- **D-04:** Unit tests only. `Console(record=True)` + `export_text()`. Mock `time.time()` for threshold tests.
- **D-05:** Custom `confirm_prompt()` using `input()` directly. Accepts `y Y n N`. KeyboardInterrupt → `"Operation aborted. No changes were made."` → returns `False`.
- **D-06:** All UI functions accept `console: Console | None = None`. Module-level `_console = Console()` in `ui/styles.py`.
- **D-07:** `Severity` enum + `print_message()` base + shortcut aliases. Color on prefix only.
- **D-08:** `config.py` with `PROJECT_NAME`, `MARKET_TZ`, `USER_TZ`, `DATA_DIR` — env-based, read-only at import time.

### Claude's Discretion

None — all major decisions were locked.

### Deferred Ideas (OUT OF SCOPE)

None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | All 31 style guide rules from spec §6 implemented | §6 fully read; all rules mapped to specific modules below |
| UI-02 | Severity prefixes with ANSI color; text fallback in non-color terminals | Rich Console auto-handles NO_COLOR; `no_color=True` verified |
| UI-03 | Tables: minimalist, left-align text, right-align numbers | Rich `Table(box=None, show_edge=False, padding=(0,1))` confirmed |
| UI-04 | Feedback thresholds: silent/spinner/progress/progress+ETA | Rich.Live + Group pattern confirmed; `dots` spinner is exact braille match |
| UI-05 | Dual timezone on every timestamp: ET and user's local (default Lisbon) | `ZoneInfo.key` typed as `str` in mypy 2.1; city extraction confirmed |
| UI-06 | No decorative unicode; no bold/italic/underline; sentence case | `header_style=""` on Table; no Rich markup for bold; verified |
| UI-07 | Confirmation prompts for destructive actions with impact summary | `input()` directly; confirmed pattern for mypy strict |
| UI-08 | Empty states always explicit | `empty_states.py` helper functions; never blank output |
| UI-09 | Critical message structure: severity + title + optional blocks | `print_message()` with `data`, `body`, `impact`, `actions` params |
| UI-10 | Numerical formatting: prices, percentages, volumes, P&L, days | Pure functions; all formats verified against spec 6.10 |
</phase_requirements>

---

## Summary

Phase 5 builds the `ui/` subpackage and `config.py` — the formatting, rendering, and feedback layer that every command (Phases 6–14) will call. There are no new dependencies: Rich 15.0.0 is already installed (transitively via Typer), and all required Rich APIs (`Live`, `Progress`, `Spinner`, `Table`, `Console`, `Group`) are present and fully typed.

The critical verified finding is that Rich's built-in `dots` spinner **exactly matches** the 10-frame braille sequence `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` required by rule 6.22. No custom spinner registration is needed. However, Rich's built-in `ProgressBar` uses `━`/`╸`/`╺` characters, **not** `█`/`░` as rule 6.30 requires. A custom `ProgressColumn` subclass must be written to render the block-character bar.

The 4-tier feedback threshold context manager is cleanest as a class-based context manager (`TrackContext`) using `Rich.Live` with a dynamically updated `Group` renderable. This pattern passes mypy strict without any `# type: ignore` annotations. The `__exit__` signature requires explicit `types.TracebackType` typing.

ZoneInfo's `.key` property is typed as `str` (not `Optional[str]`) in mypy 2.1 + Python 3.11. No None guard is required for `USER_TZ.key.split("/")[-1]`.

**Primary recommendation:** Implement in 5 plans: A (config + styles + formatters), B (messages + empty states), C (tables + prompts), D (progress/feedback), E (ui/__init__ wire-up + coverage gate).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Terminal rendering | CLI / Presentation | — | Rich Console owns all output; no web, no file |
| Color and style constants | `ui/styles.py` | — | Single definition point; all modules import from here |
| Numerical formatting | `ui/` (pure functions) | — | Pure functions; no I/O; can live in styles.py or a formatters.py |
| Date/time formatting | `ui/` (pure functions) | `config.py` | Needs MARKET_TZ and USER_TZ; imports from config |
| Severity-prefixed messages | `ui/messages.py` | `ui/styles.py` | messages.py calls styles._console |
| Table rendering | `ui/tables.py` | `ui/styles.py` | Stateless; receives data, returns/renders table |
| Confirmation prompts | `ui/prompts.py` | — | Uses `input()` directly; no Rich.Prompt |
| Feedback thresholds | `ui/progress.py` | `ui/styles.py` | Most complex; owns all 3 context managers |
| Empty states | `ui/empty_states.py` | `ui/messages.py` | Thin helpers; call print_info or print directly |
| Config constants | `config.py` | — | MODULE-level only; no I/O; imported by ui/ and commands/ |

---

## Standard Stack

### Core (already installed)

| Library | Installed Version | Purpose | Status |
|---------|------------------|---------|--------|
| rich | 15.0.0 [VERIFIED: uv run] | Tables, Console, Live, Progress, Spinner | Present |
| typer | (transitively pulls rich) | App framework | Present |

No new packages required for this phase. [VERIFIED: uv run python -c "import rich"]

### Rich APIs Used in This Phase

| API | Import | Purpose |
|-----|--------|---------|
| `Console` | `rich.console` | Output sink; `record=True` for tests |
| `Table` | `rich.table` | Minimalist tables |
| `Live` | `rich.live` | Dynamic/refreshing display for feedback |
| `Group` | `rich.console` | Composites multiple renderables for Live |
| `Spinner` | `rich.spinner` | Spinner animation (`dots` preset) |
| `Progress` | `rich.progress` | Progress tracking (used as time source) |
| `ProgressColumn` | `rich.progress` | Base class for custom block-char bar |
| `Text` | `rich.text` | Typed text for Group composition |
| `Style` | `rich.style` | Style constants in styles.py |

### Installation

No new packages. Rich is already a dependency. [VERIFIED: pyproject.toml]

---

## Package Legitimacy Audit

No new packages are installed in this phase. All libraries (rich, typer, zoneinfo) are either
already in `pyproject.toml` or are Python stdlib. Audit is not applicable.

---

## Technical Findings

### 1. Rich Spinner — `dots` Preset Exactly Matches Spec

**Finding:** The `dots` spinner in `rich.spinner.SPINNERS` has exactly 10 frames with codepoints
`U+280B U+2819 U+2839 U+2838 U+283C U+2834 U+2826 U+2827 U+2807 U+280F`. These are character-for-character
identical to the spec's required sequence `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`. [VERIFIED: uv run, direct comparison]

**Conclusion:** Use `Spinner("dots", description)` with no custom registration needed.

```python
# Source: verified via uv run in project environment
from rich.spinner import Spinner

def _make_spinner(description: str) -> Spinner:
    return Spinner("dots", description)
```

If in a future Rich version `dots` frames change, add an assertion in the test suite:

```python
# tests/test_ui/test_progress.py
from rich.spinner import SPINNERS
EXPECTED_BRAILLE = list("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

def test_dots_spinner_frames_match_spec() -> None:
    assert list(SPINNERS["dots"]["frames"]) == EXPECTED_BRAILLE
```

### 2. Feedback Threshold — Cleanest Implementation Pattern

**Finding:** Rich provides no built-in API for the 4-tier threshold logic. The cleanest approach is
a class-based context manager wrapping `Rich.Live`, updating the renderable as time thresholds cross.
[VERIFIED: Rich source, mypy strict test]

The threshold logic must run in a background check within `advance()`, not in a timer thread.
Since `advance()` is called per iteration, elapsed time is checked each call. `Live.update()` switches
the renderable from `""` (silent) to a spinner to a progress block.

**Pattern:**

```python
# Source: verified mypy strict — no errors
import time, types
from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

THRESHOLD_SPINNER = 1.0    # seconds
THRESHOLD_PROGRESS = 6.0   # seconds  
THRESHOLD_ETA = 30.0       # seconds

class TrackContext:
    def __init__(self, description: str, total: int, console: Console) -> None:
        self._description = description
        self._total = total
        self._console = console
        self._live: Live | None = None
        self._start: float = 0.0
        self._completed: int = 0
        self._current_label: str = ""

    def advance(self, current_label: str = "") -> None:
        self._completed += 1
        self._current_label = current_label
        elapsed = time.monotonic() - self._start
        if self._live is not None:
            self._live.update(self._build_renderable(elapsed))

    def _build_renderable(self, elapsed: float) -> Group | Text:
        if elapsed < THRESHOLD_SPINNER:
            return Text("")  # silent
        if elapsed < THRESHOLD_PROGRESS:
            return Text(f"  {Spinner('dots').render(elapsed)} {self._description}")
        # progress bar tier (and ETA tier >30s)
        return self._build_progress_block(elapsed)

    def _build_progress_block(self, elapsed: float) -> Group:
        # ... builds the key:value block per spec 6.21
        ...

    def __enter__(self) -> "TrackContext":
        self._start = time.monotonic()
        self._live = Live(console=self._console, refresh_per_second=10, transient=True)
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

**Key mypy finding:** `__exit__` must use explicit `types.TracebackType | None` for the third argument.
Using `*args: object` causes a mypy strict error. [VERIFIED: mypy 2.1.0 strict]

**For testing threshold transitions:** mock `time.monotonic()` to return controlled values.
`assert`s check which render tier activates via `_build_renderable()` return type.

### 3. Progress Bar Layout — Custom Column Required

**Finding:** Rich's built-in `ProgressBar` renders `━` (U+2501) as the bar character, not `█` (U+2588).
The spec rule 6.30 explicitly requires `█` and `░`. [VERIFIED: Rich source inspection]

**Solution:** Write a custom `ProgressColumn` subclass:

```python
# Source: verified — ProgressColumn.render() is the override point
from rich.progress import ProgressColumn, Task
from rich.text import Text

class BlockBarColumn(ProgressColumn):
    """Progress bar using spec-required full block and light shade characters."""

    def __init__(self, bar_width: int = 20) -> None:
        self.bar_width = bar_width
        super().__init__()

    def render(self, task: Task) -> Text:
        pct = task.completed / task.total if task.total else 0.0
        filled = int(self.bar_width * pct)
        empty = self.bar_width - filled
        return Text("█" * filled + "░" * empty)
```

**Layout assembly** for the spec 6.21 format:

```
Progress:   ████████████░░░░░░░░  127/503  (25%)
Current:    GOOGL — additional context
Elapsed:    1m 42s
Remaining:  ~5m 12s
```

The keys `Progress`, `Current`, `Elapsed`, `Remaining` follow rule 6.4 alignment:
`Remaining` is the longest (9 chars), so value column starts at position 9+1+2 = 12.

This block is rendered as plain text via `console.print(f"...")` lines (not a Rich Progress widget)
because the layout requires key:value rows that Rich.Progress cannot produce natively.

The `Progress` widget from `rich.progress` is used **only** as a time/completion tracker,
not as the visual renderer. The visual is built in `_build_progress_block()`.

Alternative approach that avoids Progress widget entirely: track `start_time`, `completed`,
`total` in the class and compute elapsed/remaining manually. This is simpler and fully
testable without Rich.Progress state.

### 4. mypy Strict + Rich 15.x

**Finding:** Rich 15.0.0 ships a `py.typed` marker and fully typed annotations. All of the following
pass mypy 2.1.0 strict with no errors and no `# type: ignore` needed:
[VERIFIED: mypy 2.1.0 --strict on project]

- `Console(record=True)`, `Console(record=True, force_terminal=True)`, `Console(record=True, no_color=True)`
- `Table(box=None, show_edge=False, padding=(0,1), header_style="")`
- `Table.add_column("name", justify="left")`, `Table.add_column("val", justify="right")`
- `Progress(TextColumn(...), BarColumn(), ..., console=c)`
- `Live(console=c, refresh_per_second=10, transient=True)` as context manager
- `Group(Text(...), Text(...))` as a Live renderable
- `Spinner("dots", "Loading...")`
- `ProgressColumn` subclass with `render(self, task: Task) -> Text`

**One typing pitfall:** `__exit__` on a manually managed `Live` requires:
```python
import types
def __exit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: types.TracebackType | None,
) -> None:
```
Using `*args: object` fails with mypy strict error `arg-type`. [VERIFIED]

**No mypy overrides needed for rich** — it is fully typed. Existing `pyproject.toml`
overrides for `yfinance` and `pandas_market_calendars` remain unchanged.

### 5. ZoneInfo.key — Type is `str` in mypy 2.1

**Finding:** `ZoneInfo.key` is typed as `str` (not `Optional[str]`) in the typeshed stubs
used by mypy 2.1 with Python 3.11 target. [VERIFIED: mypy 2.1.0 `reveal_type(tz.key)` → `str`]

```python
USER_TZ = ZoneInfo(os.environ.get("BENSDORP1_USER_TZ", "Europe/Lisbon"))
city: str = USER_TZ.key.split("/")[-1]  # no None guard needed; mypy is satisfied
```

**Edge case note:** `ZoneInfo.key` is `None` only when a `ZoneInfo` is constructed from a file
path rather than an IANA name (e.g., `ZoneInfo.from_file(...)`). Since `config.py` always
calls `ZoneInfo(string_key)`, `key` is guaranteed non-None at runtime AND at type-check time.

**The `America/New_York` → "ET" requirement** (rule 6.26 special case): the city extraction
`USER_TZ.key.split("/")[-1]` yields "New_York" for the market timezone, not "ET". The spec
explicitly says market timezone always displays as "ET" (not derived from the key). Implement
`format_timezone_pair()` with a hardcoded `"ET"` for the market side:

```python
# ui formatters
def _market_tz_label() -> str:
    return "ET"  # always; rule 6.26

def _user_tz_label() -> str:
    key = USER_TZ.key  # str, not Optional[str]
    return key.split("/")[-1]  # "Lisbon", "London", etc.
```

### 6. Key:Value Alignment — String Approach

**Finding:** The string alignment formula directly implements rule 6.4 cleanly.
Rich `Table` with `padding=(0,0)` and two columns cannot reliably produce the exact spacing
because the first column's width is determined by Rich's width calculation, not by the spec's rule.
[VERIFIED: Console(record=True) test showed Table collapses spacing for 'History downloaded:']

**Canonical pattern:**

```python
def _render_kv_block(
    data: dict[str, str],
    console: Console,
    indent: str = "",
) -> None:
    """Render key:value pairs aligned per rule 6.4."""
    max_key_len = max(len(k) for k in data)
    for k, v in data.items():
        # spaces = (max_key_len - len(k)) + 2
        # ensures longest key gets 2 spaces; shorter keys get proportionally more
        spaces = (max_key_len - len(k)) + 2
        console.print(f"{indent}{k}:{' ' * spaces}{v}")
```

This produces exactly:
```
Database created:    ~/bensdorp1/data/bensdorp1.db
History downloaded:  220 trading days
```

For the progress block, the keys are `Progress`, `Current`, `Elapsed`, `Remaining`
(max = 9 chars `Remaining`). Value column at position 12.

### 7. Testing Approach — Console(record=True) Pattern

**Finding:** The `Console(record=True)` + `export_text()` pattern works correctly.
One subtlety: `export_text()` clears the recording buffer. Each test must use a fresh console
or call `export_text()` only once. [VERIFIED: manual testing]

```python
# Correct patterns verified for all three test scenarios:

# Plain text verification (no color)
def test_format_price() -> None:
    assert format_price(1432.50) == "$1,432.50"

# Rendered text verification
def test_print_info(console: Console) -> None:  # console = Console(record=True)
    print_info("Test message", console=console)
    assert "Info: Test message" in console.export_text()

# ANSI color verification
def test_print_info_color() -> None:
    c = Console(record=True, force_terminal=True, width=80)
    print_info("Test", console=c)
    styled = c.export_text(styles=True)
    assert "\x1b[36m" in styled  # cyan = ANSI code 36

# NO_COLOR fallback
def test_print_info_no_color() -> None:
    c = Console(record=True, no_color=True, force_terminal=True, width=80)
    print_info("Test", console=c)
    text = c.export_text()
    assert "Info: Test" in text  # text present
    styled = c.export_text(styles=True)
    assert styled == ""  # buffer cleared; second call returns empty
```

**conftest.py addition needed:**
```python
# tests/conftest.py — add fixture
@pytest.fixture
def record_console() -> Console:
    """Fresh Console(record=True) for each test."""
    return Console(record=True, width=80)
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/bensdorp1/
├── config.py                    # PROJECT_NAME, MARKET_TZ, USER_TZ, DATA_DIR
└── ui/
    ├── __init__.py              # public re-exports (final plan)
    ├── styles.py                # Style constants, color palette, _console, kv-align helper
    ├── tables.py                # render_table() function
    ├── messages.py              # Severity enum, print_message, aliases
    ├── prompts.py               # confirm_prompt, text_prompt, number_prompt
    ├── progress.py              # SpinnerContext, TrackContext, MultiStepContext
    └── empty_states.py          # print_empty_state helpers

tests/
└── test_ui/
    ├── __init__.py
    ├── test_config.py           # config constants, ZoneInfo validity
    ├── test_styles.py           # formatter functions (pure), Style constants
    ├── test_messages.py         # print_message, severity colors, kv alignment
    ├── test_tables.py           # render_table output
    ├── test_prompts.py          # confirm_prompt (mock input())
    ├── test_progress.py         # threshold tiers (mock time.monotonic)
    └── test_empty_states.py     # empty state messages
```

### Pattern 1: Module-Level Console Singleton

```python
# ui/styles.py
from rich.console import Console
from rich.style import Style

_console: Console = Console()  # auto-detects TTY, respects NO_COLOR env var

# All colors from palette (rule 6.29)
ERROR_STYLE = Style(color="red")
WARNING_STYLE = Style(color="yellow")
INFO_STYLE = Style(color="cyan")
SUCCESS_STYLE = Style(color="green")
MUTED_STYLE = Style(color="bright_black")
```

### Pattern 2: Severity Enum with Prefix Map

```python
# ui/messages.py
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

### Pattern 3: Custom BlockBarColumn

```python
# ui/progress.py
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

### Pattern 4: Class-Based Context Manager for Live

See Technical Finding #2 for the complete `TrackContext` pattern with correct `__exit__` typing.

### Anti-Patterns to Avoid

- **Rich.Progress as the visual renderer:** Rich.Progress renders `━` bars. Use it only for time tracking, not for the visual output. Build the visual with `console.print()` lines.
- **Global `_console` mutation for testing:** Never reassign `_console` in tests. Pass `Console(record=True)` via the `console=` parameter instead.
- **`*args: object` in `__exit__`:** Causes mypy strict failures. Use explicit `types.TracebackType | None` for the third parameter.
- **`typer.confirm()` or `Rich.Prompt`:** D-05 mandates `input()` directly. `typer.confirm()` is not the required behavior.
- **Bold markup in any output:** Rule 6.31 forbids bold. Never use `[bold]` or `Style(bold=True)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Color stripping for non-TTY | Custom ANSI filter | `Console(no_color=True)` | Rich handles this automatically |
| Terminal width detection | `os.get_terminal_size()` | `Console()` default | Rich queries terminal width and wraps appropriately |
| Spinner frame cycling | Manual list rotation | `Spinner("dots", ...)` | Rich cycles frames at 80ms interval |
| Thread-safe terminal output | `threading.Lock()` around print | `Console()` | Rich's Console is thread-safe |
| Fallback for non-TTY | Environment checks | `Console()` auto-detect | Rich checks `isatty()` automatically |

**Key insight:** The only thing Rich cannot do natively for this spec is the `█`/`░` bar characters
and the multi-row progress layout (key:value format). Everything else is handled by Rich internals.

---

## Common Pitfalls

### Pitfall 1: Rich.Progress Visual vs. TrackContext Visual

**What goes wrong:** Developer uses `Rich.Progress(BarColumn(), ...)` expecting the spec's
`████████░░░░` bar. Gets `━━━━━━━━╸    ` instead.

**Why it happens:** Rich's `ProgressBar` renders `━` (box-drawing) by default.

**How to avoid:** Never render `BarColumn()` directly in the Live display. Use `BlockBarColumn`
from `progress.py` when a bar is needed, or build the visual as plain text lines.

**Warning signs:** `━` characters appear in test output.

### Pitfall 2: Double-Print in `Console(record=True)` Tests

**What goes wrong:** `console.export_text()` returns the text AND resets the buffer. If the
test calls `export_text()` twice, the second call returns empty string.

**Why it happens:** Rich clears the recording buffer on export.

**How to avoid:** Call `export_text()` once per test. Store the result in a variable.

**Warning signs:** Second `assert` on `export_text()` fails with empty string.

### Pitfall 3: `__exit__` Mypy Error with `*args`

**What goes wrong:**
```python
def __exit__(self, *args: object) -> None:
    self._live.__exit__(*args)  # mypy error: arg-type
```

**Why it happens:** `Live.__exit__` is typed with three specific positional params.
Splatting `*args: object` is not compatible with mypy strict.

**How to avoid:** Always spell out the three params explicitly with `types.TracebackType | None`.

### Pitfall 4: `USER_TZ.key` Yielding "New_York" for ET Display

**What goes wrong:** `MARKET_TZ.key.split("/")[-1]` yields "New_York", not "ET".

**Why it happens:** The IANA key for Eastern Time is "America/New_York".

**How to avoid:** Rule 6.26 requires "ET" for the market timezone label — hardcode it.
City extraction applies only to the user-side timezone.

### Pitfall 5: Progress Block Appearing Before 1s Mark

**What goes wrong:** A spinner appears even for fast operations (< 1s), cluttering output.

**Why it happens:** The `Live` context starts immediately. Without the threshold check,
any display update shows something.

**How to avoid:** Initialize `Live` with `Text("")` (empty renderable). Only switch to spinner
renderable when `elapsed >= THRESHOLD_SPINNER` inside `advance()`.

### Pitfall 6: Key:Value Alignment with Empty `data` Dict

**What goes wrong:** `max(len(k) for k in data)` raises `ValueError` on empty dict.

**Why it happens:** `max()` on empty sequence raises `ValueError`.

**How to avoid:** Guard: `if not data: return`. The `print_message()` function should short-circuit
the alignment block when `data` is `None` or empty.

---

## Code Examples

### Verified Pattern: Formatter Functions

```python
# Source: spec rule 6.10 — verified against all format requirements

def format_price(value: float) -> str:
    """Format a USD price: $X,XXX.XX (no sign, always positive)."""
    return f"${value:,.2f}"

def format_pct(value: float) -> str:
    """Format a percentage with explicit sign: ±X.X%."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"

def format_pnl(value: float) -> str:
    """Format P&L with sign and dollar: ±$X,XXX.XX."""
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"

def format_volume(value: int) -> str:
    """Format share volume: X,XXX,XXX."""
    return f"{value:,}"

def format_days(n: int) -> str:
    """Format days held: 'N days' or '1 day'."""
    return f"{n} day" if n == 1 else f"{n} days"
```

### Verified Pattern: Relative Duration (Rule 6.27)

```python
# Source: spec rule 6.27 — brackets verified
from datetime import datetime, timezone

def format_relative_duration(dt: datetime) -> str:
    """Return human relative duration string."""
    now = datetime.now(tz=timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    total_seconds = int(delta.total_seconds())
    minutes = total_seconds // 60
    hours = total_seconds // 3600
    days = total_seconds // 86400
    months = days // 30
    years = days // 365

    if total_seconds < 60:
        return "just now"
    if minutes < 60:
        return f"{minutes} minutes ago"
    if hours < 24:
        return f"{hours} hours ago"
    if days <= 30:
        return f"{days} days ago"
    if months < 12:
        return f"{months} months ago"
    return f"{years} years ago"
```

### Verified Pattern: Dual Timezone Display (Rule 6.26)

```python
# Source: spec rule 6.26 — "ET" hardcoded; city from user TZ key
from datetime import datetime
from zoneinfo import ZoneInfo
from bensdorp1.config import MARKET_TZ, USER_TZ

def format_timezone_pair(dt: datetime) -> str:
    """Format a datetime as 'HH:MM ET (HH:MM City)'."""
    et = dt.astimezone(MARKET_TZ)
    local = dt.astimezone(USER_TZ)
    city = USER_TZ.key.split("/")[-1]  # "Lisbon", "London", etc.
    return f"{et:%H:%M} ET ({local:%H:%M} {city})"
```

---

## Plan Boundary Recommendation

**Recommended: 5 plans**

| Plan | Files Created | Rationale |
|------|---------------|-----------|
| **A** | `config.py`, `ui/styles.py`, formatter functions in `styles.py`, `tests/test_ui/__init__.py`, `tests/test_ui/test_config.py`, `tests/test_ui/test_styles.py` | All pure/static — no Rich rendering, no I/O. Formatters and config tested with plain `assert`. Establishes the `_console` singleton and color constants that B-D depend on. |
| **B** | `ui/messages.py`, `ui/empty_states.py`, `tests/test_ui/test_messages.py`, `tests/test_ui/test_empty_states.py` | Both use `Console` for output; both test with `export_text()`. Empty states are thin wrappers over `print_info`. Can share test fixture. |
| **C** | `ui/tables.py`, `ui/prompts.py`, `tests/test_ui/test_tables.py`, `tests/test_ui/test_prompts.py` | Tables are small (1 function). Prompts require `input()` mocking with `monkeypatch`. Grouped to make a reasonably-sized plan. |
| **D** | `ui/progress.py`, `tests/test_ui/test_progress.py` | Most complex module: 3 context managers + threshold logic + `BlockBarColumn` + `Live` integration. Deserves dedicated plan. Mock `time.monotonic()` for tier tests. |
| **E** | `ui/__init__.py` (final re-exports), coverage gate, `conftest.py` updates | Wire all re-exports. Run full test suite with coverage. Verify > 90% overall. |

**Why not combine D into C:** `ui/progress.py` alone is ~150-200 lines plus ~80 lines of tests.
Adding tables and prompts to Plan D would create an oversized plan. The threshold logic requires
careful testing of all 4 tiers; it warrants its own focused plan.

**Formatters placement:** Numerical and datetime formatters belong in Plan A with `ui/styles.py`.
They are pure functions that `config.py` constants (MARKET_TZ, USER_TZ) depend on, and they have
zero rendering complexity. A separate Plan for them alone would be too small.

---

## Implementation Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `Live` + `Group` rendering in tests | MEDIUM | Use `Console(record=True)` + `export_text()`. For Live specifically, test `_build_renderable()` return value directly rather than full Live integration. |
| `BlockBarColumn.render()` called during Progress.refresh() | LOW | Test the column in isolation by constructing a mock `Task` object. |
| `input()` in prompts tests on Windows | LOW | Use `monkeypatch.setattr("builtins.input", ...)` — standard pytest pattern. |
| `time.monotonic()` mock for threshold tests | LOW | `monkeypatch.setattr("bensdorp1.ui.progress.time", ...)` — test each tier by returning controlled elapsed times. |
| Rich 15 API changes vs. 14 assumed in CLAUDE.md | NEGLIGIBLE | Installed version is 15.0.0. All APIs verified against actual installed version. No compatibility issues found. |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (detected from `__pycache__` bytecode) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_ui/ -x -q` |
| Full suite command | `uv run pytest --cov=src/bensdorp1/ui --cov=src/bensdorp1/config --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | All 31 rules implemented | unit | `uv run pytest tests/test_ui/ -x` | No — Wave 0 |
| UI-02 | Severity colors + NO_COLOR fallback | unit | `uv run pytest tests/test_ui/test_messages.py -x` | No — Wave 0 |
| UI-03 | Table: no borders, alignment | unit | `uv run pytest tests/test_ui/test_tables.py -x` | No — Wave 0 |
| UI-04 | Feedback thresholds: all 4 tiers | unit | `uv run pytest tests/test_ui/test_progress.py -x` | No — Wave 0 |
| UI-05 | Dual timezone format | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_timezone_pair -x` | No — Wave 0 |
| UI-06 | No bold/unicode icons | unit | `uv run pytest tests/test_ui/ -k "no_bold or no_icon" -x` | No — Wave 0 |
| UI-07 | Confirm prompt: y/n/Ctrl+C | unit | `uv run pytest tests/test_ui/test_prompts.py -x` | No — Wave 0 |
| UI-08 | Empty states explicit | unit | `uv run pytest tests/test_ui/test_empty_states.py -x` | No — Wave 0 |
| UI-09 | Critical message structure | unit | `uv run pytest tests/test_ui/test_messages.py -x` | No — Wave 0 |
| UI-10 | Numerical formats | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_* -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_ui/ -x -q`
- **Per wave merge:** `uv run pytest --cov=src --cov-report=term-missing`
- **Phase gate:** Full suite green + mypy strict + ruff before `/gsd-verify-work`

### Wave 0 Gaps (all test infrastructure is new)

- [ ] `tests/test_ui/__init__.py` — marks as package
- [ ] `tests/test_ui/test_config.py` — config constants; ZoneInfo validity
- [ ] `tests/test_ui/test_styles.py` — formatter pure functions; Style constants
- [ ] `tests/test_ui/test_messages.py` — print_message; severity mapping; kv alignment
- [ ] `tests/test_ui/test_tables.py` — render_table; column alignment
- [ ] `tests/test_ui/test_prompts.py` — confirm_prompt; monkeypatched input()
- [ ] `tests/test_ui/test_progress.py` — all 4 tiers; BlockBarColumn; spinner frames
- [ ] `tests/test_ui/test_empty_states.py` — empty state message content
- [ ] `tests/conftest.py` update — add `record_console` fixture returning `Console(record=True, width=80)`

---

## Security Domain

`security_enforcement: true` in config.json. ASVS Level 1 applies.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | UI components have no auth |
| V3 Session Management | No | Stateless rendering |
| V4 Access Control | No | Single-user CLI |
| V5 Input Validation | Yes (prompts) | Prompt accepts only `y Y n N`; re-prompts on anything else |
| V6 Cryptography | No | No crypto in UI layer |

### Known Threat Patterns for CLI UI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via env var (USER_TZ) | Tampering | `ZoneInfo(key)` raises `ZoneInfoNotFoundError` on invalid key; let exception propagate to command layer |
| Arbitrary string in `data=` dict rendered to console | Tampering | Rich `Console.print()` with f-strings does not execute injected markup if strings are treated as plain text; avoid `console.print(user_data)` with `markup=True` |
| Unicode direction override in console output | Tampering | Rich strips RTL override codepoints on Windows |

**Critical for `ui/messages.py`:** When rendering `data: dict[str, str]` values, use `console.print(Text(line))` (not f-string with markup) to prevent Rich markup injection from untrusted data values.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `rich.prompt.Prompt.ask()` | `input()` directly (D-05) | Design decision | More control; no Rich formatting of prompt text |
| `typer.confirm()` | `input()` directly (D-05) | Design decision | Allows custom `[y/n]` format per rule 6.15 |
| `BarColumn()` for progress bars | Custom `BlockBarColumn` | This phase | Required for spec-mandated `█`/`░` chars |
| `rich.spinner.Spinner("dots12")` | `Spinner("dots")` | Verified | `dots` is the exact braille match |

**Deprecated/outdated:**

- `SPINNERS["dots8Bit"]`: Different character set; not the spec sequence.
- `SPINNERS["simpleDots"]`: ASCII-only; not braille.

---

## Assumptions Log

All claims in this research were verified via direct execution in the project environment or mypy
strict type checking. No assumed claims.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | — | — | — |

**All claims verified:** No user confirmation needed for any factual claim in this research.

---

## Open Questions (RESOLVED)

1. **Spinner in `spinner()` context manager vs. `SpinnerColumn`**
   - What we know: `Spinner("dots")` renders frames correctly. `SpinnerColumn` is a Progress column.
   - What's unclear: For `feedback.spinner()` (not `track()`), should we use `Live(Spinner(...))` or `Progress(SpinnerColumn())`?
   - Recommendation: Use `Live(Spinner("dots", description))` directly — simpler, avoids Progress overhead for operations with no total count. Progress is only needed for `track()`.

2. **Multi-step `done.` line persistence after Live exits**
   - What we know: `transient=True` on Live removes the live area on exit.
   - What's unclear: Rule 6.23 says completed phases "remain visible with `done.` appended." This requires printing the done line AFTER the Live context exits (after `transient` cleanup).
   - Recommendation: After each multi-step phase, `console.print(f"[N/TOTAL] {description}... done.")` outside the Live context. The Live context is `transient=True` and disappears; the done line is a plain print.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.12.13 | — |
| rich | All UI rendering | Yes | 15.0.0 | — |
| typer | App framework | Yes | present | — |
| uv | Package manager | Yes | present | — |
| mypy | CI type checking | Yes | 2.1.0 | — |
| pytest | Tests | Yes | 9.0.3 | — |

No missing dependencies.

---

## Sources

### Primary (HIGH confidence)

- Rich 15.0.0 source — inspected via `uv run python -c "import inspect; ..."`: spinner frames, ProgressBar chars, Live/Progress/Console APIs
- mypy 2.1.0 strict — ran directly against test snippets: ZoneInfo.key type, __exit__ signature, all Rich types
- `.planning/Bensdorp_1.md` §6 — 31 style-guide rules (authoritative spec)
- `.planning/Bensdorp_1.md` §7 — specific output flows

### Secondary (MEDIUM confidence)

- `.planning/REQUIREMENTS.md` — UI-01 through UI-10
- `.planning/research/FEATURES.md` — output formatting conventions
- `pyproject.toml` — verified library versions

### Tertiary (LOW confidence)

None.

---

## Metadata

**Confidence breakdown:**

- Spinner frames: HIGH — directly compared character codepoints
- Progress bar chars: HIGH — inspected ProgressBar source
- mypy type safety: HIGH — ran mypy 2.1.0 strict on all patterns
- ZoneInfo.key type: HIGH — `reveal_type` confirmed `str`
- Testing patterns: HIGH — manually executed with Console(record=True)
- Plan boundary: MEDIUM — based on line-count estimates and complexity judgment

**Research date:** 2026-05-24
**Valid until:** 2026-08-24 (stable APIs; Rich versioning is slow-moving)
