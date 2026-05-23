# Phase 3: Data Sources - Context

**Gathered:** 2026-05-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the `data/` subpackage — fetch S&P 500 constituents from Wikipedia (primary) and Slickcharts (secondary), download and persist price history via yfinance, and provide NYSE trading-day utilities via pandas_market_calendars. All data-quality rules (discrepancy thresholds, 95% coverage check, retry/backoff, ticker normalization, 7-day constituent cache) are implemented here in isolation.

This phase delivers: `src/bensdorp1/data/` with `constituents.py`, `prices.py`, `calendar.py`, and `__init__.py`. Phase 4 (Strategy Logic) and Phase 7 (Scan) call into this subpackage — they do not touch yfinance or scraping code directly.

Split detection (DATA-06) and absence catch-up are Phase 11 responsibilities. This phase does not implement them.

</domain>

<decisions>
## Implementation Decisions

### Download Strategy
- **D-01:** Hybrid bulk + per-symbol retry. Primary download is `yfinance.download(tickers_list, auto_adjust=True)` — one bulk call for all symbols. After the bulk call, any symbol missing from the result or with fewer than expected rows is retried individually with exponential backoff: 3 retries at 1 s, 2 s, 4 s delays (DATA-09). The MultiIndex result from bulk multi-ticker downloads is flattened immediately after download (CLAUDE.md `yfinance download() multi-level column index` section).

### Price Data Persistence and Freshness
- **D-02:** DB-first incremental model. `init` (Phase 6) pre-loads 220 trading days for all constituents + `^GSPC` into `price_daily`. At scan time, the data layer reads from `price_daily` and fetches only days not yet present in the DB (today, or any missed trading days). The 95% coverage check (DATA-10) runs against what's in `price_daily` before any scan proceeds.

### Constituents Unavailability
- **D-03:** Stale cache with warning — never hard-fail on network unavailability alone. If the 7-day TTL has expired and both Wikipedia and Slickcharts are unreachable, the scan continues using the cached constituent list with a clear Warning-severity message: "Constituents data is N days old — refresh failed." No hard staleness cutoff: as long as the DB has constituent data, the scan can proceed. The user can run `bensdorp1 refresh` when the network is restored.

### SPX Index Data
- **D-04:** `^GSPC` is treated as a regular symbol in `price_daily` (same table, same download path). The data layer always includes `^GSPC` in its download list regardless of the constituents list — it is not an S&P 500 constituent but is required for the regime filter. Phase 4 queries `price_daily WHERE symbol = '^GSPC'` like any other symbol.

### data/ Module Structure
- **D-05 (Claude's discretion):** Four-module layout matching Phase 2's `db/` pattern:
  - `data/__init__.py` — re-exports public API (`get_constituents`, `update_price_data`, `get_trading_days`, etc.)
  - `data/constituents.py` — Wikipedia/Slickcharts scraping, discrepancy check, 7-day cache management against `constituents_cache` table
  - `data/prices.py` — yfinance bulk download + per-symbol retry, DB persistence into `price_daily`, incremental update logic
  - `data/calendar.py` — pandas_market_calendars wrappers for NYSE: trading-day offsets, is-trading-day check, N-days-ago arithmetic
  - Retry logic lives in `prices.py` and `constituents.py` as a shared helper (no separate `http.py` — retry is simple enough to inline)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/ROADMAP.md` §Phase 3 — Goal, success criteria, and 4 acceptance criteria
- `.planning/REQUIREMENTS.md` — DATA-01 through DATA-10 (all 10 data requirements are in scope for this phase)
- `.planning/PROJECT.md` — Key Decisions table (yfinance, pandas_market_calendars, Wikipedia primary choice)

### Technology guidance (in CLAUDE.md)
- `CLAUDE.md` §Verified Library Versions — yfinance `>=1.3.0`, pandas-market-calendars `>=5.3.2`, beautifulsoup4 `>=4.14.3`, httpx `>=0.28.1`
- `CLAUDE.md` §yfinance download() multi-level column index — MUST read: explains the MultiIndex issue and the fix for bulk multi-ticker downloads
- `CLAUDE.md` §yfinance auto_adjust default — auto_adjust=True required; do not rely on default
- `CLAUDE.md` §pandas-market-calendars v5 and pytz removal — v5 uses zoneinfo, not pytz; affects import patterns
- `CLAUDE.md` §Known Compatibility Issues — covers pandas 3.x and numpy 2.x compatibility

### Phase 2 context and schema
- `.planning/phases/02-database-and-migrations/02-CONTEXT.md` — D-05: all 7 tables are final; no ALTER TABLE in later phases. Phase 3 writes to `price_daily` and `constituents_cache` using the schema as defined.
- `src/bensdorp1/db/schema.py` — `price_daily` table (symbol, trade_date, close, volume; unique index on symbol+date) and `constituents_cache` table (symbol, company_name, fetched_at; unique on symbol) — read this before writing any insert/query logic

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/bensdorp1/db/engine.py` — `get_engine(path)` singleton. Phase 3 uses this to get the SQLAlchemy engine for all `price_daily` and `constituents_cache` reads/writes.
- `src/bensdorp1/db/audit.py` — `log_event()` + `AuditEventType`. Phase 3 emits `constituents_updated`, `data_fetch_failed`, and `constituents_discrepancy` events.
- `src/bensdorp1/db/schema.py` — import `price_daily`, `constituents_cache`, `metadata` from here. Do not redefine tables.

### Established Patterns
- **`src/` layout** — new subpackage at `src/bensdorp1/data/`. No flat modules at repo root.
- **`pathlib.Path` throughout** — user runs on Windows; never string concatenation for paths.
- **`-> None` on every function** — mypy strict requires explicit return annotations.
- **No circular imports** — `data/` must NOT import from `_app.py` or `commands/`. It is a pure data layer.
- **PEP 735 dependency groups** — beautifulsoup4, lxml, httpx, pandas-market-calendars are runtime deps in `[project.dependencies]` if not already present.

### Integration Points
- `src/bensdorp1/commands/init.py` (stub) — Phase 6 will call the data layer to download 220-day history and populate `price_daily`. Phase 3 implements the download functions; Phase 6 wires them.
- `src/bensdorp1/commands/scan.py` (stub) — Phase 7 calls the data layer for constituent list + incremental price update at scan time.
- `src/bensdorp1/commands/refresh.py` (stub) — Phase 10 calls `refresh_constituents()` directly.

</code_context>

<specifics>
## Specific Ideas

- Ticker normalization is the sole responsibility of `prices.py`: period form (`BRK.B`) is stored in `price_daily.symbol`; hyphen form (`BRK-B`) is constructed only at the yfinance call site and nowhere else (DATA-08).
- Wikipedia primary source: the S&P 500 component stocks page at en.wikipedia.org/wiki/List_of_S%26P_500_companies — parse the first `<table class="wikitable">` for Ticker and Security columns using BeautifulSoup + lxml.
- Slickcharts secondary source: cross-check only. The discrepancy count (DATA-02) is the absolute difference in tickers between the two sources — not intersection/union, but symmetric difference count.
- The 95% threshold (DATA-10) is checked after incremental price fetching completes: count constituent symbols with at least 220 rows in `price_daily`, divide by total constituent count. If < 95%, abort with Error-severity message.
- `^GSPC` always included in price downloads — add it to the tickers list before calling yfinance, never rely on it being in `constituents_cache`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 3-Data Sources*
*Context gathered: 2026-05-23*
