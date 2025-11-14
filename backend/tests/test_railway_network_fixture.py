"""
Integration tests for test_railway_network fixture.

Verifies that the session-scoped fixture builds correctly with all stations,
lines, hubs, and StationConnection graph as expected.
"""

import pytest

from tests.helpers.network_helpers import (
    get_connections_for_line,
    get_hub_stations,
    get_line_by_tfl_id,
    get_station_by_tfl_id,
    get_stations_on_line,
)
from tests.helpers.types import RailwayNetworkFixture


class TestRailwayNetworkFixture:
    """Tests for test_railway_network fixture structure and integrity."""

    def test_fixture_builds_successfully(self, test_railway_network: RailwayNetworkFixture):
        """Verify fixture builds without errors."""
        assert test_railway_network is not None
        assert test_railway_network.stations is not None
        assert test_railway_network.lines is not None
        assert test_railway_network.hubs is not None
        assert test_railway_network.connections is not None
        assert test_railway_network.stats is not None

    def test_network_has_expected_counts(self, test_railway_network: RailwayNetworkFixture):
        """Verify fixture contains expected number of entities."""
        stats = test_railway_network.stats

        # 43 stations (standardized test network)
        assert stats["stations_count"] == 43

        # 8 lines across 4 modes
        assert stats["lines_count"] == 8

        # 2 hubs (HUBNORTH, HUBCENTRAL)
        assert stats["hubs_count"] == 2

        # ~72 bidirectional connections from route sequences
        assert stats["connections_count"] > 50
        assert stats["connections_count"] < 150

    def test_network_has_all_expected_stations(self, test_railway_network: RailwayNetworkFixture):
        """Verify all expected stations exist in network."""
        stations = test_railway_network.stations

        # Check network stations (sample)
        assert "parallel-north" in stations
        assert "fork-junction" in stations
        assert "shared-station" in stations
        assert "hubnorth-overground" in stations
        assert "hubcentral-dlr" in stations

    def test_network_has_all_lines(self, test_railway_network: RailwayNetworkFixture):
        """Verify all 8 lines exist in network."""
        lines = test_railway_network.lines

        assert "forkedline" in lines
        assert "parallelline" in lines
        assert "asymmetricline" in lines
        assert "2stopline" in lines
        assert "sharedline-a" in lines
        assert "sharedline-b" in lines
        assert "sharedline-c" in lines
        assert "elizabethline" in lines

    def test_hub_north_structure(self, test_railway_network: RailwayNetworkFixture):
        """Verify HUB_NORTH has correct child stations."""
        hub_stations = test_railway_network.hubs["HUBNORTH"]

        # HUB_NORTH should have 4 children (tube, overground, elizabeth, bus)
        assert len(hub_stations) == 4

        # Get station IDs
        station_ids = {s.tfl_id for s in hub_stations}

        assert "parallel-north" in station_ids  # tube
        assert "hubnorth-overground" in station_ids  # overground
        assert "hubnorth-elizabeth" in station_ids  # elizabeth-line
        assert "hubnorth-bus" in station_ids  # bus

        # All should have same hub code and common name
        assert all(s.hub_naptan_code == "HUBNORTH" for s in hub_stations)
        assert all(s.hub_common_name == "North Interchange" for s in hub_stations)

    def test_hub_central_structure(self, test_railway_network: RailwayNetworkFixture):
        """Verify HUB_CENTRAL has correct child stations."""
        hub_stations = test_railway_network.hubs["HUBCENTRAL"]

        # HUB_CENTRAL should have 2 children (tube, dlr)
        assert len(hub_stations) == 2

        station_ids = {s.tfl_id for s in hub_stations}

        assert "fork-mid-1" in station_ids  # tube (forkedline)
        assert "hubcentral-dlr" in station_ids  # dlr (2stopline)

        assert all(s.hub_naptan_code == "HUBCENTRAL" for s in hub_stations)
        assert all(s.hub_common_name == "Central Hub" for s in hub_stations)

    def test_connections_are_bidirectional(self, test_railway_network: RailwayNetworkFixture):
        """Verify connections exist in both directions (sample check)."""
        connections = test_railway_network.connections

        # Get station IDs for testing
        parallel_north = test_railway_network.stations["parallel-north"]
        parallel_split = test_railway_network.stations["parallel-split"]
        parallelline = test_railway_network.lines["parallelline"]

        # Verify forward connection exists (parallel-north -> parallel-split)
        forward_exists = any(
            conn.from_station_id == parallel_north.id
            and conn.to_station_id == parallel_split.id
            and conn.line_id == parallelline.id
            for conn in connections
        )
        assert forward_exists, "Forward connection should exist"

        # Verify reverse connection exists (parallel-split -> parallel-north)
        reverse_exists = any(
            conn.from_station_id == parallel_split.id
            and conn.to_station_id == parallel_north.id
            and conn.line_id == parallelline.id
            for conn in connections
        )
        assert reverse_exists, "Reverse connection should exist"

    def test_shared_station_appears_on_multiple_lines(self, test_railway_network: RailwayNetworkFixture):
        """Verify shared-station serves 3 lines (sharedline-a, b, c)."""
        shared_station = test_railway_network.stations["shared-station"]

        # Check station.lines contains all 3 line IDs
        assert "sharedline-a" in shared_station.lines
        assert "sharedline-b" in shared_station.lines
        assert "sharedline-c" in shared_station.lines

        # Station should not be a hub
        assert shared_station.hub_naptan_code is None


