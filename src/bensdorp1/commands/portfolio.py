import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Positions")
def portfolio() -> None:
    """List all open positions with current metrics."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
