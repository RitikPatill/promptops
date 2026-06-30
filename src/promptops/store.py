from __future__ import annotations

from pathlib import Path

import yaml

from promptops.models import PromptDefinition, TestSuite


def load_prompt(path: Path) -> PromptDefinition:
    """Read a YAML file and return a validated PromptDefinition."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return PromptDefinition(**data)


def load_suite(path: Path) -> TestSuite:
    """Read a YAML/JSON file and return a validated TestSuite."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return TestSuite(**data)
