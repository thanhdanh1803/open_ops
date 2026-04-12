# Skills System

## Overview

Skills are modular capabilities that extend OpenOps agents. They provide platform-specific knowledge and tools for deployment and monitoring.

## Two-Tier Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Tier 1: SKILL.md                           │
│  - Declarative instructions for agents                          │
│  - Platform documentation and API details                       │
│  - Community can contribute without Python                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Tier 2: Python Classes                        │
│  - Complex deployment logic                                     │
│  - API integrations with error handling                         │
│  - Multi-step workflows                                         │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
skills/
├── vercel/
│   ├── SKILL.md              # Agent instructions (required)
│   ├── vercel_skill.py       # Python implementation (optional)
│   └── templates/            # Config templates (optional)
│       └── vercel.json.j2
├── railway/
│   ├── SKILL.md
│   ├── railway_skill.py
│   └── templates/
│       └── railway.toml.j2
├── render/
│   ├── SKILL.md
│   ├── render_skill.py
│   └── templates/
│       └── render.yaml.j2
└── observability/
    ├── SKILL.md
    └── observability_skill.py
```

## SKILL.md Format

Skills use YAML frontmatter for metadata and markdown for agent instructions.

### Required Format

```markdown
---
name: vercel-deploy
description: Deploy frontend applications to Vercel
version: 1.0.0
author: OpenOps Team
risk_level: write  # read, write, destructive
platforms:
  - vercel
requires:
  credentials:
    - VERCEL_TOKEN
  tools:
    - vercel_deploy
    - vercel_list_projects
---

# Vercel Deployment Skill

## When to Use

Use this skill when:
- User wants to deploy a frontend application
- Project is built with Next.js, React, Vue, or static HTML
- User mentions Vercel as the target platform

## Prerequisites

1. User must have a Vercel account
2. VERCEL_TOKEN must be configured in OpenOps
3. Project should have a valid package.json (for Node.js projects)

## Deployment Steps

### 1. Check for Existing Configuration

Look for `vercel.json` in the project root. If it exists, validate it.
If not, generate one based on the detected framework.

### 2. Framework Detection

| Framework | Build Command | Output Directory |
|-----------|---------------|------------------|
| Next.js | `next build` | `.next` |
| Create React App | `npm run build` | `build` |
| Vue CLI | `npm run build` | `dist` |
| Vite | `npm run build` | `dist` |

### 3. Generate vercel.json

```json
{
  "version": 2,
  "builds": [
    { "src": "package.json", "use": "@vercel/next" }
  ]
}
```

### 4. Deploy

Use the `vercel_deploy` tool with:
- `project_path`: Path to the project
- `project_name`: Name for the Vercel project
- `production`: Whether to deploy to production (default: false)

### 5. Report Results

After deployment, report:
- Deployment URL
- Dashboard URL
- Any warnings from the build

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `INVALID_TOKEN` | Bad Vercel token | Ask user to run `openops config set VERCEL_TOKEN <token>` |
| `BUILD_FAILED` | Build error | Show build logs and suggest fixes |
| `RATE_LIMITED` | Too many requests | Wait and retry |

## Example Conversation

User: "Deploy my project to Vercel"
Agent: "I'll analyze your project first..."
Agent: "Found a Next.js project. I'll create a vercel.json and deploy. Proceed?"
User: "Yes"
Agent: "Deploying to Vercel... Done! Your app is live at https://your-app.vercel.app"
```

## Python Skill Class

For complex logic, implement a Python skill class.

### Base Class

```python
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class SkillResult(BaseModel):
    success: bool
    message: str
    data: dict | None = None
    error: str | None = None

class BaseSkill(ABC):
    """Base class for OpenOps skills."""
    
    name: str
    description: str
    risk_level: str  # "read", "write", "destructive"
    
    @abstractmethod
    def get_tools(self) -> list:
        """Return LangChain tools provided by this skill."""
        pass
    
    def validate_credentials(self) -> bool:
        """Check if required credentials are available."""
        return True
```

### Vercel Skill Implementation

```python
import httpx
from langchain_core.tools import tool
from openops.skills.base import BaseSkill, SkillResult

