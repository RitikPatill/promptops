from __future__ import annotations

from unittest.mock import MagicMock, patch

from promptops.models import ExpectedSpec
from promptops.scorer import score_llm_judge


def _make_openai_response(text: str):
    choice = MagicMock()
    choice.message.content = text
    response = MagicMock()
    response.choices = [choice]
    return response


def _make_anthropic_response(text: str):
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


def test_judge_openai_valid_json():
    mock_response = _make_openai_response('{"score": 4, "reasoning": "Good."}')

    with patch("promptops.scorer.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        score, reasoning = score_llm_judge(
            instruction="Be helpful.",
            input_text="What is 2+2?",
            output="4",
            expected=ExpectedSpec(root=None),
            provider="openai",
            model="gpt-4o-mini",
        )

    assert score == 4
    assert reasoning == "Good."


def test_judge_anthropic_valid_json():
    mock_response = _make_anthropic_response('{"score": 5, "reasoning": "Perfect answer."}')

    with patch("promptops.scorer.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        score, reasoning = score_llm_judge(
            instruction="Be helpful.",
            input_text="What is 2+2?",
            output="4",
            expected=ExpectedSpec(root=None),
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
        )

    assert score == 5
    assert reasoning == "Perfect answer."


def test_judge_parse_error_returns_zero():
    mock_response = _make_openai_response("not json at all")

    with patch("promptops.scorer.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        score, reasoning = score_llm_judge(
            instruction="Be helpful.",
            input_text="What is 2+2?",
            output="4",
            expected=ExpectedSpec(root=None),
            provider="openai",
            model="gpt-4o-mini",
        )

    assert score == 0
    assert reasoning == "judge parse error"


def test_judge_missing_keys_returns_zero():
    mock_response = _make_openai_response('{"score": 3}')

    with patch("promptops.scorer.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        score, reasoning = score_llm_judge(
            instruction="Be helpful.",
            input_text="What is 2+2?",
            output="4",
            expected=ExpectedSpec(root=None),
            provider="openai",
            model="gpt-4o-mini",
        )

    assert score == 0
    assert reasoning == "judge parse error"
