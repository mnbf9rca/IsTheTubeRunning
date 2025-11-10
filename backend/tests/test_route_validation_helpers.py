"""
Unit tests for route validation pure helper functions.

These tests validate the pure functional helpers in app/helpers/route_validation.py
without requiring database access or async operations. This provides faster,
more focused testing of the core validation logic.

Issue #57: Route direction validation refactoring
"""

from app.helpers.route_validation import (
    RouteVariant,
    check_connection_in_route_variant,
    check_stations_in_route,
    find_valid_connection_in_routes,
    validate_station_order,
)


class TestCheckStationsInRoute:
    """Test check_stations_in_route() - station position lookup."""

    def test_both_stations_found_forward_order(self) -> None:
        """Should find both stations and return their indices."""
        stations = ["A", "B", "C", "D"]
        both_found, from_idx, to_idx = check_stations_in_route("A", "C", stations)

        assert both_found is True
        assert from_idx == 0
        assert to_idx == 2

    def test_both_stations_found_backwards_order(self) -> None:
        """Should find both stations regardless of order (doesn't validate direction)."""
        stations = ["A", "B", "C", "D"]
        both_found, from_idx, to_idx = check_stations_in_route("C", "A", stations)

        assert both_found is True
        assert from_idx == 2
        assert to_idx == 0

    def test_from_station_not_found(self) -> None:
        """Should return False if from_station not in sequence."""
        stations = ["A", "B", "C"]
        both_found, from_idx, to_idx = check_stations_in_route("X", "B", stations)

        assert both_found is False
        assert from_idx is None
        assert to_idx is None

    def test_to_station_not_found(self) -> None:
        """Should return False if to_station not in sequence."""
        stations = ["A", "B", "C"]
        both_found, from_idx, to_idx = check_stations_in_route("A", "X", stations)

        assert both_found is False
        assert from_idx == 0
        assert to_idx is None

    def test_empty_station_list(self) -> None:
        """Should handle empty station list."""
        stations: list[str] = []
        both_found, from_idx, to_idx = check_stations_in_route("A", "B", stations)

        assert both_found is False
        assert from_idx is None
        assert to_idx is None

    def test_same_station(self) -> None:
        """Should handle case where from and to are same station."""
        stations = ["A", "B", "C"]
        both_found, from_idx, to_idx = check_stations_in_route("B", "B", stations)

        assert both_found is True
        assert from_idx == 1
        assert to_idx == 1


class TestValidateStationOrder:
    """Test validate_station_order() - directional validation."""

    def test_forward_direction_valid(self) -> None:
        """Should return True when to_station comes after from_station."""
        assert validate_station_order(0, 2) is True
        assert validate_station_order(1, 3) is True
        assert validate_station_order(0, 1) is True

    def test_backwards_direction_invalid(self) -> None:
        """Should return False when to_station comes before from_station."""
        assert validate_station_order(2, 0) is False
        assert validate_station_order(3, 1) is False
        assert validate_station_order(1, 0) is False

    def test_same_position_invalid(self) -> None:
        """Should return False for same station (no movement)."""
        assert validate_station_order(1, 1) is False
        assert validate_station_order(0, 0) is False


class TestCheckConnectionInRouteVariant:
    """Test check_connection_in_route_variant() - single route validation."""

    def test_valid_forward_connection(self) -> None:
        """Should find valid connection in forward direction."""
        route: RouteVariant = {
            "name": "A → D",
            "service_type": "Regular",
            "direction": "inbound",
            "stations": ["A", "B", "C", "D"],
        }

        result = check_connection_in_route_variant("A", "C", route)

        assert result["found"] is True
        assert result["from_index"] == 0
        assert result["to_index"] == 2
        assert result["route_name"] == "A → D"
        assert result["direction"] == "inbound"

    def test_backwards_connection_rejected(self) -> None:
        """Should reject backwards connection (wrong direction)."""
        route: RouteVariant = {
            "name": "A → D",
            "service_type": "Regular",
            "direction": "inbound",
            "stations": ["A", "B", "C", "D"],
        }

        result = check_connection_in_route_variant("C", "A", route)

        assert result["found"] is False
        assert result["from_index"] == 2  # Found but wrong order
        assert result["to_index"] == 0
        assert result["route_name"] == "A → D"

    def test_station_not_in_route(self) -> None:
        """Should handle station not found in route."""
        route: RouteVariant = {
            "name": "A → C",
            "service_type": "Regular",
            "direction": "inbound",
            "stations": ["A", "B", "C"],
        }

        result = check_connection_in_route_variant("A", "X", route)

        assert result["found"] is False
        assert result["from_index"] == 0
        assert result["to_index"] is None

    def test_empty_stations_list(self) -> None:
        """Should handle route with no stations."""
        route: RouteVariant = {
            "name": "Empty Route",
            "service_type": "Regular",
            "direction": "inbound",
            "stations": [],
        }

        result = check_connection_in_route_variant("A", "B", route)

        assert result["found"] is False
        assert result["from_index"] is None
        assert result["to_index"] is None

    def test_missing_stations_key(self) -> None:
        """Should handle route dict without 'stations' key."""
        route: RouteVariant = {
            "name": "No Stations",
            "service_type": "Regular",
            "direction": "inbound",
            "stations": [],  # TypedDict requires this, but test the .get() fallback
        }

        result = check_connection_in_route_variant("A", "B", route)

        assert result["found"] is False


