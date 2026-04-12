# Implementation Plan

## Overview

This document outlines the implementation plan for OpenOps Phase 1 (MVP). The plan is designed to enable parallel development across a team by establishing shared interfaces first, then allowing independent work on 5 separate tracks.

## Current State

- `src/` directory is empty - clean slate
- Documentation exists defining architecture, agents, skills, memory
- `pyproject.toml` has basic dependencies configured

---

## Phase 0: Foundation (Must Complete First)

**Purpose**: Establish shared contracts/interfaces that enable parallel development.

**Important**: This phase must complete before parallel tracks begin. All team members should review and agree on these interfaces.

### 0.1 Package Structure

```
src/openops/
├── __init__.py
├── models.py          # Shared data models
├── config.py          # Configuration loading
├── exceptions.py      # Custom exceptions
├── skills/
│   ├── __init__.py
│   └── base.py        # BaseSkill, SkillResult
├── storage/
│   ├── __init__.py
│   └── base.py        # Abstract store interfaces
├── agent/
│   └── __init__.py
└── cli/
    └── __init__.py
```

### 0.2 Shared Data Models

**File**: `src/openops/models.py`

| Model | Purpose |
|-------|---------|
| `RiskLevel` | Enum: read, write, destructive |
| `Project` | Project metadata and analysis results |
| `Service` | Service within a project (frontend, backend, etc.) |
| `Deployment` | Deployment record with URL and status |
| `SkillResult` | Standard result type for skill operations |

Reference: [08-memory.md](./08-memory.md) for full model definitions.

### 0.3 Base Skill Interface

**File**: `src/openops/skills/base.py`

```python
class BaseSkill(ABC):
    name: str
    description: str
    risk_level: RiskLevel
    
    @abstractmethod
    def get_tools(self) -> list:
        """Return LangChain tools provided by this skill."""
        pass
    
    def validate_credentials(self) -> bool:
        """Check if required credentials are available."""
        return True
```

Reference: [03-skills.md](./03-skills.md) for full skill architecture.

### 0.4 Storage Interfaces

**File**: `src/openops/storage/base.py`

```python
class ProjectStoreBase(ABC):
    @abstractmethod
    def upsert_project(self, project: Project) -> None: ...
    
    @abstractmethod
    def get_project(self, path: str) -> Project | None: ...
    
    @abstractmethod
    def upsert_service(self, service: Service) -> None: ...
    
    @abstractmethod
    def get_services_for_project(self, project_id: str) -> list[Service]: ...
    
    @abstractmethod
    def add_deployment(self, deployment: Deployment) -> None: ...
```

Reference: [08-memory.md](./08-memory.md) for storage architecture.

### 0.5 Configuration

**File**: `src/openops/config.py`

Uses `pydantic-settings` for environment-based configuration:

| Setting | Env Var | Default |
|---------|---------|---------|
| `model_provider` | `OPENOPS_MODEL_PROVIDER` | `anthropic` |
| `model_name` | `OPENOPS_MODEL_NAME` | `claude-sonnet-4-5` |
| `vercel_token` | `OPENOPS_VERCEL_TOKEN` | None |
| `railway_token` | `OPENOPS_RAILWAY_TOKEN` | None |
| `render_api_key` | `OPENOPS_RENDER_API_KEY` | None |
| `data_dir` | `OPENOPS_DATA_DIR` | `~/.openops` |

Reference: [09-configuration.md](./09-configuration.md) for full config options.

### 0.6 Phase 0 Checklist

- [ ] Create package structure with `__init__.py` files
- [ ] Define all Pydantic models in `models.py`
- [ ] Define `BaseSkill` and `SkillResult` in `skills/base.py`
- [ ] Define `ProjectStoreBase` interface in `storage/base.py`
- [ ] Define `OpenOpsConfig` in `config.py`
- [ ] Create `exceptions.py` with custom exceptions
- [ ] Set up pytest configuration
- [ ] Team review and sign-off on interfaces

---

## Parallel Development Tracks

Once Phase 0 is complete, these 5 tracks can be developed **simultaneously** by different team members.

```
                    ┌─────────────────────┐
                    │  Phase 0: Foundation │
                    └──────────┬──────────┘
                               │
       ┌───────────┬───────────┼───────────┬───────────┐
       ▼           ▼           ▼           ▼           ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Track A    │ │  Track B    │ │  Track C    │ │  Track D    │ │  Track E    │
│  Agent      │ │  Memory     │ │  Skills     │ │  CLI/TUI    │ │  Analysis   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │               │               │
       └───────────────┴───────────────┴───────┬───────┴───────────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │    Integration      │
                                    └─────────────────────┘
```

