# Monitoring System

## Overview

The monitoring system provides background observation of deployed services, with log analysis, error detection, and alerting. This is a **Phase 2** feature - the architecture is defined here for future implementation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Monitor Daemon                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Scheduler                                    │    │
│  │  - Interval-based triggers (configurable, default 60s)              │    │
│  │  - Event-based triggers (webhooks from platforms)                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│           ┌────────────────────────┼────────────────────────┐               │
│           ▼                        ▼                        ▼               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   Log Fetcher   │    │  Health Checker │    │  Error Analyzer │         │
│  │                 │    │                 │    │                 │         │
│  │ - Vercel logs   │    │ - HTTP health   │    │ - Pattern match │         │
│  │ - Railway logs  │    │ - Response time │    │ - LLM analysis  │         │
│  │ - Render logs   │    │ - Status codes  │    │ - Root cause    │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│           │                        │                        │               │
│           └────────────────────────┼────────────────────────┘               │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Alert Dispatcher                                │    │
│  │  - Slack notifications                                               │    │
│  │  - Email alerts                                                      │    │
│  │  - CLI notifications (when running)                                  │    │
│  │  - Trigger fix workflow (integrate with Cursor/Claude Code)         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Daemon Design

### Process Management

The daemon runs as a background process managed by the system:

```python
# Linux/macOS: systemd/launchd service
# Or simple background process with PID file

class MonitorDaemon:
    def __init__(self, config_path: str = "~/.openops/config.yaml"):
        self.config = load_config(config_path)
        self.pid_file = Path("~/.openops/daemon.pid").expanduser()
        self.running = False
        
    def start(self):
        """Start the daemon process."""
        if self.is_running():
            raise DaemonError("Daemon already running")
        
        # Daemonize
        pid = os.fork()
        if pid > 0:
            # Parent exits
            return
        
        # Child continues as daemon
        self._write_pid()
        self.running = True
        self._run_loop()
    
    def stop(self):
        """Stop the daemon process."""
        if not self.is_running():
            return
            
        pid = self._read_pid()
        os.kill(pid, signal.SIGTERM)
        self.pid_file.unlink()
    
    def is_running(self) -> bool:
        """Check if daemon is running."""
        if not self.pid_file.exists():
            return False
        pid = self._read_pid()
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def _run_loop(self):
        """Main daemon loop."""
        scheduler = BackgroundScheduler()
        
        # Schedule periodic checks
        scheduler.add_job(
            self._check_all_services,
            'interval',
            seconds=self.config.monitoring.interval,
        )
        
        scheduler.start()
        
        # Keep running until stopped
        while self.running:
            time.sleep(1)
```

### CLI Integration

```bash
# Start daemon
$ openops monitor start
Starting monitor daemon...
✓ Daemon started (PID: 12345)
  Monitoring: 3 services
  Interval: 60 seconds
  Log file: ~/.openops/daemon.log

# Check status
$ openops monitor status
Monitor Daemon Status
─────────────────────
Status:     Running (PID: 12345)
Uptime:     2 hours 15 minutes
Services:   3 monitored
Last check: 30 seconds ago
Alerts:     1 warning in last hour

# View logs
$ openops monitor logs
[2026-04-11 10:30:00] INFO  Checking my-app-web...
[2026-04-11 10:30:01] OK    my-app-web: healthy (234ms)
[2026-04-11 10:30:02] INFO  Checking my-app-api...
[2026-04-11 10:30:03] WARN  my-app-api: slow response (1523ms)

# Stop daemon
$ openops monitor stop
Stopping monitor daemon...
✓ Daemon stopped
```

## Log Fetching

### Platform-Specific Log APIs

```python
class LogFetcher(ABC):
    @abstractmethod
    async def fetch_logs(
        self,
        service_id: str,
        since: datetime,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Fetch logs from the platform."""
        pass

class VercelLogFetcher(LogFetcher):
    async def fetch_logs(self, service_id: str, since: datetime, limit: int = 100):
        """Fetch logs from Vercel."""
        response = await httpx.get(
            f"https://api.vercel.com/v2/deployments/{service_id}/events",
            headers={"Authorization": f"Bearer {self.token}"},
            params={
                "since": since.isoformat(),
                "limit": limit,
            }
        )
        return [LogEntry.from_vercel(e) for e in response.json()["events"]]

class RailwayLogFetcher(LogFetcher):
    async def fetch_logs(self, service_id: str, since: datetime, limit: int = 100):
        """Fetch logs from Railway via GraphQL."""
        query = """
        query GetLogs($serviceId: String!, $since: DateTime!, $limit: Int!) {
            logs(serviceId: $serviceId, since: $since, limit: $limit) {
                timestamp
                message
                level
            }
        }
        """
        # Execute GraphQL query
        pass

class RenderLogFetcher(LogFetcher):
    async def fetch_logs(self, service_id: str, since: datetime, limit: int = 100):
        """Fetch logs from Render."""
        response = await httpx.get(
            f"https://api.render.com/v1/services/{service_id}/logs",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        return [LogEntry.from_render(l) for l in response.json()]
```

