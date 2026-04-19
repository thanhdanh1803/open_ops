---
name: railway
description: Deploy backend services and databases to Railway using the Railway CLI
metadata:
  version: 2.1.0
  author: OpenOps Team
risk_level: write
platforms:
  - railway
requires:
  cli: railway
  install: npm install -g @railway/cli
---

# Railway Deployment Skill

## When to Use

Use this skill when:
- User wants to deploy backend services (APIs, workers) to Railway
- User needs managed databases (PostgreSQL, Redis, MongoDB) with Railway
- Project is built with Python, Node.js, Go, Rust, or other backend frameworks
- User mentions Railway as the target platform
- User needs infrastructure with persistent storage



## Prerequisites

### 1. CLI Installation

Verify installation:
```bash
railway --version
```

To in stall Railway CLI, using:

```bash
npm install -g @railway/cli
```

Or using Homebrew (macOS):
```bash
brew install railway
```

### 2. Authentication

The user must be logged in to Railway CLI:

Verify railway authentication by using

```bash
railway whoami
```

If not authenticated: try to login using non-interactive mode with `RAILWAY_TOKEN` / `RAILWAY_API_TOKEN` (when the user provides a token in the environment)

```bash
railway login
```

If this raise error because of non-interactive enviroment does not support, use `handling-interactive-commands` skill to handle the error and retry with the same command in tmux:

```bash
railway login
```

**Expected output (authenticated):**
```
Logged in as user@example.com (User ID: xxx)
```

## Supported Frameworks

Railway uses Nixpacks for automatic detection:

| Framework | Language | Auto-detected |
|-----------|----------|---------------|
| FastAPI | Python | Yes |
| Django | Python | Yes |
| Flask | Python | Yes |
| Express | Node.js | Yes |
| NestJS | Node.js | Yes |
| Gin | Go | Yes |
| Actix | Rust | Yes |
| Spring Boot | Java | Yes |

## Railway Concepts

### Projects
Container for related services. Think of it as an environment.

### Services
Individual deployable units within a project:
- **Web services**: HTTP servers with public URLs
- **Workers**: Background job processors
- **Databases**: Managed PostgreSQL, Redis, MongoDB, MySQL

### Environments
Each project has environments (production, staging, etc.) with isolated:
- Services
- Environment variables
- Databases

## CLI Commands

### Agent workflow (preferred): list → user chooses → non-interactive link and deploy

**Do not rely on interactive `railway link` or menu-driven deploy** when acting as an agent. Those prompts often break without a real TTY (e.g. “Available options can not be empty”). For deploy, use this flow:

1. **List projects (JSON)** — run from the directory you will deploy (or after `cd` into the service root):
   ```bash
   railway list --json
   ```
   Each entry includes **`workspace`** (id, name), **`id`** / **`name`** for the project, **`environments`**, and **`services`**. Use this to build a clear list for the user.

2. **Workspaces only** — if you need workspace ids/names separately:
   ```bash
   railway whoami --json
   ```
   The **`workspaces`** array lists **`id`** and **`name`** for each workspace.

3. **Ask the user to choose** — present **project** (name + id). If multiple **environments** or **services** apply, ask which **environment** (and **service** if needed) before running commands.

4. **Link without prompts** (creates/updates `.railway` in the current directory):
   ```bash
   railway link --workspace <workspace_id> --project <project_id_or_name> --environment <environment_name_or_id> [--service <service_name_or_id>] --json
   ```
   Omit **`--workspace`** when the account has a single workspace or the default is correct.

5. **Deploy** (after link):
   ```bash
   railway up
   ```
   Non-blocking logs:
   ```bash
   railway up --detach
   ```
   If your CLI supports deploying without a prior link in that directory, you may use:
   ```bash
   railway up --project <project_id> --environment <environment_name_or_id> [--service <service_name_or_id>]
   ```
   (When using **`--project`**, **`--environment`** is required per Railway docs.)

6. **Automation / CI** — prefer **`RAILWAY_TOKEN`** (project token) or **`RAILWAY_API_TOKEN`** per Railway docs; still use explicit **project**, **environment**, and **service** flags where applicable—do not depend on interactive menus.

### Disambiguation workflow (generic): list → present choices → user picks → retry with explicit flags

Railway CLIs frequently “block” when there are multiple valid targets (multiple **workspaces**, **projects**, **environments**, or **services**) and the command needs an explicit selection (e.g. it requires `--service`). As an agent, **never stop at a blocker message**. Instead, resolve ambiguity with a repeatable “choose one” loop.

#### When to trigger disambiguation

Trigger this workflow whenever you see any of the following patterns (stdout/stderr) or equivalent wording:
- The CLI mentions multiple targets and asks you to choose in a TUI/menu you can’t use.
- The CLI says a selection is required (e.g. “needs an explicit `--service`”, “please specify `--project`”, “environment is required”, “multiple workspaces found”).
- The CLI is “stuck” waiting for input or prints a prompt without a real TTY.

