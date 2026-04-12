# Configuration

## Overview

OpenOps uses a layered configuration system:

1. **Global config** (`~/.openops/config.yaml`) - User-wide settings
2. **Project config** (`<project>/.openops/config.yaml`) - Project overrides
3. **Environment variables** - Runtime overrides
4. **CLI flags** - Session overrides

Priority: CLI flags > Environment > Project config > Global config > Defaults

## Global Configuration

### Location

```
~/.openops/
├── config.yaml           # Main configuration
├── credentials.enc       # Encrypted API keys
├── memory.db             # Agent memory (SQLite)
├── projects.db           # Project knowledge (SQLite)
├── checkpoints.db        # Agent state checkpoints
├── daemon.pid            # Monitor daemon PID
├── daemon.log            # Monitor daemon logs
└── skills/               # Community skills
    ├── aws-deploy/
    └── gcp-deploy/
```

### Full Configuration Reference

```yaml
# ~/.openops/config.yaml

# =============================================================================
# Model Configuration
# =============================================================================
model:
  # LLM provider: openai, anthropic, google
  provider: anthropic

  # Model name (provider-specific)
  # Anthropic: claude-sonnet-4-5, claude-opus-4
  # OpenAI: gpt-4o, gpt-4o-mini
  # Google: gemini-pro, gemini-ultra
  name: claude-sonnet-4-5

  # Model parameters
  temperature: 0.1
  max_tokens: 4096

  # Fallback model if primary fails
  fallback:
    provider: openai
    name: gpt-4o-mini

# =============================================================================
# CLI and TUI Settings
# =============================================================================
cli:
  # Output format: rich, plain, json
  output_format: rich

  # Color mode: auto, always, never
  color: auto

  # Pager for long output: auto, always, never
  pager: auto

tui:
  # Syntax highlighting theme
  # Available: monokai, dracula, github-dark, one-dark, nord
  theme: monokai

  # Command history size
  history_size: 1000

  # Show thinking indicator while agent processes
  show_thinking: true

  # Confirm before destructive operations
  confirm_destructive: true

  # Auto-scroll to latest message
  auto_scroll: true

# =============================================================================
# Default Behaviors
# =============================================================================
defaults:
  # Default deployment platform
  platform: vercel

  # Dry run by default (show what would happen without doing it)
  dry_run: false

  # Auto-save project analysis
  auto_save_analysis: true

  # Auto-suggest monitoring after deployment
  suggest_monitoring: true

# =============================================================================
# Memory Configuration
# =============================================================================
memory:
  # Agent memory backend (only sqlite supported)
  agent_store: sqlite
  agent_store_path: ~/.openops/memory.db

  # Project knowledge backend: sqlite or neo4j
  project_store: sqlite
  project_store_path: ~/.openops/projects.db

  # Neo4j settings (if project_store: neo4j)
  neo4j_uri: bolt://localhost:7687
  neo4j_user: neo4j
  neo4j_password: ${OPENOPS_NEO4J_PASSWORD}

  # Data retention
  conversation_retention_days: 30
  checkpoint_retention_days: 7

# =============================================================================
# Monitoring Configuration
# =============================================================================
monitoring:
  # Enable background monitoring
  enabled: false

  # Check interval in seconds
  interval: 60

  # Thresholds
  thresholds:
    response_time_warning: 1000   # ms
    response_time_critical: 5000  # ms
    error_rate_warning: 0.01      # 1%
    error_rate_critical: 0.05     # 5%

  # Alert channels
  alerts:
    slack:
      enabled: false
      webhook_url: ${SLACK_WEBHOOK_URL}
      channels:
        critical: "#alerts-critical"
        warning: "#alerts-warning"
        info: "#alerts-info"

    email:
      enabled: false
      smtp_host: smtp.example.com
      smtp_port: 587
      smtp_user: ${SMTP_USER}
      smtp_password: ${SMTP_PASSWORD}
      from: openops@example.com
      to:
        - team@example.com

# =============================================================================
# Skills Configuration
# =============================================================================
skills:
  # Directories to load skills from
  paths:
    - ~/.openops/skills/
    - ./skills/

  # Auto-update community skills
  auto_update: true

  # Update check interval (hours)
  update_interval: 24

# =============================================================================
# Security Configuration
# =============================================================================
security:
  # Require approval for these operations
  require_approval:
    - deploy
    - delete_file
    - modify_env

  # Sandbox file operations to project directory
  sandbox_enabled: true

  # Allowed directories outside sandbox
  allowed_paths:
    - ~/.openops/

  # Credential encryption
  credential_encryption: true

# =============================================================================
# Logging Configuration
# =============================================================================
logging:
  # Log level: debug, info, warning, error
  level: info

  # Log file path
  file: ~/.openops/openops.log

  # Log format: text, json
  format: text

  # Max log file size (MB)
  max_size: 10

  # Number of backup files to keep
  backup_count: 3

# =============================================================================
# Advanced Configuration
# =============================================================================
advanced:
  # Request timeout (seconds)
  request_timeout: 30

  # Max retries for failed requests
  max_retries: 3

  # Retry backoff multiplier
  retry_backoff: 2.0

  # Enable debug mode
  debug: false

  # Disable telemetry
  telemetry_disabled: false
```

## Credentials Management

### Encrypted Storage

