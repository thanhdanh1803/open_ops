# Deployment Flow

## Overview

The deployment flow takes a project from analysis through configuration generation to live deployment. It's designed to be conversational, with the agent explaining each step and asking for confirmation at key points.

## High-Level Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Analysis   │ ──▶ │   Planning   │ ──▶ │  Generation  │ ──▶ │  Deployment  │
│              │     │              │     │              │     │              │
│ - Scan proj  │     │ - Select     │     │ - Create     │     │ - Call API   │
│ - Detect     │     │   platform   │     │   configs    │     │ - Monitor    │
│   stack      │     │ - Map        │     │ - Validate   │     │   progress   │
│ - Find       │     │   services   │     │ - Preview    │     │ - Report     │
│   services   │     │ - Plan deps  │     │              │     │   results    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                      │
                                                                      ▼
                                                               ┌──────────────┐
                                                               │   Followup   │
                                                               │              │
                                                               │ - Save URLs  │
                                                               │ - Setup      │
                                                               │   monitoring │
                                                               │ - Suggest    │
                                                               │   next steps │
                                                               └──────────────┘
```

## Detailed Sequence

```
User                    Orchestrator              Analyzer                Deploy Agent           Platform
  │                          │                        │                        │                    │
  │ "Deploy to Vercel"       │                        │                        │                    │
  │─────────────────────────▶│                        │                        │                    │
  │                          │                        │                        │                    │
  │                          │ task(analyze)          │                        │                    │
  │                          │───────────────────────▶│                        │                    │
  │                          │                        │                        │                    │
  │                          │                        │ glob, read_file        │                    │
  │                          │                        │◀──────────────────────▶│                    │
  │                          │                        │                        │                    │
  │                          │      ProjectAnalysis   │                        │                    │
  │                          │◀───────────────────────│                        │                    │
  │                          │                        │                        │                    │
  │ "Found Next.js app..."   │                        │                        │                    │
  │◀─────────────────────────│                        │                        │                    │
  │                          │                        │                        │                    │
  │ "Yes, proceed"           │                        │                        │                    │
  │─────────────────────────▶│                        │                        │                    │
  │                          │                        │                        │                    │
  │                          │ task(deploy, vercel)   │                        │                    │
  │                          │──────────────────────────────────────────────▶ │                    │
  │                          │                        │                        │                    │
  │                          │                        │                        │ write_file         │
  │                          │                        │                        │ (vercel.json)      │
  │                          │                        │                        │                    │
  │                          │                        │                        │ vercel_deploy      │
  │                          │                        │                        │───────────────────▶│
  │                          │                        │                        │                    │
  │                          │                        │                        │    Deployment URL  │
  │                          │                        │                        │◀───────────────────│
  │                          │                        │                        │                    │
  │                          │                  DeployResult                   │                    │
  │                          │◀────────────────────────────────────────────────│                    │
  │                          │                        │                        │                    │
  │ "Deployed! URL: ..."     │                        │                        │                    │
  │◀─────────────────────────│                        │                        │                    │
  │                          │                        │                        │                    │
```

## Phase Details

### Phase 1: Analysis

See [05-project-analysis.md](./05-project-analysis.md) for full details.

**Output:**
- List of services with tech stacks
- Existing deployment configs
- Missing configs needed
- Environment variables required

### Phase 2: Planning

The orchestrator creates a deployment plan:

```python
@dataclass
class DeploymentPlan:
    services: list[ServiceDeployPlan]
    platform: str
    requires_approval: bool
    estimated_steps: int
    warnings: list[str]

@dataclass
class ServiceDeployPlan:
    service_name: str
    platform_config: dict
    config_files_to_generate: list[str]
    env_vars_needed: list[str]
    dependencies: list[str]  # Other services to deploy first
```

**Example Plan:**

```
Deployment Plan for my-saas to Vercel:

1. API Service (apps/api)
   - Generate: vercel.json
   - Env vars needed: DATABASE_URL, JWT_SECRET
   - Deploy as: Serverless Function

2. Web Service (apps/web)
   - Generate: vercel.json
   - Env vars needed: NEXT_PUBLIC_API_URL
   - Depends on: API (needs URL for env var)
   - Deploy as: Next.js App

⚠️ Warnings:
- DATABASE_URL not configured - you'll need to set this in Vercel dashboard
- Redis (REDIS_URL) not available on Vercel - consider Railway for this service
```

### Phase 3: Configuration Generation

Generate platform-specific configuration files.

#### Vercel Config Generation

```python
def generate_vercel_config(service: ServiceInfo) -> dict:
    """Generate vercel.json for a service."""

    config = {"version": 2}

    if service.framework == "nextjs":
        # Next.js auto-detected by Vercel, minimal config needed
        config["framework"] = "nextjs"

    elif service.framework == "fastapi":
        config["builds"] = [{
            "src": "main.py",
            "use": "@vercel/python"
        }]
        config["routes"] = [{
            "src": "/(.*)",
            "dest": "main.py"
        }]

    # Add environment variable references
    if service.env_vars:
        config["env"] = {
            var: f"@{var.lower()}"  # Reference Vercel env var
            for var in service.env_vars
        }

    return config
```

#### Railway Config Generation

```python
def generate_railway_config(service: ServiceInfo) -> str:
    """Generate railway.toml for a service."""

    config = {
        "[build]": {},
        "[deploy]": {},
    }

    if service.build_command:
        config["[build]"]["builder"] = "nixpacks"
        config["[build]"]["buildCommand"] = service.build_command

    if service.start_command:
        config["[deploy]"]["startCommand"] = service.start_command

    if service.port:
        config["[deploy]"]["healthcheckPath"] = "/"
        config["[deploy]"]["healthcheckTimeout"] = 30

    return toml.dumps(config)
