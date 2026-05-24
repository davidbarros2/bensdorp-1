# Phase 6: First-Run Init Command - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 06-first-run-init-command
**Areas discussed:** Guard condition and recovery, Cash validation rules, Abort mid-flow behavior, Unit test depth

---

## Guard Condition and Recovery

### Q1: What triggers the guard?

| Option | Description | Selected |
|--------|-------------|----------|
| DB file exists | `Path(DATA_DIR / "data" / "bensdorp1.db").exists()` — fast, conservative, spec-correct | ✓ |
| DB file + valid schema | File exists AND core tables present — catches empty/corrupt files, more code, false confidence on half-migrated DB | |

**User's choice:** DB file exists (recommended)

---

### Q2: What does the guard error message say?

| Option | Description | Selected |
|--------|-------------|----------|
| Mention manual deletion | Error mentions: delete file + re-run init (for partial/failed inits) | |
| Mention restore command | Error mentions: `bensdorp1 restore PATH` (for existing DB) | |
| Both paths | Error mentions both recovery paths | ✓ |

**User's choice:** Both paths (recommended)

---

## Cash Validation Rules

### Q3: Minimum valid cash amount?

| Option | Description | Selected |
|--------|-------------|----------|
| > 0 | Any positive float — zero/negative breaks position sizing | ✓ |
| >= 1000 | Practical minimum: <$1000 yields 0 shares on most stocks | |
| No minimum | Defer to position sizing logic | |

**User's choice:** > 0 (recommended)

---

### Q4: KeyboardInterrupt handling for number_prompt?

| Option | Description | Selected |
|--------|-------------|----------|
| Command wraps in try/except KeyboardInterrupt | Init command catches Ctrl+C, prints abort message, exits. number_prompt signature unchanged. | ✓ |
| Fix number_prompt | Update return type to float \| None — more consistent but changes signature for all callers | |
| Let Ctrl+C bubble | Raw KeyboardInterrupt = Python stack trace — bad UX | |

**User's choice:** Command wraps the call (recommended)

---

### Q5: On invalid cash — re-prompt or abort?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-prompt with error message | Print error, stay in flow — user doesn't have to re-run the whole command | ✓ |
| Abort with error message | Exit — user re-runs init (no DB written yet, so safe) | |

**User's choice:** Re-prompt (recommended)

---

## Abort Mid-Flow Behavior

### Q6: Ctrl+C during price download (DB already created)?

| Option | Description | Selected |
|--------|-------------|----------|
| No cleanup — partial DB stays | Print abort message, exit. Guard on re-run explains recovery. Simple, no risky deletion logic. | ✓ |
| Delete DB file on abort | Attempt cleanup: delete DB + backups. File deletion on signal can fail. | |

**User's choice:** No cleanup (recommended)

---

### Q7: Extra confirmation before execution begins?

| Option | Description | Selected |
|--------|-------------|----------|
| No extra prompt — spec already has one | "Continue? [y/n]" at step 1 is the only escape hatch. Matches spec §7.1 exactly. | ✓ |
| Add final confirm before execution | After cash, add "Ready to begin? [y/n]". Spec doesn't show this step. | |

**User's choice:** No extra prompt (recommended)

---

## Unit Test Depth

### Q8: What tests should Phase 6 ship?

| Option | Description | Selected |
|--------|-------------|----------|
| Moderate: CLI tests with mocked data layer | CliRunner + mock get_constituents/update_price_data/run_migrations/log_event | ✓ |
| Minimal: guard + cash validation only | No CLI runner tests; fast but leaves wiring untested until Phase 13 | |
| Defer all to Phase 13 | No new tests in Phase 6 | |

**User's choice:** Moderate (recommended)

---

### Q9: Which specific scenarios?

| Scenario | Selected |
|----------|----------|
| Guard fires when DB exists | ✓ |
| Full happy path (mocked data layer) | ✓ |
| Cash validation: zero/negative re-prompts | ✓ |
| Ctrl+C during cash entry aborts cleanly | ✓ |

**User's choice:** "I don't understand, this is a technical question so I let you decide" → all 4 scenarios (Claude discretion)

---

## Claude's Discretion

- Test directory structure (`tests/test_commands/` — `__init__.py`, conftest placement) — follow existing pattern
- Whether to extract `_run_init()` helper for testability or keep command function flat
- Exact wording of guard error message (beyond the two required recovery paths)
- All 4 test scenarios (user deferred to Claude)

## Deferred Ideas

None — discussion stayed within phase scope.
