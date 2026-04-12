"""Tests for the framework detection module."""

from pathlib import Path

from openops.analysis.detector import (
    detect_existing_configs,
    detect_framework,
    detect_project_type,
    get_missing_configs,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestDetectProjectType:
    """Tests for detect_project_type function."""

    def test_detect_node_project(self):
        """Test detection of Node.js project."""
        result = detect_project_type(FIXTURES_DIR / "nextjs_app")
        assert result is not None
        assert result.project_type == "node_project"
        assert "package.json" in result.root_files

    def test_detect_python_project_pyproject(self):
        """Test detection of Python project with pyproject.toml."""
        result = detect_project_type(FIXTURES_DIR / "fastapi_app")
        assert result is not None
        assert result.project_type == "python_project"
        assert "pyproject.toml" in result.root_files

    def test_detect_python_project_requirements(self):
        """Test detection of Python project with requirements.txt."""
        result = detect_project_type(FIXTURES_DIR / "django_app")
        assert result is not None
        assert result.project_type == "python_project"
        assert "requirements.txt" in result.root_files

    def test_detect_go_project(self):
        """Test detection of Go project."""
        result = detect_project_type(FIXTURES_DIR / "go_app")
        assert result is not None
        assert result.project_type == "go_project"
        assert "go.mod" in result.root_files

    def test_detect_rust_project(self):
        """Test detection of Rust project."""
        result = detect_project_type(FIXTURES_DIR / "rust_app")
        assert result is not None
        assert result.project_type == "rust_project"
        assert "Cargo.toml" in result.root_files

    def test_detect_monorepo(self):
        """Test detection of monorepo."""
        result = detect_project_type(FIXTURES_DIR / "monorepo")
        assert result is not None
        assert result.is_monorepo is True
        assert result.monorepo_type == "turborepo"
        assert "turbo.json" in result.root_files

    def test_nonexistent_directory(self):
        """Test with non-existent directory."""
        result = detect_project_type(FIXTURES_DIR / "nonexistent")
        assert result is None

    def test_empty_directory(self, tmp_path):
        """Test with empty directory."""
        result = detect_project_type(tmp_path)
        assert result is None


class TestDetectFramework:
    """Tests for detect_framework function."""

    def test_detect_nextjs(self):
        """Test detection of Next.js framework."""
        result = detect_framework(FIXTURES_DIR / "nextjs_app")
        assert result is not None
        assert result.framework == "nextjs"
        assert result.language == "typescript"
        assert result.service_type == "frontend"
        assert result.default_port == 3000
        assert result.confidence == 1.0

    def test_detect_nextjs_version(self):
        """Test Next.js version extraction."""
        result = detect_framework(FIXTURES_DIR / "nextjs_app")
        assert result is not None
        assert result.version == "14.0.0"

    def test_detect_nextjs_scripts(self):
        """Test Next.js build/start command detection."""
        result = detect_framework(FIXTURES_DIR / "nextjs_app")
        assert result is not None
        assert result.build_command == "npm run build"
        assert result.start_command == "npm start"

    def test_detect_fastapi(self):
        """Test detection of FastAPI framework."""
        result = detect_framework(FIXTURES_DIR / "fastapi_app")
        assert result is not None
        assert result.framework == "fastapi"
        assert result.language == "python"
        assert result.service_type == "backend"
        assert result.default_port == 8000

    def test_detect_fastapi_entry_point(self):
        """Test FastAPI entry point and start command."""
        result = detect_framework(FIXTURES_DIR / "fastapi_app")
        assert result is not None
        assert result.entry_point == "main.py"
        assert "uvicorn" in result.start_command

    def test_detect_django(self):
        """Test detection of Django framework."""
        result = detect_framework(FIXTURES_DIR / "django_app")
        assert result is not None
        assert result.framework == "django"
        assert result.language == "python"
        assert result.service_type == "backend"

    def test_detect_vite(self):
        """Test detection of Vite framework."""
        result = detect_framework(FIXTURES_DIR / "vite_app")
        assert result is not None
        assert result.framework == "vite"
        assert result.language == "typescript"
        assert result.service_type == "frontend"
        assert result.default_port == 5173

    def test_detect_express(self):
        """Test detection of Express framework."""
        result = detect_framework(FIXTURES_DIR / "express_app")
        assert result is not None
        assert result.framework == "express"
        assert result.language == "javascript"
        assert result.service_type == "backend"

    def test_detect_go_gin(self):
        """Test detection of Go Gin framework."""
        result = detect_framework(FIXTURES_DIR / "go_app")
        assert result is not None
        assert result.framework == "gin"
        assert result.language == "go"
        assert result.service_type == "backend"

    def test_detect_rust_actix(self):
        """Test detection of Rust Actix-web framework."""
        result = detect_framework(FIXTURES_DIR / "rust_app")
        assert result is not None
        assert result.framework == "actix-web"
        assert result.language == "rust"
        assert result.service_type == "backend"

    def test_nonexistent_directory(self):
        """Test with non-existent directory."""
        result = detect_framework(FIXTURES_DIR / "nonexistent")
        assert result is None


class TestDetectExistingConfigs:
    """Tests for detect_existing_configs function."""

    def test_no_configs(self, tmp_path):
        """Test project with no deployment configs."""
        (tmp_path / "package.json").write_text("{}")
        result = detect_existing_configs(tmp_path)
        assert result == []

    def test_detect_dockerfile(self, tmp_path):
        """Test detection of Dockerfile."""
        (tmp_path / "Dockerfile").write_text("FROM node:18")
        result = detect_existing_configs(tmp_path)
        assert len(result) == 1
        assert result[0].config_type == "docker"

    def test_detect_vercel_config(self, tmp_path):
        """Test detection of vercel.json."""
        (tmp_path / "vercel.json").write_text("{}")
        result = detect_existing_configs(tmp_path)
        assert len(result) == 1
        assert result[0].config_type == "vercel"
        assert result[0].platform == "vercel"

    def test_detect_railway_config(self, tmp_path):
        """Test detection of railway.toml."""
        (tmp_path / "railway.toml").write_text("")
        result = detect_existing_configs(tmp_path)
        assert len(result) == 1
        assert result[0].config_type == "railway"
        assert result[0].platform == "railway"

    def test_detect_multiple_configs(self, tmp_path):
        """Test detection of multiple configs."""
        (tmp_path / "Dockerfile").write_text("FROM node:18")
        (tmp_path / "vercel.json").write_text("{}")
        (tmp_path / "render.yaml").write_text("")
        result = detect_existing_configs(tmp_path)
        assert len(result) == 3
        config_types = {c.config_type for c in result}
        assert "docker" in config_types
        assert "vercel" in config_types
        assert "render" in config_types


class TestGetMissingConfigs:
    """Tests for get_missing_configs function."""

    def test_missing_vercel_config(self, tmp_path):
        """Test detection of missing vercel config."""
        (tmp_path / "package.json").write_text("{}")
        result = get_missing_configs(tmp_path, "vercel")
        assert "vercel" in result

    def test_vercel_config_present(self, tmp_path):
        """Test when vercel config is present."""
        (tmp_path / "vercel.json").write_text("{}")
        result = get_missing_configs(tmp_path, "vercel")
        assert result == []

    def test_missing_railway_config(self, tmp_path):
        """Test detection of missing railway config."""
        (tmp_path / "pyproject.toml").write_text("")
        result = get_missing_configs(tmp_path, "railway")
        assert "railway" in result

    def test_railway_config_present(self, tmp_path):
        """Test when railway config is present."""
        (tmp_path / "railway.toml").write_text("")
        result = get_missing_configs(tmp_path, "railway")
        assert result == []
