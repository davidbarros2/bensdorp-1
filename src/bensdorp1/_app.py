import typer

app = typer.Typer(
    name="bensdorp1",
    help="Bensdorp System #1 — daily S&P 500 trend-following CLI.",
    rich_markup_mode="rich",
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # don't show Python tracebacks to the user
)
