from __future__ import annotations

from pydantic import BaseModel, ConfigDict, RootModel, model_validator


class PromptMetadata(BaseModel):
    version: str
    author: str | None = None
    description: str | None = None


class PromptDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str
    user_template: str
    variables: list[str] = []
    metadata: PromptMetadata


class ExpectedSpec(RootModel):
    root: str | list[str] | None = None


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    input: dict[str, str]
    expected: ExpectedSpec = ExpectedSpec()


class TestSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    cases: list[TestCase]

    @model_validator(mode="after")
    def _assign_missing_ids(self) -> "TestSuite":
        for i, case in enumerate(self.cases):
            if case.id is None:
                case.id = f"tc{i + 1:02d}"
        return self


class EvalResult(BaseModel):
    case_id: str
    input: dict[str, str]
    rendered_user: str        # Jinja2-resolved user message
    output: str               # raw LLM response text
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    token_cost_usd: float     # estimated cost
    det_pass: bool            # deterministic check result
    det_reason: str           # human-readable explanation of the check
    judge_score: int | None = None       # 1–5 Likert; None when --judge not used
    judge_reasoning: str | None = None   # one-sentence rationale from judge
    judge_cost_usd: float = 0.0          # cost of the judge call itself
