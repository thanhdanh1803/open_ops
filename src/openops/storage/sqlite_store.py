"""SQLite implementation of the project store."""

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from openops.models import Deployment, MonitoringPrefs, Project, Service
from openops.storage.base import ProjectStoreBase

logger = logging.getLogger(__name__)


class SqliteProjectStore(ProjectStoreBase):
    """SQLite-based implementation of the project knowledge store.

    This store persists project metadata, services, and deployment information
    to a local SQLite database.

    A single ``sqlite3`` connection may be used from multiple threads (e.g.
    LangGraph ToolNode). All access is serialized with a re-entrant lock so the
    connection is never used concurrently.
    """

    def __init__(self, db_path: str | Path):
        """Initialize the SQLite project store.

        Args:
            db_path: Path to the SQLite database file. Use ":memory:" for in-memory database.
        """
        self.db_path = str(db_path)
        self._connection: sqlite3.Connection | None = None
        self._db_lock = threading.RLock()
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        """Return the live SQLite connection.

        Call only while holding ``self._db_lock``.
        """
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 10000")
            logger.debug("Opened SQLite connection for %s", self.db_path)
        return self._connection

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path) as f:
            schema_sql = f.read()

        with self._db_lock:
            self._conn().executescript(schema_sql)
            self._conn().commit()
        logger.debug("Initialized schema for database at %s", self.db_path)

    def close(self) -> None:
        """Close the database connection."""
        with self._db_lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
                logger.debug("Closed SQLite connection for %s", self.db_path)

    def pragma_integrity_check(self) -> str:
        """Run ``PRAGMA integrity_check`` under the store lock (for diagnostics)."""
        with self._db_lock:
            row = self._conn().execute("PRAGMA integrity_check").fetchone()
            return row[0] if row else ""

    def _serialize_datetime(self, dt: datetime | None) -> str | None:
        """Serialize datetime to ISO format string."""
        return dt.isoformat() if dt else None

    def _deserialize_datetime(self, value: str | None) -> datetime | None:
        """Deserialize ISO format string to datetime."""
        if not value:
            return None
        return datetime.fromisoformat(value)

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        """Convert a database row to a Project model."""
        return Project(
            id=row["id"],
            path=row["path"],
            name=row["name"],
            description=row["description"] or "",
            keypoints=json.loads(row["keypoints"] or "[]"),
            analyzed_at=self._deserialize_datetime(row["analyzed_at"]),
            updated_at=self._deserialize_datetime(row["updated_at"]),
        )

    def _row_to_service(self, row: sqlite3.Row) -> Service:
        """Convert a database row to a Service model."""
        return Service(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            path=row["path"],
            description=row["description"] or "",
            type=row["type"],
            framework=row["framework"],
            language=row["language"],
            version=row["version"],
            entry_point=row["entry_point"],
            build_command=row["build_command"],
            start_command=row["start_command"],
            port=row["port"],
            env_vars=json.loads(row["env_vars"] or "[]"),
            dependencies=json.loads(row["dependencies"] or "[]"),
            keypoints=json.loads(row["keypoints"] or "[]"),
        )

    def _row_to_deployment(self, row: sqlite3.Row) -> Deployment:
        """Convert a database row to a Deployment model."""
        return Deployment(
            id=row["id"],
            service_id=row["service_id"],
            platform=row["platform"],
            url=row["url"],
            dashboard_url=row["dashboard_url"],
            deployed_at=self._deserialize_datetime(row["deployed_at"]),
            config=json.loads(row["config"] or "{}"),
            status=row["status"],
        )

    # Project operations

    def upsert_project(self, project: Project) -> None:
        """Insert or update a project."""
        with self._db_lock:
            self._conn().execute(
                """
                INSERT INTO projects (id, path, name, description, keypoints, analyzed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path = excluded.path,
                    name = excluded.name,
                    description = excluded.description,
                    keypoints = excluded.keypoints,
                    analyzed_at = excluded.analyzed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    project.id,
                    project.path,
                    project.name,
                    project.description,
                    json.dumps(project.keypoints),
                    self._serialize_datetime(project.analyzed_at),
                    self._serialize_datetime(project.updated_at),
                ),
            )
            self._conn().commit()
        logger.debug("Upserted project: %s at %s", project.id, project.path)

    def get_project(self, path: str) -> Project | None:
        """Get a project by its path."""
        with self._db_lock:
            row = self._conn().execute("SELECT * FROM projects WHERE path = ?", (path,)).fetchone()

        if not row:
            return None

        return self._row_to_project(row)

    def get_project_by_id(self, project_id: str) -> Project | None:
        """Get a project by its ID."""
        with self._db_lock:
            row = self._conn().execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

        if not row:
            return None

        return self._row_to_project(row)

    def list_projects(self) -> list[Project]:
        """List all known projects."""
        with self._db_lock:
            rows = self._conn().execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()

        return [self._row_to_project(row) for row in rows]

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all associated data."""
        with self._db_lock:
            cursor = self._conn().execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self._conn().commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("Deleted project: %s", project_id)
        return deleted

    # Service operations

    def upsert_service(self, service: Service) -> None:
        """Insert or update a service."""
        with self._db_lock:
            self._conn().execute(
                """
                INSERT INTO services (
                    id, project_id, name, path, description, type, framework, language,
                    version, entry_point, build_command, start_command, port, env_vars,
                    dependencies, keypoints
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id = excluded.project_id,
                    name = excluded.name,
                    path = excluded.path,
                    description = excluded.description,
                    type = excluded.type,
                    framework = excluded.framework,
                    language = excluded.language,
                    version = excluded.version,
                    entry_point = excluded.entry_point,
                    build_command = excluded.build_command,
                    start_command = excluded.start_command,
                    port = excluded.port,
                    env_vars = excluded.env_vars,
                    dependencies = excluded.dependencies,
                    keypoints = excluded.keypoints
                """,
                (
                    service.id,
                    service.project_id,
                    service.name,
                    service.path,
                    service.description,
                    service.type,
                    service.framework,
                    service.language,
                    service.version,
                    service.entry_point,
                    service.build_command,
                    service.start_command,
                    service.port,
                    json.dumps(service.env_vars),
                    json.dumps(service.dependencies),
                    json.dumps(service.keypoints),
                ),
            )

            self._sync_service_dependencies_unlocked(service.id, service.dependencies)
            self._conn().commit()
        logger.debug("Upserted service: %s (%s)", service.id, service.name)

    def _sync_service_dependencies_unlocked(self, service_id: str, dependencies: list[str]) -> None:
        """Synchronize the service_dependencies table; caller must hold ``_db_lock``."""
        self._conn().execute("DELETE FROM service_dependencies WHERE service_id = ?", (service_id,))

        for depends_on_id in dependencies:
            self._conn().execute(
                """
                INSERT OR IGNORE INTO service_dependencies (service_id, depends_on_id)
                VALUES (?, ?)
                """,
                (service_id, depends_on_id),
            )

    def get_service(self, service_id: str) -> Service | None:
        """Get a service by its ID."""
        with self._db_lock:
            row = self._conn().execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()

        if not row:
            return None

        return self._row_to_service(row)

    def get_services_for_project(self, project_id: str) -> list[Service]:
        """Get all services for a project."""
        with self._db_lock:
            rows = (
                self._conn()
                .execute(
                    "SELECT * FROM services WHERE project_id = ? ORDER BY name",
                    (project_id,),
                )
                .fetchall()
            )

        return [self._row_to_service(row) for row in rows]

    def delete_service(self, service_id: str) -> bool:
        """Delete a service."""
        with self._db_lock:
            cursor = self._conn().execute("DELETE FROM services WHERE id = ?", (service_id,))
            self._conn().commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("Deleted service: %s", service_id)
        return deleted

    def get_dependent_services(self, service_id: str) -> list[Service]:
        """Get all services that depend on the given service.

        This uses the service_dependencies table for efficient reverse lookup.

        Args:
            service_id: ID of the service to find dependents for

        Returns:
            List of services that depend on the given service
        """
        with self._db_lock:
            rows = (
                self._conn()
                .execute(
                    """
                SELECT s.* FROM services s
                INNER JOIN service_dependencies sd ON s.id = sd.service_id
                WHERE sd.depends_on_id = ?
                ORDER BY s.name
                """,
                    (service_id,),
                )
                .fetchall()
            )

        return [self._row_to_service(row) for row in rows]

    # Deployment operations

    def add_deployment(self, deployment: Deployment) -> None:
        """Record a new deployment.

        Marks any previous active deployments for the same service as 'superseded'.
        """
        with self._db_lock:
            self._conn().execute(
                """
                UPDATE deployments SET status = 'superseded'
                WHERE service_id = ? AND status = 'active'
                """,
                (deployment.service_id,),
            )

            self._conn().execute(
                """
                INSERT INTO deployments
                (id, service_id, platform, url, dashboard_url, deployed_at, config, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    deployment.id,
                    deployment.service_id,
                    deployment.platform,
                    deployment.url,
                    deployment.dashboard_url,
                    self._serialize_datetime(deployment.deployed_at),
                    json.dumps(deployment.config),
                    deployment.status,
                ),
            )
            self._conn().commit()
        logger.debug("Added deployment: %s for service %s", deployment.id, deployment.service_id)

    def get_active_deployment(self, service_id: str) -> Deployment | None:
        """Get the active deployment for a service."""
        with self._db_lock:
            row = (
                self._conn()
                .execute(
                    """
                SELECT * FROM deployments
                WHERE service_id = ? AND status = 'active'
                ORDER BY deployed_at DESC
                LIMIT 1
                """,
                    (service_id,),
                )
                .fetchone()
            )

        if not row:
            return None

        return self._row_to_deployment(row)

    def get_deployments_for_service(self, service_id: str) -> list[Deployment]:
        """Get all deployments for a service, ordered by deployed_at desc."""
        with self._db_lock:
            rows = (
                self._conn()
                .execute(
                    """
                SELECT * FROM deployments
                WHERE service_id = ?
                ORDER BY deployed_at DESC
                """,
                    (service_id,),
                )
                .fetchall()
            )

        return [self._row_to_deployment(row) for row in rows]

    def _row_to_monitoring_prefs(self, row: sqlite3.Row) -> MonitoringPrefs:
        """Convert a database row to MonitoringPrefs."""
        return MonitoringPrefs(
            project_path=row["project_path"],
            enabled=bool(row["enabled"]),
            interval_seconds=int(row["interval_seconds"]),
            updated_at=self._deserialize_datetime(row["updated_at"]),
            last_run_at=self._deserialize_datetime(row["last_run_at"]),
            last_error=(row["last_error"] or ""),
        )

    def upsert_monitoring_prefs(self, prefs: MonitoringPrefs) -> None:
        """Insert or update monitoring preferences."""
        path = str(Path(prefs.project_path).resolve())
        now = datetime.now()
        updated_at = prefs.updated_at or now
        with self._db_lock:
            self._conn().execute(
                """
                INSERT INTO project_monitoring_prefs
                    (project_path, enabled, interval_seconds, updated_at, last_run_at, last_error)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_path) DO UPDATE SET
                    enabled = excluded.enabled,
                    interval_seconds = excluded.interval_seconds,
                    updated_at = excluded.updated_at
                """,
                (
                    path,
                    1 if prefs.enabled else 0,
                    prefs.interval_seconds,
                    self._serialize_datetime(updated_at),
                    self._serialize_datetime(prefs.last_run_at),
                    prefs.last_error or "",
                ),
            )
            self._conn().commit()
        logger.debug("Upserted monitoring prefs for %s (enabled=%s)", path, prefs.enabled)

    def get_monitoring_prefs(self, project_path: str) -> MonitoringPrefs | None:
        """Return monitoring preferences for a project path."""
        path = str(Path(project_path).resolve())
        with self._db_lock:
            row = (
                self._conn()
                .execute(
                    "SELECT * FROM project_monitoring_prefs WHERE project_path = ?",
                    (path,),
                )
                .fetchone()
            )
        if not row:
            return None
        return self._row_to_monitoring_prefs(row)

    def list_enabled_monitoring_prefs(self) -> list[MonitoringPrefs]:
        """Return rows where background monitoring is enabled."""
        with self._db_lock:
            rows = (
                self._conn()
                .execute(
                    """
                    SELECT * FROM project_monitoring_prefs
                    WHERE enabled = 1
                    ORDER BY project_path
                    """
                )
                .fetchall()
            )
        return [self._row_to_monitoring_prefs(row) for row in rows]

    def touch_monitoring_run(
        self,
        project_path: str,
        *,
        last_run_at: datetime | None = None,
        last_error: str | None = None,
    ) -> None:
        """Update last_run_at and/or last_error."""
        path = str(Path(project_path).resolve())
        if last_run_at is None and last_error is None:
            return
        with self._db_lock:
            row = (
                self._conn()
                .execute(
                    "SELECT 1 FROM project_monitoring_prefs WHERE project_path = ?",
                    (path,),
                )
                .fetchone()
            )
            if not row:
                logger.debug("touch_monitoring_run: no prefs row for %s", path)
                return
            assignments: list[str] = []
            values: list = []
            if last_run_at is not None:
                assignments.append("last_run_at = ?")
                values.append(self._serialize_datetime(last_run_at))
            if last_error is not None:
                assignments.append("last_error = ?")
                values.append(last_error)
            values.append(path)
            sql = f"UPDATE project_monitoring_prefs SET {', '.join(assignments)} WHERE project_path = ?"
            self._conn().execute(sql, values)
            self._conn().commit()
        logger.debug("Updated monitoring run metadata for %s", path)


__all__ = ["SqliteProjectStore"]
