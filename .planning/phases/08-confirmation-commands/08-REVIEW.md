---
phase: 08-confirmation-commands
reviewed: 2026-05-25T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - src/bensdorp1/commands/buy.py
  - src/bensdorp1/commands/sell.py
  - src/bensdorp1/commands/fix.py
  - src/bensdorp1/db/schema.py
  - tests/test_commands/test_buy.py
  - tests/test_commands/test_sell.py
  - tests/test_commands/test_fix.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-05-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

The three command modules (buy, sell, fix) implement the confirmation workflow
described in the phase plan. SQL injection prevention is solid throughout: all
DB writes use SQLAlchemy ORM `insert`/`update` with bound parameters, and the
two `text()` calls in sell.py use named-parameter dicts. KeyboardInterrupt
handling is consistent and correct. The buy/sell happy paths are well-covered by
integration tests against a real SQLite engine.

The primary blocker is a missing input validation in `fix.py`: the field-editing
loop accepts zero and negative values for price and shares with no guard,
allowing corrupt values to be written directly to the DB. Beyond that, four
quality/robustness warnings were found, and three informational items.

---

## Critical Issues

### CR-01: fix.py accepts zero or negative price and shares without validation

**File:** `src/bensdorp1/commands/fix.py:179` (buy price), `fix.py:190` (shares), `fix.py:219` (sell price)

**Issue:** The field-editing loop parses `new_price` and `new_shares` from raw
user input but never validates that they are greater than zero. A user who
types `0` or `-50` will pass the parse step (`float()` / `int()` succeed on
those inputs) and the values are written directly to the database. `buy.py`
correctly guards with `if price <= 0 or shares <= 0` (line 98); `fix.py` has
no equivalent gate. This allows `entry_close = 0`, which would make every
downstream stop-loss calculation (`initial_stop = 0 * 0.93 = 0`) silently
wrong, and `realized_pnl` arithmetic on zero entry price would produce
economically meaningless values.

**Fix:** Add explicit range checks immediately after each successful `float()`
/ `int()` parse, mirroring the guard already in buy.py:

```python
# After parsing new_price (buy path, ~line 180)
if new_price <= 0:
    print_error("Price must be greater than zero.", console=console)
    raise typer.Exit(code=1) from None

# After parsing new_shares (buy path, ~line 191)
if new_shares <= 0:
    print_error("Shares must be greater than zero.", console=console)
    raise typer.Exit(code=1) from None

# After parsing new_price (sell path, ~line 220)
if new_price <= 0:
    print_error("Price must be greater than zero.", console=console)
    raise typer.Exit(code=1) from None
```

---

## Warnings

### WR-01: sell.py — silent fallback in `_REASON_MAP` corrupts `closed_reason` for unknown trigger strings

**File:** `src/bensdorp1/commands/sell.py:162`

**Issue:** `_REASON_MAP.get(trigger_row.reason, "stop_trailing")` silently maps
any trigger reason string that is not in the map to `"stop_trailing"`. The map
currently covers the two known values (`"Trailing stop"` and `"Initial stop"`).
If a future scan phase introduces a third exit reason (e.g., `"Index exit"` or
`"Regime change"`), the stored `closed_reason` will be `"stop_trailing"` with
no warning. This corrupts the audit trail silently.

**Fix:** Remove the default fallback and raise an explicit error on unknown
reason strings:

```python
mapped = _REASON_MAP.get(trigger_row.reason)
if mapped is None:
    print_error(
        f"Unrecognised exit trigger reason: {trigger_row.reason!r}.",
        body=["Use --manual to record this sell with a custom reason."],
        console=console,
    )
    raise typer.Exit(code=1)
closed_reason = mapped
```

### WR-02: fix.py — sell-side `realized_pnl` silently overwrites with NULL when only date or manual reason changes

**File:** `src/bensdorp1/commands/fix.py:269-270`

**Issue:** When fixing a closed position and the user changes only the date or
the manual reason (not the exit price), the code takes the `else` branch:
`new_realized_pnl = current_realized_pnl`. This is then passed as
`realized_pnl=new_realized_pnl` in the UPDATE (line 407). If a prior database
migration or a manually-inserted row left `realized_pnl` as `NULL`, the UPDATE
will write `NULL` back and the impact-display block (lines 350-365) will show
`"N/A -> N/A"` with no error. More importantly, this means a date-only fix on a
position whose `realized_pnl` was legitimately computed will preserve NULL
rather than re-computing. While the current `sell.py` always sets
`realized_pnl`, the schema declares it nullable and the fix command should
re-compute rather than blindly preserve the stored value.

