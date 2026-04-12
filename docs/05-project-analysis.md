# Project Analysis

## Overview

The Project Analyzer subagent scans user projects to understand their structure, identify services, detect technology stacks, and determine what's needed for deployment. The analysis is **shallow but purposeful** - only extracting information relevant to DevOps tasks.

## Analysis Goals

1. **Identify Services** - What components make up this project?
2. **Detect Tech Stack** - What frameworks, languages, databases are used?
3. **Find Existing Configs** - What deployment configs already exist?
4. **Identify Missing Pieces** - What's needed to deploy?
5. **Map Dependencies** - How do services connect to each other?
6. **Extract Environment Vars** - What configuration is required?

## Detection Strategy

### Phase 1: Root-Level Scan

Quick scan of root directory for key indicators:

```python
ROOT_INDICATORS = {
    # Monorepo indicators
    "pnpm-workspace.yaml": "pnpm_monorepo",
    "lerna.json": "lerna_monorepo",
    "nx.json": "nx_monorepo",
    "turbo.json": "turborepo",
    
    # Single project indicators
    "package.json": "node_project",
    "pyproject.toml": "python_project",
    "Cargo.toml": "rust_project",
    "go.mod": "go_project",
    "pom.xml": "java_maven",
    "build.gradle": "java_gradle",
    
    # Deployment configs (already exists)
    "Dockerfile": "has_docker",
    "docker-compose.yml": "has_compose",
    "vercel.json": "has_vercel",
    "railway.toml": "has_railway",
    "render.yaml": "has_render",
    ".github/workflows": "has_ci",
}
```

### Phase 2: Framework Detection

Deep inspection based on Phase 1 findings:

```python
FRAMEWORK_DETECTION = {
    "node_project": {
        "next.config.js": ("nextjs", "frontend"),
        "next.config.mjs": ("nextjs", "frontend"),
        "nuxt.config.ts": ("nuxt", "frontend"),
        "vite.config.ts": ("vite", "frontend"),
        "angular.json": ("angular", "frontend"),
        "svelte.config.js": ("sveltekit", "frontend"),
        "remix.config.js": ("remix", "fullstack"),
        "nest-cli.json": ("nestjs", "backend"),
        "express": ("express", "backend"),  # Check package.json deps
    },
    "python_project": {
        "manage.py": ("django", "backend"),
        "app.py": ("flask_or_fastapi", "backend"),  # Need deeper check
        "fastapi": ("fastapi", "backend"),  # Check pyproject.toml deps
        "streamlit": ("streamlit", "frontend"),
    },
}
```

### Phase 3: Service Mapping

For each detected service, gather:

```python
@dataclass
class ServiceInfo:
    name: str
    path: str  # Relative path from project root
    type: str  # "frontend", "backend", "worker", "database"
    framework: str
    language: str
    version: str | None
    entry_point: str | None  # Main file or command
    build_command: str | None
    start_command: str | None
    port: int | None
    env_vars: list[str]  # Required environment variables
    dependencies: list[str]  # Other services it depends on
```

## Monorepo Handling

### Detection

```python
def is_monorepo(project_path: str) -> bool:
    """Check if project is a monorepo."""
    monorepo_markers = [
        "pnpm-workspace.yaml",
        "lerna.json", 
        "nx.json",
        "turbo.json",
        "packages/",
        "apps/",
    ]
    return any(
        (Path(project_path) / marker).exists() 
        for marker in monorepo_markers
    )
```

### Service Discovery

```python
def discover_services(project_path: str) -> list[ServiceInfo]:
    """Discover all services in a monorepo."""
    services = []
    
    # Check common monorepo structures
    service_dirs = [
        "apps/*",
        "packages/*", 
        "services/*",
        "frontend",
        "backend",
        "api",
        "web",
        "worker",
    ]
    
    for pattern in service_dirs:
        for path in Path(project_path).glob(pattern):
            if path.is_dir():
                service = analyze_service(path)
                if service:
                    services.append(service)
    
    return services
```

## Database Detection

```python
DATABASE_INDICATORS = {
    # ORM/Migration tools
    "prisma/schema.prisma": {"type": "prisma", "db": "from_schema"},
    "drizzle.config.ts": {"type": "drizzle", "db": "from_config"},
    "alembic/": {"type": "sqlalchemy", "db": "from_env"},
    "migrations/": {"type": "generic_migration"},
    
    # Direct database clients
    "pg": "postgresql",  # package.json dep
    "mysql2": "mysql",
    "mongodb": "mongodb",
    "redis": "redis",
    "psycopg2": "postgresql",  # pyproject.toml dep
    "pymongo": "mongodb",
}
```

## Environment Variable Extraction

```python
def extract_env_vars(project_path: str) -> list[dict]:
    """Extract required environment variables."""
    env_vars = []
    
    # Check .env.example, .env.sample, .env.template
    for env_file in [".env.example", ".env.sample", ".env.template"]:
        path = Path(project_path) / env_file
        if path.exists():
            env_vars.extend(parse_env_file(path))
    
    # Check for env usage in code
    # This is a shallow check - just looking for common patterns
    patterns = [
        r"process\.env\.(\w+)",  # JavaScript
        r"os\.environ\[(['\"])(\w+)\1\]",  # Python
        r"os\.getenv\(['\"](\w+)['\"]",  # Python
        r"env::var\(['\"](\w+)['\"]",  # Rust
    ]
    
    # Scan entry point files only (shallow)
    entry_points = ["app.py", "main.py", "index.ts", "server.ts"]
    for entry in entry_points:
        # Extract env var names
        pass
    
    return env_vars
```

