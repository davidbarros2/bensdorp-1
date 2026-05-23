import typer

from bensdorp1._app import app


@app.command(rich_help_panel="System")
def help(
    ctx: typer.Context,
    command: str = typer.Argument(default="", show_default=False),
) -> None:
    """Show command list, or detailed help for COMMAND."""
    if command:
        root_ctx = ctx.find_root()
        cmd_obj = root_ctx.command.commands.get(command)  # type: ignore[attr-defined]
        if cmd_obj is None:
            typer.echo(f"Unknown command: {command}", err=True)
            raise typer.Exit(1)
        typer.echo(cmd_obj.get_help(root_ctx))
    else:
        typer.echo(ctx.find_root().get_help())
    raise typer.Exit()
