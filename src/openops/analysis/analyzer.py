"""Main project analyzer for OpenOps.

This module provides the main ProjectAnalyzer class that orchestrates
framework detection, environment variable extraction, and project analysis.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from openops.analysis.detector import (
    ExistingConfig,
    FrameworkInfo,
    ProjectTypeInfo,
    detect_existing_configs,
    detect_framework,
    detect_project_type,
    get_missing_configs,
)
from openops.analysis.env_extractor import EnvVar, extract_env_vars
from openops.models import Project, Service

logger = logging.getLogger(__name__)


@dataclass
class ProjectAnalysis:
    """Complete analysis result for a project."""

    project: Project
    services: list[Service]
    project_type: ProjectTypeInfo | None
    framework_info: FrameworkInfo | None
    existing_configs: list[ExistingConfig]
    env_vars: list[EnvVar]
    keypoints: list[str] = field(default_factory=list)


class ProjectAnalyzer:
    """Analyzes projects to understand their structure and deployment requirements.

    This class orchestrates the analysis of a project directory, detecting:
    - Project type (Node.js, Python, Rust, Go, etc.)
    - Framework (Next.js, FastAPI, Django, etc.)
    - Required environment variables
    - Existing deployment configurations
    - Missing deployment configurations

    Usage:
        analyzer = ProjectAnalyzer()
        analysis = analyzer.analyze("/path/to/project")
        print(analysis.project.name)
        print(analysis.services)
    """

    def analyze(self, directory: str | Path) -> ProjectAnalysis:
        """Analyze a project directory.

        Args:
            directory: Path to the project root directory

        Returns:
            ProjectAnalysis containing project, services, and analysis details

        Raises:
            ValueError: If the directory does not exist
        """
        directory = Path(directory).resolve()
        if not directory.is_dir():
            raise ValueError(f"Directory does not exist: {directory}")

        logger.info(f"Analyzing project at {directory}")

        project_type = detect_project_type(directory)
        framework_info = detect_framework(directory)
        existing_configs = detect_existing_configs(directory)
        env_vars = extract_env_vars(directory)

        keypoints = self._generate_keypoints(directory, project_type, framework_info, existing_configs, env_vars)

        project_id = str(uuid.uuid4())
        project_name = directory.name
        now = datetime.now(UTC)

        project = Project(
            id=project_id,
            path=str(directory),
            name=project_name,
            description=self._generate_description(project_type, framework_info),
            keypoints=keypoints,
            analyzed_at=now,
            updated_at=now,
        )

        services = []
        if framework_info:
            service = self._create_service(
                project_id=project_id,
                directory=directory,
                framework_info=framework_info,
                env_vars=env_vars,
            )
            services.append(service)

        analysis = ProjectAnalysis(
            project=project,
            services=services,
            project_type=project_type,
            framework_info=framework_info,
            existing_configs=existing_configs,
            env_vars=env_vars,
            keypoints=keypoints,
        )

        logger.info(
            f"Analysis complete: {project_name} "
            f"({framework_info.framework if framework_info else 'unknown'}) "
            f"with {len(services)} service(s)"
        )

        return analysis

    def _create_service(
        self,
        project_id: str,
        directory: Path,
        framework_info: FrameworkInfo,
        env_vars: list[EnvVar],
    ) -> Service:
        """Create a Service model from framework info."""
        return Service(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name=directory.name,
            path=".",
            description=f"{framework_info.framework.title()} {framework_info.service_type}",
            type=framework_info.service_type,
            framework=framework_info.framework,
            language=framework_info.language,
            version=framework_info.version,
            entry_point=framework_info.entry_point,
            build_command=framework_info.build_command,
            start_command=framework_info.start_command,
            port=framework_info.default_port,
            env_vars=[v.name for v in env_vars if v.required],
            dependencies=[],
            keypoints=[],
        )

    def _generate_description(
        self,
        project_type: ProjectTypeInfo | None,
        framework_info: FrameworkInfo | None,
    ) -> str:
        """Generate a human-readable description of the project."""
        if framework_info:
            lang = framework_info.language.title()
            framework = framework_info.framework.title()
            svc_type = framework_info.service_type

            if framework_info.framework in ("nextjs", "nuxt", "sveltekit", "remix"):
                return f"A {framework} application for building {svc_type} web applications"
            elif framework_info.framework in ("fastapi", "django", "flask", "express", "nestjs"):
                return f"A {framework} {svc_type} application written in {lang}"
            elif framework_info.framework in ("vite", "astro"):
                return f"A {framework} {svc_type} application"
            else:
                return f"A {lang} {svc_type} application using {framework}"

        if project_type:
            type_names = {
                "node_project": "Node.js",
                "python_project": "Python",
                "rust_project": "Rust",
                "go_project": "Go",
                "java_maven": "Java (Maven)",
                "java_gradle": "Java (Gradle)",
            }
            lang = type_names.get(project_type.project_type, "Unknown")
            return f"A {lang} project"

        return "A software project"

    def _generate_keypoints(
        self,
        directory: Path,
        project_type: ProjectTypeInfo | None,
        framework_info: FrameworkInfo | None,
        existing_configs: list[ExistingConfig],
        env_vars: list[EnvVar],
    ) -> list[str]:
        """Generate key observations about the project."""
        keypoints = []

        if project_type:
            if project_type.is_monorepo:
                keypoints.append(
                    f"Monorepo detected ({project_type.monorepo_type}) - " "multi-service analysis deferred to Phase 2"
                )

        if framework_info:
            confidence_str = (
                "high" if framework_info.confidence >= 0.9 else "medium" if framework_info.confidence >= 0.7 else "low"
            )
            keypoints.append(f"Framework: {framework_info.framework} ({confidence_str} confidence)")

            if framework_info.version:
                keypoints.append(f"Version: {framework_info.version}")

            keypoints.append(f"Service type: {framework_info.service_type}")

            if framework_info.default_port:
                keypoints.append(f"Default port: {framework_info.default_port}")

        if existing_configs:
            config_names = [c.config_type for c in existing_configs]
            keypoints.append(f"Existing configs: {', '.join(config_names)}")

            platforms = [c.platform for c in existing_configs if c.platform]
            if platforms:
                keypoints.append(f"Platform configs found: {', '.join(platforms)}")

        if env_vars:
            required_vars = [v for v in env_vars if v.required]
            if required_vars:
                keypoints.append(f"Required env vars: {len(required_vars)}")
                if len(required_vars) <= 5:
                    var_names = ", ".join(v.name for v in required_vars)
                    keypoints.append(f"Env vars: {var_names}")

        for platform in ["vercel", "railway", "render"]:
            missing = get_missing_configs(directory, platform)
            if missing:
                pass
            else:
                keypoints.append(f"Ready for {platform} deployment")

        return keypoints

    def get_deployment_readiness(
        self,
        analysis: ProjectAnalysis,
        target_platform: str,
    ) -> dict:
        """Check if a project is ready for deployment to a specific platform.

        Args:
            analysis: The project analysis result
            target_platform: Target platform (vercel, railway, render)

        Returns:
            Dictionary with readiness info:
            - ready: bool indicating if ready for deployment
            - missing_configs: list of missing configuration files
            - missing_env_vars: list of required env vars without defaults
            - recommendations: list of recommended actions
        """
        missing_configs = get_missing_configs(
            analysis.project.path,
            target_platform,
        )

        missing_env_vars = [v.name for v in analysis.env_vars if v.required and v.default is None]

        recommendations = []

        if missing_configs:
            for config in missing_configs:
                recommendations.append(f"Create {config} configuration file")

        if missing_env_vars:
            recommendations.append(
                f"Set {len(missing_env_vars)} environment variable(s) " f"in {target_platform} dashboard"
            )

        if analysis.framework_info:
            if target_platform == "vercel" and analysis.framework_info.framework not in (
                "nextjs",
                "nuxt",
                "vite",
                "astro",
                "sveltekit",
                "remix",
            ):
                recommendations.append(
                    f"Vercel is optimized for frontend frameworks. "
                    f"Consider Railway or Render for {analysis.framework_info.framework}"
                )

            if target_platform in ("railway", "render") and analysis.framework_info.framework in (
                "nextjs",
                "nuxt",
                "sveltekit",
            ):
                recommendations.append(f"Consider Vercel for optimal {analysis.framework_info.framework} support")

        ready = len(missing_configs) == 0

        return {
            "ready": ready,
            "missing_configs": missing_configs,
            "missing_env_vars": missing_env_vars,
            "recommendations": recommendations,
        }


def analyze_project(directory: str | Path) -> ProjectAnalysis:
    """Analyze a project directory (convenience function).

    Args:
        directory: Path to the project root directory

    Returns:
        ProjectAnalysis containing project, services, and analysis details
    """
    analyzer = ProjectAnalyzer()
    return analyzer.analyze(directory)