Credentials are stored encrypted in `~/.openops/credentials.enc`:

```python
from cryptography.fernet import Fernet

class CredentialStore:
    def __init__(self, path: str = "~/.openops/credentials.enc"):
        self.path = Path(path).expanduser()
        self.key = self._get_or_create_key()
        self.fernet = Fernet(self.key)

    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key from system keyring."""
        import keyring

        key = keyring.get_password("openops", "encryption_key")
        if not key:
            key = Fernet.generate_key().decode()
            keyring.set_password("openops", "encryption_key", key)
        return key.encode()

    def set(self, name: str, value: str) -> None:
        """Store an encrypted credential."""
        data = self._load()
        data[name] = self.fernet.encrypt(value.encode()).decode()
        self._save(data)

    def get(self, name: str) -> str | None:
        """Retrieve a decrypted credential."""
        data = self._load()
        if name not in data:
            return None
        return self.fernet.decrypt(data[name].encode()).decode()
```

### CLI Commands

```bash
# Add credentials
$ openops credentials add vercel
Enter Vercel API token: ****
✓ Vercel credentials saved

# List credentials
$ openops credentials list
Platform     Status
──────────────────────
Anthropic    ✓ configured
Vercel       ✓ configured
Railway      ✗ not configured
Render       ✗ not configured

# Remove credentials
$ openops credentials remove vercel
✓ Vercel credentials removed

# Test credentials
$ openops credentials test vercel
Testing Vercel credentials...
✓ Valid (user: john@example.com)
```

### Environment Variables

All credentials can be provided via environment:

```bash
# LLM providers
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."

# Deployment platforms
export VERCEL_TOKEN="..."
export RAILWAY_TOKEN="..."
export RENDER_API_KEY="..."

# Monitoring
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."

# Database (for Neo4j)
export OPENOPS_NEO4J_PASSWORD="..."
```

## Project Configuration

### Location

```
<project>/
├── .openops/
│   ├── config.yaml       # Project-specific config
│   └── skills/           # Project-specific skills
└── ... (project files)
```

### Project Config Example

```yaml
# <project>/.openops/config.yaml

# Override deployment platform for this project
defaults:
  platform: railway

# Project-specific environment mapping
env_mapping:
  DATABASE_URL: RAILWAY_DATABASE_URL
  REDIS_URL: RAILWAY_REDIS_URL

# Service configuration
services:
  api:
    platform: railway
    env_vars:
      - DATABASE_URL
      - JWT_SECRET

  web:
    platform: vercel
    env_vars:
      - NEXT_PUBLIC_API_URL

# Monitoring for this project
monitoring:
  enabled: true
  services:
    - name: api
      health_check: /health
      interval: 30
    - name: web
      health_check: /
      interval: 60
```

## CLI Configuration Commands

```bash
# View current configuration
$ openops config show
Model:
  provider: anthropic
  name: claude-sonnet-4-5
  temperature: 0.1

Defaults:
  platform: vercel
  dry_run: false
...

# Get specific value
$ openops config get model.provider
anthropic

# Set value
$ openops config set model.provider openai
✓ Set model.provider = openai

# Set nested value
$ openops config set monitoring.alerts.slack.enabled true
✓ Set monitoring.alerts.slack.enabled = true

# Reset to defaults
$ openops config reset
? Reset all configuration to defaults? Yes
✓ Configuration reset

# Reset specific key
$ openops config reset model
✓ Reset model configuration

# Edit config file directly
$ openops config edit
# Opens ~/.openops/config.yaml in $EDITOR

# Validate configuration
$ openops config validate
✓ Configuration is valid
```

## Configuration Validation

```python
from pydantic import BaseModel, validator
from typing import Literal

class ModelConfig(BaseModel):
    provider: Literal["anthropic", "openai", "google"]
    name: str
    temperature: float = 0.1
    max_tokens: int = 4096

    @validator("temperature")
    def validate_temperature(cls, v):
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

class MonitoringConfig(BaseModel):
    enabled: bool = False
    interval: int = 60

    @validator("interval")
    def validate_interval(cls, v):
        if v < 10:
            raise ValueError("Interval must be at least 10 seconds")
        return v

class OpenOpsConfig(BaseModel):
    model: ModelConfig
    monitoring: MonitoringConfig
    # ... other sections

    @classmethod
    def load(cls, path: str = "~/.openops/config.yaml") -> "OpenOpsConfig":
        """Load and validate configuration."""
        path = Path(path).expanduser()

        if not path.exists():
            return cls.defaults()

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(**data)
```

## Environment Variable Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENOPS_CONFIG` | Config file path | `~/.openops/config.yaml` |
| `OPENOPS_MODEL` | Model override | From config |
| `OPENOPS_DRY_RUN` | Dry run mode | `false` |
| `OPENOPS_DEBUG` | Debug mode | `false` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GOOGLE_API_KEY` | Google API key | - |
| `VERCEL_TOKEN` | Vercel API token | - |
| `RAILWAY_TOKEN` | Railway API token | - |
| `RENDER_API_KEY` | Render API key | - |
| `SLACK_WEBHOOK_URL` | Slack webhook URL | - |

## Next Steps

- [10-testing.md](./10-testing.md) - Testing configuration
- [11-contributing.md](./11-contributing.md) - Contributing guidelines
