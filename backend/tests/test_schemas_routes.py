"""Unit tests for route schema validators."""

from datetime import time

import pytest
from app.schemas.routes import _validate_day_codes, _validate_time_range, _validate_timezone


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

    def test_valid_timezone_london(self) -> None:
        """Test validation passes with Europe/London timezone."""
        result = _validate_timezone("Europe/London")
        assert result == "Europe/London"

    def test_valid_timezone_new_york(self) -> None:
        """Test validation passes with America/New_York timezone."""
        result = _validate_timezone("America/New_York")
        assert result == "America/New_York"

    def test_valid_timezone_tokyo(self) -> None:
        """Test validation passes with Asia/Tokyo timezone."""
        result = _validate_timezone("Asia/Tokyo")
        assert result == "Asia/Tokyo"

    def test_valid_timezone_utc(self) -> None:
        """Test validation passes with UTC timezone."""
        result = _validate_timezone("UTC")
        assert result == "UTC"

    def test_invalid_timezone(self) -> None:
        """Test validation fails with invalid timezone."""
        with pytest.raises(ValueError, match="Invalid IANA timezone: Invalid/Timezone"):
            _validate_timezone("Invalid/Timezone")

    def test_invalid_timezone_typo(self) -> None:
        """Test validation fails with typo in timezone name."""
        with pytest.raises(ValueError, match="Invalid IANA timezone: Europe/Londan"):
            _validate_timezone("Europe/Londan")

    def test_invalid_timezone_empty_string(self) -> None:
        """Test validation fails with empty string."""
        with pytest.raises(ValueError, match="Invalid IANA timezone: "):
            _validate_timezone("")

    def test_timezone_none(self) -> None:
        """Test validation passes when timezone is None."""
        result = _validate_timezone(None)
        assert result is None
