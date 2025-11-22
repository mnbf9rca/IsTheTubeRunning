"""Tests for DisruptionMatchingService."""

from datetime import UTC, datetime

import pytest
from app.models.tfl import AlertDisabledSeverity
from app.models.user import User
from app.models.user_route import UserRoute
from app.models.user_route_index import UserRouteStationIndex
from app.schemas.tfl import AffectedRouteInfo, DisruptionResponse
from app.services.disruption_matching_service import DisruptionMatchingService
from sqlalchemy.ext.asyncio import AsyncSession

# NOTE: Pure helper function tests (extract_line_station_pairs, disruption_affects_route,
# calculate_affected_segments, calculate_affected_stations) are in tests/helpers/test_disruption_helpers.py
# This file contains only DisruptionMatchingService-specific tests (database operations, service methods)

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
