"""Tests for ui/tables.py — minimalist Rich Table rendering per rules 6.8/6.9/6.31."""

import pytest
from rich.console import Console

from bensdorp1.ui.tables import render_table


# Box-drawing characters that must NOT appear in minimalist table output (rule 6.8)
_BOX_CHARS = "│┌┐└┘├┤─━"


def test_render_table_no_borders() -> None:
    """render_table produces no box-drawing characters (rule 6.8 — minimalist)."""
    c = Console(record=True, width=80)
    render_table(
        [("Symbol", "left"), ("Close", "right")],
        [["AAPL", "$150.00"]],
        console=c,
    )
    output = c.export_text()
    for char in _BOX_CHARS:
        assert char not in output, f"Box-drawing char {char!r} found in output: {output!r}"


def test_render_table_header_text() -> None:
    """render_table output contains the header text verbatim."""
    c = Console(record=True, width=80)
    render_table(
        [("Symbol", "left"), ("Close", "right")],
        [["AAPL", "$150.00"]],
        console=c,
    )
    output = c.export_text()
    assert "Symbol" in output
    assert "Close" in output
    assert "AAPL" in output
    assert "$150.00" in output


def test_render_table_number_alignment() -> None:
    """Right-aligned number column: trailing chars of numbers align at same column."""
    c = Console(record=True, width=80)
    render_table(
        [("Symbol", "left"), ("Close", "right")],
        [
            ["AAPL", "$1.00"],
            ["MSFT", "$1,432.50"],
        ],
        console=c,
    )
    output = c.export_text()
    lines = [ln for ln in output.splitlines() if ln.strip()]
    # Find lines containing the number values
    number_lines = [ln for ln in lines if "$1.00" in ln or "$1,432.50" in ln]
    assert len(number_lines) == 2
    # Both numbers must end at the same column position (right-aligned)
    col_1 = len(number_lines[0].rstrip())
    col_2 = len(number_lines[1].rstrip())
    assert col_1 == col_2, (
        f"Numbers not right-aligned: '{number_lines[0].rstrip()}' ends at col {col_1}, "
        f"'{number_lines[1].rstrip()}' ends at col {col_2}"
    )


def test_render_table_no_bold_headers() -> None:
    """Header row contains no bold ANSI escape (rule 6.31 — header_style='')."""
    c = Console(record=True, force_terminal=True, width=80)
    render_table(
        [("Symbol", "left"), ("Close", "right")],
        [["AAPL", "$150.00"]],
        console=c,
    )
    styled = c.export_text(styles=True)
    assert "\x1b[1m" not in styled, f"Bold ANSI escape found in styled output: {styled!r}"


def test_render_table_empty_rows() -> None:
    """render_table with empty rows list does not raise and still shows header."""
    c = Console(record=True, width=80)
    render_table(
        [("Symbol", "left"), ("Close", "right")],
        [],
        console=c,
    )
    output = c.export_text()
    assert "Symbol" in output


def test_render_table_default_console_no_crash() -> None:
    """render_table without console= kwarg uses _default_console without raising."""
    # Smoke test — no assertion on output, just verifying no exception is raised
    render_table(
        [("Symbol", "left"), ("Close", "right")],
        [["AAPL", "$150.00"]],
    )


def test_render_table_sentence_case_header_passthrough() -> None:
    """render_table emits sentence-case headers verbatim (rule 6.1 is caller's duty)."""
    c = Console(record=True, width=80)
    render_table(
        [("Last close", "right"), ("Days held", "right")],
        [["$150.00", "3 days"]],
        console=c,
    )
    output = c.export_text()
    assert "Last close" in output
    assert "Days held" in output
