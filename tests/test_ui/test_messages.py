"""Tests for ui/messages.py — severity prefixes, colors, kv alignment, security.

All assertions use Console(record=True) per D-04 testing approach.
"""

import pytest
from rich.console import Console

from bensdorp1.ui.messages import (
    Severity,
    print_error,
    print_info,
    print_message,
    print_success,
    print_warning,
)

# ---------------------------------------------------------------------------
# Parametrized severity prefix tests
# ---------------------------------------------------------------------------

SEVERITY_PREFIXES = {
    Severity.ERROR: "Error:",
    Severity.WARNING: "Warning:",
    Severity.INFO: "Info:",
    Severity.SUCCESS: "Success:",
}


@pytest.mark.parametrize("severity", list(Severity))
def test_severity_prefix_in_output(severity: Severity) -> None:
    """Each severity prefix appears as plain text in rendered output."""
    c = Console(record=True, width=80)
    print_message(severity, "Test message", console=c)
    text = c.export_text()
    expected_prefix = SEVERITY_PREFIXES[severity]
    assert expected_prefix in text, (
        f"Expected '{expected_prefix}' in output, got: {text!r}"
    )


def test_severity_enum_values() -> None:
    """Severity enum values are display labels, NOT StrEnum storage strings."""
    assert Severity.ERROR.value == "Error"
    assert Severity.WARNING.value == "Warning"
    assert Severity.INFO.value == "Info"
    assert Severity.SUCCESS.value == "Success"


# ---------------------------------------------------------------------------
# Shortcut alias tests
# ---------------------------------------------------------------------------


def test_print_error() -> None:
    """print_error produces output containing 'Error: Disk full.'."""
    c = Console(record=True, width=80)
    print_error("Disk full.", console=c)
    text = c.export_text()
    assert "Error: Disk full." in text


def test_print_warning() -> None:
    """print_warning produces output containing 'Warning:' prefix."""
    c = Console(record=True, width=80)
    print_warning("Low disk space.", console=c)
    text = c.export_text()
    assert "Warning: Low disk space." in text


def test_print_info() -> None:
    """print_info produces output containing 'Info:' prefix."""
    c = Console(record=True, width=80)
    print_info("System ready.", console=c)
    text = c.export_text()
    assert "Info: System ready." in text


def test_print_success() -> None:
    """print_success produces output containing 'Success:' prefix."""
    c = Console(record=True, width=80)
    print_success("Trade recorded.", console=c)
    text = c.export_text()
    assert "Success: Trade recorded." in text


# ---------------------------------------------------------------------------
# ANSI color path tests
# ---------------------------------------------------------------------------


def test_print_info_ansi_color() -> None:
    """print_info emits ANSI cyan escape when force_terminal=True."""
    c = Console(record=True, force_terminal=True, width=80)
    print_info("Test", console=c)
    styled = c.export_text(styles=True)
    assert "\x1b[36m" in styled, f"Expected cyan ANSI code in: {styled!r}"


def test_print_error_ansi_color() -> None:
    """print_error emits ANSI red escape when force_terminal=True."""
    c = Console(record=True, force_terminal=True, width=80)
    print_error("Test", console=c)
    styled = c.export_text(styles=True)
    assert "\x1b[31m" in styled, f"Expected red ANSI code in: {styled!r}"


def test_print_warning_ansi_color() -> None:
    """print_warning emits ANSI yellow escape when force_terminal=True."""
    c = Console(record=True, force_terminal=True, width=80)
    print_warning("Test", console=c)
    styled = c.export_text(styles=True)
    assert "\x1b[33m" in styled, f"Expected yellow ANSI code in: {styled!r}"


def test_print_success_ansi_color() -> None:
    """print_success emits ANSI green escape when force_terminal=True."""
    c = Console(record=True, force_terminal=True, width=80)
    print_success("Test", console=c)
    styled = c.export_text(styles=True)
    assert "\x1b[32m" in styled, f"Expected green ANSI code in: {styled!r}"


# ---------------------------------------------------------------------------
# NO_COLOR fallback test
# ---------------------------------------------------------------------------


def test_print_info_no_color() -> None:
    """NO_COLOR: prefix present; second export_text() returns '' (buffer cleared)."""
    c = Console(record=True, no_color=True, force_terminal=True, width=80)
    print_info("Test", console=c)
    text = c.export_text()
    assert "Info: Test" in text
    # Buffer cleared on first export_text() call — second call returns empty string
    styled = c.export_text(styles=True)
    assert styled == "", f"Expected empty after buffer cleared, got: {styled!r}"


# ---------------------------------------------------------------------------
# KV block alignment tests
# ---------------------------------------------------------------------------


