# Contributing Guide

## Overview

OpenOps is an open-source project and we welcome contributions! This guide covers:

1. **Adding Platform Skills** - Support new deployment platforms
2. **Improving Core Features** - Enhance agents, memory, CLI
3. **Documentation** - Improve docs and examples
4. **Bug Fixes** - Fix issues and improve stability

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- A code editor (VS Code, Cursor, etc.)

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/openops/openops.git
cd openops

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"

# Verify installation
openops --version
pytest tests/unit/ -v
```

### Development Workflow

```bash
# Create a branch for your work
git checkout -b feature/my-feature

# Make changes...

# Run tests
pytest tests/

# Run linting
ruff check src/
ruff format src/

# Commit changes
git add .
git commit -m "Add feature X"

# Push and create PR
git push origin feature/my-feature
```

## Adding a New Platform Skill

The most common contribution is adding support for a new deployment platform.

### Step 1: Create Skill Directory

```bash
mkdir -p src/openops/skills/builtin/my-platform
cd src/openops/skills/builtin/my-platform
```

### Step 2: Write SKILL.md

```markdown
---
name: my-platform-deploy
description: Deploy applications to MyPlatform
version: 1.0.0
author: Your Name <your@email.com>
risk_level: write
platforms:
  - my-platform
requires:
  credentials:
    - MYPLATFORM_TOKEN
  tools:
    - myplatform_deploy
    - myplatform_list_projects
---

# MyPlatform Deployment Skill

## When to Use

Use this skill when:
- User wants to deploy to MyPlatform
- Project is compatible with MyPlatform's supported frameworks

## Prerequisites

1. User must have a MyPlatform account
2. MYPLATFORM_TOKEN must be configured

## API Reference

Base URL: https://api.myplatform.com/v1

### Create Deployment

POST /deployments
Headers: Authorization: Bearer {token}

### Response
{
  "id": "deploy-123",
  "url": "https://app.myplatform.com",
  "status": "building"
}

## Deployment Steps

1. Validate project structure
2. Generate platform config if needed
3. Create deployment via API
4. Poll for completion
5. Report final URL

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| 401 | Invalid token | Check credentials |
| 422 | Invalid config | Validate project structure |
```

### Step 3: Implement Python Skill

```python
# src/openops/skills/builtin/my-platform/skill.py
import httpx
from langchain_core.tools import tool
from openops.skills.base import BaseSkill, SkillResult
import os
import logging

logger = logging.getLogger(__name__)

class MyPlatformSkill(BaseSkill):
    """Skill for deploying to MyPlatform."""
    
    name = "my-platform-deploy"
    description = "Deploy applications to MyPlatform"
    risk_level = "write"
    
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("MYPLATFORM_TOKEN")
        self.base_url = "https://api.myplatform.com/v1"
    
    def validate_credentials(self) -> bool:
        """Check if credentials are configured."""
        return self.token is not None
    
    def get_tools(self) -> list:
        """Return tools provided by this skill."""
        return [
            self._create_deploy_tool(),
            self._create_list_projects_tool(),
        ]
    
    def _create_deploy_tool(self):
        @tool
        def myplatform_deploy(
            project_path: str,
            project_name: str,
            environment: str = "preview",
        ) -> SkillResult:
            """Deploy a project to MyPlatform.
            
            Args:
                project_path: Path to the project directory
                project_name: Name for the deployment
                environment: Target environment (preview or production)
                
            Returns:
                Deployment result with URL and status
            """
            logger.info(f"Deploying {project_name} to MyPlatform")
            
            if not self.validate_credentials():
                logger.error("MyPlatform credentials not configured")
                return SkillResult(
                    success=False,
                    message="MyPlatform token not configured",
                    error="MISSING_CREDENTIALS"
                )
            
            try:
                # Create deployment
                response = httpx.post(
                    f"{self.base_url}/deployments",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={
                        "name": project_name,
                        "environment": environment,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"Deployment created: {data['id']}")
                
                # Poll for completion (simplified)
                # In real implementation, poll until ready
                
                return SkillResult(
                    success=True,
                    message=f"Deployed to MyPlatform",
                    data={
                        "deployment_id": data["id"],
                        "url": data["url"],
                        "status": data["status"],
                    }
                )
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Deployment failed: {e}")
                return SkillResult(
                    success=False,
                    message=f"Deployment failed: {e.response.status_code}",
                    error=str(e)
                )
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return SkillResult(
                    success=False,
                    message=f"Deployment failed: {e}",
                    error=str(e)
                )
        
        return myplatform_deploy
    
    def _create_list_projects_tool(self):
        @tool
        def myplatform_list_projects() -> SkillResult:
            """List all projects on MyPlatform."""
            if not self.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Credentials not configured",
                    error="MISSING_CREDENTIALS"
                )
            
            try:
                response = httpx.get(
                    f"{self.base_url}/projects",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                response.raise_for_status()
                
                return SkillResult(
                    success=True,
                    message="Projects retrieved",
                    data={"projects": response.json()}
                )
            except Exception as e:
                return SkillResult(
                    success=False,
                    message=str(e),
                    error=str(e)
                )
        
        return myplatform_list_projects
```

### Step 4: Add __init__.py

```python
# src/openops/skills/builtin/my-platform/__init__.py
from .skill import MyPlatformSkill

__all__ = ["MyPlatformSkill"]
```

### Step 5: Register the Skill

```python
# src/openops/skills/builtin/__init__.py
from .vercel import VercelSkill
from .railway import RailwaySkill
from .render import RenderSkill
from .my_platform import MyPlatformSkill  # Add this line

BUILTIN_SKILLS = [
    VercelSkill,
    RailwaySkill,
    RenderSkill,
    MyPlatformSkill,  # Add this line
]
```

### Step 6: Write Tests

```python
# tests/unit/test_skills/test_myplatform_skill.py
import pytest
from unittest.mock import Mock, patch
from openops.skills.builtin.my_platform import MyPlatformSkill

@pytest.fixture
def skill():
    return MyPlatformSkill(token="test-token")

class TestMyPlatformSkill:
    def test_validate_credentials(self, skill):
        assert skill.validate_credentials() is True
    
    def test_validate_credentials_missing(self):
        skill = MyPlatformSkill(token=None)
        assert skill.validate_credentials() is False
    
    @patch("httpx.post")
    def test_deploy_success(self, mock_post, skill):
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "id": "deploy-123",
                "url": "https://app.myplatform.com",
                "status": "ready",
            }
        )
        
        deploy_tool = skill.get_tools()[0]
        result = deploy_tool.invoke({
            "project_path": "/test",
            "project_name": "test-app",
        })
        
        assert result.success is True
        assert "myplatform.com" in result.data["url"]
