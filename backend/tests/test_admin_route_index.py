"""Tests for admin route index management endpoint."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.user import User
from httpx import ASGITransport, AsyncClient
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
        admin_headers: dict[str, str],
    ) -> None:
        """Test rebuilding indexes for a single route successfully."""
        route_id = uuid4()

        # Mock the service method to avoid needing full database setup
        mock_result = {"rebuilt_count": 1, "failed_count": 0, "errors": []}

        with patch("app.api.admin.RouteIndexService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.rebuild_routes = AsyncMock(return_value=mock_result)
            mock_service_class.return_value = mock_service

            response = await async_client_with_db.post(
                build_api_url(f"/admin/routes/rebuild-indexes?route_id={route_id}"),
                headers=admin_headers,
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
        admin_headers: dict[str, str],
    ) -> None:
        """Test rebuilding indexes for all routes successfully."""
        mock_result = {"rebuilt_count": 5, "failed_count": 0, "errors": []}

        with patch("app.api.admin.RouteIndexService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.rebuild_routes = AsyncMock(return_value=mock_result)
            mock_service_class.return_value = mock_service

            response = await async_client_with_db.post(
                build_api_url("/admin/routes/rebuild-indexes"),
                headers=admin_headers,
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
        admin_headers: dict[str, str],
    ) -> None:
        """Test rebuilding indexes with some failures."""
        route_id = uuid4()
        mock_result = {
            "rebuilt_count": 0,
            "failed_count": 1,
            "errors": [f"Route {route_id}: Route not found"],
        }

        with patch("app.api.admin.RouteIndexService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.rebuild_routes = AsyncMock(return_value=mock_result)
            mock_service_class.return_value = mock_service

            response = await async_client_with_db.post(
                build_api_url(f"/admin/routes/rebuild-indexes?route_id={route_id}"),
                headers=admin_headers,
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
        admin_headers: dict[str, str],
    ) -> None:
        """Test that service exceptions are properly converted to HTTP errors."""
        with patch("app.api.admin.RouteIndexService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.rebuild_routes = AsyncMock(side_effect=Exception("Database error"))
            mock_service_class.return_value = mock_service

            response = await async_client_with_db.post(
                build_api_url("/admin/routes/rebuild-indexes"),
                headers=admin_headers,
            )

            assert response.status_code == 500
            assert "Failed to rebuild indexes" in response.json()["detail"]
