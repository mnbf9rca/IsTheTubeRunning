"""Tests for disruption_helpers pure functions.

This module tests pure helper functions extracted to backend/app/helpers/disruption_helpers.py:
- extract_line_station_pairs()
- disruption_affects_route()
- calculate_affected_segments()
- calculate_affected_stations()

These tests follow ADR 10 testing patterns and achieve 100% branch and statement coverage.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.helpers.disruption_helpers import (
    calculate_affected_segments,
    calculate_affected_stations,
    disruption_affects_route,
    extract_line_station_pairs,
)
from app.models.tfl import Line, Station
from app.models.user_route import UserRouteSegment
from app.schemas.tfl import AffectedRouteInfo, DisruptionResponse

# ==================== Fixtures ====================


@pytest.fixture
def piccadilly_line() -> Line:
    """Create a mock Piccadilly Line."""
    return Line(
        id=uuid4(),
        tfl_id="piccadilly",
        name="Piccadilly",
        mode="tube",
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def victoria_line() -> Line:
    """Create a mock Victoria Line."""
    return Line(
        id=uuid4(),
        tfl_id="victoria",
        name="Victoria",
        mode="tube",
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def district_line() -> Line:
    """Create a mock District Line."""
    return Line(
        id=uuid4(),
        tfl_id="district",
        name="District",
        mode="tube",
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def kings_cross_station() -> Station:
    """Create a mock King's Cross station."""
    return Station(
        id=uuid4(),
        tfl_id="940GZZLUKSX",
        name="King's Cross St Pancras",
        latitude=51.5308,
        longitude=-0.1238,
        lines=["piccadilly", "circle", "hammersmith-city", "metropolitan", "northern"],
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def russell_square_station() -> Station:
    """Create a mock Russell Square station."""
    return Station(
        id=uuid4(),
        tfl_id="940GZZLURSQ",
        name="Russell Square",
        latitude=51.5230,
        longitude=-0.1244,
        lines=["piccadilly"],
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def holborn_station() -> Station:
    """Create a mock Holborn station."""
    return Station(
        id=uuid4(),
        tfl_id="940GZZLUHBN",
        name="Holborn",
        latitude=51.5174,
        longitude=-0.1200,
        lines=["piccadilly", "central"],
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def embankment_station() -> Station:
    """Create a mock Embankment station."""
    return Station(
        id=uuid4(),
        tfl_id="940GZZLUEMB",
        name="Embankment",
        latitude=51.5073,
        longitude=-0.1248,
        lines=["bakerloo", "circle", "district", "hammersmith-city", "northern"],
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def leicester_square_station() -> Station:
    """Create a mock Leicester Square station."""
    return Station(
        id=uuid4(),
        tfl_id="940GZZLULST",
        name="Leicester Square",
        latitude=51.5111,
        longitude=-0.1281,
        lines=["piccadilly", "northern"],
        last_updated=datetime.now(UTC),
    )


@pytest.fixture
def route_id() -> str:
    """Generate a route ID."""
    return str(uuid4())


# ==================== Test extract_line_station_pairs ====================


class TestExtractLineStationPairs:
    """Test extract_line_station_pairs function."""

    def test_extract_single_route_single_station(self) -> None:
        """Test extracting pairs from single route with single station."""
        disruption = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Cockfosters → Heathrow T5",
                    direction="outbound",
                    affected_stations=["940GZZLURSQ"],
                )
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        assert len(pairs) == 1
        assert ("piccadilly", "940GZZLURSQ") in pairs

    def test_extract_single_route_multiple_stations(self) -> None:
        """Test extracting pairs from single route with multiple stations."""
        disruption = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Cockfosters → Heathrow T5",
                    direction="outbound",
                    affected_stations=["940GZZLURSQ", "940GZZLUHBN", "940GZZLULST"],
                )
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        assert len(pairs) == 3
        assert ("piccadilly", "940GZZLURSQ") in pairs
        assert ("piccadilly", "940GZZLUHBN") in pairs
        assert ("piccadilly", "940GZZLULST") in pairs

    def test_extract_multiple_routes_different_stations(self) -> None:
        """Test extracting pairs from multiple routes with different stations."""
        disruption = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Cockfosters → Heathrow T5",
                    direction="outbound",
                    affected_stations=["940GZZLURSQ", "940GZZLUHBN"],
                ),
                AffectedRouteInfo(
                    name="Heathrow T5 → Cockfosters",
                    direction="inbound",
                    affected_stations=["940GZZLUHBN", "940GZZLULST"],
                ),
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        # Should have 4 pairs (including duplicate for 940GZZLUHBN)
        assert len(pairs) == 4
        assert ("piccadilly", "940GZZLURSQ") in pairs
        assert ("piccadilly", "940GZZLUHBN") in pairs
        assert ("piccadilly", "940GZZLULST") in pairs
        # Count duplicates
        assert pairs.count(("piccadilly", "940GZZLUHBN")) == 2

    def test_extract_multiple_routes_overlapping_stations(self) -> None:
        """Test extracting pairs from routes with overlapping stations."""
        disruption = DisruptionResponse(
            line_id="district",
            line_name="District",
            mode="tube",
            status_severity=9,
            status_severity_description="Severe Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Ealing Broadway → Upminster",
                    direction="outbound",
                    affected_stations=["940GZZLUEMB", "940GZZLURSQ"],
                ),
                AffectedRouteInfo(
                    name="Upminster → Ealing Broadway",
                    direction="inbound",
                    affected_stations=["940GZZLURSQ", "940GZZLUEMB"],
                ),
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        # Should have 4 pairs (2 duplicates)
        assert len(pairs) == 4
        assert pairs.count(("district", "940GZZLUEMB")) == 2
        assert pairs.count(("district", "940GZZLURSQ")) == 2

    def test_extract_with_empty_affected_routes_list(self) -> None:
        """Test with disruption that has empty affected_routes list."""
        disruption = DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=10,
            status_severity_description="Good Service",
            affected_routes=[],
        )

        pairs = extract_line_station_pairs(disruption)

        assert pairs == []

    def test_extract_with_none_affected_routes(self) -> None:
        """Test with disruption that has None affected_routes."""
        disruption = DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=10,
            status_severity_description="Good Service",
            affected_routes=None,
        )

        pairs = extract_line_station_pairs(disruption)

        assert pairs == []

    def test_extract_with_empty_stations_list(self) -> None:
        """Test with route that has empty affected_stations list (edge case)."""
        disruption = DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Edgware → Morden",
                    direction="outbound",
                    affected_stations=[],
                )
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        assert pairs == []

    def test_extract_multiple_routes_with_mixed_empty_stations(self) -> None:
        """Test multiple routes where one has empty stations."""
        disruption = DisruptionResponse(
            line_id="circle",
            line_name="Circle",
            mode="tube",
            status_severity=9,
            status_severity_description="Minor Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Circle Line",
                    direction="both",
                    affected_stations=["940GZZLURSQ", "940GZZLUKSX"],
                ),
                AffectedRouteInfo(
                    name="Empty Route",
                    direction="both",
                    affected_stations=[],
                ),
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        assert len(pairs) == 2
        assert ("circle", "940GZZLURSQ") in pairs
        assert ("circle", "940GZZLUKSX") in pairs

    def test_extract_with_long_naptan_codes(self) -> None:
        """Test with various NaPTAN code formats."""
        disruption = DisruptionResponse(
            line_id="elizabeth-line",
            line_name="Elizabeth Line",
            mode="elizabeth-line",
            status_severity=8,
            status_severity_description="Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Paddington → Abbey Wood",
                    direction="outbound",
                    affected_stations=[
                        "940GZZLUPDD",
                        "940GZZLBBK",
                        "940GZZLASG",
                    ],
                )
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        assert len(pairs) == 3
        assert all(line_id == "elizabeth-line" for line_id, _ in pairs)

    def test_extract_preserves_pair_order(self) -> None:
        """Test that pair extraction maintains order from affected_routes."""
        disruption = DisruptionResponse(
            line_id="bakerloo",
            line_name="Bakerloo",
            mode="tube",
            status_severity=9,
            status_severity_description="Minor Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Harrow & Wealdstone → Elephant & Castle",
                    direction="outbound",
                    affected_stations=["940GZZLUHAW", "940GZZLUKSX", "940GZZLUEC"],
                )
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        # Verify order is preserved from affected_stations
        assert pairs == [
            ("bakerloo", "940GZZLUHAW"),
            ("bakerloo", "940GZZLUKSX"),
            ("bakerloo", "940GZZLUEC"),
        ]