```

### Step 7: Update Documentation

Add your platform to:
- `docs/03-skills.md` - Add to built-in skills table
- `docs/09-configuration.md` - Add credential reference

### Step 8: Submit PR

```bash
git add .
git commit -m "Add MyPlatform deployment skill"
git push origin feature/myplatform-skill
# Create PR on GitHub
```

## Code Style Guidelines

### Python

```python
# Use type hints
def process_message(message: str, context: dict | None = None) -> dict:
    ...

# Use dataclasses for data structures
from dataclasses import dataclass

@dataclass
class DeploymentResult:
    success: bool
    url: str | None
    error: str | None = None

# Use logging, not print
import logging
logger = logging.getLogger(__name__)
logger.info("Processing deployment")
logger.debug(f"Config: {config}")

# Document public functions
def analyze_project(path: str) -> ProjectAnalysis:
    """Analyze a project's structure for deployment.
    
    Args:
        path: Absolute path to the project root
        
    Returns:
        ProjectAnalysis with detected services and tech stack
        
    Raises:
        ValueError: If path doesn't exist
    """
    ...
```

### Formatting

We use `ruff` for linting and formatting:

```bash
# Check code
ruff check src/

# Auto-fix issues
ruff check src/ --fix

# Format code
ruff format src/
```

### Configuration

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]  # Line length handled by formatter
```

## Pull Request Guidelines

### PR Title

Use conventional commit format:
- `feat: Add MyPlatform deployment skill`
- `fix: Handle timeout in Vercel deployment`
- `docs: Update skill contribution guide`
- `test: Add integration tests for monitoring`

### PR Description

```markdown
## Summary

Brief description of what this PR does.

## Changes

- Added MyPlatformSkill class
- Added SKILL.md documentation
- Added unit tests

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass (if applicable)
- [ ] Manually tested with mock project

## Documentation

- [ ] Updated relevant docs
- [ ] Added code comments where needed
```

### Review Process

1. **Automated checks** - CI runs tests, linting
2. **Code review** - Maintainer reviews code quality
3. **Testing** - Verify functionality works
4. **Documentation** - Ensure docs are updated
5. **Merge** - Squash and merge to main

## Contribution Areas

### High Priority

- [ ] AWS ECS/EKS deployment skill
- [ ] GCP Cloud Run skill
- [ ] DigitalOcean App Platform skill
- [ ] Docker Compose deployment skill

### Medium Priority

- [ ] Improved error messages
- [ ] More framework detection patterns
- [ ] Better monorepo support
- [ ] Kubernetes manifest generation

### Good First Issues

- Add more framework detection patterns
- Improve test coverage
- Fix typos in documentation
- Add example projects

## Community

### Getting Help

- **GitHub Issues** - Bug reports, feature requests
- **GitHub Discussions** - Questions, ideas
- **Discord** - Real-time chat (coming soon)

### Code of Conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/). Be respectful and inclusive.

## License

OpenOps is MIT licensed. By contributing, you agree that your contributions will be licensed under the same terms.

## Next Steps

- [10-testing.md](./10-testing.md) - Testing requirements
- [12-roadmap.md](./12-roadmap.md) - What we're working on
