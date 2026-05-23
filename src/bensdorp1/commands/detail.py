import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Positions")
def detail() -> None:
    """Show full history of a single open position."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
