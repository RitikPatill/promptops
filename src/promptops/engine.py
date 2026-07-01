from __future__ import annotations

import time

import anthropic
import jinja2
import openai

from promptops.models import EvalResult, PromptDefinition, TestSuite
from promptops.scorer import score_deterministic, score_llm_judge

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}

# Cost per 1 M tokens (input, output) — USD, approximate
COST_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":               (0.15,  0.60),
    "gpt-4o":                    (5.00, 15.00),
    "claude-haiku-4-5-20251001": (0.25,  1.25),
    "claude-sonnet-4-6":         (3.00, 15.00),
}


def _render(template_str: str, variables: dict[str, str]) -> str:
    """Jinja2 render; raises jinja2.TemplateError on bad syntax."""
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    template = env.from_string(template_str)
    return template.render(**variables)


def _call_openai(system: str, user: str, model: str) -> tuple[str, int, int, float]:
    """Returns (output_text, prompt_tokens, completion_tokens, latency_ms)."""
    client = openai.OpenAI()
    start = time.monotonic()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    latency_ms = (time.monotonic() - start) * 1000
    output_text = response.choices[0].message.content or ""
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    return output_text, prompt_tokens, completion_tokens, latency_ms


def _call_anthropic(system: str, user: str, model: str) -> tuple[str, int, int, float]:
    """Returns (output_text, input_tokens, output_tokens, latency_ms)."""
    client = anthropic.Anthropic()
    start = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    latency_ms = (time.monotonic() - start) * 1000
    output_text = response.content[0].text if response.content else ""
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    return output_text, input_tokens, output_tokens, latency_ms


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Falls back to 0.0 if model not in COST_TABLE."""
    if model not in COST_TABLE:
        return 0.0
    input_cost_per_m, output_cost_per_m = COST_TABLE[model]
    cost = (prompt_tokens / 1_000_000) * input_cost_per_m + (completion_tokens / 1_000_000) * output_cost_per_m
    return round(cost, 6)


def run_eval(
    prompt: PromptDefinition,
    suite: TestSuite,
    provider: str,
    model: str,
    judge: bool = False,
    judge_provider: str | None = None,
    judge_model: str | None = None,
) -> list[EvalResult]:
    results: list[EvalResult] = []

    for case in suite.cases:
        rendered_user = _render(prompt.user_template, case.input)

        if provider == "openai":
            output, prompt_tokens, completion_tokens, latency_ms = _call_openai(
                prompt.system, rendered_user, model
            )
        elif provider == "anthropic":
            output, prompt_tokens, completion_tokens, latency_ms = _call_anthropic(
                prompt.system, rendered_user, model
            )
        else:
            raise ValueError(f"Unknown provider: {provider!r}")

        token_cost_usd = _estimate_cost(model, prompt_tokens, completion_tokens)
        det_pass, det_reason = score_deterministic(output, case.expected)

        if judge:
            jp = judge_provider or provider
            jm = judge_model or model
            j_score, j_reason = score_llm_judge(
                instruction=prompt.system,
                input_text=rendered_user,
                output=output,
                expected=case.expected,
                provider=jp,
                model=jm,
            )
            j_cost = _estimate_cost(jm, len(rendered_user) // 4 + 200, 50)
        else:
            j_score, j_reason, j_cost = None, None, 0.0

        results.append(EvalResult(
            case_id=case.id,
            input=case.input,
            rendered_user=rendered_user,
            output=output,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            token_cost_usd=token_cost_usd,
            det_pass=det_pass,
            det_reason=det_reason,
            judge_score=j_score,
            judge_reasoning=j_reason,
            judge_cost_usd=j_cost,
        ))

    return results
