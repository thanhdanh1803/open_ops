# Agent Design

## Overview

OpenOps uses the **Deep Agents** framework built on LangChain/LangGraph. This provides:

- **TodoListMiddleware**: Task planning and tracking
- **FilesystemMiddleware**: Project file operations
- **SubAgentMiddleware**: Specialized agent delegation
- **SkillsMiddleware**: On-demand skill loading
- **MemoryMiddleware**: Persistent memory across sessions
- **HumanInTheLoopMiddleware**: Approval for sensitive operations

## Agent Hierarchy

```
┌──────────────────────────────────────────────────────────────────┐
│                      Orchestrator Agent                          │
│  - Main conversation handler                                     │
│  - Task planning (write_todos)                                   │
│  - Delegates to specialized subagents                            │
└──────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Project Analyzer │ │   Deploy Agent   │ │  Monitor Agent   │
│                  │ │                  │ │                  │
│ - Scan structure │ │ - Platform skills│ │ - Log fetching   │
│ - Detect stack   │ │ - Config gen     │ │ - Error analysis │
│ - Find services  │ │ - API calls      │ │ - Alerting       │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

## Agent Specifications

### Orchestrator Agent

The main agent that handles all user interactions.

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

orchestrator = create_deep_agent(
    name="openops-orchestrator",
    model="anthropic:claude-sonnet-4-5",  # or user's configured model
    system_prompt=ORCHESTRATOR_PROMPT,
    tools=[
        # Custom tools beyond built-in filesystem/todos
        query_project_knowledge,
        save_project_knowledge,
    ],
    subagents=[
        project_analyzer,
        deploy_agent,
        monitor_agent,
    ],
    backend=FilesystemBackend(root_dir=".", virtual_mode=False),
    skills=["~/.openops/skills/", "./skills/"],
    checkpointer=MemorySaver(),
    store=InMemoryStore(),  # or SqliteStore for persistence
    interrupt_on={
        "deploy": True,      # Require approval for deployments
        "write_file": False, # Allow file writes without approval
    },
)
```

**System Prompt (condensed)**:
```
You are OpenOps, a DevOps assistant that helps developers deploy and monitor
their applications.

Your capabilities:
1. Analyze project structure to understand services and tech stacks
2. Generate missing deployment configurations (Dockerfile, vercel.json, etc.)
3. Deploy to platforms (Vercel, Railway, Render, etc.)
4. Monitor deployed services and analyze logs

Always:
- Explain what you're about to do before doing it
- Ask for confirmation before deployments
- Save analysis results to project knowledge for future reference
- Be concise but thorough in explanations
```

### Project Analyzer Subagent

Specialized for understanding project structure.

```python
project_analyzer = {
    "name": "project-analyzer",
    "model": "anthropic:claude-sonnet-4-5",
    "system_prompt": """You analyze project structures for deployment.

Your task is to:
1. Identify all services in the project (frontend, backend, workers, etc.)
2. Detect technology stacks (frameworks, languages, databases)
3. Find existing deployment configs (Dockerfile, docker-compose, etc.)
4. Identify missing configurations needed for deployment
5. Note environment variables required
6. Document dependencies between services

Output your findings as structured keypoints that will be saved to memory.
""",
    "tools": [
        # Inherits filesystem tools from Deep Agents
        detect_framework,  # Custom tool for framework detection
        parse_package_json,
        parse_requirements_txt,
        parse_pyproject_toml,
    ],
}
```

### Deploy Agent Subagent

Handles deployment to specific platforms.

```python
deploy_agent = {
    "name": "deploy-agent",
    "model": "anthropic:claude-sonnet-4-5",
    "system_prompt": """You handle deployments to cloud platforms.

Your task is to:
1. Generate any missing configuration files
2. Validate configurations before deployment
3. Execute deployment via platform APIs
4. Report deployment status and URLs
5. Handle errors and suggest fixes

Always validate that required credentials are available before attempting deployment.
""",
    "skills": [
        "~/.openops/skills/vercel/",
        "~/.openops/skills/railway/",
        "~/.openops/skills/render/",
    ],
    "tools": [
        # Platform-specific tools loaded from skills
    ],
}
```

### Monitor Agent Subagent

Background monitoring and log analysis.

