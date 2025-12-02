"""Tests for database credential extraction utility."""

import os
from io import StringIO
from unittest.mock import patch

import pytest
from app.utils.extract_db_credentials import (
    extract_credentials,
    extract_env_var,
    get_mode_from_args,
    load_database_url,
    main,
)


class TestGetModeFromArgs:
    """Tests for get_mode_from_args function."""

    def test_returns_mode_when_argument_provided(self) -> None:
        """Test that mode is returned when provided in arguments."""
        assert get_mode_from_args(["script.py", "export"]) == "export"
        assert get_mode_from_args(["script.py", "user"]) == "user"
        assert get_mode_from_args(["script.py", "password"]) == "password"

    def test_raises_error_when_no_argument(self) -> None:
        """Test that ValueError is raised when no argument provided."""
        with pytest.raises(ValueError, match="Mode argument required"):
            get_mode_from_args(["script.py"])

    def test_raises_error_for_empty_args(self) -> None:
        """Test that ValueError is raised for empty argument list."""
        with pytest.raises(ValueError, match="Mode argument required"):
            get_mode_from_args([])


class TestLoadDatabaseUrl:
    """Tests for load_database_url function."""

    def test_returns_database_url_from_environment(self) -> None:
        """Test that SECRET_DATABASE_URL is returned when present in environment."""
        test_url = "postgresql+asyncpg://test:test@localhost:5432/test"
        with patch.dict(os.environ, {"SECRET_DATABASE_URL": test_url}):
            assert load_database_url() == test_url

    def test_raises_value_error_when_database_url_empty(self) -> None:
        """Test that ValueError is raised when SECRET_DATABASE_URL is empty."""
        with (
            patch.dict(os.environ, {"SECRET_DATABASE_URL": ""}, clear=True),
            pytest.raises(ValueError, match="SECRET_DATABASE_URL not found in environment"),
        ):
            load_database_url()

    def test_raises_value_error_when_database_url_missing(self) -> None:
        """Test that ValueError is raised when SECRET_DATABASE_URL is not set."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="SECRET_DATABASE_URL not found in environment"),
        ):
            load_database_url()


class TestExtractDbCredentials:
    """Tests for extract_db_credentials module."""

    @pytest.fixture
    def sample_database_url(self) -> str:
        """Sample DATABASE_URL for testing."""
        return "postgresql+asyncpg://testuser:testpass123@db.example.com:5432/testdb"

    @pytest.fixture
    def database_url_no_password(self) -> str:
        """DATABASE_URL without password."""
        return "postgresql+asyncpg://testuser@db.example.com:5432/testdb"

    @pytest.fixture
    def database_url_default_port(self) -> str:
        """DATABASE_URL without explicit port."""
        return "postgresql+asyncpg://testuser:testpass123@db.example.com/testdb"

    def test_export_mode_all_credentials(self, sample_database_url: str) -> None:
        """Test export mode outputs all credentials in bash export format."""
        result = extract_credentials(sample_database_url, "export")

        # shlex.quote() only adds quotes when necessary
        assert "export PGUSER=testuser" in result
        assert "export PGPASSWORD=testpass123" in result
        assert "export PGHOST=db.example.com" in result
        assert "export PGPORT=5432" in result
        assert "export PGDATABASE=testdb" in result

    def test_single_field_extraction_password(self, sample_database_url: str) -> None:
        """Test extracting password field only."""
        result = extract_credentials(sample_database_url, "password")
        assert result == "testpass123"

    def test_single_field_extraction_user(self, sample_database_url: str) -> None:
        """Test extracting user field only."""
        result = extract_credentials(sample_database_url, "user")
        assert result == "testuser"

    def test_single_field_extraction_host(self, sample_database_url: str) -> None:
        """Test extracting host field only."""
        result = extract_credentials(sample_database_url, "host")
        assert result == "db.example.com"

    def test_single_field_extraction_port(self, sample_database_url: str) -> None:
        """Test extracting port field only."""
        result = extract_credentials(sample_database_url, "port")
        assert result == "5432"

    def test_single_field_extraction_database(self, sample_database_url: str) -> None:
        """Test extracting database field only."""
        result = extract_credentials(sample_database_url, "database")
        assert result == "testdb"

    def test_default_mode_extracts_password(self, sample_database_url: str) -> None:
        """Test that default mode (no arguments) extracts password."""
        result = extract_credentials(sample_database_url)  # Default mode
        assert result == "testpass123"

    def test_missing_database_url_exits_with_error(self) -> None:
        """Test that missing SECRET_DATABASE_URL raises ValueError."""
        with pytest.raises(ValueError, match="SECRET_DATABASE_URL cannot be empty"):
            extract_credentials("", "export")

    def test_invalid_mode_exits_with_error(self, sample_database_url: str) -> None:
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            extract_credentials(sample_database_url, "invalid_mode")

    def test_url_without_password(self, database_url_no_password: str) -> None:
        """Test extraction when DATABASE_URL has no password."""
        result = extract_credentials(database_url_no_password, "export")

        assert "export PGUSER=testuser" in result
        assert "export PGPASSWORD=''" in result  # Empty password (quotes needed for empty string)
        assert "export PGHOST=db.example.com" in result

    def test_url_with_default_port(self, database_url_default_port: str) -> None:
        """Test extraction when DATABASE_URL doesn't specify port (should default to 5432)."""
        result = extract_credentials(database_url_default_port, "export")

        assert "export PGPORT=5432" in result  # Default PostgreSQL port

    def test_special_characters_in_password(self) -> None:
        """Test extraction with special characters in password."""
        special_password_url = "postgresql+asyncpg://user:p@ss!w0rd%23@localhost:5432/mydb"
        result = extract_credentials(special_password_url, "password")

        # URL-encoded %23 is preserved as-is by urlparse (doesn't decode)
        # If you need decoded values, use urllib.parse.unquote()
        assert result == "p@ss!w0rd%23"

    def test_localhost_url(self) -> None:
        """Test extraction with localhost URL."""
        localhost_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/isthetube"
        result = extract_credentials(localhost_url, "export")

        assert "export PGHOST=localhost" in result
        assert "export PGUSER=postgres" in result
        assert "export PGDATABASE=isthetube" in result


