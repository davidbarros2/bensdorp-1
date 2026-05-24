---
phase: 05-ui-components
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/bensdorp1/config.py
  - src/bensdorp1/ui/__init__.py
  - src/bensdorp1/ui/styles.py
  - src/bensdorp1/ui/messages.py
  - src/bensdorp1/ui/empty_states.py
  - src/bensdorp1/ui/tables.py
  - src/bensdorp1/ui/prompts.py
  - src/bensdorp1/ui/progress.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-05-24
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the `config.py` and full `ui/` subpackage introduced in Phase 5. The
markup-injection mitigations in `messages.py` and `empty_states.py` are solid —
`Text()` wrappers and `markup=False` are used consistently. Style constants obey
rule 6.31 (no bold/italic/underline). The `format_timezone_pair` literal-ET
decision is correctly documented per D-08. Architecture constraint D-08 (no
imports from db/data/strategy/commands) is respected across all files.

Two critical defects were found: a `ZeroDivisionError` reachable at runtime in
`TrackContext._estimate_remaining` and a Rich markup injection vector in
`render_table` (row cell values rendered with markup enabled). Three warnings
cover `text_prompt`/`number_prompt` missing `KeyboardInterrupt` handling, a
dead exported class (`BlockBarColumn`), and silent wrong output from naive
datetimes passed to `format_timezone_pair`. Two info items cover a future-
datetime edge case and a `format_relative_duration` singularity ("1 minutes ago").

---

## Critical Issues

### CR-01: ZeroDivisionError in `TrackContext._estimate_remaining` when `elapsed == 0`

**File:** `src/bensdorp1/ui/progress.py:208`
**Issue:** `_estimate_remaining` computes `rate = self._completed / elapsed`.
When `advance()` is called at the very first monotonic tick (elapsed is
effectively zero) — which happens in unit tests that mock `time.monotonic` to a
fixed value and call `advance()` before advancing the clock — this raises
`ZeroDivisionError`. The downstream `if rate > 0` guard on line 210 is
evaluated _after_ the division, not before it.

```python
# BUG — current code
def _estimate_remaining(self, elapsed: float) -> float:
    if self._completed == 0:
        return 0.0
    rate = self._completed / elapsed          # ZeroDivisionError when elapsed == 0
    remaining_items = self._total - self._completed
    return remaining_items / rate if rate > 0 else 0.0
```

**Fix:** Guard `elapsed` before dividing:

```python
def _estimate_remaining(self, elapsed: float) -> float:
    if self._completed == 0 or elapsed <= 0:
        return 0.0
    rate = self._completed / elapsed
    remaining_items = self._total - self._completed
    return remaining_items / rate if rate > 0 else 0.0
```

---

### CR-02: Rich markup injection in `render_table` row cells

**File:** `src/bensdorp1/ui/tables.py:39`
**Issue:** `table.add_row(*row)` passes caller-supplied strings to Rich's
`Table.add_row()`. Rich's default rendering interprets markup in cell strings.
A stock symbol or other data value containing `[` characters (e.g.,
`[red]HACK[/red]` or a ticker like `[TGT]`) will be interpreted as Rich markup,
producing garbled output or injected styles. `messages.py` explicitly wraps
every caller-supplied string in `Text()` for this reason; `tables.py` does not.

```python
# BUG — current code
for row in rows:
    table.add_row(*row)       # markup_on by default in each cell
```

**Fix:** Wrap each cell in `Text()` to prevent markup parsing:

```python
from rich.text import Text

for row in rows:
    table.add_row(*[Text(cell) for cell in row])
```

Alternatively, pass `markup=False` if `add_row` gains that parameter in a
future Rich version — but `Text()` wrapping is the portable, current-API-safe
approach.

---

## Warnings

### WR-01: `text_prompt` and `number_prompt` do not handle `KeyboardInterrupt`

**File:** `src/bensdorp1/ui/prompts.py:63,85`
**Issue:** `confirm_prompt` explicitly catches `KeyboardInterrupt` and prints
the rule 6.18 cancellation message before returning `False`. `text_prompt` and
`number_prompt` do not. A Ctrl+C during either prompt will propagate a raw
`KeyboardInterrupt` to the caller, bypassing the cancellation message required
by rule 6.18. Commands that call `text_prompt` or `number_prompt` would have to
re-implement this handling themselves — inconsistent and error-prone.

**Fix:** Apply the same pattern as `confirm_prompt` to both functions:

```python
def text_prompt(label: str, *, console: Console | None = None) -> str:
    con = console if console is not None else _default_console
    while True:
        try:
            raw = input(f"Enter {label}: ").strip()
        except KeyboardInterrupt:
            con.print()
            con.print(Text("Operation aborted. No changes were made."))
            raise  # or return a sentinel; caller must decide action
        if raw:
            return raw
```

Note: the function cannot return an empty string as a sentinel without
changing its documented return type. The cleanest resolution is to catch
`KeyboardInterrupt`, print the message, and re-raise so the command's
top-level handler can exit cleanly. Update `number_prompt` the same way.