#### How to resolve (decision tree)

1. **Fetch canonical options (JSON)**:
   - Projects + environments + services (preferred):
     ```bash
     railway list --json
     ```
   - Workspaces (if needed separately):
     ```bash
     railway whoami --json
     ```

2. **Build an option set from the JSON**:
   - **Workspace**: `workspace.name` + `workspace.id`
   - **Project**: `project.name` + `project.id`
   - **Environment**: `environment.name` (and id if present)
   - **Service**: `service.name` (and id if present)

3. **Ask the user to choose** (always offer a numbered list):
   - If multiple **workspaces** exist and you can’t infer the right one, ask for workspace first.
   - Then ask for **project**.
   - Then ask for **environment** (if multiple exist, or if the command requires it).
   - Then ask for **service** (if multiple services exist, or if the command requires it).

4. **Retry using explicit flags (non-interactive)**:
   - Prefer linking the current directory first (creates/updates `.railway`), then run deploy:
     ```bash
     railway link --workspace <workspace_id> --project <project_id_or_name> --environment <environment_name_or_id> --service <service_name_or_id> --json
     ```
     Then:
     ```bash
     railway up
     ```
   - If you already know the target and your CLI supports it, you may deploy directly with flags:
     ```bash
     railway up --project <project_id> --environment <environment_name_or_id> --service <service_name_or_id>
     ```

#### Presentation template (use this verbatim shape)

When prompting the user, keep it short and deterministic:

```
I found multiple Railway <things>. Which one should I use?

1) <name> — <id>
2) <name> — <id>
...

Reply with the number (or paste the id/name).
```

If you need multiple picks (project + environment + service), ask them in one message:

```
Reply with:
- project: (number/id/name)
- environment: (name/id)
- service: (name/id)
```

### Link to Project

**Preferred:** non-interactive link (see **Agent workflow** above).

Interactive fallback (human in a real terminal only):

```bash
cd /path/to/project
railway link
```

Or create new project directly:
```bash
railway init
```

### List Projects

**For agents, always use JSON:**
```bash
railway list --json
```

Human-readable table (optional):
```bash
railway list
```

**Expected output (table):**
```
┌──────────────────────────────────┬─────────────────────────────────┐
│ Project                          │ ID                              │
├──────────────────────────────────┼─────────────────────────────────┤
│ my-app-prod                      │ abc123-def456-...               │
│ my-app-staging                   │ xyz789-uvw012-...               │
└──────────────────────────────────┴─────────────────────────────────┘
```

### Deploy Service

Deploy the current directory:

```bash
cd /path/to/project
railway up
```

**Expected output:**
```
☁️ Deploying from /path/to/project
☁️ Build logs available at https://railway.app/project/xxx/deployments/yyy

======= Build Succeeded =======

☁️ Deployment successful 🎉
```