## Analysis Output

### Project Summary

```python
@dataclass  
class ProjectAnalysis:
    path: str
    name: str
    description: str  # AI-generated summary
    is_monorepo: bool
    services: list[ServiceInfo]
    databases: list[str]
    existing_configs: list[str]
    missing_configs: list[str]
    env_vars: list[dict]
    keypoints: list[str]  # Key observations
    analyzed_at: datetime
```

### Example Output

```json
{
  "path": "/Users/dev/my-saas",
  "name": "my-saas",
  "description": "A SaaS application with Next.js frontend and FastAPI backend, using PostgreSQL via Prisma",
  "is_monorepo": true,
  "services": [
    {
      "name": "web",
      "path": "apps/web",
      "type": "frontend",
      "framework": "nextjs",
      "language": "typescript",
      "version": "14.0.0",
      "build_command": "npm run build",
      "start_command": "npm start",
      "port": 3000,
      "env_vars": ["NEXT_PUBLIC_API_URL"],
      "dependencies": ["api"]
    },
    {
      "name": "api",
      "path": "apps/api",
      "type": "backend",
      "framework": "fastapi",
      "language": "python",
      "version": "0.104.0",
      "build_command": null,
      "start_command": "uvicorn main:app --host 0.0.0.0 --port 8000",
      "port": 8000,
      "env_vars": ["DATABASE_URL", "JWT_SECRET", "REDIS_URL"],
      "dependencies": []
    }
  ],
  "databases": ["postgresql", "redis"],
  "existing_configs": ["docker-compose.yml", ".github/workflows/ci.yml"],
  "missing_configs": ["vercel.json", "railway.toml"],
  "env_vars": [
    {"name": "DATABASE_URL", "required": true, "default": null},
    {"name": "JWT_SECRET", "required": true, "default": null},
    {"name": "REDIS_URL", "required": true, "default": null},
    {"name": "NEXT_PUBLIC_API_URL", "required": true, "default": null}
  ],
  "keypoints": [
    "Turborepo monorepo with 2 services",
    "Frontend (Next.js 14) depends on backend API",
    "Backend uses PostgreSQL via Prisma ORM",
    "Redis used for caching/sessions",
    "Has CI workflow but no CD configuration",
    "Missing platform deployment configs"
  ],
  "analyzed_at": "2026-04-11T10:30:00Z"
}
```

## Caching Analysis

Analysis results are cached to avoid re-scanning:

```python
def get_or_analyze_project(project_path: str) -> ProjectAnalysis:
    """Get cached analysis or run new analysis."""
    cache_key = get_cache_key(project_path)
    
    # Check if cached and still valid
    cached = memory_store.get(cache_key)
    if cached and is_cache_valid(cached, project_path):
        return cached
    
    # Run fresh analysis
    analysis = analyze_project(project_path)
    
    # Cache result
    memory_store.set(cache_key, analysis)
    
    return analysis

def is_cache_valid(cached: ProjectAnalysis, project_path: str) -> bool:
    """Check if cached analysis is still valid."""
    # Simple: check if any key files changed
    key_files = ["package.json", "pyproject.toml", "Cargo.toml"]
    for f in key_files:
        path = Path(project_path) / f
        if path.exists():
            if path.stat().st_mtime > cached.analyzed_at.timestamp():
                return False
    return True
```

## Integration with Memory

Analysis results are stored in the Project Knowledge Graph:

```python
async def save_analysis_to_memory(analysis: ProjectAnalysis):
    """Save analysis to project knowledge store."""
    project_store.upsert_project(
        path=analysis.path,
        name=analysis.name,
        description=analysis.description,
        keypoints=analysis.keypoints,
    )
    
    for service in analysis.services:
        project_store.upsert_service(
            project_path=analysis.path,
            name=service.name,
            **service.__dict__,
        )
```

## Agent Integration

The Project Analyzer subagent uses these tools:

```python
@tool
def analyze_project(project_path: str) -> ProjectAnalysis:
    """Analyze a project's structure for deployment.
    
    Args:
        project_path: Path to the project root
        
    Returns:
        Comprehensive project analysis
    """
    pass

@tool
def detect_framework(directory: str) -> dict:
    """Detect the framework used in a directory.
    
    Args:
        directory: Path to check
        
    Returns:
        Framework info with confidence score
    """
    pass

@tool  
def find_missing_configs(
    project_path: str,
    target_platform: str,
) -> list[str]:
    """Find missing configuration files for a platform.
    
    Args:
        project_path: Path to project
        target_platform: Target deployment platform
        
    Returns:
        List of missing config files
    """
    pass
```

## Next Steps

- [06-deployment-flow.md](./06-deployment-flow.md) - How analysis feeds into deployment
- [08-memory.md](./08-memory.md) - How analysis is stored
