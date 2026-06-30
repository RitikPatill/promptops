from __future__ import annotations

from unittest.mock import MagicMock, patch

import jinja2
import pytest

from promptops.engine import (
    DEFAULT_MODELS,
    _call_anthropic,
    _call_openai,
    _estimate_cost,
    _render,
    run_eval,
)
from promptops.models import (
    EvalResult,
    ExpectedSpec,
    PromptDefinition,
    PromptMetadata,
    TestCase,
    TestSuite,
)
from promptops.scorer import score_deterministic


# ---------------------------------------------------------------------------
# _render
# ---------------------------------------------------------------------------

def test_render_jinja_basic():
    result = _render("hello {{ name }}", {"name": "world"})
    assert result == "hello world"


def test_render_missing_variable_raises():
    with pytest.raises(jinja2.UndefinedError):
        _render("hello {{ name }}", {})


# ---------------------------------------------------------------------------
# score_deterministic
# ---------------------------------------------------------------------------

def test_score_deterministic_none():
    passed, reason = score_deterministic("anything", ExpectedSpec(root=None))
    assert passed is True
    assert reason == "no check"


def test_score_deterministic_regex_pass():
    passed, reason = score_deterministic("The model is GPT-4 here", ExpectedSpec(root="GPT-4"))
    assert passed is True
    assert "GPT-4" in reason


def test_score_deterministic_regex_fail():
    passed, reason = score_deterministic("The model is GPT-4 here", ExpectedSpec(root="GPT-5"))
    assert passed is False
    assert "GPT-5" in reason


def test_score_deterministic_list_pass():
    passed, reason = score_deterministic(
        "The moon is a lunar body",
        ExpectedSpec(root=["moon", "lunar"]),
    )
    assert passed is True


def test_score_deterministic_list_fail():
    passed, reason = score_deterministic(
        "The moon is bright",
        ExpectedSpec(root=["moon", "lunar"]),
    )
    assert passed is False
    assert "lunar" in reason
    assert "missing" in reason


# ---------------------------------------------------------------------------
# _estimate_cost
# ---------------------------------------------------------------------------

def test_estimate_cost_known_model():
    # gpt-4o-mini: $0.15/M input, $0.60/M output
    # 100 prompt + 50 completion tokens
    cost = _estimate_cost("gpt-4o-mini", 100, 50)
    expected = (100 / 1_000_000) * 0.15 + (50 / 1_000_000) * 0.60
    assert abs(cost - round(expected, 6)) < 1e-9


def test_estimate_cost_unknown_model():
    cost = _estimate_cost("unknown-model-xyz", 1000, 500)
    assert cost == 0.0


# ---------------------------------------------------------------------------
# _call_openai (mocked)
# ---------------------------------------------------------------------------

def _make_openai_response(text: str, prompt_tokens: int, completion_tokens: int):
    choice = MagicMock()
    choice.message.content = text
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_anthropic_response(text: str, input_tokens: int, output_tokens: int):
    content_block = MagicMock()
    content_block.text = text
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


def test_run_eval_openai():
    mock_response = _make_openai_response("Hello from GPT", 10, 5)

    prompt = PromptDefinition(
        system="You are helpful.",
        user_template="Say hello to {{ name }}.",
        variables=["name"],
        metadata=PromptMetadata(version="1.0"),
    )
    suite = TestSuite(
        name="test",
        cases=[TestCase(id="tc01", input={"name": "Alice"}, expected=ExpectedSpec(root=None))],
    )

    with patch("promptops.engine.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        results = run_eval(prompt, suite, provider="openai", model="gpt-4o-mini")

    assert len(results) == 1
    r = results[0]
    assert isinstance(r, EvalResult)
    assert r.case_id == "tc01"
    assert r.output == "Hello from GPT"
    assert r.prompt_tokens == 10
    assert r.completion_tokens == 5
    assert r.det_pass is True
    assert r.rendered_user == "Say hello to Alice."


def test_run_eval_anthropic():
    mock_response = _make_anthropic_response("Hello from Claude", 8, 4)

    prompt = PromptDefinition(
        system="You are helpful.",
        user_template="Greet {{ name }}.",
        variables=["name"],
        metadata=PromptMetadata(version="1.0"),
    )
    suite = TestSuite(
        name="test",
        cases=[TestCase(id="tc01", input={"name": "Bob"}, expected=ExpectedSpec(root=None))],
    )

    with patch("promptops.engine.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        results = run_eval(prompt, suite, provider="anthropic", model="claude-haiku-4-5-20251001")

    assert len(results) == 1
    r = results[0]
    assert r.output == "Hello from Claude"
    assert r.prompt_tokens == 8
    assert r.completion_tokens == 4
    assert r.rendered_user == "Greet Bob."


def test_run_eval_det_pass_and_fail():
    """Two-case suite: first matches expected substring, second doesn't."""
    mock_resp_pass = _make_openai_response("The answer is Paris", 5, 5)
    mock_resp_fail = _make_openai_response("I don't know the answer", 5, 5)

    prompt = PromptDefinition(
        system="You are a geography expert.",
        user_template="What is the capital of {{ country }}?",
        variables=["country"],
        metadata=PromptMetadata(version="1.0"),
    )
    suite = TestSuite(
        name="geo",
        cases=[
            TestCase(id="tc01", input={"country": "France"}, expected=ExpectedSpec(root=["Paris"])),
            TestCase(id="tc02", input={"country": "Germany"}, expected=ExpectedSpec(root=["Berlin"])),
        ],
    )

    with patch("promptops.engine.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = [mock_resp_pass, mock_resp_fail]

        results = run_eval(prompt, suite, provider="openai", model="gpt-4o-mini")

    assert results[0].det_pass is True
    assert results[1].det_pass is False
    assert "Berlin" in results[1].det_reason
