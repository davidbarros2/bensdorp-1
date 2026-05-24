"""Minimalist Rich Table rendering per rules 6.8/6.9/6.31 (D-02).

Depends on: bensdorp1.ui.styles (_console singleton)
Used by: all commands that need tabular output
"""

from typing import Literal

from rich.console import Console
from rich.table import Table

from bensdorp1.ui.styles import _console as _default_console

Justify = Literal["left", "right"]


def render_table(
    columns: list[tuple[str, Justify]],
    rows: list[list[str]],
    *,
    console: Console | None = None,
) -> None:
    """Render a minimalist Rich Table per rules 6.8/6.9/6.31.

    No borders, no bold headers, 2-space column separation.
    Text columns use justify='left'; number columns use justify='right'.
    Empty rows list renders headers only — no traceback.

    Args:
        columns: Sequence of (header, justify) pairs.
        rows:    Sequence of row cell values (strings).
        console: Output console. Defaults to module-level _default_console.
    """
    con = console if console is not None else _default_console
    table = Table(box=None, show_edge=False, padding=(0, 1), header_style="")
    for header, justify in columns:
        table.add_column(header, justify=justify)
    for row in rows:
        table.add_row(*row)
    con.print(table)
