# Testing Strategy

## Overview

Testing an agentic system requires multiple layers:

1. **Unit Tests** - Individual skills, tools, and utilities
2. **Integration Tests** - Agent interactions with mocked dependencies
3. **Simulation Tests** - Full conversation flows with recorded responses
4. **Mock Project** - Manual testing with a sample project

## Testing Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              E2E Tests (Optional)                            │
│  - Real deployments to test accounts                                         │
│  - Expensive, slow, use sparingly                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                            Simulation Tests                                  │
│  - Recorded LLM responses (deterministic)                                    │
│  - Full conversation flows                                                   │
│  - Golden output comparison                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                           Integration Tests                                  │
│  - Agent with mocked LLM                                                     │
│  - Mocked platform APIs                                                      │
│  - Memory store operations                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                              Unit Tests                                      │
│  - Skill logic                                                               │
│  - Tool functions                                                            │
│  - Config parsers                                                            │
│  - Project analyzers                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_skills/
│   │   ├── test_vercel_skill.py
│   │   ├── test_railway_skill.py
│   │   └── test_render_skill.py
│   ├── test_analyzers/
│   │   ├── test_framework_detection.py
│   │   └── test_project_analysis.py
│   ├── test_memory/
│   │   ├── test_project_store.py
│   │   └── test_agent_memory.py
│   └── test_config.py
├── integration/
│   ├── test_agent_flows.py
│   ├── test_deployment_flow.py
│   └── test_monitoring.py
├── simulation/
│   ├── recordings/          # Recorded LLM responses
│   │   ├── deploy_nextjs_vercel.json
│   │   └── analyze_monorepo.json
│   ├── test_conversations.py
│   └── golden/              # Expected outputs
│       └── deploy_nextjs_vercel.txt
└── fixtures/
    ├── projects/            # Sample project structures
    │   ├── nextjs-simple/
    │   ├── fastapi-simple/
    │   └── monorepo/
    └── responses/           # Mock API responses
        ├── vercel/
        └── railway/
```

## Unit Tests

### Testing Skills

```python
# tests/unit/test_skills/test_vercel_skill.py
import pytest
from unittest.mock import Mock, patch
from openops.skills.vercel import VercelSkill, SkillResult

@pytest.fixture
def skill():
    """Create skill with test token."""
    return VercelSkill(token="test-token-123")

@pytest.fixture
def skill_no_token():
    """Create skill without token."""
    return VercelSkill(token=None)

class TestVercelSkill:
    def test_get_tools_returns_expected_tools(self, skill):
        """Verify skill exposes correct tools."""
        tools = skill.get_tools()
        tool_names = [t.name for t in tools]
        
        assert "vercel_deploy" in tool_names
        assert "vercel_list_projects" in tool_names
        assert "vercel_get_deployments" in tool_names
    
    def test_validate_credentials_with_token(self, skill):
        """Credentials valid when token present."""
        assert skill.validate_credentials() is True
    
    def test_validate_credentials_without_token(self, skill_no_token):
        """Credentials invalid when token missing."""
        assert skill_no_token.validate_credentials() is False
    
    @patch("httpx.post")
    def test_deploy_success(self, mock_post, skill):
        """Test successful deployment."""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "id": "dpl_123",
                "url": "https://my-app.vercel.app",
                "owner": {"username": "testuser"},
            }
        )
        
        deploy_tool = skill.get_tools()[0]  # vercel_deploy
        result = deploy_tool.invoke({
            "project_path": "/test/project",
            "project_name": "my-app",
            "production": False,
        })
        
        assert result.success is True
        assert "my-app.vercel.app" in result.data["url"]
    
    @patch("httpx.post")
    def test_deploy_api_error(self, mock_post, skill):
        """Test deployment with API error."""
        mock_post.return_value = Mock(
            status_code=401,
            raise_for_status=Mock(side_effect=Exception("Unauthorized"))
        )
        
        deploy_tool = skill.get_tools()[0]
        result = deploy_tool.invoke({
            "project_path": "/test/project",
            "project_name": "my-app",
        })
        
        assert result.success is False
        assert "Unauthorized" in result.error
    
    def test_deploy_without_credentials(self, skill_no_token):
        """Test deployment fails gracefully without credentials."""
        deploy_tool = skill_no_token.get_tools()[0]
        result = deploy_tool.invoke({
            "project_path": "/test/project",
            "project_name": "my-app",
        })
        
        assert result.success is False
        assert result.error == "MISSING_CREDENTIALS"
```

### Testing Project Analysis

```python
# tests/unit/test_analyzers/test_framework_detection.py
import pytest
from pathlib import Path
from openops.analysis.framework import detect_framework, FRAMEWORK_DETECTION

