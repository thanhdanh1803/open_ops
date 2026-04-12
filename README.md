# OpenOps

OpenOps is a Python CLI that pairs **LangGraph / LangChain** with a **Rich** terminal UI so you can chat with an agent about DevOps tasks—especially **analyzing repos and driving deployments** (for example Vercel, Railway, and Render) from your project directory.

- **Python:** 3.11+
- **Install:** editable install from this repo (see below)

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

Configure deployment tokens when prompted, or use `openops credentials add <platform>` after `init`. Global settings and encrypted credentials live under `~/.openops/` (see [docs/09-configuration.md](docs/09-configuration.md)).

## CLI overview

| Command | Purpose |
| --- | --- |
| `openops init` | First-run wizard |
| `openops chat` | Interactive assistant (optional `--model provider:model`) |
| `openops deploy` | Deploy / dry-run with optional `--platform` |
| `openops config …` | Show, get, set, reset, or print config path |
| `openops credentials …` | List, add, remove, or test platform credentials |
| `openops doctor` | Health check |
| `openops version` | Version and active model |
| `openops monitor` | Placeholder for future monitoring |

Run `openops --help` or `openops <command> --help` for options.

## Documentation

Design and contributor material lives in [docs/](docs/):

- [Architecture](docs/01-architecture.md)
- [CLI and TUI](docs/04-cli-and-tui.md)
- [Configuration](docs/09-configuration.md)
- [Contributing](docs/11-contributing.md)

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
pytest
```

Built with [Typer](https://typer.tiangolo.com/), [Rich](https://rich.readthedocs.io/), [LangGraph](https://langchain-ai.github.io/langgraph/), and related LangChain packages—see `pyproject.toml` for the full dependency list.
