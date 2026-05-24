---
phase: 06-first-run-init-command
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/bensdorp1/commands/init.py
  - tests/test_cli.py
  - tests/test_commands/__init__.py
  - tests/test_commands/test_init.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the `init` command implementation and its test suite. The core happy-path
logic is well-structured — the guard, cash validation loop, and completion summary
are all present and correct. The critical issue is a behavioral mismatch between
`confirm_prompt`'s internal `KeyboardInterrupt` handler and `init.py`'s own
`try/except KeyboardInterrupt` block: on Ctrl+C during the "Confirm?" sub-prompt,
the system prints "Operation aborted" but then loops back to re-prompt the user,
producing a broken UX. Four warnings cover a duplicate `datetime.now(UTC)` call in
`_store_cash`, a type-system workaround with `type: ignore`, insufficient test
assertion coverage for validation re-prompts, and an unresolved `confirm_prompt`
double-message side-effect. Two info items flag a private-import boundary violation
and a minor test-suite gap.

---

## Critical Issues

### CR-01: `confirm_prompt` swallows `KeyboardInterrupt` — init Ctrl+C handling is broken for the "Confirm?" prompt

**File:** `src/bensdorp1/commands/init.py:154` (interaction with `src/bensdorp1/ui/prompts.py:37-40`)

**Issue:** `confirm_prompt` catches `KeyboardInterrupt` internally and returns `False`
instead of re-raising (prompts.py lines 37-40). When the user presses Ctrl+C at the
"Confirm?" prompt on line 154, `confirm_prompt` prints "Operation aborted. No changes
were made." and returns `False`. The `init.py` while-loop treats `False` as "user said
no" and loops back to call `number_prompt` again — so the abort message is printed but
the command does NOT exit. The `except KeyboardInterrupt` on line 157 of `init.py` can
only catch `KeyboardInterrupt` from `number_prompt`, not from `confirm_prompt`. The
result is a UX where the terminal shows the abort message then immediately re-prompts
for "Available cash in USD:", with no way to cleanly exit via Ctrl+C at the "Confirm?"
step.

Note: this also means `test_ctrl_c_during_cash_entry` only tests Ctrl+C during
`number_prompt` (which still raises correctly). There is no test for Ctrl+C during
the "Confirm?" sub-prompt.

**Fix:** `confirm_prompt` must re-raise `KeyboardInterrupt` after printing the abort
message, so callers can handle the exit at the appropriate level. Alternatively,
`init.py` must not rely on `confirm_prompt` raising — it should check a sentinel
return value. The cleanest fix is to stop swallowing in `confirm_prompt`:

```python
# ui/prompts.py — confirm_prompt, lines 37-40
except KeyboardInterrupt:
    con.print()
    con.print(Text("Operation aborted. No changes were made."))
    raise  # re-raise so callers' except KeyboardInterrupt blocks fire
```

If `confirm_prompt` must keep swallowing for its own callers, then `init.py` must
detect the abort differently — but that requires an API change. The re-raise approach
is the correct fix; callers that previously relied on silent return `False` must be
audited.

---

## Warnings

### WR-01: `_store_cash` calls `datetime.now(UTC)` twice in the same upsert — timestamps can diverge

**File:** `src/bensdorp1/commands/init.py:76,82`

**Issue:** The `sqlite_insert().values()` call on line 76 computes `datetime.now(UTC)`,
and the `on_conflict_do_update(set_=...)` dict on line 82 computes `datetime.now(UTC)`
again independently. On a conflict (re-init scenario that bypasses the guard), the
`updated_at` stored in the DB corresponds to the second call, which will be microseconds
later than the first. The two calls also add unnecessary ambiguity about which timestamp
the record holds on the insert path vs. the update path.

**Fix:** Capture the timestamp once and reuse it:

```python
def _store_cash(engine: Engine, amount: float) -> None:
    now = datetime.now(UTC)
    stmt = (
        sqlite_insert(config_table)
        .values(
            key="available_cash",
            value=f"{amount:.2f}",
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": f"{amount:.2f}", "updated_at": now},
        )
    )
    with engine.connect() as conn:
        conn.execute(stmt)
        conn.commit()
```

---

### WR-02: `type: ignore[assignment]` at line 190 papers over an unresolved type mismatch

**File:** `src/bensdorp1/commands/init.py:190`