def test_print_message_kv_alignment() -> None:
    """Key:value pairs are column-aligned per rule 6.4."""
    c = Console(record=True, width=80)
    print_message(
        Severity.INFO,
        "Setup complete",
        data={"Database created": "/p/x.db", "History downloaded": "220 trading days"},
        console=c,
    )
    text = c.export_text()
    # Both keys must appear
    assert "Database created" in text
    assert "History downloaded" in text
    # The values must also appear
    assert "/p/x.db" in text
    assert "220 trading days" in text
    # Find column positions of values to verify alignment
    lines = text.splitlines()
    kv_lines = [
        line for line in lines if "/p/x.db" in line or "220 trading days" in line
    ]
    assert len(kv_lines) == 2, f"Expected 2 kv lines, got: {kv_lines}"
    # The values must start at the same column position (aligned)
    col_db = kv_lines[0].index("/p/x.db")
    col_hist = kv_lines[1].index("220 trading days")
    assert col_db == col_hist, (
        f"Values not column-aligned: '/p/x.db' at col {col_db}, "
        f"'220 trading days' at col {col_hist}"
    )


# ---------------------------------------------------------------------------
# Optional block tests
# ---------------------------------------------------------------------------


def test_print_message_with_actions() -> None:
    """print_message with actions produces numbered action list."""
    c = Console(record=True, width=80)
    print_message(
        Severity.ERROR,
        "Database corrupted",
        actions=["Run the restore command.", "Contact support if issue persists."],
        console=c,
    )
    text = c.export_text()
    assert "Recommended actions:" in text
    assert "1. Run the restore command." in text
    assert "2. Contact support if issue persists." in text


def test_print_message_with_impact_and_body() -> None:
    """print_message with all optional blocks renders all sections."""
    c = Console(record=True, width=80)
    print_message(
        Severity.WARNING,
        "Positions need review",
        data={"Open positions": "7"},
        body=["This is a body line.", "Second body line."],
        impact={"Trading impact": "Reduced capacity"},
        actions=["Review all positions."],
        console=c,
    )
    text = c.export_text()
    assert "Warning: Positions need review" in text
    assert "Open positions" in text
    assert "This is a body line." in text
    assert "Second body line." in text
    assert "Impact" in text
    assert "Trading impact" in text
    assert "Recommended actions:" in text
    assert "1. Review all positions." in text


def test_print_message_no_data_no_actions() -> None:
    """print_message with only severity+title produces exactly one meaningful line."""
    c = Console(record=True, width=80)
    print_message(Severity.INFO, "System ready", console=c)
    text = c.export_text()
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 1, f"Expected 1 meaningful line, got {len(lines)}: {lines!r}"
    assert "Info: System ready" in lines[0]


def test_print_message_data_none_no_extra_blank_lines() -> None:
    """print_message with data=None produces no spurious blank lines."""
    c = Console(record=True, width=80)
    print_message(Severity.INFO, "Simple message", data=None, console=c)
    text = c.export_text()
    # Strip trailing newline from Rich's output — look for consecutive blank lines
    assert "\n\n\n" not in text, f"Spurious blank lines in output: {text!r}"


# ---------------------------------------------------------------------------
# Security: Rich markup injection guard
# ---------------------------------------------------------------------------


def test_print_message_data_markup_injection() -> None:
    """Rich markup in data values is rendered literally, not interpreted."""
    c = Console(record=True, width=80)
    print_message(
        Severity.INFO,
        "Markup test",
        data={"label": "[red]X[/red]"},
        console=c,
    )
    text = c.export_text()
    # The literal string must appear unchanged — not interpreted as markup
    assert "[red]X[/red]" in text, f"Expected literal markup text in: {text!r}"


def test_print_message_title_markup_injection() -> None:
    """Rich markup in title is rendered literally, not interpreted."""
    c = Console(record=True, force_terminal=True, width=80)
    print_message(
        Severity.INFO,
        "[bold]injected[/bold]",
        console=c,
    )
    # No bold ANSI from title: bold markup in title must not be interpreted
    styled = c.export_text(styles=True)
    assert "\x1b[1m" not in styled, "Bold ANSI from title markup injection found"


# ---------------------------------------------------------------------------
# No bold / no decorative icons (rules 6.31 and 6.30)
# ---------------------------------------------------------------------------


def test_no_bold_in_output() -> None:
    """No bold ANSI sequence (\\x1b[1m) in any rendered output (rule 6.31)."""
    c = Console(record=True, force_terminal=True, width=80)
    print_info("Test", console=c)
    styled = c.export_text(styles=True)
    assert "\x1b[1m" not in styled, f"Bold ANSI sequence found in output: {styled!r}"


def test_no_decorative_icons_in_output() -> None:
    """No decorative unicode icons in rendered output (rule 6.30)."""
    c = Console(record=True, width=80)
    print_info("Test", console=c)
    text = c.export_text()
    for icon in ("✓", "✗", "⚠", "ℹ"):
        assert icon not in text, f"Decorative icon '{icon}' found in output: {text!r}"
