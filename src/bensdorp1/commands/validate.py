import typer

from bensdorp1._app import app


@app.command(rich_help_panel="System")
def validate() -> None:
    """Show what buy candidates System 1 would have produced on DATE."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
