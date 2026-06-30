# PromptOps

A lightweight, local-first CLI toolkit for prompt engineers and LLM developers who want to iterate on system prompts with confidence.

## The Problem

Every serious LLM product needs evals, but most eval frameworks are either massive SaaS platforms or opinionated research libraries. There is no simple, zero-infra, git-friendly tool that lets you define a prompt in a file, pin a set of test inputs, run and score, then commit the prompt and its scores side-by-side.

PromptOps fills that gap.

## Who It's For

- Prompt engineers iterating on system prompts across versions
- LLM developers who want CI-friendly eval output
- Anyone who needs rigorous, reproducible prompt testing without a cloud dependency

## What Works (M1)

The scaffold is in place and the package installs cleanly.

- Python package at `src/promptops/` with `__version__ = "0.1.0"`
- `pyproject.toml` with pinned runtime dependencies: `typer`, `rich`, `pydantic`, `anthropic`, `openai`, `jinja2`, `pyyaml`
- Dev dependencies: `pytest`, `pytest-cov`, `ruff`, `mypy`
- MIT license and `.gitignore`
- `promptops` entry point registered via `[project.scripts]`; `promptops --help` and `promptops --version` work
- Test harness in `tests/` with two passing smoke tests (`test_help_exits_zero`, `test_version_flag`)

## Planned Features

- **Prompt store**: each prompt is a `.yaml` file with `system`, `user_template`, optional `variables`, and metadata (version, author)
- **Test suite**: a JSON/YAML file of `{input, expected}` pairs; `expected` can be a regex, a list of must-contain strings, or `null` for LLM-judge-only scoring
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
```

## Architecture

```
promptops/
├── src/
│   └── promptops/
│       ├── __init__.py     # package version
│       └── cli.py          # Typer app, entry point for all subcommands
├── tests/
│   └── test_cli.py         # CLI smoke tests
├── pyproject.toml
├── .gitignore
├── LICENSE
└── README.md
```

<!-- TODO: add modules here as they are introduced (e.g. store.py, engine.py, scorer.py, differ.py) -->

## Roadmap

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1 | Scaffold + README | done |
| M2 | Prompt store — YAML schema + `promptops validate` | planned |
| M3 | Eval engine — run prompts against test suite, collect outputs | planned |
| M4 | Scoring — deterministic + LLM-as-judge | planned |
| M5 | Diff mode — side-by-side terminal diff of two prompt versions | planned |
| M6 | Export + CI integration — `--output results.json` | planned |

## License

MIT — see [LICENSE](LICENSE).
