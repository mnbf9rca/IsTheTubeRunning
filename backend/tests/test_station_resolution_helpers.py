"""
Unit tests for station resolution helper functions.

These are pure functions, so tests are simple and don't require database access.
Uses abstract test data via create_test_station() factory for clarity and maintainability.
"""

from datetime import UTC, datetime

import pytest
from app.helpers.station_resolution import (
    NoMatchingStationsError,
    StationNotFoundError,
    StationResolutionError,
    aggregate_station_lines,
    create_hub_representative,
    filter_stations_by_line,
    get_canonical_station_id,
    get_latest_update_time,
    group_stations_by_hub,
    select_station_from_candidates,
    should_canonicalize_to_hub,
)

from tests.conftest import create_test_station


class TestFilterStationsByLine:
    """Tests for filter_stations_by_line() pure function."""

    def test_filter_stations_by_line_single_match(self):
        """Should return only stations that serve the specified line."""
        station1 = create_test_station("STATION_A", "Alpha Station", ["line1", "line2"])
        station2 = create_test_station("STATION_B", "Beta Station", ["line3"])
        station3 = create_test_station("STATION_C", "Charlie Station", ["line1", "line4"])

        result = filter_stations_by_line([station1, station2, station3], "line1")

        assert len(result) == 2
        assert station1 in result
        assert station3 in result
        assert station2 not in result

    def test_filter_stations_by_line_no_matches(self):
        """Should return empty list when no stations serve the line."""
        station1 = create_test_station("STATION_A", "Alpha Station", ["line2"])
        station2 = create_test_station("STATION_B", "Beta Station", ["line3"])

        result = filter_stations_by_line([station1, station2], "line1")

        assert result == []

    def test_filter_stations_by_line_all_match(self):
        """Should return all stations if they all serve the line."""
        station1 = create_test_station("STATION_A", "Alpha Station", ["line1"])
        station2 = create_test_station("STATION_B", "Beta Station", ["line1", "line2"])

        result = filter_stations_by_line([station1, station2], "line1")

        assert len(result) == 2
        assert station1 in result
        assert station2 in result

    def test_filter_stations_by_line_empty_input(self):
        """Should return empty list for empty input."""
        result = filter_stations_by_line([], "line1")
        assert result == []