**Fix:** Always recompute `realized_pnl` from `new_price` and
`current_entry_close` in the sell path, regardless of what changed:

```python
else:
    new_initial_stop = 0.0  # not used for sell
    new_realized_pnl = (new_price - current_entry_close) * current_shares
```

This is idempotent when the price is unchanged and eliminates the NULL
propagation risk.

### WR-03: test_fix.py — sell-side fix path has zero test coverage

**File:** `tests/test_commands/test_fix.py`

**Issue:** The test file contains three tests: `test_no_transaction`,
`test_no_changes`, and `test_price_change_updates_stop`. All three exercise the
buy path only (`target_kind == "buy"`). The sell path (fixing a closed
position) — including the `closed_manual_reason` update, `realized_pnl`
recalculation, diff rendering, and the ORM UPDATE — is completely untested.
The bug in CR-01 (zero-price validation) and the issue in WR-02 (NULL
`realized_pnl`) are both on the sell path and have no test that would catch
them.

**Fix:** Add at minimum one integration test seeding a closed position and
invoking `fix SYMBOL` with a price correction, then asserting
`exit_price`, `realized_pnl`, and `closed_manual_reason` in the DB and an
`audit_log` row with `"transaction_corrected"` event type.

### WR-04: buy.py — price/shares validation executes after two DB round-trips

**File:** `src/bensdorp1/commands/buy.py:97-104`

**Issue:** The check `if price <= 0 or shares <= 0` at line 98 is labelled
"step C.3" in the comments, but it runs after two `engine.connect()` blocks
(steps C.1 and C.2, lines 68-95). A caller passing `price=0, shares=0` will
trigger two database queries before receiving the validation error. While not
a correctness bug (the DB write is still prevented), it is an inconsistency
with the validation-first convention implied by the spec's D-04 ordering, and
means the error message comes after the "not a valid S&P 500 constituent" check
rather than before it, which can confuse the user if both conditions hold.

**Fix:** Move the `price <= 0 or shares <= 0` check to the top of the function,
before the first `engine.connect()` call:

```python
# Validate price and shares first (fast, no DB required)
if price <= 0 or shares <= 0:
    print_error(
        "Price and shares must be greater than zero.",
        data={"Price": format_price(price), "Shares": str(shares)},
        console=console,
    )
    raise typer.Exit(code=1)
```

---

## Info

### IN-01: `SEPARATOR` constant duplicated across three modules

**File:** `src/bensdorp1/commands/buy.py:31`, `sell.py:38`, `fix.py:33`

**Issue:** All three command modules independently define
`SEPARATOR: str = "=" * 64`. If the separator length ever needs to change, it
must be updated in three places.

**Fix:** Move `SEPARATOR` to a shared location such as
`src/bensdorp1/ui/styles.py` (which already owns styling constants) or a new
`src/bensdorp1/commands/_shared.py`, and import it in each command module.

### IN-02: test_sell.py — missing test for "no open position" error path

**File:** `tests/test_commands/test_sell.py`

**Issue:** The test file covers `test_no_exit_trigger`, the happy path, and the
manual sell. It does not cover the case where `pos_row is None` (line 102 of
sell.py) — i.e., the user calls `sell SYMBOL PRICE` for a symbol with no open
position. This error branch has no test.

**Fix:** Add a mock-based test analogous to `test_no_exit_trigger` that sets
`fetchone.return_value = None` for the initial position lookup and asserts
`exit_code == 1` and `"No open position"` in output.

### IN-03: fix.py — `--date` is a dead parameter

**File:** `src/bensdorp1/commands/fix.py:39-44`

**Issue:** The `date` parameter is declared with `typer.Option` and appears in
CLI help text, but is immediately assigned to `_unused` (line 44) and never
consulted. A user who passes `--date 2026-05-01` will receive no error and no
indication the flag was ignored. If this is truly reserved, it should either be
omitted from the CLI surface entirely or documented with a `hidden=True` in the
`typer.Option()` call so it does not pollute `--help` output.

**Fix:**
```python
date: str | None = typer.Option(
    None, "--date", help="(Reserved; unused in Phase 8.)", hidden=True
),
```
Or remove the parameter until it has an implementation.

---

_Reviewed: 2026-05-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
