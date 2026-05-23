import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Daily operation")
def last() -> None:
    """Show the most recent scan output without re-running."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
