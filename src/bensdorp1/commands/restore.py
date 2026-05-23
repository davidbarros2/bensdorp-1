import typer

from bensdorp1._app import app


@app.command(rich_help_panel="Setup")
def restore() -> None:
    """Replace current database with a backup file."""
    typer.echo("Not yet implemented.")
    raise typer.Exit()
