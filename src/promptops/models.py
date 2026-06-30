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
