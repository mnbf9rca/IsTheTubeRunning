"""
Type definitions for test fixtures.

Provides type-safe structures for test data, improving IDE support and
maintaining clear contracts between fixtures and test functions.
"""

from dataclasses import dataclass

from app.models.tfl import Line, Station, StationConnection


@dataclass
class RailwayNetworkFixture:
    """
    Complete test railway network with all components.

    Provides attribute-style access to network entities with full IDE support.

    Attributes:
        stations: Dictionary mapping TfL station IDs to Station objects
        lines: Dictionary mapping TfL line IDs to Line objects
        hubs: Dictionary mapping hub codes to lists of child Station objects
        connections: List of all StationConnection records (bidirectional)
        stats: Dictionary with counts (stations_count, lines_count, hubs_count, connections_count)
    """

    stations: dict[str, Station]
    lines: dict[str, Line]
    hubs: dict[str, list[Station]]
    connections: list[StationConnection]
    stats: dict[str, int]
