import typer

from bensdorp1._app import app


@app.command(rich_help_panel="System")
def refresh() -> None:
    """Force re-fetch and re-verification of S&P 500 constituents."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
