"""
Station resolution helpers for hub NaPTAN code support.

These pure functions enable testable, functional-style station resolution logic
without requiring database access. They are used by TfLService.resolve_station_or_hub()
and response serialization for canonical hub code representation.

Issue #65: Support hub NaPTAN codes as station_tfl_id in route validation
Issue #67: Deduplication helpers for hub-grouped station responses
"""

from __future__ import annotations

from datetime import datetime

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


# Deduplication helpers (Issue #67)


def group_stations_by_hub(
    stations: list[Station],
) -> tuple[dict[str, list[Station]], list[Station]]:
    """
    Group stations into hub groups and standalone stations.

    Pure function that partitions a list of stations into:
    1. Hub groups: dict mapping hub_naptan_code to list of stations in that hub
    2. Standalone stations: list of stations without hub_naptan_code

    Used for deduplicating stations by hub in API responses.

    Args:
        stations: List of Station objects to group

    Returns:
        Tuple of (hub_groups, standalone_stations) where:
        - hub_groups: dict[hub_code, list[Station]] for all hub stations
        - standalone_stations: list[Station] for all non-hub stations

    Examples:
        >>> hub_station1 = Station(tfl_id="940GZZLUSVS", hub_naptan_code="HUBSVS")
        >>> hub_station2 = Station(tfl_id="910GSEVNSIS", hub_naptan_code="HUBSVS")
        >>> standalone = Station(tfl_id="940GZZLUOXC", hub_naptan_code=None)
        >>> hubs, standalone_list = group_stations_by_hub([hub_station1, hub_station2, standalone])
        >>> hubs["HUBSVS"]
        [hub_station1, hub_station2]
        >>> standalone_list
        [standalone]
    """
    hub_groups: dict[str, list[Station]] = {}
    standalone_stations: list[Station] = []

    for station in stations:
        if should_canonicalize_to_hub(station):
            hub_code = station.hub_naptan_code
            assert hub_code is not None  # Type narrowing - already checked by should_canonicalize_to_hub
            if hub_code not in hub_groups:
                hub_groups[hub_code] = []
            hub_groups[hub_code].append(station)
        else:
            standalone_stations.append(station)

    return hub_groups, standalone_stations


def aggregate_station_lines(stations: list[Station]) -> list[str]:
    """
    Aggregate unique lines from multiple stations.

    Pure function that collects all unique line IDs from a list of stations
    and returns them as a sorted list. Used when creating a hub representative
    station that aggregates lines from all child stations.

    Args:
        stations: List of Station objects to aggregate lines from

    Returns:
        Sorted list of unique line IDs from all stations

    Examples:
        >>> station1 = Station(tfl_id="ABC", lines=["victoria", "northern"])
        >>> station2 = Station(tfl_id="DEF", lines=["victoria", "piccadilly"])
        >>> aggregate_station_lines([station1, station2])
        ['northern', 'piccadilly', 'victoria']
    """
    all_lines = set()
    for station in stations:
        all_lines.update(station.lines)
    return sorted(all_lines)


def get_latest_update_time(stations: list[Station]) -> datetime:
    """
    Get the most recent update timestamp from a list of stations.

    Pure function that finds the maximum last_updated timestamp among
    a list of stations. Used when creating a hub representative station.

    Args:
        stations: Non-empty list of Station objects

    Returns:
        The most recent last_updated datetime from all stations

    Raises:
        ValueError: If stations list is empty

    Examples:
        >>> from datetime import datetime
        >>> station1 = Station(tfl_id="ABC", last_updated=datetime(2025, 1, 1))
        >>> station2 = Station(tfl_id="DEF", last_updated=datetime(2025, 1, 15))
        >>> get_latest_update_time([station1, station2])
        datetime(2025, 1, 15, 0, 0)
    """
    if not stations:
        msg = "Cannot get latest update time from empty station list"
        raise ValueError(msg)

    return max(station.last_updated for station in stations)