```python
monitor_agent = {
    "name": "monitor-agent",
    "model": "anthropic:claude-sonnet-4-5",  # Can use faster model for monitoring
    "system_prompt": """You monitor deployed services.

Your task is to:
1. Fetch logs from deployed services
2. Analyze logs for errors and warnings
3. Identify patterns that indicate issues
4. Generate alerts for critical problems
5. Suggest fixes when errors are detected

Prioritize actionable insights over raw data.
""",
    "tools": [
        fetch_vercel_logs,
        fetch_railway_logs,
        fetch_render_logs,
        analyze_error_trace,
        dispatch_alert,
    ],
}
```

## Tool Definitions

### Built-in Tools (from Deep Agents)

These are automatically available:

| Tool | Description |
|------|-------------|
| `write_todos` | Plan and track multi-step tasks |
| `task` | Delegate work to subagents |
| `ls` | List directory contents |
| `read_file` | Read file contents |
| `write_file` | Write/create files |
| `edit_file` | Edit existing files |
| `glob` | Find files by pattern |
| `grep` | Search file contents |

### Custom Tools

```python
from langchain_core.tools import tool

@tool
def query_project_knowledge(project_path: str) -> dict:
    """Query stored knowledge about a project.

    Args:
        project_path: Absolute path to the project

    Returns:
        Project analysis including services, tech stack, and deployment history
    """
    # Implementation in memory layer
    pass

@tool
def save_project_knowledge(
    project_path: str,
    description: str,
    keypoints: list[str],
    services: list[dict],
) -> bool:
    """Save project analysis to knowledge store.

    Args:
        project_path: Absolute path to the project
        description: What this project does
        keypoints: Key observations from analysis
        services: List of services with their details

    Returns:
        True if saved successfully
    """
    pass

@tool
def detect_framework(directory: str) -> dict:
    """Detect the framework/technology used in a directory.

    Args:
        directory: Path to check

    Returns:
        Detected framework info including name, version, and confidence
    """
    pass
```

## Agent Communication

### Delegation Pattern

```python
# Orchestrator delegates to Project Analyzer
result = orchestrator.invoke({
    "messages": [{
        "role": "user",
        "content": "Analyze the project at /path/to/project"
    }]
}, config={"configurable": {"thread_id": "session-123"}})

# Internally, orchestrator uses the `task` tool:
# task(agent="project-analyzer", prompt="Analyze /path/to/project structure")
```

### State Sharing

Subagents share state through:

1. **Thread ID**: Same conversation thread
2. **Memory Store**: Shared persistent storage
3. **Tool Results**: Returned to orchestrator for context

## Human-in-the-Loop

Sensitive operations require approval:

```python
# Configure in orchestrator
interrupt_on={
    "deploy": True,           # Always approve deployments
    "write_file": ["*.env"],  # Approve .env file writes
    "delete_file": True,      # Always approve deletions
}

# In CLI, user sees:
# > OpenOps wants to deploy to Vercel. Approve? [y/n]
```

## Model Configuration

Users can configure their preferred LLM:

```yaml
# ~/.openops/config.yaml
model:
  provider: anthropic  # openai, anthropic, google
  name: claude-sonnet-4-5
  temperature: 0.1

# Or via environment
OPENOPS_MODEL=openai:gpt-4o
```

The LLM router translates to LangChain model strings:
- `anthropic:claude-sonnet-4-5` → `ChatAnthropic(model="claude-sonnet-4-5")`
- `openai:gpt-4o` → `ChatOpenAI(model="gpt-4o")`
- `google:gemini-pro` → `ChatGoogleGenerativeAI(model="gemini-pro")`

## Error Handling

```python
from deepagents.errors import AgentError, ToolError

try:
    result = orchestrator.invoke(...)
except ToolError as e:
    # Tool execution failed
    logger.error(f"Tool {e.tool_name} failed: {e.message}")
    # Agent will retry or ask user for help
except AgentError as e:
    # Agent loop failed
    logger.error(f"Agent error: {e}")
    # Fall back to safe state
```

## Next Steps

- [03-skills.md](./03-skills.md) - How skills extend agent capabilities
- [08-memory.md](./08-memory.md) - Memory architecture for persistence