class TestFindValidConnectionInRoutes:
    """Test find_valid_connection_in_routes() - multi-route search."""

    def test_finds_connection_in_first_route(self) -> None:
        """Should return connection from first matching route."""
        routes: list[RouteVariant] = [
            {
                "name": "A → D",
                "service_type": "Regular",
                "direction": "inbound",
                "stations": ["A", "B", "C", "D"],
            },
            {
                "name": "D → A",
                "service_type": "Regular",
                "direction": "outbound",
                "stations": ["D", "C", "B", "A"],
            },
        ]

        result = find_valid_connection_in_routes("A", "C", routes)

        assert result is not None
        assert result["found"] is True
        assert result["route_name"] == "A → D"
        assert result["from_index"] == 0
        assert result["to_index"] == 2

    def test_finds_connection_in_second_route_when_first_backwards(self) -> None:
        """Should skip first route if backwards, find connection in second route."""
        routes: list[RouteVariant] = [
            {
                "name": "A → D",
                "service_type": "Regular",
                "direction": "inbound",
                "stations": ["A", "B", "C", "D"],
            },
            {
                "name": "D → A",
                "service_type": "Regular",
                "direction": "outbound",
                "stations": ["D", "C", "B", "A"],
            },
        ]

        # C → A is backwards on first route, forward on second route
        result = find_valid_connection_in_routes("C", "A", routes)

        assert result is not None
        assert result["found"] is True
        assert result["route_name"] == "D → A"
        assert result["from_index"] == 1
        assert result["to_index"] == 3

    def test_no_valid_connection_in_any_route(self) -> None:
        """Should return None if no valid connection found."""
        routes: list[RouteVariant] = [
            {
                "name": "A → C",
                "service_type": "Regular",
                "direction": "inbound",
                "stations": ["A", "B", "C"],
            },
            {
                "name": "D → F",
                "service_type": "Regular",
                "direction": "inbound",
                "stations": ["D", "E", "F"],
            },
        ]

        # A and X not in same route
        result = find_valid_connection_in_routes("A", "X", routes)

        assert result is None

    def test_branches_on_same_line(self) -> None:
        """Should correctly handle branched lines (different routes for different branches)."""
        routes: list[RouteVariant] = [
            {
                "name": "Edgware → Morden via Bank",
                "service_type": "Regular",
                "direction": "inbound",
                "stations": ["EGW", "CMD", "BNK", "MDN"],
            },
            {
                "name": "Edgware → Morden via Charing Cross",
                "service_type": "Regular",
                "direction": "inbound",
                "stations": ["EGW", "CMD", "CHX", "MDN"],
            },
        ]

        # Bank → Charing Cross should fail (different branches)
        result = find_valid_connection_in_routes("BNK", "CHX", routes)
        assert result is None

        # Camden → Bank should succeed (same branch)
        result = find_valid_connection_in_routes("CMD", "BNK", routes)
        assert result is not None
        assert result["found"] is True
        assert result["route_name"] == "Edgware → Morden via Bank"

    def test_empty_routes_list(self) -> None:
        """Should handle empty routes list."""
        routes: list[RouteVariant] = []

        result = find_valid_connection_in_routes("A", "B", routes)

        assert result is None

    def test_bidirectional_line_support(self) -> None:
        """Should support bidirectional travel via separate route variants."""
        routes: list[RouteVariant] = [
            {
                "name": "Brixton → Walthamstow",
                "service_type": "Regular",
                "direction": "inbound",
                "stations": ["BXN", "STK", "WTH"],
            },
            {
                "name": "Walthamstow → Brixton",
                "service_type": "Regular",
                "direction": "outbound",
                "stations": ["WTH", "STK", "BXN"],
            },
        ]

        # Forward direction (matches first route)
        result = find_valid_connection_in_routes("BXN", "WTH", routes)
        assert result is not None
        assert result["found"] is True
        assert result["direction"] == "inbound"

        # Reverse direction (matches second route)
        result = find_valid_connection_in_routes("WTH", "BXN", routes)
        assert result is not None
        assert result["found"] is True
        assert result["direction"] == "outbound"