**Issue:** `ms.step()` is declared to yield `SpinnerContext | TrackContext`. When
`total` is provided, the runtime value is always a `TrackContext`, but the static type
remains the union. The code uses `type: ignore[assignment]` to force-cast `_track` to
`TrackContext` rather than using a type guard or narrowing. This suppresses a mypy
error that would catch a real bug if `step()` ever returns the wrong type.

**Fix:** Use `assert isinstance` for a checked narrowing rather than a bare ignore:

```python
with ms.step("Downloading price history", total=len(symbols)) as _track:
    assert isinstance(_track, TrackContext), (
        f"Expected TrackContext from ms.step(total=...), got {type(_track)!r}"
    )
    for symbol in symbols:
        update_price_data(engine, [symbol])
        _track.advance(symbol)
```

This removes the `# type: ignore[assignment]` and provides a runtime assertion that
documents the invariant. Alternatively, add an `@overload` to `MultiStepContext.step`
so mypy infers the correct return type when `total` is provided.

---

### WR-03: `test_cash_validation_reprompts` only asserts the error message appears once, not twice

**File:** `tests/test_commands/test_init.py:72,75`

**Issue:** The test feeds `"y\n0\n-100\n50000\ny\n"` — two invalid values (0 and -100)
and one valid (50000). The assertion only checks that "Error: Cash must be greater than
zero." appears in the output (substring match), which passes even if only one of the two
rejections produced the error message. A regression where the loop fails to re-prompt on
negative values (for example, checking `cash < 0` instead of `cash <= 0`) would still
pass this test.

**Fix:** Assert the error message appears exactly twice:

```python
assert result.output.count("Error: Cash must be greater than zero.") == 2
```

---

### WR-04: `_store_cash` is never tested against a real database

**File:** `tests/test_commands/test_init.py:27-52`

**Issue:** In `test_happy_path`, `get_engine` is mocked to return a `MagicMock`.
`_store_cash` is not mocked, so it calls `mock_engine.connect()`, which MagicMock
satisfies silently. The actual SQL statement is never executed against SQLite. Any
regression in `_store_cash` (wrong column name, type error in the upsert, schema
mismatch) would not be caught by this test suite. There is no standalone unit test for
`_store_cash` with the `db_engine` fixture.

**Fix:** Add a focused test for `_store_cash` using the `db_engine` fixture from
`conftest.py`:

```python
def test_store_cash_writes_to_config(db_engine: Engine) -> None:
    from bensdorp1.commands.init import _store_cash
    from sqlalchemy import select
    from bensdorp1.db.schema import config as config_table

    _store_cash(db_engine, 75_000.0)

    with db_engine.connect() as conn:
        row = conn.execute(
            select(config_table).where(config_table.c.key == "available_cash")
        ).one()
    assert row.value == "75000.00"
```

---

## Info

### IN-01: Private symbol `_render_kv_block` imported directly from `bensdorp1.ui.styles`, violating stated module boundary

**File:** `src/bensdorp1/commands/init.py:35`

**Issue:** The module docstring of `bensdorp1.ui.__init__` explicitly states "All
commands...consume only the names exported here — never deep-import from
ui.styles/messages/tables/prompts/progress/empty_states." Line 35 of `init.py`
imports the private `_render_kv_block` directly from `bensdorp1.ui.styles`, bypassing
this boundary and coupling the command to an internal implementation detail.

**Fix:** Promote `_render_kv_block` to the public `bensdorp1.ui` surface. Remove the
leading underscore, add it to `ui/__init__.py`'s imports and `__all__`, then update
`init.py` to use the public import:

```python
# init.py — replace the private import
from bensdorp1.ui import (
    ...,
    render_kv_block,  # promoted from _render_kv_block
)
```

---

### IN-02: `test_stub_exits_cleanly` in `test_cli.py` does not list `init` — absence is implicit and could confuse future maintainers

**File:** `tests/test_cli.py:36-57`

**Issue:** `test_stub_exits_cleanly` checks that every stub command exits 0 and prints
"Not yet implemented." The list (lines 37-51) omits `init`, which is correct because
`init` is no longer a stub. However, `test_help_subcommand_shows_help` (lines 60-83)
does include `init`, making the asymmetry non-obvious. There is no comment explaining
that `init` was deliberately excluded from the stub list.

**Fix:** Add a one-line comment to the parametrize list noting that `init` is
intentionally absent:

```python
# init is intentionally absent — it is a full implementation, not a stub
@pytest.mark.parametrize(
    "cmd",
    [
        "restore",
        ...
    ],
)
def test_stub_exits_cleanly(cmd: str) -> None:
```

---

_Reviewed: 2026-05-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
