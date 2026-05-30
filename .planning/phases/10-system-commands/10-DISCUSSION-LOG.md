# Phase 10: System Commands - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 10-system-commands
**Areas discussed:** status health markers, restore double-confirmation, refresh change summary

---

## status health markers

### Data section thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Constituents: >7d = STALE, >14d = WARNING; Last scan: >1 trading day = STALE | Mirrors existing system rules (7-day cache TTL, daily scan expectation) | ✓ |
| No health labels — just raw dates | Simpler, user interprets freshness themselves | |
| Custom thresholds | User-defined day counts | |

**User's choice:** Recommended option — thresholds grounded in existing system rules.

### Backup and database health labels

| Option | Description | Selected |
|--------|-------------|----------|
| Backup: >3 days since last backup = STALE; DB: integrity check OK/FAILED | Backup staleness meaningful; DB integrity is binary | ✓ |
| Only DB integrity gets a label; backup shows raw date only | Backup date informational only | |
| No health labels on any section | All raw values | |

**User's choice:** Recommended option.

### Health label rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Severity colors: OK = green, STALE = yellow, WARNING = yellow, FAILED = red | Reuses existing severity color palette from ui/messages.py | ✓ |
| Bracketed plain text: [OK], [STALE], [WARNING] | Works in non-color terminals | |
| You decide | Claude picks rendering | |

**User's choice:** Recommended option — consistent with existing severity color system.

---

## restore double-confirmation

### First confirmation content

| Option | Description | Selected |
|--------|-------------|----------|
| File info: path, size, modified date, then ask "Replace active database with this file?" | User verifies they picked the right backup | ✓ |
| Just the path, then ask immediately | Leaner | |
| Schema validation result + file info, then ask | Show validation result before asking | |

**User's choice:** Recommended option — file info first, then confirm.

### Second confirmation wording

| Option | Description | Selected |
|--------|-------------|----------|
| "A pre-restore backup will be created first. This will overwrite your current database. Are you sure?" | Names the safety net and what gets overwritten | ✓ |
| "This cannot be undone." | Stronger but technically misleading (backup IS created) | |
| You decide | Claude picks wording | |

**User's choice:** Recommended option — accurate framing with the safety net named.

### Schema validation

| Option | Description | Selected |
|--------|-------------|----------|
| PRAGMA integrity_check = ok + all 7 expected table names present | Pragmatic: catches corruption + verifies it's a bensdorp1 DB | ✓ |
| PRAGMA integrity_check only | Catches corruption but not wrong-DB | |
| Full column-by-column schema comparison | Thorough but brittle across schema versions | |

**User's choice:** Recommended option.

---

## refresh change summary

### Change output format

| Option | Description | Selected |
|--------|-------------|----------|
| Summary line + table of changed tickers only | "Added: N, Removed: N" then table of additions/removals | ✓ |
| Summary line only, no table | Compact; user can use audit for details | |
| Full table of all 500 tickers with markers | Complete but verbose | |

**User's choice:** Recommended option — actionable when changes exist, quiet otherwise.

### No-change output

| Option | Description | Selected |
|--------|-------------|----------|
| "Constituents up to date. N tickers, no changes." | Confirms the refresh ran, shows current count | ✓ |
| Silent success, just show "Done." | Minimal | |
| You decide | Claude picks | |

**User's choice:** Recommended option.

---

## Claude's Discretion

- `status` layout: `render_kv_block` per section with `---` separators (consistent with Phase 9 config/detail pattern)
- `status` health label placement: inline after value, space-separated
- `status` operational section data sources: `scan_exit_triggers` JOIN open positions for pending exits count
- `restore` pre-restore backup: created after both confirmations, before file copy; on failure name the backup path in the error
- `restore` audit event: logged to the NEW (restored) DB after swap, not the pre-restore DB
- `restore` file copy: `shutil.copy2` (same pattern as backup module, reversed)
- `restore` validation order: runs before any confirmation prompt
- `refresh` progress: `SpinnerContext` (expected 1-6s for two HTTP requests)
- Single file per command (Phase 8 D-25 pattern carried forward)
- `restore.py` opens backup file as separate read-only engine for validation, closes before file copy

## Deferred Ideas

None — discussion stayed within phase scope.
