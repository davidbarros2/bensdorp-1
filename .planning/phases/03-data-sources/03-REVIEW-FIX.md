---
phase: 03-data-sources
fixed_at: 2026-05-23T00:00:00Z
review_path: .planning/phases/03-data-sources/03-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-05-23T00:00:00Z
**Source review:** .planning/phases/03-data-sources/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: `_fetch_wikipedia` crashes with AttributeError when `<tbody>` is absent

**Files modified:** `src/bensdorp1/data/constituents.py`
**Commit:** 37dc63e
**Applied fix:** Replaced the bare `table.find("tbody").find_all("tr")` call (which crashes with `AttributeError` when lxml omits the `<tbody>` element) with an explicit `None`-check that raises `ValueError("Wikipedia S&P 500 wikitable has no tbody")`. This keeps the error type consistent with what `refresh_constituents` already catches via `except (httpx.HTTPError, ValueError)`, satisfying D-03.

---

### CR-02: Third backoff delay (4s) is dead code; DATA-09 retry spec not fully implemented

**Files modified:** `src/bensdorp1/data/prices.py`
**Commit:** 9a0324c
**Applied fix:** Trimmed `BACKOFF_DELAYS` from `[1.0, 2.0, 4.0]` to `[1.0, 2.0]` (option A from review), matching the actual loop behavior (sleeps between attempts, not after the last). Added a clarifying comment above the constant. Updated the `DATA-09` module docstring line from "delays 1s, 2s, 4s" to "sleeps 1s, 2s between them".

---

### WR-01: `update_price_data` silently discards a caller-supplied `start` when `end` is omitted

**Files modified:** `src/bensdorp1/data/prices.py`
**Commit:** 51a2b2d
**Applied fix:** Changed the guard from `if start is None or end is None` to `if start is None and end is None` for the default-range path, plus an `elif start is None or end is None: raise ValueError(...)` branch for the mixed case. Callers that supply only one boundary now get an immediate, clear error instead of silently wrong date ranges.

---

### WR-02: `_download_bulk` raises `KeyError` if yfinance omits the "Volume" column

**Files modified:** `src/bensdorp1/data/prices.py`
**Commits:** 997a5b7, 3aa1ec0
**Applied fix:** `_download_bulk` now builds `available = [c for c in ["Close", "Volume"] if c in stacked.columns]`, returns empty DataFrame if "Close" is absent, and slices only the available columns. `_stacked_to_rows` guards the "Volume" key access with `"Volume" in row.index` so rows lacking the column persist with `volume=None` rather than raising `KeyError`.

A follow-up commit (3aa1ec0) also guarded `yf.download()` None returns (stubs allow `DataFrame | None`) in both `_download_bulk` and `_download_with_retry`, acknowledged the `.stack()` annotation mismatch with `# type: ignore[assignment]` (bulk downloads always produce DataFrame at runtime), suppressed the Pyright false positive on `int(vol_raw)`, and added `pyrightconfig.json` to configure Pyright with the project's `.venv` so IDE import resolution works correctly.

---

### WR-03: DB errors in `_persist_constituents` and `_persist_price_rows` bypass D-03

**Files modified:** `src/bensdorp1/data/constituents.py`, `src/bensdorp1/data/prices.py`
**Commit:** a15f21f
**Applied fix:** Wrapped `_persist_constituents(engine, wiki_data)` in `refresh_constituents` and `_persist_price_rows(engine, rows)` in `update_price_data` with `try/except Exception` blocks that catch any `OperationalError` (or other DB exception) and emit `DATA_FETCH_FAILED` via `log_event`. The `return` in the constituents path prevents the `CONSTITUENTS_UPDATED` event from firing after a failed persist.

---

_Fixed: 2026-05-23T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
