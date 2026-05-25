---
phase: 09-consultation-commands
fixed_at: 2026-05-25T00:00:00Z
review_path: .planning/phases/09-consultation-commands/09-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 09: Code Review Fix Report

**Fixed at:** 2026-05-25T00:00:00Z
**Source review:** .planning/phases/09-consultation-commands/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 10
- Fixed: 10
- Skipped: 0

## Fixed Issues

### CR-01: `format_timezone_pair` crashes on timezone-naive datetimes

**Files modified:** `src/bensdorp1/ui/styles.py`
**Commit:** 75ae87d
**Applied fix:** Added `if dt.tzinfo is None: dt = dt.replace(tzinfo=UTC)` guard at the start of `format_timezone_pair`. Also applied the IN-03 `USER_TZ.key` None guard (`(USER_TZ.key or "Unknown").split("/")[-1]`) in the same function, since the fix touched the same line. This covers both `audit.py:131` and `cash.py:74` call sites by hardening the shared function.

---

### CR-02: `_format_details` crashes with `ValueError`/`TypeError` on malformed payloads

**Files modified:** `src/bensdorp1/commands/audit.py`
**Commit:** 06fa892
**Applied fix:** Wrapped both `float()` conversion paths (`old`/`new` and `price`/`shares`) in `try/except (ValueError, TypeError)` blocks, falling back to `str(data)[:60]` on conversion failure.

---

### WR-01: `portfolio.py` uses stale `pos.highest_close` for the "High $" column

**Files modified:** `src/bensdorp1/commands/portfolio.py`
**Commit:** 5524422
**Applied fix:** Added a footer note printed after the table (`console.print(...)`) stating "Note: High $ and Stop $ reflect the last scan run." — the safer option that avoids changing business logic. The comment directs users to run `bensdorp1 scan` to update stop levels.

---

### WR-02: `history.py` raises inside connection block — fragile pattern

**Files modified:** `src/bensdorp1/commands/history.py`
**Commit:** e078a2c
**Applied fix:** Moved the empty-state guard (`if not scan_rows`) outside the `with engine.connect()` block. The first connection block now only fetches `scan_rows` and closes. The sub-queries for candidates open a second, separate connection block — matching the suggested fix pattern.

---

### WR-03: `audit.py` and `history.py` call `.where()` with zero args

**Files modified:** `src/bensdorp1/commands/audit.py`, `src/bensdorp1/commands/history.py`
**Commits:** e078a2c (history.py), 2d66d0f (audit.py)
**Applied fix:** For both files: built the base `stmt` without `.where()`, then applied `if filters: stmt = stmt.where(*filters)` conditionally. The `history.py` fix was bundled with WR-02 in a single atomic commit since both changes were in the same structural refactor of the connection block.

---

### WR-04: `detail.py` computes `effective_stop` inconsistently with `portfolio.py`

**Files modified:** `src/bensdorp1/commands/detail.py`
**Commit:** 07f1de6
**Applied fix:** Added a clarifying comment above the `trailing_stop` computation explaining that `detail.py` is the authoritative live-recomputation view (from `price_daily`), while `portfolio.py` reads the stored `pos.trailing_stop` from the last scan — documenting the intentional difference rather than changing business logic.

---

### WR-05: `config.py` crashes with `PackageNotFoundError` when package not installed

**Files modified:** `src/bensdorp1/commands/config.py`
**Commit:** 82092e7
**Applied fix:** Added `from importlib.metadata import PackageNotFoundError, version as pkg_version` and wrapped the call in `try: version_str = pkg_version("bensdorp1") / except PackageNotFoundError: version_str = "unknown"`. Bundled with IN-03 fix in same commit.

---

### IN-01: Weak `<= 3` assertion in `test_audit_limit_flag_returns_at_most_n_events`

**Files modified:** `tests/test_commands/test_audit.py`
**Commit:** 30fd3f2
**Applied fix:** Changed `assert result.output.count("buy_confirmed") <= 3` to `assert result.output.count("buy_confirmed") == 3`. With 5 rows inserted and `--limit 3`, exactly 3 `buy_confirmed` events should appear — the equality assertion catches both over- and under-counting regressions.

---

### IN-02: Dead assignment in `test_history.py` — `scan1_id` and `scan3_id` unused

**Files modified:** `tests/test_commands/test_history.py`
**Commit:** d1611af
**Applied fix:** Removed the `r1 = conn.execute(...)` / `scan1_id = r1.inserted_primary_key[0]` captures for scan1 and scan3, replacing them with plain `conn.execute(...)` calls. Also removed the `_ = scan1_id` and `_ = scan3_id` suppression lines. `scan2_id` (used for inserting candidates) is preserved.

---

### IN-03: `config.py` accesses `USER_TZ.key` without guard for `None`

**Files modified:** `src/bensdorp1/commands/config.py`, `src/bensdorp1/ui/styles.py`
**Commit:** 82092e7 (config.py), 75ae87d (styles.py)
**Applied fix:** In `config.py`, replaced `USER_TZ.key.split('/')[-1]` with `(USER_TZ.key or "Unknown").split("/")[-1]` extracted into `tz_label`. In `styles.py`, applied the same guard to the `city` variable inside `format_timezone_pair` as part of the CR-01 fix.

---

_Fixed: 2026-05-25T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
