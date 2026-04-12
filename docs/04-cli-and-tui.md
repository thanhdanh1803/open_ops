# CLI and TUI Design

## Overview

OpenOps provides two interaction modes:
1. **CLI Commands** - One-shot operations via Typer
2. **Rich TUI** - Interactive chat interface for conversational workflows

## CLI Commands

### Command Reference

```bash
# Onboarding
openops init                              # Interactive setup wizard
openops init --provider anthropic         # Quick setup with provider

# Chat Interface
openops chat                              # Start TUI in current directory
openops chat /path/to/project             # Start TUI with project context
openops chat --model openai:gpt-4o        # Override model for session

# One-shot Operations
openops deploy                            # Deploy current project
openops deploy /path/to/project           # Deploy specific project
openops deploy --platform vercel          # Deploy to specific platform
openops deploy --dry-run                  # Show what would be deployed

# Monitoring (Phase 2)
openops monitor start                     # Start background daemon
openops monitor stop                      # Stop daemon
openops monitor status                    # Check daemon status
openops monitor logs                      # Stream daemon logs

# Configuration
openops config show                       # Show current config
openops config set KEY VALUE              # Set config value
openops config get KEY                    # Get config value
openops config reset                      # Reset to defaults

# Credentials
openops credentials add PLATFORM          # Add platform credentials
openops credentials list                  # List configured credentials
openops credentials remove PLATFORM       # Remove credentials

# Skills
openops skills list                       # List available skills
openops skills add PATH_OR_URL            # Add community skill
openops skills remove SKILL_NAME          # Remove skill
openops skills update                     # Update all skills

# Project Management
openops project init                      # Initialize OpenOps in project
openops project status                    # Show project analysis
openops project forget                    # Clear project memory

# Utilities
openops doctor                            # Check system health
openops version                           # Show version info
openops help [COMMAND]                    # Show help
```

### Command Examples

```bash
# First-time setup
$ openops init
Welcome to OpenOps! Let's set up your environment.

? Choose your LLM provider: Anthropic
? Enter your Anthropic API key: ****
? Enable auto-updates for skills? Yes

✓ Configuration saved to ~/.openops/config.yaml
✓ Credentials encrypted and stored

Run 'openops chat' to start chatting with OpenOps.

# Deploy a project
$ openops deploy --platform vercel
Analyzing project...
✓ Detected: Next.js 14 application
✓ Found: package.json, next.config.js
✗ Missing: vercel.json

? Generate vercel.json? Yes
✓ Generated vercel.json

? Deploy to Vercel? Yes
Deploying...
✓ Deployed successfully!

URL: https://my-app-abc123.vercel.app
Dashboard: https://vercel.com/user/my-app

# Check system health
$ openops doctor
OpenOps Health Check
────────────────────
Python:     ✓ 3.11.4
LangChain:  ✓ 1.0.2
Config:     ✓ ~/.openops/config.yaml
Credentials:
  - Anthropic: ✓ configured
  - Vercel:    ✓ configured
  - Railway:   ✗ not configured
Skills:     ✓ 5 loaded (3 built-in, 2 community)
```

## TUI Design

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ OpenOps v0.1.0                          [Project: /path/to/project] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Assistant: I'll analyze your project to understand its structure. │
│             One moment...                                           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Analyzing project...                                         │   │
│  │ ✓ Found package.json (Next.js 14)                           │   │
│  │ ✓ Found src/ directory with 23 components                   │   │
│  │ ✓ Found prisma/ directory (PostgreSQL)                      │   │
│  │ ✗ No deployment configuration found                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Assistant: I found a Next.js 14 project with Prisma for database. │
│             It's missing deployment config. Which platform would    │
│             you like to deploy to?                                  │
│                                                                     │
│             1. Vercel (recommended for Next.js)                     │
│             2. Railway                                              │
│             3. Render                                               │
│             4. Other (tell me which)                                │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ You: _                                                              │
├─────────────────────────────────────────────────────────────────────┤
│ [Ctrl+C] Exit  [↑↓] History  [Tab] Complete  [Ctrl+L] Clear        │
└─────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Library | Purpose |
|-----------|---------|---------|
| Header | Rich Panel | Show version and project context |
| Message Area | Rich Console | Display conversation with formatting |
| Progress | Rich Progress | Show ongoing operations |
| Input | Rich Prompt | User input with history |
| Status Bar | Rich Panel | Keyboard shortcuts and status |

