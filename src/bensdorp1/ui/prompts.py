"""Custom prompts per rules 6.15-6.18 (D-05).

Uses input() directly — NOT typer.confirm or Rich.Prompt.

Depends on: bensdorp1.ui.styles (_console singleton)
Used by: commands that require user confirmation or data entry
"""

from rich.console import Console
from rich.text import Text

from bensdorp1.ui.styles import _console as _default_console


def confirm_prompt(message: str, *, console: Console | None = None) -> bool:
    """Prompt user for y/n confirmation per rule 6.15.

    Displays exactly '{message} [y/n] '.
    Accepts y Y n N (case-insensitive after strip).
    Re-prompts on empty input or any other character (rule 6.15 — no default).
    On KeyboardInterrupt: prints blank line then cancellation message,
    then re-raises so callers' except KeyboardInterrupt blocks fire.

    Args:
        message: The question to display (caller responsible for sentence case).
        console: Output console for KeyboardInterrupt message.
            Defaults to _default_console.

    Returns:
        True for y/Y, False for n/N.

    Raises:
        KeyboardInterrupt: when the user presses Ctrl+C.
    """
    con = console if console is not None else _default_console
    prompt_text = f"{message} [y/n] "
    while True:
        try:
            raw = input(prompt_text).strip().lower()
        except KeyboardInterrupt:
            con.print()
            con.print(Text("Operation aborted. No changes were made."))
            raise  # re-raise so callers' except KeyboardInterrupt blocks fire
        if raw == "y":
            return True
        if raw == "n":
            return False
        # re-prompt on empty or invalid input (rule 6.15 — no default)


def text_prompt(label: str, *, console: Console | None = None) -> str:
    """Prompt for free-text input per rule 6.16.

    Displays 'Enter {label}: ' and re-prompts on empty input.

    Args:
        label: What to ask for (e.g. 'symbol', 'reason').
        console: Unused parameter; kept for API consistency with other prompts.

    Returns:
        Non-empty stripped string entered by the user.
    """
    # console accepted for API consistency; text_prompt outputs nothing on re-prompt
    _ = console
    while True:
        raw = input(f"Enter {label}: ").strip()
        if raw:
            return raw
        # re-prompt on empty input


def number_prompt(label: str, unit: str, *, console: Console | None = None) -> float:
    """Prompt for a numeric value per rule 6.16.

    Displays '{label} in {unit}: ' and re-prompts on non-numeric input.
    Prints 'Error: Expected a number.' via console on invalid entry.

    Args:
        label: Description of the value (e.g. 'Cash').
        unit:  Unit of the value (e.g. 'USD').
        console: Output console for error message. Defaults to _default_console.

    Returns:
        Validated float value entered by the user.
    """
    con = console if console is not None else _default_console
    while True:
        raw = input(f"{label} in {unit}: ").strip()
        try:
            return float(raw)
        except ValueError:
            con.print(Text("Error: Expected a number."))
