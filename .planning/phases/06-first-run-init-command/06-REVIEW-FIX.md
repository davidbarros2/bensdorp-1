---
phase: 06-first-run-init-command
fixed_at: 2026-05-24T00:00:00Z
review_path: .planning/phases/06-first-run-init-command/06-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-05-24
**Source review:** .planning/phases/06-first-run-init-command/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: `confirm_prompt` swallows `KeyboardInterrupt`

**Files modified:** `src/bensdorp1/ui/prompts.py`, `src/bensdorp1/commands/init.py`, `tests/test_ui/test_prompts.py`
**Commit:** 19f685a
**Applied fix:** Added `raise` after the abort message in `confirm_prompt`'s `except KeyboardInterrupt` handler so the exception propagates to callers. Updated the docstring to document the new `Raises` behaviour. In `init.py`, wrapped the pre-cash `confirm_prompt("Continue?")` call in its own `try/except KeyboardInterrupt` block (it was outside the existing cash-entry block). Updated `test_confirm_keyboard_interrupt` to use `pytest.raises(KeyboardInterrupt)` instead of asserting `result is False`.

---

### WR-01: `_store_cash` calls `datetime.now(UTC)` twice

**Files modified:** `src/bensdorp1/commands/init.py`
**Commit:** 801b6ff
**Applied fix:** Captured `now = datetime.now(UTC)` once at the top of `_store_cash` and reused the variable in both `.values(updated_at=now)` and `.on_conflict_do_update(set_={"updated_at": now})`.

---

### WR-02: `type: ignore[assignment]` on TrackContext

**Files modified:** `src/bensdorp1/commands/init.py`
**Commit:** 9ae08d5
**Applied fix:** Replaced `track: TrackContext = _track  # type: ignore[assignment]` with `assert isinstance(_track, TrackContext, ...)` and used `_track` directly in the loop body. Provides a runtime-checked narrowing with a descriptive error message.

---

### WR-03: `test_cash_validation_reprompts` only checks error message appears once

**Files modified:** `tests/test_commands/test_init.py`
**Commit:** 13cc2d1
**Applied fix:** Changed `assert "Error: Cash must be greater than zero." in result.output` to `assert result.output.count("Error: Cash must be greater than zero.") == 2`, ensuring both invalid inputs (0 and -100) trigger the validation error.

---

### WR-04: `_store_cash` untested against real DB

**Files modified:** `tests/test_commands/test_init.py`
**Commit:** e983ced
**Applied fix:** Added `test_store_cash_writes_to_config(db_engine: Engine)` using the shared `db_engine` fixture from `conftest.py`. The test calls `_store_cash(db_engine, 75_000.0)` then queries the config table directly to assert `row.value == "75000.00"`.

---

### IN-01: Private `_render_kv_block` imported directly from `bensdorp1.ui.styles`

**Files modified:** `src/bensdorp1/ui/styles.py`, `src/bensdorp1/ui/__init__.py`, `src/bensdorp1/ui/messages.py`, `src/bensdorp1/commands/init.py`, `tests/test_ui/test_styles.py`
**Commit:** 449d1bd
**Applied fix:** Renamed `_render_kv_block` to `render_kv_block` in `styles.py`. Added `render_kv_block` to `ui/__init__.py` imports and `__all__`. Updated `init.py` to import `render_kv_block` from `bensdorp1.ui` and removed the private deep-import. Updated `messages.py` (internal ui module) and `test_styles.py` to use the new public name.

---

### IN-02: No comment explaining `init` absent from stub parametrize

**Files modified:** `tests/test_cli.py`
**Commit:** 2431fbd
**Applied fix:** Added `# init is intentionally absent — it is a full implementation, not a stub` immediately before the `@pytest.mark.parametrize` decorator for `test_stub_exits_cleanly`.

---

## Skipped Issues

None — all findings were fixed.

---

_Fixed: 2026-05-24_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
