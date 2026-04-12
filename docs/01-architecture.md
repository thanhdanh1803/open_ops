# OpenOps Architecture

## Overview

OpenOps is an open-source agentic DevOps assistant that helps developers go from working local code to production deployment and monitoring. It provides a chat-first interface via terminal TUI, powered by the Deep Agents framework.

## Design Principles

1. **Chat-first interaction** - All operations happen through natural conversation
2. **Shallow but purposeful understanding** - Analyzes only what's needed for DevOps tasks
3. **Community extensible** - Easy to add new platforms via skills
4. **Provider agnostic** - Works with OpenAI, Anthropic, or Google LLMs
5. **Hybrid architecture** - CLI for interaction, optional daemon for monitoring

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Rich TUI (chat interface)  │  Typer Commands (init, deploy, etc.)  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Core Agent System                                  │
│  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │   Orchestrator    │──│ Project Analyzer │  │     Subagents            │  │
│  │   (Deep Agent)    │  │   (Subagent)     │  │  - Deploy Agent          │  │
│  │                   │  │                  │  │  - Monitor Agent         │  │
│  └───────────────────┘  └──────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│    Skills Layer      │  │   Memory Layer   │  │    Infrastructure        │
│  ┌────────────────┐  │  │  ┌────────────┐  │  │  ┌────────────────────┐  │
│  │ Built-in:      │  │  │  │ LangGraph  │  │  │  │   LLM Router       │  │
│  │ - Vercel       │  │  │  │ Store      │  │  │  │   (multi-provider) │  │
│  │ - Railway      │  │  │  └────────────┘  │  │  └────────────────────┘  │
│  │ - Render       │  │  │  ┌────────────┐  │  │  ┌────────────────────┐  │
│  ├────────────────┤  │  │  │ Project    │  │  │  │   Config Store     │  │
│  │ Community:     │  │  │  │ Knowledge  │  │  │  │   (.openops/)      │  │
│  │ - AWS          │  │  │  │ Graph      │  │  │  └────────────────────┘  │
│  │ - GCP          │  │  │  └────────────┘  │  │  ┌────────────────────┐  │
│  │ - etc.         │  │  │                  │  │  │   Run History      │  │
│  └────────────────┘  │  │                  │  │  │   (.openops_runs)  │  │
└──────────────────────┘  └──────────────────┘  └──────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Background Layer (Optional)                         │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │   Monitor Daemon    │──│   Log Watcher   │──│   Alert Dispatcher      │  │
│  └─────────────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### CLI Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| Rich TUI | `rich`, `textual` | Interactive chat interface in terminal |
| Typer Commands | `typer` | CLI commands (`init`, `chat`, `deploy`, etc.) |

### Core Agent System

| Component | Framework | Purpose |
|-----------|-----------|---------|
| Orchestrator | Deep Agents | Main conversation handler, task planning, delegation |
| Project Analyzer | Subagent | Scans projects, identifies services and tech stacks |
| Deploy Agent | Subagent | Executes deployments using platform skills |
| Monitor Agent | Subagent | Background monitoring and log analysis |

### Skills Layer

Skills are modular capabilities that agents can use. See [03-skills.md](./03-skills.md) for details.

| Type | Format | Use Case |
|------|--------|----------|
| Built-in | Python + SKILL.md | Core platforms (Vercel, Railway, Render) |
| Community | SKILL.md or Python | User-contributed platforms |

### Memory Layer

Persistent storage for agent context and project knowledge. See [08-memory.md](./08-memory.md) for details.

| Store | Technology | Purpose |
|-------|------------|---------|
| LangGraph Store | SQLite | Conversation history, agent state, todos |
| Project Knowledge | SQLite/Neo4j | Project analysis, services, deployments |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| LLM Router | Route to OpenAI, Anthropic, or Google based on config |
| Config Store | User preferences, API keys (encrypted) |
| Run History | Audit log of all operations |

### Background Layer

| Component | Purpose |
|-----------|---------|
| Monitor Daemon | Persistent process for continuous monitoring |
| Log Watcher | Fetch and analyze logs from deployed services |
| Alert Dispatcher | Send notifications (Slack, email, etc.) |

## Data Flow

### Deployment Flow

```
User Message → Orchestrator → Project Analyzer → Deploy Agent → Platform API
      ↑              │                │                │              │
      │              ▼                ▼                ▼              │
      └──────── Response ◄──── Memory Update ◄─── Skill Execution ◄──┘
```

### Monitoring Flow

```
Daemon (interval) → Monitor Agent → Log Fetch → Analysis → Alert (if needed)
        │                                          │
        └─────────────── Memory Update ◄───────────┘
```

## Directory Structure

```
~/.openops/                    # Global config directory
├── config.yaml                # User configuration
├── credentials.enc            # Encrypted API keys
├── memory.db                  # SQLite for agent memory
└── projects.db                # SQLite for project knowledge

<project>/.openops/            # Project-specific config (optional)
├── project.yaml               # Project overrides
└── skills/                    # Project-specific skills
```

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | >= 3.11 |
| Agent Framework | Deep Agents (LangChain/LangGraph) | >= 1.0 |
| CLI | Typer | >= 0.9 |
| TUI | Rich / Textual | latest |
| Database | SQLite (default), Neo4j (optional) | - |
| HTTP Client | httpx | >= 0.24 |

## Security Considerations

1. **Credential Storage**: API keys stored encrypted in `~/.openops/credentials.enc`
2. **Approval Workflows**: Destructive operations require user confirmation
3. **Sandboxing**: File operations limited to project directories
4. **Audit Logging**: All operations logged for traceability

## Next Steps

- [02-agents.md](./02-agents.md) - Agent design and configuration
- [03-skills.md](./03-skills.md) - Skill system architecture
- [04-cli-and-tui.md](./04-cli-and-tui.md) - CLI and TUI design
