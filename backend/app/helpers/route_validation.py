"""
Route validation helpers for directional validation.

These pure functions enable testable, functional-style route validation logic
without requiring database access. They are used by TfLService._check_connection()
for validating station connections on TfL lines.

Issue #57: Route direction validation
"""

from __future__ import annotations

from typing import TypedDict


class RouteVariant(TypedDict):
    """Type definition for a route variant from Line.route_variants JSON."""

    name: str
    service_type: str
    direction: str
    stations: list[str]


class ConnectionResult(TypedDict):
    """Result of checking a connection in a single route variant."""

    found: bool
    from_index: int | None
    to_index: int | None
    route_name: str | None
    direction: str | None


def check_stations_in_route(
    from_station_tfl_id: str,
    to_station_tfl_id: str,
    stations: list[str],
) -> tuple[bool, int | None, int | None]:
    """
    Check if two stations exist in a route sequence and return their positions.

    Pure function that finds the positions of both stations in the route sequence.
    Does NOT validate direction - just returns positions for further processing.

    Args:
        from_station_tfl_id: Starting station TfL ID
        to_station_tfl_id: Destination station TfL ID
        stations: Ordered list of station TfL IDs in route sequence

    Returns:
        Tuple of (both_found, from_index, to_index)
        - both_found: True if both stations exist in sequence
        - from_index: Index of from_station (None if not found)
        - to_index: Index of to_station (None if not found)

    Examples:
        >>> check_stations_in_route("A", "C", ["A", "B", "C"])
        (True, 0, 2)

        >>> check_stations_in_route("C", "A", ["A", "B", "C"])
        (True, 2, 0)

        >>> check_stations_in_route("A", "D", ["A", "B", "C"])
        (False, 0, None)
    """
    try:
        from_index = stations.index(from_station_tfl_id)
    except ValueError:
        return (False, None, None)

    try:
        to_index = stations.index(to_station_tfl_id)
    except ValueError:
        return (False, from_index, None)

    return (True, from_index, to_index)


def validate_station_order(from_index: int, to_index: int) -> bool:
    """
    Validate that stations appear in forward order (directional validation).

    Pure function that enforces from_station must come BEFORE to_station
    in the route sequence to prevent backwards travel.

    Args:
        from_index: Index of starting station
        to_index: Index of destination station

    Returns:
        True if to_station comes after from_station (valid forward direction)

    Examples:
        >>> validate_station_order(0, 2)  # A → C
        True

        >>> validate_station_order(2, 0)  # C → A (backwards)
        False

        >>> validate_station_order(1, 1)  # Same station
        False
    """
    return from_index < to_index


def check_connection_in_route_variant(
    from_station_tfl_id: str,
    to_station_tfl_id: str,
    route: RouteVariant,
) -> ConnectionResult:
    """
    Check if two stations are connected in correct order within a single route variant.

    Combines station lookup and directional validation for a single route variant.
    Pure function with no side effects.

    Args:
        from_station_tfl_id: Starting station TfL ID
        to_station_tfl_id: Destination station TfL ID
        route: Route variant dict with 'stations', 'name', 'direction' keys

    Returns:
        ConnectionResult dict with:
        - found: True if valid connection exists in correct order
        - from_index: Position of from_station (None if not found)
        - to_index: Position of to_station (None if not found)
        - route_name: Name of route variant
        - direction: Direction label (inbound/outbound)

    Examples:
        >>> route = {
        ...     "name": "A → C",
        ...     "direction": "inbound",
        ...     "service_type": "Regular",
        ...     "stations": ["A", "B", "C"]
        ... }
        >>> check_connection_in_route_variant("A", "C", route)
        {'found': True, 'from_index': 0, 'to_index': 2, 'route_name': 'A → C', 'direction': 'inbound'}

        >>> check_connection_in_route_variant("C", "A", route)  # Backwards
        {'found': False, 'from_index': 2, 'to_index': 0, 'route_name': 'A → C', 'direction': 'inbound'}
    """
    stations = route.get("stations", [])
    both_found, from_index, to_index = check_stations_in_route(from_station_tfl_id, to_station_tfl_id, stations)

    # If both stations found, validate direction
    if both_found and from_index is not None and to_index is not None:
        valid_direction = validate_station_order(from_index, to_index)
        return ConnectionResult(
            found=valid_direction,
            from_index=from_index,
            to_index=to_index,
            route_name=route.get("name"),
            direction=route.get("direction"),
        )

    # Stations not both found in this route variant
    return ConnectionResult(
        found=False,
        from_index=from_index,
        to_index=to_index,
        route_name=route.get("name"),
        direction=route.get("direction"),
    )


def find_valid_connection_in_routes(
    from_station_tfl_id: str,
    to_station_tfl_id: str,
    routes: list[RouteVariant],
) -> ConnectionResult | None:
    """
    Find the first valid connection across multiple route variants.

    Iterates through route variants and returns the first one where both stations
    exist in the correct order. Returns None if no valid connection found.

    If stations are found but in wrong order (backwards), returns a ConnectionResult
    with found=False but with indices populated, allowing caller to distinguish
    between backwards travel and stations not being in same route.

    Performance: O(r * n) where r = number of route variants, n = stations per route.
    With typical values (2-6 route variants, 20-60 stations each), this is fast.

    Args:
        from_station_tfl_id: Starting station TfL ID
        to_station_tfl_id: Destination station TfL ID
        routes: List of route variant dicts

    Returns:
        - ConnectionResult with found=True if valid connection exists
        - ConnectionResult with found=False + indices if backwards travel detected
        - None if stations not found in any common route sequence

    Examples:
        >>> routes = [
        ...     {"name": "A → C", "direction": "inbound", "service_type": "Regular", "stations": ["A", "B", "C"]},
        ...     {"name": "C → A", "direction": "outbound", "service_type": "Regular", "stations": ["C", "B", "A"]},
        ... ]
        >>> find_valid_connection_in_routes("A", "C", routes)
        {'found': True, 'from_index': 0, 'to_index': 2, ...}

        >>> find_valid_connection_in_routes("B", "A", routes)  # Backwards on first, need second route
        {'found': True, 'from_index': 1, 'to_index': 2, ...}
    """
    backwards_result = None

    for route in routes:
        result = check_connection_in_route_variant(from_station_tfl_id, to_station_tfl_id, route)
        if result["found"]:
            return result

        # Track backwards travel (stations found but wrong order) for better error reporting
        if result["from_index"] is not None and result["to_index"] is not None and backwards_result is None:
            backwards_result = result

    # Return backwards result if detected, otherwise None (different branches)
    return backwards_result