---

## Track A: Agent/Orchestrator

**Owner**: 1 developer  
**Dependencies**: Phase 0 models, base classes  
**Reference**: [02-agents.md](./02-agents.md)

### Files to Create

| File | Purpose |
|------|---------|
| `agent/orchestrator.py` | Main Deep Agent with middleware |
| `agent/subagents.py` | Project Analyzer, Deploy Agent, Monitor Agent configs |
| `agent/prompts.py` | System prompts for all agents |
| `agent/tools.py` | Custom tools (query_project_knowledge, save_project_knowledge) |

### Key Implementation

- Use `create_deep_agent()` from Deep Agents framework
- Configure middleware: TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware
- Define 3 subagents: project-analyzer, deploy-agent, monitor-agent
- Implement custom tools for project knowledge operations

### Testing Strategy

- Mock stores and skills to test agent logic independently
- Test subagent delegation
- Test human-in-the-loop approval flow

---

## Track B: Memory/Storage

**Owner**: 1 developer  
**Dependencies**: Phase 0 storage interfaces, models  
**Reference**: [08-memory.md](./08-memory.md)

### Files to Create

| File | Purpose |
|------|---------|
| `storage/sqlite_store.py` | SQLite implementation of ProjectStore |
| `storage/schema.sql` | Database schema |
| `storage/checkpointer.py` | SqliteSaver wrapper for LangGraph |

### Key Implementation

- Implement `SqliteProjectStore` following the interface
- Create schema with tables: projects, services, deployments, service_dependencies
- Wrap LangGraph's `SqliteSaver` for checkpointing

### Database Schema

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    keypoints TEXT,  -- JSON array
    analyzed_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE services (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    type TEXT,
    framework TEXT,
    language TEXT,
    -- ... see 08-memory.md for full schema
);

CREATE TABLE deployments (
    id TEXT PRIMARY KEY,
    service_id TEXT REFERENCES services(id),
    platform TEXT NOT NULL,
    url TEXT,
    status TEXT DEFAULT 'active',
    deployed_at DATETIME
);
```

### Testing Strategy

- Unit tests with in-memory SQLite (`:memory:`)
- Test CRUD operations for each entity
- Test query helpers

---

## Track C: Deployment Skills

**Owner**: 1-2 developers (can split by platform)  
**Dependencies**: Phase 0 BaseSkill, SkillResult  
**Reference**: [03-skills.md](./03-skills.md)

### Files to Create

| Directory | Files |
|-----------|-------|
| `skills/vercel/` | `skill.py`, `SKILL.md` |
| `skills/railway/` | `skill.py`, `SKILL.md` |
| `skills/render/` | `skill.py`, `SKILL.md` |

### Skills to Implement

| Skill | Tools | API Base |
|-------|-------|----------|
| VercelSkill | `vercel_deploy`, `vercel_list_projects`, `vercel_get_deployments` | `https://api.vercel.com` |
| RailwaySkill | `railway_deploy`, `railway_list_services` | `https://backboard.railway.app/graphql/v2` |
| RenderSkill | `render_deploy`, `render_list_services` | `https://api.render.com/v1` |

### Key Implementation

- Each skill extends `BaseSkill`
- Each skill provides LangChain tools via `get_tools()`
- Use `httpx` for API calls
- Return `SkillResult` with success/failure info

### Testing Strategy

- Mock HTTP responses with `respx` or `httpx.MockTransport`
- Test credential validation
- Test error handling

---

## Track D: CLI/TUI

**Owner**: 1 developer  
**Dependencies**: Phase 0 config only (can use stub agent initially)  
**Reference**: [04-cli-and-tui.md](./04-cli-and-tui.md)

### Files to Create

| File | Purpose |
|------|---------|
| `cli/main.py` | Typer app, command routing |
| `cli/chat.py` | Interactive chat command with Rich |
| `cli/init.py` | Project initialization wizard |
| `cli/deploy.py` | One-shot deploy command |
| `cli/tui/app.py` | Textual TUI (optional enhancement) |

### Commands to Implement

| Command | Purpose |
|---------|---------|
| `openops chat` | Interactive conversation with agent |
| `openops init` | Initialize OpenOps in current directory |
| `openops deploy` | One-shot deployment |
| `openops monitor` | Start/check monitoring |

