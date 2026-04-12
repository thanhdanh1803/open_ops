# Roadmap

## Vision

OpenOps aims to be the go-to agentic DevOps assistant for developers, handling everything from initial deployment to ongoing monitoring and maintenance.

## Current State

**Version**: 0.1.0 (Pre-release)

The current codebase has basic foundations but needs significant work:
- Basic LangChain agent exists but not using Deep Agents
- Simple skills for Vercel, Railway, Render (partially implemented)
- CLI structure in place but missing TUI
- Memory system defined but not integrated

## Phase 1: Core Deployment (MVP)

**Target**: Functional deployment workflow for single-service projects

### Goals

- [ ] **Deep Agents Integration**
  - Migrate from basic LangChain to Deep Agents framework
  - Implement TodoListMiddleware for task planning
  - Implement FilesystemMiddleware for project access
  - Set up SubAgentMiddleware for specialized agents

- [ ] **Project Analysis**
  - Implement framework detection (Next.js, FastAPI, etc.)
  - Support single-service projects
  - Extract environment variable requirements
  - Identify missing deployment configs

- [ ] **Deployment Skills**
  - Vercel skill (complete implementation)
  - Railway skill (complete implementation)
  - Render skill (complete implementation)
  - Config file generation (vercel.json, railway.toml, etc.)

- [ ] **CLI/TUI**
  - Rich TUI for interactive chat
  - `openops init` for onboarding
  - `openops chat` for interactive mode
  - `openops deploy` for one-shot deployment

- [ ] **Memory**
  - SQLite-based project store
  - LangGraph Store for conversations
  - Cache project analysis results

### Deliverables

1. Working deployment for:
   - Next.js apps to Vercel
   - FastAPI apps to Railway
   - Static sites to Render
   
2. Interactive TUI experience
3. Basic documentation

### Success Criteria

- Deploy a Next.js project to Vercel via conversation
- Agent remembers project context across sessions
- Config files generated correctly

---

## Phase 2: Multi-Service & Monitoring Foundation

**Target**: Support for monorepos and basic monitoring

### Goals

- [ ] **Multi-Service Support**
  - Monorepo detection (Turborepo, Nx, Lerna)
  - Service dependency mapping
  - Coordinated multi-service deployment
  - Environment variable linking between services

- [ ] **Background Monitoring**
  - Monitor daemon implementation
  - Health check system
  - Log fetching from platforms
  - Basic alerting (Slack integration)

- [ ] **Enhanced Memory**
  - Project Knowledge Graph
  - Deployment history tracking
  - Service relationship mapping
  - Optional Neo4j support

- [ ] **More Platforms**
  - Fly.io skill
  - DigitalOcean App Platform skill
  - Docker Compose local deployment

### Deliverables

1. Deploy monorepo with frontend + backend
2. Background monitoring daemon
3. Slack alerting
4. Neo4j integration (optional)

### Success Criteria

- Deploy a Turborepo with 2 services to different platforms
- Receive Slack alert when service goes down
- Query deployment history via conversation

---

## Phase 3: Error Resolution & Self-Healing

**Target**: Detect, diagnose, and fix deployment issues

### Goals

- [ ] **Error Analysis**
  - Log pattern recognition
  - LLM-based error diagnosis
  - Root cause analysis
  - Fix suggestions

- [ ] **Integration with Code Agents**
  - Cursor CLI integration for fixes
  - Claude Code integration
  - Automated PR creation for fixes
  - Human approval workflow

- [ ] **Deployment Pipeline**
  - Pre-deployment validation
  - Rollback on failure
  - Canary deployments (where supported)
  - Health check before traffic switch

- [ ] **Enhanced Skills**
  - AWS ECS/EKS skill
  - GCP Cloud Run skill
  - Kubernetes (k8s) manifests
  - Terraform integration

### Deliverables

1. Automatic error detection and diagnosis
2. Integration with code editing tools
3. Deployment rollback capability
4. Cloud provider skills (AWS, GCP)

### Success Criteria

- Detect deployment error, diagnose, suggest fix
- Automatically trigger Cursor to fix code issue
- Rollback failed deployment automatically

---

## Phase 4: Enterprise Features

**Target**: Production-ready for teams

### Goals

- [ ] **Team Features**
  - Multi-user support
  - Role-based access control
  - Audit logging
  - Shared project configurations

- [ ] **Infrastructure as Code**
  - Terraform generation
  - Pulumi support
  - CDK support
  - GitOps workflows

- [ ] **Advanced Monitoring**
  - Metrics collection
  - Grafana dashboard generation
  - Custom alerting rules
  - SLA monitoring

- [ ] **Security**
  - Secret scanning
  - Vulnerability detection
  - Compliance checking
  - Security recommendations

### Deliverables

1. Team management features
2. IaC generation
3. Full observability stack setup
4. Security scanning integration

---

## Future Explorations

### Ideas Under Consideration

- **Voice Interface**: Voice commands for hands-free operation
- **IDE Extensions**: VS Code, JetBrains integration
- **Mobile App**: Monitor deployments from phone
- **Self-Hosting Guide**: Run OpenOps for your organization
- **Plugin Marketplace**: Community skill discovery

### Community Requested

Track feature requests at: github.com/openops/openops/discussions

---

## Timeline (Tentative)

| Phase | Focus | Target |
|-------|-------|--------|
| Phase 1 | Core Deployment | Q2 2026 |
| Phase 2 | Multi-Service & Monitoring | Q3 2026 |
| Phase 3 | Error Resolution | Q4 2026 |
| Phase 4 | Enterprise | 2027 |

*Note: Timelines are estimates and may shift based on community feedback and contributions.*

---

## How to Contribute

See [11-contributing.md](./11-contributing.md) for contribution guidelines.

### Current Priorities

1. **Phase 1 features** - Help us reach MVP
2. **Platform skills** - Add support for more platforms
3. **Testing** - Improve test coverage
4. **Documentation** - Better examples and guides

### Getting Started

```bash
# Clone and set up
git clone https://github.com/openops/openops.git
cd openops
pip install -e ".[dev]"

# Run tests
pytest tests/

# Pick an issue and start contributing!
```

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 0.1.0 | - | Initial architecture and basic skills |

---

## Contact

- **GitHub**: github.com/openops/openops
- **Issues**: github.com/openops/openops/issues
- **Discussions**: github.com/openops/openops/discussions
