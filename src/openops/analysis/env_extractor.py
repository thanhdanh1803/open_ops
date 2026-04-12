"""Environment variable extraction for OpenOps.

This module discovers required environment variables by parsing env template files
and scanning source code for environment variable usage patterns.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EnvVar:
    """Information about an environment variable."""

    name: str
    required: bool = True
    default: str | None = None
    description: str | None = None
    source: str | None = None  # Where this env var was discovered


ENV_TEMPLATE_FILES = [
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.local.example",
    ".env.development.example",
]

JS_ENV_PATTERNS = [
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"process\.env\[(['\"])([A-Z][A-Z0-9_]*)\1\]"),
    re.compile(r"import\.meta\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"Deno\.env\.get\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
]

PYTHON_ENV_PATTERNS = [
    re.compile(r"os\.environ\[(['\"])([A-Z][A-Z0-9_]*)\1\]"),
    re.compile(r"os\.environ\.get\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"os\.getenv\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"environ\[(['\"])([A-Z][A-Z0-9_]*)\1\]"),
    re.compile(r"environ\.get\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"getenv\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
]

RUST_ENV_PATTERNS = [
    re.compile(r"env::var\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"std::env::var\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"env::var_os\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
]

GO_ENV_PATTERNS = [
    re.compile(r"os\.Getenv\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"os\.LookupEnv\(['\"]([A-Z][A-Z0-9_]*)['\"]"),
]

CODE_FILE_EXTENSIONS = {
    "js": JS_ENV_PATTERNS,
    "jsx": JS_ENV_PATTERNS,
    "ts": JS_ENV_PATTERNS,
    "tsx": JS_ENV_PATTERNS,
    "mjs": JS_ENV_PATTERNS,
    "cjs": JS_ENV_PATTERNS,
    "py": PYTHON_ENV_PATTERNS,
    "rs": RUST_ENV_PATTERNS,
    "go": GO_ENV_PATTERNS,
}

COMMON_ENTRY_FILES = [
    "app.py",
    "main.py",
    "server.py",
    "api.py",
    "index.ts",
    "index.js",
    "server.ts",
    "server.js",
    "app.ts",
    "app.js",
    "main.ts",
    "main.js",
    "main.go",
    "main.rs",
    "src/main.py",
    "src/app.py",
    "src/index.ts",
    "src/index.js",
    "src/main.ts",
    "src/main.go",
    "src/main.rs",
    "src/lib.rs",
]

IGNORED_ENV_VARS = {
    "NODE_ENV",
    "PATH",
    "HOME",
    "USER",
    "PWD",
    "SHELL",
    "LANG",
    "TERM",
    "EDITOR",
    "HOSTNAME",
    "PORT",  # Often has a default
}


def extract_env_vars(directory: str | Path) -> list[EnvVar]:
    """Extract required environment variables from a project.

    This function looks for environment variables in two places:
    1. Environment template files (.env.example, .env.sample, etc.)
    2. Source code files (scanning for common env var patterns)

    Args:
        directory: Path to the project directory

    Returns:
        List of EnvVar objects representing required environment variables
    """
    directory = Path(directory)
    if not directory.is_dir():
        logger.warning(f"Directory does not exist: {directory}")
        return []

    env_vars: dict[str, EnvVar] = {}

    template_vars = _extract_from_templates(directory)
    for var in template_vars:
        env_vars[var.name] = var

    code_vars = _extract_from_code(directory)
    for var in code_vars:
        if var.name not in env_vars:
            env_vars[var.name] = var

    result = list(env_vars.values())
    result = [v for v in result if v.name not in IGNORED_ENV_VARS]
    result.sort(key=lambda v: v.name)

    logger.debug(f"Extracted {len(result)} environment variables from {directory}")
    return result


def _extract_from_templates(directory: Path) -> list[EnvVar]:
    """Extract environment variables from template files."""
    env_vars = []

    for template_name in ENV_TEMPLATE_FILES:
        template_path = directory / template_name
        if template_path.exists():
            logger.debug(f"Parsing env template: {template_name}")
            vars_from_file = _parse_env_file(template_path)
            for var in vars_from_file:
                var.source = template_name
            env_vars.extend(vars_from_file)

    return env_vars


def _parse_env_file(file_path: Path) -> list[EnvVar]:
    """Parse an environment file and extract variables."""
    env_vars = []
    current_comment = None

    try:
        content = file_path.read_text()
        for line in content.split("\n"):
            line = line.strip()

            if not line:
                current_comment = None
                continue

            if line.startswith("#"):
                comment_text = line[1:].strip()
                if current_comment:
                    current_comment += " " + comment_text
                else:
                    current_comment = comment_text
                continue

            match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
            if match:
                name = match.group(1)
                value = match.group(2).strip()

                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                has_default = bool(value) and not value.startswith("your_") and not value.startswith("<")
                is_placeholder = any(
                    placeholder in value.lower()
                    for placeholder in ["your_", "<", "xxx", "changeme", "replace", "example", "localhost", "127.0.0.1"]
                )

                env_vars.append(
                    EnvVar(
                        name=name,
                        required=not has_default or is_placeholder,
                        default=value if has_default and not is_placeholder else None,
                        description=current_comment,
                    )
                )
                current_comment = None

    except OSError as e:
        logger.warning(f"Failed to read env file {file_path}: {e}")

    return env_vars


def _extract_from_code(directory: Path) -> list[EnvVar]:
    """Extract environment variables from source code files."""
    env_vars: dict[str, EnvVar] = {}

    for entry_file in COMMON_ENTRY_FILES:
        file_path = directory / entry_file
        if file_path.exists():
            logger.debug(f"Scanning entry file for env vars: {entry_file}")
            vars_from_file = _scan_file_for_env_vars(file_path)
            for var in vars_from_file:
                if var.name not in env_vars:
                    var.source = entry_file
                    env_vars[var.name] = var

    config_patterns = [
        "config.py",
        "config.ts",
        "config.js",
        "settings.py",
        "src/config.py",
        "src/config.ts",
        "src/config.js",
        "lib/config.py",
        "lib/config.ts",
        "lib/config.js",
    ]

    for config_file in config_patterns:
        file_path = directory / config_file
        if file_path.exists():
            logger.debug(f"Scanning config file for env vars: {config_file}")
            vars_from_file = _scan_file_for_env_vars(file_path)
            for var in vars_from_file:
                if var.name not in env_vars:
                    var.source = config_file
                    env_vars[var.name] = var

    return list(env_vars.values())


def _scan_file_for_env_vars(file_path: Path) -> list[EnvVar]:
    """Scan a source file for environment variable usage."""
    env_vars: dict[str, EnvVar] = {}

    extension = file_path.suffix.lstrip(".")
    patterns = CODE_FILE_EXTENSIONS.get(extension, [])

    if not patterns:
        return []

    try:
        content = file_path.read_text()

        for pattern in patterns:
            for match in pattern.finditer(content):
                groups = match.groups()
                if len(groups) == 1:
                    var_name = groups[0]
                elif len(groups) == 2:
                    var_name = groups[1]
                else:
                    continue

                if var_name and var_name not in env_vars:
                    env_vars[var_name] = EnvVar(
                        name=var_name,
                        required=True,
                    )

    except OSError as e:
        logger.warning(f"Failed to read file {file_path}: {e}")

    return list(env_vars.values())


def get_env_vars_by_source(env_vars: list[EnvVar]) -> dict[str, list[EnvVar]]:
    """Group environment variables by their source file.

    Args:
        env_vars: List of EnvVar objects

    Returns:
        Dictionary mapping source file names to lists of EnvVar objects
    """
    by_source: dict[str, list[EnvVar]] = {}
    for var in env_vars:
        source = var.source or "unknown"
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(var)
    return by_source
