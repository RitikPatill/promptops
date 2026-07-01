from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from promptops.cli import app
from promptops.models import EvalResult

runner = CliRunner()

PROMPT_YAML = (
    "system: You are helpful.\n"
    "user_template: '{{ question }}'\n"
    "variables: [question]\n"
    "metadata:\n"
    "  version: '1.0'\n"
)

SUITE_YAML = (
    "name: test\n"
    "cases:\n"
    "  - id: tc01\n"
    "    input:\n"
    "      question: What is 2+2?\n"
    "  - id: tc02\n"
    "    input:\n"
    "      question: What is the capital of France?\n"
    "  - id: tc03\n"
    "    input:\n"
    "      question: What colour is the sky?\n"
    "  - id: tc04\n"
    "    input:\n"
    "      question: Is water wet?\n"
)


def _fake_result(
    case_id: str,
    det_pass: bool,
    output: str = "Some output",
    judge_score: int | None = None,
    token_cost_usd: float = 0.0001,
    judge_cost_usd: float = 0.0,
) -> EvalResult:
    return EvalResult(
        case_id=case_id,
        input={"question": "test"},
        rendered_user="Answer: test.",
        output=output,
        latency_ms=100.0,
        prompt_tokens=10,
        completion_tokens=5,
        token_cost_usd=token_cost_usd,
        det_pass=det_pass,
        det_reason="no check" if det_pass else "no match",
        judge_score=judge_score,
        judge_reasoning="Good." if judge_score else None,
        judge_cost_usd=judge_cost_usd,
    )


@pytest.fixture
def prompt_files(tmp_path: Path):
    v1 = tmp_path / "v1.yaml"
    v2 = tmp_path / "v2.yaml"
    suite = tmp_path / "suite.yaml"
    v1.write_text(PROMPT_YAML)
    v2.write_text(PROMPT_YAML)
    suite.write_text(SUITE_YAML)
    return v1, v2, suite


def _make_v1_results():
    return [
        _fake_result("tc01", True),
        _fake_result("tc02", False),
        _fake_result("tc03", True),
        _fake_result("tc04", False),
    ]


def _make_v2_results():
    return [
        _fake_result("tc01", True),
        _fake_result("tc02", True),
        _fake_result("tc03", True),
        _fake_result("tc04", False),
    ]


def test_diff_exits_zero(prompt_files):
    v1, v2, suite = prompt_files
    with patch("promptops.cli._engine.run_eval", side_effect=[_make_v1_results(), _make_v2_results()]):
        result = runner.invoke(app, ["diff", str(v1), str(v2), "--suite", str(suite)])
    assert result.exit_code == 0, result.output
    assert "Δ" in result.output


def test_diff_table_headers(prompt_files):
    v1, v2, suite = prompt_files
    with patch("promptops.cli._engine.run_eval", side_effect=[_make_v1_results(), _make_v2_results()]):
        result = runner.invoke(app, ["diff", str(v1), str(v2), "--suite", str(suite)])
    assert result.exit_code == 0, result.output
    assert "V1 Det" in result.output
    assert "V2 Det" in result.output
    assert "V1 Output" in result.output
    assert "V2 Output" in result.output


def test_diff_delta_summary(prompt_files):
    """v1: 2/4 pass (50%), v2: 3/4 pass (75%) → delta +25.0%"""
    v1, v2, suite = prompt_files
    with patch("promptops.cli._engine.run_eval", side_effect=[_make_v1_results(), _make_v2_results()]):
        result = runner.invoke(app, ["diff", str(v1), str(v2), "--suite", str(suite)])
    assert result.exit_code == 0, result.output
    assert "+25.0%" in result.output


def test_diff_cost_delta_negative(prompt_files):
    """v1 cost > v2 cost → summary shows Δ -$"""
    v1, v2, suite = prompt_files
    v1_results = [_fake_result(f"tc0{i}", True, token_cost_usd=0.001) for i in range(1, 3)]
    v2_results = [_fake_result(f"tc0{i}", True, token_cost_usd=0.0005) for i in range(1, 3)]

    suite_two = (
        "name: small\n"
        "cases:\n"
        "  - id: tc01\n"
        "    input:\n"
        "      question: Q1\n"
        "  - id: tc02\n"
        "    input:\n"
        "      question: Q2\n"
    )
    import tempfile
    import os
    tf = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w")
    tf.write(suite_two)
    tf.close()
    try:
        with patch("promptops.cli._engine.run_eval", side_effect=[v1_results, v2_results]):
            result = runner.invoke(app, ["diff", str(v1), str(v2), "--suite", tf.name])
        assert result.exit_code == 0, result.output
        assert "-$0.0010" in result.output
    finally:
        os.unlink(tf.name)


def test_diff_json_export(prompt_files, tmp_path):
    v1, v2, suite = prompt_files
    out_file = tmp_path / "results.json"
    with patch("promptops.cli._engine.run_eval", side_effect=[_make_v1_results(), _make_v2_results()]):
        result = runner.invoke(app, ["diff", str(v1), str(v2), "--suite", str(suite), "--output", str(out_file)])
    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert "v1" in data
    assert "v2" in data
    assert "delta" in data
    assert isinstance(data["v1"], list)
    assert isinstance(data["v2"], list)
    assert "pass_rate_delta" in data["delta"]


def test_diff_with_judge(prompt_files):
    v1, v2, suite = prompt_files
    v1_results = [
        _fake_result("tc01", True, judge_score=3),
        _fake_result("tc02", False, judge_score=2),
        _fake_result("tc03", True, judge_score=4),
        _fake_result("tc04", False, judge_score=2),
    ]
    v2_results = [
        _fake_result("tc01", True, judge_score=4),
        _fake_result("tc02", True, judge_score=4),
        _fake_result("tc03", True, judge_score=5),
        _fake_result("tc04", False, judge_score=3),
    ]
    with patch("promptops.cli._engine.run_eval", side_effect=[v1_results, v2_results]):
        result = runner.invoke(app, ["diff", str(v1), str(v2), "--suite", str(suite), "--judge"])
    assert result.exit_code == 0, result.output
    assert "V1 ★" in result.output
    assert "Δ★" in result.output
