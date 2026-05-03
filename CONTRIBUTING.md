# Contributing to OpenOps

Thanks for contributing! This repo is an agentic DevOps assistant CLI (`openops`) built on LangGraph / Deep Agents, with a focus on safe execution (human approvals for risky actions).

## Quick start (dev)

- **Python**: 3.11+
- **Install (editable)**:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Common commands

```bash
ruff check src tests
pytest
```

If you use `pre-commit` locally:

```bash
pre-commit install
pre-commit run -a
```

## Project layout (high level)

- `src/openops/cli/`: Typer CLI entrypoints (`openops chat`, `openops deploy`, `openops monitor`, ...)
- `src/openops/agent/`: orchestrator, subagents, tools, prompts, tracing
- `src/openops/storage/`: persistence backends + schema
- `docs/`: design notes and deeper documentation
- `tests/`: test suite

## Development guidelines

- **Style**: keep code formatted and lint-clean under Ruff.
- **Tests**: add/adjust tests for behavior changes (especially around tools, storage, and daemon behavior).
- **Logging**:
  - Use `logger.info(...)` for key lifecycle events and user-relevant state changes.
  - Use `logger.debug(...)` for details that help diagnose behavior without spamming normal runs.
  - Avoid logging secrets (API keys, tokens, full env files).
- **Human approvals (HITL)**: changes that alter what requires approval should be called out clearly in PRs.

## Adding a monitoring sink (plugin)

OpenOps supports pluggable monitoring report sinks. Implement a sink object that conforms to the `MonitoringReportSink` protocol (`publish(report) -> None`) and expose it via a Python entry point group:

- **Entry point group**: `openops.monitoring_sinks`

If you add a sink inside this repo (not as a separate package), prefer keeping it small, dependency-light, and testable.

## Pull requests

- **Keep PRs small**: one logical change per PR when possible.
- **Include a test plan**: commands you ran and what you validated.
- **Explain user impact**: how the CLI/agent behavior changes (especially safety / approvals / config).

## Reporting bugs / requesting features

When filing an issue, include:

- What command you ran and expected behavior
- What happened instead (full error output if possible)
- Your OS + Python version
- Any relevant config details (redact secrets)
