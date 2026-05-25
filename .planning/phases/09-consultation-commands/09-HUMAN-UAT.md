---
status: partial
phase: 09-consultation-commands
source: [09-VERIFICATION.md]
started: 2026-05-25T00:00:00Z
updated: 2026-05-25T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Raw output verbatim rendering
expected: `bensdorp1 last` with a live scan record prints raw scan text with no Rich markup artifacts (no `[bold]`, no color codes)
result: [pending]

### 2. History table alignment
expected: `bensdorp1 history` shows 5-column table; Bear regime scans show `—` in the Top candidates column
result: [pending]

### 3. Portfolio 10-column layout
expected: `bensdorp1 portfolio` shows D-06 headers with right-aligned numbers; positions with no price data show `N/A` in price-derived columns
result: [pending]

### 4. Detail stop-history math
expected: `bensdorp1 detail SYMBOL` Highest close column is monotonically non-decreasing and Trailing stop = Highest close × 0.75 for each row
result: [pending]

### 5. Cash update side-effects
expected: `bensdorp1 cash AMOUNT` (confirmed with `y`) creates a backup file and inserts an audit_log row; `bensdorp1 audit --type cash_updated` shows the new event
result: [pending]

### 6. Audit --type StrEnum rejection
expected: `bensdorp1 audit --type invalid_value` exits non-zero and lists the 17 valid event types in the error output (Typer built-in validation)
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
