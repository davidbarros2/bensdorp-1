import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Confirmations")
def buy() -> None:
    """Record a confirmed buy transaction."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
