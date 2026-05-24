"""Empty-state helpers per rules 6.11 and 6.19. Thin wrappers over print_info."""

from rich.console import Console

from bensdorp1.ui.messages import print_info


def print_empty_state(
    entity: str,
    suggestion: str | None = None,
    *,
    console: Console | None = None,
) -> None:
    """Print an explicit empty state message so output is never blank (rule 6.11).

    Builds 'No {entity} found.' and optionally appends the suggestion text.
    Delegates to print_info for consistent Info: severity prefix and color.
    """
    msg = f"No {entity} found."
    if suggestion:
        msg = f"{msg} {suggestion}"
    print_info(msg, console=console)
