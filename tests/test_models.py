from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from promptops.models import ExpectedSpec, PromptDefinition, TestCase, TestSuite
from promptops.store import load_prompt, load_suite

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_prompt_round_trips_yaml():
    prompt = load_prompt(EXAMPLES / "summarise_v1.yaml")
    assert prompt.system
    assert prompt.variables == ["article"]


def test_suite_round_trips_yaml():
    suite = load_suite(EXAMPLES / "summarise_tests.yaml")
    assert len(suite.cases) == 5


def test_prompt_missing_system_raises():
    with pytest.raises(ValidationError):
        PromptDefinition(
            user_template="hello",
            metadata={"version": "1.0.0"},
        )


def test_suite_extra_key_raises():
    with pytest.raises(ValidationError):
        TestCase(
            id="tc01",
            input={"article": "text"},
            expected=None,
            unknown_key="bad",
        )


def test_expected_spec_variants():
    spec_none = ExpectedSpec(root=None)
    assert spec_none.root is None

    spec_str = ExpectedSpec(root="some regex")
    assert isinstance(spec_str.root, str)

    spec_list = ExpectedSpec(root=["must", "contain"])
    assert isinstance(spec_list.root, list)


def test_prompt_extra_key_raises():
    with pytest.raises(ValidationError):
        PromptDefinition(
            system="you are helpful",
            user_template="hello",
            metadata={"version": "1.0.0"},
            unknown_field="oops",
        )


def test_suite_auto_assigns_ids():
    suite = TestSuite(
        name="test",
        cases=[
            {"input": {"x": "a"}},
            {"input": {"x": "b"}},
        ],
    )
    assert suite.cases[0].id == "tc01"
    assert suite.cases[1].id == "tc02"
