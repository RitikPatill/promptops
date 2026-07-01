from __future__ import annotations

import json
import re

import anthropic
import openai

from promptops.models import ExpectedSpec


def score_deterministic(output: str, expected: ExpectedSpec) -> tuple[bool, str]:
    """
    Returns (pass, reason).
    - expected.root is None  → always passes, reason = "no check"
    - expected.root is str   → re.search(pattern, output) must match
    - expected.root is list  → every substring must appear (case-sensitive)
    """
    spec = expected.root

    if spec is None:
        return True, "no check"

    if isinstance(spec, str):
        if re.search(spec, output):
            return True, f"regex matched: '{spec}'"
        return False, f"regex not matched: '{spec}'"

    # list of substrings — all must be present
    for substring in spec:
        if substring not in output:
            return False, f"missing: '{substring}'"
    return True, "all substrings found"


JUDGE_SYSTEM = (
    "You are an impartial LLM evaluator. Score the model output below on a 1–5 Likert scale "
    "where 1 = completely wrong/unhelpful and 5 = perfect. Respond with JSON only.\n"
    '{"score": <integer 1-5>, "reasoning": "<one concise sentence>"}'
)


def score_llm_judge(
    instruction: str,
    input_text: str,
    output: str,
    expected: "ExpectedSpec",
    provider: str,
    model: str,
) -> tuple[int, str]:
    """Call an LLM judge to score the output on a 1-5 Likert scale.

    Returns (score, reasoning). On parse errors returns (0, "judge parse error").
    """
    expected_str = ""
    if expected.root is not None:
        if isinstance(expected.root, list):
            expected_str = f"\nExpected to contain: {', '.join(repr(s) for s in expected.root)}"
        else:
            expected_str = f"\nExpected pattern: {expected.root!r}"

    judge_user = (
        f"Instruction (system prompt given to the model under test):\n{instruction}\n\n"
        f"Input sent to the model:\n{input_text}\n\n"
        f"Model output to evaluate:\n{output}"
        f"{expected_str}\n\n"
        "Respond with JSON only, no prose."
    )

    try:
        if provider == "openai":
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": judge_user},
                ],
                response_format={"type": "json_object"},
            )
            output_text = response.choices[0].message.content or ""
        elif provider == "anthropic":
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=model,
                max_tokens=256,
                system=JUDGE_SYSTEM,
                messages=[{"role": "user", "content": judge_user}],
            )
            output_text = response.content[0].text if response.content else ""
        else:
            return 0, "judge parse error"

        parsed = json.loads(output_text)
        score = parsed["score"]
        reasoning = parsed["reasoning"]
        return int(score), str(reasoning)
    except (json.JSONDecodeError, KeyError, Exception):
        return 0, "judge parse error"
