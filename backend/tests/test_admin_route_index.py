"""Tests for admin route index management endpoint."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.tfl import Line, Station
from app.models.user import User
from app.models.user_route import UserRoute, UserRouteSegment
from app.models.user_route_index import UserRouteStationIndex
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def build_api_url(endpoint: str) -> str:
    """
    Build full API URL with version prefix.

    Args:
        endpoint: API endpoint path (e.g., '/admin/routes/rebuild-indexes')

    Returns:
        Full API URL (e.g., '/api/v1/admin/routes/rebuild-indexes')
    """
    prefix = settings.API_V1_PREFIX.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{prefix}{path}"


@pytest.fixture
async def async_client_with_db(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client with database dependency override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


class TestAdminRebuildIndexesEndpoint:
    """Tests for POST /admin/routes/rebuild-indexes endpoint."""

    @pytest.mark.asyncio
    async def test_rebuild_indexes_success_single_route(
        self,
        async_client_with_db: AsyncClient,
        admin_user: User,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test rebuilding indexes for a single route successfully."""
        route_id = uuid4()

        # Mock the service method to avoid needing full database setup
        mock_result = {"rebuilt_count": 1, "failed_count": 0, "errors": []}

        with patch("app.api.admin.UserRouteIndexService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.rebuild_routes = AsyncMock(return_value=mock_result)
            mock_service_class.return_value = mock_service

            response = await async_client_with_db.post(
                build_api_url(f"/admin/routes/rebuild-indexes?route_id={route_id}"),
                headers=auth_headers_for_user,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["rebuilt_count"] == 1
            assert data["failed_count"] == 0
            assert data["errors"] == []

            # Verify service was called correctly
            mock_service.rebuild_routes.assert_called_once_with(route_id, auto_commit=True)

    @pytest.mark.asyncio
    async def test_rebuild_indexes_success_all_routes(
        self,
        async_client_with_db: AsyncClient,
        admin_user: User,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test rebuilding indexes for all routes successfully."""
        mock_result = {"rebuilt_count": 5, "failed_count": 0, "errors": []}

        with patch("app.api.admin.UserRouteIndexService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.rebuild_routes = AsyncMock(return_value=mock_result)
            mock_service_class.return_value = mock_service

            response = await async_client_with_db.post(
                build_api_url("/admin/routes/rebuild-indexes"),
                headers=auth_headers_for_user,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["rebuilt_count"] == 5
            assert data["failed_count"] == 0
            assert data["errors"] == []

            # Verify service was called with None (all routes)
            mock_service.rebuild_routes.assert_called_once_with(None, auto_commit=True)

    @pytest.mark.asyncio
    async def test_rebuild_indexes_partial_failure(
        self,
        async_client_with_db: AsyncClient,
        admin_user: User,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test rebuilding indexes with some failures."""
        route_id = uuid4()
        mock_result = {
            "rebuilt_count": 0,
            "failed_count": 1,
            "errors": [f"Route {route_id}: Route not found"],
        }

        with patch("app.api.admin.UserRouteIndexService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.rebuild_routes = AsyncMock(return_value=mock_result)
            mock_service_class.return_value = mock_service

            response = await async_client_with_db.post(
                build_api_url(f"/admin/routes/rebuild-indexes?route_id={route_id}"),
                headers=auth_headers_for_user,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["rebuilt_count"] == 0
            assert data["failed_count"] == 1
            assert len(data["errors"]) == 1

    @pytest.mark.asyncio
    async def test_rebuild_indexes_requires_admin(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test that non-admin users cannot rebuild indexes."""
        response = await async_client_with_db.post(
            build_api_url("/admin/routes/rebuild-indexes"),
            headers=auth_headers_for_user,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rebuild_indexes_exception_handling(
        self,
        async_client_with_db: AsyncClient,
        admin_user: User,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test that service exceptions are properly converted to HTTP errors."""
        with patch("app.api.admin.UserRouteIndexService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.rebuild_routes = AsyncMock(side_effect=Exception("Database error"))
            mock_service_class.return_value = mock_service

            response = await async_client_with_db.post(
                build_api_url("/admin/routes/rebuild-indexes"),
                headers=auth_headers_for_user,
            )

            assert response.status_code == 500
            assert "Failed to rebuild indexes" in response.json()["detail"]


# =============================================================================
# Integration Tests (No Mocks - Full Stack)
# =============================================================================


class TestAdminRebuildIndexesIntegration:
    """Integration tests for rebuild indexes endpoint without mocks."""

    @pytest.mark.asyncio
    async def test_rebuild_indexes_integration_single_route(
        self,
        async_client_with_db: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Integration test: Rebuild indexes for a single route with real database."""
        # Unpack admin_user tuple (User, AdminUser)
        user, _ = admin_user

        # Create real test data
        line = Line(
            id=uuid.uuid4(),
            tfl_id="testline-integration",
            name="Test Line",
            mode="tube",
            last_updated=datetime.now(UTC),
            route_variants={
                "routes": [
                    {
                        "name": "Eastbound",
                        "direction": "inbound",
                        "stations": ["station-a", "station-b"],
                    }
                ]
            },
        )
        station_a = Station(
            id=uuid.uuid4(),
            tfl_id="station-a",
            name="Station A",
            latitude=51.5,
            longitude=-0.1,
            lines=["testline-integration"],
            last_updated=datetime.now(UTC),
        )
        station_b = Station(
            id=uuid.uuid4(),
            tfl_id="station-b",
            name="Station B",
            latitude=51.6,
            longitude=-0.2,
            lines=["testline-integration"],
            last_updated=datetime.now(UTC),
        )

        db_session.add_all([line, station_a, station_b])
        await db_session.flush()

        # Create route with segments
        route = UserRoute(user_id=user.id, name="Integration Test Route", active=True)
        db_session.add(route)
        await db_session.flush()

        segments = [
            UserRouteSegment(route_id=route.id, sequence=1, station_id=station_a.id, line_id=line.id),
            UserRouteSegment(route_id=route.id, sequence=2, station_id=station_b.id, line_id=None),
        ]
        db_session.add_all(segments)
        await db_session.commit()

        # Call the endpoint to rebuild indexes (NO MOCKS)
        response = await async_client_with_db.post(
            build_api_url(f"/admin/routes/rebuild-indexes?route_id={route.id}"),
            headers=auth_headers_for_user,
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rebuilt_count"] == 1
        assert data["failed_count"] == 0

        # Verify database state: check that UserRouteStationIndex entries were created
        result = await db_session.execute(
            select(UserRouteStationIndex).where(UserRouteStationIndex.route_id == route.id)
        )
        index_entries = result.scalars().all()

        assert len(index_entries) == 2  # Both stations indexed
        station_naptans = {entry.station_naptan for entry in index_entries}
        assert station_naptans == {"station-a", "station-b"}
        assert all(entry.line_tfl_id == "testline-integration" for entry in index_entries)

    @pytest.mark.asyncio
    async def test_rebuild_indexes_integration_all_routes(
        self,
        async_client_with_db: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Integration test: Rebuild indexes for all routes with real database."""
        # Unpack admin_user tuple (User, AdminUser)
        user, _ = admin_user

        # Create real test data
        line = Line(
            id=uuid.uuid4(),
            tfl_id="testline-multi",
            name="Test Line Multi",
            mode="tube",
            last_updated=datetime.now(UTC),
            route_variants={
                "routes": [
                    {
                        "name": "Route 1",
                        "direction": "inbound",
                        "stations": ["station-x", "station-y", "station-z"],
                    }
                ]
            },
        )
        station_x = Station(
            id=uuid.uuid4(),
            tfl_id="station-x",
            name="Station X",
            latitude=51.5,
            longitude=-0.1,
            lines=["testline-multi"],
            last_updated=datetime.now(UTC),
        )
        station_y = Station(
            id=uuid.uuid4(),
            tfl_id="station-y",
            name="Station Y",
            latitude=51.6,
            longitude=-0.2,
            lines=["testline-multi"],
            last_updated=datetime.now(UTC),
        )
        station_z = Station(
            id=uuid.uuid4(),
            tfl_id="station-z",
            name="Station Z",
            latitude=51.7,
            longitude=-0.3,
            lines=["testline-multi"],
            last_updated=datetime.now(UTC),
        )

        db_session.add_all([line, station_x, station_y, station_z])
        await db_session.flush()

        # Create multiple routes
        route1 = UserRoute(user_id=user.id, name="Route 1", active=True)
        route2 = UserRoute(user_id=user.id, name="Route 2", active=True)
        db_session.add_all([route1, route2])
        await db_session.flush()

        # Route 1: X → Y
        segments1 = [
            UserRouteSegment(route_id=route1.id, sequence=1, station_id=station_x.id, line_id=line.id),
            UserRouteSegment(route_id=route1.id, sequence=2, station_id=station_y.id, line_id=None),
        ]
        # Route 2: Y → Z
        segments2 = [
            UserRouteSegment(route_id=route2.id, sequence=1, station_id=station_y.id, line_id=line.id),
            UserRouteSegment(route_id=route2.id, sequence=2, station_id=station_z.id, line_id=None),
        ]
        db_session.add_all(segments1 + segments2)
        await db_session.commit()

        # Call the endpoint to rebuild ALL indexes (NO MOCKS)
        response = await async_client_with_db.post(
            build_api_url("/admin/routes/rebuild-indexes"),
            headers=auth_headers_for_user,
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rebuilt_count"] == 2  # Both routes rebuilt
        assert data["failed_count"] == 0

        # Verify database state: check that indexes were created for both routes
        result = await db_session.execute(select(UserRouteStationIndex))
        all_index_entries = result.scalars().all()

        # Should have entries for both routes
        route_ids_in_index = {entry.route_id for entry in all_index_entries}
        assert route1.id in route_ids_in_index
        assert route2.id in route_ids_in_index

        # Route 1 should have 2 entries (X, Y)
        route1_entries = [e for e in all_index_entries if e.route_id == route1.id]
        assert len(route1_entries) == 2

        # Route 2 should have 2 entries (Y, Z)
        route2_entries = [e for e in all_index_entries if e.route_id == route2.id]
        assert len(route2_entries) == 2


# =============================================================================
# Tests for TfL Graph Build with Staleness Detection
# =============================================================================


class TestAdminTfLGraphBuildEndpoint:
    """Tests for POST /admin/tfl/build-graph endpoint."""

    @pytest.mark.asyncio
    async def test_build_graph_triggers_staleness_detection(
        self,
        async_client_with_db: AsyncClient,
        admin_user: User,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test that building TfL graph triggers staleness detection task."""
        # Mock the service to avoid hitting real TfL API
        mock_result = {
            "lines_count": 5,
            "stations_count": 100,
            "connections_count": 200,
            "hubs_count": 10,
        }

        with (
            patch("app.api.admin.TfLService") as mock_service_class,
            patch("app.api.admin.detect_and_rebuild_stale_routes") as mock_task,
        ):
            mock_service = AsyncMock()
            mock_service.build_station_graph = AsyncMock(return_value=mock_result)
            mock_service_class.return_value = mock_service

            # Mock the task's delay method (synchronous, not async)
            mock_task.delay = MagicMock()

            response = await async_client_with_db.post(
                build_api_url("/admin/tfl/build-graph"),
                headers=auth_headers_for_user,
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["lines_count"] == 5
            assert data["stations_count"] == 100

            # Verify service was called
            mock_service.build_station_graph.assert_called_once()

            # Verify staleness detection task was triggered
            mock_task.delay.assert_called_once()
