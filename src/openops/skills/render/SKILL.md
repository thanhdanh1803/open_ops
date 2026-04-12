---
name: render
description: Deploy web services, static sites, and workers to Render using the Render CLI
version: 2.0.0
author: OpenOps Team
risk_level: write
platforms:
  - render
requires:
  cli: render
  install: npm install -g @render-oss/cli
---

# Render Deployment Skill

## When to Use

Use this skill when:
- User wants to deploy web services, APIs, or static sites
- User needs background workers or cron jobs
- User mentions Render as the target platform
- User wants simple, managed infrastructure with free tier
- User needs PostgreSQL or Redis databases

## Prerequisites

### 1. CLI Installation

```bash
npm install -g @render-oss/cli
```

Or using Homebrew (macOS):
```bash
brew install render
```

Verify installation:
```bash
render --version
```

### 2. Authentication

Set up an API key for CLI access:

1. Go to https://dashboard.render.com/u/settings#api-keys
2. Create a new API key
3. Set it as environment variable:

```bash
export RENDER_API_KEY=rnd_xxxxxxxxxxxxx
```

Or configure in CLI:
```bash
render config set api-key rnd_xxxxxxxxxxxxx
```

To verify authentication:
```bash
render services list
```

**Expected output (authenticated):**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ Services                                                                │
├──────────────────┬────────────────┬──────────┬──────────────────────────┤
│ Name             │ Type           │ Status   │ URL                      │
├──────────────────┼────────────────┼──────────┼──────────────────────────┤
│ my-api           │ Web Service    │ Live     │ https://my-api.onrender  │
└──────────────────┴────────────────┴──────────┴──────────────────────────┘
```

**Expected output (not authenticated):**
```
Error: No API key configured. Set RENDER_API_KEY or run 'render config set api-key'
```

If not authenticated:
1. Inform user that Render requires an API key from the dashboard
2. Offer to open the API key page: https://dashboard.render.com/u/settings#api-keys
3. Once user provides the API key, execute: `render config set api-key <key>`
4. Verify with `render services list`

## Supported Service Types

| Type | Description | Use Case |
|------|-------------|----------|
| `web_service` | HTTP server with public URL | APIs, web apps |
| `static_site` | Static file hosting | SPAs, documentation |
| `background_worker` | Non-HTTP service | Job processors, bots |
| `private_service` | Internal service | Microservices |

## Supported Frameworks

Render auto-detects and builds:

| Framework | Language | Build Command | Start Command |
|-----------|----------|---------------|---------------|
| Next.js | Node.js | `npm run build` | `npm start` |
| Express | Node.js | `npm install` | `node index.js` |
| FastAPI | Python | `pip install -r requirements.txt` | `uvicorn main:app` |
| Django | Python | `pip install -r requirements.txt` | `gunicorn app.wsgi` |
| Flask | Python | `pip install -r requirements.txt` | `gunicorn app:app` |
| Go | Go | `go build -o app` | `./app` |
| Rust | Rust | `cargo build --release` | `./target/release/app` |

## CLI Commands

### List Services

```bash
render services list
```

**Expected output:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ Services                                                                │
├──────────────────┬────────────────┬──────────┬──────────────────────────┤
│ Name             │ Type           │ Status   │ URL                      │
├──────────────────┼────────────────┼──────────┼──────────────────────────┤
│ my-api           │ Web Service    │ Live     │ https://my-api.onrender  │
│ my-worker        │ Background     │ Live     │ -                        │
│ my-site          │ Static Site    │ Live     │ https://my-site.onrender │
└──────────────────┴────────────────┴──────────┴──────────────────────────┘
```

### Get Service Details

```bash
render services show --name <service-name>
```

Or by ID:
```bash
render services show --id srv-xxxxxxxxxxxxx
```

### Trigger Deploy

For an existing service, trigger a new deployment:

```bash
render deploys create --service-id srv-xxxxxxxxxxxxx
```

Or by service name:
```bash
render deploys create --service-name my-api
```

**Expected output:**
```
Deployment triggered successfully.
Deployment ID: dep-xxxxxxxxxxxxx
Status: build_in_progress
```

### List Deployments

```bash
render deploys list --service-id srv-xxxxxxxxxxxxx
```

