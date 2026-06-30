# PromptOps

A lightweight, local-first CLI toolkit for prompt engineers and LLM developers who want to iterate on system prompts with confidence.

## The Problem

Every serious LLM product needs evals, but most eval frameworks are either massive SaaS platforms or opinionated research libraries. There is no simple, zero-infra, git-friendly tool that lets you define a prompt in a file, pin a set of test inputs, run and score, then commit the prompt and its scores side-by-side.

PromptOps fills that gap.

## Who It's For

- Prompt engineers iterating on system prompts across versions
- LLM developers who want CI-friendly eval output
- Anyone who needs rigorous, reproducible prompt testing without a cloud dependency

## What Works (M2)

### M1 — Scaffold
- Python package at `src/promptops/` with `__version__ = "0.1.0"`
- `pyproject.toml` with pinned runtime dependencies: `typer`, `rich`, `pydantic`, `anthropic`, `openai`, `jinja2`, `pyyaml`
- Dev dependencies: `pytest`, `pytest-cov`, `ruff`, `mypy`
- MIT license and `.gitignore`
- `promptops` entry point registered via `[project.scripts]`; `promptops --help` and `promptops --version` work

### M2 — Prompt store + test suite schema
- Pydantic v2 models in `src/promptops/models.py`: `PromptDefinition`, `TestSuite`, `TestCase`, `ExpectedSpec`
- YAML loaders in `src/promptops/store.py`: `load_prompt` and `load_suite`
- `promptops validate <file>` command — validates any prompt or test-suite YAML, prints a rich summary on success, exits 1 on failure
- Example fixtures under `examples/`: `summarise_v1.yaml` (prompt) and `summarise_tests.yaml` (5-case test suite)
- `expected` per test case accepts `null`, a regex string, or a list of must-contain strings

```bash
promptops validate examples/summarise_v1.yaml
promptops validate examples/summarise_tests.yaml
```

## Planned Features

- **Eval engine**: resolves variables, calls OpenAI or Anthropic (env-var selected), collects `{output, latency_ms, token_cost}`
- **Scoring**: two layers — deterministic (regex/substring match) and LLM-as-judge (1–5 Likert score with reasoning)
- **Rich CLI output**: colour-coded table of per-case scores, aggregate pass-rate, cost estimate
- **Diff mode**: `promptops diff v1.yaml v2.yaml --suite tests.yaml` runs both prompts and renders a side-by-side terminal diff of outputs and scores
- **Export**: `--output results.json` for CI integration

## Out of Scope (v1)

- No web UI, no database, no hosted service
- No fine-tuning or training
- No multi-turn conversation evals (single-turn only)
- No image/multimodal prompts

## Quick Start

```bash
pip install -e ".[dev]"
promptops --help
```

```
Usage: promptops [OPTIONS] COMMAND [ARGS]...

  PromptOps — local-first prompt eval toolkit.

Options:
  -V, --version  Show version and exit.
  --help         Show this message and exit.

Commands:
  validate  Validate a prompt or test-suite YAML file.
```

Validate the bundled example fixtures:

```bash
promptops validate examples/summarise_v1.yaml
promptops validate examples/summarise_tests.yaml
```

## Architecture

```
promptops/
├── src/
│   └── promptops/
│       ├── __init__.py     # package version
│       ├── cli.py          # Typer app, entry point for all subcommands
│       ├── models.py       # Pydantic v2 models: PromptDefinition, TestSuite, …
│       └── store.py        # YAML loaders: load_prompt, load_suite
├── examples/
│   ├── summarise_v1.yaml   # example prompt definition
│   └── summarise_tests.yaml # 5-case test suite
├── tests/
│   ├── test_cli.py         # CLI smoke tests
│   ├── test_models.py      # model + loader unit tests
│   └── test_validate_cmd.py # validate command integration tests
├── pyproject.toml
├── .gitignore
├── LICENSE
└── README.md
```

## Roadmap

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1 | Scaffold + README | done |
| M2 | Prompt store — YAML schema + `promptops validate` | done |
| M3 | Eval engine — run prompts against test suite, collect outputs | planned |
| M4 | Scoring — deterministic + LLM-as-judge | planned |
| M5 | Diff mode — side-by-side terminal diff of two prompt versions | planned |
| M6 | Export + CI integration — `--output results.json` | planned |

## License

MIT — see [LICENSE](LICENSE).
