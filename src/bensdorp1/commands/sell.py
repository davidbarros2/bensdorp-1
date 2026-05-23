import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Confirmations")
def sell() -> None:
    """Record a confirmed sell transaction."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
