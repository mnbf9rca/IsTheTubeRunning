"""
Unit tests for station fetching helper functions.

Tests pure validation and filtering functions used by TfLService.fetch_stations().
These tests don't require database mocking since all functions are pure.
"""

from uuid import uuid4

import pytest
from app.helpers.station_fetching import (
    DatabaseNotInitializedError,
    LineNotFoundError,
    NoStationsForLineError,
    StationFetchError,
    build_station_cache_key,
    filter_stations_by_line_tfl_id,
    is_database_initialized,
    validate_stations_exist_for_line,
)
from app.models.tfl import Station


class TestBuildStationCacheKey:
    """Tests for build_station_cache_key()."""

    def test_with_line_id(self):
        """Should build cache key with line ID."""
        result = build_station_cache_key("victoria")
        assert result == "stations:line:victoria"

    def test_without_line_id(self):
        """Should build cache key for all stations."""
        result = build_station_cache_key(None)
        assert result == "stations:all"

    def test_different_lines_produce_different_keys(self):
        """Different lines should produce different cache keys."""
        victoria = build_station_cache_key("victoria")
        northern = build_station_cache_key("northern")
        assert victoria != northern
        assert victoria == "stations:line:victoria"
        assert northern == "stations:line:northern"


class TestIsDatabaseInitialized:
    """Tests for is_database_initialized()."""

    def test_with_stations(self):
        """Should return True when stations exist."""
        assert is_database_initialized(100) is True
        assert is_database_initialized(1) is True

    def test_without_stations(self):
        """Should return False when no stations exist."""
        assert is_database_initialized(0) is False

    def test_negative_count(self):
        """Should handle negative counts (edge case)."""
        # In practice this shouldn't happen, but pure function should handle it
        assert is_database_initialized(-1) is False


class TestFilterStationsByLineTflId:
    """Tests for filter_stations_by_line_tfl_id()."""

    def test_single_match(self):
        """Should filter stations serving the specified line."""
        station1 = Station(
            id=uuid4(),
            tfl_id="ABC",
            name="Station A",
            latitude=51.5,
            longitude=-0.1,
            lines=["victoria", "northern"],
        )
        station2 = Station(
            id=uuid4(),
            tfl_id="DEF",
            name="Station B",
            latitude=51.5,
            longitude=-0.1,
            lines=["piccadilly"],
        )

        result = filter_stations_by_line_tfl_id([station1, station2], "victoria")

        assert len(result) == 1
        assert result[0].tfl_id == "ABC"

    def test_multiple_matches(self):
        """Should return all stations serving the line."""
        station1 = Station(
            id=uuid4(),
            tfl_id="ABC",
            name="Station A",
            latitude=51.5,
            longitude=-0.1,
            lines=["victoria", "northern"],
        )
        station2 = Station(
            id=uuid4(),
            tfl_id="DEF",
            name="Station B",
            latitude=51.5,
            longitude=-0.1,
            lines=["victoria"],
        )
        station3 = Station(
            id=uuid4(),
            tfl_id="GHI",
            name="Station C",
            latitude=51.5,
            longitude=-0.1,
            lines=["piccadilly"],
        )

        result = filter_stations_by_line_tfl_id([station1, station2, station3], "victoria")

        assert len(result) == 2
        assert {s.tfl_id for s in result} == {"ABC", "DEF"}

    def test_no_matches(self):
        """Should return empty list when no stations serve the line."""
        station1 = Station(
            id=uuid4(),
            tfl_id="ABC",
            name="Station A",
            latitude=51.5,
            longitude=-0.1,
            lines=["piccadilly"],
        )
        station2 = Station(
            id=uuid4(),
            tfl_id="DEF",
            name="Station B",
            latitude=51.5,
            longitude=-0.1,
            lines=["northern"],
        )

        result = filter_stations_by_line_tfl_id([station1, station2], "victoria")

        assert result == []

    def test_empty_input_list(self):
        """Should return empty list when input is empty."""
        result = filter_stations_by_line_tfl_id([], "victoria")
        assert result == []

    def test_station_with_empty_lines(self):
        """Should handle stations with no lines."""
        station = Station(
            id=uuid4(),
            tfl_id="ABC",
            name="Station A",
            latitude=51.5,
            longitude=-0.1,
            lines=[],
        )

        result = filter_stations_by_line_tfl_id([station], "victoria")

        assert result == []