# ==================== Test disruption_affects_route ====================


class TestDisruptionAffectsRoute:
    """Test disruption_affects_route function."""

    def test_affects_route_single_match(self) -> None:
        """Test when one disruption pair matches a route pair."""
        disruption_pairs = [("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLUHBN")]
        route_pairs = {("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLULST")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is True

    def test_affects_route_multiple_matches(self) -> None:
        """Test when multiple disruption pairs match route pairs."""
        disruption_pairs = [
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLUHBN"),
        ]
        route_pairs = {
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLUHBN"),
            ("piccadilly", "940GZZLULST"),
        }

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is True

    def test_affects_route_no_match_different_lines(self) -> None:
        """Test when no pairs match due to different lines."""
        disruption_pairs = [("piccadilly", "940GZZLURSQ")]
        route_pairs = {("district", "940GZZLURSQ")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_affects_route_no_match_different_stations(self) -> None:
        """Test when no pairs match due to different stations."""
        disruption_pairs = [("piccadilly", "940GZZLURSQ")]
        route_pairs = {("piccadilly", "940GZZLUHBN")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_affects_route_no_match_both_different(self) -> None:
        """Test when no pairs match (both line and station different)."""
        disruption_pairs = [("piccadilly", "940GZZLURSQ")]
        route_pairs = {("victoria", "940GZZLUVIC")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_affects_route_empty_disruption_pairs(self) -> None:
        """Test with empty disruption pairs list."""
        disruption_pairs: list[tuple[str, str]] = []
        route_pairs = {("piccadilly", "940GZZLURSQ")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_affects_route_empty_route_pairs(self) -> None:
        """Test with empty route pairs set."""
        disruption_pairs = [("piccadilly", "940GZZLURSQ")]
        route_pairs: set[tuple[str, str]] = set()

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_affects_route_both_empty(self) -> None:
        """Test with both empty disruption and route pairs."""
        disruption_pairs: list[tuple[str, str]] = []
        route_pairs: set[tuple[str, str]] = set()

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_affects_route_large_disruption_list(self) -> None:
        """Test with large list of disruption pairs."""
        disruption_pairs = [(f"line_{i}", f"station_{i}") for i in range(100)]
        # Match on the last item
        disruption_pairs.append(("piccadilly", "940GZZLURSQ"))
        route_pairs = {("piccadilly", "940GZZLURSQ")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is True

    def test_affects_route_large_route_set(self) -> None:
        """Test with large set of route pairs."""
        route_pairs = {(f"line_{i}", f"station_{i}") for i in range(100)}
        route_pairs.add(("piccadilly", "940GZZLURSQ"))
        disruption_pairs = [("piccadilly", "940GZZLURSQ")]

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is True

    def test_affects_route_with_duplicates_in_disruption_list(self) -> None:
        """Test when disruption pairs list contains duplicates."""
        disruption_pairs = [
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLURSQ"),  # Duplicate
        ]
        route_pairs = {("piccadilly", "940GZZLURSQ")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is True


# ==================== Test calculate_affected_segments ====================


class TestCalculateAffectedSegments:
    """Test calculate_affected_segments function."""

    def test_single_matched_segment(
        self, piccadilly_line: Line, russell_square_station: Station, route_id: str
    ) -> None:
        """Test calculating affected segments with single match."""
        segment = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=russell_square_station.id,
            line_id=piccadilly_line.id,
        )
        segment.line = piccadilly_line
        segment.station = russell_square_station

        matched_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_segments([segment], matched_pairs)

        assert result == [0]

    def test_multiple_matched_segments(
        self,
        piccadilly_line: Line,
        russell_square_station: Station,
        holborn_station: Station,
        route_id: str,
    ) -> None:
        """Test calculating affected segments with multiple matches."""
        segment1 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=russell_square_station.id,
            line_id=piccadilly_line.id,
        )
        segment1.line = piccadilly_line
        segment1.station = russell_square_station

        segment2 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=1,
            station_id=holborn_station.id,
            line_id=piccadilly_line.id,
        )
        segment2.line = piccadilly_line
        segment2.station = holborn_station

        matched_pairs = {("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLUHBN")}

        result = calculate_affected_segments([segment1, segment2], matched_pairs)

        assert result == [0, 1]

    def test_no_matched_segments(self, piccadilly_line: Line, russell_square_station: Station, route_id: str) -> None:
        """Test when no segments match."""
        segment = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=russell_square_station.id,
            line_id=piccadilly_line.id,
        )
        segment.line = piccadilly_line
        segment.station = russell_square_station

        # Different station
        matched_pairs = {("piccadilly", "940GZZLUHBN")}

        result = calculate_affected_segments([segment], matched_pairs)

        assert result == []

    def test_partial_matched_segments(
        self,
        piccadilly_line: Line,
        victoria_line: Line,
        russell_square_station: Station,
        holborn_station: Station,
        route_id: str,
    ) -> None:
        """Test when only some segments match."""
        segment1 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=russell_square_station.id,
            line_id=piccadilly_line.id,
        )
        segment1.line = piccadilly_line
        segment1.station = russell_square_station

        segment2 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=1,
            station_id=holborn_station.id,
            line_id=victoria_line.id,
        )
        segment2.line = victoria_line
        segment2.station = holborn_station

        # Only match first segment
        matched_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_segments([segment1, segment2], matched_pairs)

        assert result == [0]

    def test_segment_without_line(self, russell_square_station: Station, route_id: str) -> None:
        """Test that segments without line (destination) are skipped."""
        segment = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=russell_square_station.id,
            line_id=None,
        )
        segment.line = None  # type: ignore[assignment]
        segment.station = russell_square_station

        matched_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_segments([segment], matched_pairs)

        # Should be empty because segment has no line
        assert result == []

    def test_segment_without_station(self, piccadilly_line: Line, route_id: str) -> None:
        """Test that segments without station are skipped."""
        segment = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=uuid4(),
            line_id=piccadilly_line.id,
        )
        segment.line = piccadilly_line
        segment.station = None  # type: ignore[assignment]

        matched_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_segments([segment], matched_pairs)

        # Should be empty because segment has no station
        assert result == []

    def test_empty_segments_list(self) -> None:
        """Test with empty segments list."""
        matched_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_segments([], matched_pairs)

        assert result == []

    def test_empty_matched_pairs(self, piccadilly_line: Line, russell_square_station: Station, route_id: str) -> None:
        """Test with empty matched pairs."""
        segment = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=russell_square_station.id,
            line_id=piccadilly_line.id,
        )
        segment.line = piccadilly_line
        segment.station = russell_square_station

        matched_pairs: set[tuple[str, str]] = set()

        result = calculate_affected_segments([segment], matched_pairs)

        assert result == []

    def test_many_segments_mixed_matches(
        self,
        piccadilly_line: Line,
        district_line: Line,
        russell_square_station: Station,
        holborn_station: Station,
        kings_cross_station: Station,
        embankment_station: Station,
        route_id: str,
    ) -> None:
        """Test with many segments where some match."""
        segments = [
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=0,
                station_id=kings_cross_station.id,
                line_id=piccadilly_line.id,
            ),
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=1,
                station_id=russell_square_station.id,
                line_id=piccadilly_line.id,
            ),
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=2,
                station_id=holborn_station.id,
                line_id=piccadilly_line.id,
            ),
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=3,
                station_id=embankment_station.id,
                line_id=district_line.id,
            ),
        ]

        # Set relationships
        segments[0].line = piccadilly_line
        segments[0].station = kings_cross_station
        segments[1].line = piccadilly_line
        segments[1].station = russell_square_station
        segments[2].line = piccadilly_line
        segments[2].station = holborn_station
        segments[3].line = district_line
        segments[3].station = embankment_station

        # Only match sequences 1 and 3
        matched_pairs = {
            ("piccadilly", "940GZZLURSQ"),
            ("district", "940GZZLUEMB"),
        }

        result = calculate_affected_segments(segments, matched_pairs)

        assert result == [1, 3]

    def test_non_sequential_affected_segments(
        self,
        piccadilly_line: Line,
        russell_square_station: Station,
        holborn_station: Station,
        kings_cross_station: Station,
        route_id: str,
    ) -> None:
        """Test affected segments that are not sequential."""
        segments = [
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=0,
                station_id=kings_cross_station.id,
                line_id=piccadilly_line.id,
            ),
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=1,
                station_id=russell_square_station.id,
                line_id=piccadilly_line.id,
            ),
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=2,
                station_id=holborn_station.id,
                line_id=piccadilly_line.id,
            ),
        ]

        segments[0].line = piccadilly_line
        segments[0].station = kings_cross_station
        segments[1].line = piccadilly_line
        segments[1].station = russell_square_station
        segments[2].line = piccadilly_line
        segments[2].station = holborn_station

        # Match sequences 0 and 2 (non-sequential)
        matched_pairs = {
            ("piccadilly", "940GZZLUKSX"),
            ("piccadilly", "940GZZLUHBN"),
        }

        result = calculate_affected_segments(segments, matched_pairs)

        assert result == [0, 2]


