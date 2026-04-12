"""Tests for the main project analyzer module."""

from pathlib import Path

import pytest

from openops.analysis.analyzer import ProjectAnalysis, ProjectAnalyzer, analyze_project
from openops.models import Project

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestProjectAnalyzer:
    """Tests for ProjectAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a ProjectAnalyzer instance."""
        return ProjectAnalyzer()

    def test_analyze_nextjs_app(self, analyzer):
        """Test analysis of Next.js application."""
        result = analyzer.analyze(FIXTURES_DIR / "nextjs_app")

        assert isinstance(result, ProjectAnalysis)
        assert isinstance(result.project, Project)
        assert result.project.name == "nextjs_app"
        assert result.project.path == str(FIXTURES_DIR / "nextjs_app")
        assert result.project.analyzed_at is not None

        assert result.framework_info is not None
        assert result.framework_info.framework == "nextjs"
        assert result.framework_info.language == "typescript"

        assert len(result.services) == 1
        service = result.services[0]
        assert service.framework == "nextjs"
        assert service.type == "frontend"
        assert service.port == 3000

    def test_analyze_fastapi_app(self, analyzer):
        """Test analysis of FastAPI application."""
        result = analyzer.analyze(FIXTURES_DIR / "fastapi_app")

        assert result.framework_info is not None
        assert result.framework_info.framework == "fastapi"
        assert result.framework_info.language == "python"

        assert len(result.services) == 1
        service = result.services[0]
        assert service.framework == "fastapi"
        assert service.type == "backend"
        assert service.port == 8000

    def test_analyze_django_app(self, analyzer):
        """Test analysis of Django application."""
        result = analyzer.analyze(FIXTURES_DIR / "django_app")

        assert result.framework_info is not None
        assert result.framework_info.framework == "django"

    def test_analyze_vite_app(self, analyzer):
        """Test analysis of Vite application."""
        result = analyzer.analyze(FIXTURES_DIR / "vite_app")

        assert result.framework_info is not None
        assert result.framework_info.framework == "vite"
        assert result.framework_info.service_type == "frontend"

    def test_analyze_go_app(self, analyzer):
        """Test analysis of Go application."""
        result = analyzer.analyze(FIXTURES_DIR / "go_app")

        assert result.framework_info is not None
        assert result.framework_info.framework == "gin"
        assert result.framework_info.language == "go"

    def test_analyze_rust_app(self, analyzer):
        """Test analysis of Rust application."""
        result = analyzer.analyze(FIXTURES_DIR / "rust_app")

        assert result.framework_info is not None
        assert result.framework_info.framework == "actix-web"
        assert result.framework_info.language == "rust"

    def test_analyze_monorepo_detection(self, analyzer):
        """Test that monorepo is detected and noted."""
        result = analyzer.analyze(FIXTURES_DIR / "monorepo")

        assert result.project_type is not None
        assert result.project_type.is_monorepo is True
        assert result.project_type.monorepo_type == "turborepo"

        assert any("monorepo" in kp.lower() for kp in result.keypoints)

    def test_env_vars_included(self, analyzer):
        """Test that environment variables are included in analysis."""
        result = analyzer.analyze(FIXTURES_DIR / "nextjs_app")

        assert len(result.env_vars) > 0
        var_names = {v.name for v in result.env_vars}
        assert "DATABASE_URL" in var_names

    def test_env_vars_in_service(self, analyzer):
        """Test that required env vars are added to service."""
        result = analyzer.analyze(FIXTURES_DIR / "fastapi_app")

        assert len(result.services) == 1
        service = result.services[0]
        assert "DATABASE_URL" in service.env_vars

    def test_keypoints_generated(self, analyzer):
        """Test that keypoints are generated."""
        result = analyzer.analyze(FIXTURES_DIR / "nextjs_app")

        assert len(result.keypoints) > 0
        assert any("nextjs" in kp.lower() for kp in result.keypoints)

    def test_project_description_generated(self, analyzer):
        """Test that project description is generated."""
        result = analyzer.analyze(FIXTURES_DIR / "nextjs_app")

        assert result.project.description != ""
        assert "Next" in result.project.description or "next" in result.project.description.lower()

    def test_nonexistent_directory_raises(self, analyzer):
        """Test that analyzing non-existent directory raises error."""
        with pytest.raises(ValueError, match="does not exist"):
            analyzer.analyze(FIXTURES_DIR / "nonexistent")

    def test_analyze_project_function(self):
        """Test the convenience analyze_project function."""
        result = analyze_project(FIXTURES_DIR / "nextjs_app")

        assert isinstance(result, ProjectAnalysis)
        assert result.framework_info.framework == "nextjs"


class TestDeploymentReadiness:
    """Tests for deployment readiness checking."""

    @pytest.fixture
    def analyzer(self):
        """Create a ProjectAnalyzer instance."""
        return ProjectAnalyzer()

    def test_readiness_without_config(self, analyzer):
        """Test readiness check when config is missing."""
        analysis = analyzer.analyze(FIXTURES_DIR / "nextjs_app")
        readiness = analyzer.get_deployment_readiness(analysis, "vercel")

        assert readiness["ready"] is False
        assert "vercel" in readiness["missing_configs"]

    def test_readiness_with_config(self, analyzer, tmp_path):
        """Test readiness check when config is present."""
        (tmp_path / "package.json").write_text('{"name": "test", "dependencies": {"next": "14.0.0"}}')
        (tmp_path / "next.config.js").write_text("module.exports = {}")
        (tmp_path / "vercel.json").write_text("{}")

        analysis = analyzer.analyze(tmp_path)
        readiness = analyzer.get_deployment_readiness(analysis, "vercel")

        assert readiness["ready"] is True
        assert readiness["missing_configs"] == []

    def test_readiness_missing_env_vars(self, analyzer):
        """Test that missing env vars are reported."""
        analysis = analyzer.analyze(FIXTURES_DIR / "fastapi_app")
        readiness = analyzer.get_deployment_readiness(analysis, "railway")

        assert "DATABASE_URL" in readiness["missing_env_vars"]

    def test_readiness_recommendations(self, analyzer):
        """Test that recommendations are provided."""
        analysis = analyzer.analyze(FIXTURES_DIR / "nextjs_app")
        readiness = analyzer.get_deployment_readiness(analysis, "railway")

        assert len(readiness["recommendations"]) > 0