class TestNetworkHelpers:
    """Tests for network helper functions."""

    def test_get_station_by_tfl_id(self, test_railway_network: RailwayNetworkFixture):
        """Test getting station by TfL ID."""
        station = get_station_by_tfl_id(test_railway_network, "parallel-north")

        assert station.tfl_id == "parallel-north"
        assert station.hub_naptan_code == "HUBNORTH"

    def test_get_line_by_tfl_id(self, test_railway_network: RailwayNetworkFixture):
        """Test getting line by TfL ID."""
        line = get_line_by_tfl_id(test_railway_network, "forkedline")

        assert line.tfl_id == "forkedline"
        assert line.mode == "tube"

    def test_get_hub_stations(self, test_railway_network: RailwayNetworkFixture):
        """Test getting hub child stations."""
        hub_stations = get_hub_stations(test_railway_network, "HUBNORTH")

        assert len(hub_stations) == 4
        assert all(s.hub_naptan_code == "HUBNORTH" for s in hub_stations)

    def test_get_connections_for_line(self, test_railway_network: RailwayNetworkFixture):
        """Test getting connections for a specific line."""
        connections = get_connections_for_line(test_railway_network, "2stopline")

        # 2stopline has only 2 stations, so 2 bidirectional connections (A→B, B→A)
        assert len(connections) == 2

        # Verify line_id matches
        line = get_line_by_tfl_id(test_railway_network, "2stopline")
        assert all(conn.line_id == line.id for conn in connections)

    def test_get_stations_on_line(self, test_railway_network: RailwayNetworkFixture):
        """Test getting all stations on a line."""
        stations = get_stations_on_line(test_railway_network, "2stopline")

        # 2stopline has exactly 2 stations
        assert len(stations) == 2

        station_ids = {s.tfl_id for s in stations}
        assert "twostop-west" in station_ids
        assert "twostop-east" in station_ids

    def test_helper_raises_on_invalid_id(self, test_railway_network: RailwayNetworkFixture):
        """Test helpers raise KeyError for invalid IDs."""
        with pytest.raises(KeyError):
            get_station_by_tfl_id(test_railway_network, "nonexistent-station")

        with pytest.raises(KeyError):
            get_line_by_tfl_id(test_railway_network, "nonexistent-line")

        with pytest.raises(KeyError):
            get_hub_stations(test_railway_network, "NONEXISTENT_HUB")
