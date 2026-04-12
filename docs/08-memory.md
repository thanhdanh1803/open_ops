# Memory Architecture

## Overview

OpenOps uses a dual-memory system:

1. **Agent Memory (LangGraph Store)** - Conversation history, todos, agent state
2. **Project Knowledge Graph** - Project analysis, services, deployments

Both support SQLite by default, with optional Neo4j for users who want richer graph queries.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Memory Layer                                    │
│                                                                             │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │       Agent Memory              │  │    Project Knowledge Graph      │  │
│  │       (LangGraph Store)         │  │                                 │  │
│  │                                 │  │                                 │  │
│  │  - Conversation history         │  │  - Projects                     │  │
│  │  - Agent todos/plans            │  │  - Services                     │  │
│  │  - Checkpoint state             │  │  - Deployments                  │  │
│  │  - User preferences             │  │  - Dependencies                 │  │
│  │                                 │  │  - Monitoring configs           │  │
│  └─────────────────────────────────┘  └─────────────────────────────────┘  │
│                 │                                    │                      │
│                 └──────────────┬─────────────────────┘                      │
│                                │                                            │
│                                ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Storage Backend                                 │   │
│  │                                                                      │   │
│  │   Default: SQLite (~/.openops/memory.db, ~/.openops/projects.db)    │   │
│  │   Optional: Neo4j (for complex project graphs)                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Agent Memory (LangGraph Store)

### What's Stored

| Data | Purpose | Retention |
|------|---------|-----------|
| Conversations | Chat history with agent | Per thread_id |
| Todos | Agent's task planning | Per thread_id |
| Checkpoints | Agent state snapshots | Configurable |
| Preferences | User settings learned in conversation | Persistent |

### Implementation

Using Deep Agents with `SqliteStore`:

```python
from langgraph.store.sqlite import SqliteStore
from langgraph.checkpoint.sqlite import SqliteSaver
from deepagents import create_deep_agent

# Initialize stores
store = SqliteStore(Path("~/.openops/memory.db").expanduser())
checkpointer = SqliteSaver(Path("~/.openops/checkpoints.db").expanduser())

# Create agent with memory
orchestrator = create_deep_agent(
    model="anthropic:claude-sonnet-4-5",
    store=store,
    checkpointer=checkpointer,
    # ... other config
)

# Invoke with thread_id for conversation continuity
config = {"configurable": {"thread_id": "session-abc123"}}
result = orchestrator.invoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config=config
)
```

### Memory Operations

```python
# Store remembers across sessions
# Session 1
agent.invoke({"messages": [{"role": "user", "content": "My name is Dan"}]}, config)

# Session 2 (same thread_id)
agent.invoke({"messages": [{"role": "user", "content": "What's my name?"}]}, config)
# Agent remembers: "Your name is Dan"

# Different thread_id = fresh conversation
new_config = {"configurable": {"thread_id": "session-xyz"}}
agent.invoke({"messages": [{"role": "user", "content": "What's my name?"}]}, new_config)
# Agent doesn't know (different thread)
```

## Project Knowledge Graph

### Data Models

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Project:
    """A project being managed by OpenOps."""
    id: str  # UUID
    path: str  # Absolute path
    name: str
    description: str  # AI-generated summary
    keypoints: list[str]  # Key observations
    analyzed_at: datetime
    updated_at: datetime

@dataclass
class Service:
    """A service within a project."""
    id: str
    project_id: str
    name: str
    path: str  # Relative to project
    description: str
    type: str  # "frontend", "backend", "worker", "database"
    framework: str
    language: str
    version: Optional[str]
    entry_point: Optional[str]
    build_command: Optional[str]
    start_command: Optional[str]
    port: Optional[int]
    env_vars: list[str]
    dependencies: list[str]  # Other service IDs
    keypoints: list[str]  # Service-specific observations

@dataclass
class Deployment:
    """A deployment of a service."""
    id: str
    service_id: str
    platform: str  # "vercel", "railway", "render"
    url: str
    dashboard_url: Optional[str]
    deployed_at: datetime
    config: dict  # Platform-specific config
    status: str  # "active", "failed", "superseded"

@dataclass
class MonitoringConfig:
    """Monitoring configuration for a deployment."""
    id: str
    deployment_id: str
    health_check_url: str
    interval_seconds: int
    alert_channels: list[str]
    thresholds: dict
    enabled: bool
```

### SQLite Schema

```sql
-- Projects table
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    keypoints TEXT,  -- JSON array
    analyzed_at DATETIME,
    updated_at DATETIME
);

-- Services table
CREATE TABLE services (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    description TEXT,
    type TEXT,
    framework TEXT,
    language TEXT,
    version TEXT,
    entry_point TEXT,
    build_command TEXT,
    start_command TEXT,
    port INTEGER,
    env_vars TEXT,  -- JSON array
    dependencies TEXT,  -- JSON array of service IDs
    keypoints TEXT  -- JSON array
);

