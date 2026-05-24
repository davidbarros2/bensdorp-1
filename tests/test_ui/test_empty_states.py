"""Tests for ui/empty_states.py — empty state message content and behavior."""

from rich.console import Console

from bensdorp1.ui.empty_states import print_empty_state


def test_print_empty_state_basic() -> None:
    """Empty state without suggestion produces 'No X found.' with Info prefix."""
    c = Console(record=True, width=80)
    print_empty_state("open positions", console=c)
    text = c.export_text()
    assert "No open positions found." in text
    assert "Info:" in text


def test_print_empty_state_with_suggestion() -> None:
    """Empty state with suggestion includes both the 'No X found.' and suggestion."""
    c = Console(record=True, width=80)
    print_empty_state(
        "scans",
        suggestion="Run `bensdorp1 scan` first.",
        console=c,
    )
    text = c.export_text()
    assert "No scans found." in text
    assert "Run `bensdorp1 scan` first." in text


def test_print_empty_state_explicit_console() -> None:
    """The passed-in console receives the output — not a different console."""
    c = Console(record=True, width=80)
    print_empty_state("entries", console=c)
    text = c.export_text()
    assert "No entries found." in text


def test_print_empty_state_suggestion_appended() -> None:
    """Suggestion is appended to the 'No X found.' message (same line/message)."""
    c = Console(record=True, width=80)
    print_empty_state("positions", suggestion="Try adding a buy first.", console=c)
    text = c.export_text()
    # Suggestion must appear in output
    assert "Try adding a buy first." in text
    # Both message parts must be present
    assert "No positions found." in text


def test_print_empty_state_uses_info_severity() -> None:
    """Empty states use Info: severity prefix (delegates to print_info)."""
    c = Console(record=True, width=80)
    print_empty_state("scans", console=c)
    text = c.export_text()
    assert "Info:" in text


def test_print_empty_state_no_suggestion_no_extra_text() -> None:
    """Without suggestion, only the 'No X found.' message appears (no garbage)."""
    c = Console(record=True, width=80)
    print_empty_state("history", console=c)
    text = c.export_text().strip()
    # Should contain the core message
    assert "No history found." in text
    # Should not contain 'None' from a mis-handled None suggestion
    assert "None" not in text
