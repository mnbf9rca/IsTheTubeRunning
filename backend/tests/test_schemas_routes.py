"""Unit tests for route schema validators."""

from datetime import time
from unittest.mock import patch

import pytest
from app.schemas.routes import (
    CreateUserRouteRequest,
    _validate_day_codes,
    _validate_time_range,
    _validate_timezone,
)


class TestValidateDayCodes:
    """Tests for _validate_day_codes helper function."""

    def test_valid_days(self) -> None:
        """Test validation passes with valid day codes."""
        days = ["MON", "TUE", "WED"]
        result = _validate_day_codes(days)
        assert result == days

    def test_all_valid_days(self) -> None:
        """Test validation passes with all valid day codes."""
        days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        result = _validate_day_codes(days)
        assert result == days

    def test_invalid_day_code(self) -> None:
        """Test validation fails with invalid day code."""
        with pytest.raises(ValueError, match=r"Invalid day codes: \{'MONDAY'\}"):
            _validate_day_codes(["MON", "MONDAY"])

    def test_duplicate_day_codes(self) -> None:
        """Test validation fails with duplicate day codes."""
        with pytest.raises(ValueError, match="Duplicate day codes are not allowed"):
            _validate_day_codes(["MON", "TUE", "MON"])

    def test_empty_list(self) -> None:
        """Test validation passes with empty list (field validator handles min_length)."""
        result = _validate_day_codes([])
        assert result == []


class TestValidateTimeRange:
    """Tests for _validate_time_range helper function."""

    def test_valid_time_range(self) -> None:
        """Test validation passes when end_time > start_time."""
        start = time(9, 0)
        end = time(17, 0)
        _validate_time_range(start, end)  # Should not raise

    def test_invalid_time_range_equal(self) -> None:
        """Test validation fails when end_time == start_time."""
        same_time = time(9, 0)
        with pytest.raises(ValueError, match="end_time must be after start_time"):
            _validate_time_range(same_time, same_time)

    def test_invalid_time_range_before(self) -> None:
        """Test validation fails when end_time < start_time."""
        start = time(17, 0)
        end = time(9, 0)
        with pytest.raises(ValueError, match="end_time must be after start_time"):
            _validate_time_range(start, end)

    def test_both_none(self) -> None:
        """Test validation passes when both times are None."""
        _validate_time_range(None, None)  # Should not raise

    def test_start_none(self) -> None:
        """Test validation passes when only start_time is None."""
        _validate_time_range(None, time(17, 0))  # Should not raise

    def test_end_none(self) -> None:
        """Test validation passes when only end_time is None."""
        _validate_time_range(time(9, 0), None)  # Should not raise

    def test_microsecond_difference(self) -> None:
        """Test validation passes with minimal time difference."""
        start = time(9, 0, 0, 0)
        end = time(9, 0, 0, 1)
        _validate_time_range(start, end)  # Should not raise


class TestValidateTimezone:
    """Tests for _validate_timezone helper function."""

    @pytest.mark.parametrize(
        "timezone",
        [
            "Europe/London",
            "America/New_York",
            "Asia/Tokyo",
            "Australia/Sydney",
            "UTC",
        ],
    )
    def test_valid_canonical_timezone(self, timezone: str) -> None:
        """Test that canonical IANA timezone names are accepted."""
        result = _validate_timezone(timezone)
        assert result == timezone

    @pytest.mark.parametrize(
        "invalid_timezone",
        [
            "Invalid/Timezone",
            "europe/london",  # Wrong case - rejected deterministically
            "EUROPE/LONDON",  # Wrong case - rejected deterministically
            "Europe/Londan",  # Typo
            "",
        ],
    )
    def test_invalid_timezone_rejected(self, invalid_timezone: str) -> None:
        """Test that invalid timezone names are rejected deterministically."""
        with pytest.raises(ValueError, match="Invalid IANA timezone"):
            _validate_timezone(invalid_timezone)

    def test_timezone_none(self) -> None:
        """Test validation passes when timezone is None."""
        result = _validate_timezone(None)
        assert result is None

    def test_zoneinfo_exception_handling(self) -> None:
        """Test that ZoneInfo exception is caught and re-raised as ValueError."""
        # Mock ZoneInfo to raise an exception even for valid timezone
        with patch("app.schemas.routes.ZoneInfo") as mock_zoneinfo:
            mock_zoneinfo.side_effect = RuntimeError("Simulated ZoneInfo error")

            # Should catch the exception and raise ValueError
            with pytest.raises(ValueError, match="Invalid IANA timezone: Europe/London"):
                _validate_timezone("Europe/London")


class TestCreateUserRouteRequest:
    """Tests for CreateUserRouteRequest schema."""

    def test_validate_timezone_none_handling(self) -> None:
        """Test that validator handles unexpected None from _validate_timezone."""
        # Mock _validate_timezone to return None (should never happen in practice)
        with patch("app.schemas.routes._validate_timezone") as mock_validate:
            mock_validate.return_value = None

            # Should raise ValueError when None is returned
            with pytest.raises(ValueError, match="Invalid timezone"):
                CreateUserRouteRequest(name="Test Route", timezone="Europe/London")
