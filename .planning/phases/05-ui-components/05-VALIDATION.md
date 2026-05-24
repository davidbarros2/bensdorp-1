---
phase: 5
slug: ui-components
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-24
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_ui/ -x -q` |
| **Full suite command** | `uv run pytest --cov=src/bensdorp1/ui --cov=src/bensdorp1/config --cov-report=term-missing` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_ui/ -x -q`
- **After every plan wave:** Run `uv run pytest --cov=src/bensdorp1/ui --cov=src/bensdorp1/config --cov-report=term-missing`
- **Before `/gsd-verify-work`:** Full suite green + `uv run mypy src/bensdorp1/ui/ src/bensdorp1/config.py` + `uv run ruff check src/bensdorp1/ui/ src/bensdorp1/config.py`
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| config.py constants | A | 1 | UI-05 | — | ZoneInfo raises on invalid key | unit | `uv run pytest tests/test_ui/test_config.py -x -q` | ❌ W0 | ⬜ pending |
| format_price | A | 1 | UI-10 | — | N/A | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_price -x` | ❌ W0 | ⬜ pending |
| format_pct | A | 1 | UI-10 | — | N/A | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_pct -x` | ❌ W0 | ⬜ pending |
| format_pnl | A | 1 | UI-10 | — | N/A | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_pnl -x` | ❌ W0 | ⬜ pending |
| format_volume | A | 1 | UI-10 | — | N/A | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_volume -x` | ❌ W0 | ⬜ pending |
| format_days | A | 1 | UI-10 | — | N/A | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_days -x` | ❌ W0 | ⬜ pending |
| format_timezone_pair | A | 1 | UI-05 | — | N/A | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_timezone_pair -x` | ❌ W0 | ⬜ pending |
| format_relative_duration | A | 1 | UI-05 | — | N/A | unit | `uv run pytest tests/test_ui/test_styles.py::test_format_relative_duration -x` | ❌ W0 | ⬜ pending |
| Style constants palette | A | 1 | UI-02, UI-06 | — | N/A | unit | `uv run pytest tests/test_ui/test_styles.py::test_style_constants -x` | ❌ W0 | ⬜ pending |
| dots spinner frames match spec | A | 1 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_dots_spinner_frames_match_spec -x` | ❌ W0 | ⬜ pending |
| print_message Severity.ERROR | B | 2 | UI-02, UI-09 | — | data= renders plain Text (no markup injection) | unit | `uv run pytest tests/test_ui/test_messages.py::test_print_error -x` | ❌ W0 | ⬜ pending |
| print_message Severity.WARNING | B | 2 | UI-02, UI-09 | — | data= renders plain Text | unit | `uv run pytest tests/test_ui/test_messages.py::test_print_warning -x` | ❌ W0 | ⬜ pending |
| print_message Severity.INFO | B | 2 | UI-02, UI-09 | — | data= renders plain Text | unit | `uv run pytest tests/test_ui/test_messages.py::test_print_info -x` | ❌ W0 | ⬜ pending |
| print_message Severity.SUCCESS | B | 2 | UI-02, UI-09 | — | data= renders plain Text | unit | `uv run pytest tests/test_ui/test_messages.py::test_print_success -x` | ❌ W0 | ⬜ pending |
| print_message ANSI color (force_terminal) | B | 2 | UI-02 | — | N/A | unit | `uv run pytest tests/test_ui/test_messages.py::test_print_info_ansi_color -x` | ❌ W0 | ⬜ pending |
| print_message NO_COLOR fallback | B | 2 | UI-02 | — | N/A | unit | `uv run pytest tests/test_ui/test_messages.py::test_print_info_no_color -x` | ❌ W0 | ⬜ pending |
| print_message kv alignment (rule 6.4) | B | 2 | UI-09 | — | N/A | unit | `uv run pytest tests/test_ui/test_messages.py::test_print_message_kv_alignment -x` | ❌ W0 | ⬜ pending |
| print_message no bold in output | B | 2 | UI-06 | — | N/A | unit | `uv run pytest tests/test_ui/test_messages.py::test_no_bold_in_output -x` | ❌ W0 | ⬜ pending |
| print_empty_state content | B | 2 | UI-08 | — | N/A | unit | `uv run pytest tests/test_ui/test_empty_states.py -x` | ❌ W0 | ⬜ pending |
| render_table no borders | C | 3 | UI-03 | — | N/A | unit | `uv run pytest tests/test_ui/test_tables.py::test_render_table_no_borders -x` | ❌ W0 | ⬜ pending |
| render_table number right-align | C | 3 | UI-03 | — | N/A | unit | `uv run pytest tests/test_ui/test_tables.py::test_render_table_number_alignment -x` | ❌ W0 | ⬜ pending |
| render_table sentence case header | C | 3 | UI-03, UI-06 | — | N/A | unit | `uv run pytest tests/test_ui/test_tables.py::test_render_table_header -x` | ❌ W0 | ⬜ pending |
| render_table no bold headers | C | 3 | UI-06 | — | N/A | unit | `uv run pytest tests/test_ui/test_tables.py::test_render_table_no_bold -x` | ❌ W0 | ⬜ pending |
| confirm_prompt y returns True | C | 3 | UI-07 | — | N/A | unit | `uv run pytest tests/test_ui/test_prompts.py::test_confirm_y -x` | ❌ W0 | ⬜ pending |
| confirm_prompt n returns False | C | 3 | UI-07 | — | N/A | unit | `uv run pytest tests/test_ui/test_prompts.py::test_confirm_n -x` | ❌ W0 | ⬜ pending |
| confirm_prompt re-prompts on invalid | C | 3 | UI-07 | — | N/A | unit | `uv run pytest tests/test_ui/test_prompts.py::test_confirm_reprompt -x` | ❌ W0 | ⬜ pending |
| confirm_prompt KeyboardInterrupt | C | 3 | UI-07 | — | N/A | unit | `uv run pytest tests/test_ui/test_prompts.py::test_confirm_keyboard_interrupt -x` | ❌ W0 | ⬜ pending |
| feedback.spinner() silent <1s | D | 4 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_spinner_silent_fast -x` | ❌ W0 | ⬜ pending |
| feedback.spinner() braille ≥1s | D | 4 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_spinner_shows_braille -x` | ❌ W0 | ⬜ pending |
| feedback.track() silent <1s | D | 4 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_track_silent_fast -x` | ❌ W0 | ⬜ pending |
| feedback.track() spinner 1–6s | D | 4 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_track_spinner_tier -x` | ❌ W0 | ⬜ pending |
| feedback.track() progress bar 6–30s | D | 4 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_track_progress_tier -x` | ❌ W0 | ⬜ pending |
| feedback.track() progress+ETA >30s | D | 4 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_track_eta_tier -x` | ❌ W0 | ⬜ pending |
| BlockBarColumn uses █/░ | D | 4 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_block_bar_chars -x` | ❌ W0 | ⬜ pending |
| feedback.multi_step() done. line | D | 4 | UI-04 | — | N/A | unit | `uv run pytest tests/test_ui/test_progress.py::test_multi_step_done_line -x` | ❌ W0 | ⬜ pending |
| ui/__init__.py re-exports | E | 5 | UI-01 | — | N/A | unit | `uv run pytest --co -q 2>&1 \| grep test_ui` | ❌ W0 | ⬜ pending |
| ui/ coverage gate | E | 5 | UI-01 | — | N/A | coverage | `uv run pytest tests/test_ui/ --cov=src/bensdorp1/ui --cov=src/bensdorp1/config --cov-fail-under=90` | ❌ W0 | ⬜ pending |
| mypy strict clean | E | 5 | UI-01..10 | — | N/A | type | `uv run mypy src/bensdorp1/ui/ src/bensdorp1/config.py` | ❌ W0 | ⬜ pending |
| ruff clean | E | 5 | UI-01..10 | — | N/A | lint | `uv run ruff check src/bensdorp1/ui/ src/bensdorp1/config.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ui/__init__.py` — empty package marker
- [ ] `tests/test_ui/test_config.py` — config constants; ZoneInfo validity
- [ ] `tests/test_ui/test_styles.py` — formatter pure functions; Style constants
- [ ] `tests/test_ui/test_messages.py` — print_message; severity mapping; kv alignment
- [ ] `tests/test_ui/test_tables.py` — render_table; column alignment
- [ ] `tests/test_ui/test_prompts.py` — confirm_prompt; monkeypatched input()
- [ ] `tests/test_ui/test_progress.py` — all 4 tiers; BlockBarColumn; spinner frames
- [ ] `tests/test_ui/test_empty_states.py` — empty state message content
- [ ] `tests/conftest.py` update — add `record_console` fixture returning `Console(record=True, width=80)`
- [ ] `src/bensdorp1/config.py` — PROJECT_NAME, MARKET_TZ, USER_TZ, DATA_DIR
- [ ] `src/bensdorp1/ui/__init__.py` — package marker (final re-exports in Plan E)
- [ ] `src/bensdorp1/ui/styles.py` — _console singleton + Style constants + formatter functions

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `confirm_prompt()` displays exact `[y/n]` on terminal | UI-07 | `Console(record=True)` captures the `?` part but interactive prompt text goes to stdin/stdout; visual layout hard to unit-test | Run `uv run python -c "from bensdorp1.ui.prompts import confirm_prompt; confirm_prompt('Delete position?')"` and verify output format matches rule 6.15 |
| Braille spinner renders on terminal | UI-04 | Live animation cannot be captured by `Console(record=True)` | Run a quick script with `feedback.spinner("Fetching data...")` that sleeps 2s and verify `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` frames appear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
