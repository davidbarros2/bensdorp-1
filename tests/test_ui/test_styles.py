"""Tests for bensdorp1.ui.styles formatters, Style constants, and _console singleton."""

from datetime import UTC, date, datetime, timedelta

import pytest
from rich.console import Console
from rich.style import Style

from bensdorp1.ui.styles import (
    ERROR_STYLE,
    INFO_STYLE,
    MUTED_STYLE,
    SUCCESS_STYLE,
    WARNING_STYLE,
    _console,
    format_date,
    format_days,
    format_pct,
    format_pnl,
    format_price,
    format_relative_duration,
    format_time,
    format_timezone_pair,
    format_volume,
    render_kv_block,
)

# ---------------------------------------------------------------------------
# Numerical formatters (rule 6.10)
# ---------------------------------------------------------------------------


def test_format_price_typical() -> None:
    """format_price(1432.50) returns '$1,432.50'."""
    assert format_price(1432.50) == "$1,432.50"


def test_format_price_zero() -> None:
    """format_price(0.0) returns '$0.00'."""
    assert format_price(0.0) == "$0.00"


def test_format_pct_positive() -> None:
    """format_pct(185.3) returns '+185.3%'."""
    assert format_pct(185.3) == "+185.3%"


def test_format_pct_negative() -> None:
    """format_pct(-12.4) returns '-12.4%'."""
    assert format_pct(-12.4) == "-12.4%"


def test_format_pct_zero() -> None:
    """format_pct(0.0) returns '+0.0%' (zero treated as non-negative)."""
    assert format_pct(0.0) == "+0.0%"


def test_format_pnl_positive() -> None:
    """format_pnl(1432.50) returns '+$1,432.50'."""
    assert format_pnl(1432.50) == "+$1,432.50"


def test_format_pnl_negative() -> None:
    """format_pnl(-543.20) returns '-$543.20'."""
    assert format_pnl(-543.20) == "-$543.20"


def test_format_pnl_zero() -> None:
    """format_pnl(0.0) returns '+$0.00'."""
    assert format_pnl(0.0) == "+$0.00"


def test_format_volume_large() -> None:
    """format_volume(52341200) returns '52,341,200'."""
    assert format_volume(52341200) == "52,341,200"


def test_format_days_one() -> None:
    """format_days(1) returns '1 day'."""
    assert format_days(1) == "1 day"


def test_format_days_zero() -> None:
    """format_days(0) returns '0 days'."""
    assert format_days(0) == "0 days"


def test_format_days_many() -> None:
    """format_days(47) returns '47 days'."""
    assert format_days(47) == "47 days"


# ---------------------------------------------------------------------------
# Date/time formatters (rules 6.24/6.25)
# ---------------------------------------------------------------------------


def test_format_date_iso8601() -> None:
    """format_date(date(2026, 5, 14)) returns '2026-05-14'."""
    assert format_date(date(2026, 5, 14)) == "2026-05-14"


def test_format_time_hhmm() -> None:
    """format_time returns HH:MM for the datetime supplied."""
    dt = datetime(2026, 5, 14, 9, 35, 0, tzinfo=UTC)
    assert format_time(dt) == "09:35"


# ---------------------------------------------------------------------------
# Timezone formatter (rule 6.26)
# ---------------------------------------------------------------------------


def test_format_timezone_pair_contains_et() -> None:
    """format_timezone_pair output contains 'ET (' for market side."""
    dt = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)
    result = format_timezone_pair(dt)
    assert "ET (" in result


def test_format_timezone_pair_contains_lisbon() -> None:
    """format_timezone_pair output ends with 'Lisbon)' for default user TZ."""
    dt = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)
    result = format_timezone_pair(dt)
    assert result.endswith("Lisbon)")


# ---------------------------------------------------------------------------
# Relative duration (rule 6.27)
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("delta_seconds", "expected"),
    [
        (30, "just now"),
        (90, "1 minutes ago"),
        (3600, "1 hours ago"),
        (86400, "1 days ago"),
        (86400 * 5, "5 days ago"),
        (86400 * 35, "1 months ago"),
        (86400 * 400, "1 years ago"),
    ],
)
def test_format_relative_duration_buckets(delta_seconds: int, expected: str) -> None:
    """Relative duration buckets match spec rule 6.27."""
    dt = _FIXED_NOW - timedelta(seconds=delta_seconds)
    result = format_relative_duration(dt, _now=_FIXED_NOW)
    assert result == expected


# ---------------------------------------------------------------------------
# KV alignment helper
# ---------------------------------------------------------------------------


def test_render_kv_block_alignment() -> None:
    """render_kv_block values align at max_key_len + 1 + 2 columns."""
    console = Console(record=True, width=80)
    data = {
        "Database created": "/p/x.db",
        "History downloaded": "220 trading days",
    }
    render_kv_block(data, console)
    text = console.export_text()
    # longest key is "History downloaded" (18 chars); value at col 21 (18 + 1 colon + 2)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "Database created:" in lines[0]
    assert "History downloaded:" in lines[1]
    # values start at the same column
    val0_col = lines[0].index("/p/x.db")
    val1_col = lines[1].index("220 trading days")
    assert val0_col == val1_col


def test_render_kv_block_empty() -> None:
    """render_kv_block({}, console) writes nothing."""
    console = Console(record=True, width=80)
    render_kv_block({}, console)
    text = console.export_text()
    assert text.strip() == ""


# ---------------------------------------------------------------------------
# Style constants (rule 6.29)
# ---------------------------------------------------------------------------


def test_style_constants_colors() -> None:
    """Each Style constant has the correct color name."""
    assert ERROR_STYLE.color is not None
    assert WARNING_STYLE.color is not None
    assert INFO_STYLE.color is not None
    assert SUCCESS_STYLE.color is not None
    assert MUTED_STYLE.color is not None
    assert ERROR_STYLE.color.name == "red"
    assert WARNING_STYLE.color.name == "yellow"
    assert INFO_STYLE.color.name == "cyan"
    assert SUCCESS_STYLE.color.name == "green"
    assert MUTED_STYLE.color.name == "bright_black"


@pytest.mark.parametrize(
    "style",
    [ERROR_STYLE, WARNING_STYLE, INFO_STYLE, SUCCESS_STYLE, MUTED_STYLE],
)
def test_no_bold_in_styles(style: Style) -> None:
    """No style has bold=True (rule 6.31)."""
    assert style.bold is None or style.bold is False


# ---------------------------------------------------------------------------
# Spinner frames assertion (rule 6.22)
# ---------------------------------------------------------------------------


def test_dots_spinner_frames_match_spec() -> None:
    """Rich 'dots' spinner frames exactly match spec braille sequence (rule 6.22)."""
    from typing import Any, cast  # noqa: PLC0415

    import rich.spinner as _rs  # noqa: PLC0415

    # SPINNERS is not in rich.spinner's __all__; access via type: ignore
    spinners: dict[str, Any] = cast(
        "dict[str, Any]",
        _rs.SPINNERS,  # type: ignore[attr-defined]
    )
    # frames may be a str (joined) or list[str] — normalise to list[str]
    raw_frames: Any = spinners["dots"]["frames"]
    frames: list[str] = list(raw_frames)
    expected = list("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    assert frames == expected


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


def test_console_singleton_exists() -> None:
    """_console is a Console instance at module level."""
    assert isinstance(_console, Console)