### Log Entry Model

```python
@dataclass
class LogEntry:
    timestamp: datetime
    level: str  # "info", "warn", "error"
    message: str
    source: str  # service name
    metadata: dict | None = None
    
    @classmethod
    def from_vercel(cls, event: dict) -> "LogEntry":
        return cls(
            timestamp=datetime.fromisoformat(event["timestamp"]),
            level=event.get("level", "info"),
            message=event["message"],
            source=event.get("source", "unknown"),
        )
```

## Health Checking

### Health Check Implementation

```python
@dataclass
class HealthStatus:
    healthy: bool
    response_time_ms: int
    status_code: int
    error: str | None = None

class HealthChecker:
    def __init__(self, timeout_seconds: int = 10):
        self.timeout = timeout_seconds
        self.thresholds = {
            "response_time_warning": 1000,  # ms
            "response_time_critical": 5000,  # ms
        }
    
    async def check(self, url: str) -> HealthStatus:
        """Check health of a service endpoint."""
        start = time.monotonic()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                
            elapsed = (time.monotonic() - start) * 1000
            
            return HealthStatus(
                healthy=response.status_code < 400,
                response_time_ms=int(elapsed),
                status_code=response.status_code,
            )
            
        except httpx.TimeoutException:
            return HealthStatus(
                healthy=False,
                response_time_ms=self.timeout * 1000,
                status_code=0,
                error="Timeout",
            )
        except Exception as e:
            return HealthStatus(
                healthy=False,
                response_time_ms=0,
                status_code=0,
                error=str(e),
            )
```

## Error Analysis

### Pattern-Based Analysis

```python
ERROR_PATTERNS = {
    "database_connection": [
        r"connection refused.*5432",
        r"ECONNREFUSED.*postgres",
        r"timeout.*database",
    ],
    "memory_exhausted": [
        r"JavaScript heap out of memory",
        r"MemoryError",
        r"OOM",
    ],
    "missing_env_var": [
        r"environment variable .* not set",
        r"Missing required env",
        r"undefined.*process\.env",
    ],
    "build_failure": [
        r"npm ERR!",
        r"ModuleNotFoundError",
        r"Cannot find module",
    ],
}

def analyze_error_pattern(log_entries: list[LogEntry]) -> list[dict]:
    """Analyze logs for known error patterns."""
    findings = []
    
    for entry in log_entries:
        if entry.level != "error":
            continue
            
        for error_type, patterns in ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, entry.message, re.IGNORECASE):
                    findings.append({
                        "type": error_type,
                        "log": entry,
                        "pattern": pattern,
                    })
                    break
    
    return findings
```

### LLM-Based Analysis

For complex errors, use the Monitor Agent:

```python
async def analyze_with_llm(
    logs: list[LogEntry],
    context: dict,
) -> str:
    """Use LLM to analyze error logs."""
    
    prompt = f"""Analyze these error logs from a deployed service:

Service: {context['service_name']}
Platform: {context['platform']}
Tech Stack: {context['tech_stack']}

Recent Logs:
{format_logs(logs)}

Provide:
1. Root cause analysis
2. Severity assessment (low/medium/high/critical)
3. Suggested fix
4. Whether this requires immediate attention
"""
    
    response = await monitor_agent.invoke({
        "messages": [{"role": "user", "content": prompt}]
    })
    
    return response["messages"][-1].content
```

## Alerting

### Alert Configuration

```yaml
# ~/.openops/config.yaml
monitoring:
  enabled: true
  interval: 60  # seconds
  
  alerts:
    slack:
      enabled: true
      webhook_url: ${SLACK_WEBHOOK_URL}
      channels:
        critical: "#alerts-critical"
        warning: "#alerts-warning"
        
    email:
      enabled: false
      smtp_host: smtp.example.com
      from: openops@example.com
      to:
        - team@example.com
        
  thresholds:
    response_time_warning: 1000  # ms
    response_time_critical: 5000
    error_rate_warning: 0.01  # 1%
    error_rate_critical: 0.05  # 5%
```

