"""
Helper functions for accessing test railway network entities.

Provides convenient access methods for retrieving stations, lines, hubs, and
connections from the test_railway_network fixture.
"""

from app.models.tfl import Line, Station, StationConnection

from tests.conftest import RailwayNetworkFixture


def get_station_by_tfl_id(network: RailwayNetworkFixture, tfl_id: str) -> Station:
    """
    Get a station from the network by its TfL ID.

    Args:
        network: Test railway network dictionary from fixture
        tfl_id: TfL ID of the station (e.g., "parallel-north", "fork-junction")

    Returns:
        Station object

    Raises:
        KeyError: If station with given tfl_id doesn't exist in network
    """
    return network["stations"][tfl_id]


def get_line_by_tfl_id(network: RailwayNetworkFixture, tfl_id: str) -> Line:
    """
    Get a line from the network by its TfL ID.

    Args:
        network: Test railway network dictionary from fixture
        tfl_id: TfL ID of the line (e.g., "forkedline", "parallelline")

    Returns:
        Line object

    Raises:
        KeyError: If line with given tfl_id doesn't exist in network
    """
    return network["lines"][tfl_id]


def get_hub_stations(network: RailwayNetworkFixture, hub_code: str) -> list[Station]:
    """
    Get all child stations of a hub.

    Args:
        network: Test railway network dictionary from fixture
        hub_code: Hub NaPTAN code (e.g., "HUBNORTH", "HUBCENTRAL")

    Returns:
        List of Station objects belonging to the hub

    Raises:
        KeyError: If hub with given code doesn't exist in network
    """
    return network["hubs"][hub_code]


def get_connections_for_line(network: RailwayNetworkFixture, line_tfl_id: str) -> list[StationConnection]:
    """
    Get all StationConnection records for a specific line.

    Args:
        network: Test railway network dictionary from fixture
        line_tfl_id: TfL ID of the line

    Returns:
        List of StationConnection objects for the line

    Raises:
        KeyError: If line with given tfl_id doesn't exist in network
    """
    line = get_line_by_tfl_id(network, line_tfl_id)
    return [conn for conn in network["connections"] if conn.line_id == line.id]


def get_stations_on_line(network: RailwayNetworkFixture, line_tfl_id: str) -> list[Station]:
    """
    Get all stations served by a line.

    Extracts unique station TfL IDs from the line's route sequences
    and returns the corresponding Station objects.

    Args:
        network: Test railway network dictionary from fixture
        line_tfl_id: TfL ID of the line

    Returns:
        List of unique Station objects served by the line
    """
    line = get_line_by_tfl_id(network, line_tfl_id)

    # Extract unique station IDs from all routes
    station_ids = set()
    for route in line.routes["routes"]:
        station_ids.update(route["stations"])

    # Return corresponding Station objects
    return [network["stations"][tfl_id] for tfl_id in station_ids]
