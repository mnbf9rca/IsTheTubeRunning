"""
Station fetching helpers for validation and filtering logic.

These pure functions enable testable, functional-style station fetching validation
without requiring database access. They are used by TfLService.fetch_stations()
to reduce complexity while maintaining security validation from Issue #38.

Issue #38: Prevent API quota exhaustion with database validation
"""

from __future__ import annotations

from app.models.tfl import Station


def build_station_cache_key(line_tfl_id: str | None) -> str:
    """
    Build Redis cache key for station queries.

    Pure function for consistent cache key generation.

    Args:
        line_tfl_id: Optional line ID for filtering

    Returns:
        Redis cache key string

    Examples:
        >>> build_station_cache_key("victoria")
        'stations:line:victoria'

        >>> build_station_cache_key(None)
        'stations:all'
    """
    return f"stations:line:{line_tfl_id}" if line_tfl_id else "stations:all"


def is_database_initialized(station_count: int) -> bool:
    """
    Check if TfL database has been initialized.

    Pure function - determines if graph building has occurred by checking
    if any stations exist in the database.

    Args:
        station_count: Total number of stations in database

    Returns:
        True if database initialized (count > 0), False otherwise

    Examples:
        >>> is_database_initialized(100)
        True

        >>> is_database_initialized(0)
        False
    """
    return station_count > 0


def filter_stations_by_line_tfl_id(
    stations: list[Station],
    line_tfl_id: str,
) -> list[Station]:
    """
    Filter stations that serve the specified line.

    Pure function for filtering stations by line TfL ID. Needed because
    Station.lines is JSON type (not JSONB), so containment operators don't
    work well in SQL. This allows filtering in Python after fetching.

    Defensive: Handles cases where Station.lines might not be a list (e.g.,
    legacy data, manual DB manipulation, or edge cases during migrations).

    Args:
        stations: List of Station objects to filter
        line_tfl_id: TfL line ID to filter by (e.g., 'victoria', 'northern')

    Returns:
        List of stations that have line_tfl_id in their lines array

    Examples:
        >>> station1 = Station(tfl_id="ABC", lines=["victoria", "northern"])
        >>> station2 = Station(tfl_id="DEF", lines=["piccadilly"])
        >>> filter_stations_by_line_tfl_id([station1, station2], "victoria")
        [station1]

        >>> filter_stations_by_line_tfl_id([station2], "victoria")
        []
    """
    return [s for s in stations if isinstance(s.lines, list) and line_tfl_id in s.lines]


def validate_stations_exist_for_line(
    stations: list[Station],
    line_tfl_id: str,
) -> None:
    """
    Validate that at least one station exists for line.

    Pure validation function that raises domain exception if validation fails.
    This is a security validation to ensure users only query valid line/station
    combinations from the database.

    Args:
        stations: Filtered list of stations
        line_tfl_id: Line being validated

    Raises:
        NoStationsForLineError: If stations list is empty

    Examples:
        >>> validate_stations_exist_for_line([], "victoria")
        Traceback (most recent call last):
            ...
        NoStationsForLineError: No stations found for line 'victoria'.

        >>> station = Station(tfl_id="ABC", lines=["victoria"])
        >>> validate_stations_exist_for_line([station], "victoria")
        # No exception raised
    """
    if not stations:
        raise NoStationsForLineError(line_tfl_id)


# Custom domain exceptions


class StationFetchError(Exception):
    """Base exception for station fetching errors."""

    pass


class DatabaseNotInitializedError(StationFetchError):
    """
    Raised when TfL database hasn't been initialized.

    This indicates that the /admin/tfl/build-graph endpoint needs to be run
    to populate the station and line data from the TfL API.
    """

    def __init__(self) -> None:
        super().__init__(
            "TfL data not initialized. Please contact administrator to run /admin/tfl/build-graph endpoint."
        )


class LineNotFoundError(StationFetchError):
    """
    Raised when requested line doesn't exist in database.

    This is a security validation to prevent users from querying arbitrary
    line IDs that might trigger TfL API calls.
    """

    def __init__(self, line_tfl_id: str) -> None:
        self.line_tfl_id = line_tfl_id
        super().__init__(f"Line '{line_tfl_id}' not found.")


class NoStationsForLineError(StationFetchError):
    """
    Raised when line exists but has no stations.

    This should be rare in practice, but provides better error messaging
    than returning an empty list.
    """

    def __init__(self, line_tfl_id: str) -> None:
        self.line_tfl_id = line_tfl_id
        super().__init__(f"No stations found for line '{line_tfl_id}'.")
