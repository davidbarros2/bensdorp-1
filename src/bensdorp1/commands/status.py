import typer

from bensdorp1._app import app


@app.command(rich_help_panel="System")
def status() -> None:
    """Show a diagnostic dashboard of system health."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
