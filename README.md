# PromptOps

A lightweight, local-first CLI toolkit for prompt engineers and LLM developers who want to iterate on system prompts with confidence.

## The Problem

Every serious LLM product needs evals, but most eval frameworks are either massive SaaS platforms or opinionated research libraries. There is no simple, zero-infra, git-friendly tool that lets you define a prompt in a file, pin a set of test inputs, run and score, then commit the prompt and its scores side-by-side.

PromptOps fills that gap.

## Who It's For

- Prompt engineers iterating on system prompts across versions
- LLM developers who want CI-friendly eval output
- Anyone who needs rigorous, reproducible prompt testing without a cloud dependency

## What Works (M4)

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

### M3 — Eval engine + deterministic scoring
- `src/promptops/engine.py` — Jinja2 variable resolution, OpenAI and Anthropic dispatch, token cost estimation
- `src/promptops/scorer.py` — deterministic scoring: regex match or substring containment checks
- `promptops run <prompt.yaml> --suite <tests.yaml>` — runs all test cases, prints a Rich table with per-case pass/fail, latency, and cost; prints aggregate pass rate and total cost
- Provider selected via `--provider` flag or `PROMPTOPS_PROVIDER` env var (default: `openai`)
- Model override via `--model` flag; defaults to `gpt-4o-mini` (OpenAI) or `claude-haiku-4-5-20251001` (Anthropic)
- JSON export via `--output results.json` for CI integration
- Cost table covers `gpt-4o-mini`, `gpt-4o`, `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`

### M4 — LLM-as-judge scoring + rich CLI output
- `score_llm_judge()` in `src/promptops/scorer.py` — sends `(instruction, input, output, expected)` to a configurable judge model, parses a structured JSON response with `score` (1–5) and `reasoning`
- `EvalResult` gains three new optional fields: `judge_score`, `judge_reasoning`, `judge_cost_usd`
- `promptops run --judge` flag enables LLM-as-judge scoring (opt-in; no extra API calls without the flag)
- `--judge-model` flag to specify a different model for the judge (defaults to the same model as the eval)
- Revised Rich table adds **Judge** (★N/5, color-coded) and **Reasoning** columns when `--judge` is active
- Summary line shows pass rate, mean judge score (when applicable), total latency, and total cost
- Full judge data included in `--output` JSON export

```bash
# Set your API key
export OPENAI_API_KEY=sk-...
# or for Anthropic:
export ANTHROPIC_API_KEY=sk-ant-...
export PROMPTOPS_PROVIDER=anthropic

# Run eval (deterministic only)
promptops run examples/summarise_v1.yaml --suite examples/summarise_tests.yaml

# Run eval with LLM-as-judge scoring
promptops run examples/summarise_v1.yaml --suite examples/summarise_tests.yaml --judge

# Use a different judge model
promptops run examples/summarise_v1.yaml --suite examples/summarise_tests.yaml --judge --judge-model gpt-4o

# With JSON export (includes judge scores)
promptops run examples/summarise_v1.yaml --suite examples/summarise_tests.yaml --judge --output results.json

# Validate files
promptops validate examples/summarise_v1.yaml
promptops validate examples/summarise_tests.yaml
```

## Planned Features

- **Rich diff mode**: `promptops diff v1.yaml v2.yaml --suite tests.yaml` — side-by-side terminal diff of outputs and scores

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
  run       Run a prompt against a test suite; display scores and optional LLM judge.
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
│       ├── engine.py       # eval runner: Jinja2 render, API dispatch, cost estimation
│       ├── models.py       # Pydantic v2 models: PromptDefinition, TestSuite, EvalResult, …
│       ├── scorer.py       # deterministic + LLM-as-judge scoring
│       └── store.py        # YAML loaders: load_prompt, load_suite
├── examples/
│   ├── summarise_v1.yaml   # example prompt definition
│   └── summarise_tests.yaml # 5-case test suite
├── tests/
│   ├── test_cli.py         # CLI smoke tests
│   ├── test_engine.py      # engine unit tests (all mocked, no API key needed)
│   ├── test_models.py      # model + loader unit tests
│   ├── test_scorer.py      # deterministic and LLM-as-judge scorer unit tests
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
| M3 | Eval engine — run prompts against test suite, deterministic scoring, JSON export | done |
| M4 | LLM-as-judge scoring + rich CLI output | done |
| M5 | Diff mode — side-by-side terminal diff of two prompt versions | planned |

## License

MIT — see [LICENSE](LICENSE).
