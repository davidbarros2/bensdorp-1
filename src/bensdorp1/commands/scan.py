import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Daily operation")
def scan() -> None:
    """Run daily end-of-day screening for exit triggers and buy candidates."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