@pytest.fixture
def nextjs_project(tmp_path):
    """Create a minimal Next.js project structure."""
    (tmp_path / "package.json").write_text('{"dependencies": {"next": "14.0.0"}}')
    (tmp_path / "next.config.js").write_text("module.exports = {}")
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "index.tsx").write_text("export default function Home() {}")
    return tmp_path

@pytest.fixture
def fastapi_project(tmp_path):
    """Create a minimal FastAPI project structure."""
    (tmp_path / "pyproject.toml").write_text("""
[project]
dependencies = ["fastapi>=0.100.0", "uvicorn"]
""")
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
    return tmp_path

class TestFrameworkDetection:
    def test_detect_nextjs(self, nextjs_project):
        """Detect Next.js project."""
        result = detect_framework(str(nextjs_project))
        
        assert result["framework"] == "nextjs"
        assert result["type"] == "frontend"
        assert result["confidence"] > 0.9
    
    def test_detect_fastapi(self, fastapi_project):
        """Detect FastAPI project."""
        result = detect_framework(str(fastapi_project))
        
        assert result["framework"] == "fastapi"
        assert result["type"] == "backend"
        assert result["confidence"] > 0.9
    
    def test_detect_unknown(self, tmp_path):
        """Handle unknown project gracefully."""
        (tmp_path / "random.txt").write_text("hello")
        
        result = detect_framework(str(tmp_path))
        
        assert result["framework"] == "unknown"
        assert result["confidence"] == 0
```

### Testing Memory Store

```python
# tests/unit/test_memory/test_project_store.py
import pytest
from datetime import datetime
from openops.memory.project_store import ProjectStore, Project, Service

@pytest.fixture
def store(tmp_path):
    """Create in-memory test store."""
    db_path = tmp_path / "test.db"
    return ProjectStore(str(db_path))

@pytest.fixture
def sample_project():
    return Project(
        id="proj-123",
        path="/test/my-project",
        name="my-project",
        description="A test project",
        keypoints=["Next.js frontend", "FastAPI backend"],
        analyzed_at=datetime.now(),
        updated_at=datetime.now(),
    )

class TestProjectStore:
    def test_upsert_and_get_project(self, store, sample_project):
        """Test project CRUD."""
        store.upsert_project(sample_project)
        
        retrieved = store.get_project(sample_project.path)
        
        assert retrieved is not None
        assert retrieved.name == sample_project.name
        assert retrieved.keypoints == sample_project.keypoints
    
    def test_get_nonexistent_project(self, store):
        """Get returns None for missing project."""
        result = store.get_project("/nonexistent")
        assert result is None
    
    def test_upsert_updates_existing(self, store, sample_project):
        """Upsert updates existing project."""
        store.upsert_project(sample_project)
        
        sample_project.description = "Updated description"
        store.upsert_project(sample_project)
        
        retrieved = store.get_project(sample_project.path)
        assert retrieved.description == "Updated description"
```

## Integration Tests

### Testing Agent Flows

```python
# tests/integration/test_agent_flows.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from openops.agent.runtime import OpenOpsRuntime
from openops.agent.orchestrator import create_orchestrator

@pytest.fixture
def mock_llm():
    """Create mock LLM that returns predefined responses."""
    mock = Mock()
    mock.invoke = Mock(return_value={
        "messages": [Mock(content="I'll analyze your project now.")]
    })
    return mock

@pytest.fixture
def runtime(mock_llm, tmp_path):
    """Create runtime with mocked LLM."""
    with patch("openops.agent.runtime.create_deep_agent") as mock_create:
        mock_create.return_value = mock_llm
        
        runtime = OpenOpsRuntime(
            config_path=str(tmp_path / "config.yaml"),
            memory_path=str(tmp_path / "memory.db"),
        )
        return runtime

class TestAgentFlows:
    def test_process_returns_response(self, runtime):
        """Basic message processing works."""
        result = runtime.process("Hello, analyze my project")
        
        assert "summary" in result
        assert result["mode"] == "agent"
    
    def test_session_continuity(self, runtime):
        """Same session maintains context."""
        runtime.process("My project is at /test/path")
        result = runtime.process("What's the path?")
        
        # Verify same thread_id used
        assert runtime._session_id is not None
```

### Testing Deployment Flow

```python
# tests/integration/test_deployment_flow.py
import pytest
import respx
from httpx import Response
from openops.deployment.flow import DeploymentFlow
from openops.skills.vercel import VercelSkill

@pytest.fixture
def deployment_flow():
    return DeploymentFlow(
        skills=[VercelSkill(token="test-token")]
    )

