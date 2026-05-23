import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Daily operation")
def history() -> None:
    """Show a compact table of past scans."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
