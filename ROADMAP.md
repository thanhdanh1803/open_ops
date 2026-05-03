# OpenOps Roadmap

This roadmap is intentionally lightweight and oriented around user-visible capabilities of the CLI and agent runtimes.

## Near-term (next few iterations)

### Background task sink channels

OpenOps already has a pluggable sink layer for monitoring reports. Extend this idea so background tasks can publish to one or more channels consistently.

- **More monitoring sinks**:
  - Slack / Discord / Teams sink (post summary + severity)
  - Webhook sink (POST JSON `MonitoringReport`)
  - Email sink (digest / critical-only)
  - GitHub sink (create/update issue for repeated findings)
- **Sink configuration**:
  - Enable/disable sinks per project
  - Severity thresholds per sink (e.g. only `ERROR` to paging channels)
  - Retry policy + backoff for network sinks
- **Unify background events**:
  - Standardize a generic “background event” envelope (monitor tick, deploy result, skill install, doctor findings)
  - Let sinks subscribe to event types (not only monitoring reports)

### Multiple models for different purposes

The codebase already supports model providers and subagents; expand toward explicit model routing for cost/performance.

- **Per-subagent model selection**:
  - Use a cheaper/faster model for `project-analyzer` and routine monitoring ticks
  - Use a stronger model for deploy planning, risk evaluation, and high-impact decisions
- **Per-task model routing**:
  - Route based on tool category (filesystem traversal vs reasoning-heavy planning vs code generation)
  - Route based on budget limits / token caps
- **Fallbacks**:
  - If provider errors or rate limits, retry with a configured fallback model/provider

## Mid-term

- **Graph database for service relationships**:
  - Persist service dependency graphs (and “who calls who”) for richer queries
  - Power features like impact analysis, transitive dependents, and blast radius previews
- **Monitoring improvements**:
  - Better “interrupt pending” handling so daemon ticks can pause safely and resume once approved
  - Reporting diffs: highlight what changed since last tick
  - Per-service “watch rules” (log patterns, SLO checks, known false positives)
- **More platform coverage (testing + integrations)**:
  - Validate deploy + monitor flows across additional platforms and templates
  - Add compatibility checks and “known-good” example projects per platform
- **Observability**:
  - First-class tracing toggles and metadata conventions for all agent operations
  - Optional structured log output for daemon runs (machine parseable)
- **Grafana integration**:
  - Provision Grafana for a new project (datasources + dashboards bootstrap)
  - Generate/update dashboards based on detected services
  - Monitor logs/alerts via Grafana stack (e.g. Loki) and route incidents to sinks
- **Plugin story**:
  - Clear extension points for sinks, skills, and platform integrations
  - Example sink packages to use as references (webhook, slack)

## Longer-term

- **Auto-fix loops via external coding CLIs**:
  - Trigger Claude Code or Cursor CLI to attempt fixes for detected errors
  - Keep it safe: run in a clean workspace/branch and require explicit approval before applying changes
- **Isolated execution backends**:
  - Pluggable sandbox backends for safer command execution in automation contexts
- **Team usage**:
  - Shared project knowledge store (beyond local SQLite) with access controls
- **UX**:
  - Better TUI affordances for approvals, auditing, and “what will happen” previews
