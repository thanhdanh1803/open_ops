---
name: railway-deploy
description: Deploy backend services and databases to Railway
version: 1.0.0
author: OpenOps Team
risk_level: write
platforms:
  - railway
requires:
  credentials:
    - OPENOPS_RAILWAY_TOKEN
  tools:
    - railway_deploy
    - railway_list_projects
    - railway_list_services
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

1. User must have a Railway account
2. OPENOPS_RAILWAY_TOKEN must be configured
3. For Git deployments: GitHub account connected to Railway

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

## Deployment Steps

### 1. Identify or Create Project

First, check existing projects:
```
Use railway_list_projects to see available projects
```

If no suitable project exists, user needs to create one via Railway dashboard or CLI.

### 2. Analyze Service Requirements

Check for:
- `requirements.txt` or `pyproject.toml` (Python)
- `package.json` (Node.js)
- `go.mod` (Go)
- `Cargo.toml` (Rust)
- Database dependencies in code

### 3. Deploy Service

Use `railway_deploy` with:
- `project_id`: Target Railway project
- `service_name`: Name for the service
- `git_repo`: GitHub repository URL
- `environment_variables`: Required env vars
- `start_command`: Custom start command if needed

### 4. Configure Networking

Railway automatically:
- Assigns internal hostname: `service-name.railway.internal`
- Generates public domain on request
- Handles TLS certificates

### 5. Verify Deployment

Use `railway_list_services` to check:
- Deployment status (SUCCESS, BUILDING, FAILED)
- Service URL
- Recent logs

## Available Tools

### railway_deploy

Deploy a service to an existing Railway project.

**Parameters:**
- `project_id` (required): Railway project ID
- `service_name` (required): Name for the service
- `git_repo`: GitHub repository URL
- `environment_variables`: Dict of environment variables
- `start_command`: Custom start command
- `build_command`: Custom build command
- `root_directory`: Root directory for monorepos

### railway_list_projects

List all projects in the user's Railway account.

**Returns:** List of projects with IDs, names, and service counts.

### railway_list_services

List services in a specific project with their deployment status.

**Parameters:**
- `project_id` (required): Railway project ID

**Returns:** List of services with status, URLs, and deployment info.

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

| Error | Cause | Solution |
|-------|-------|----------|
| `MISSING_CREDENTIALS` | No Railway token | Configure OPENOPS_RAILWAY_TOKEN |
| `project not found` | Invalid project ID | Use railway_list_projects to find correct ID |
| `build failed` | Build error | Check build logs, verify dependencies |
| `port not detected` | App doesn't expose port | Set PORT env var or configure in railway.json |

## Environment Variables

Railway environment variables:
- Are encrypted at rest
- Automatically injected at runtime
- Can reference other variables: `${DATABASE_URL}`
- Support Railway-provided variables: `${{RAILWAY_STATIC_URL}}`

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

**Deploy backend API:**
```
User: "Deploy my FastAPI backend to Railway"
Agent: "Let me check your Railway projects..."
Agent: "Found project 'my-app-prod'. I'll create a service called 'api'. Proceed?"
User: "Yes"
Agent: "Deployed! Service 'api' is building. URL will be available shortly."
```

**Check deployment status:**
```
User: "What's the status of my Railway services?"
Agent: "Checking services in project..."
Agent: "Found 3 services:
- api: SUCCESS (https://api-production.up.railway.app)
- worker: SUCCESS (no public URL - internal service)
- postgres: SUCCESS (internal)"
```

## Best Practices

1. **Use environment variables** for configuration, never hardcode secrets
2. **Health checks** - implement `/health` endpoint for automatic restart
3. **Graceful shutdown** - handle SIGTERM for zero-downtime deploys
4. **Monorepos** - use `root_directory` to specify service location
5. **Databases** - use Railway's managed databases for simplicity
