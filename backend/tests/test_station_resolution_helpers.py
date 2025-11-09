"""
Unit tests for station resolution helper functions.

These are pure functions, so tests are simple and don't require database access.
"""

import pytest
from app.helpers.station_resolution import (
    NoMatchingStationsError,
    StationNotFoundError,
    StationResolutionError,
    filter_stations_by_line,
    get_canonical_station_id,
    select_station_from_candidates,
    should_canonicalize_to_hub,
)
from app.models.tfl import Station


class TestFilterStationsByLine:
    """Tests for filter_stations_by_line() pure function."""

    def test_filter_stations_by_line_single_match(self):
        """Should return only stations that serve the specified line."""
        station1 = Station(
            tfl_id="ABC",
            name="Station A",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria", "northern"],
        )
        station2 = Station(
            tfl_id="DEF",
            name="Station B",
            latitude=0.0,
            longitude=0.0,
            lines=["piccadilly"],
        )
        station3 = Station(
            tfl_id="GHI",
            name="Station C",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria", "circle"],
        )

        result = filter_stations_by_line([station1, station2, station3], "victoria")

        assert len(result) == 2
        assert station1 in result
        assert station3 in result
        assert station2 not in result

    def test_filter_stations_by_line_no_matches(self):
        """Should return empty list when no stations serve the line."""
        station1 = Station(
            tfl_id="ABC",
            name="Station A",
            latitude=0.0,
            longitude=0.0,
            lines=["northern"],
        )
        station2 = Station(
            tfl_id="DEF",
            name="Station B",
            latitude=0.0,
            longitude=0.0,
            lines=["piccadilly"],
        )

        result = filter_stations_by_line([station1, station2], "victoria")

        assert result == []

    def test_filter_stations_by_line_all_match(self):
        """Should return all stations if they all serve the line."""
        station1 = Station(
            tfl_id="ABC",
            name="Station A",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria"],
        )
        station2 = Station(
            tfl_id="DEF",
            name="Station B",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria", "northern"],
        )

        result = filter_stations_by_line([station1, station2], "victoria")

        assert len(result) == 2
        assert station1 in result
        assert station2 in result

    def test_filter_stations_by_line_empty_input(self):
        """Should return empty list for empty input."""
        result = filter_stations_by_line([], "victoria")
        assert result == []


class TestSelectStationFromCandidates:
    """Tests for select_station_from_candidates() pure function."""

    def test_select_station_from_candidates_single(self):
        """Should return the only station when given one candidate."""
        station = Station(
            tfl_id="ABC",
            name="Station A",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria"],
        )

        result = select_station_from_candidates([station])

        assert result == station

    def test_select_station_from_candidates_multiple_alphabetical(self):
        """Should return first station alphabetically by tfl_id."""
        station1 = Station(
            tfl_id="940GZZLUSVS",  # Tube station (940...)
            name="Seven Sisters Tube",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria"],
        )
        station2 = Station(
            tfl_id="910GSEVNSIS",  # Rail station (910...)
            name="Seven Sisters Rail",
            latitude=0.0,
            longitude=0.0,
            lines=["overground"],
        )

        result = select_station_from_candidates([station1, station2])

        # "910..." < "940..." alphabetically
        assert result == station2

    def test_select_station_from_candidates_deterministic(self):
        """Should always return the same result for the same input (deterministic)."""
        stations = [
            Station(tfl_id="C", name="C", latitude=0.0, longitude=0.0, lines=[]),
            Station(tfl_id="A", name="A", latitude=0.0, longitude=0.0, lines=[]),
            Station(tfl_id="B", name="B", latitude=0.0, longitude=0.0, lines=[]),
        ]

        result1 = select_station_from_candidates(stations)
        result2 = select_station_from_candidates(stations)
        result3 = select_station_from_candidates(stations)

        assert result1 == result2 == result3
        assert result1.tfl_id == "A"  # First alphabetically

    def test_select_station_from_candidates_empty_raises_error(self):
        """Should raise ValueError for empty list."""
        with pytest.raises(ValueError, match="Cannot select from empty station list"):
            select_station_from_candidates([])


class TestShouldCanonicalizeToHub:
    """Tests for should_canonicalize_to_hub() pure function."""

    def test_should_canonicalize_to_hub_with_hub_code(self):
        """Should return True when station has hub_naptan_code."""
        station = Station(
            tfl_id="940GZZLUSVS",
            name="Seven Sisters",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria"],
            hub_naptan_code="HUBSVS",
        )

        assert should_canonicalize_to_hub(station) is True

    def test_should_canonicalize_to_hub_without_hub_code(self):
        """Should return False when station has no hub_naptan_code."""
        station = Station(
            tfl_id="940GZZLUOXC",
            name="Oxford Circus",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria", "central"],
            hub_naptan_code=None,
        )

        assert should_canonicalize_to_hub(station) is False


class TestGetCanonicalStationId:
    """Tests for get_canonical_station_id() pure function."""

    def test_get_canonical_station_id_with_hub_code(self):
        """Should return hub code when available."""
        station = Station(
            tfl_id="940GZZLUSVS",
            name="Seven Sisters",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria"],
            hub_naptan_code="HUBSVS",
        )

        result = get_canonical_station_id(station)

        assert result == "HUBSVS"

    def test_get_canonical_station_id_without_hub_code(self):
        """Should return tfl_id when no hub code."""
        station = Station(
            tfl_id="940GZZLUOXC",
            name="Oxford Circus",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria", "central"],
            hub_naptan_code=None,
        )

        result = get_canonical_station_id(station)

        assert result == "940GZZLUOXC"

    def test_get_canonical_station_id_deterministic(self):
        """Should always return the same result (pure function)."""
        station = Station(
            tfl_id="940GZZLUSVS",
            name="Seven Sisters",
            latitude=0.0,
            longitude=0.0,
            lines=["victoria"],
            hub_naptan_code="HUBSVS",
        )

        result1 = get_canonical_station_id(station)
        result2 = get_canonical_station_id(station)

        assert result1 == result2 == "HUBSVS"


class TestStationResolutionExceptions:
    """Tests for custom exception classes."""

    def test_station_not_found_error(self):
        """Should create StationNotFoundError with correct message."""
        error = StationNotFoundError("HUBXYZ")

        assert "HUBXYZ" in str(error)
        assert "not found" in str(error)
        assert error.tfl_id_or_hub == "HUBXYZ"

    def test_no_matching_stations_error(self):
        """Should create NoMatchingStationsError with correct message."""
        error = NoMatchingStationsError("HUBSVS", "victoria", ["910GSEVNSIS", "940GZZLUSVS"])

        assert "HUBSVS" in str(error)
        assert "victoria" in str(error)
        assert "910GSEVNSIS" in str(error)
        assert "940GZZLUSVS" in str(error)
        assert error.hub_code == "HUBSVS"
        assert error.line_tfl_id == "victoria"
        assert error.available_stations == ["910GSEVNSIS", "940GZZLUSVS"]

    def test_station_resolution_error_base_class(self):
        """Should be able to catch all resolution errors with base class."""
        hub_code = "HUBSVS"
        line_id = "victoria"
        station_id = "ABC"
        try:
            raise NoMatchingStationsError(hub_code, line_id, [])
        except StationResolutionError:
            pass  # Should catch

        try:
            raise StationNotFoundError(station_id)
        except StationResolutionError:
            pass  # Should catch
