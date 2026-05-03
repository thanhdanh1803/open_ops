# OpenOps

OpenOps is a Python CLI for running an **agentic DevOps assistant** from your terminal via a single entrypoint: **`openops chat`**.

`openops chat` is built for **repository traversal**: it can move through your project (files, folders, and code paths), build understanding across modules, and help you plan and carry out DevOps work with your repo as the working context. Potentially dangerous actions can be routed through **human-in-the-loop approvals** in the TUI so execution stays explicit.

- **Python**: 3.11+
- **Install**: editable install from this repo (see below)

## Quick start

```bash
cd /path/to/open_ops
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

openops init                 # interactive setup (LLM provider, keys, data dir)
openops doctor               # sanity-check install and credentials
openops chat                 # TUI chat in the current directory
openops chat /path/to/app    # chat with another project as context
openops deploy               # agent-assisted deploy flow for the current project
openops deploy --dry-run     # inspect without applying
```


## CLI overview

| Command | Purpose |
| --- | --- |
| `openops init` | First-run wizard |
| `openops chat` | Interactive assistant (supports `--new`, `--model`) |
| `openops deploy` | Deploy / dry-run (supports `--platform`, `--dry-run`, `--yes`, `--env-file`) |
| `openops config …` | `show`, `get`, `set`, `reset`, `path` |
| `openops doctor` | Health check |
| `openops version` | Version and active model |
| `openops monitor` | Monitoring daemon (`start`, `stop`, `status`, `logs`) |

Run `openops --help` or `openops <command> --help` for options.

## Documentation

Design and contributor material lives in [docs/](docs/):

- [Architecture](docs/01-architecture.md)
- [CLI and TUI](docs/04-cli-and-tui.md)
- [Configuration](docs/09-configuration.md)
- [Contributing](CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
pytest
```

Built with [Typer](https://typer.tiangolo.com/), [Rich](https://rich.readthedocs.io/), [LangGraph](https://langchain-ai.github.io/langgraph/), and related LangChain packages—see `pyproject.toml` for the full dependency list.
