"""Tests for configuration module."""

import pytest
from app.core.config import Settings, require_config, settings


class TestRequireConfig:
    """Tests for require_config function."""

    def test_require_config_passes_when_all_fields_present(self) -> None:
        """Test that require_config passes when all required fields are set."""
        # These fields should always be set in test environment
        require_config("DEBUG", "PROJECT_NAME")
        # If we get here without exception, test passes

    def test_require_config_raises_when_field_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that require_config raises ValueError when a field is None."""
        # Set a field to None
        monkeypatch.setattr(settings, "TFL_API_KEY", None)

        # Should raise ValueError
        with pytest.raises(ValueError, match="Required configuration missing: TFL_API_KEY"):
            require_config("TFL_API_KEY")

    def test_require_config_raises_when_field_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that require_config raises ValueError when a field is empty string."""
        # Set a field to empty string
        monkeypatch.setattr(settings, "PROJECT_NAME", "")

        # Should raise ValueError
        with pytest.raises(ValueError, match="Required configuration missing: PROJECT_NAME"):
            require_config("PROJECT_NAME")

    def test_require_config_raises_when_field_whitespace_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that require_config raises ValueError when a field is whitespace only."""
        # Set a field to whitespace only
        monkeypatch.setattr(settings, "PROJECT_NAME", "   ")

        # Should raise ValueError
        with pytest.raises(ValueError, match="Required configuration missing: PROJECT_NAME"):
            require_config("PROJECT_NAME")

    def test_require_config_raises_with_multiple_missing_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that require_config lists all missing fields in error message."""
        # Set multiple fields to None
        monkeypatch.setattr(settings, "TFL_API_KEY", None)
        monkeypatch.setattr(settings, "SMTP_HOST", None)

        # Should raise ValueError with both fields listed
        with pytest.raises(ValueError, match="Required configuration missing:") as exc_info:
            require_config("TFL_API_KEY", "SMTP_HOST")

        error_message = str(exc_info.value)
        assert "TFL_API_KEY" in error_message
        assert "SMTP_HOST" in error_message

    def test_require_config_raises_when_field_does_not_exist(self) -> None:
        """Test that require_config raises ValueError when field doesn't exist on settings."""
        # Field that doesn't exist on settings object
        with pytest.raises(ValueError, match="Required configuration missing: NONEXISTENT_FIELD"):
            require_config("NONEXISTENT_FIELD")


class TestParseCorsValidator:
    """Tests for parse_cors field validator."""

    def test_parse_cors_with_string(self) -> None:
        """Test parse_cors splits comma-separated string into list."""
        result = Settings.parse_cors("http://localhost:3000,http://localhost:8080")
        assert result == ["http://localhost:3000", "http://localhost:8080"]

    def test_parse_cors_with_string_strips_whitespace(self) -> None:
        """Test parse_cors removes whitespace around origins."""
        result = Settings.parse_cors("http://localhost:3000, http://localhost:8080 , http://example.com")
        assert result == ["http://localhost:3000", "http://localhost:8080", "http://example.com"]

    def test_parse_cors_with_single_origin(self) -> None:
        """Test parse_cors handles single origin string."""
        result = Settings.parse_cors("http://localhost:3000")
        assert result == ["http://localhost:3000"]

    def test_parse_cors_with_list_input(self) -> None:
        """Test parse_cors passes through list unchanged (regression test)."""
        input_list = ["http://localhost:3000", "http://localhost:8080"]
        result = Settings.parse_cors(input_list)
        assert result == input_list
        assert result is input_list  # Same object, not a copy


class TestParseAuth0AlgorithmsValidator:
    """Tests for parse_auth0_algorithms field validator."""

    def test_parse_auth0_algorithms_with_string(self) -> None:
        """Test parse_auth0_algorithms splits comma-separated string into list."""
        result = Settings.parse_auth0_algorithms("RS256,HS256")
        assert result == ["RS256", "HS256"]

    def test_parse_auth0_algorithms_with_string_strips_whitespace(self) -> None:
        """Test parse_auth0_algorithms removes whitespace around algorithms."""
        result = Settings.parse_auth0_algorithms("RS256, HS256 , ES256")
        assert result == ["RS256", "HS256", "ES256"]

    def test_parse_auth0_algorithms_with_single_algorithm(self) -> None:
        """Test parse_auth0_algorithms handles single algorithm string."""
        result = Settings.parse_auth0_algorithms("RS256")
        assert result == ["RS256"]

    def test_parse_auth0_algorithms_with_list_input(self) -> None:
        """Test parse_auth0_algorithms passes through list unchanged (regression test)."""
        input_list = ["RS256", "HS256"]
        result = Settings.parse_auth0_algorithms(input_list)
        assert result == input_list
        assert result is input_list  # Same object, not a copy


class TestValidateLogLevelValidator:
    """Tests for validate_log_level field validator."""

    def test_validate_log_level_with_valid_levels(self) -> None:
        """Test validate_log_level accepts all valid log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            result = Settings.validate_log_level(level)
            assert result == level

    def test_validate_log_level_normalizes_to_uppercase(self) -> None:
        """Test validate_log_level converts lowercase to uppercase."""
        result = Settings.validate_log_level("debug")
        assert result == "DEBUG"

        result = Settings.validate_log_level("info")
        assert result == "INFO"

        result = Settings.validate_log_level("Warning")
        assert result == "WARNING"

    def test_validate_log_level_raises_on_invalid(self) -> None:
        """Test validate_log_level raises ValueError for invalid levels."""
        with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
            Settings.validate_log_level("INVALID")

        with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
            Settings.validate_log_level("TRACE")

        with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
            Settings.validate_log_level("")