class TestSelectStationFromCandidates:
    """Tests for select_station_from_candidates() pure function."""

    def test_select_station_from_candidates_single(self):
        """Should return the only station when given one candidate."""
        station = create_test_station("STATION_A", "Alpha Station", ["line1"])

        result = select_station_from_candidates([station])

        assert result == station

    def test_select_station_from_candidates_multiple_alphabetical(self):
        """Should return first station alphabetically by tfl_id."""
        # Use IDs where alphabetical order is clear: B < C
        station1 = create_test_station("STATION_C", "Charlie Station", ["line1"])
        station2 = create_test_station("STATION_B", "Beta Station", ["line2"])

        result = select_station_from_candidates([station1, station2])

        # "STATION_B" < "STATION_C" alphabetically
        assert result == station2

    def test_select_station_from_candidates_deterministic(self):
        """Should always return the same result for the same input (deterministic)."""
        stations = [
            create_test_station("C", "C", []),
            create_test_station("A", "A", []),
            create_test_station("B", "B", []),
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
        station = create_test_station(
            "STATION_A", "Alpha Station", ["line1"], hub_naptan_code="HUB1", hub_common_name="Hub Alpha"
        )

        assert should_canonicalize_to_hub(station) is True

    def test_should_canonicalize_to_hub_without_hub_code(self):
        """Should return False when station has no hub_naptan_code."""
        station = create_test_station("STATION_B", "Beta Station", ["line1", "line2"])

        assert should_canonicalize_to_hub(station) is False


class TestGetCanonicalStationId:
    """Tests for get_canonical_station_id() pure function."""

    def test_get_canonical_station_id_with_hub_code(self):
        """Should return hub code when available."""
        station = create_test_station(
            "STATION_A", "Alpha Station", ["line1"], hub_naptan_code="HUB1", hub_common_name="Hub Alpha"
        )

        result = get_canonical_station_id(station)

        assert result == "HUB1"

    def test_get_canonical_station_id_without_hub_code(self):
        """Should return tfl_id when no hub code."""
        station = create_test_station("STATION_B", "Beta Station", ["line1", "line2"])

        result = get_canonical_station_id(station)

        assert result == "STATION_B"

    def test_get_canonical_station_id_deterministic(self):
        """Should always return the same result (pure function)."""
        station = create_test_station(
            "STATION_A", "Alpha Station", ["line1"], hub_naptan_code="HUB1", hub_common_name="Hub Alpha"
        )

        result1 = get_canonical_station_id(station)
        result2 = get_canonical_station_id(station)

        assert result1 == result2 == "HUB1"


class TestStationResolutionExceptions:
    """Tests for custom exception classes."""

    def test_station_not_found_error(self):
        """Should create StationNotFoundError with correct message."""
        error = StationNotFoundError("STATION_XYZ")

        assert "STATION_XYZ" in str(error)
        assert "not found" in str(error)
        assert error.tfl_id_or_hub == "STATION_XYZ"

    def test_no_matching_stations_error(self):
        """Should create NoMatchingStationsError with correct message."""
        error = NoMatchingStationsError("HUB1", "line1", ["STATION_A", "STATION_B"])

        assert "HUB1" in str(error)
        assert "line1" in str(error)
        assert "STATION_A" in str(error)
        assert "STATION_B" in str(error)
        assert error.hub_code == "HUB1"
        assert error.line_tfl_id == "line1"
        assert error.available_stations == ["STATION_A", "STATION_B"]

    def test_station_resolution_error_base_class(self):
        """Should be able to catch all resolution errors with base class."""
        hub_code = "HUB1"
        line_id = "line1"
        station_id = "STATION_A"
        try:
            raise NoMatchingStationsError(hub_code, line_id, [])
        except StationResolutionError:
            pass  # Should catch

        try:
            raise StationNotFoundError(station_id)
        except StationResolutionError:
            pass  # Should catch


# Tests for deduplication helpers (Issue #67)


class TestGroupStationsByHub:
    """Tests for group_stations_by_hub() pure function."""

    def test_group_stations_by_hub_with_mixed_stations(self):
        """Should correctly partition hub and standalone stations."""
        hub_station1 = create_test_station(
            "HUB1_CHILD_A", "Hub 1 Alpha", ["line1"], hub_naptan_code="HUB1", hub_common_name="Hub Alpha"
        )
        hub_station2 = create_test_station(
            "HUB1_CHILD_B", "Hub 1 Beta", ["line2"], hub_naptan_code="HUB1", hub_common_name="Hub Alpha"
        )
        standalone = create_test_station("STATION_C", "Charlie Station", ["line3"])

        hub_groups, standalone_stations = group_stations_by_hub([hub_station1, hub_station2, standalone])

        assert len(hub_groups) == 1
        assert "HUB1" in hub_groups
        assert len(hub_groups["HUB1"]) == 2
        assert hub_station1 in hub_groups["HUB1"]
        assert hub_station2 in hub_groups["HUB1"]
        assert len(standalone_stations) == 1
        assert standalone in standalone_stations

    def test_group_stations_by_hub_all_standalone(self):
        """Should return empty hub_groups when all stations are standalone."""
        station1 = create_test_station("STATION_A", "Alpha Station", ["line1"])
        station2 = create_test_station("STATION_B", "Beta Station", ["line2"])

        hub_groups, standalone_stations = group_stations_by_hub([station1, station2])

        assert hub_groups == {}
        assert len(standalone_stations) == 2
        assert station1 in standalone_stations
        assert station2 in standalone_stations

    def test_group_stations_by_hub_all_hub_stations(self):
        """Should return empty standalone_stations when all stations are in hubs."""
        hub_station1 = create_test_station(
            "HUB1_CHILD_A", "Hub 1 Alpha", ["line1"], hub_naptan_code="HUB1", hub_common_name="Hub Alpha"
        )
        hub_station2 = create_test_station(
            "HUB1_CHILD_B", "Hub 1 Beta", ["line2"], hub_naptan_code="HUB1", hub_common_name="Hub Alpha"
        )

        hub_groups, standalone_stations = group_stations_by_hub([hub_station1, hub_station2])

        assert len(hub_groups) == 1
        assert "HUB1" in hub_groups
        assert len(hub_groups["HUB1"]) == 2
        assert standalone_stations == []

    def test_group_stations_by_hub_multiple_hubs(self):
        """Should correctly group stations into multiple separate hubs."""
        hub1_station1 = create_test_station("A1", "Hub1 A", ["line1"], hub_naptan_code="HUB1")
        hub1_station2 = create_test_station("A2", "Hub1 B", ["line2"], hub_naptan_code="HUB1")
        hub2_station1 = create_test_station("B1", "Hub2 A", ["line3"], hub_naptan_code="HUB2")

        hub_groups, standalone_stations = group_stations_by_hub([hub1_station1, hub1_station2, hub2_station1])

        assert len(hub_groups) == 2
        assert "HUB1" in hub_groups
        assert "HUB2" in hub_groups
        assert len(hub_groups["HUB1"]) == 2
        assert len(hub_groups["HUB2"]) == 1
        assert standalone_stations == []

    def test_group_stations_by_hub_empty_list(self):
        """Should return empty groups and stations for empty input."""
        hub_groups, standalone_stations = group_stations_by_hub([])

        assert hub_groups == {}
        assert standalone_stations == []


class TestAggregateStationLines:
    """Tests for aggregate_station_lines() pure function."""

    def test_aggregate_station_lines_multiple_stations(self):
        """Should aggregate and deduplicate lines from multiple stations."""
        station1 = create_test_station("A", "Station A", ["line1", "line2"])
        station2 = create_test_station("B", "Station B", ["line1", "line3"])

        result = aggregate_station_lines([station1, station2])

        assert result == ["line1", "line2", "line3"]  # Sorted and deduplicated

    def test_aggregate_station_lines_no_duplicates(self):
        """Should return sorted unique lines when no duplicates exist."""
        station1 = create_test_station("A", "Station A", ["line2"])
        station2 = create_test_station("B", "Station B", ["line3"])

        result = aggregate_station_lines([station1, station2])

        assert result == ["line2", "line3"]

    def test_aggregate_station_lines_all_same(self):
        """Should deduplicate when all stations serve same lines."""
        station1 = create_test_station("A", "Station A", ["line1"])
        station2 = create_test_station("B", "Station B", ["line1"])

        result = aggregate_station_lines([station1, station2])

        assert result == ["line1"]

    def test_aggregate_station_lines_single_station(self):
        """Should return station's lines when only one station provided."""
        station = create_test_station("A", "Station A", ["line1", "line2"])

        result = aggregate_station_lines([station])

        assert result == ["line1", "line2"]  # Sorted

    def test_aggregate_station_lines_empty_list(self):
        """Should return empty list for empty input."""
        result = aggregate_station_lines([])

        assert result == []


class TestGetLatestUpdateTime:
    """Tests for get_latest_update_time() pure function."""

    def test_get_latest_update_time_multiple_stations(self):
        """Should return most recent timestamp from all stations."""
        station1 = create_test_station(
            "STATION_A", "Alpha Station", ["line1"], last_updated=datetime(2025, 1, 1, tzinfo=UTC)
        )
        station2 = create_test_station(
            "STATION_B", "Beta Station", ["line2"], last_updated=datetime(2025, 1, 15, tzinfo=UTC)
        )
        station3 = create_test_station(
            "STATION_C", "Charlie Station", ["line3"], last_updated=datetime(2025, 1, 10, tzinfo=UTC)
        )

        result = get_latest_update_time([station1, station2, station3])

        assert result == datetime(2025, 1, 15, tzinfo=UTC)

    def test_get_latest_update_time_single_station(self):
        """Should return timestamp when only one station provided."""
        station = create_test_station(
            "STATION_A", "Alpha Station", ["line1"], last_updated=datetime(2025, 1, 1, tzinfo=UTC)
        )

        result = get_latest_update_time([station])

        assert result == datetime(2025, 1, 1, tzinfo=UTC)

    def test_get_latest_update_time_all_same(self):
        """Should handle all stations having same timestamp."""
        timestamp = datetime(2025, 1, 1, tzinfo=UTC)
        station1 = create_test_station("A", "Station A", ["line1"], last_updated=timestamp)
        station2 = create_test_station("B", "Station B", ["line2"], last_updated=timestamp)

        result = get_latest_update_time([station1, station2])

        assert result == timestamp

    def test_get_latest_update_time_empty_list(self):
        """Should raise ValueError for empty list."""
        with pytest.raises(ValueError, match="Cannot get latest update time from empty station list"):
            get_latest_update_time([])


class TestCreateHubRepresentative:
    """Tests for create_hub_representative() pure function."""

    def test_create_hub_representative_basic(self):
        """Should create representative with aggregated data from hub children."""
        child1 = create_test_station(
            "HUB1_CHILD_A",
            "Hub 1 Alpha",
            ["line2"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code="HUB1",
            hub_common_name="Hub Alpha",
        )
        child2 = create_test_station(
            "HUB1_CHILD_B",
            "Hub 1 Beta",
            ["line1"],
            last_updated=datetime(2025, 1, 15, tzinfo=UTC),
            hub_naptan_code="HUB1",
            hub_common_name="Hub Alpha",
        )

        representative = create_hub_representative([child1, child2])

        assert representative.tfl_id == "HUB1"  # Uses hub code
        assert representative.name == "Hub Alpha"  # Uses hub_common_name
        assert representative.lines == ["line1", "line2"]  # Aggregated and sorted
        assert representative.last_updated == datetime(2025, 1, 15, tzinfo=UTC)  # Most recent
        assert representative.hub_naptan_code == "HUB1"
        assert representative.hub_common_name == "Hub Alpha"

    def test_create_hub_representative_single_child(self):
        """Should create representative even with single child."""
        station = create_test_station(
            "HUB1_CHILD_A",
            "Hub 1 Alpha",
            ["line1"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code="HUB1",
            hub_common_name="Hub Alpha",
        )

        representative = create_hub_representative([station])

        assert representative.tfl_id == "HUB1"
        assert representative.name == "Hub Alpha"
        assert representative.lines == ["line1"]

    def test_create_hub_representative_without_common_name(self):
        """Should fallback to station name when hub_common_name is None."""
        station = create_test_station(
            "HUB1_CHILD_A",
            "Alpha Station",
            ["line1"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code="HUB1",
            hub_common_name=None,
        )

        representative = create_hub_representative([station])

        assert representative.name == "Alpha Station"  # Falls back to station name

    def test_create_hub_representative_many_children(self):
        """Should handle many hub children correctly."""
        children = [
            create_test_station(
                f"HUB1_CHILD_{i}",
                f"Hub 1 Child {i}",
                [f"line{i}"],
                last_updated=datetime(2025, 1, i + 1, tzinfo=UTC),
                hub_naptan_code="HUB1",
                hub_common_name="Hub Alpha",
            )
            for i in range(5)
        ]

        representative = create_hub_representative(children)

        assert representative.tfl_id == "HUB1"
        assert representative.name == "Hub Alpha"
        assert len(representative.lines) == 5
        assert representative.lines == ["line0", "line1", "line2", "line3", "line4"]
        assert representative.last_updated == datetime(2025, 1, 5, tzinfo=UTC)  # Most recent

    def test_create_hub_representative_empty_list(self):
        """Should raise ValueError for empty list."""
        with pytest.raises(ValueError, match="Cannot create hub representative from empty list"):
            create_hub_representative([])

    def test_create_hub_representative_with_preferred_child(self):
        """Should use preferred_child as template for UUID and coordinates."""
        child1 = create_test_station(
            "HUB1_CHILD_A",
            "Hub 1 Alpha",
            ["line1"],
            latitude=51.0,
            longitude=-0.1,
            hub_naptan_code="HUB1",
            hub_common_name="Hub Alpha",
        )
        child2 = create_test_station(
            "HUB1_CHILD_B",
            "Hub 1 Beta",
            ["line2"],
            latitude=51.0,
            longitude=-0.1,
            hub_naptan_code="HUB1",
            hub_common_name="Hub Alpha",
        )

        # Use child2 as preferred
        representative = create_hub_representative([child1, child2], preferred_child=child2)

        assert representative.id == child2.id  # Uses preferred child's UUID
        assert representative.tfl_id == "HUB1"
        assert representative.lines == ["line1", "line2"]  # Still aggregates from all

    def test_create_hub_representative_preferred_child_not_in_list(self):
        """Should raise ValueError if preferred_child not in hub_children list."""
        child1 = create_test_station(
            "HUB1_CHILD_A", "Hub 1 Alpha", ["line1"], hub_naptan_code="HUB1", hub_common_name="Hub Alpha"
        )
        other_child = create_test_station(
            "HUB2_CHILD_A", "Hub 2 Alpha", ["line2"], hub_naptan_code="HUB2", hub_common_name="Hub Beta"
        )

        with pytest.raises(ValueError, match=r"preferred_child .* not found in hub_children"):
            create_hub_representative([child1], preferred_child=other_child)
