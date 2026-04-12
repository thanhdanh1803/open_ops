---
name: vercel-deploy
description: Deploy frontend applications to Vercel
version: 1.0.0
author: OpenOps Team
risk_level: write
platforms:
  - vercel
requires:
  credentials:
    - OPENOPS_VERCEL_TOKEN
  tools:
    - vercel_deploy
    - vercel_list_projects
    - vercel_get_deployments
---

# Vercel Deployment Skill

## When to Use

Use this skill when:
- User wants to deploy a frontend or fullstack application
- Project is built with Next.js, React, Vue, Nuxt, Vite, or static HTML
- User mentions Vercel as the target platform
- User wants serverless deployment with edge functions

## Prerequisites

1. User must have a Vercel account
2. OPENOPS_VERCEL_TOKEN must be configured
3. For Git deployments: repository must be accessible to Vercel

## Supported Frameworks

| Framework | Auto-detected | Build Command | Output Directory |
|-----------|---------------|---------------|------------------|
| Next.js | Yes | `next build` | `.next` |
| Create React App | Yes | `npm run build` | `build` |
| Vue CLI | Yes | `npm run build` | `dist` |
| Vite | Yes | `npm run build` | `dist` |
| Nuxt | Yes | `nuxt build` | `.nuxt` |
| Astro | Yes | `npm run build` | `dist` |
| SvelteKit | Yes | `npm run build` | `.svelte-kit` |

## Deployment Steps

### 1. Analyze Project

Before deploying, check:
- `package.json` for framework detection
- Existing `vercel.json` configuration
- Required environment variables

### 2. Check for Existing Configuration

If `vercel.json` exists, validate it. Common structure:

```json
{
  "version": 2,
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next"
}
```

### 3. Deploy

Use `vercel_deploy` tool with:
- `project_name`: Name for the Vercel project
- `git_repo`: GitHub repository URL (recommended for CI/CD)
- `production`: Whether to deploy to production domain
- `environment_variables`: Required env vars
- `framework`: Framework preset if not auto-detected

### 4. Verify Deployment

After deployment, use `vercel_get_deployments` to check:
- Deployment state (READY, BUILDING, ERROR)
- Deployment URL
- Build logs if there are errors

## Available Tools

### vercel_deploy

Deploy a project to Vercel.

**Parameters:**
- `project_name` (required): Name for the Vercel project
- `git_repo`: Git repository URL for CI/CD integration
- `production`: Deploy to production (default: false for preview)
- `environment_variables`: Dict of environment variables
- `framework`: Framework preset (nextjs, vite, etc.)
- `build_command`: Custom build command
- `output_directory`: Custom output directory

### vercel_list_projects

List all projects in the user's Vercel account.

**Parameters:**
- `limit`: Maximum projects to return (default: 20)

### vercel_get_deployments

Get recent deployments for a project.

**Parameters:**
- `project_name` (required): Name of the Vercel project
- `limit`: Number of deployments (default: 10)
- `state`: Filter by state (READY, ERROR, BUILDING, QUEUED, CANCELED)

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `MISSING_CREDENTIALS` | No Vercel token | Configure OPENOPS_VERCEL_TOKEN |
| `forbidden` | Token lacks permissions | Generate new token with correct scopes |
| `not_found` | Project doesn't exist | Create project first or check name |
| `rate_limited` | Too many API requests | Wait and retry |

## Environment Variables

Vercel environment variables can be scoped to:
- `production`: Only production deployments
- `preview`: Only preview/staging deployments
- `development`: Local development with `vercel dev`

Set all three targets for variables needed everywhere.

## Example Conversations

**Simple deployment:**
```
User: "Deploy my project to Vercel"
Agent: "I'll check your project structure first..."
Agent: "Found a Next.js project. Creating Vercel project 'my-app'. Proceed?"
User: "Yes"
Agent: "Deployed! Your app is live at https://my-app.vercel.app"
```

**With environment variables:**
```
User: "Deploy to Vercel with my API key"
Agent: "I'll deploy with the environment variable. What's the variable name and value?"
User: "NEXT_PUBLIC_API_URL=https://api.example.com"
Agent: "Deploying with NEXT_PUBLIC_API_URL set..."
```

## Best Practices

1. **Use Git integration** for production apps - enables automatic deployments
2. **Preview deployments** for PRs - deploy with `production: false`
3. **Environment variables** - use Vercel's encrypted storage, not `.env` files
4. **Monorepos** - set `rootDirectory` in vercel.json for specific app
