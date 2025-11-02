"""Tests for configuration module."""

import pytest
from app.core.config import require_config, settings


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
