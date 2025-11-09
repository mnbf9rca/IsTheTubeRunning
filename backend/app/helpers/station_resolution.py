"""
Station resolution helpers for hub NaPTAN code support.

These pure functions enable testable, functional-style station resolution logic
without requiring database access. They are used by TfLService.resolve_station_or_hub()
and response serialization for canonical hub code representation.

Issue #65: Support hub NaPTAN codes as station_tfl_id in route validation
"""

from __future__ import annotations

from app.models.tfl import Station


def filter_stations_by_line(stations: list[Station], line_tfl_id: str) -> list[Station]:
    """
    Filter stations that serve the specified line.

    Pure function for filtering stations by line context. Used when resolving
    hub codes with line_tfl_id context.

    Args:
        stations: List of Station objects to filter
        line_tfl_id: TfL line ID to filter by (e.g., 'victoria', 'northern')

    Returns:
        List of stations that have line_tfl_id in their lines array

    Examples:
        >>> station1 = Station(tfl_id="ABC", lines=["victoria", "northern"])
        >>> station2 = Station(tfl_id="DEF", lines=["piccadilly"])
        >>> filter_stations_by_line([station1, station2], "victoria")
        [station1]
    """
    return [s for s in stations if line_tfl_id in s.lines]


def select_station_from_candidates(stations: list[Station]) -> Station:
    """
    Select a single station from multiple candidates.

    When multiple stations match criteria (e.g., multiple stations in a hub serve
    the same line), this function provides deterministic selection by choosing the
    first station alphabetically by tfl_id.

    Pure function - no side effects, deterministic output.

    Args:
        stations: Non-empty list of Station objects

    Returns:
        The first station when sorted alphabetically by tfl_id

    Raises:
        ValueError: If stations list is empty

    Examples:
        >>> s1 = Station(tfl_id="940GZZLUSVS", name="Seven Sisters Tube")
        >>> s2 = Station(tfl_id="910GSEVNSIS", name="Seven Sisters Rail")
        >>> select_station_from_candidates([s1, s2])
        <Station(tfl_id='910GSEVNSIS', ...)>  # "910..." < "940..." alphabetically
    """
    if not stations:
        msg = "Cannot select from empty station list"
        raise ValueError(msg)

    return sorted(stations, key=lambda s: s.tfl_id)[0]


def should_canonicalize_to_hub(station: Station) -> bool:
    """
    Determine if a station should be represented by its hub code in API responses.

    Pure function for canonicalization logic. Returns True if the station has a
    hub_naptan_code, indicating it should be returned as the hub code rather than
    the specific station tfl_id.

    This implements the "normalize on read" pattern where hub-capable stations
    are always returned with their canonical hub representation.

    Args:
        station: Station object to check

    Returns:
        True if station has hub_naptan_code (should use hub code)
        False if station has no hub (should use station tfl_id)

    Examples:
        >>> station_with_hub = Station(tfl_id="940GZZLUSVS", hub_naptan_code="HUBSVS")
        >>> should_canonicalize_to_hub(station_with_hub)
        True

        >>> standalone_station = Station(tfl_id="940GZZLUOXC", hub_naptan_code=None)
        >>> should_canonicalize_to_hub(standalone_station)
        False
    """
    return station.hub_naptan_code is not None


def get_canonical_station_id(station: Station) -> str:
    """
    Get the canonical station ID for API responses.

    Returns hub_naptan_code if available (canonical representation), otherwise
    returns the station's tfl_id. This implements the "normalize on read" pattern.

    Pure function - always returns the same output for the same input.

    Args:
        station: Station object

    Returns:
        Hub NaPTAN code if available, otherwise station tfl_id

    Examples:
        >>> station_with_hub = Station(
        ...     tfl_id="940GZZLUSVS",
        ...     hub_naptan_code="HUBSVS"
        ... )
        >>> get_canonical_station_id(station_with_hub)
        'HUBSVS'

        >>> standalone_station = Station(
        ...     tfl_id="940GZZLUOXC",
        ...     hub_naptan_code=None
        ... )
        >>> get_canonical_station_id(standalone_station)
        '940GZZLUOXC'
    """
    return station.hub_naptan_code or station.tfl_id


class StationResolutionError(Exception):
    """Base exception for station resolution errors."""

    pass


class NoMatchingStationsError(StationResolutionError):
    """Raised when no stations in hub serve the specified line."""

    def __init__(self, hub_code: str, line_tfl_id: str, available_stations: list[str]) -> None:
        self.hub_code = hub_code
        self.line_tfl_id = line_tfl_id
        self.available_stations = available_stations
        super().__init__(
            f"Hub '{hub_code}' found, but no station serves line '{line_tfl_id}'. "
            f"Available stations: {', '.join(available_stations)}"
        )


class StationNotFoundError(StationResolutionError):
    """Raised when station or hub code is not found."""

    def __init__(self, tfl_id_or_hub: str) -> None:
        self.tfl_id_or_hub = tfl_id_or_hub
        super().__init__(
            f"Station or hub with ID '{tfl_id_or_hub}' not found. "
            "Please ensure TfL data is imported via /admin/tfl/build-graph endpoint."
        )