-- Deployments table
CREATE TABLE deployments (
    id TEXT PRIMARY KEY,
    service_id TEXT REFERENCES services(id),
    platform TEXT NOT NULL,
    url TEXT,
    dashboard_url TEXT,
    deployed_at DATETIME,
    config TEXT,  -- JSON object
    status TEXT DEFAULT 'active'
);

-- Service dependencies (for graph queries)
CREATE TABLE service_dependencies (
    service_id TEXT REFERENCES services(id),
    depends_on_id TEXT REFERENCES services(id),
    PRIMARY KEY (service_id, depends_on_id)
);

-- Indexes
CREATE INDEX idx_services_project ON services(project_id);
CREATE INDEX idx_deployments_service ON deployments(service_id);
CREATE INDEX idx_projects_path ON projects(path);
```

### Project Store Implementation

```python
import sqlite3
import json
from pathlib import Path

class ProjectStore:
    def __init__(self, db_path: str = "~/.openops/projects.db"):
        self.db_path = Path(db_path).expanduser()
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        with open(Path(__file__).parent / "schema.sql") as f:
            self.db.executescript(f.read())

    # Project operations
    def upsert_project(self, project: Project) -> None:
        """Insert or update a project."""
        self.db.execute("""
            INSERT INTO projects (id, path, name, description, keypoints, analyzed_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                keypoints = excluded.keypoints,
                analyzed_at = excluded.analyzed_at,
                updated_at = excluded.updated_at
        """, (
            project.id, project.path, project.name, project.description,
            json.dumps(project.keypoints), project.analyzed_at, project.updated_at
        ))
        self.db.commit()

    def get_project(self, path: str) -> Optional[Project]:
        """Get project by path."""
        row = self.db.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()

        if not row:
            return None

        return Project(
            id=row["id"],
            path=row["path"],
            name=row["name"],
            description=row["description"],
            keypoints=json.loads(row["keypoints"] or "[]"),
            analyzed_at=row["analyzed_at"],
            updated_at=row["updated_at"],
        )

    # Service operations
    def upsert_service(self, service: Service) -> None:
        """Insert or update a service."""
        self.db.execute("""
            INSERT INTO services
            (id, project_id, name, path, description, type, framework, language,
             version, entry_point, build_command, start_command, port, env_vars,
             dependencies, keypoints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                type = excluded.type,
                framework = excluded.framework,
                -- ... other fields
        """, (
            service.id, service.project_id, service.name, service.path,
            service.description, service.type, service.framework, service.language,
            service.version, service.entry_point, service.build_command,
            service.start_command, service.port, json.dumps(service.env_vars),
            json.dumps(service.dependencies), json.dumps(service.keypoints)
        ))
        self.db.commit()

    def get_services_for_project(self, project_id: str) -> list[Service]:
        """Get all services for a project."""
        rows = self.db.execute(
            "SELECT * FROM services WHERE project_id = ?", (project_id,)
        ).fetchall()

        return [self._row_to_service(row) for row in rows]

    # Deployment operations
    def add_deployment(self, deployment: Deployment) -> None:
        """Record a new deployment."""
        # Mark previous deployments as superseded
        self.db.execute("""
            UPDATE deployments SET status = 'superseded'
            WHERE service_id = ? AND status = 'active'
        """, (deployment.service_id,))

        self.db.execute("""
            INSERT INTO deployments
            (id, service_id, platform, url, dashboard_url, deployed_at, config, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            deployment.id, deployment.service_id, deployment.platform,
            deployment.url, deployment.dashboard_url, deployment.deployed_at,
            json.dumps(deployment.config), deployment.status
        ))
        self.db.commit()

    def get_active_deployment(self, service_id: str) -> Optional[Deployment]:
        """Get active deployment for a service."""
        row = self.db.execute("""
            SELECT * FROM deployments
            WHERE service_id = ? AND status = 'active'
            ORDER BY deployed_at DESC
            LIMIT 1
        """, (service_id,)).fetchone()

        if not row:
            return None

        return self._row_to_deployment(row)

    # Query helpers
    def get_project_summary(self, path: str) -> dict:
        """Get full project summary with services and deployments."""
        project = self.get_project(path)
        if not project:
            return None

        services = self.get_services_for_project(project.id)

        return {
            "project": project,
            "services": [
                {
                    "service": s,
                    "deployment": self.get_active_deployment(s.id)
                }
                for s in services
            ]
        }
```

## Neo4j Integration (Optional)

For users with complex multi-project setups, Neo4j provides richer graph queries.

### Setup Flow

```python
async def setup_neo4j():
    """Guide user through Neo4j setup."""

    console.print("Neo4j provides powerful graph queries for complex projects.")
    console.print("You can run it locally with Docker.\n")

    if Confirm.ask("Set up Neo4j with Docker?"):
        # Check Docker
        if not docker_available():
            console.print("[red]Docker not found. Install Docker first.[/red]")
            return

        # Run Neo4j container
        console.print("Starting Neo4j container...")
        subprocess.run([
            "docker", "run", "-d",
            "--name", "openops-neo4j",
            "-p", "7474:7474",
            "-p", "7687:7687",
            "-e", "NEO4J_AUTH=neo4j/openops123",
            "neo4j:latest"
        ])

        # Wait for startup
        await wait_for_neo4j()

        # Update config
        config.set("memory.backend", "neo4j")
        config.set("memory.neo4j_uri", "bolt://localhost:7687")
        config.set("memory.neo4j_user", "neo4j")
        config.set("memory.neo4j_password", "openops123")

        console.print("[green]Neo4j is ready![/green]")

        # Migrate existing data
        if Confirm.ask("Migrate existing project data to Neo4j?"):
            await migrate_to_neo4j()
```

### Neo4j Store Implementation

```python
from neo4j import GraphDatabase

class Neo4jProjectStore:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def upsert_project(self, project: Project) -> None:
        """Insert or update a project node."""
        with self.driver.session() as session:
            session.run("""
                MERGE (p:Project {path: $path})
                SET p.id = $id,
                    p.name = $name,
                    p.description = $description,
                    p.keypoints = $keypoints,
                    p.analyzed_at = $analyzed_at,
                    p.updated_at = $updated_at
            """, project.__dict__)

    def upsert_service(self, service: Service) -> None:
        """Insert or update a service node with relationships."""
        with self.driver.session() as session:
            # Create service node
            session.run("""
                MATCH (p:Project {id: $project_id})
                MERGE (s:Service {id: $id})
                SET s.name = $name,
                    s.path = $path,
                    s.type = $type,
                    s.framework = $framework,
                    s.language = $language
                MERGE (p)-[:CONTAINS]->(s)
            """, service.__dict__)

            # Create dependency relationships
            for dep_id in service.dependencies:
                session.run("""
                    MATCH (s:Service {id: $service_id})
                    MATCH (d:Service {id: $dep_id})
                    MERGE (s)-[:DEPENDS_ON]->(d)
                """, {"service_id": service.id, "dep_id": dep_id})

    def get_dependency_graph(self, project_id: str) -> dict:
        """Get full dependency graph for a project."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(s:Service)
                OPTIONAL MATCH (s)-[:DEPENDS_ON]->(d:Service)
                RETURN s, collect(d) as dependencies
            """, {"project_id": project_id})

            return self._build_graph(result)

    def find_affected_services(self, service_id: str) -> list[Service]:
        """Find all services affected by a change to this service."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Service {id: $service_id})<-[:DEPENDS_ON*]-(affected:Service)
                RETURN DISTINCT affected
            """, {"service_id": service_id})

            return [self._node_to_service(r["affected"]) for r in result]
```

## Memory Usage in Agents

### Querying Project Knowledge

```python
@tool
def query_project_knowledge(project_path: str) -> dict:
    """Query stored knowledge about a project.

    Args:
        project_path: Absolute path to the project

    Returns:
        Project summary including services, tech stack, and deployment history
    """
    store = get_project_store()
    summary = store.get_project_summary(project_path)

    if not summary:
        return {"found": False, "message": "Project not analyzed yet"}

    return {
        "found": True,
        "project": {
            "name": summary["project"].name,
            "description": summary["project"].description,
            "keypoints": summary["project"].keypoints,
        },
        "services": [
            {
                "name": s["service"].name,
                "type": s["service"].type,
                "framework": s["service"].framework,
                "deployment": s["deployment"].url if s["deployment"] else None,
            }
            for s in summary["services"]
        ]
    }

@tool
def save_project_analysis(
    project_path: str,
    description: str,
    keypoints: list[str],
    services: list[dict],
) -> bool:
    """Save project analysis results to knowledge store.

    Args:
        project_path: Absolute path to the project
        description: What this project does
        keypoints: Key observations from analysis
        services: List of services with their details

    Returns:
        True if saved successfully
    """
    store = get_project_store()

    # Create or update project
    project = Project(
        id=str(uuid.uuid4()),
        path=project_path,
        name=Path(project_path).name,
        description=description,
        keypoints=keypoints,
        analyzed_at=datetime.now(),
        updated_at=datetime.now(),
    )
    store.upsert_project(project)

    # Create services
    for s in services:
        service = Service(
            id=str(uuid.uuid4()),
            project_id=project.id,
            **s
        )
        store.upsert_service(service)

    return True
```

## Configuration

```yaml
# ~/.openops/config.yaml
memory:
  # Agent memory (LangGraph Store)
  agent_store: sqlite  # only sqlite supported
  agent_store_path: ~/.openops/memory.db

  # Project knowledge
  project_store: sqlite  # sqlite or neo4j
  project_store_path: ~/.openops/projects.db

  # Neo4j settings (if project_store: neo4j)
  neo4j_uri: bolt://localhost:7687
  neo4j_user: neo4j
  neo4j_password: ${OPENOPS_NEO4J_PASSWORD}

  # Retention
  conversation_retention_days: 30
  checkpoint_retention_days: 7
```

## Next Steps

- [09-configuration.md](./09-configuration.md) - Full configuration reference
- [07-monitoring.md](./07-monitoring.md) - How monitoring uses memory
