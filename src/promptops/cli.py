from __future__ import annotations

import json
import os
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from promptops import __version__
from promptops import engine as _engine
from promptops.engine import DEFAULT_MODELS
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


@app.command()
def run(
    prompt_path: Path = typer.Argument(..., help="Prompt YAML file."),
    suite_path: Path = typer.Option(..., "--suite", "-s", help="Test suite YAML."),
    provider: str = typer.Option(None, "--provider", "-p", help="openai or anthropic."),
    model: str = typer.Option(None, "--model", "-m", help="Model name override."),
    output: Path = typer.Option(None, "--output", "-o", help="Write JSON results here."),
):
    """Run a prompt against a test suite and display deterministic scores."""
    # Resolve provider
    if provider is None:
        provider = os.environ.get("PROMPTOPS_PROVIDER", "openai")
    if provider not in DEFAULT_MODELS:
        console.print(f"[red]Unknown provider: '{provider}'. Must be 'openai' or 'anthropic'.[/red]")
        raise typer.Exit(code=1)

    # Resolve model
    if model is None:
        model = DEFAULT_MODELS[provider]

    # Load prompt and suite
    try:
        prompt = load_prompt(prompt_path)
    except (ValidationError, FileNotFoundError) as exc:
        console.print(f"[red]Failed to load prompt:[/red] {exc}")
        raise typer.Exit(code=1)

    try:
        suite = load_suite(suite_path)
    except (ValidationError, FileNotFoundError) as exc:
        console.print(f"[red]Failed to load suite:[/red] {exc}")
        raise typer.Exit(code=1)

    # Run eval
    try:
        results = _engine.run_eval(prompt, suite, provider, model)
    except Exception as exc:
        console.print(f"[red]Eval failed:[/red] {exc}")
        raise typer.Exit(code=1)

    # Print results table
    table = Table(title=f"Eval results — {prompt_path.name} × {suite_path.name}")
    table.add_column("ID")
    table.add_column("Pass")
    table.add_column("Det Reason")
    table.add_column("Latency ms", justify="right")
    table.add_column("Cost $", justify="right")

    total_cost = 0.0
    passed = 0
    for r in results:
        status = "[green]✓[/green]" if r.det_pass else "[red]✗[/red]"
        table.add_row(
            r.case_id,
            status,
            r.det_reason,
            f"{r.latency_ms:.0f}",
            f"${r.token_cost_usd:.5f}",
        )
        total_cost += r.token_cost_usd
        if r.det_pass:
            passed += 1

    console.print(table)
    console.print(f"Pass rate: {passed}/{len(results)} | Total cost: ${total_cost:.5f}")

    # Optional JSON export
    if output is not None:
        output.write_text(json.dumps([r.model_dump() for r in results], indent=2))
        console.print(f"Results written to [bold]{output}[/bold]")