### Alert Dispatcher

```python
@dataclass
class Alert:
    severity: str  # "info", "warning", "critical"
    service: str
    title: str
    message: str
    timestamp: datetime
    metadata: dict | None = None

class AlertDispatcher:
    def __init__(self, config: dict):
        self.channels = self._setup_channels(config)
    
    async def dispatch(self, alert: Alert):
        """Send alert to configured channels."""
        for channel in self.channels:
            if channel.should_send(alert):
                await channel.send(alert)
    
    def _setup_channels(self, config: dict) -> list:
        channels = []
        
        if config.get("slack", {}).get("enabled"):
            channels.append(SlackChannel(config["slack"]))
            
        if config.get("email", {}).get("enabled"):
            channels.append(EmailChannel(config["email"]))
        
        return channels

class SlackChannel:
    async def send(self, alert: Alert):
        """Send alert to Slack."""
        color = {
            "info": "#36a64f",
            "warning": "#ffcc00",
            "critical": "#ff0000",
        }[alert.severity]
        
        payload = {
            "attachments": [{
                "color": color,
                "title": f"[{alert.severity.upper()}] {alert.title}",
                "text": alert.message,
                "fields": [
                    {"title": "Service", "value": alert.service, "short": True},
                    {"title": "Time", "value": alert.timestamp.isoformat(), "short": True},
                ],
            }]
        }
        
        await httpx.post(self.webhook_url, json=payload)
```

## Fix Integration

### Triggering External Fix Tools

When errors are detected, OpenOps can suggest or trigger fixes:

```python
async def suggest_fix(error_analysis: dict, project_path: str):
    """Suggest or trigger a fix for an error."""
    
    # Option 1: Show suggestion in CLI (if running)
    if cli_session_active():
        show_fix_suggestion(error_analysis)
        return
    
    # Option 2: Trigger Cursor CLI
    if config.auto_fix.cursor_enabled:
        await trigger_cursor_fix(error_analysis, project_path)
        return
    
    # Option 3: Send alert with fix instructions
    await dispatch_alert(Alert(
        severity="warning",
        service=error_analysis["service"],
        title=f"Error detected: {error_analysis['type']}",
        message=f"""
Error detected in {error_analysis['service']}.

Root cause: {error_analysis['root_cause']}

Suggested fix:
{error_analysis['suggested_fix']}

Run `openops chat` to let OpenOps help fix this issue.
""",
    ))

async def trigger_cursor_fix(error_analysis: dict, project_path: str):
    """Trigger Cursor CLI to fix the issue."""
    fix_prompt = f"""
Fix the following error in this project:

Error: {error_analysis['type']}
Location: {error_analysis['location']}
Root cause: {error_analysis['root_cause']}

Suggested approach: {error_analysis['suggested_fix']}
"""
    
    # Run Cursor CLI with the fix prompt
    subprocess.run([
        "cursor", "--command",
        f"@workspace {fix_prompt}",
        project_path,
    ])
```

## Monitoring Data Storage

Store monitoring data for analysis:

```python
class MonitoringStore:
    def __init__(self, db_path: str = "~/.openops/monitoring.db"):
        self.db = sqlite3.connect(Path(db_path).expanduser())
        self._init_schema()
    
    def _init_schema(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY,
                service_id TEXT,
                timestamp DATETIME,
                healthy BOOLEAN,
                response_time_ms INTEGER,
                status_code INTEGER,
                error TEXT
            )
        """)
        
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                service_id TEXT,
                severity TEXT,
                title TEXT,
                message TEXT,
                timestamp DATETIME,
                acknowledged BOOLEAN DEFAULT FALSE
            )
        """)
    
    def save_health_check(self, service_id: str, status: HealthStatus):
        self.db.execute(
            "INSERT INTO health_checks VALUES (?, ?, ?, ?, ?, ?, ?)",
            (None, service_id, datetime.now(), status.healthy,
             status.response_time_ms, status.status_code, status.error)
        )
        self.db.commit()
    
    def get_health_history(
        self,
        service_id: str,
        since: datetime,
    ) -> list[HealthStatus]:
        """Get health check history for a service."""
        cursor = self.db.execute(
            "SELECT * FROM health_checks WHERE service_id = ? AND timestamp > ?",
            (service_id, since)
        )
        return [HealthStatus(**row) for row in cursor.fetchall()]
```

## Next Steps

- [08-memory.md](./08-memory.md) - How monitoring data is stored
- [09-configuration.md](./09-configuration.md) - Monitoring configuration