With detached mode (don't stream logs):
```bash
railway up --detach
```

### Check Deployment Status

```bash
railway status
```

**Expected output:**
```
Project: my-app-prod (abc123)
Service: api
Environment: production

Latest Deployment:
  Status: SUCCESS
  URL: https://api-production.up.railway.app
  Deployed: 5 minutes ago
```

### View Logs

```bash
railway logs
```

With follow:
```bash
railway logs --follow
```

### Set Environment Variables

```bash
railway variables set KEY=value
```

Or multiple:
```bash
railway variables set KEY1=value1 KEY2=value2
```

### List Environment Variables

```bash
railway variables
```

**Expected output:**
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
PORT=3000
```

### Add Database

```bash
railway add
```

**Expected output:**
```
? What would you like to add?
  Empty Service
> PostgreSQL
  MySQL
  MongoDB
  Redis
```

### Open Dashboard

```bash
railway open
```

Opens the project in browser.

### Run Commands in Railway Environment

```bash
railway run <command>
```

Example - run migrations:
```bash
railway run python manage.py migrate
```

## Deployment Steps

### 0. Check CLI Installation

```bash
railway --version
```

If CLI not installed:
1. Ask user for permission to install
2. Execute: `npm install -g @railway/cli` (or `brew install railway` on macOS)
3. Verify installation with `railway --version`

### 1. Check Authentication

```bash
railway whoami
```

### 2. List projects and get user selection

```bash
railway list --json
```

Present projects (and environments/services from the JSON). **Ask the user which project** (and environment/service if needed) to use.

### 3. Link non-interactively

From the directory to deploy:

```bash
railway link --workspace <workspace_id> --project <project_id_or_name> --environment <environment_name_or_id> [--service <service_name_or_id>] --json
```

Avoid interactive **`railway link`** unless the user is at a real terminal and chooses that path.

### 4. Deploy

```bash
railway up
```

Use **`railway up --detach`** for non-blocking deploy. You may use **`railway up --project … --environment …`** without a prior **`railway link`** if the CLI version supports it and the situation calls for it.

### Alternative: new project (user wants create, not link)

```bash
railway init
```

Then run **`railway up`** (or **`railway up --detach`**) as in step 4.

### 5. Verify

```bash
railway status
```

## Database Deployment

Railway provides one-click database deployments:

| Database | Plugin Name | Default Port |
|----------|-------------|--------------|
| PostgreSQL | postgresql | 5432 |
| MySQL | mysql | 3306 |
| Redis | redis | 6379 |
| MongoDB | mongodb | 27017 |

Database connection strings are automatically injected as environment variables:
- `DATABASE_URL` for PostgreSQL/MySQL
- `REDIS_URL` for Redis
- `MONGO_URL` for MongoDB

## Error Handling

| Error Output | Cause | Action |
|--------------|-------|--------|
| `Not logged in` | Not authenticated | Ask permission, then run `railway login` in **interactive mode** (tmux) when no `RAILWAY_TOKEN` / `RAILWAY_API_TOKEN` is available; re-check with `railway whoami` |
| `No project linked` | Not linked to project | Run **`railway list --json`**, ask user to choose project/env/service, then **`railway link --project … --environment … [--workspace …] [--service …] --json`** (avoid interactive `railway link` in agent runs) |
| Mentions multiple projects/workspaces/environments or requires selection | Ambiguous target | Run **`railway list --json`** (and **`railway whoami --json`** if needed), present a numbered list, ask user to choose, then retry with explicit flags (`--workspace/--project/--environment/--service`) |
| Mentions “needs an explicit `--service`” (or similar) | Multiple services in the selected project/environment | From **`railway list --json`**, present services for the chosen project/env, ask user which service, then rerun **`railway link ... --service ... --json`** (or `railway up ... --service ...`) |
| Mentions environment required / multiple environments | Environment not specified or ambiguous | From **`railway list --json`**, list environments for the chosen project, ask user which environment, then rerun with `--environment ...` |
| `Build failed` | Build error | Execute `railway logs` to diagnose, then fix |
| `Project not found` | Invalid project | Run **`railway list --json`** and reconcile ids/names with the user |
| `command not found: railway` | CLI not installed | Ask permission, then install CLI |

## Output Parsing

### Deployment Success

Look for:
- `☁️ Deployment successful` or `Deployment successful 🎉`
- `======= Build Succeeded =======`

### Deployment Failure

Look for:
- `======= Build Failed =======`
- `Error:` prefix
- Exit code non-zero

### Status Check

Parse `railway status` output for:
- `Status: SUCCESS` or `Status: FAILED`
- `URL:` line for public URL

## Railway-Specific Configuration

### railway.json

Optional configuration file:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "npm run build"
  },
  "deploy": {
    "startCommand": "npm start",
    "healthcheckPath": "/health",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

### Procfile

Alternative for start command:

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
worker: python worker.py
```

## Example Conversations

**Deploy backend API (already set up):**
```
User: "Deploy my FastAPI backend to Railway"
Agent: [executes: railway whoami]
Agent: "You're logged in. Fetching projects..."
Agent: [executes: railway list --json]
Agent: "Projects: my-app-prod, my-app-staging. Which project and environment?"
User: "my-app-prod, production"
Agent: [executes: railway link --project my-app-prod --environment production --json]
Agent: [executes: railway up --detach]
Agent: "Deployed! Service is building. URL: https://api-production.up.railway.app"
```

**Deploy blocked because multiple services (requires `--service`):**
```
User: "Deploy my backend to Railway"
Agent: [executes: railway whoami]
Agent: "You're logged in. Listing projects/services so we can select the right target..."
Agent: [executes: railway list --json]
Agent: "I found multiple services in the selected project/environment. Which service should I deploy?

1) api — id …
2) worker — id …
3) postgres — id …

Reply with:
- project: (number/id/name)
- environment: (name/id)
- service: (number/id/name)"
User: "project: 1, environment: production, service: api"
Agent: [executes: railway link --project <id_or_name> --environment production --service api --json]
Agent: [executes: railway up --detach]
Agent: "Deploy started. I’ll report the build URL / public URL once it appears in `railway status`."
```

**Check deployment status:**
```
User: "What's the status of my Railway deployment?"
Agent: [executes: railway status]
Agent: "Your service is running:
- Status: SUCCESS
- URL: https://api-production.up.railway.app
- Deployed: 5 minutes ago"
```

## Best Practices

1. **Deploy flow** — **`railway list --json`** → user picks project (and env/service) → **`railway link … --json`** → **`railway up`**; avoid interactive CLI wizards in agent subprocesses
2. **Use environment variables** for configuration, never hardcode secrets
3. **Health checks** - implement `/health` endpoint for automatic restart
4. **Graceful shutdown** - handle SIGTERM for zero-downtime deploys
5. **Use `railway up --detach`** for non-blocking deployments
6. **Databases** - use Railway's managed databases for simplicity
