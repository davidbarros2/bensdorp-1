"""Severity-prefixed messages per rules 6.12, 6.13, 6.29 (D-07)."""

from enum import Enum

from rich.console import Console
from rich.text import Text

from bensdorp1.ui.styles import _console as _default_console
from bensdorp1.ui.styles import render_kv_block


class Severity(Enum):
    """Severity levels for user-facing messages (rule 6.13).

    Values are display labels — use Severity.X.value for the prefix string.
    NOT StrEnum: these are not storage keys, they are UI labels.
    """

    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"
    SUCCESS = "Success"


_SEVERITY_COLORS: dict[Severity, str] = {
    Severity.ERROR: "red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
    Severity.SUCCESS: "green",
}


def print_message(
    severity: Severity,
    title: str,
    *,
    data: dict[str, str] | None = None,
    body: list[str] | None = None,
    impact: dict[str, str] | None = None,
    actions: list[str] | None = None,
    console: Console | None = None,
) -> None:
    """Critical message structure per rule 6.12. Color on prefix only (rule 6.13).

    Prefix line: colored "Severity:" followed by plain title text.
    Optional blocks: data (kv-aligned), body (plain lines), impact (kv-aligned),
    actions (numbered list with "Recommended actions:" header).
    All caller-supplied strings rendered as plain text (markup injection blocked).
    """
    con = console if console is not None else _default_console
    color = _SEVERITY_COLORS[severity]

    # Line 1: colored prefix + plain title — build as Text to prevent markup injection
    # from both prefix context and title (rule 6.13: color on prefix only).
    prefix_text = Text()
    prefix_text.append(f"{severity.value}:", style=color)
    prefix_text.append(f" {title}")
    con.print(prefix_text, highlight=False)

    # Optional: data kv block — render_kv_block uses markup=False internally (T-05-04)
    if data:
        con.print()
        render_kv_block(data, con)

    # Optional: impact kv block with subsection separator
    if impact:
        con.print()
        con.print(Text("Impact"), highlight=False)
        con.print(Text("---"), highlight=False)
        render_kv_block(impact, con)

    # Optional: body lines — wrapped in Text to prevent markup injection
    if body:
        con.print()
        for line in body:
            con.print(Text(line), highlight=False)

    # Optional: numbered actions list
    if actions:
        con.print()
        con.print(Text("Recommended actions:"), highlight=False)
        for i, action in enumerate(actions, start=1):
            con.print(Text(f"{i}. {action}"), highlight=False)


def print_error(
    title: str,
    *,
    data: dict[str, str] | None = None,
    body: list[str] | None = None,
    impact: dict[str, str] | None = None,
    actions: list[str] | None = None,
    console: Console | None = None,
) -> None:
    """Print an error-severity message (rule 6.13: red prefix)."""
    print_message(
        Severity.ERROR,
        title,
        data=data,
        body=body,
        impact=impact,
        actions=actions,
        console=console,
    )


def print_warning(
    title: str,
    *,
    data: dict[str, str] | None = None,
    body: list[str] | None = None,
    impact: dict[str, str] | None = None,
    actions: list[str] | None = None,
    console: Console | None = None,
) -> None:
    """Print a warning-severity message (rule 6.13: yellow prefix)."""
    print_message(
        Severity.WARNING,
        title,
        data=data,
        body=body,
        impact=impact,
        actions=actions,
        console=console,
    )


def print_info(
    title: str,
    *,
    data: dict[str, str] | None = None,
    body: list[str] | None = None,
    impact: dict[str, str] | None = None,
    actions: list[str] | None = None,
    console: Console | None = None,
) -> None:
    """Print an info-severity message (rule 6.13: cyan prefix)."""
    print_message(
        Severity.INFO,
        title,
        data=data,
        body=body,
        impact=impact,
        actions=actions,
        console=console,
    )


def print_success(
    title: str,
    *,
    data: dict[str, str] | None = None,
    body: list[str] | None = None,
    impact: dict[str, str] | None = None,
    actions: list[str] | None = None,
    console: Console | None = None,
) -> None:
    """Print a success-severity message (rule 6.13: green prefix)."""
    print_message(
        Severity.SUCCESS,
        title,
        data=data,
        body=body,
        impact=impact,
        actions=actions,
        console=console,
    )