### Implementation

```python
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner
from rich.markdown import Markdown

class OpenOpsTUI:
    def __init__(self, project_path: str | None = None):
        self.console = Console()
        self.project_path = project_path or os.getcwd()
        self.history: list[str] = []

    def run(self):
        """Main TUI loop."""
        self._show_header()

        while True:
            try:
                user_input = self._get_input()
                if user_input.lower() in ("exit", "quit", "q"):
                    break

                self._process_message(user_input)

            except KeyboardInterrupt:
                break

        self._show_goodbye()

    def _show_header(self):
        self.console.print(Panel(
            f"[bold blue]OpenOps[/bold blue] v0.1.0\n"
            f"Project: {self.project_path}",
            title="Welcome",
        ))

    def _get_input(self) -> str:
        return Prompt.ask("[bold green]You[/bold green]")

    def _process_message(self, message: str):
        # Show thinking indicator
        with Live(Spinner("dots", text="Thinking..."), refresh_per_second=10):
            response = self.agent.invoke({
                "messages": [{"role": "user", "content": message}]
            }, config=self.config)

        # Display response
        content = response["messages"][-1].content
        self.console.print(Panel(
            Markdown(content),
            title="[bold blue]OpenOps[/bold blue]",
            border_style="blue",
        ))

    def _show_progress(self, tasks: list[dict]):
        """Show progress for multi-step operations."""
        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
        ) as progress:
            for task in tasks:
                task_id = progress.add_task(task["name"])
                # Execute task
                progress.update(task_id, completed=True)
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Exit TUI |
| `↑` / `↓` | Navigate command history |
| `Tab` | Auto-complete commands |
| `Ctrl+L` | Clear screen |
| `Ctrl+D` | Send EOF (exit) |

### Rich Formatting

The TUI uses Rich for beautiful output:

```python
# Code blocks
self.console.print(Syntax(code, "python", theme="monokai"))

# Tables
table = Table(title="Services Found")
table.add_column("Name", style="cyan")
table.add_column("Type", style="green")
table.add_column("Path", style="yellow")
self.console.print(table)

# Progress
with Progress() as progress:
    task = progress.add_task("Deploying...", total=100)
    # Update progress...

# Confirmations
if Confirm.ask("Deploy to production?"):
    # Deploy
```

## User Flows

### First-Time User

```
1. openops init
   └─> Interactive setup wizard
       └─> Configure LLM provider
       └─> Set up credentials
       └─> Test connection

2. openops chat /path/to/project
   └─> Project analyzed automatically
       └─> Agent suggests next steps
```

### Deploy Flow

```
1. User: "Deploy to Vercel"
   └─> Agent analyzes project
       └─> Identifies missing configs
       └─> Generates vercel.json
       └─> Asks for confirmation
           └─> Deploys
               └─> Reports URL
```

### Error Recovery Flow

```
1. Deployment fails
   └─> Agent shows error
       └─> Analyzes cause
       └─> Suggests fix
           └─> User approves fix
               └─> Retry deployment
```

## Configuration File

```yaml
# ~/.openops/config.yaml
model:
  provider: anthropic
  name: claude-sonnet-4-5
  temperature: 0.1

tui:
  theme: monokai          # Code highlighting theme
  history_size: 1000      # Command history limit
  confirm_destructive: true
  show_thinking: true     # Show thinking indicator

cli:
  output_format: rich     # rich, json, plain
  color: auto             # auto, always, never

defaults:
  platform: vercel        # Default deployment platform
  dry_run: false
```

## Error Messages

User-friendly error messages:

```python
class OpenOpsError(Exception):
    def __init__(self, message: str, hint: str | None = None):
        self.message = message
        self.hint = hint

# Usage
raise OpenOpsError(
    "Vercel token not configured",
    hint="Run 'openops credentials add vercel' to configure"
)

# Display
self.console.print(Panel(
    f"[red]Error:[/red] {error.message}\n\n"
    f"[dim]Hint: {error.hint}[/dim]" if error.hint else "",
    title="Error",
    border_style="red",
))
```

## Accessibility

- Clear contrast ratios
- Screen reader compatible (plain text fallback)
- Keyboard-only navigation
- No color-only information

## Next Steps

- [05-project-analysis.md](./05-project-analysis.md) - How projects are analyzed
- [06-deployment-flow.md](./06-deployment-flow.md) - Deployment process details
