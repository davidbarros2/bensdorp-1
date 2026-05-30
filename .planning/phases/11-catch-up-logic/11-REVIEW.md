---
phase: 11-catch-up-logic
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/bensdorp1/commands/_scan_engine.py
  - src/bensdorp1/commands/events.py
  - src/bensdorp1/data/__init__.py
  - src/bensdorp1/data/prices.py
  - src/bensdorp1/db/engine.py
  - src/bensdorp1/db/schema.py
  - tests/test_commands/test_catchup.py
  - tests/test_commands/test_scan.py
  - tests/test_commands/test_scan_engine.py
findings:
  critical: 4
  warning: 6
  info: 3
  total: 13
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-05-30
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 11 implements catch-up logic, split detection, delist flagging, and regime-flip
events. The overall architecture is sound and the SQLAlchemy usage is parameterized
throughout. However, four blocking defects were found that can cause data corruption,
incorrect triggered-scan output, silent audit failures, and a semantic bug in the
catch-up window trigger guard. Six warnings address reliability gaps under edge-case
inputs or partial failures.

---

## Critical Issues

### CR-01: CATCH_UP_PERFORMED audit event logged for single-day absence (off-by-one vs. spec)

**File:** `src/bensdorp1/commands/_scan_engine.py:282-284`

**Issue:** The comment at line 282 claims `len >= 1` satisfies the spec §7.6 "N >= 2"
threshold, but the condition `if len(missed_list) >= 1:` fires when only **one** trading
day was missed. A single missed day means the user was absent for exactly one day, not
two. The spec text "at least 2 elapsed trading days" is quoted in the comment itself,
yet the guard contradicts it. Consequence: `CATCH_UP_PERFORMED` is written to the
audit log on every ordinary one-day absence (e.g. the user scans Monday after a
Friday scan), inflating audit noise and misrepresenting what happened. The catch-up
summary block at the render step has the same threshold; if the intent is to also show
the catch-up block for a 1-day absence, the audit comment must be corrected. If not,
both places must use `>= 2`.

