from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from promptops import __version__
from promptops import engine as _engine
from promptops.engine import DEFAULT_MODELS
from promptops.models import EvalResult
from promptops.store import load_prompt, load_suite

app = typer.Typer(help="PromptOps — local-first prompt eval toolkit.")
console = Console()


def _resolve_provider_model(provider: Optional[str], model: Optional[str]) -> tuple[str, str]:
    """Resolve provider and model from args + env, with defaults."""
    if provider is None:
        provider = os.environ.get("PROMPTOPS_PROVIDER", "openai")
    if provider not in DEFAULT_MODELS:
        console.print(f"[red]Unknown provider: '{provider}'. Must be 'openai' or 'anthropic'.[/red]")
        raise typer.Exit(code=1)
    if model is None:
        model = DEFAULT_MODELS[provider]
    return provider, model


def _truncate(text: str, max_len: int = 60) -> str:
    return (text[:max_len] + "…") if len(text) > max_len else text


def _judge_cell(score: Optional[int]) -> str:
    if score is None:
        return "—"
    if score == 0:
        return "[red]ERR[/red]"
    if score >= 4:
        color = "green"
    elif score == 3:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]★{score}/5[/{color}]"


def _build_diff_table(v1_results: list[EvalResult], v2_results: list[EvalResult], judge: bool) -> Table:
    table = Table(title="Diff results — V1 vs V2")
    table.add_column("ID")
    table.add_column("V1 Det")
    table.add_column("V2 Det")
    table.add_column("Δ")
    table.add_column("V1 Output")
    table.add_column("V2 Output")
    if judge:
        table.add_column("V1 ★")
        table.add_column("V2 ★")
        table.add_column("Δ★")

    for r1, r2 in zip(v1_results, v2_results):
        v1_det = "[green]PASS[/green]" if r1.det_pass else "[red]FAIL[/red]"
        v2_det = "[green]PASS[/green]" if r2.det_pass else "[red]FAIL[/red]"

        if r1.det_pass == r2.det_pass:
            delta_det = "="
        elif r2.det_pass:
            delta_det = "[green]+[/green]"
        else:
            delta_det = "[red]-[/red]"

        row = [
            r1.case_id,
            v1_det,
            v2_det,
            delta_det,
            _truncate(r1.output),
            _truncate(r2.output),
        ]

        if judge:
            v1_star = _judge_cell(r1.judge_score)
            v2_star = _judge_cell(r2.judge_score)
            s1 = r1.judge_score or 0
            s2 = r2.judge_score or 0
            if r1.judge_score is None and r2.judge_score is None:
                delta_star = "—"
            else:
                diff = s2 - s1
                if diff > 0:
                    delta_star = f"[green]+{diff}[/green]"
                elif diff < 0:
                    delta_star = f"[red]{diff}[/red]"
                else:
                    delta_star = "=0"
            row += [v1_star, v2_star, delta_star]

        table.add_row(*row)

    return table


def _compute_delta(v1_results: list[EvalResult], v2_results: list[EvalResult]) -> dict:
    def _pass_rate(results: list[EvalResult]) -> float:
        if not results:
            return 0.0
        return sum(1 for r in results if r.det_pass) / len(results)

    def _total_cost(results: list[EvalResult]) -> float:
        return sum(r.token_cost_usd + r.judge_cost_usd for r in results)

    def _mean_judge(results: list[EvalResult]) -> Optional[float]:
        scores = [r.judge_score for r in results if r.judge_score is not None and r.judge_score > 0]
        return sum(scores) / len(scores) if scores else None

    pr1 = _pass_rate(v1_results)
    pr2 = _pass_rate(v2_results)
    cost1 = _total_cost(v1_results)
    cost2 = _total_cost(v2_results)
    mj1 = _mean_judge(v1_results)
    mj2 = _mean_judge(v2_results)

    return {
        "pass_rate_v1": pr1,
        "pass_rate_v2": pr2,
        "pass_rate_delta": pr2 - pr1,
        "total_cost_v1_usd": cost1,
        "total_cost_v2_usd": cost2,
        "cost_delta_usd": cost2 - cost1,
        "mean_judge_v1": mj1,
        "mean_judge_v2": mj2,
        "judge_delta": (mj2 - mj1) if (mj1 is not None and mj2 is not None) else None,
    }


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
    judge: bool = typer.Option(False, "--judge/--no-judge", help="Enable LLM-as-judge scoring."),
    judge_model: str = typer.Option(None, "--judge-model", help="Model for judge (defaults to --model)."),
):
    """Run a prompt against a test suite and display deterministic scores."""
    provider, model = _resolve_provider_model(provider, model)

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
        results = _engine.run_eval(
            prompt, suite, provider, model,
            judge=judge,
            judge_provider=provider,
            judge_model=judge_model,
        )
    except Exception as exc:
        console.print(f"[red]Eval failed:[/red] {exc}")
        raise typer.Exit(code=1)

    # Print results table
    table = Table(title=f"Eval results — {prompt_path.name} × {suite_path.name}")
    table.add_column("ID")
    table.add_column("Det")
    table.add_column("Det Reason")
    if judge:
        table.add_column("Judge")
        table.add_column("Reasoning")
    table.add_column("Latency ms", justify="right")
    table.add_column("Cost $", justify="right")

    total_cost = 0.0
    total_latency = 0.0
    passed = 0
    judge_scores: list[int] = []

    for r in results:
        det_badge = "[green]PASS[/green]" if r.det_pass else "[red]FAIL[/red]"
        case_cost = r.token_cost_usd + r.judge_cost_usd
        total_cost += case_cost
        total_latency += r.latency_ms
        if r.det_pass:
            passed += 1

        row = [r.case_id, det_badge, r.det_reason]

        if judge:
            if r.judge_score is None:
                judge_cell = "—"
                reasoning_cell = "—"
            elif r.judge_score == 0:
                judge_cell = "[red]ERR[/red]"
                reasoning_cell = r.judge_reasoning or "—"
            else:
                score = r.judge_score
                judge_scores.append(score)
                if score >= 4:
                    color = "green"
                elif score == 3:
                    color = "yellow"
                else:
                    color = "red"
                judge_cell = f"[{color}]★{score}/5[/{color}]"
                raw_reason = r.judge_reasoning or ""
                reasoning_cell = (raw_reason[:60] + "…") if len(raw_reason) > 60 else raw_reason
            row += [judge_cell, reasoning_cell]

        row += [f"{r.latency_ms:.0f}", f"${case_cost:.5f}"]
        table.add_row(*row)

    console.print(table)

    summary = f"Pass rate: {passed}/{len(results)} ({100 * passed / len(results):.1f}%)"
    if judge and judge_scores:
        mean_judge = sum(judge_scores) / len(judge_scores)
        summary += f" | Mean judge: {mean_judge:.1f}/5"
    summary += f" | Total latency: {total_latency:.0f} ms | Total cost: ${total_cost:.5f}"
    console.print(summary)

    # Optional JSON export
    if output is not None:
        output.write_text(json.dumps([r.model_dump() for r in results], indent=2))
        console.print(f"Results written to [bold]{output}[/bold]")


