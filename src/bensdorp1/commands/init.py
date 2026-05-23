import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Setup")
def init() -> None:
    """First-run setup: create data directory, download history, record cash."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
