"""Tests for soft delete helper functions."""

from datetime import UTC, datetime, time

import pytest
from app.helpers.soft_delete_filters import (
    add_active_filter,
    add_active_filters,
    get_active_children_for_parents,
    is_soft_deleted,
    soft_delete,
)
from app.models.user import User
from app.models.user_route import UserRoute, UserRouteSchedule, UserRouteSegment
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.soft_delete_assertions import (
    assert_api_returns_404,
    assert_cascade_soft_deleted,
    assert_not_in_api_list,
    assert_not_soft_deleted,
    assert_soft_deleted,
)
from tests.helpers.types import RailwayNetworkFixture


class TestSoftDeleteFilters:
    """Test soft delete filtering helpers."""

    async def test_add_active_filter_excludes_deleted(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test add_active_filter excludes soft-deleted entities."""
        # Create two routes: one active, one deleted
        active_route = UserRoute(
            user_id=test_user.id,
            name="Active Route",
            timezone="Europe/London",
        )
        deleted_route = UserRoute(
            user_id=test_user.id,
            name="Deleted Route",
            timezone="Europe/London",
            deleted_at=datetime.now(UTC),
        )

        db_session.add_all([active_route, deleted_route])
        await db_session.commit()

        # Query without filter - should return both
        query_all = select(UserRoute).where(UserRoute.user_id == test_user.id)
        result_all = await db_session.execute(query_all)
        all_routes = result_all.scalars().all()
        assert len(all_routes) == 2

        # Query with active filter - should return only active
        query_active = select(UserRoute).where(UserRoute.user_id == test_user.id)
        query_active = add_active_filter(query_active, UserRoute)
        result_active = await db_session.execute(query_active)
        active_routes = result_active.scalars().all()

        assert len(active_routes) == 1
        assert active_routes[0].id == active_route.id

    async def test_add_active_filters_multiple_models(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test add_active_filters with multiple joined models."""
        # Get a station and line from the test network
        station = next(iter(test_railway_network.stations.values()))
        line = next(iter(test_railway_network.lines.values()))

        # Create route with deleted segment
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        active_segment = UserRouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station.id,
            line_id=line.id,
        )
        deleted_segment = UserRouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station.id,
            line_id=line.id,
            deleted_at=datetime.now(UTC),
        )
        db_session.add_all([active_segment, deleted_segment])
        await db_session.commit()

        # Query with filters for both models
        query = select(UserRouteSegment).join(UserRoute).where(UserRoute.user_id == test_user.id)
        query = add_active_filters(query, UserRouteSegment, UserRoute)

        result = await db_session.execute(query)
        segments = result.scalars().all()

        # Should only return active segment
        assert len(segments) == 1
        assert segments[0].id == active_segment.id

    async def test_soft_delete_sets_deleted_at(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test soft_delete helper sets deleted_at timestamp."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        # Verify not deleted initially
        assert route.deleted_at is None

        # Soft delete using helper
        await soft_delete(db_session, UserRoute, UserRoute.id == route.id)
        await db_session.commit()
        await db_session.refresh(route)

        # Verify deleted
        assert route.deleted_at is not None
        assert isinstance(route.deleted_at, datetime)

    async def test_soft_delete_only_affects_active_records(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test soft_delete doesn't update already-deleted records."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            timezone="Europe/London",
            deleted_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db_session.add(route)
        await db_session.commit()

        original_deleted_at = route.deleted_at

        # Try to soft delete again
        await soft_delete(db_session, UserRoute, UserRoute.id == route.id)
        await db_session.commit()
        await db_session.refresh(route)

        # deleted_at should remain unchanged
        assert route.deleted_at == original_deleted_at

    async def test_soft_delete_with_multiple_conditions(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test soft_delete with multiple WHERE conditions."""
        route1 = UserRoute(
            user_id=test_user.id,
            name="Route 1",
            timezone="Europe/London",
        )
        route2 = UserRoute(
            user_id=test_user.id,
            name="Route 2",
            timezone="Europe/London",
        )
        db_session.add_all([route1, route2])
        await db_session.commit()

        # Soft delete only route1
        await soft_delete(
            db_session,
            UserRoute,
            UserRoute.user_id == test_user.id,
            UserRoute.name == "Route 1",
        )
        await db_session.commit()
        await db_session.refresh(route1)
        await db_session.refresh(route2)

        # Only route1 should be deleted
        assert route1.deleted_at is not None
        assert route2.deleted_at is None

    async def test_soft_delete_requires_where_clause(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test soft_delete raises ValueError if no where_clauses provided."""
        # Attempt to soft delete without any where clauses
        with pytest.raises(
            ValueError,
            match="soft_delete requires at least one WHERE clause to prevent accidental mass deletion",
        ):
            await soft_delete(db_session, UserRoute)

    def test_is_soft_deleted_returns_true_for_deleted(
        self,
        test_user: User,
    ) -> None:
        """Test is_soft_deleted returns True for deleted entity."""
        route = UserRoute(
            user_id=test_user.id,
            name="Deleted Route",
            timezone="Europe/London",
            deleted_at=datetime.now(UTC),
        )

        assert is_soft_deleted(route) is True

    def test_is_soft_deleted_returns_false_for_active(
        self,
        test_user: User,
    ) -> None:
        """Test is_soft_deleted returns False for active entity."""
        route = UserRoute(
            user_id=test_user.id,
            name="Active Route",
            timezone="Europe/London",
        )

        assert is_soft_deleted(route) is False

    async def test_get_active_children_for_parents_returns_empty_dict_for_empty_parent_list(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test get_active_children_for_parents returns empty dict when no parent_ids provided."""
        result = await get_active_children_for_parents(
            db_session,
            UserRouteSchedule,
            UserRouteSchedule.route_id,
            [],
        )

        assert result == {}

    async def test_get_active_children_for_parents_loads_only_active_children(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test get_active_children_for_parents filters out soft-deleted children."""
        # Create route
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        # Create active and deleted schedules
        active_schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        deleted_schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["TUE"],
            start_time=time(10, 0),
            end_time=time(11, 0),
            deleted_at=datetime.now(UTC),
        )
        db_session.add_all([active_schedule, deleted_schedule])
        await db_session.commit()

        # Load children
        result = await get_active_children_for_parents(
            db_session,
            UserRouteSchedule,
            UserRouteSchedule.route_id,
            [route.id],
        )

        # Should only return active schedule
        assert route.id in result
        assert len(result[route.id]) == 1
        assert result[route.id][0].id == active_schedule.id

    async def test_get_active_children_for_parents_groups_by_parent_id(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test get_active_children_for_parents correctly groups children by parent."""
        # Create two routes
        route1 = UserRoute(
            user_id=test_user.id,
            name="Route 1",
            timezone="Europe/London",
        )
        route2 = UserRoute(
            user_id=test_user.id,
            name="Route 2",
            timezone="Europe/London",
        )
        db_session.add_all([route1, route2])
        await db_session.commit()

        # Create schedules for each route
        schedule1a = UserRouteSchedule(
            route_id=route1.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        schedule1b = UserRouteSchedule(
            route_id=route1.id,
            days_of_week=["TUE"],
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        schedule2 = UserRouteSchedule(
            route_id=route2.id,
            days_of_week=["WED"],
            start_time=time(12, 0),
            end_time=time(13, 0),
        )
        db_session.add_all([schedule1a, schedule1b, schedule2])
        await db_session.commit()

        # Load children
        result = await get_active_children_for_parents(
            db_session,
            UserRouteSchedule,
            UserRouteSchedule.route_id,
            [route1.id, route2.id],
        )

        # Verify grouping
        assert len(result) == 2
        assert len(result[route1.id]) == 2
        assert len(result[route2.id]) == 1
        assert {s.id for s in result[route1.id]} == {schedule1a.id, schedule1b.id}
        assert result[route2.id][0].id == schedule2.id

    async def test_get_active_children_for_parents_returns_empty_list_for_parent_with_no_children(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test get_active_children_for_parents returns empty list for parent with no children."""
        # Create route with no schedules
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        # Load children
        result = await get_active_children_for_parents(
            db_session,
            UserRouteSchedule,
            UserRouteSchedule.route_id,
            [route.id],
        )

        # Should return empty list for this route
        assert route.id in result
        assert result[route.id] == []

    async def test_get_active_children_for_parents_with_segments(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test get_active_children_for_parents works with different child models."""
        # Get stations and line from test network
        stations = list(test_railway_network.stations.values())
        line = next(iter(test_railway_network.lines.values()))

        # Create route
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        # Create active and deleted segments
        active_segment = UserRouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=stations[0].id,
            line_id=line.id,
        )
        deleted_segment = UserRouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=stations[1].id,
            line_id=line.id,
            deleted_at=datetime.now(UTC),
        )
        db_session.add_all([active_segment, deleted_segment])
        await db_session.commit()

        # Load children
        result = await get_active_children_for_parents(
            db_session,
            UserRouteSegment,
            UserRouteSegment.route_id,
            [route.id],
        )

        # Should only return active segment
        assert route.id in result
        assert len(result[route.id]) == 1
        assert result[route.id][0].id == active_segment.id


class TestSoftDeleteAssertions:
    """Test soft delete assertion helpers."""

    async def test_assert_soft_deleted_passes_for_deleted_entity(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test assert_soft_deleted passes for deleted entity."""
        route = UserRoute(
            user_id=test_user.id,
            name="Deleted Route",
            timezone="Europe/London",
            deleted_at=datetime.now(UTC),
        )
        db_session.add(route)
        await db_session.commit()

        # Should not raise
        await assert_soft_deleted(db_session, UserRoute, route.id)

    async def test_assert_soft_deleted_fails_for_active_entity(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test assert_soft_deleted raises for active entity."""
        route = UserRoute(
            user_id=test_user.id,
            name="Active Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        # Should raise AssertionError
        with pytest.raises(AssertionError, match="should be soft deleted"):
            await assert_soft_deleted(db_session, UserRoute, route.id)

    async def test_assert_not_soft_deleted_passes_for_active_entity(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test assert_not_soft_deleted passes for active entity."""
        route = UserRoute(
            user_id=test_user.id,
            name="Active Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        # Should not raise
        await assert_not_soft_deleted(db_session, UserRoute, route.id)

    async def test_assert_not_soft_deleted_fails_for_deleted_entity(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test assert_not_soft_deleted raises for deleted entity."""
        route = UserRoute(
            user_id=test_user.id,
            name="Deleted Route",
            timezone="Europe/London",
            deleted_at=datetime.now(UTC),
        )
        db_session.add(route)
        await db_session.commit()

        # Should raise AssertionError
        with pytest.raises(AssertionError, match="should NOT be soft deleted"):
            await assert_not_soft_deleted(db_session, UserRoute, route.id)

    async def test_assert_cascade_soft_deleted_verifies_all_relations(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test assert_cascade_soft_deleted verifies cascade deletion."""
        # Get a station and line from the test network
        station = next(iter(test_railway_network.stations.values()))
        line = next(iter(test_railway_network.lines.values()))

        # Create route with related entities
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        segment = UserRouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station.id,
            line_id=line.id,
        )
        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        db_session.add_all([segment, schedule])
        await db_session.commit()

        # Soft delete all
        segment.deleted_at = datetime.now(UTC)
        schedule.deleted_at = datetime.now(UTC)
        await db_session.commit()

        # Should not raise
        await assert_cascade_soft_deleted(
            db_session,
            route.id,
            {
                UserRouteSegment: UserRouteSegment.route_id,
                UserRouteSchedule: UserRouteSchedule.route_id,
            },
        )

    async def test_assert_cascade_soft_deleted_fails_if_not_cascaded(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test assert_cascade_soft_deleted raises if cascade incomplete."""
        # Get a station and line from the test network
        station = next(iter(test_railway_network.stations.values()))
        line = next(iter(test_railway_network.lines.values()))

        # Create route with segment
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()

        segment = UserRouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station.id,
            line_id=line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        # Segment is NOT deleted
        # Should raise AssertionError
        with pytest.raises(AssertionError, match="should be soft deleted"):
            await assert_cascade_soft_deleted(
                db_session,
                route.id,
                {UserRouteSegment: UserRouteSegment.route_id},
            )

    async def test_assert_not_in_api_list(
        self,
        async_client_with_db: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test assert_not_in_api_list helper."""
        # Create two routes: one active, one deleted
        active_route = UserRoute(
            user_id=test_user.id,
            name="Active Route",
            timezone="Europe/London",
        )
        deleted_route = UserRoute(
            user_id=test_user.id,
            name="Deleted Route",
            timezone="Europe/London",
            deleted_at=datetime.now(UTC),
        )
        db_session.add_all([active_route, deleted_route])
        await db_session.commit()

        # Deleted route should not appear in list
        await assert_not_in_api_list(
            async_client_with_db,
            "/api/v1/routes",
            deleted_route.id,
            auth_headers_for_user,
        )

    async def test_assert_api_returns_404(
        self,
        async_client_with_db: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test assert_api_returns_404 helper."""
        # Create deleted route
        deleted_route = UserRoute(
            user_id=test_user.id,
            name="Deleted Route",
            timezone="Europe/London",
            deleted_at=datetime.now(UTC),
        )
        db_session.add(deleted_route)
        await db_session.commit()

        # Should return 404
        await assert_api_returns_404(
            async_client_with_db,
            f"/api/v1/routes/{deleted_route.id}",
            auth_headers_for_user,
        )
