---
phase: 04
slug: strategy-logic
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-23
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Phase 7 → strategy/ | Phase 7 passes pre-validated DataFrames; strategy/ receives only typed Python objects (no user-controlled data) | Public market price/volume floats; no PII, no secrets |
| Phase 7/8 → positions.py | Scalar float/int inputs from DB rows; no user input reaches these functions | Float scalars (close prices, cash amounts); derived from public market data |
| Test runner → strategy/ | pytest invokes pure functions with in-memory test data; no external I/O | In-memory DataFrames and floats |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-01 | Tampering | screening.py inputs | accept | No user input reaches strategy/. DataFrames constructed by Phase 7 from DB rows populated by yfinance. Pure math layer with no I/O. | closed |
| T-04-02 | Denial of Service | regime_filter large Series | accept | len() guard raises ValueError for < 200 rows; iloc[-200:].mean() is O(200) — no unbounded computation. | closed |
| T-04-03 | Information Disclosure | Candidate TypedDict | accept | No secrets in Candidate fields (symbol, roc_200, prev_close, position_size); all sourced from public market data. | closed |
| T-04-04 | Tampering | compute_position_size inputs | accept | Inputs are float scalars from DB (entry_close, available_cash). No user-controlled data path. Phase 7 validates DB values before calling. | closed |
| T-04-05 | Denial of Service | compute_position_size near-zero price | accept | prev_close comes from price_daily.close (yfinance), which is always positive. Hypothesis tests with min_value=0.01 cover low-value boundary. Division-by-zero requires close == 0.0, which yfinance does not produce. | closed |
| T-04-06 | Information Disclosure | Stop levels / scalar returns | accept | No secrets. Stop levels derived from publicly available price data only. | closed |
| T-04-07 | Tampering | Coverage gate bypass | accept | --cov-fail-under enforced by pytest-cov exit code; gate cannot be silently bypassed. Non-zero exit fails pipeline. | closed |
| T-04-08 | Repudiation | Coverage numbers not recorded | mitigate | Coverage percentages recorded in 04-03-SUMMARY.md (screening.py 100%, positions.py 100%, __init__.py 100%, all-modules 96.17%). | closed |
| T-04-SC | Tampering | Supply chain (pip installs) | accept | No new packages installed across all three plans. All dependencies are pre-existing project deps verified in Phases 1–3. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-01 | strategy/ is a pure math layer. ASVS L1 trust boundary controls are enforced at the Phase 7 call site (the entry point receiving user-triggered scans), not inside strategy/. | David Barros | 2026-05-23 |
| AR-04-02 | T-04-02 | O(200) SMA computation bounded by design. ValueError guard prevents inputs outside the valid domain. | David Barros | 2026-05-23 |
| AR-04-03 | T-04-03 | Candidate fields contain only public market data (symbol, price, position count). No PII or credentials. | David Barros | 2026-05-23 |
| AR-04-04 | T-04-04, T-04-05 | positions.py accepts only float/int scalar arguments. ASVS L1 perimeter enforced at Phase 7 before any call into strategy/. | David Barros | 2026-05-23 |
| AR-04-05 | T-04-06 | Stop levels are arithmetic derivatives of public exchange prices. | David Barros | 2026-05-23 |
| AR-04-06 | T-04-07 | Gate is process-enforced (CI exit code). Risk of manual bypass is accepted for a single-user personal tool. | David Barros | 2026-05-23 |
| AR-04-07 | T-04-SC | Verification-only plan (04-03) installs nothing. All prior deps verified in Phase 1 skeleton. | David Barros | 2026-05-23 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-23 | 9 | 9 | 0 | gsd-secure-phase (automated) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-23
