---
name: vercel
description: Deploy frontend applications to Vercel using the Vercel CLI
metadata:
  version: 2.0.0
  author: OpenOps Team
risk_level: write
platforms:
  - vercel
requires:
  cli: vercel
  install: npm install -g vercel
---

# Vercel Deployment Skill

## When to Use

Use this skill when:
- User wants to deploy a frontend or fullstack application
- Project is built with Next.js, React, Vue, Nuxt, Vite, or static HTML
- User mentions Vercel as the target platform
- User wants serverless deployment with edge functions

## Prerequisites

### 1. CLI Installation

Verify installation:
```bash
vercel --version
```

```bash
npm install -g vercel
```


### 2. Authentication

The user must be logged in to Vercel CLI:

To check auth status:
```bash
vercel whoami
```

```bash
vercel login
```
If `VERCEL_TOKEN` is provided, above command will login through non-interactive mode.

Else, this's required to be ran in interactive mode to open the browser to authorize.

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

## CLI Commands

### Deploy Preview

Deploy to a preview URL (recommended for testing):

```bash
cd /path/to/project
vercel --yes
```

**Expected output:**
```
Vercel CLI 32.x.x
🔍  Inspect: https://vercel.com/team/project/xxx
✅  Preview: https://project-xxx.vercel.app
```

### Deploy Production

Deploy to the production domain:

```bash
cd /path/to/project
vercel --prod --yes
```

**Expected output:**
```
Vercel CLI 32.x.x
🔍  Inspect: https://vercel.com/team/project/xxx
✅  Production: https://project.vercel.app
```

### List Projects

```bash
vercel list
```

**Expected output:**
```
> 3 Deployments found under username

my-app      https://my-app.vercel.app         2h ago
my-api      https://my-api.vercel.app         1d ago
portfolio   https://portfolio.vercel.app       3d ago
```

### Get Project Info

```bash
vercel inspect <deployment-url>
```

### Set Environment Variables

```bash
vercel env add VARIABLE_NAME
```

Interactive prompt for value and target environments (production/preview/development).

For non-interactive:
```bash
echo "value" | vercel env add VARIABLE_NAME production
```

### List Environment Variables

```bash
vercel env ls
```

### Pull Environment Variables Locally

```bash
vercel env pull
```

Creates `.env.local` with all environment variables.

### Link to Existing Project

```bash
vercel link
```

Links current directory to an existing Vercel project.

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

If there are any placeholder-like or missing value (such as backend url, ...), figure out it by yourself from project analysis and deployment history.


### 3. Deploy

```bash
cd /path/to/project
vercel --yes              # Preview
vercel --prod --yes       # Production
```

### 5. Verify Deployment

Parse the output URL and confirm deployment is live.

## Error Handling

| Error Output | Cause | Action |
|--------------|-------|--------|
| `Error: Not authenticated` | Not logged in | Ask permission, then run `vercel login` in **interactive mode** (tmux) when no `VERCEL_TOKEN` is available; re-check with `vercel whoami` |
| `Error: No Project Settings found` | First deploy | Execute `vercel --yes` to set up |
| `Error: Build Failed` | Build error | Analyze build logs, then fix the issue |
| `Error: forbidden` | Token lacks permissions / wrong account | Ask permission, then run `vercel login` in **interactive mode** (tmux) to re-authenticate; re-check with `vercel whoami` |
| `command not found: vercel` | CLI not installed | Ask permission, then install CLI |

## Output Parsing

### Deployment Success

Look for lines containing:
- `✅  Preview:` or `✅  Production:` followed by URL
- `🔍  Inspect:` followed by dashboard URL

### Deployment Failure

Look for:
- `Error:` prefix
- `Build Failed` message
- Exit code non-zero

## Example Conversations

**Simple deployment (already set up):**
```
User: "Deploy my project to Vercel"
Agent: [executes: vercel whoami]
Agent: "You're logged in as user@example.com. Deploying to preview..."
Agent: [executes: vercel --yes]
Agent: "Deployed! Your app is live at https://project-xxx.vercel.app"
```

**Production deployment:**
```
User: "Deploy to production"
Agent: "Deploying to production..."
Agent: [executes: vercel --prod --yes]
Agent: "Production deployment complete! Live at https://project.vercel.app"
```

## Best Practices

1. **Use preview deployments** for testing before production
2. **Use `vercel link`** to connect to existing projects
3. **Environment variables** - use `vercel env` commands, not `.env` files in git
4. **Monorepos** - set `rootDirectory` in vercel.json for specific app
5. **Always use `--yes`** flag to skip confirmation prompts in automated workflows