```

### Phase 4: Deployment

Execute deployment using platform skills.

```python
async def execute_deployment(
    plan: DeploymentPlan,
    approve_fn: Callable[[str], bool],
) -> DeploymentResult:
    """Execute a deployment plan."""

    results = []

    # Sort services by dependencies (topological sort)
    sorted_services = topological_sort(plan.services)

    for service_plan in sorted_services:
        # Generate config files
        for config_file in service_plan.config_files_to_generate:
            content = generate_config(service_plan, config_file)
            write_file(config_file, content)

        # Request approval if needed
        if plan.requires_approval:
            if not approve_fn(f"Deploy {service_plan.service_name}?"):
                return DeploymentResult(
                    success=False,
                    message="Deployment cancelled by user"
                )

        # Execute deployment
        skill = get_skill_for_platform(plan.platform)
        result = await skill.deploy(
            project_path=service_plan.path,
            config=service_plan.platform_config,
        )

        results.append(result)

        # Update env vars for dependent services
        if result.success and result.url:
            update_dependent_env_vars(
                service_plan.service_name,
                result.url,
                sorted_services,
            )

    return DeploymentResult(
        success=all(r.success for r in results),
        services=results,
    )
```

### Phase 5: Followup

After successful deployment:

```python
async def deployment_followup(result: DeploymentResult):
    """Post-deployment actions."""

    # 1. Save deployment to memory
    for service_result in result.services:
        memory.save_deployment(
            service_name=service_result.service_name,
            platform=service_result.platform,
            url=service_result.url,
            deployed_at=datetime.now(),
        )

    # 2. Suggest monitoring setup
    if not monitoring_enabled():
        suggest_monitoring()

    # 3. Provide next steps
    return f"""
Deployment complete! 🎉

URLs:
{format_urls(result)}

Suggested next steps:
1. Verify your app is working at the URLs above
2. Configure environment variables in {platform} dashboard
3. Run `openops monitor start` to enable monitoring
"""
```

## Platform-Specific Flows

### Vercel

```
1. Create vercel.json if missing
2. Validate project structure
3. POST /v13/deployments
4. Poll for deployment completion
5. Return deployment URL
```

### Railway

```
1. Create railway.toml if missing
2. Link project to Railway (or create new)
3. Push via Railway CLI or GraphQL API
4. Wait for build completion
5. Return deployment URL
```

### Render

```
1. Create render.yaml if missing
2. Create/update service via API
3. Trigger deploy
4. Monitor build logs
5. Return deployment URL
```

## Error Handling

### Common Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| `MISSING_CREDENTIALS` | API token not configured | `openops credentials add <platform>` |
| `BUILD_FAILED` | Build error in project | Show build logs, suggest fixes |
| `INVALID_CONFIG` | Bad deployment config | Validate and regenerate |
| `RATE_LIMITED` | Too many API calls | Exponential backoff retry |
| `QUOTA_EXCEEDED` | Platform limits reached | Suggest upgrade or alternative |

### Error Recovery Flow

```python
async def deploy_with_recovery(plan: DeploymentPlan) -> DeploymentResult:
    """Deploy with automatic error recovery."""

    max_retries = 3

    for attempt in range(max_retries):
        try:
            result = await execute_deployment(plan)
            if result.success:
                return result

            # Analyze failure
            if result.error_type == "BUILD_FAILED":
                # Ask user if they want to see logs
                if user_wants_logs():
                    show_build_logs(result.build_logs)

                # Suggest fixes
                fixes = analyze_build_error(result.build_logs)
                if fixes:
                    present_fixes(fixes)

            return result

        except RateLimitError:
            wait_time = 2 ** attempt  # Exponential backoff
            await asyncio.sleep(wait_time)

        except CredentialsError as e:
            return DeploymentResult(
                success=False,
                error_type="MISSING_CREDENTIALS",
                message=f"Please run: openops credentials add {e.platform}"
            )

    return DeploymentResult(
        success=False,
        error_type="MAX_RETRIES",
        message="Deployment failed after multiple attempts"
    )
```

## Multi-Service Deployment

For monorepos with multiple services:

```python
def plan_multi_service_deployment(
    analysis: ProjectAnalysis,
    platform: str,
) -> DeploymentPlan:
    """Plan deployment for multiple services."""

    service_plans = []

    # Build dependency graph
    dep_graph = build_dependency_graph(analysis.services)

    # Determine deployment order
    order = topological_sort(dep_graph)

    for service_name in order:
        service = get_service(analysis, service_name)

        # Determine if service is compatible with platform
        if not is_compatible(service, platform):
            # Suggest alternative
            alt_platform = suggest_platform(service)
            warnings.append(
                f"{service_name} may be better suited for {alt_platform}"
            )

        service_plans.append(ServiceDeployPlan(
            service_name=service_name,
            platform_config=generate_platform_config(service, platform),
            config_files_to_generate=get_required_configs(service, platform),
            env_vars_needed=service.env_vars,
            dependencies=dep_graph.get(service_name, []),
        ))

    return DeploymentPlan(
        services=service_plans,
        platform=platform,
        requires_approval=True,
        estimated_steps=len(service_plans) * 3,  # config + deploy + verify
        warnings=warnings,
    )
```

## Next Steps

- [07-monitoring.md](./07-monitoring.md) - Post-deployment monitoring
- [03-skills.md](./03-skills.md) - Platform skill implementation details
