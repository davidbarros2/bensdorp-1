import typer

from bensdorp1._app import app


@app.command(rich_help_panel="System")
def audit() -> None:
    """Query the audit log with optional filters."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
