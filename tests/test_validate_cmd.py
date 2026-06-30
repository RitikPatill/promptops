from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from promptops.cli import app

runner = CliRunner()
EXAMPLES = Path(__file__).parent.parent / "examples"


def test_validate_prompt_exits_zero():
    result = runner.invoke(app, ["validate", str(EXAMPLES / "summarise_v1.yaml")])
    assert result.exit_code == 0
    assert "1.0.0" in result.output or "valid" in result.output.lower()


def test_validate_suite_exits_zero():
    result = runner.invoke(app, ["validate", str(EXAMPLES / "summarise_tests.yaml")])
    assert result.exit_code == 0
    assert "5" in result.output


def test_validate_bad_file_exits_one(tmp_path):
    bad = tmp_path / "bad_prompt.yaml"
    bad.write_text("system: 123\nuser_template: hello\nmetadata:\n  version: 1\n")
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code == 1


def test_validate_missing_file_exits_one(tmp_path):
    result = runner.invoke(app, ["validate", str(tmp_path / "nonexistent.yaml")])
    assert result.exit_code == 1
