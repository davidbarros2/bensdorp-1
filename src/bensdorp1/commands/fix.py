import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Confirmations")
def fix() -> None:
    """Interactively correct the last transaction for a symbol."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
