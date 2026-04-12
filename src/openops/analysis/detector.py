"""Framework and project type detection for OpenOps.

This module detects project types, frameworks, and existing deployment configurations
by inspecting file patterns, configuration files, and dependency manifests.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FrameworkInfo:
    """Information about a detected framework."""

    framework: str
    language: str
    service_type: str  # frontend, backend, fullstack
    version: str | None = None
    confidence: float = 1.0
    entry_point: str | None = None
    build_command: str | None = None
    start_command: str | None = None
    default_port: int | None = None


@dataclass
class ProjectTypeInfo:
    """Information about the project type."""

    project_type: str  # node_project, python_project, rust_project, go_project
    is_monorepo: bool = False
    monorepo_type: str | None = None  # turborepo, nx, lerna, pnpm
    root_files: list[str] = field(default_factory=list)


@dataclass
class ExistingConfig:
    """Information about an existing deployment configuration."""

    config_type: str  # docker, vercel, railway, render, github_actions
    file_path: str
    platform: str | None = None


MONOREPO_MARKERS = {
    "pnpm-workspace.yaml": "pnpm",
    "lerna.json": "lerna",
    "nx.json": "nx",
    "turbo.json": "turborepo",
}

PROJECT_TYPE_MARKERS = {
    "package.json": "node_project",
    "pyproject.toml": "python_project",
    "requirements.txt": "python_project",
    "Cargo.toml": "rust_project",
    "go.mod": "go_project",
    "pom.xml": "java_maven",
    "build.gradle": "java_gradle",
}

DEPLOYMENT_CONFIG_MARKERS = {
    "Dockerfile": ("docker", None),
    "docker-compose.yml": ("docker_compose", None),
    "docker-compose.yaml": ("docker_compose", None),
    "vercel.json": ("vercel", "vercel"),
    "railway.toml": ("railway", "railway"),
    "railway.json": ("railway", "railway"),
    "render.yaml": ("render", "render"),
    ".github/workflows": ("github_actions", None),
}

NODE_FRAMEWORK_CONFIG_FILES = {
    "next.config.js": ("nextjs", "frontend", 3000),
    "next.config.mjs": ("nextjs", "frontend", 3000),
    "next.config.ts": ("nextjs", "frontend", 3000),
    "nuxt.config.ts": ("nuxt", "frontend", 3000),
    "nuxt.config.js": ("nuxt", "frontend", 3000),
    "vite.config.ts": ("vite", "frontend", 5173),
    "vite.config.js": ("vite", "frontend", 5173),
    "angular.json": ("angular", "frontend", 4200),
    "svelte.config.js": ("sveltekit", "frontend", 5173),
    "remix.config.js": ("remix", "fullstack", 3000),
    "astro.config.mjs": ("astro", "frontend", 4321),
    "nest-cli.json": ("nestjs", "backend", 3000),
}

NODE_FRAMEWORK_DEPENDENCIES = {
    "next": ("nextjs", "frontend", 3000),
    "nuxt": ("nuxt", "frontend", 3000),
    "vite": ("vite", "frontend", 5173),
    "@angular/core": ("angular", "frontend", 4200),
    "svelte": ("sveltekit", "frontend", 5173),
    "@remix-run/node": ("remix", "fullstack", 3000),
    "astro": ("astro", "frontend", 4321),
    "@nestjs/core": ("nestjs", "backend", 3000),
    "express": ("express", "backend", 3000),
    "fastify": ("fastify", "backend", 3000),
    "koa": ("koa", "backend", 3000),
    "hono": ("hono", "backend", 3000),
}

PYTHON_FRAMEWORK_DEPENDENCIES = {
    "fastapi": ("fastapi", "backend", 8000),
    "django": ("django", "backend", 8000),
    "flask": ("flask", "backend", 5000),
    "streamlit": ("streamlit", "frontend", 8501),
    "gradio": ("gradio", "frontend", 7860),
    "litestar": ("litestar", "backend", 8000),
}


def detect_project_type(directory: str | Path) -> ProjectTypeInfo | None:
    """Detect the type of project in a directory.

    Args:
        directory: Path to the project directory

    Returns:
        ProjectTypeInfo if a known project type is detected, None otherwise
    """
    directory = Path(directory)
    if not directory.is_dir():
        logger.warning(f"Directory does not exist: {directory}")
        return None

    root_files = []
    project_type = None
    is_monorepo = False
    monorepo_type = None

    for marker, mono_type in MONOREPO_MARKERS.items():
        marker_path = directory / marker
        if marker_path.exists():
            is_monorepo = True
            monorepo_type = mono_type
            root_files.append(marker)
            logger.debug(f"Detected monorepo marker: {marker} ({mono_type})")

    for marker, ptype in PROJECT_TYPE_MARKERS.items():
        marker_path = directory / marker
        if marker_path.exists():
            if project_type is None:
                project_type = ptype
            root_files.append(marker)
            logger.debug(f"Detected project type marker: {marker} ({ptype})")

    if project_type is None:
        logger.debug(f"No project type detected in {directory}")
        return None

    return ProjectTypeInfo(
        project_type=project_type,
        is_monorepo=is_monorepo,
        monorepo_type=monorepo_type,
        root_files=root_files,
    )


def detect_framework(directory: str | Path) -> FrameworkInfo | None:
    """Detect the framework used in a directory.

    Args:
        directory: Path to the project directory

    Returns:
        FrameworkInfo if a framework is detected, None otherwise
    """
    directory = Path(directory)
    if not directory.is_dir():
        logger.warning(f"Directory does not exist: {directory}")
        return None

    project_type = detect_project_type(directory)
    if project_type is None:
        return None

    if project_type.project_type == "node_project":
        return _detect_node_framework(directory)
    elif project_type.project_type == "python_project":
        return _detect_python_framework(directory)
    elif project_type.project_type == "rust_project":
        return _detect_rust_framework(directory)
    elif project_type.project_type == "go_project":
        return _detect_go_framework(directory)

    return None


def _detect_node_framework(directory: Path) -> FrameworkInfo | None:
    """Detect Node.js framework from config files and package.json."""
    for config_file, (framework, svc_type, port) in NODE_FRAMEWORK_CONFIG_FILES.items():
        if (directory / config_file).exists():
            logger.debug(f"Detected Node framework from config: {config_file}")
            dep_name = _get_framework_dep_name(framework)
            version = _get_node_dependency_version(directory, dep_name)
            build_cmd, start_cmd = _get_node_scripts(directory, framework)
            return FrameworkInfo(
                framework=framework,
                language="typescript" if _has_typescript(directory) else "javascript",
                service_type=svc_type,
                version=version,
                confidence=1.0,
                build_command=build_cmd,
                start_command=start_cmd,
                default_port=port,
            )

    package_json = directory / "package.json"
    if package_json.exists():
        try:
            with open(package_json) as f:
                pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            for dep, (framework, svc_type, port) in NODE_FRAMEWORK_DEPENDENCIES.items():
                if dep in deps:
                    logger.debug(f"Detected Node framework from dependency: {dep}")
                    version = deps.get(dep)
                    if version:
                        version = re.sub(r"^[\^~>=<]", "", version)
                    build_cmd, start_cmd = _get_node_scripts(directory, framework)
                    return FrameworkInfo(
                        framework=framework,
                        language="typescript" if _has_typescript(directory) else "javascript",
                        service_type=svc_type,
                        version=version,
                        confidence=0.9,
                        build_command=build_cmd,
                        start_command=start_cmd,
                        default_port=port,
                    )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to parse package.json: {e}")

    if package_json.exists():
        build_cmd, start_cmd = _get_node_scripts(directory, None)
        return FrameworkInfo(
            framework="node",
            language="typescript" if _has_typescript(directory) else "javascript",
            service_type="backend",
            confidence=0.5,
            build_command=build_cmd,
            start_command=start_cmd,
            default_port=3000,
        )

    return None


def _detect_python_framework(directory: Path) -> FrameworkInfo | None:
    """Detect Python framework from pyproject.toml or requirements.txt."""
    deps = _get_python_dependencies(directory)

    for dep, (framework, svc_type, port) in PYTHON_FRAMEWORK_DEPENDENCIES.items():
        if dep in deps:
            logger.debug(f"Detected Python framework from dependency: {dep}")
            version = deps.get(dep)
            entry_point, start_cmd = _get_python_entry_point(directory, framework)
            return FrameworkInfo(
                framework=framework,
                language="python",
                service_type=svc_type,
                version=version,
                confidence=0.9,
                entry_point=entry_point,
                start_command=start_cmd,
                default_port=port,
            )

    if (directory / "manage.py").exists():
        logger.debug("Detected Django from manage.py")
        return FrameworkInfo(
            framework="django",
            language="python",
            service_type="backend",
            confidence=1.0,
            entry_point="manage.py",
            start_command="python manage.py runserver 0.0.0.0:8000",
            default_port=8000,
        )

    if deps:
        entry_point, _ = _get_python_entry_point(directory, None)
        return FrameworkInfo(
            framework="python",
            language="python",
            service_type="backend",
            confidence=0.5,
            entry_point=entry_point,
            default_port=8000,
        )

    return None


def _detect_rust_framework(directory: Path) -> FrameworkInfo | None:
    """Detect Rust project type from Cargo.toml."""
    cargo_toml = directory / "Cargo.toml"
    if not cargo_toml.exists():
        return None

    try:
        content = cargo_toml.read_text()
        version = None
        name = None

        for line in content.split("\n"):
            if line.startswith("version"):
                match = re.search(r'"([^"]+)"', line)
                if match:
                    version = match.group(1)
            if line.startswith("name"):
                match = re.search(r'"([^"]+)"', line)
                if match:
                    name = match.group(1)

        is_web = any(dep in content.lower() for dep in ["actix-web", "axum", "rocket", "warp", "tide"])

        return FrameworkInfo(
            framework="actix-web" if "actix-web" in content else "rust",
            language="rust",
            service_type="backend" if is_web else "worker",
            version=version,
            confidence=0.8 if is_web else 0.5,
            build_command="cargo build --release",
            start_command=f"./target/release/{name}" if name else None,
            default_port=8080 if is_web else None,
        )
    except OSError as e:
        logger.warning(f"Failed to read Cargo.toml: {e}")
        return None


def _detect_go_framework(directory: Path) -> FrameworkInfo | None:
    """Detect Go project type from go.mod."""
    go_mod = directory / "go.mod"
    if not go_mod.exists():
        return None

    try:
        content = go_mod.read_text()
        version = None
        # module_name = None

        for line in content.split("\n"):
            if line.startswith("go "):
                version = line.split()[1]
            # if line.startswith("module "):
            #     module_name = line.split()[1]

        is_web = any(dep in content for dep in ["gin-gonic", "echo", "fiber", "chi", "gorilla/mux"])

        framework = "gin" if "gin-gonic" in content else "go"

        return FrameworkInfo(
            framework=framework,
            language="go",
            service_type="backend" if is_web else "worker",
            version=version,
            confidence=0.8 if is_web else 0.5,
            build_command="go build -o app",
            start_command="./app",
            default_port=8080 if is_web else None,
        )
    except OSError as e:
        logger.warning(f"Failed to read go.mod: {e}")
        return None


def detect_existing_configs(directory: str | Path) -> list[ExistingConfig]:
    """Detect existing deployment configurations in a directory.

    Args:
        directory: Path to the project directory

    Returns:
        List of ExistingConfig objects for each detected configuration
    """
    directory = Path(directory)
    configs = []

    for marker, (config_type, platform) in DEPLOYMENT_CONFIG_MARKERS.items():
        marker_path = directory / marker
        if marker_path.exists():
            logger.debug(f"Detected deployment config: {marker}")
            configs.append(
                ExistingConfig(
                    config_type=config_type,
                    file_path=str(marker_path.relative_to(directory)),
                    platform=platform,
                )
            )

    return configs


def get_missing_configs(
    directory: str | Path,
    target_platform: str,
) -> list[str]:
    """Identify missing configuration files for a target platform.

    Args:
        directory: Path to the project directory
        target_platform: Target deployment platform (vercel, railway, render)

    Returns:
        List of missing configuration file names
    """
    existing = detect_existing_configs(directory)
    existing_types = {c.config_type for c in existing}

    platform_configs = {
        "vercel": ["vercel"],
        "railway": ["railway"],
        "render": ["render"],
    }

    required = platform_configs.get(target_platform, [])
    missing = [cfg for cfg in required if cfg not in existing_types]

    return missing


def _has_typescript(directory: Path) -> bool:
    """Check if the project uses TypeScript."""
    return (directory / "tsconfig.json").exists()


def _get_framework_dep_name(framework: str) -> str:
    """Get the npm package name for a framework."""
    mapping = {
        "nextjs": "next",
        "nuxt": "nuxt",
        "vite": "vite",
        "angular": "@angular/core",
        "sveltekit": "svelte",
        "remix": "@remix-run/node",
        "astro": "astro",
        "nestjs": "@nestjs/core",
        "express": "express",
        "fastify": "fastify",
    }
    return mapping.get(framework, framework)


def _get_node_dependency_version(directory: Path, package: str) -> str | None:
    """Get the version of a Node.js dependency."""
    package_json = directory / "package.json"
    if not package_json.exists():
        return None

    try:
        with open(package_json) as f:
            pkg = json.load(f)
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        version = deps.get(package)
        if version:
            return re.sub(r"^[\^~>=<]", "", version)
    except (json.JSONDecodeError, OSError):
        pass

    return None


def _get_node_scripts(directory: Path, framework: str | None) -> tuple[str | None, str | None]:
    """Get build and start commands from package.json scripts."""
    package_json = directory / "package.json"
    if not package_json.exists():
        return None, None

    try:
        with open(package_json) as f:
            pkg = json.load(f)
        scripts = pkg.get("scripts", {})

        build_cmd = None
        start_cmd = None

        if "build" in scripts:
            build_cmd = "npm run build"
        elif "compile" in scripts:
            build_cmd = "npm run compile"

        if "start" in scripts:
            start_cmd = "npm start"
        elif "serve" in scripts:
            start_cmd = "npm run serve"
        elif "dev" in scripts:
            start_cmd = "npm run dev"

        return build_cmd, start_cmd
    except (json.JSONDecodeError, OSError):
        return None, None


def _get_python_dependencies(directory: Path) -> dict[str, str | None]:
    """Extract Python dependencies from pyproject.toml or requirements.txt."""
    deps: dict[str, str | None] = {}

    pyproject = directory / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            in_deps = False
            for line in content.split("\n"):
                if "dependencies" in line and "=" in line:
                    in_deps = True
                    continue
                if in_deps:
                    if line.startswith("[") or (line.strip() and not line.startswith(" ") and not line.startswith('"')):
                        in_deps = False
                        continue
                    match = re.search(r'"([a-zA-Z0-9_-]+)(?:[><=!~]+([^"]+))?"', line)
                    if match:
                        pkg_name = match.group(1).lower().replace("-", "_").replace("_", "-")
                        deps[pkg_name] = match.group(2)
        except OSError:
            pass

    requirements = directory / "requirements.txt"
    if requirements.exists():
        try:
            for line in requirements.read_text().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r"([a-zA-Z0-9_-]+)(?:[><=!~]+(.+))?", line)
                if match:
                    pkg_name = match.group(1).lower().replace("-", "_").replace("_", "-")
                    deps[pkg_name] = match.group(2)
        except OSError:
            pass

    return deps


def _get_python_entry_point(directory: Path, framework: str | None) -> tuple[str | None, str | None]:
    """Determine the entry point and start command for a Python project."""
    common_entry_points = ["app.py", "main.py", "server.py", "run.py", "api.py"]

    for entry in common_entry_points:
        if (directory / entry).exists():
            if framework == "fastapi":
                module_name = entry.replace(".py", "")
                return entry, f"uvicorn {module_name}:app --host 0.0.0.0 --port 8000"
            elif framework == "flask":
                return entry, f"flask --app {entry.replace('.py', '')} run --host 0.0.0.0 --port 5000"
            elif framework == "streamlit":
                return entry, f"streamlit run {entry}"
            elif framework == "gradio":
                return entry, f"python {entry}"
            else:
                return entry, f"python {entry}"

    src_main = directory / "src" / "main.py"
    if src_main.exists():
        if framework == "fastapi":
            return "src/main.py", "uvicorn src.main:app --host 0.0.0.0 --port 8000"
        return "src/main.py", "python -m src.main"

    return None, None
