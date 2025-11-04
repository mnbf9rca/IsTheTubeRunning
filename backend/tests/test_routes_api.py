"""Tests for routes API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, patch

import pytest
from app.core.database import get_db
from app.main import app
from app.models.route import Route, RouteSchedule, RouteSegment
from app.models.tfl import Line, Station
from app.models.user import User
from fastapi import HTTPException, status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


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
        station = Station(
            tfl_id="940GZZLUOXC",
            name="Oxford Circus",
            latitude=51.515,
            longitude=-0.141,
            lines=["central", "victoria"],
            last_updated=datetime.now(UTC),
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)
        return station

    @pytest.fixture
    async def test_station2(self, db_session: AsyncSession) -> Station:
        """Create a second test station."""
        station = Station(
            tfl_id="940GZZLUBND",
            name="Bond Street",
            latitude=51.514,
            longitude=-0.149,
            lines=["central", "jubilee"],
            last_updated=datetime.now(UTC),
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
            color="#DC241F",
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
        route1 = Route(user_id=test_user.id, name="Route 1", active=True)
        route2 = Route(user_id=test_user.id, name="Route 2", active=False)
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
        route1 = Route(user_id=test_user.id, name="My Route", active=True)
        route2 = Route(user_id=another_user.id, name="Other Route", active=True)
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
        route = Route(
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
        route = Route(user_id=another_user.id, name="Other Route", active=True)
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
        route = Route(user_id=test_user.id, name="Old Name", active=True)
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
        route = Route(
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
        db_session: AsyncSession,
    ) -> None:
        """Test deleting a route."""
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        route_id = route.id

        response = await async_client.delete(
            f"/api/v1/routes/{route_id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify route was deleted
        result = await db_session.execute(select(Route).where(Route.id == route_id))
        assert result.scalar_one_or_none() is None

    # ==================== Segment Tests ====================

    @pytest.mark.asyncio
    @patch("app.services.route_service.RouteService._validate_segments")
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

        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
                        "sequence": 1,
                        "station_id": str(test_station2.id),
                        "line_id": str(test_line.id),
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
    @patch("app.services.route_service.RouteService._validate_segments")
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

        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
                        "sequence": 1,
                        "station_id": str(test_station2.id),
                        "line_id": str(test_line.id),
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
    @patch("app.services.route_service.RouteService._validate_route_segments")
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

        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segment = RouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"station_id": str(test_station2.id)},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["station_id"] == str(test_station2.id)

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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        # Create 3 segments
        segments = [
            RouteSegment(
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

        # Verify segment was deleted and others resequenced
        result = await db_session.execute(
            select(RouteSegment).where(RouteSegment.route_id == route.id).order_by(RouteSegment.sequence)
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        # Create exactly 2 segments (minimum)
        segments = [
            RouteSegment(
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = RouteSchedule(
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = RouteSchedule(
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = RouteSchedule(
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

        # Verify deletion
        result = await db_session.execute(select(RouteSchedule).where(RouteSchedule.id == schedule_id))
        assert result.scalar_one_or_none() is None

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
        route = Route(user_id=another_user.id, name="Other Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = RouteSchedule(
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)

        # Try to update segment that doesn't exist
        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"station_id": str(test_station1.id)},
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        # Add 3 segments so we can test deletion without hitting minimum constraint
        segments = [
            RouteSegment(
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
        route = Route(
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
    @patch("app.services.route_service.RouteService._validate_route_segments")
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
            color="#0098D4",
            last_updated=datetime.now(UTC),
        )
        db_session.add(line2)
        await db_session.commit()
        await db_session.refresh(line2)

        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segment = RouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"line_id": str(line2.id)},  # Update only line_id
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["line_id"] == str(line2.id)
        assert data["station_id"] == str(test_station1.id)  # Unchanged

    @pytest.mark.asyncio
    async def test_update_schedule_start_time(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating only the start_time field of a schedule."""
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = RouteSchedule(
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
    @patch("app.services.route_service.RouteService._validate_segments")
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

        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
                        "sequence": 1,
                        "station_id": str(test_station2.id),
                        "line_id": str(test_line.id),
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
    @patch("app.services.route_service.RouteService._validate_route_segments")
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

        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segment = RouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"station_id": str(test_station2.id)},
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = RouteSchedule(
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

        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
                        "sequence": 1,
                        "station_id": str(test_station2.id),
                        "line_id": str(test_line.id),
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

        route = Route(user_id=test_user.id, name="Test Route", active=True)
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
                        "sequence": 1,
                        "station_id": str(test_station2.id),
                        "line_id": str(test_line.id),
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

        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segment = RouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=test_station1.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/routes/{route.id}/segments/0",
            json={"station_id": str(test_station2.id)},
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
        route = Route(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        schedule = RouteSchedule(
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