---

### WR-02: `BlockBarColumn` is exported but never used; its `render` has a latent `TypeError`

**File:** `src/bensdorp1/ui/progress.py:34-50` and `ui/__init__.py:11`
**Issue:** `BlockBarColumn` is a `ProgressColumn` subclass intended for use
with Rich's `Progress` widget. However, `TrackContext._build_progress_block`
builds the progress bar inline using plain string arithmetic — it never
instantiates `BlockBarColumn`. The class is exported in `ui/__init__.py` and
`__all__`, creating a false expectation that it integrates with `TrackContext`.

Additionally, `BlockBarColumn.render` accesses `task.total` without
handling the case where Rich passes `total=None` (Rich's `Task.total` is
`Optional[float]`). The guard `if task.total` catches `None` correctly for the
falsy check, but the division `task.completed / task.total` on line 47 would
raise `TypeError` if `total` is `None` and somehow the guard was bypassed.
This is not reachable today since the column is unused, but it is a defect in
the dead code.

**Fix:** Either (a) integrate `BlockBarColumn` into `TrackContext` so it is
actually used, or (b) remove it from the public API and `__all__`. If keeping
it, fix the `render` method:

```python
def render(self, task: Task) -> Text:
    total = task.total or 0.0          # treat None as 0
    pct = (task.completed / total) if total > 0 else 0.0
    filled = int(self.bar_width * pct)
    empty = self.bar_width - filled
    return Text("█" * filled + "░" * empty)
```

---

### WR-03: `format_timezone_pair` silently produces wrong output for naive datetimes

**File:** `src/bensdorp1/ui/styles.py:92`
**Issue:** `dt.astimezone(MARKET_TZ)` called on a naive `datetime` (one without
`tzinfo`) will interpret the naive datetime using the system's local timezone
before converting to Eastern Time. On a developer machine in a different
timezone (e.g., UTC+1), the displayed ET time will be off by the local offset.
The function's docstring does not require the caller to pass a timezone-aware
datetime, making this a silent contract gap. Any command that constructs a
naive `datetime` from a SQLite date string and calls `format_timezone_pair`
will display the wrong time without raising an error.

**Fix:** Add a runtime guard:

```python
def format_timezone_pair(dt: datetime) -> str:
    """Format a datetime as 'HH:MM ET (HH:MM City)' (rule 6.26).

    Args:
        dt: Timezone-aware datetime. Naive datetimes are rejected.
    """
    if dt.tzinfo is None:
        raise ValueError(
            f"format_timezone_pair requires a timezone-aware datetime; got naive {dt!r}"
        )
    et = dt.astimezone(MARKET_TZ)
    local = dt.astimezone(USER_TZ)
    city = USER_TZ.key.split("/")[-1]
    return f"{et:%H:%M} ET ({local:%H:%M} {city})"
```

Alternatively, annotate the parameter as `datetime` with a note in the
docstring ("must be timezone-aware") and add an assertion — but a `ValueError`
with a descriptive message is more debuggable.

---

## Info

### IN-01: `format_relative_duration` uses singular "1 minutes ago" / "1 hours ago"

**File:** `src/bensdorp1/ui/styles.py:132-133`
**Issue:** The function returns `f"{minutes} minutes ago"` and `f"{hours}
hours ago"` without pluralization guards. When `minutes == 1` the output is
"1 minutes ago"; when `hours == 1` the output is "1 hours ago". The spec
example shows "N minutes ago" as a bracket label, not a sample value, so it
does not demonstrate singulars — but English grammar requires "1 minute ago"
and "1 hour ago". The `format_days` function (line 62) correctly handles
singular/plural, establishing a precedent.

**Fix:**

```python
if minutes < 60:
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit} ago"
if hours < 24:
    unit = "hour" if hours == 1 else "hours"
    return f"{hours} {unit} ago"
```

Apply the same pattern to "months" and "years" for completeness.

---

### IN-02: `format_relative_duration` silently returns "just now" for future datetimes

**File:** `src/bensdorp1/ui/styles.py:121,128`
**Issue:** `delta = now - dt.astimezone(UTC)` yields a negative `timedelta`
when `dt` is in the future. `int(delta.total_seconds())` then yields a
negative integer. All comparisons (`< 60`, `< 60`, `< 24`, `<= 30`, `< 12`)
are true for any sufficiently negative value on the wrong branch — in practice
the function falls through to `return "just now"` for a slightly-future
timestamp and would return `"just now"` for any future timestamp where
`total_seconds < 0` (since `0 < 60` is still true after the first branch).
This is wrong but not a crash. The function is intended for "last scan" display
where a future timestamp would indicate a data integrity problem.

**Fix:** Clamp to zero or raise:

```python
total_seconds = max(0, int(delta.total_seconds()))
```

This ensures future datetimes display as "just now" intentionally and
consistently rather than by accident.

---

_Reviewed: 2026-05-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