def create_hub_representative(hub_children: list[Station], preferred_child: Station | None = None) -> Station:
    """
    Create a representative station from hub child stations.

    Pure function that aggregates data from multiple stations in a hub
    into a single canonical representative station. Uses the preferred child
    (if provided) or first child as a template and aggregates data from all children.

    The representative station has:
    - id: from preferred_child (if provided) or first child
    - tfl_id: hub_naptan_code (canonical ID)
    - name: hub_common_name (or first child's name as fallback)
    - lines: aggregated from all children (sorted, deduplicated)
    - last_updated: most recent timestamp from all children
    - latitude/longitude: from preferred_child or first child (same location for all hub children)

    Args:
        hub_children: Non-empty list of Station objects sharing the same hub
        preferred_child: Optional Station to use as template (e.g., station serving queried line).
                        Must be in hub_children list. If None, uses first child.

    Returns:
        A new Station object representing the entire hub

    Raises:
        ValueError: If hub_children is empty or preferred_child not in hub_children

    Examples:
        >>> rail = Station(
        ...     id=uuid4(),
        ...     tfl_id="910GSEVNSIS",
        ...     name="Seven Sisters (Rail)",
        ...     hub_naptan_code="HUBSVS",
        ...     hub_common_name="Seven Sisters",
        ...     lines=["overground"],
        ...     last_updated=datetime(2025, 1, 1),
        ...     latitude=51.58,
        ...     longitude=-0.07,
        ... )
        >>> tube = Station(
        ...     id=uuid4(),
        ...     tfl_id="940GZZLUSVS",
        ...     name="Seven Sisters",
        ...     hub_naptan_code="HUBSVS",
        ...     hub_common_name="Seven Sisters",
        ...     lines=["victoria"],
        ...     last_updated=datetime(2025, 1, 15),
        ...     latitude=51.58,
        ...     longitude=-0.07,
        ... )
        >>> representative = create_hub_representative([rail, tube])
        >>> representative.tfl_id
        'HUBSVS'
        >>> representative.name
        'Seven Sisters'
        >>> representative.lines
        ['overground', 'victoria']
    """
    if not hub_children:
        msg = "Cannot create hub representative from empty list"
        raise ValueError(msg)

    # Validate preferred_child if provided
    if preferred_child is not None and preferred_child not in hub_children:
        msg = f"preferred_child {preferred_child.tfl_id} not found in hub_children"
        raise ValueError(msg)

    # Use preferred child as template, or first child if no preference
    representative = preferred_child if preferred_child is not None else hub_children[0]

    # Aggregate data from all children
    aggregated_lines = aggregate_station_lines(hub_children)
    latest_update = get_latest_update_time(hub_children)

    # Create new Station with aggregated data
    return Station(
        id=representative.id,
        tfl_id=get_canonical_station_id(representative),  # Use hub code as canonical ID
        name=representative.hub_common_name or representative.name,  # Prefer hub common name
        latitude=representative.latitude,
        longitude=representative.longitude,
        lines=aggregated_lines,
        last_updated=latest_update,
        hub_naptan_code=representative.hub_naptan_code,
        hub_common_name=representative.hub_common_name,
    )


def build_naptan_to_canonical_map(stations: list[Station]) -> dict[str, str]:
    """
    Build mapping from tfl_id (NaPTAN) to canonical station ID (hub code or self).

    Pure function that creates an efficient lookup table for translating NaPTAN IDs
    to their canonical identifiers. Used when translating route_variants for API responses.

    For hub stations, the canonical ID is the hub_naptan_code.
    For standalone stations, the canonical ID is the station's own tfl_id.

    Args:
        stations: List of Station objects from database

    Returns:
        Dictionary mapping tfl_id (NaPTAN ID) -> canonical_id (hub code or tfl_id)

    Examples:
        >>> hub_station = Station(tfl_id="940GZZLUPAC", hub_naptan_code="HUBPAD", ...)
        >>> standalone = Station(tfl_id="940GZZLUOXC", hub_naptan_code=None, ...)
        >>> mapping = build_naptan_to_canonical_map([hub_station, standalone])
        >>> mapping["940GZZLUPAC"]
        'HUBPAD'
        >>> mapping["940GZZLUOXC"]
        '940GZZLUOXC'
    """
    return {station.tfl_id: get_canonical_station_id(station) for station in stations}


def translate_route_variants_to_canonical(
    route_variants: dict[str, list[dict[str, str | list[str]]]] | None,
    naptan_to_canonical: dict[str, str],
) -> dict[str, list[dict[str, str | list[str]]]] | None:
    """
    Translate station IDs in route_variants to canonical IDs.

    Pure function that transforms route_variants data by replacing raw NaPTAN IDs
    with canonical station IDs (hub codes where applicable). Used to generate
    route_variants_canonical for API responses.

    Args:
        route_variants: Route variants dict with "routes" list containing "stations"
        naptan_to_canonical: Mapping from NaPTAN ID to canonical ID

    Returns:
        New dict with translated station IDs, or None/empty if input is None/empty
        Falls back to original ID if not found in mapping (defensive coding)

    Examples:
        >>> route_variants = {
        ...     "routes": [
        ...         {"name": "Test", "stations": ["940GZZLUPAC", "940GZZLUOXC"]}
        ...     ]
        ... }
        >>> mapping = {"940GZZLUPAC": "HUBPAD", "940GZZLUOXC": "940GZZLUOXC"}
        >>> result = translate_route_variants_to_canonical(route_variants, mapping)
        >>> result["routes"][0]["stations"]
        ['HUBPAD', '940GZZLUOXC']
    """
    if not route_variants or "routes" not in route_variants:
        return route_variants

    translated_routes = []
    for route in route_variants["routes"]:
        translated_route = route.copy()
        if "stations" in route:
            # Translate each station ID, fallback to original if not in mapping
            translated_route["stations"] = [naptan_to_canonical.get(sid, sid) for sid in route["stations"]]
        translated_routes.append(translated_route)

    return {"routes": translated_routes}