class TestValidateStationsExistForLine:
    """Tests for validate_stations_exist_for_line()."""

    def test_with_stations(self):
        """Should not raise when stations exist."""
        station = Station(
            id=uuid4(),
            tfl_id="ABC",
            name="Station A",
            latitude=51.5,
            longitude=-0.1,
            lines=["victoria"],
        )

        # Should not raise
        validate_stations_exist_for_line([station], "victoria")

    def test_with_multiple_stations(self):
        """Should not raise when multiple stations exist."""
        stations = [
            Station(
                id=uuid4(),
                tfl_id="ABC",
                name="Station A",
                latitude=51.5,
                longitude=-0.1,
                lines=["victoria"],
            ),
            Station(
                id=uuid4(),
                tfl_id="DEF",
                name="Station B",
                latitude=51.5,
                longitude=-0.1,
                lines=["victoria"],
            ),
        ]

        # Should not raise
        validate_stations_exist_for_line(stations, "victoria")

    def test_with_empty_list(self):
        """Should raise NoStationsForLineError when no stations provided."""
        with pytest.raises(NoStationsForLineError) as exc_info:
            validate_stations_exist_for_line([], "victoria")

        assert exc_info.value.line_tfl_id == "victoria"
        assert "victoria" in str(exc_info.value)

    def test_error_message_format(self):
        """Error message should include line ID."""
        with pytest.raises(NoStationsForLineError) as exc_info:
            validate_stations_exist_for_line([], "northern")

        error_message = str(exc_info.value)
        assert "northern" in error_message
        assert "No stations found" in error_message


class TestDatabaseNotInitializedError:
    """Tests for DatabaseNotInitializedError exception."""

    def test_error_message(self):
        """Error should have helpful message about initializing database."""
        error = DatabaseNotInitializedError()

        error_message = str(error)
        assert "TfL data not initialized" in error_message
        assert "/admin/tfl/build-graph" in error_message

    def test_is_station_fetch_error(self):
        """Should be instance of base StationFetchError."""
        error = DatabaseNotInitializedError()
        assert isinstance(error, StationFetchError)


class TestLineNotFoundError:
    """Tests for LineNotFoundError exception."""

    def test_error_message(self):
        """Error should include line ID in message."""
        error = LineNotFoundError("victoria")

        assert error.line_tfl_id == "victoria"
        assert "victoria" in str(error)
        assert "not found" in str(error)

    def test_different_line_ids(self):
        """Should work with different line IDs."""
        victoria_error = LineNotFoundError("victoria")
        northern_error = LineNotFoundError("northern")

        assert victoria_error.line_tfl_id == "victoria"
        assert northern_error.line_tfl_id == "northern"
        assert "victoria" in str(victoria_error)
        assert "northern" in str(northern_error)

    def test_is_station_fetch_error(self):
        """Should be instance of base StationFetchError."""
        error = LineNotFoundError("victoria")
        assert isinstance(error, StationFetchError)


class TestNoStationsForLineError:
    """Tests for NoStationsForLineError exception."""

    def test_error_message(self):
        """Error should include line ID in message."""
        error = NoStationsForLineError("victoria")

        assert error.line_tfl_id == "victoria"
        assert "victoria" in str(error)
        assert "No stations found" in str(error)

    def test_different_line_ids(self):
        """Should work with different line IDs."""
        victoria_error = NoStationsForLineError("victoria")
        northern_error = NoStationsForLineError("northern")

        assert victoria_error.line_tfl_id == "victoria"
        assert northern_error.line_tfl_id == "northern"

    def test_is_station_fetch_error(self):
        """Should be instance of base StationFetchError."""
        error = NoStationsForLineError("victoria")
        assert isinstance(error, StationFetchError)
