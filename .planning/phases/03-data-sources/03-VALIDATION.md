---
phase: 3
slug: data-sources
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-23
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_data_*.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_data_*.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green + `uv run python -m mypy src/` + `uv run ruff check src/`
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| calendar.py | 01 | 1 | DATA-07 | — | N/A | unit | `pytest tests/test_data_calendar.py -x` | ❌ W0 | ⬜ pending |
| NYSE excludes holidays | 01 | 1 | DATA-07 | — | N/A | unit | `pytest tests/test_data_calendar.py::test_excludes_holidays -x` | ❌ W0 | ⬜ pending |
| n_trading_days_ago | 01 | 1 | DATA-07 | — | N/A | unit | `pytest tests/test_data_calendar.py::test_n_trading_days_ago -x` | ❌ W0 | ⬜ pending |
| constituents.py | 02 | 2 | DATA-01, DATA-02, DATA-05 | T-3-01 | Ticker symbols validated before DB insert (regex `^[A-Z.\-\^]{1,10}$`) | unit (mocked HTTP) | `pytest tests/test_data_constituents.py -x` | ❌ W0 | ⬜ pending |
| Wikipedia fetch | 02 | 2 | DATA-01 | T-3-01 | `get_text(strip=True)` strips HTML; symbols validated by regex | unit | `pytest tests/test_data_constituents.py::test_fetch_wikipedia -x` | ❌ W0 | ⬜ pending |
| Slickcharts fetch | 02 | 2 | DATA-01 | T-3-01 | User-Agent set; 403 raises immediately; `data_fetch_failed` audit | unit | `pytest tests/test_data_constituents.py::test_fetch_slickcharts -x` | ❌ W0 | ⬜ pending |
| Discrepancy 0-3 silent | 02 | 2 | DATA-02 | — | N/A | unit | `pytest tests/test_data_constituents.py::test_discrepancy_silent -x` | ❌ W0 | ⬜ pending |
| Discrepancy 4-10 warn | 02 | 2 | DATA-02 | — | N/A | unit | `pytest tests/test_data_constituents.py::test_discrepancy_warn -x` | ❌ W0 | ⬜ pending |
| Discrepancy 11+ abort | 02 | 2 | DATA-02 | — | N/A | unit | `pytest tests/test_data_constituents.py::test_discrepancy_abort -x` | ❌ W0 | ⬜ pending |
| Cache stale refresh | 02 | 2 | DATA-05 | — | N/A | unit (db_engine) | `pytest tests/test_data_constituents.py::test_cache_stale_refresh -x` | ❌ W0 | ⬜ pending |
| Cache fresh skip | 02 | 2 | DATA-05 | — | N/A | unit (db_engine) | `pytest tests/test_data_constituents.py::test_cache_fresh_skip -x` | ❌ W0 | ⬜ pending |
| prices.py bulk download | 03 | 3 | DATA-03, DATA-04 | T-3-02 | Explicit casts `float(Close)` / `int(Volume)` before DB insert | unit (mocked yf) | `pytest tests/test_data_prices.py -x` | ❌ W0 | ⬜ pending |
| auto_adjust=True | 03 | 3 | DATA-03 | — | N/A | unit | `pytest tests/test_data_prices.py::test_download_auto_adjust -x` | ❌ W0 | ⬜ pending |
| 220 days fetched | 03 | 3 | DATA-04 | — | N/A | unit | `pytest tests/test_data_prices.py::test_220_days_fetched -x` | ❌ W0 | ⬜ pending |
| Ticker normalization period | 03 | 3 | DATA-08 | T-3-03 | Period form stored in DB (BRK.B, not BRK-B) | unit (db_engine) | `pytest tests/test_data_prices.py::test_ticker_normalization_period -x` | ❌ W0 | ⬜ pending |
| Ticker normalization yfinance | 03 | 3 | DATA-08 | T-3-03 | Hyphen form used only at yfinance call site | unit (mock) | `pytest tests/test_data_prices.py::test_ticker_normalization_yfinance -x` | ❌ W0 | ⬜ pending |
| Retry backoff | 03 | 3 | DATA-09 | — | N/A | unit (mock + sleep mock) | `pytest tests/test_data_prices.py::test_retry_backoff -x` | ❌ W0 | ⬜ pending |
| Coverage check pass | 03 | 3 | DATA-10 | — | N/A | unit (db_engine) | `pytest tests/test_data_prices.py::test_coverage_check_pass -x` | ❌ W0 | ⬜ pending |
| Coverage check fail | 03 | 3 | DATA-10 | — | N/A | unit (db_engine) | `pytest tests/test_data_prices.py::test_coverage_check_fail -x` | ❌ W0 | ⬜ pending |
| data/__init__.py re-exports | 04 | 4 | DATA-01..10 | — | N/A | unit | `pytest tests/test_data_init.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_data_calendar.py` — stubs for DATA-07 (NYSE calendar wrappers)
- [ ] `tests/test_data_constituents.py` — stubs for DATA-01, DATA-02, DATA-05
- [ ] `tests/test_data_prices.py` — stubs for DATA-03, DATA-04, DATA-08, DATA-09, DATA-10
- [ ] `tests/test_data_init.py` — stubs for public API surface (optional but recommended)
- [ ] `pyproject.toml`: add `lxml-stubs>=0.5.1` to `[dependency-groups]` dev group
- [ ] `pyproject.toml`: add mypy overrides for `yfinance` and `pandas_market_calendars`

*Existing `tests/conftest.py` with `db_engine` fixture is reusable — no new conftest needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Slickcharts live HTML structure | DATA-01 | Requires live HTTP GET; Cloudflare may block; table class/column order not verifiable offline | During implementation: `python -c "import httpx; from bs4 import BeautifulSoup; r=httpx.get('https://slickcharts.com/sp500', headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code)"` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
