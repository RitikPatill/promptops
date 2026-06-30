from __future__ import annotations

from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from promptops import __version__
from promptops.store import load_prompt, load_suite

app = typer.Typer(help="PromptOps — local-first prompt eval toolkit.")
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, version: bool = typer.Option(False, "--version", "-V", help="Show version and exit.")):
    if version:
        typer.echo(f"promptops {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def validate(path: Path = typer.Argument(..., help="Prompt or test-suite YAML file to validate.")):
    """Validate a prompt definition or test suite file."""
    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(code=1)

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        console.print(f"[red]YAML parse error:[/red] {exc}")
        raise typer.Exit(code=1)

    # Try prompt first
    try:
        prompt = load_prompt(path)
        table = Table(title=f"[green]Valid prompt[/green]: {path.name}")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("version", prompt.metadata.version)
        table.add_row("author", prompt.metadata.author or "—")
        table.add_row("variables", ", ".join(prompt.variables) if prompt.variables else "—")
        table.add_row("system (preview)", prompt.system[:80].replace("\n", " ") + ("…" if len(prompt.system) > 80 else ""))
        console.print(table)
        return
    except ValidationError as prompt_err:
        # If the raw dict looks like a suite, try that
        if isinstance(raw, dict) and "cases" in raw:
            try:
                suite = load_suite(path)
                table = Table(title=f"[green]Valid test suite[/green]: {path.name}")
                table.add_column("Field")
                table.add_column("Value")
                table.add_row("name", suite.name)
                table.add_row("cases", str(len(suite.cases)))
                console.print(table)
                return
            except ValidationError as suite_err:
                console.print("[red]Validation failed (suite):[/red]")
                console.print(str(suite_err))
                raise typer.Exit(code=1)

        console.print("[red]Validation failed (prompt):[/red]")
        console.print(str(prompt_err))
        raise typer.Exit(code=1)