@pytest.fixture
def mock_vercel_api():
    """Mock Vercel API responses."""
    with respx.mock:
        # Mock deployment creation
        respx.post("https://api.vercel.com/v13/deployments").mock(
            return_value=Response(200, json={
                "id": "dpl_abc123",
                "url": "https://test-app.vercel.app",
                "readyState": "READY",
            })
        )
        
        # Mock deployment status check
        respx.get(respx.patterns.path__regex(r"/v13/deployments/.*")).mock(
            return_value=Response(200, json={
                "readyState": "READY",
                "url": "https://test-app.vercel.app",
            })
        )
        
        yield

class TestDeploymentFlow:
    def test_deploy_to_vercel(self, deployment_flow, mock_vercel_api, tmp_path):
        """Test complete deployment flow."""
        # Setup test project
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "next.config.js").write_text("{}")
        
        result = deployment_flow.deploy(
            project_path=str(tmp_path),
            platform="vercel",
        )
        
        assert result.success is True
        assert "vercel.app" in result.url
```

## Simulation Tests

### Recording LLM Responses

```python
# tests/simulation/recorder.py
import json
from pathlib import Path
from datetime import datetime

class ResponseRecorder:
    """Record LLM responses for deterministic replay."""
    
    def __init__(self, recording_path: Path):
        self.recording_path = recording_path
        self.responses = []
    
    def record(self, prompt: str, response: str):
        """Record a prompt-response pair."""
        self.responses.append({
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response": response,
        })
    
    def save(self, name: str):
        """Save recording to file."""
        path = self.recording_path / f"{name}.json"
        with open(path, "w") as f:
            json.dump(self.responses, f, indent=2)

class ResponseReplayer:
    """Replay recorded LLM responses."""
    
    def __init__(self, recording_path: Path):
        self.recording_path = recording_path
        self.responses = []
        self.index = 0
    
    def load(self, name: str):
        """Load recording from file."""
        path = self.recording_path / f"{name}.json"
        with open(path) as f:
            self.responses = json.load(f)
        self.index = 0
    
    def get_next_response(self) -> str:
        """Get next recorded response."""
        if self.index >= len(self.responses):
            raise IndexError("No more recorded responses")
        
        response = self.responses[self.index]["response"]
        self.index += 1
        return response
```

### Running Simulation Tests

```python
# tests/simulation/test_conversations.py
import pytest
from pathlib import Path
from openops.agent.orchestrator import create_orchestrator
from .recorder import ResponseReplayer

RECORDINGS_DIR = Path(__file__).parent / "recordings"
GOLDEN_DIR = Path(__file__).parent / "golden"

@pytest.fixture
def replayer():
    return ResponseReplayer(RECORDINGS_DIR)

@pytest.fixture  
def mock_agent(replayer):
    """Create agent with recorded responses."""
    replayer.load("deploy_nextjs_vercel")
    
    # Patch LLM to return recorded responses
    # ...
    
    return create_orchestrator()

class TestConversations:
    def test_deploy_nextjs_to_vercel(self, mock_agent):
        """Test complete deployment conversation."""
        conversation = [
            "I have a Next.js project at /test/nextjs-app",
            "Yes, deploy to Vercel",
            "Use production",
        ]
        
        outputs = []
        for message in conversation:
            result = mock_agent.invoke({
                "messages": [{"role": "user", "content": message}]
            })
            outputs.append(result["messages"][-1].content)
        
        # Compare to golden output
        golden_path = GOLDEN_DIR / "deploy_nextjs_vercel.txt"
        expected = golden_path.read_text()
        
        # Verify key elements present
        assert "vercel.app" in outputs[-1]
        assert "deployed" in outputs[-1].lower()
```

## Mock Project

A sample project for manual testing is included at `docs/mock-project/`.

### Structure

```
docs/mock-project/
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── pages/
│   │   └── index.tsx
│   └── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── main.py
│   └── .env.example
└── README.md
```

### Usage

```bash
# Navigate to mock project
cd docs/mock-project

# Test project analysis
openops chat .
# Ask: "Analyze this project"

# Test deployment (dry run)
openops deploy --dry-run

# Test with specific platform
openops deploy --platform vercel --dry-run
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=openops --cov-report=html

# Run specific layer
pytest tests/unit/
pytest tests/integration/
pytest tests/simulation/

# Run specific test file
pytest tests/unit/test_skills/test_vercel_skill.py

# Run with verbose output
pytest tests/ -v

# Run only fast tests (skip slow integration)
pytest tests/ -m "not slow"
```

## Test Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "simulation: marks tests as simulation tests",
]
addopts = "-ra -q"

[tool.coverage.run]
source = ["src/openops"]
omit = ["tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

## CI Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Run unit tests
        run: pytest tests/unit/ -v
      
      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          OPENOPS_TEST_MODE: "true"
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

## Next Steps

- [11-contributing.md](./11-contributing.md) - How to contribute tests
- [12-roadmap.md](./12-roadmap.md) - Testing milestones
