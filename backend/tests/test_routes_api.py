"""Tests for routes API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, patch

import pytest
from app.core.database import get_db
from app.main import app
from app.models.notification import (
    NotificationLog,
    NotificationMethod,
    NotificationPreference,
    NotificationStatus,
)
from app.models.tfl import Line, Station
from app.models.user import EmailAddress, User
from app.models.user_route import UserRoute, UserRouteSchedule, UserRouteSegment
from app.models.user_route_index import UserRouteStationIndex
from fastapi import HTTPException, status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.railway_network import create_test_station
from tests.helpers.soft_delete_assertions import (
    assert_api_returns_404,
    assert_cascade_soft_deleted,
    assert_not_in_api_list,
    assert_soft_deleted,
)
from tests.helpers.types import RailwayNetworkFixture


class TestRoutesAPI:
    """Test cases for routes API endpoints."""

    @pytest.fixture(autouse=True)
    async def setup_test(self, db_session: AsyncSession) -> AsyncGenerator[None]:
        """Set up test database dependency override."""

        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    async def test_station1(self, db_session: AsyncSession) -> Station:
        """Create a test station."""
        station = create_test_station(
            tfl_id="test-station-1",
            name="Test Station 1",
            lines=["test-line-1", "test-line-2"],
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)
        return station

    @pytest.fixture
    async def test_station2(self, db_session: AsyncSession) -> Station:
        """Create a second test station."""
        station = create_test_station(
            tfl_id="test-station-2",
            name="Test Station 2",
            lines=["test-line-1", "test-line-3"],
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)
        return station

    @pytest.fixture
    async def test_station3(self, db_session: AsyncSession) -> Station:
        """Create a third test station."""
        station = create_test_station(
            tfl_id="test-station-3",
            name="Test Station 3",
            lines=["test-line-1", "test-line-4"],
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)
        return station

    @pytest.fixture
    async def test_line(self, db_session: AsyncSession) -> Line:
        """Create a test line."""
        line = Line(
            tfl_id="central",
            name="Central",
            last_updated=datetime.now(UTC),
        )
        db_session.add(line)
        await db_session.commit()
        await db_session.refresh(line)
        return line

    # ==================== Route CRUD Tests ====================

    @pytest.mark.asyncio
    async def test_create_route_success(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
    ) -> None:
        """Test successfully creating a route."""
        response = await async_client.post(
            "/api/v1/routes",
            json={
                "name": "Home to Work",
                "description": "My daily commute",
                "active": True,
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Home to Work"
        assert data["description"] == "My daily commute"
        assert data["active"] is True
        assert data["segments"] == []
        assert data["schedules"] == []

    @pytest.mark.asyncio
    async def test_create_route_minimal(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test creating a route with minimal fields."""
        response = await async_client.post(
            "/api/v1/routes",
            json={"name": "Test Route"},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test Route"
        assert data["description"] is None
        assert data["active"] is True  # Default value

    @pytest.mark.asyncio
    async def test_create_route_requires_auth(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that route creation requires authentication."""
        response = await async_client.post(
            "/api/v1/routes",
            json={"name": "Test Route"},
        )

        # Auth middleware returns 403 when no token is provided in DEBUG mode
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_list_routes(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test listing all routes for a user."""
        # Create test routes
        route1 = UserRoute(user_id=test_user.id, name="Route 1", active=True, timezone="Europe/London")
        route2 = UserRoute(user_id=test_user.id, name="Route 2", active=False, timezone="Europe/London")
        db_session.add_all([route1, route2])
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/routes",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        # Check that both active and inactive routes are returned
        names = {r["name"] for r in data}
        assert names == {"Route 1", "Route 2"}

    @pytest.mark.asyncio
    async def test_list_routes_empty(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test listing routes when user has none."""
        response = await async_client.get(
            "/api/v1/routes",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_routes_isolation(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        another_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that users can only see their own routes."""
        route1 = UserRoute(user_id=test_user.id, name="My Route", active=True)
        route2 = UserRoute(user_id=another_user.id, name="Other Route", active=True)
        db_session.add_all([route1, route2])
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/routes",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "My Route"

    @pytest.mark.asyncio
    async def test_get_route(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test getting a single route by ID."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            description="Test description",
            active=True,
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.get(
            f"/api/v1/routes/{route.id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(route.id)
        assert data["name"] == "Test Route"
        assert data["description"] == "Test description"

    @pytest.mark.asyncio
    async def test_get_route_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test getting a non-existent route returns 404."""
        fake_id = uuid.uuid4()
        response = await async_client.get(
            f"/api/v1/routes/{fake_id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_route_wrong_owner(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        another_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that users cannot access other users' routes."""
        route = UserRoute(user_id=another_user.id, name="Other Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.get(
            f"/api/v1/routes/{route.id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_route(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating a route."""
        route = UserRoute(user_id=test_user.id, name="Old Name", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}",
            json={
                "name": "New Name",
                "description": "Updated description",
                "active": False,
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "Updated description"
        assert data["active"] is False

    @pytest.mark.asyncio
    async def test_update_route_partial(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test partial update of a route."""
        route = UserRoute(
            user_id=test_user.id,
            name="Old Name",
            description="Old description",
            active=True,
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}",
            json={"name": "New Name"},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "Old description"  # Unchanged
        assert data["active"] is True  # Unchanged

    @pytest.mark.asyncio
    async def test_delete_route(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting a route and verifying cascade soft delete behavior (Issue #233)."""
        # Create route with full related entities
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        # Add segments
        segment1 = UserRouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        segment2 = UserRouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=test_station2.id,
            line_id=test_line.id,
        )
        db_session.add_all([segment1, segment2])
        await db_session.flush()

        # Add schedule
        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON", "TUE"],
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        await db_session.flush()

        # Add station index
        station_index = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id=test_line.tfl_id,
            station_naptan=test_station1.tfl_id,
            line_data_version=test_line.last_updated,
        )
        db_session.add(station_index)
        await db_session.flush()

        # Add email address for notification preference
        email = EmailAddress(
            user_id=test_user.id,
            email="test@example.com",
            verified=True,
            is_primary=True,
        )
        db_session.add(email)
        await db_session.flush()

        # Add notification preference
        notification_pref = NotificationPreference(
            route_id=route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=email.id,
        )
        db_session.add(notification_pref)
        await db_session.flush()

        # Add notification log (should NOT be deleted)
        notification_log = NotificationLog(
            user_id=test_user.id,
            route_id=route.id,
            method=NotificationMethod.EMAIL,
            status=NotificationStatus.SENT,
            sent_at=datetime.now(UTC),
        )
        db_session.add(notification_log)
        await db_session.commit()

        route_id = route.id
        notification_log_id = notification_log.id

        # Delete the route
        response = await async_client.delete(
            f"/api/v1/routes/{route_id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify route was soft deleted
        await assert_soft_deleted(db_session, UserRoute, route_id)

        # Verify ALL related entities are cascaded soft deleted
        await assert_cascade_soft_deleted(
            db_session,
            route_id,
            {
                UserRouteSegment: UserRouteSegment.route_id,
                UserRouteSchedule: UserRouteSchedule.route_id,
                UserRouteStationIndex: UserRouteStationIndex.route_id,
                NotificationPreference: NotificationPreference.route_id,
            },
        )

        # Verify NotificationLog is NOT deleted (intentional exception per Issue #233)
        result = await db_session.execute(select(NotificationLog).where(NotificationLog.id == notification_log_id))
        log = result.scalar_one_or_none()
        assert log is not None, "NotificationLog should exist"
        assert log.deleted_at is None, "NotificationLog should NOT be soft deleted"

    @pytest.mark.asyncio
    async def test_deleted_route_not_in_list(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that deleted routes do not appear in GET /routes list (Issue #233)."""
        # Create and delete a route
        route = UserRoute(user_id=test_user.id, name="To Be Deleted", active=True)
        db_session.add(route)
        await db_session.commit()
        route_id = route.id

        # Delete the route
        response = await async_client.delete(
            f"/api/v1/routes/{route_id}",
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deleted route doesn't appear in list
        await assert_not_in_api_list(
            async_client,
            "/api/v1/routes",
            route_id,
            auth_headers_for_user,
        )

    @pytest.mark.asyncio
    async def test_deleted_route_returns_404(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that GET /routes/{id} returns 404 for deleted route (Issue #233)."""
        # Create and delete a route
        route = UserRoute(user_id=test_user.id, name="To Be Deleted", active=True)
        db_session.add(route)
        await db_session.commit()
        route_id = route.id

        # Delete the route
        response = await async_client.delete(
            f"/api/v1/routes/{route_id}",
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify GET by ID returns 404
        await assert_api_returns_404(
            async_client,
            f"/api/v1/routes/{route_id}",
            auth_headers_for_user,
        )

    @pytest.mark.asyncio
    async def test_delete_already_deleted_route_returns_404(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that deleting an already-deleted route returns 404 (Issue #233)."""
        # Create and delete a route
        route = UserRoute(user_id=test_user.id, name="To Be Deleted", active=True)
        db_session.add(route)
        await db_session.commit()
        route_id = route.id

        # Delete the route (first time)
        response = await async_client.delete(
            f"/api/v1/routes/{route_id}",
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Try to delete again (should return 404)
        response = await async_client.delete(
            f"/api/v1/routes/{route_id}",
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ==================== Timezone Tests ====================

    @pytest.mark.asyncio
    async def test_create_route_with_custom_timezone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test creating a route with a custom timezone."""
        response = await async_client.post(
            "/api/v1/routes",
            json={
                "name": "NYC Route",
                "timezone": "America/New_York",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_create_route_default_timezone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test creating a route without timezone defaults to Europe/London."""
        response = await async_client.post(
            "/api/v1/routes",
            json={"name": "Test Route"},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["timezone"] == "Europe/London"

    @pytest.mark.asyncio
    async def test_create_route_invalid_timezone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test creating a route with invalid timezone fails validation."""
        response = await async_client.post(
            "/api/v1/routes",
            json={
                "name": "Test Route",
                "timezone": "Invalid/Timezone",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()
        assert "Invalid IANA timezone" in str(data)

    @pytest.mark.asyncio
    async def test_update_route_timezone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating a route's timezone."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}",
            json={"timezone": "Asia/Tokyo"},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["timezone"] == "Asia/Tokyo"

    @pytest.mark.asyncio
    async def test_update_route_invalid_timezone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating a route with invalid timezone fails validation."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}",
            json={"timezone": "Europe/Londan"},  # Typo
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()
        assert "Invalid IANA timezone" in str(data)

    @pytest.mark.asyncio
    async def test_get_route_includes_timezone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that getting a route returns timezone field."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/Paris",
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.get(
            f"/api/v1/routes/{route.id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["timezone"] == "Europe/Paris"

    @pytest.mark.asyncio
    async def test_list_routes_includes_timezone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that listing routes includes timezone field."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="UTC",
        )
        db_session.add(route)
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/routes",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["timezone"] == "UTC"

    @pytest.mark.asyncio
    async def test_update_route_timezone_to_none_preserves_existing(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that updating route with timezone=None preserves existing timezone."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Asia/Tokyo",
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        # Update with timezone=None (omitted) should preserve existing value
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}",
            json={"name": "Updated Name"},  # No timezone field
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["timezone"] == "Asia/Tokyo"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_route_timezone_explicit_none_preserves_existing(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that updating route with explicit timezone: null preserves existing timezone."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/Paris",
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        # Update with explicit None should preserve existing value (per UpdateUserRouteRequest logic)
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}",
            json={"name": "Updated Name", "timezone": None},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["timezone"] == "Europe/Paris"  # Unchanged

    # ==================== Segment Tests ====================

    @pytest.mark.asyncio
    @patch("app.services.user_route_service.UserRouteService._validate_segments")
    async def test_upsert_segments_success(
        self,
        mock_validate: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test successfully adding segments to a route."""
        # Mock validation to pass
        mock_validate.return_value = None

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json={
                "segments": [
                    {
                        "sequence": 0,
                        "station_tfl_id": test_station1.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                    {
                        "sequence": 1,
                        "station_tfl_id": test_station2.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["sequence"] == 0
        assert data[1]["sequence"] == 1

    @pytest.mark.asyncio
    @patch("app.services.user_route_service.UserRouteService._validate_segments")
    async def test_upsert_segments_validation_failure(
        self,
        mock_validate: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test that invalid segments are rejected."""
        # Mock validation to fail
        mock_validate.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route validation failed: No connection between stations",
        )

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json={
                "segments": [
                    {
                        "sequence": 0,
                        "station_tfl_id": test_station1.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                    {
                        "sequence": 1,
                        "station_tfl_id": test_station2.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "validation failed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upsert_segments_invalid_sequence(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test that non-consecutive sequences are rejected."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json={
                "segments": [
                    {
                        "sequence": 0,
                        "station_id": str(test_station1.id),
                        "line_id": str(test_line.id),
                    },
                    {
                        "sequence": 5,  # Gap in sequence
                        "station_id": str(test_station2.id),
                        "line_id": str(test_line.id),
                    },
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    @patch("app.services.user_route_service.UserRouteService._validate_route_segments")
    async def test_update_segment(
        self,
        mock_validate: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test updating a single segment."""
        # Mock validation to pass
        mock_validate.return_value = None

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segment = UserRouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"station_tfl_id": test_station2.tfl_id},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["station_tfl_id"] == test_station2.tfl_id

    @pytest.mark.asyncio
    async def test_delete_segment(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting a segment and resequencing."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        # Create 3 segments
        segments = [
            UserRouteSegment(
                route_id=route.id,
                sequence=i,
                station_id=test_station1.id if i % 2 == 0 else test_station2.id,
                line_id=test_line.id,
            )
            for i in range(3)
        ]
        db_session.add_all(segments)
        await db_session.commit()

        response = await async_client.delete(
            f"/api/v1/routes/{route.id}/segments/1",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify segment was soft deleted and others resequenced (Issue #233)
        result = await db_session.execute(
            select(UserRouteSegment)
            .where(
                UserRouteSegment.route_id == route.id,
                UserRouteSegment.deleted_at.is_(None),
            )
            .order_by(UserRouteSegment.sequence)
        )
        remaining = list(result.scalars().all())
        assert len(remaining) == 2
        assert remaining[0].sequence == 0
        assert remaining[1].sequence == 1

    @pytest.mark.asyncio
    async def test_delete_segment_minimum_constraint(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test that deletion is prevented if it would leave <2 segments."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        # Create exactly 2 segments (minimum)
        segments = [
            UserRouteSegment(
                route_id=route.id,
                sequence=i,
                station_id=test_station1.id if i == 0 else test_station2.id,
                line_id=test_line.id,
            )
            for i in range(2)
        ]
        db_session.add_all(segments)
        await db_session.commit()

        response = await async_client.delete(
            f"/api/v1/routes/{route.id}/segments/0",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "at least 2 segments" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.services.user_route_service.UserRouteService._validate_segments")
    async def test_upsert_segments_with_null_destination_line(
        self,
        mock_validate: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_station3: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test creating segments with NULL line_tfl_id for destination (valid case)."""
        # Mock validation to pass
        mock_validate.return_value = None

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json={
                "segments": [
                    {
                        "sequence": 0,
                        "station_tfl_id": test_station1.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                    {
                        "sequence": 1,
                        "station_tfl_id": test_station2.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                    {
                        "sequence": 2,
                        "station_tfl_id": test_station3.tfl_id,
                        "line_tfl_id": None,  # Destination has NULL line_tfl_id
                    },
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        assert data[0]["line_tfl_id"] == test_line.tfl_id
        assert data[1]["line_tfl_id"] == test_line.tfl_id
        assert data[2]["line_tfl_id"] is None  # Destination has no line

    # ==================== Schedule Tests ====================

    @pytest.mark.asyncio
    async def test_create_schedule(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test creating a schedule for a route."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.post(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "days_of_week": ["MON", "TUE", "WED", "THU", "FRI"],
                "start_time": "08:00:00",
                "end_time": "18:00:00",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["days_of_week"] == ["MON", "TUE", "WED", "THU", "FRI"]
        assert data["start_time"] == "08:00:00"
        assert data["end_time"] == "18:00:00"

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_days(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that invalid day codes are rejected."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.post(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "days_of_week": ["MONDAY", "TUESDAY"],  # Invalid format
                "start_time": "08:00:00",
                "end_time": "18:00:00",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_time_range(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that end_time must be after start_time."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.post(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "days_of_week": ["MON"],
                "start_time": "18:00:00",
                "end_time": "08:00:00",  # Before start_time
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_update_schedule_partial_time_validation(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test service-layer validation when partially updating time (only one field)."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)

        # Update only end_time to be before existing start_time
        # Schema validator can't catch this (only one time provided)
        # Service layer must validate against database values
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/schedules/{schedule.id}",
            json={"end_time": "07:00:00"},  # Before existing start_time (08:00)
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_update_schedule(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating a schedule."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON", "TUE"],
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/schedules/{schedule.id}",
            json={"days_of_week": ["MON", "TUE", "WED", "THU", "FRI"]},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["days_of_week"]) == 5

    @pytest.mark.asyncio
    async def test_delete_schedule(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting a schedule."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        await db_session.commit()
        schedule_id = schedule.id

        response = await async_client.delete(
            f"/api/v1/routes/{route.id}/schedules/{schedule_id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify soft deletion (Issue #233)
        result = await db_session.execute(select(UserRouteSchedule).where(UserRouteSchedule.id == schedule_id))
        deleted_schedule = result.scalar_one_or_none()
        assert deleted_schedule is not None
        assert deleted_schedule.deleted_at is not None

    @pytest.mark.asyncio
    async def test_schedule_ownership_validation(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        another_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that users cannot modify other users' schedules."""
        # Create route and schedule for another user
        route = UserRoute(user_id=another_user.id, name="Other Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        await db_session.commit()

        # Try to update it as test_user
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/schedules/{schedule.id}",
            json={"days_of_week": ["TUE"]},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ==================== Upsert Schedules Tests ====================

    @pytest.mark.asyncio
    async def test_upsert_schedules_replaces_all(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that upsert replaces all existing schedules."""
        # Create route with existing schedules
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        # Add existing schedule
        old_schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        db_session.add(old_schedule)
        await db_session.commit()
        old_schedule_id = old_schedule.id

        # Upsert with new schedules
        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "schedules": [
                    {"days_of_week": ["TUE", "WED"], "start_time": "10:00:00", "end_time": "11:00:00"},
                    {"days_of_week": ["THU"], "start_time": "14:00:00", "end_time": "15:00:00"},
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Verify old schedule was soft-deleted
        result = await db_session.execute(select(UserRouteSchedule).where(UserRouteSchedule.id == old_schedule_id))
        deleted_schedule = result.scalar_one()
        assert deleted_schedule.deleted_at is not None

    @pytest.mark.asyncio
    async def test_upsert_schedules_empty_array_deletes_all(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that empty array deletes all schedules."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        db_session.add(schedule)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={"schedules": []},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_upsert_schedules_validation_failure_rolls_back(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that validation failure on second schedule preserves original state."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        original_schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        db_session.add(original_schedule)
        await db_session.commit()
        await db_session.refresh(original_schedule)

        # Try to upsert with one valid and one invalid schedule
        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "schedules": [
                    {"days_of_week": ["TUE"], "start_time": "10:00:00", "end_time": "11:00:00"},
                    {"days_of_week": ["INVALID_DAY"], "start_time": "14:00:00", "end_time": "15:00:00"},
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Verify original schedule is still active (transaction rolled back)
        await db_session.refresh(original_schedule)
        assert original_schedule.deleted_at is None

    @pytest.mark.asyncio
    async def test_upsert_schedules_invalid_time_range(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that end_time <= start_time is rejected."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "schedules": [
                    {"days_of_week": ["MON"], "start_time": "18:00:00", "end_time": "08:00:00"},
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_upsert_schedules_route_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test 404 for non-existent route."""
        fake_route_id = str(uuid.uuid4())

        response = await async_client.put(
            f"/api/v1/routes/{fake_route_id}/schedules",
            json={"schedules": []},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_upsert_schedules_ownership_validation(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        another_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that users cannot modify other users' schedules."""
        route = UserRoute(user_id=another_user.id, name="Other User Route", active=True)
        db_session.add(route)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={"schedules": []},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_upsert_schedules_invalid_days(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that invalid day codes are rejected."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "schedules": [
                    {"days_of_week": ["MONDAY"], "start_time": "08:00:00", "end_time": "18:00:00"},
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_upsert_schedules_invalid_quarter_hour(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test that times not on quarter-hour boundaries are rejected."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()

        # Test with start_time not on quarter-hour
        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "schedules": [
                    {"days_of_week": ["MON"], "start_time": "08:17:00", "end_time": "09:00:00"},
                ]
            },
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "quarter-hour boundary" in response.json()["detail"][0]["msg"].lower()

        # Test with end_time not on quarter-hour
        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "schedules": [
                    {"days_of_week": ["MON"], "start_time": "08:00:00", "end_time": "09:07:00"},
                ]
            },
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "quarter-hour boundary" in response.json()["detail"][0]["msg"].lower()

        # Test with seconds (not on quarter-hour)
        response = await async_client.put(
            f"/api/v1/routes/{route.id}/schedules",
            json={
                "schedules": [
                    {"days_of_week": ["MON"], "start_time": "08:00:30", "end_time": "09:00:00"},
                ]
            },
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "quarter-hour boundary" in response.json()["detail"][0]["msg"].lower()

    # ==================== Additional Coverage Tests ====================

    @pytest.mark.asyncio
    async def test_update_segment_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test updating a non-existent segment."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        # Try to update segment that doesn't exist
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"station_tfl_id": test_station1.tfl_id},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_segment_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting a non-existent segment."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        # Add 3 segments so we can test deletion without hitting minimum constraint
        segments = [
            UserRouteSegment(
                route_id=route.id,
                sequence=i,
                station_id=test_station1.id if i % 2 == 0 else test_station2.id,
                line_id=test_line.id,
            )
            for i in range(3)
        ]
        db_session.add_all(segments)
        await db_session.commit()

        # Try to delete segment with non-existent sequence
        response = await async_client.delete(
            f"/api/v1/routes/{route.id}/segments/99",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_schedule_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating/deleting a non-existent schedule."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        fake_id = uuid.uuid4()

        # Try to update non-existent schedule
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/schedules/{fake_id}",
            json={"days_of_week": ["TUE"]},
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Try to delete non-existent schedule
        response = await async_client.delete(
            f"/api/v1/routes/{route.id}/schedules/{fake_id}",
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ==================== Additional Exception Path Tests ====================

    @pytest.mark.asyncio
    async def test_update_route_description(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating only the description field of a route."""
        route = UserRoute(
            user_id=test_user.id,
            name="Original Name",
            description="Original description",
            active=True,
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}",
            json={"description": "Updated description only"},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Original Name"  # Unchanged
        assert data["description"] == "Updated description only"
        assert data["active"] is True  # Unchanged

    @pytest.mark.asyncio
    @patch("app.services.user_route_service.UserRouteService._validate_route_segments")
    async def test_update_segment_line_id(
        self,
        mock_validate: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test updating only the line_id field of a segment."""
        # Mock validation to pass
        mock_validate.return_value = None

        # Create a second line for testing
        line2 = Line(
            tfl_id="victoria",
            name="Victoria",
            last_updated=datetime.now(UTC),
        )
        db_session.add(line2)
        await db_session.commit()
        await db_session.refresh(line2)

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segment = UserRouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"line_tfl_id": line2.tfl_id},  # Update only line_tfl_id
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["line_tfl_id"] == line2.tfl_id
        assert data["station_tfl_id"] == test_station1.tfl_id  # Unchanged

    @pytest.mark.asyncio
    async def test_update_schedule_start_time(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating only the start_time field of a schedule."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON"],
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/schedules/{schedule.id}",
            json={"start_time": "09:00:00"},  # Update only start_time
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["start_time"] == "09:00:00"
        assert data["end_time"] == "18:00:00"  # Unchanged
        assert data["days_of_week"] == ["MON"]  # Unchanged

    @pytest.mark.asyncio
    @patch("app.services.user_route_service.UserRouteService._validate_segments")
    async def test_upsert_segments_validation_with_index(
        self,
        mock_validate: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test validation failure with invalid_index in error message."""
        # Mock validation to fail with an index
        mock_validate.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route validation failed: Station not on line (segment index: 1)",
        )

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json={
                "segments": [
                    {
                        "sequence": 0,
                        "station_tfl_id": test_station1.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                    {
                        "sequence": 1,
                        "station_tfl_id": test_station2.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"]
        assert "validation failed" in detail.lower()
        assert "segment index: 1" in detail.lower()

    @pytest.mark.asyncio
    @patch("app.services.user_route_service.UserRouteService._validate_route_segments")
    async def test_update_segment_validation_failure(
        self,
        mock_validate: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test that segment update validation failures are handled correctly."""
        # Mock validation to fail
        mock_validate.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route validation failed: Invalid route configuration",
        )

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segment = UserRouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"station_tfl_id": test_station2.tfl_id},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "validation failed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_schedule_without_days(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating schedule without providing days_of_week (None case)."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON", "TUE"],
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)

        # Update only end_time, leaving days_of_week as None
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/schedules/{schedule.id}",
            json={"end_time": "17:00:00"},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["end_time"] == "17:00:00"
        assert data["days_of_week"] == ["MON", "TUE"]  # Unchanged

    @pytest.mark.asyncio
    @patch("app.services.tfl_service.TfLService.validate_route")
    async def test_validate_segments_with_invalid_index(
        self,
        mock_validate_route: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test _validate_segments method with invalid_index from TfL service."""
        # Mock TfL service to return validation failure with index
        mock_validate_route.return_value = (False, "Station not on line", 1)

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json={
                "segments": [
                    {
                        "sequence": 0,
                        "station_tfl_id": test_station1.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                    {
                        "sequence": 1,
                        "station_tfl_id": test_station2.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"]
        assert "route validation failed" in detail.lower()
        assert "station not on line" in detail.lower()
        assert "segment index: 1" in detail.lower()

    @pytest.mark.asyncio
    @patch("app.services.tfl_service.TfLService.validate_route")
    async def test_validate_segments_without_invalid_index(
        self,
        mock_validate_route: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test _validate_segments method without invalid_index from TfL service."""
        # Mock TfL service to return validation failure without index
        mock_validate_route.return_value = (False, "Invalid route configuration", None)

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json={
                "segments": [
                    {
                        "sequence": 0,
                        "station_tfl_id": test_station1.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                    {
                        "sequence": 1,
                        "station_tfl_id": test_station2.tfl_id,
                        "line_tfl_id": test_line.tfl_id,
                    },
                ]
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"]
        assert "route validation failed" in detail.lower()
        assert "invalid route configuration" in detail.lower()
        # Should NOT contain segment index
        assert "segment index" not in detail.lower()

    @pytest.mark.asyncio
    @patch("app.services.tfl_service.TfLService.validate_route")
    async def test_validate_route_segments_method(
        self,
        mock_validate_route: AsyncMock,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        test_station1: Station,
        test_station2: Station,
        test_line: Line,
        db_session: AsyncSession,
    ) -> None:
        """Test _validate_route_segments method is called during segment update."""
        # Mock TfL service to return success
        mock_validate_route.return_value = (True, "", None)

        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segment = UserRouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"station_tfl_id": test_station2.tfl_id},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        # Verify TfL validate_route was called (which means _validate_route_segments worked)
        mock_validate_route.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_schedule_with_explicit_none_days(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating schedule with explicit days_of_week: None to trigger validator line 153."""
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = UserRouteSchedule(
            route_id=route.id,
            days_of_week=["MON", "TUE"],
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)

        # Explicitly pass days_of_week as None to trigger line 153 in validate_days
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/schedules/{schedule.id}",
            json={"days_of_week": None, "start_time": "09:00:00"},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["start_time"] == "09:00:00"
        assert data["days_of_week"] == ["MON", "TUE"]  # Unchanged


# ==================== Hub NaPTAN Code Integration Tests (Issue #65) ====================


@pytest.mark.asyncio
class TestRouteSegmentsWithHubCodes:
    """Integration tests for creating routes with hub NaPTAN codes (Issue #65)."""

    @pytest.fixture(autouse=True)
    async def setup_test(self, db_session: AsyncSession) -> AsyncGenerator[None]:
        """Set up test database dependency override."""

        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        yield
        app.dependency_overrides.clear()

    async def test_create_route_with_hub_codes(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test creating route segments using hub NaPTAN codes instead of station IDs.

        Route: parallel-split → HUBNORTH (via elizabethline) → elizabeth-east
        - Start on parallelline
        - Use hub code "HUBNORTH" to specify interchange (resolves to hubnorth-elizabeth with elizabethline context)
        - Destination on elizabethline
        """
        # Create route
        route = UserRoute(user_id=test_user.id, name="Cross-Mode Hub Route", active=True)
        db_session.add(route)
        await db_session.commit()

        # Upsert segments using hub code "HUBNORTH" instead of specific station ID
        segments_data = {
            "segments": [
                {"sequence": 0, "station_tfl_id": "parallel-split", "line_tfl_id": "parallelline"},
                {"sequence": 1, "station_tfl_id": "HUBNORTH", "line_tfl_id": "elizabethline"},  # Hub code!
                {"sequence": 2, "station_tfl_id": "elizabeth-east", "line_tfl_id": None},
            ]
        }

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json=segments_data,
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Response should canonicalize to hub code (normalize on read)
        assert len(data) == 3
        assert data[1]["station_tfl_id"] == "HUBNORTH"  # Canonical representation
        assert data[1]["line_tfl_id"] == "elizabethline"

    async def test_create_route_with_mixed_hub_and_station_ids(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test creating route with mix of hub codes and regular station IDs."""
        route = UserRoute(user_id=test_user.id, name="Mixed Route", active=True)
        db_session.add(route)
        await db_session.commit()

        segments_data = {
            "segments": [
                {"sequence": 0, "station_tfl_id": "HUBNORTH", "line_tfl_id": "parallelline"},  # Hub code
                {"sequence": 1, "station_tfl_id": "parallel-south", "line_tfl_id": None},  # Station ID
            ]
        }

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json=segments_data,
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data[0]["station_tfl_id"] == "HUBNORTH"  # Has hub, returns hub code
        assert data[1]["station_tfl_id"] == "parallel-south"  # No hub, returns station ID

    async def test_create_route_hub_code_invalid_line(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test error when hub code used with line that doesn't serve it."""
        # Create a line3 that doesn't serve the hub
        line3 = Line(
            tfl_id="line3",
            name="Line 3",
            mode="dlr",
            last_updated=datetime.now(UTC),
            route_variants={"routes": [{"name": "Line 3 Route", "stations": ["other-station"]}]},
        )
        other_station = Station(
            tfl_id="other-station",
            name="Other Station",
            latitude=51.6,
            longitude=0.1,
            lines=["line3"],
            last_updated=datetime.now(UTC),
        )
        db_session.add_all([line3, other_station])
        await db_session.commit()

        route = UserRoute(user_id=test_user.id, name="Invalid Route", active=True)
        db_session.add(route)
        await db_session.commit()

        segments_data = {
            "segments": [
                {"sequence": 0, "station_tfl_id": "HUBNORTH", "line_tfl_id": "line3"},  # Hub doesn't serve line3
                {"sequence": 1, "station_tfl_id": "other-station", "line_tfl_id": None},
            ]
        }

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json=segments_data,
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "HUBNORTH" in response.json()["detail"]
        assert "line3" in response.json()["detail"]

    async def test_update_segment_with_hub_code(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test updating an existing segment to use a hub code."""
        route = UserRoute(user_id=test_user.id, name="Update Test Route", active=True)
        db_session.add(route)
        await db_session.commit()

        # Create initial segments: parallel-split → parallel-south (all on parallelline)
        segments_data = {
            "segments": [
                {"sequence": 0, "station_tfl_id": "parallel-split", "line_tfl_id": "parallelline"},
                {"sequence": 1, "station_tfl_id": "parallel-south", "line_tfl_id": None},
            ]
        }
        await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json=segments_data,
            headers=auth_headers_for_user,
        )

        # Update first segment to use hub code (changes the station at the start)
        update_data = {"station_tfl_id": "HUBNORTH"}  # Keep parallelline, just change station to hub

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json=update_data,
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["station_tfl_id"] == "HUBNORTH"  # Returns hub code
        assert data["line_tfl_id"] == "parallelline"

    async def test_get_route_returns_canonical_hub_codes(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test GET route returns hub codes (canonicalize on read)."""
        route = UserRoute(user_id=test_user.id, name="Canonical Test Route", active=True)
        db_session.add(route)
        await db_session.commit()

        # Create segments using station ID (hubnorth-elizabeth)
        segments_data = {
            "segments": [
                {
                    "sequence": 0,
                    "station_tfl_id": "hubnorth-elizabeth",
                    "line_tfl_id": "elizabethline",
                },  # Station ID with hub
                {"sequence": 1, "station_tfl_id": "elizabeth-east", "line_tfl_id": None},
            ]
        }
        await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json=segments_data,
            headers=auth_headers_for_user,
        )

        # GET route - should return hub code not station ID
        response = await async_client.get(
            f"/api/v1/routes/{route.id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["segments"]) == 2
        assert data["segments"][0]["station_tfl_id"] == "HUBNORTH"  # Canonicalized to hub code

    async def test_backward_compatibility_station_ids_still_work(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
        test_railway_network: RailwayNetworkFixture,
    ) -> None:
        """Test that existing routes using station IDs continue to work."""
        route = UserRoute(user_id=test_user.id, name="Backward Compat Route", active=True)
        db_session.add(route)
        await db_session.commit()

        # Use station IDs directly (no hub codes)
        segments_data = {
            "segments": [
                {"sequence": 0, "station_tfl_id": "parallel-split", "line_tfl_id": "parallelline"},
                {"sequence": 1, "station_tfl_id": "parallel-south", "line_tfl_id": None},
            ]
        }

        response = await async_client.put(
            f"/api/v1/routes/{route.id}/segments",
            json=segments_data,
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # No hubs involved, should return station IDs
        assert data[0]["station_tfl_id"] == "parallel-split"
        assert data[1]["station_tfl_id"] == "parallel-south"
