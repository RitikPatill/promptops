from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from promptops.cli import app
from promptops.models import EvalResult

runner = CliRunner()


def test_help_exits_zero():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "PromptOps" in result.output


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_run_with_judge_flag(tmp_path: Path):
    """run --judge should show Judge column and exit 0."""
    prompt_yaml = tmp_path / "prompt.yaml"
    prompt_yaml.write_text(
        "system: You are helpful.\n"
        "user_template: Say hello to {{ name }}.\n"
        "variables: [name]\n"
        "metadata:\n"
        "  version: '1.0'\n"
    )
    suite_yaml = tmp_path / "suite.yaml"
    suite_yaml.write_text(
        "name: test\n"
        "cases:\n"
        "  - id: tc01\n"
        "    input:\n"
        "      name: Alice\n"
    )

    mock_result = EvalResult(
        case_id="tc01",
        input={"name": "Alice"},
        rendered_user="Say hello to Alice.",
        output="Hello, Alice!",
        latency_ms=100.0,
        prompt_tokens=10,
        completion_tokens=5,
        token_cost_usd=0.0,
        det_pass=True,
        det_reason="no check",
        judge_score=4,
        judge_reasoning="Good response.",
        judge_cost_usd=0.0,
    )

    with patch("promptops.cli._engine.run_eval", return_value=[mock_result]):
        result = runner.invoke(app, [
            "run",
            str(prompt_yaml),
            "--suite", str(suite_yaml),
            "--judge",
        ])

    assert result.exit_code == 0
    assert "Judge" in result.output or "★" in result.output