**Fix:** Align the guard with the stated spec requirement (and the comment's own claim):

```python
# CATCH_UP_PERFORMED: logged when at least 1 missed trading day exists
# (spec §7.6: "N >= 1" trading days missed)
if len(missed_list) >= 1:   # keep as-is if the spec really means >= 1
```

OR — if the spec truly requires two missed days before the event fires:

```python
if len(missed_list) >= 2:
    log_event(engine, AuditEventType.CATCH_UP_PERFORMED, ...)
```

The comment, code condition, and spec reference must all agree. The current state is
self-contradictory.

---

### CR-02: Symbol extraction from event string is fragile — breaks silently if format changes

**File:** `src/bensdorp1/commands/_scan_engine.py:185-188`

**Issue:** `run_scan` extracts the position symbol from the rendered event string by
splitting on the double-space separator `"  "` and taking `[0]`:

```python
for ev in delisted_events:
    sym = ev.split("  ")[0]
    catch_up_events.setdefault(sym, []).append(ev)
```

`render_removed_from_sp500` (events.py:71-88) indeed uses `f"{symbol}  Removed…"`, so
today the extraction works. However:

1. This couples the **rendering layer** to the **data layer** — a template wording
   change (e.g. replacing the double-space separator with a newline, a colon, or a
   tab) will silently create a corrupt key in `catch_up_events` (e.g.
   `"SIVB  Removed from S&P 500"` instead of `"SIVB"`), meaning the event is
   displayed under the wrong position or lost entirely.
2. `_detect_delisted_positions` already receives `open_positions` — it knows the
   symbol of every affected position without any string parsing.

**Fix:** Return `(symbol, event_str)` pairs from `_detect_delisted_positions` instead
of just strings, or pass the symbol separately alongside the event:

```python
# _detect_delisted_positions returns list[tuple[str, str]]
delisted_events = _detect_delisted_positions(engine, open_positions, constituents)
for sym, ev in delisted_events:
    catch_up_events.setdefault(sym, []).append(ev)
```

This removes the dependency on the rendered template format entirely.

---

### CR-03: Template 7 (market delist) added even for positions already flagged delisted=1

**File:** `src/bensdorp1/commands/_scan_engine.py:206-213`

**Issue:** The Template 7 check at step 5b runs unconditionally against
`open_positions` (after `_update_position_stops` has been called):

```python
if missed_list:
    for pos in open_positions:
        closes_on_missed = [
            _get_close_for_day(price_dfs, pos.symbol, d) for d in missed_list
        ]
        if all(c is None for c in closes_on_missed):
            delist_ev = render_market_delist(pos.symbol, delist_date=None)
            catch_up_events.setdefault(pos.symbol, []).append(delist_ev)
```

This fires for **any** position whose symbol has no price rows on missed days,
including positions that were already flagged `delisted=1` by a prior scan (e.g.
the stock was removed from the index last week and has been sitting with
`delisted=1` in the DB ever since). On every subsequent scan where the
already-delisted stock still has no price data, a new Template 7 event will be
appended to `catch_up_events`, and `render_market_delist` will be shown again in
the output even though `_detect_delisted_positions` correctly skips positions with
`delisted == 1` (D-11 set-once semantics). The Template 7 path has no equivalent
idempotency guard.

Additionally, a symbol with no price data on missed days is not necessarily
delisted — it could simply be a data-fetch failure or a non-trading day not
captured by `get_trading_days`. The check `all(c is None for c in closes_on_missed)`
is a heuristic and should not silently merge with the delist-flagging path (which
already handled the S&P 500 removal case).

**Fix:** Add the same `pos.delisted == 1` guard that `_detect_delisted_positions`
uses, and separate the two delist heuristics so Template 4 and Template 7 cannot
both fire for the same position in the same scan:

```python
if missed_list:
    for pos in open_positions:
        if pos.delisted == 1:
            continue  # already flagged — D-11 set-once; no Template 7 repeat
        # ... rest of the check
```

---

### CR-04: `_apply_splits` sequential update uses stale `before_*` snapshot after first split

**File:** `src/bensdorp1/commands/_scan_engine.py:580-680`

**Issue:** When a position has **two splits in the same window** (rare but possible —
e.g. a 2:1 in January and another 3:2 in March, both within the same catch-up gap),
the inner loop iterates over `applicable.items()` and updates `pos` at the end of
each iteration. The `before_*` variables for the **second** split correctly capture
the post-first-split `pos.*` values (because `pos` is reassigned). However, the
**DB persistence** for the second split calls:

```python
conn.execute(
    update(positions)
    .where(positions.c.id == pos.id)
    .values(
        shares=new_shares,
        entry_close=new_entry_close,
        ...
    )
)
```

This is correct — it uses the newly computed `new_*` values derived from the current
`pos.*` after the first split was applied in-memory. The DB is written twice. The
**audit payload** for the second split also uses the correctly updated `before_*`
and `after_*` values. The **split notification** (line 640-650) however passes
`before_entry_close` and `new_entry_close`. For the second split,
`before_entry_close = pos.entry_close` at the *start of the second iteration*,
which is `new_entry_close` from the *first* iteration — so this is also correct.

The actual bug: the `pos = _OpenPosition(...)` assignment at line 668 inside the
inner `for split_ts, ratio` loop correctly updates `pos` for the next split
iteration. But `updated[idx] = pos` at line 680 is **outside** the inner loop —
it only runs after all splits are processed. If the first `conn.execute` raises an
exception (e.g. DB locked), the inner loop will `continue` past the failed split
without updating `pos` via the reassignment at line 668, but `updated[idx]` will
remain the original un-split snapshot even though subsequent splits (if any) will
compute deltas against the post-exception `pos` state. This is a partial-failure
corruption path, not the normal path.

More concretely: the commit for each split is issued inside the inner loop, but
if a commit fails mid-sequence, the in-memory `pos` has already been updated
(at line 668) while the DB row may not have been. Re-running the scan with the
**same** `last_scan_date` (because the scan was not persisted) will re-apply all
splits from `window_start` again — including ones that already succeeded.
`ON CONFLICT DO NOTHING` is not present on the `update(positions)` path, so
re-application will silently double-adjust price fields.

**Fix:** Wrap the per-split DB write + in-memory update in a single transaction.
If the DB write fails, do not update `pos` and do not emit the audit event or
notification:

```python
try:
    with engine.begin() as conn:  # atomic: commit or rollback together
        conn.execute(
            update(positions).where(...).values(...)
        )
except Exception:
    continue  # skip this split — will be re-attempted next scan

# Only reach here if DB write succeeded
log_event(...)
split_notifications.append(...)
pos = _OpenPosition(...)   # update in-memory only after DB success
```

---

## Warnings

### WR-01: `_run_preflight` queries `scans` before `_persist_scan_placeholder` inserts — last_scan_date reads a stale placeholder

**File:** `src/bensdorp1/commands/_scan_engine.py:353-365`

**Issue:** `_run_preflight` selects the latest `scan_date` from `scans` ordered
descending. On a `--force` re-run, the current day's placeholder was inserted by
a previous run of `run_scan` (step `_persist_scan_placeholder` line 218), so
`row.scan_date` will be today's date, and `last_scan_date` will be today. This
makes `start_of_window = today + 1 day`, which is `> yesterday`, so
`missed_days` will be empty even if the user actually was absent. The `--force`
flag is designed to re-run but *not* to suppress catch-up detection. However, on
a `--force` same-day re-run, the catch-up logic will be silently skipped.

The placeholder is inserted at line 218, **after** `_run_preflight` at line 161,
so on a fresh first run of the day this is not an issue. But if the placeholder
from an earlier call exists (crash-and-retry, `--force`), `_run_preflight` will
see today's date as the last scan and suppress catch-up.

**Fix:** In `_run_preflight`, filter out placeholder rows (where `raw_output IS NULL`)
when computing `last_scan_date`:

```python
row = conn.execute(
    select(scans.c.scan_date)
    .where(scans.c.raw_output.isnot(None))   # exclude placeholders
    .order_by(scans.c.scan_date.desc())
    .limit(1)
).fetchone()
```

---

### WR-02: `row.scan_date.date()` will crash if SQLite returns a naive datetime without `.date()` method

**File:** `src/bensdorp1/commands/_scan_engine.py:359`

**Issue:** `last_scan_date = row.scan_date.date()` assumes `row.scan_date` is always a
`datetime`. SQLite stores `DateTime(timezone=True)` columns as ISO text strings;
SQLAlchemy's pysqlite dialect typically converts these back to `datetime` objects.
However, if the column value was stored without timezone info (e.g. by a legacy
migration or a buggy earlier insert), SQLAlchemy may return a naive `datetime`
or, in edge cases with certain SQLite versions, a raw string. A `str` has no
`.date()` method and will raise `AttributeError`.

**Fix:** Use the defensive pattern already used elsewhere in the codebase:

```python
scan_dt = row.scan_date
if hasattr(scan_dt, "date"):
    last_scan_date = scan_dt.date()
else:
    last_scan_date = date.fromisoformat(str(scan_dt)[:10])
```

---

### WR-03: `_apply_splits` emits Template 5 (catch-up event) even when the split date is NOT within the missed-days window

**File:** `src/bensdorp1/commands/_scan_engine.py:652-665`

**Issue:** `catchup_split_events` is populated whenever `catchup_split_events is not None`,
which is set to `{}` in `_update_position_stops` whenever `missed_days` is non-empty
(line 793-794). The `applicable` Series is filtered to `split_date > window_start AND
split_date <= today` (D-05), but `window_start = max(entry_date, last_scan_date)`.
If a split occurred **before** the missed-days window (e.g. between the entry date and
the last scan date) it is correctly excluded by the window filter. But if a split
occurred **today** (split_date == today), it will be included in the catch-up event
list even though `today` is not in `missed_days`. The Template 5 catch-up block is
intended for events that occurred "during your absence," so showing it for a split
that happened today (a scan day, not an absence day) is misleading.

**Fix:** Add a guard before appending to `catchup_split_events`:

```python
if catchup_split_events is not None and split_date in missed_set:
    ev_list = catchup_split_events.setdefault(pos.symbol, [])
    ev_list.append(render_stock_split(...))
```

Where `missed_set` is the set of actual missed trading days, not just any day in the
D-05 window.

---

### WR-04: `_update_position_stops` modifies `open_positions[idx]` in-place but `_apply_splits` returns a new list — caller passes the same list reference

**File:** `src/bensdorp1/commands/_scan_engine.py:795`

**Issue:** `_apply_splits` returns an updated list (`updated: list[_OpenPosition] =
list(open_positions)`), and the caller reassigns via slice `open_positions[:] = ...`
(line 795). This correctly updates the caller's list in-place. However, `_detect_delisted_positions`
was called at lines 182-184 **before** `_update_position_stops` is called, using the
**original** `open_positions` snapshot. Positions whose splits were applied during the
catch-up walk will have stale `pos.shares` / `pos.trailing_stop` values inside
`delisted_events` processing. Since `_detect_delisted_positions` only reads
`pos.symbol` and `pos.delisted`, this is not a data-corruption risk, but it is
a fragile ordering dependency.

More critically: the `open_positions` list passed to the outer `run_scan` scope is
mutated at line 795 (`open_positions[:] = ...`), but `open_positions` is a local
variable from the `_query_open_positions` call at line 176. The mutations flow correctly
through the rest of `run_scan` because all subsequent steps use the same local
variable. This is fine. The warning is that the mutation-via-slice pattern is
surprising and a future refactor could easily miss the slice assignment, causing a
name rebinding that leaves the outer variable pointing at the stale list.

**Fix:** Return the updated list explicitly and reassign by name, not slice:

```python
open_positions = _apply_splits(engine, open_positions, ...)
```

This is unambiguous and avoids the mutable-default-argument style pitfall.

---

### WR-05: `_persist_scan` deletes `scan_candidates` on every call, not only on `--force`

**File:** `src/bensdorp1/commands/_scan_engine.py:1652-1657`

**Issue:** The `scan_candidates` delete runs unconditionally (lines 1652-1657):

```python
# Delete existing scan_candidates for this scan_id (idempotent on --force)
with engine.connect() as conn:
    conn.execute(
        delete(scan_candidates).where(scan_candidates.c.scan_id == scan_id)
    )
    conn.commit()
```

The comment says "idempotent on --force" but the block runs on both `force=True` and
`force=False`. On a first run this is harmless (no rows exist yet). On a `--force`
re-run it correctly clears and re-inserts. The asymmetry is that `scan_exit_triggers`
is conditionally deleted only when `force=True` (line 1643), but `scan_candidates`
is always deleted. This is not a bug for the current flow (the placeholder always
inserts with `candidate_count=0` before this runs), but it creates an inconsistency
that will confuse future readers into thinking the two tables are treated the same way.
If an exception occurs between the delete and the re-insert, `scan_candidates` will
be empty while `scan_exit_triggers` will still have valid rows — leaving the DB in an
inconsistent partial-state.

**Fix:** Wrap both deletes and the re-insert in a single transaction, or explicitly
gate the `scan_candidates` delete on `force=True` as is done for `scan_exit_triggers`.

---

### WR-06: `_get_close_for_day` uses `.apply(lambda)` on every call — O(n) per day per position

**File:** `src/bensdorp1/commands/_scan_engine.py:750-757`

**Issue:** For each `(position, day)` pair in the catch-up walk, `_get_close_for_day`
applies a Python lambda to every row of the DataFrame to extract `.date()`:

```python
dates = df["trade_date"].apply(
    lambda td: td.date() if hasattr(td, "date") else date(td.year, td.month, td.day)
)
mask = dates == target_date
```

With 221 rows per symbol and up to 10 positions and up to ~5 missed days, this creates
`221 * 10 * 5 = 11,050` Python function calls per scan. This is not a performance
issue per the review scope, but the real correctness risk is: if `trade_date` contains
a `datetime.date` object (not `datetime`), `hasattr(td, "date")` returns `True` because
`date` objects also have a `.date()` method (inherited). However, `date.date()` does
not exist — `datetime.date` is a final type without a `.date()` accessor. The lambda
would raise `AttributeError` at runtime for rows stored as plain `date` values.

**Fix:** Use pandas-native date extraction, which is both faster and type-safe:

```python
if pd.api.types.is_datetime64_any_dtype(df["trade_date"]):
    mask = df["trade_date"].dt.date == target_date
else:
    mask = df["trade_date"].apply(
        lambda td: td.date() if isinstance(td, datetime) else td
    ) == target_date
```

---

## Info

### IN-01: Private function `_to_yfinance` imported across module boundaries

**File:** `src/bensdorp1/commands/_scan_engine.py:46`

**Issue:** `from bensdorp1.data.prices import _to_yfinance` imports a private
(underscore-prefixed) function from another module. The comment acknowledges it as
"DATA-08: sole normalization site," but the import creates a coupling that mypy strict
mode will flag (`no_implicit_reexport` — though it won't fire here because this is
a direct internal import, not a re-export). If `prices.py` is ever refactored and
`_to_yfinance` is renamed or removed, the error surfaces at runtime rather than at
import time in tests.

**Fix:** Expose `to_yfinance` (without leading underscore) via `bensdorp1.data` or
`bensdorp1.data.prices` public API, or move it to a shared `bensdorp1.tickers` utility
module. Since CLAUDE.md says the module is the "sole normalization site," the canonical
form is correct — just remove the privacy underscore from the name if it is intended
for cross-module use.

---

### IN-02: `render_composite` embeds raw event strings as bullet items — no escaping

**File:** `src/bensdorp1/commands/events.py:224`

**Issue:** `render_composite` builds:

```python
bullets = "\n".join(f"      - {e}" for e in events_list)
return f"{symbol}  Multiple events during your absence:\n{bullets}"
```

Each event string `e` is itself a multi-line string (e.g. Template 1 is three lines
with `\n` in it). When embedded into the composite bullet, the continuation lines of
each sub-event will appear at column 0, not indented under the bullet. The spec §7.6
requires "continuation lines indented 6 spaces," but the nested event strings already
contain their own 6-space continuation indents (`"      Position remained open…"`).
This means the composite render will have correct first-line indentation but the
sub-event continuation lines will collide visually with the outer bullet structure.

**Fix:** Strip or re-indent the sub-event continuation lines when embedding in a
composite:

```python
def _indent_event(ev: str, indent: str = "        ") -> str:
    """Re-indent all lines of an event string for composite embedding."""
    lines = ev.splitlines()
    return "\n".join(f"{indent}{line.lstrip()}" for line in lines)

bullets = "\n".join(f"      - {_indent_event(e)}" for e in events_list)
```

---

### IN-03: `conftest.py` `db_engine` fixture does not run `run_migrations` — `delisted` column missing from test DB

**File:** `tests/conftest.py:43`

**Issue:** The `db_engine` fixture calls `metadata.create_all(engine, checkfirst=True)`
which creates all tables from the DDL in `schema.py`. The `delisted` column is defined
in the schema (line 60 of `schema.py`), so it will be present in test DBs.
`run_migrations` (which adds `delisted` via `ALTER TABLE` for existing databases) is
NOT called. For test databases this is fine because `create_all` picks up the full
current schema. However, if a test inserts into `positions` without specifying
`delisted`, SQLite will use the `server_default=text("0")` — but only if the column
default is recognized by the pysqlite driver. The `server_default` is a DDL-level
default, not a Python-level default, so it will be applied correctly by SQLite.

The actual gap: `test_scan.py:test_catchup_stop_updates` and
`test_scan.py:test_stop_freeze_after_trigger` insert positions without the `delisted`
column (lines 210-222 and 307-315 of `test_scan.py`). With `server_default`, SQLite
will default to `0`, which is correct. But the `_OpenPosition` namedtuple constructed
at lines 260-270 and 347-357 explicitly sets `delisted=0`. If anyone changes
`server_default` to something else, these tests will silently pass with the wrong
value. This is a minor fragility.

**Fix:** Either always specify `delisted=0` in test inserts (consistency), or assert
`delisted == 0` after the query to make the assumption explicit.

---

_Reviewed: 2026-05-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