class VercelSkill(BaseSkill):
    name = "vercel-deploy"
    description = "Deploy applications to Vercel"
    risk_level = "write"
    
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("VERCEL_TOKEN")
        self.base_url = "https://api.vercel.com"
    
    def validate_credentials(self) -> bool:
        return self.token is not None
    
    def get_tools(self) -> list:
        return [
            self._create_deploy_tool(),
            self._create_list_projects_tool(),
            self._create_get_deployments_tool(),
        ]
    
    def _create_deploy_tool(self):
        @tool
        def vercel_deploy(
            project_path: str,
            project_name: str,
            production: bool = False,
        ) -> SkillResult:
            """Deploy a project to Vercel.
            
            Args:
                project_path: Path to the project directory
                project_name: Name for the Vercel project
                production: Deploy to production (default: staging)
                
            Returns:
                Deployment result with URL and status
            """
            if not self.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Vercel token not configured",
                    error="MISSING_CREDENTIALS"
                )
            
            # Implementation using Vercel API
            try:
                response = httpx.post(
                    f"{self.base_url}/v13/deployments",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={
                        "name": project_name,
                        "target": "production" if production else "preview",
                        # ... more config
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                return SkillResult(
                    success=True,
                    message=f"Deployed successfully",
                    data={
                        "url": data["url"],
                        "deployment_id": data["id"],
                        "dashboard": f"https://vercel.com/{data['owner']}/{project_name}",
                    }
                )
            except httpx.HTTPError as e:
                return SkillResult(
                    success=False,
                    message=f"Deployment failed: {e}",
                    error=str(e)
                )
        
        return vercel_deploy
    
    def _create_list_projects_tool(self):
        @tool
        def vercel_list_projects() -> SkillResult:
            """List all Vercel projects for the authenticated user."""
            # Implementation
            pass
        return vercel_list_projects
    
    def _create_get_deployments_tool(self):
        @tool
        def vercel_get_deployments(project_name: str, limit: int = 10) -> SkillResult:
            """Get recent deployments for a project.
            
            Args:
                project_name: Name of the Vercel project
                limit: Number of deployments to fetch
            """
            # Implementation
            pass
        return vercel_get_deployments
```

## Skill Loading

Skills are loaded by the `SkillsMiddleware` in Deep Agents.

```python
# Orchestrator loads skills from directories
orchestrator = create_deep_agent(
    skills=[
        "~/.openops/skills/",      # Global skills
        "./skills/",                # Project-specific skills
    ],
    # ...
)
```

### Loading Order

1. **SKILL.md parsed** - Frontmatter extracted, content loaded
2. **Python module imported** - If `metadata.entrypoint` specified
3. **Tools registered** - Added to agent's tool list
4. **Instructions injected** - SKILL.md content available to agent

## Community Contribution

### Simple Contribution (SKILL.md only)

For platforms with simple REST APIs, a SKILL.md is often sufficient:

```markdown
---
name: netlify-deploy
description: Deploy static sites to Netlify
version: 1.0.0
author: Community Contributor
risk_level: write
platforms:
  - netlify
requires:
  credentials:
    - NETLIFY_TOKEN
---

# Netlify Deployment

## API Reference

Base URL: https://api.netlify.com/api/v1

### Create Deploy

POST /sites/{site_id}/deploys

Headers:
- Authorization: Bearer {NETLIFY_TOKEN}

Body: multipart/form-data with zip file

### Response

{
  "id": "deploy-id",
  "url": "https://site-name.netlify.app",
  "state": "ready"
}

## Steps for Agent

1. Check for existing netlify.toml
2. Create site if not exists
3. Zip project files
4. Upload to Netlify
5. Report deployment URL
```

### Full Contribution (Python + SKILL.md)

For complex platforms, include Python implementation:

```
my-skill/
├── SKILL.md                 # Required: Agent instructions
├── skill.py                 # Python skill class
├── __init__.py              # Package init
├── templates/               # Config templates
│   └── config.j2
├── tests/
│   ├── test_skill.py
│   └── fixtures/
└── README.md                # Contributor docs
```

## Built-in Skills

| Skill | Platform | Risk Level | Status |
|-------|----------|------------|--------|
| `vercel-deploy` | Vercel | write | ✅ Implemented |
| `railway-deploy` | Railway | write | ✅ Implemented |
| `render-deploy` | Render | write | ✅ Implemented |
| `observability` | Health checks, alerts | read | ✅ Implemented |

## Testing Skills

See [10-testing.md](./10-testing.md) for skill testing guidelines.

```python
# tests/test_vercel_skill.py
import pytest
from openops.skills.vercel import VercelSkill

@pytest.fixture
def skill():
    return VercelSkill(token="test-token")

def test_tools_registered(skill):
    tools = skill.get_tools()
    assert len(tools) >= 1
    assert any(t.name == "vercel_deploy" for t in tools)

def test_deploy_missing_token():
    skill = VercelSkill(token=None)
    result = skill.get_tools()[0].invoke({
        "project_path": "/test",
        "project_name": "test"
    })
    assert not result.success
    assert result.error == "MISSING_CREDENTIALS"
```

## Next Steps

- [04-cli-and-tui.md](./04-cli-and-tui.md) - How users interact with skills
- [11-contributing.md](./11-contributing.md) - Full contribution guide