# ==================== Test calculate_affected_stations ====================


class TestCalculateAffectedStations:
    """Test calculate_affected_stations function."""

    def test_single_affected_station(self) -> None:
        """Test with single station in intersection."""
        route_pairs = {("piccadilly", "940GZZLUKSX"), ("piccadilly", "940GZZLURSQ")}
        disruption_pairs = {("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLUHBN")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == ["940GZZLURSQ"]

    def test_multiple_affected_stations(self) -> None:
        """Test with multiple stations in intersection."""
        route_pairs = {
            ("piccadilly", "940GZZLUKSX"),
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLUHBN"),
        }
        disruption_pairs = {
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLUHBN"),
        }

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        # Should be sorted
        assert result == ["940GZZLUHBN", "940GZZLURSQ"]

    def test_no_affected_stations(self) -> None:
        """Test with no intersection."""
        route_pairs = {("piccadilly", "940GZZLUKSX")}
        disruption_pairs = {("victoria", "940GZZLUVIC")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == []

    def test_empty_route_pairs(self) -> None:
        """Test with empty route pairs."""
        route_pairs: set[tuple[str, str]] = set()
        disruption_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == []

    def test_empty_disruption_pairs(self) -> None:
        """Test with empty disruption pairs."""
        route_pairs = {("piccadilly", "940GZZLURSQ")}
        disruption_pairs: set[tuple[str, str]] = set()

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == []

    def test_both_empty_pairs(self) -> None:
        """Test with both empty pairs."""
        route_pairs: set[tuple[str, str]] = set()
        disruption_pairs: set[tuple[str, str]] = set()

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == []

    def test_affected_stations_sorted_order(self) -> None:
        """Test that affected stations are returned in sorted order."""
        route_pairs = {
            ("piccadilly", "940GZZLUZZ"),  # Z
            ("piccadilly", "940GZZLUAA"),  # A
            ("piccadilly", "940GZZLUMM"),  # M
        }
        disruption_pairs = {
            ("piccadilly", "940GZZLUAA"),
            ("piccadilly", "940GZZLUZZ"),
            ("piccadilly", "940GZZLUMM"),
        }

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == sorted(result)
        assert result == ["940GZZLUAA", "940GZZLUMM", "940GZZLUZZ"]

    def test_mixed_line_ids_same_station(self) -> None:
        """Test with same station on different lines."""
        route_pairs = {
            ("piccadilly", "940GZZLUKSX"),
            ("circle", "940GZZLUKSX"),
        }
        disruption_pairs = {
            ("piccadilly", "940GZZLUKSX"),
            ("northern", "940GZZLUKSX"),
        }

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        # Only match where (line, station) pair matches
        assert result == ["940GZZLUKSX"]

    def test_multiple_stations_different_lines(self) -> None:
        """Test matching stations on different lines."""
        route_pairs = {
            ("piccadilly", "940GZZLURSQ"),
            ("circle", "940GZZLUHBN"),
            ("district", "940GZZLUEMB"),
        }
        disruption_pairs = {
            ("piccadilly", "940GZZLURSQ"),
            ("circle", "940GZZLUHBN"),
        }

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == ["940GZZLUHBN", "940GZZLURSQ"]

    def test_large_intersection(self) -> None:
        """Test with large number of affected stations."""
        # Create 100 stations
        route_pairs = {(f"line_{i % 10}", f"station_{i}") for i in range(100)}
        disruption_pairs = {(f"line_{i % 10}", f"station_{i}") for i in range(50, 150)}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        # Intersection should have stations 50-99 with their line pairs
        expected_stations = sorted([f"station_{i}" for i in range(50, 100)])
        assert result == expected_stations

    def test_affected_stations_unique(self) -> None:
        """Test that affected stations don't have duplicates."""
        route_pairs = {
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLURSQ"),  # Duplicate line-station pair
        }
        disruption_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        # Should have exactly one entry
        assert result == ["940GZZLURSQ"]
        assert len(result) == 1

    def test_affected_stations_same_station_different_lines_no_match(self) -> None:
        """Test station appearing on different lines with no line-pair match."""
        route_pairs = {
            ("piccadilly", "940GZZLUKSX"),
            ("victoria", "940GZZLUKSX"),
        }
        disruption_pairs = {
            ("circle", "940GZZLUKSX"),
            ("northern", "940GZZLUKSX"),
        }

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        # No matching (line, station) pairs
        assert result == []

    def test_affected_stations_partial_line_match(self) -> None:
        """Test when station matches but line doesn't."""
        route_pairs = {("piccadilly", "940GZZLURSQ")}
        disruption_pairs = {("district", "940GZZLURSQ")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        # No match because line is different
        assert result == []


# ==================== Integration Tests ====================


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_disruption_matching_flow(
        self,
        piccadilly_line: Line,
        russell_square_station: Station,
        holborn_station: Station,
        route_id: str,
    ) -> None:
        """Test full flow: extract -> check match -> calculate affected."""
        # Step 1: Extract pairs from disruption
        disruption = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=9,
            status_severity_description="Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Cockfosters → Heathrow T5",
                    direction="outbound",
                    affected_stations=["940GZZLURSQ", "940GZZLUHBN"],
                )
            ],
        )
        disruption_pairs = extract_line_station_pairs(disruption)

        # Step 2: Build route pairs
        segments = [
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=0,
                station_id=russell_square_station.id,
                line_id=piccadilly_line.id,
            ),
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=1,
                station_id=holborn_station.id,
                line_id=piccadilly_line.id,
            ),
        ]
        segments[0].line = piccadilly_line
        segments[0].station = russell_square_station
        segments[1].line = piccadilly_line
        segments[1].station = holborn_station

        route_pairs = {
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLUHBN"),
        }

        # Step 3: Check if disruption affects route
        affects = disruption_affects_route(disruption_pairs, route_pairs)
        assert affects is True

        # Step 4: Calculate affected segments
        affected_seqs = calculate_affected_segments(segments, set(disruption_pairs))
        assert affected_seqs == [0, 1]

        # Step 5: Calculate affected stations
        affected_stns = calculate_affected_stations(route_pairs, set(disruption_pairs))
        assert set(affected_stns) == {"940GZZLURSQ", "940GZZLUHBN"}

    def test_partial_match_flow(
        self,
        piccadilly_line: Line,
        victoria_line: Line,
        russell_square_station: Station,
        holborn_station: Station,
        route_id: str,
    ) -> None:
        """Test flow when only some route segments are affected."""
        # Disruption on Piccadilly only
        disruption = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=9,
            status_severity_description="Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Cockfosters → Heathrow T5",
                    direction="outbound",
                    affected_stations=["940GZZLURSQ"],
                )
            ],
        )
        disruption_pairs = extract_line_station_pairs(disruption)

        # Route with both Piccadilly and Victoria segments
        segments = [
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=0,
                station_id=russell_square_station.id,
                line_id=piccadilly_line.id,
            ),
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=1,
                station_id=holborn_station.id,
                line_id=victoria_line.id,
            ),
        ]
        segments[0].line = piccadilly_line
        segments[0].station = russell_square_station
        segments[1].line = victoria_line
        segments[1].station = holborn_station

        route_pairs = {
            ("piccadilly", "940GZZLURSQ"),
            ("victoria", "940GZZLUHBN"),
        }

        # Should affect route
        assert disruption_affects_route(disruption_pairs, route_pairs) is True

        # But only segment 0 is affected
        affected_seqs = calculate_affected_segments(segments, set(disruption_pairs))
        assert affected_seqs == [0]

        # Only Russell Square is affected
        affected_stns = calculate_affected_stations(route_pairs, set(disruption_pairs))
        assert affected_stns == ["940GZZLURSQ"]

    def test_no_match_flow(
        self,
        piccadilly_line: Line,
        district_line: Line,
        russell_square_station: Station,
        embankment_station: Station,
        route_id: str,
    ) -> None:
        """Test full flow when disruption doesn't affect route."""
        # Disruption on Piccadilly
        disruption = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=9,
            status_severity_description="Delays",
            affected_routes=[
                AffectedRouteInfo(
                    name="Cockfosters → Heathrow T5",
                    direction="outbound",
                    affected_stations=["940GZZLURSQ"],
                )
            ],
        )
        disruption_pairs = extract_line_station_pairs(disruption)

        # Route on District Line only
        segments = [
            UserRouteSegment(
                id=uuid4(),
                route_id=route_id,
                sequence=0,
                station_id=embankment_station.id,
                line_id=district_line.id,
            )
        ]
        segments[0].line = district_line
        segments[0].station = embankment_station

        route_pairs = {("district", "940GZZLUEMB")}

        # Should not affect route
        assert disruption_affects_route(disruption_pairs, route_pairs) is False

        # No affected segments
        affected_seqs = calculate_affected_segments(segments, set(disruption_pairs))
        assert affected_seqs == []

        # No affected stations
        affected_stns = calculate_affected_stations(route_pairs, set(disruption_pairs))
        assert affected_stns == []
