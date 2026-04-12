"""Tests for the environment variable extraction module."""

from pathlib import Path

from openops.analysis.env_extractor import (
    EnvVar,
    extract_env_vars,
    get_env_vars_by_source,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestExtractEnvVars:
    """Tests for extract_env_vars function."""

    def test_extract_from_nextjs_app(self):
        """Test env var extraction from Next.js app."""
        result = extract_env_vars(FIXTURES_DIR / "nextjs_app")
        var_names = {v.name for v in result}
        assert "DATABASE_URL" in var_names
        assert "NEXT_PUBLIC_API_URL" in var_names
        assert "SECRET_KEY" in var_names

    def test_extract_from_fastapi_app(self):
        """Test env var extraction from FastAPI app."""
        result = extract_env_vars(FIXTURES_DIR / "fastapi_app")
        var_names = {v.name for v in result}
        assert "DATABASE_URL" in var_names
        assert "API_KEY" in var_names

    def test_extract_from_env_example(self, tmp_path):
        """Test extraction from .env.example file."""
        env_example = tmp_path / ".env.example"
        env_example.write_text(
            "# API Configuration\n"
            "API_KEY=your_api_key_here\n"
            "DATABASE_URL=postgresql://localhost/db\n"
            "DEBUG=true\n"
        )
        result = extract_env_vars(tmp_path)
        var_names = {v.name for v in result}
        assert "API_KEY" in var_names
        assert "DATABASE_URL" in var_names
        assert "DEBUG" in var_names

    def test_required_detection_placeholder(self, tmp_path):
        """Test that placeholder values are marked as required."""
        env_example = tmp_path / ".env.example"
        env_example.write_text("API_KEY=your_api_key_here\n" "SECRET=<replace_me>\n")
        result = extract_env_vars(tmp_path)
        api_key = next(v for v in result if v.name == "API_KEY")
        secret = next(v for v in result if v.name == "SECRET")
        assert api_key.required is True
        assert secret.required is True

    def test_default_value_detection(self, tmp_path):
        """Test that real default values are detected."""
        env_example = tmp_path / ".env.example"
        env_example.write_text("LOG_LEVEL=info\n" "TIMEOUT=30\n")
        result = extract_env_vars(tmp_path)
        log_level = next(v for v in result if v.name == "LOG_LEVEL")
        timeout = next(v for v in result if v.name == "TIMEOUT")
        assert log_level.default == "info"
        assert timeout.default == "30"

    def test_comment_as_description(self, tmp_path):
        """Test that comments become descriptions."""
        env_example = tmp_path / ".env.example"
        env_example.write_text("# The database connection string\n" "DATABASE_URL=\n")
        result = extract_env_vars(tmp_path)
        db_url = next(v for v in result if v.name == "DATABASE_URL")
        assert db_url.description == "The database connection string"

    def test_extract_from_js_code(self, tmp_path):
        """Test extraction from JavaScript code."""
        js_file = tmp_path / "index.js"
        js_file.write_text("const apiKey = process.env.API_KEY;\n" "const dbUrl = process.env.DATABASE_URL;\n")
        result = extract_env_vars(tmp_path)
        var_names = {v.name for v in result}
        assert "API_KEY" in var_names
        assert "DATABASE_URL" in var_names

    def test_extract_from_ts_code(self, tmp_path):
        """Test extraction from TypeScript code."""
        ts_file = tmp_path / "index.ts"
        ts_file.write_text(
            "const apiKey: string = process.env.API_KEY!;\n" "const secret = process.env['SECRET_KEY'];\n"
        )
        result = extract_env_vars(tmp_path)
        var_names = {v.name for v in result}
        assert "API_KEY" in var_names
        assert "SECRET_KEY" in var_names

    def test_extract_from_python_code(self, tmp_path):
        """Test extraction from Python code."""
        py_file = tmp_path / "app.py"
        py_file.write_text(
            "import os\n"
            "db_url = os.environ['DATABASE_URL']\n"
            "api_key = os.getenv('API_KEY')\n"
            "secret = os.environ.get('SECRET')\n"
        )
        result = extract_env_vars(tmp_path)
        var_names = {v.name for v in result}
        assert "DATABASE_URL" in var_names
        assert "API_KEY" in var_names
        assert "SECRET" in var_names

    def test_extract_from_go_code(self):
        """Test extraction from Go code."""
        result = extract_env_vars(FIXTURES_DIR / "go_app")
        var_names = {v.name for v in result}
        assert "API_KEY" in var_names

    def test_extract_from_rust_code(self):
        """Test extraction from Rust code."""
        result = extract_env_vars(FIXTURES_DIR / "rust_app")
        var_names = {v.name for v in result}
        assert "API_KEY" in var_names

    def test_ignore_common_vars(self, tmp_path):
        """Test that common system env vars are ignored."""
        js_file = tmp_path / "index.js"
        js_file.write_text(
            "const env = process.env.NODE_ENV;\n" "const home = process.env.HOME;\n" "const path = process.env.PATH;\n"
        )
        result = extract_env_vars(tmp_path)
        var_names = {v.name for v in result}
        assert "NODE_ENV" not in var_names
        assert "HOME" not in var_names
        assert "PATH" not in var_names

    def test_nonexistent_directory(self):
        """Test with non-existent directory."""
        result = extract_env_vars(FIXTURES_DIR / "nonexistent")
        assert result == []

    def test_empty_directory(self, tmp_path):
        """Test with empty directory."""
        result = extract_env_vars(tmp_path)
        assert result == []


class TestGetEnvVarsBySource:
    """Tests for get_env_vars_by_source function."""

    def test_group_by_source(self):
        """Test grouping env vars by source."""
        env_vars = [
            EnvVar(name="VAR1", source=".env.example"),
            EnvVar(name="VAR2", source=".env.example"),
            EnvVar(name="VAR3", source="app.py"),
        ]
        result = get_env_vars_by_source(env_vars)
        assert len(result[".env.example"]) == 2
        assert len(result["app.py"]) == 1

    def test_unknown_source(self):
        """Test handling of env vars without source."""
        env_vars = [
            EnvVar(name="VAR1", source=None),
        ]
        result = get_env_vars_by_source(env_vars)
        assert "unknown" in result
        assert len(result["unknown"]) == 1
