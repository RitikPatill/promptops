import typer
from promptops import __version__

app = typer.Typer(help="PromptOps — local-first prompt eval toolkit.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, version: bool = typer.Option(False, "--version", "-V", help="Show version and exit.")):
    if version:
        typer.echo(f"promptops {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
