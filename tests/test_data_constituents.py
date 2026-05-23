"""Tests for DATA-01, DATA-02, DATA-05: constituent fetching, discrepancy check, cache.

Uses db_engine fixture for cache TTL tests. HTTP calls mocked via unittest.mock.patch.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from bensdorp1.data import constituents as constituents_module
from bensdorp1.data.constituents import get_constituents, refresh_constituents
from bensdorp1.db.schema import audit_log, constituents_cache

# ---------------------------------------------------------------------------
# Minimal HTML fixtures
# ---------------------------------------------------------------------------

_WIKI_HTML_TWO_ROWS = """
<html><body>
<table class="wikitable">
<thead><tr><th>Symbol</th><th>Security</th></tr></thead>
<tbody>
<tr><td>AAPL</td><td>Apple Inc.</td></tr>
<tr><td>MSFT</td><td>Microsoft</td></tr>
</tbody>
</table>
</body></html>
"""

_WIKI_HTML_MALFORMED = """
<html><body>
<table class="wikitable">
<thead><tr><th>Symbol</th><th>Security</th></tr></thead>
<tbody>
<tr><td>AAPL</td><td>Apple</td></tr>
<tr><td>aapl;DROP TABLE</td><td>Bad</td></tr>
</tbody>
</table>
</body></html>
"""

_WIKI_HTML_NO_TABLE = """
<html><body><p>No table here.</p></body></html>
"""

_SLICKCHARTS_HTML = """
<html><body>
<table>
<tbody>
<tr><td>1</td><td>Apple Inc.</td><td>AAPL</td><td>7.0%</td><td>190</td><td>+1</td></tr>
<tr><td>2</td><td>Microsoft</td><td>MSFT</td><td>6.5%</td><td>380</td><td>-1</td></tr>
<tr><td>3</td><td>Berkshire</td><td>BRK.B</td><td>1.5%</td><td>350</td><td>0</td></tr>
</tbody>
</table>
</body></html>
"""


def _make_mock_client(html: str) -> MagicMock:
    """Return a mock httpx.Client whose .get() returns a response with .text = html."""
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_resp
    return mock_client


# ---------------------------------------------------------------------------
# DATA-01: Wikipedia fetch
# ---------------------------------------------------------------------------


def test_fetch_wikipedia_parses_symbols_and_names() -> None:
    """DATA-01: _fetch_wikipedia returns {symbol: company_name} for each valid row."""
    client = _make_mock_client(_WIKI_HTML_TWO_ROWS)
    result = constituents_module._fetch_wikipedia(client)
    assert result == {"AAPL": "Apple Inc.", "MSFT": "Microsoft"}


def test_fetch_wikipedia_drops_malformed_tickers() -> None:
    """Security: _fetch_wikipedia silently drops symbols failing the ticker regex."""
    client = _make_mock_client(_WIKI_HTML_MALFORMED)
    result = constituents_module._fetch_wikipedia(client)
    assert list(result.keys()) == ["AAPL"]
    assert "aapl;DROP TABLE" not in result


def test_fetch_wikipedia_raises_when_table_missing() -> None:
    """DATA-01: _fetch_wikipedia raises ValueError when wikitable not found."""
    client = _make_mock_client(_WIKI_HTML_NO_TABLE)
    with pytest.raises(ValueError, match=r"wikitable not found"):
        constituents_module._fetch_wikipedia(client)


# ---------------------------------------------------------------------------
# DATA-01: Slickcharts fetch
# ---------------------------------------------------------------------------


def test_fetch_slickcharts_parses_symbol_column() -> None:
    """DATA-01: _fetch_slickcharts returns set of valid ticker symbols from table."""
    client = _make_mock_client(_SLICKCHARTS_HTML)
    result = constituents_module._fetch_slickcharts(client)
    assert isinstance(result, set)
    assert result == {"AAPL", "MSFT", "BRK.B"}


# ---------------------------------------------------------------------------
# DATA-02: Discrepancy classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("diff_count", "expected"),
    [
        (0, "silent"),
        (3, "silent"),
        (4, "warn"),
        (10, "warn"),
        (11, "abort"),
        (500, "abort"),
    ],
)
def test_classify_discrepancy_bounds(diff_count: int, expected: str) -> None:
    """DATA-02: _classify_discrepancy returns correct category at boundaries."""
    assert constituents_module._classify_discrepancy(diff_count) == expected


def test_refresh_silent_when_discrepancy_le_3(db_engine: Engine) -> None:
    """DATA-02: refresh emits no CONSTITUENTS_DISCREPANCY when symmetric diff <= 3."""
    wiki = {"AAPL": "Apple", "MSFT": "MS", "GOOG": "Google"}
    slack = {"AAPL", "MSFT", "GOOG"}
    with (
        patch.object(constituents_module, "_fetch_wikipedia", return_value=wiki),
        patch.object(constituents_module, "_fetch_slickcharts", return_value=slack),
    ):
        refresh_constituents(db_engine)
    with db_engine.connect() as conn:
        cache_rows = conn.execute(select(constituents_cache)).fetchall()
        disc_rows = conn.execute(
            select(audit_log).where(
                audit_log.c.event_type == "constituents_discrepancy"
            )
        ).fetchall()
        updated_rows = conn.execute(
            select(audit_log).where(
                audit_log.c.event_type == "constituents_updated"
            )
        ).fetchall()
    assert len(cache_rows) == 3
    assert len(disc_rows) == 0
    assert len(updated_rows) == 1


def test_refresh_warn_when_discrepancy_4_to_10(db_engine: Engine) -> None:
    """DATA-02: refresh emits CONSTITUENTS_DISCREPANCY severity=warn when diff=10."""
    wiki = {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "GOOG": "Google",
        "AMZN": "Amazon",
        "META": "Meta",
        "NVDA": "Nvidia",
        "TSLA": "Tesla",
        "JPM": "JPMorgan",
        "V": "Visa",
        "MA": "Mastercard",
    }
    # Slickcharts matches 5 of wikipedia's, adds 5 different → symmetric diff = 10
    slack = {
        "AAPL", "MSFT", "GOOG", "AMZN", "META",
        "BRK.B", "UNH", "JNJ", "XOM", "PG",
    }
    with (
        patch.object(constituents_module, "_fetch_wikipedia", return_value=wiki),
        patch.object(constituents_module, "_fetch_slickcharts", return_value=slack),
    ):
        refresh_constituents(db_engine)
    with db_engine.connect() as conn:
        disc_rows = conn.execute(
            select(audit_log).where(
                audit_log.c.event_type == "constituents_discrepancy"
            )
        ).fetchall()
    assert len(disc_rows) == 1
    raw_payload: str = disc_rows[0][4]
    payload = json.loads(raw_payload)
    assert payload["severity"] == "warn"
    assert payload["diff_count"] == 10


def test_refresh_abort_when_discrepancy_ge_11(db_engine: Engine) -> None:
    """DATA-02: refresh emits CONSTITUENTS_DISCREPANCY severity=abort when diff>=11."""
    wiki = {f"SYM{i}": f"Company {i}" for i in range(12)}
    slack: set[str] = set()  # all 12 from wiki + 0 from slack = diff 12
    with (
        patch.object(constituents_module, "_fetch_wikipedia", return_value=wiki),
        patch.object(constituents_module, "_fetch_slickcharts", return_value=slack),
    ):
        refresh_constituents(db_engine)
    with db_engine.connect() as conn:
        disc_rows = conn.execute(
            select(audit_log).where(
                audit_log.c.event_type == "constituents_discrepancy"
            )
        ).fetchall()
    assert len(disc_rows) == 1
    raw_payload_abort: str = disc_rows[0][4]
    payload = json.loads(raw_payload_abort)
    assert payload["severity"] == "abort"
    assert payload["diff_count"] == 12


# ---------------------------------------------------------------------------
# DATA-05: 7-day cache TTL
# ---------------------------------------------------------------------------


def test_get_constituents_skips_fetch_when_cache_fresh(db_engine: Engine) -> None:
    """DATA-05: get_constituents skips refresh when cache is fresh (< 7 days old)."""
    now = datetime.now(UTC)
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="AAPL",
                company_name="Apple Inc.",
                fetched_at=now - timedelta(days=1),
            )
        )
        conn.commit()
    with patch.object(
        constituents_module, "refresh_constituents"
    ) as mock_refresh:
        result = get_constituents(db_engine)
    mock_refresh.assert_not_called()
    assert result == {"AAPL": "Apple Inc."}


def test_get_constituents_refreshes_when_cache_stale(db_engine: Engine) -> None:
    """DATA-05: get_constituents replaces cache when it is >7 days old."""
    now = datetime.now(UTC)
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="OLD",
                company_name="Old Corp",
                fetched_at=now - timedelta(days=8),
            )
        )
        conn.commit()
    new_wiki = {"AAPL": "Apple Inc.", "MSFT": "Microsoft"}
    new_slack = {"AAPL", "MSFT"}
    with (
        patch.object(constituents_module, "_fetch_wikipedia", return_value=new_wiki),
        patch.object(constituents_module, "_fetch_slickcharts", return_value=new_slack),
    ):
        result = get_constituents(db_engine)
    with db_engine.connect() as conn:
        rows = conn.execute(select(constituents_cache)).fetchall()
        updated = conn.execute(
            select(audit_log).where(audit_log.c.event_type == "constituents_updated")
        ).fetchall()
    assert "OLD" not in {r.symbol for r in rows}
    assert {"AAPL", "MSFT"} == {r.symbol for r in rows}
    assert len(updated) == 1
    assert result == {"AAPL": "Apple Inc.", "MSFT": "Microsoft"}


# ---------------------------------------------------------------------------
# D-03: Graceful degradation
# ---------------------------------------------------------------------------


def test_refresh_emits_data_fetch_failed_when_wikipedia_unreachable(
    db_engine: Engine,
) -> None:
    """D-03: refresh emits DATA_FETCH_FAILED when Wikipedia raises HTTPError."""
    with patch.object(
        constituents_module,
        "_fetch_wikipedia",
        side_effect=httpx.HTTPError("503"),
    ):
        refresh_constituents(db_engine)
    with db_engine.connect() as conn:
        fail_rows = conn.execute(
            select(audit_log).where(audit_log.c.event_type == "data_fetch_failed")
        ).fetchall()
        updated_rows = conn.execute(
            select(audit_log).where(audit_log.c.event_type == "constituents_updated")
        ).fetchall()
        cache_rows = conn.execute(select(constituents_cache)).fetchall()
    assert len(fail_rows) == 1
    raw_fail: str = fail_rows[0][4]
    payload = json.loads(raw_fail)
    assert payload["source"] == "wikipedia"
    assert len(updated_rows) == 0
    assert len(cache_rows) == 0


def test_refresh_continues_when_slickcharts_unreachable_but_wikipedia_succeeds(
    db_engine: Engine,
) -> None:
    """D-03: refresh continues when Slickcharts fails; discrepancy_count=-1 sentinel."""
    wiki = {"AAPL": "Apple", "MSFT": "Microsoft", "GOOG": "Google"}
    with (
        patch.object(constituents_module, "_fetch_wikipedia", return_value=wiki),
        patch.object(
            constituents_module,
            "_fetch_slickcharts",
            side_effect=httpx.HTTPError("403"),
        ),
    ):
        refresh_constituents(db_engine)
    with db_engine.connect() as conn:
        fail_rows = conn.execute(
            select(audit_log).where(audit_log.c.event_type == "data_fetch_failed")
        ).fetchall()
        updated_rows = conn.execute(
            select(audit_log).where(audit_log.c.event_type == "constituents_updated")
        ).fetchall()
        cache_rows = conn.execute(select(constituents_cache)).fetchall()
    assert len(fail_rows) == 1
    raw_fail_sc: str = fail_rows[0][4]
    fail_payload = json.loads(raw_fail_sc)
    assert fail_payload["source"] == "slickcharts"
    assert len(updated_rows) == 1
    raw_upd: str = updated_rows[0][4]
    upd_payload = json.loads(raw_upd)
    assert upd_payload["discrepancy_count"] == -1
    assert len(cache_rows) == 3


def test_get_constituents_returns_stale_cache_when_refresh_fails(
    db_engine: Engine,
) -> None:
    """D-03: get_constituents returns stale data + DATA_FETCH_FAILED on network fail."""
    now = datetime.now(UTC)
    with db_engine.connect() as conn:
        conn.execute(
            insert(constituents_cache).values(
                symbol="AAPL",
                company_name="Apple",
                fetched_at=now - timedelta(days=8),
            )
        )
        conn.execute(
            insert(constituents_cache).values(
                symbol="MSFT",
                company_name="Microsoft",
                fetched_at=now - timedelta(days=8),
            )
        )
        conn.commit()
    with patch.object(
        constituents_module,
        "_fetch_wikipedia",
        side_effect=httpx.HTTPError("timeout"),
    ):
        result = get_constituents(db_engine)
    assert "AAPL" in result
    assert "MSFT" in result
    with db_engine.connect() as conn:
        fail_rows = conn.execute(
            select(audit_log).where(audit_log.c.event_type == "data_fetch_failed")
        ).fetchall()
    assert len(fail_rows) == 1


# ---------------------------------------------------------------------------
# Security: ticker validation
# ---------------------------------------------------------------------------


def test_validate_ticker_accepts_period_form() -> None:
    """Security: _validate_ticker accepts valid S&P 500 ticker formats."""
    assert constituents_module._validate_ticker("AAPL") is True
    assert constituents_module._validate_ticker("BRK.B") is True
    assert constituents_module._validate_ticker("^GSPC") is True
    assert constituents_module._validate_ticker("BF.B") is True
    assert constituents_module._validate_ticker("aapl") is False
    assert constituents_module._validate_ticker("A APPLE") is False
    assert constituents_module._validate_ticker("TOOLONGTICKER") is False
    assert constituents_module._validate_ticker("AAPL;DROP") is False
    assert constituents_module._validate_ticker("") is False