### Key Implementation

- Use `typer` for CLI framework
- Use `rich` for console output and prompts
- Create stub runtime interface for testing without real agent

### Testing Strategy

- Test CLI commands with mock runtime
- Test prompt flows
- Test output formatting

---

## Track E: Project Analysis

**Owner**: 1 developer  
**Dependencies**: Phase 0 models (Service, Project)  
**Reference**: [05-project-analysis.md](./05-project-analysis.md)

### Files to Create

| File | Purpose |
|------|---------|
| `analysis/detector.py` | Framework detection logic |
| `analysis/env_extractor.py` | Environment variable discovery |
| `analysis/analyzer.py` | Main ProjectAnalyzer class |

### Framework Detection Signals

| File/Pattern | Framework | Language |
|--------------|-----------|----------|
| `next.config.js`, `next.config.mjs` | Next.js | JavaScript/TypeScript |
| `package.json` with `"next"` dep | Next.js | JavaScript/TypeScript |
| `pyproject.toml` with `fastapi` | FastAPI | Python |
| `requirements.txt` with `django` | Django | Python |
| `vite.config.js`, `vite.config.ts` | Vite | JavaScript/TypeScript |
| `Cargo.toml` | Rust | Rust |
| `go.mod` | Go | Go |

### Key Implementation

- `detect_framework(directory)` - returns framework info
- `extract_env_vars(directory)` - finds required env vars from code
- `analyze_project(path)` - returns full Project and Service list

### Testing Strategy

- Create fixture projects in `tests/fixtures/`
- Test each framework detection independently
- Test env var extraction patterns

---

## Integration Phase

After parallel tracks complete, bring them together.

### Integration Tasks

| Task | Description |
|------|-------------|
| Wire Agent to Skills | Register skills in orchestrator |
| Wire Agent to Storage | Connect SqliteProjectStore to agent tools |
| Wire CLI to Agent | Create runtime that CLI commands use |
| Wire Analysis to Agent | Make ProjectAnalyzer available as subagent tool |
| End-to-End Testing | Test full flow with mock project |

### Integration File

**File**: `src/openops/app.py`

```python
def create_runtime(config: OpenOpsConfig) -> OpenOpsRuntime:
    """Create fully wired OpenOps runtime."""
    # Storage
    store = SqliteProjectStore(config.data_dir / "projects.db")
    checkpointer = SqliteSaver(config.data_dir / "checkpoints.db")
    
    # Skills
    skills = [
        VercelSkill(token=config.vercel_token),
        RailwaySkill(token=config.railway_token),
        RenderSkill(api_key=config.render_api_key),
    ]
    
    # Agent
    orchestrator = create_orchestrator(config, store, checkpointer, skills)
    
    return OpenOpsRuntime(orchestrator, store, config)
```

---

## Team Assignment Summary

| Track | Focus | Owner | Can Start After |
|-------|-------|-------|-----------------|
| Phase 0 | Interfaces, models | Lead / All | - |
| Track A | Agent/Orchestrator | Dev 1 | Phase 0 |
| Track B | Memory/Storage | Dev 2 | Phase 0 |
| Track C | Skills | Dev 3 (+ Dev 4) | Phase 0 |
| Track D | CLI/TUI | Dev 4 | Phase 0 |
| Track E | Project Analysis | Dev 5 | Phase 0 |
| Integration | Wire everything | Lead | All tracks |

---

## Testing Strategy by Track

| Track | Test Type | Tools |
|-------|-----------|-------|
| Track A | Unit + Mock | pytest, unittest.mock |
| Track B | Unit + SQLite | pytest, in-memory SQLite |
| Track C | Unit + HTTP Mock | pytest, respx/httpx mock |
| Track D | CLI Tests | pytest, typer.testing |
| Track E | Fixture Projects | pytest, temp directories |
| Integration | E2E | pytest, mock project |

---

## Success Criteria

Phase 1 is complete when:

- [ ] Deploy a Next.js project to Vercel via conversation
- [ ] Agent remembers project context across sessions
- [ ] Config files generated correctly
- [ ] CLI commands work (`chat`, `init`, `deploy`)
- [ ] All tests pass

---

## Next Steps

1. Complete Phase 0 with team review
2. Assign track owners
3. Begin parallel development
4. Daily sync on interface changes
5. Integration sprint after tracks complete