class TestExtractEnvVar:
    """Tests for extract_env_var function."""

    def test_extracts_environment_variable_when_present(self) -> None:
        """Test that environment variable is extracted when present."""
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"
        with patch.dict(os.environ, {"CLOUDFLARE_TUNNEL_TOKEN": test_token}):
            result = extract_env_var("CLOUDFLARE_TUNNEL_TOKEN")
            assert result == test_token

    def test_raises_value_error_when_variable_missing(self) -> None:
        """Test that ValueError is raised when environment variable is missing."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="CLOUDFLARE_TUNNEL_TOKEN not found in environment"),
        ):
            extract_env_var("CLOUDFLARE_TUNNEL_TOKEN")

    def test_raises_value_error_when_variable_empty(self) -> None:
        """Test that ValueError is raised when environment variable is empty."""
        with (
            patch.dict(os.environ, {"CLOUDFLARE_TUNNEL_TOKEN": ""}),
            pytest.raises(ValueError, match="CLOUDFLARE_TUNNEL_TOKEN not found in environment"),
        ):
            extract_env_var("CLOUDFLARE_TUNNEL_TOKEN")

    def test_works_with_different_variable_names(self) -> None:
        """Test that function works with any environment variable name."""
        test_value = "test_value_123"
        with patch.dict(os.environ, {"SOME_OTHER_VAR": test_value}):
            result = extract_env_var("SOME_OTHER_VAR")
            assert result == test_value


class TestMainFunction:
    """Tests for main CLI function with tunnel_token mode."""

    def test_main_extracts_tunnel_token_successfully(self) -> None:
        """Test that main() extracts CLOUDFLARE_TUNNEL_TOKEN when tunnel_token mode is used."""
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"

        with (
            patch.dict(os.environ, {"CLOUDFLARE_TUNNEL_TOKEN": test_token}),
            patch("sys.argv", ["script.py", "tunnel_token"]),
            patch("sys.stdout", new=StringIO()) as mock_stdout,
        ):
            main()
            output = mock_stdout.getvalue()
            assert output.strip() == test_token

    def test_main_extracts_password_for_database_mode(self) -> None:
        """Test that main() extracts database password for password mode."""
        test_db_url = "postgresql+asyncpg://user:testpass@localhost:5432/db"

        with (
            patch.dict(os.environ, {"SECRET_DATABASE_URL": test_db_url}),
            patch("sys.argv", ["script.py", "password"]),
            patch("sys.stdout", new=StringIO()) as mock_stdout,
        ):
            main()
            output = mock_stdout.getvalue()
            assert output.strip() == "testpass"

    def test_main_exits_with_error_for_missing_tunnel_token(self) -> None:
        """Test that main() exits with error when CLOUDFLARE_TUNNEL_TOKEN is missing."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.argv", ["script.py", "tunnel_token"]),
            patch("sys.stderr", new=StringIO()) as mock_stderr,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        error_output = mock_stderr.getvalue()
        assert "CLOUDFLARE_TUNNEL_TOKEN not found in environment" in error_output
