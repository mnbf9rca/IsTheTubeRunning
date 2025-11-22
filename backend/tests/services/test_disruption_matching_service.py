"""Tests for DisruptionMatchingService."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.models.tfl import AlertDisabledSeverity, Line, Station
from app.models.user import User
from app.models.user_route import UserRoute, UserRouteSegment
from app.models.user_route_index import UserRouteStationIndex
from app.schemas.tfl import AffectedRouteInfo, DisruptionResponse
from app.services.disruption_matching_service import (
    DisruptionMatchingService,
    calculate_affected_segments,
    calculate_affected_stations,
    disruption_affects_route,
    extract_line_station_pairs,
)
from sqlalchemy.ext.asyncio import AsyncSession

# ==================== Test Pure Helper Functions ====================


class TestPureHelperFunctions:
    """Test pure helper functions."""

    def test_extract_line_station_pairs_with_stations(self) -> None:
        """Test extracting pairs from disruption with affected stations."""
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
                )
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        assert len(pairs) == 2
        assert ("piccadilly", "940GZZLURSQ") in pairs
        assert ("piccadilly", "940GZZLUHBN") in pairs

    def test_extract_line_station_pairs_multiple_routes(self) -> None:
        """Test extracting pairs from disruption with multiple affected routes."""
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
                    affected_stations=["940GZZLUHBN", "940GZZLUCGN"],
                ),
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        # Should have 4 pairs (may have duplicates)
        assert len(pairs) == 4
        assert ("piccadilly", "940GZZLURSQ") in pairs
        assert ("piccadilly", "940GZZLUHBN") in pairs
        assert ("piccadilly", "940GZZLUCGN") in pairs

    def test_extract_line_station_pairs_empty_routes(self) -> None:
        """Test with disruption that has no affected_routes."""
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

    def test_extract_line_station_pairs_empty_list(self) -> None:
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

    def test_disruption_affects_route_match(self) -> None:
        """Test when disruption affects route."""
        disruption_pairs = [("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLUHBN")]
        route_pairs = {("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLULST")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is True

    def test_disruption_affects_route_no_match(self) -> None:
        """Test when disruption does not affect route."""
        disruption_pairs = [("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLUHBN")]
        route_pairs = {("district", "940GZZLUEMB")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_disruption_affects_route_empty_disruption(self) -> None:
        """Test with empty disruption pairs."""
        disruption_pairs: list[tuple[str, str]] = []
        route_pairs = {("piccadilly", "940GZZLURSQ")}

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_disruption_affects_route_empty_route(self) -> None:
        """Test with empty route pairs."""
        disruption_pairs = [("piccadilly", "940GZZLURSQ")]
        route_pairs: set[tuple[str, str]] = set()

        result = disruption_affects_route(disruption_pairs, route_pairs)

        assert result is False

    def test_calculate_affected_segments(self) -> None:
        """Test calculating affected segment indices."""
        # Create mock line and station objects
        line = Line(
            id=uuid4(),
            tfl_id="piccadilly",
            name="Piccadilly",
            mode="tube",
            last_updated=datetime.now(UTC),
        )
        station1 = Station(
            id=uuid4(),
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["piccadilly"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            id=uuid4(),
            tfl_id="940GZZLURSQ",
            name="Russell Square",
            latitude=51.5230,
            longitude=-0.1244,
            lines=["piccadilly"],
            last_updated=datetime.now(UTC),
        )
        station3 = Station(
            id=uuid4(),
            tfl_id="940GZZLUHBN",
            name="Holborn",
            latitude=51.5174,
            longitude=-0.1200,
            lines=["piccadilly"],
            last_updated=datetime.now(UTC),
        )

        # Create mock segments
        route_id = uuid4()
        segment1 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=station1.id,
            line_id=line.id,
        )
        segment1.line = line
        segment1.station = station1

        segment2 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=1,
            station_id=station2.id,
            line_id=line.id,
        )
        segment2.line = line
        segment2.station = station2

        segment3 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=2,
            station_id=station3.id,
            line_id=line.id,
        )
        segment3.line = line
        segment3.station = station3

        # Only segment2 is affected
        matched_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_segments([segment1, segment2, segment3], matched_pairs)

        assert result == [1]

    def test_calculate_affected_segments_multiple(self) -> None:
        """Test calculating multiple affected segments."""
        line = Line(
            id=uuid4(),
            tfl_id="piccadilly",
            name="Piccadilly",
            mode="tube",
            last_updated=datetime.now(UTC),
        )
        station1 = Station(
            id=uuid4(),
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["piccadilly"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            id=uuid4(),
            tfl_id="940GZZLURSQ",
            name="Russell Square",
            latitude=51.5230,
            longitude=-0.1244,
            lines=["piccadilly"],
            last_updated=datetime.now(UTC),
        )

        route_id = uuid4()
        segment1 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=station1.id,
            line_id=line.id,
        )
        segment1.line = line
        segment1.station = station1

        segment2 = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=1,
            station_id=station2.id,
            line_id=line.id,
        )
        segment2.line = line
        segment2.station = station2

        # Both segments affected
        matched_pairs = {("piccadilly", "940GZZLUKSX"), ("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_segments([segment1, segment2], matched_pairs)

        assert result == [0, 1]

    def test_calculate_affected_segments_no_match(self) -> None:
        """Test with no matching segments."""
        line = Line(
            id=uuid4(),
            tfl_id="piccadilly",
            name="Piccadilly",
            mode="tube",
            last_updated=datetime.now(UTC),
        )
        station = Station(
            id=uuid4(),
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["piccadilly"],
            last_updated=datetime.now(UTC),
        )

        route_id = uuid4()
        segment = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=station.id,
            line_id=line.id,
        )
        segment.line = line
        segment.station = station

        # Different line
        matched_pairs = {("victoria", "940GZZLUKSX")}

        result = calculate_affected_segments([segment], matched_pairs)

        assert result == []

    def test_calculate_affected_segments_no_line(self) -> None:
        """Test segment without line (destination segment)."""
        station = Station(
            id=uuid4(),
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["piccadilly"],
            last_updated=datetime.now(UTC),
        )

        route_id = uuid4()
        segment = UserRouteSegment(
            id=uuid4(),
            route_id=route_id,
            sequence=0,
            station_id=station.id,
            line_id=None,
        )
        segment.line = None  # type: ignore[assignment]
        segment.station = station

        matched_pairs = {("piccadilly", "940GZZLUKSX")}

        result = calculate_affected_segments([segment], matched_pairs)

        # Destination segments (no line) should not be included
        assert result == []

    def test_calculate_affected_stations(self) -> None:
        """Test calculating affected station NaPTANs."""
        route_pairs = {("piccadilly", "940GZZLUKSX"), ("piccadilly", "940GZZLURSQ")}
        disruption_pairs = {("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLUHBN")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        # Only Russell Square is in both sets
        assert result == ["940GZZLURSQ"]

    def test_calculate_affected_stations_multiple(self) -> None:
        """Test with multiple affected stations."""
        route_pairs = {
            ("piccadilly", "940GZZLUKSX"),
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLUHBN"),
        }
        disruption_pairs = {("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLUHBN")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        # Should be sorted
        assert result == ["940GZZLUHBN", "940GZZLURSQ"]

    def test_calculate_affected_stations_no_match(self) -> None:
        """Test with no matching stations."""
        route_pairs = {("piccadilly", "940GZZLUKSX")}
        disruption_pairs = {("victoria", "940GZZLUVIC")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == []

    def test_calculate_affected_stations_empty_route(self) -> None:
        """Test with empty route pairs."""
        route_pairs: set[tuple[str, str]] = set()
        disruption_pairs = {("piccadilly", "940GZZLURSQ")}

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == []

    def test_calculate_affected_stations_empty_disruption(self) -> None:
        """Test with empty disruption pairs."""
        route_pairs = {("piccadilly", "940GZZLURSQ")}
        disruption_pairs: set[tuple[str, str]] = set()

        result = calculate_affected_stations(route_pairs, disruption_pairs)

        assert result == []


# ==================== Test DisruptionMatchingService ====================


class TestDisruptionMatchingService:
    """Test DisruptionMatchingService."""

    @pytest.mark.asyncio
    async def test_get_route_index_pairs(self, db_session: AsyncSession) -> None:
        """Test getting route index pairs from database."""
        # Create test user
        user = User(external_id="test-user-1", auth_provider="auth0")
        db_session.add(user)
        await db_session.flush()

        # Create test data
        route = UserRoute(
            user_id=user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Add index entries
        index1 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLUKSX",
            line_data_version=datetime.now(UTC),
        )
        index2 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLURSQ",
            line_data_version=datetime.now(UTC),
        )
        db_session.add_all([index1, index2])
        await db_session.commit()

        # Test
        service = DisruptionMatchingService(db=db_session)
        pairs = await service.get_route_index_pairs(route.id)

        assert len(pairs) == 2
        assert ("piccadilly", "940GZZLUKSX") in pairs
        assert ("piccadilly", "940GZZLURSQ") in pairs

    @pytest.mark.asyncio
    async def test_get_route_index_pairs_empty(self, db_session: AsyncSession) -> None:
        """Test with route that has no index entries."""
        # Create test user
        user = User(external_id="test-user-2", auth_provider="auth0")
        db_session.add(user)
        await db_session.flush()

        route = UserRoute(
            user_id=user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        service = DisruptionMatchingService(db=db_session)
        pairs = await service.get_route_index_pairs(route.id)

        assert len(pairs) == 0

    @pytest.mark.asyncio
    async def test_get_route_index_pairs_ignores_soft_deleted(self, db_session: AsyncSession) -> None:
        """Test that soft-deleted index entries are ignored."""
        # Create test user
        user = User(external_id="test-user-3", auth_provider="auth0")
        db_session.add(user)
        await db_session.flush()

        route = UserRoute(
            user_id=user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Add active index entry
        index1 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLUKSX",
            line_data_version=datetime.now(UTC),
        )
        # Add soft-deleted index entry
        index2 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLURSQ",
            line_data_version=datetime.now(UTC),
            deleted_at=datetime.now(UTC),
        )
        db_session.add_all([index1, index2])
        await db_session.commit()

        service = DisruptionMatchingService(db=db_session)
        pairs = await service.get_route_index_pairs(route.id)

        # Should only return the active entry
        assert len(pairs) == 1
        assert ("piccadilly", "940GZZLUKSX") in pairs
        assert ("piccadilly", "940GZZLURSQ") not in pairs

    @pytest.mark.asyncio
    async def test_filter_alertable_disruptions(self, db_session: AsyncSession) -> None:
        """Test filtering by disabled severities."""
        # Add disabled severity to database (use unique values for test isolation)
        disabled = AlertDisabledSeverity(mode_id="test-mode-1", severity_level=10)
        db_session.add(disabled)
        await db_session.commit()

        # Create disruptions
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="test-mode-1",
                status_severity=10,
                status_severity_description="Good Service",
            ),
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="test-mode-1",
                status_severity=9,
                status_severity_description="Minor Delays",
            ),
        ]

        # Test
        service = DisruptionMatchingService(db=db_session)
        result = await service.filter_alertable_disruptions(disruptions)

        # Should only return the one with severity 9 (not disabled)
        assert len(result) == 1
        assert result[0].line_id == "piccadilly"

    @pytest.mark.asyncio
    async def test_filter_alertable_disruptions_multiple_modes(self, db_session: AsyncSession) -> None:
        """Test filtering with multiple modes."""
        # Add disabled severities (use unique values for test isolation)
        disabled1 = AlertDisabledSeverity(mode_id="test-mode-2", severity_level=10)
        disabled2 = AlertDisabledSeverity(mode_id="test-mode-3", severity_level=10)
        db_session.add_all([disabled1, disabled2])
        await db_session.commit()

        # Create disruptions
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="test-mode-2",
                status_severity=10,
                status_severity_description="Good Service",
            ),
            DisruptionResponse(
                line_id="dlr",
                line_name="DLR",
                mode="test-mode-3",
                status_severity=10,
                status_severity_description="Good Service",
            ),
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="test-mode-2",
                status_severity=9,
                status_severity_description="Minor Delays",
            ),
        ]

        service = DisruptionMatchingService(db=db_session)
        result = await service.filter_alertable_disruptions(disruptions)

        # Should only return the one with severity 9
        assert len(result) == 1
        assert result[0].line_id == "piccadilly"

    @pytest.mark.asyncio
    async def test_filter_alertable_disruptions_empty_list(self, db_session: AsyncSession) -> None:
        """Test filtering empty disruption list."""
        service = DisruptionMatchingService(db=db_session)
        result = await service.filter_alertable_disruptions([])

        assert result == []

    @pytest.mark.asyncio
    async def test_filter_alertable_disruptions_no_disabled(self, db_session: AsyncSession) -> None:
        """Test with no disabled severities configured."""
        # Use a unique mode that has no disabled severities
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="test-mode-unique",
                status_severity=10,
                status_severity_description="Good Service",
            ),
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="test-mode-unique",
                status_severity=9,
                status_severity_description="Minor Delays",
            ),
        ]

        service = DisruptionMatchingService(db=db_session)
        result = await service.filter_alertable_disruptions(disruptions)

        # All disruptions should be returned
        assert len(result) == 2

    def test_match_disruptions_to_route_with_match(self) -> None:
        """Test matching disruptions to route."""
        route_pairs = {("piccadilly", "940GZZLUKSX"), ("piccadilly", "940GZZLURSQ")}
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Test Route",
                        direction="outbound",
                        affected_stations=["940GZZLURSQ"],
                    )
                ],
            ),
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Test Route",
                        direction="outbound",
                        affected_stations=["940GZZLUVIC"],
                    )
                ],
            ),
        ]

        service = DisruptionMatchingService(db=None)  # type: ignore[arg-type]
        result = service.match_disruptions_to_route(route_pairs, disruptions)

        # Should only match the Piccadilly disruption
        assert len(result) == 1
        assert result[0].line_id == "piccadilly"

    def test_match_disruptions_to_route_no_match(self) -> None:
        """Test with no matching disruptions."""
        route_pairs = {("piccadilly", "940GZZLUKSX")}
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Test Route",
                        direction="outbound",
                        affected_stations=["940GZZLUVIC"],
                    )
                ],
            )
        ]

        service = DisruptionMatchingService(db=None)  # type: ignore[arg-type]
        result = service.match_disruptions_to_route(route_pairs, disruptions)

        assert len(result) == 0

    def test_match_disruptions_to_route_empty_route(self) -> None:
        """Test with empty route pairs."""
        route_pairs: set[tuple[str, str]] = set()
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Test Route",
                        direction="outbound",
                        affected_stations=["940GZZLURSQ"],
                    )
                ],
            )
        ]

        service = DisruptionMatchingService(db=None)  # type: ignore[arg-type]
        result = service.match_disruptions_to_route(route_pairs, disruptions)

        assert len(result) == 0

    def test_match_disruptions_to_route_no_affected_routes(self) -> None:
        """Test with disruption that has no affected_routes."""
        route_pairs = {("piccadilly", "940GZZLUKSX")}
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                affected_routes=None,
            )
        ]

        service = DisruptionMatchingService(db=None)  # type: ignore[arg-type]
        result = service.match_disruptions_to_route(route_pairs, disruptions)

        # Should not match because no station-level data
        assert len(result) == 0

    def test_match_disruptions_to_route_multiple_matches(self) -> None:
        """Test matching multiple disruptions."""
        route_pairs = {("piccadilly", "940GZZLUKSX"), ("victoria", "940GZZLUVIC")}
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Test Route",
                        direction="outbound",
                        affected_stations=["940GZZLUKSX"],
                    )
                ],
            ),
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=8,
                status_severity_description="Severe Delays",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Test Route",
                        direction="outbound",
                        affected_stations=["940GZZLUVIC"],
                    )
                ],
            ),
        ]

        service = DisruptionMatchingService(db=None)  # type: ignore[arg-type]
        result = service.match_disruptions_to_route(route_pairs, disruptions)

        # Both should match
        assert len(result) == 2
        assert {d.line_id for d in result} == {"piccadilly", "victoria"}
