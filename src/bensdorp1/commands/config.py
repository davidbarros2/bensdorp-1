import typer

from bensdorp1._app import app


@app.command(rich_help_panel="System")
def config() -> None:
    """Show current configuration: cash, directory, timezone, version."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