@app.command()
def diff(
    v1_path: Annotated[Path, typer.Argument(help="First prompt YAML")],
    v2_path: Annotated[Path, typer.Argument(help="Second prompt YAML")],
    suite_path: Annotated[Path, typer.Option("--suite", "-s", help="Test suite YAML")] = ...,
    provider: Annotated[Optional[str], typer.Option("--provider", "-p", help="openai or anthropic.")] = None,
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Model name override.")] = None,
    judge: Annotated[bool, typer.Option("--judge/--no-judge", help="Enable LLM-as-judge scoring.")] = False,
    judge_model: Annotated[Optional[str], typer.Option("--judge-model", help="Model for judge (defaults to --model).")] = None,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Write JSON results here.")] = None,
) -> None:
    """Compare two prompt versions side-by-side on the same test suite."""
    provider, model = _resolve_provider_model(provider, model)

    # Load prompts
    try:
        v1 = load_prompt(v1_path)
    except (ValidationError, FileNotFoundError) as exc:
        console.print(f"[red]Failed to load v1 prompt:[/red] {exc}")
        raise typer.Exit(code=1)

    try:
        v2 = load_prompt(v2_path)
    except (ValidationError, FileNotFoundError) as exc:
        console.print(f"[red]Failed to load v2 prompt:[/red] {exc}")
        raise typer.Exit(code=1)

    try:
        suite = load_suite(suite_path)
    except (ValidationError, FileNotFoundError) as exc:
        console.print(f"[red]Failed to load suite:[/red] {exc}")
        raise typer.Exit(code=1)

    # Run evals
    try:
        v1_results = _engine.run_eval(v1, suite, provider, model, judge=judge, judge_provider=provider, judge_model=judge_model)
    except Exception as exc:
        console.print(f"[red]Eval failed for v1:[/red] {exc}")
        raise typer.Exit(code=1)

    try:
        v2_results = _engine.run_eval(v2, suite, provider, model, judge=judge, judge_provider=provider, judge_model=judge_model)
    except Exception as exc:
        console.print(f"[red]Eval failed for v2:[/red] {exc}")
        raise typer.Exit(code=1)

    # Print diff table
    table = _build_diff_table(v1_results, v2_results, judge)
    console.print(table)

    # Print summary delta
    delta = _compute_delta(v1_results, v2_results)
    n = len(v1_results)
    p1 = delta["pass_rate_v1"]
    p2 = delta["pass_rate_v2"]
    pd = delta["pass_rate_delta"]
    c1 = delta["total_cost_v1_usd"]
    c2 = delta["total_cost_v2_usd"]
    cd = delta["cost_delta_usd"]

    p1_passed = round(p1 * n)
    p2_passed = round(p2 * n)
    pd_pct = pd * 100

    if pd > 0:
        pd_str = f"[green]Δ +{pd_pct:.1f}%[/green]"
    elif pd < 0:
        pd_str = f"[red]Δ {pd_pct:.1f}%[/red]"
    else:
        pd_str = "Δ 0.0%"

    if cd < 0:
        cd_str = f"[green]Δ -${abs(cd):.4f}/run[/green]"
    elif cd > 0:
        cd_str = f"[red]Δ +${cd:.4f}/run[/red]"
    else:
        cd_str = "Δ $0.0000/run"

    summary = (
        f"Pass-rate: {p1_passed}/{n} ({p1*100:.1f}%) → {p2_passed}/{n} ({p2*100:.1f}%)  {pd_str}"
        f"  |  Cost: ${c1:.4f} → ${c2:.4f}  {cd_str}"
    )
    console.print(summary)

    # Optional JSON export
    if output is not None:
        payload = {
            "v1_path": str(v1_path),
            "v2_path": str(v2_path),
            "suite_path": str(suite_path),
            "v1": [r.model_dump() for r in v1_results],
            "v2": [r.model_dump() for r in v2_results],
            "delta": delta,
        }
        output.write_text(json.dumps(payload, indent=2))
        console.print(f"Results written to [bold]{output}[/bold]")