**Expected output:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ Deployments for my-api                                                  │
├──────────────────┬────────────────┬──────────────────────────────────────┤
│ ID               │ Status         │ Created                              │
├──────────────────┼────────────────┼──────────────────────────────────────┤
│ dep-abc123       │ live           │ 2024-01-15 10:30:00                  │
│ dep-xyz789       │ deactivated    │ 2024-01-14 09:15:00                  │
└──────────────────┴────────────────┴──────────────────────────────────────┘
```

### View Logs

```bash
render logs --service-id srv-xxxxxxxxxxxxx
```

With follow:
```bash
render logs --service-id srv-xxxxxxxxxxxxx --tail
```

### Set Environment Variables

```bash
render env set --service-id srv-xxxxxxxxxxxxx KEY=value
```

### List Environment Variables

```bash
render env list --service-id srv-xxxxxxxxxxxxx
```

### Create Service via Blueprint

Using a `render.yaml` file:

```bash
render blueprint launch
```

This creates all services defined in `render.yaml`.

## Deployment Steps

### 0. Check CLI Installation

```bash
render --version
```

If CLI not installed:
1. Ask user for permission to install
2. Execute: `npm install -g @render-oss/cli` (or `brew install render` on macOS)
3. Verify installation with `render --version`

### 1. Check Authentication

```bash
render services list
```

If error about API key:
1. Inform user that Render requires an API key from the dashboard
2. Open or direct to: https://dashboard.render.com/u/settings#api-keys
3. Once user provides the API key, execute: `render config set api-key <key>`
4. Verify with `render services list`

### 2. List Existing Services

```bash
render services list
```

### 3. Deploy

For existing service:
```bash
render deploys create --service-name <name>
```

For new service, guide user to:
1. Create `render.yaml` blueprint
2. Run `render blueprint launch`

Or create via dashboard and then trigger deploy via CLI.

### 4. Verify Deployment

```bash
render deploys list --service-name <name>
```

Check latest deployment status is `live`.

## Instance Types and Pricing

| Type | RAM | CPU | Use Case |
|------|-----|-----|----------|
| free | 512 MB | Shared | Development, testing |
| starter | 512 MB | 0.5 | Low-traffic apps |
| standard | 2 GB | 1 | Production apps |
| pro | 4 GB | 2 | High-traffic apps |
| pro_plus | 8 GB | 4 | Resource-intensive |

Free tier limitations:
- Spins down after 15 min inactivity
- 750 hours/month
- No custom domains

## Error Handling

| Error Output | Cause | Action |
|--------------|-------|--------|
| `No API key configured` | Not authenticated | Guide user to create API key, then execute `render config set api-key <key>` |
| `Service not found` | Wrong name/ID | Execute `render services list` to find correct service |
| `Deployment failed` | Build error | Execute `render logs` to diagnose, then fix |
| `Rate limited` | Too many requests | Wait briefly, then retry |
| `command not found: render` | CLI not installed | Ask permission, then install CLI |

## Output Parsing

### Service List

Parse table output for:
- Service name (first column)
- Service type (second column)
- Status: `Live`, `Deploying`, `Failed`

### Deployment Status

Look for:
- `Status: live` - deployment successful
- `Status: build_in_progress` - still building
- `Status: failed` - deployment failed

### Logs

Check for:
- `Error:` or `error:` lines
- Stack traces
- Exit codes

## render.yaml Blueprint

For Infrastructure as Code:

```yaml
services:
  - type: web
    name: my-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: my-db
          property: connectionString

databases:
  - name: my-db
    plan: free
```

## Health Checks

Render performs health checks on web services:
- Default path: `/`
- Custom path: Set in dashboard or render.yaml
- Timeout: 30 seconds
- Unhealthy threshold: 3 consecutive failures

Implement a `/health` endpoint:
```python
@app.get("/health")
def health():
    return {"status": "healthy"}
```

## Example Conversations

**Deploy web service (CLI not installed):**
```
User: "Deploy my Express API to Render"
Agent: [executes: render --version]
Agent: "Render CLI is not installed. May I install it for you?"
User: "Yes"
Agent: [executes: npm install -g @render-oss/cli]
Agent: "CLI installed. Checking authentication..."
Agent: [executes: render services list]
Agent: "Render requires an API key. Please create one at:
https://dashboard.render.com/u/settings#api-keys
Then share the key with me."
User: "Here it is: rnd_xxxxxxxxxxxxx"
Agent: [executes: render config set api-key rnd_xxxxxxxxxxxxx]
Agent: "API key configured. Checking services..."
Agent: [executes: render services list]
Agent: "Found existing service 'my-api'. Triggering deployment..."
Agent: [executes: render deploys create --service-name my-api]
Agent: "Deployment triggered! Your API will be live at https://my-api.onrender.com"
```

**Deploy web service (already set up):**
```
User: "Deploy my Express API to Render"
Agent: [executes: render services list]
Agent: "Found existing service 'my-api'. Triggering deployment..."
Agent: [executes: render deploys create --service-name my-api]
Agent: "Deployment triggered! Checking status..."
Agent: [executes: render deploys list --service-name my-api]
Agent: "Build in progress. Your API will be live at https://my-api.onrender.com once complete."
```

**Check deployment status:**
```
User: "What's the status of my Render deployment?"
Agent: [executes: render deploys list --service-name my-api]
Agent: "Latest deployment:
- Status: live
- Deployed: 5 minutes ago"
```

## Best Practices

1. **Use health checks** for automatic recovery
2. **Set start command explicitly** for reliable builds
3. **Use environment groups** for shared config
4. **Enable auto-deploy** for CI/CD workflow (configure in dashboard)
5. **Upgrade from free tier** for production (no spin-down)
6. **Use render.yaml** for reproducible infrastructure
