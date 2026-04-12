"""Project analysis module for OpenOps.

This module provides tools for analyzing project structure, detecting frameworks,
extracting environment variables, and identifying deployment requirements.
"""

from openops.analysis.analyzer import ProjectAnalyzer, analyze_project
from openops.analysis.detector import (
    FrameworkInfo,
    detect_existing_configs,
    detect_framework,
    detect_project_type,
)
from openops.analysis.env_extractor import EnvVar, extract_env_vars

__all__ = [
    "ProjectAnalyzer",
    "analyze_project",
    "FrameworkInfo",
    "detect_framework",
    "detect_project_type",
    "detect_existing_configs",
    "EnvVar",
    "extract_env_vars",
]
