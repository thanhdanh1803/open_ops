---
name: render-deploy
description: Deploy web services, static sites, and workers to Render
version: 1.0.0
author: OpenOps Team
risk_level: write
platforms:
  - render
requires:
  credentials:
    - OPENOPS_RENDER_API_KEY
  tools:
    - render_deploy
    - render_list_services
    - render_get_deployments
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

1. User must have a Render account
2. OPENOPS_RENDER_API_KEY must be configured
3. Git repository must be accessible to Render

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

## Deployment Steps

### 1. Analyze Project

Check for:
- `package.json` (Node.js)
- `requirements.txt` / `pyproject.toml` (Python)
- `go.mod` (Go)
- `Cargo.toml` (Rust)
- `render.yaml` (Blueprint spec)

### 2. Determine Service Type

Based on project analysis:
- Has HTTP server → `web_service`
- Has `build` output, no server → `static_site`
- Has worker/queue processing → `background_worker`
- Internal API only → `private_service`

### 3. Deploy Service

Use `render_deploy` with:
- `service_name`: Name for the service
- `service_type`: One of the supported types
- `git_repo`: GitHub repository URL
- `branch`: Branch to deploy (default: main)
- `environment_variables`: Required env vars
- `build_command`: Custom build command
- `start_command`: Custom start command

### 4. Verify Deployment

Use `render_get_deployments` to check:
- Deployment status (live, build_in_progress, failed)
- Build logs if failed
- Deployment URL

## Available Tools

### render_deploy

Create and deploy a new service to Render.

**Parameters:**
- `service_name` (required): Name for the Render service
- `service_type` (required): Type (web_service, static_site, background_worker, private_service)
- `git_repo` (required): Git repository URL
- `branch`: Git branch (default: main)
- `environment_variables`: Dict of environment variables
- `build_command`: Custom build command
- `start_command`: Custom start command
- `health_check_path`: Health check endpoint path
- `instance_type`: Instance type (free, starter, standard, pro, etc.)
- `auto_deploy`: Enable auto-deploy on push (default: true)

### render_list_services

List all services in the user's Render account.

**Parameters:**
- `service_type`: Filter by type
- `limit`: Maximum services to return (default: 20)

### render_get_deployments

Get deployment history for a service.

**Parameters:**
- `service_id` (required): Render service ID
- `limit`: Number of deployments (default: 10)

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

| Error | Cause | Solution |
|-------|-------|----------|
| `MISSING_CREDENTIALS` | No API key | Configure OPENOPS_RENDER_API_KEY |
| `INVALID_SERVICE_TYPE` | Wrong type value | Use valid service type |
| `repo not accessible` | Git permission issue | Connect GitHub to Render |
| `build failed` | Build error | Check build logs |
| `out of memory` | App exceeds plan limits | Upgrade instance type |

## Environment Variables

Render environment variables:
- Set per-service or in environment groups
- Can be marked as secret (hidden in dashboard)
- Available at build and runtime

Common auto-injected variables:
- `PORT`: Port to bind (always use this)
- `RENDER`: Set to `true` on Render
- `RENDER_SERVICE_ID`: Service ID
- `RENDER_EXTERNAL_URL`: Public URL

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
- Custom path: Set `health_check_path`
- Timeout: 30 seconds
- Unhealthy threshold: 3 consecutive failures

Implement a `/health` endpoint:
```python
@app.get("/health")
def health():
    return {"status": "healthy"}
```

## Example Conversations

**Deploy web service:**
```
User: "Deploy my Express API to Render"
Agent: "I'll create a web service from your repository. What's your GitHub repo URL?"
User: "https://github.com/user/my-api"
Agent: "Creating web service 'my-api' on Render's free tier..."
Agent: "Deployed! Your API will be live at https://my-api.onrender.com once build completes."
```

**Deploy static site:**
```
User: "Deploy my React app to Render"
Agent: "I'll deploy this as a static site. Using the 'build' directory for output."
Agent: "Static site 'my-app' deployed to https://my-app.onrender.com"
```

**Check deployment status:**
```
User: "What's the status of my Render deployment?"
Agent: "Checking recent deployments..."
Agent: "Latest deployment:
- Status: live
- Commit: abc1234 ('Add user auth')
- Deployed: 5 minutes ago"
```

## Best Practices

1. **Use health checks** for automatic recovery
2. **Set start command explicitly** for reliable builds
3. **Use environment groups** for shared config
4. **Enable auto-deploy** for CI/CD workflow
5. **Upgrade from free tier** for production (no spin-down)
6. **Use render.yaml** for reproducible infrastructure
