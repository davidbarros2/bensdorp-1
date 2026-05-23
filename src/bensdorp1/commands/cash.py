import typer

from bensdorp1._app import app


@app.command(rich_help_panel="System")
def cash() -> None:
    """Show current cash balance, or update it."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
