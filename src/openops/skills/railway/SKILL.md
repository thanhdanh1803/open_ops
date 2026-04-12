---
name: railway-deploy
description: Deploy backend services and databases to Railway using the Railway CLI
version: 2.0.0
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
- User wants to deploy backend services (APIs, workers)
- User needs managed databases (PostgreSQL, Redis, MongoDB)
- Project is built with Python, Node.js, Go, Rust, or other backend frameworks
- User mentions Railway as the target platform
- User needs infrastructure with persistent storage

## Prerequisites

### 1. CLI Installation

```bash
npm install -g @railway/cli
```

Or using Homebrew (macOS):
```bash
brew install railway
```

Verify installation:
```bash
railway --version
```

### 2. Authentication

The user must be logged in to Railway CLI:

```bash
railway login
```

This opens a browser for authentication.

To check auth status:
```bash
railway whoami
```

**Expected output (authenticated):**
```
Logged in as user@example.com (User ID: xxx)
```

**Expected output (not authenticated):**
```
Not logged in
```

If not authenticated:
1. Ask user for permission to authenticate
2. Execute `railway login` (this opens a browser for authentication)
3. Wait for authentication to complete, then verify with `railway whoami`

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

### Link to Project

First, link to an existing project or create a new one:

```bash
cd /path/to/project
railway link
```

**Expected output:**
```
? Select a project
  my-project-prod
> my-project-staging
  Create new project
```

Or create new project directly:
```bash
railway init
```

### List Projects

```bash
railway list
```

**Expected output:**
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

If not authenticated:
1. Ask user for permission to authenticate
2. Execute `railway login` (opens browser)
3. Verify with `railway whoami` after completion

### 2. Link or Create Project

```bash
railway link
```

Or list existing:
```bash
railway list
```

### 3. Deploy

```bash
cd /path/to/project
railway up
```

### 4. Verify

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
| `Not logged in` | Not authenticated | Ask permission, then execute `railway login` |
| `No project linked` | Not linked to project | Execute `railway link` to link/create project |
| `Build failed` | Build error | Execute `railway logs` to diagnose, then fix |
| `Project not found` | Invalid project | Execute `railway list` to find correct project |
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

**Deploy backend API (CLI not installed):**
```
User: "Deploy my FastAPI backend to Railway"
Agent: [executes: railway --version]
Agent: "Railway CLI is not installed. May I install it for you?"
User: "Yes"
Agent: [executes: npm install -g @railway/cli]
Agent: "CLI installed. Checking authentication..."
Agent: [executes: railway whoami]
Agent: "Not authenticated. May I run `railway login`? This will open a browser window."
User: "Go ahead"
Agent: [executes: railway login]
Agent: "Please complete authentication in the browser..."
Agent: [executes: railway whoami]
Agent: "Authenticated as user@example.com. Deploying..."
Agent: [executes: railway up]
Agent: "Deployed! Service is building at https://railway.app/project/xxx"
```

**Deploy backend API (already set up):**
```
User: "Deploy my FastAPI backend to Railway"
Agent: [executes: railway whoami]
Agent: "You're logged in. Deploying to project 'my-app-prod'..."
Agent: [executes: railway up]
Agent: "Deployed! Service is building. URL: https://api-production.up.railway.app"
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

1. **Use environment variables** for configuration, never hardcode secrets
2. **Health checks** - implement `/health` endpoint for automatic restart
3. **Graceful shutdown** - handle SIGTERM for zero-downtime deploys
4. **Use `railway up --detach`** for non-blocking deployments
5. **Databases** - use Railway's managed databases for simplicity
