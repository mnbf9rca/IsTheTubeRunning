"""Tests for admin alert management endpoints."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.notification import NotificationLog, NotificationMethod, NotificationStatus
from app.models.user import User
from app.models.user_route import UserRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.http_assertions import assert_401_unauthorized


def build_api_url(endpoint: str) -> str:
    """
    Build full API URL with version prefix.

    Args:
        endpoint: API endpoint path (e.g., '/admin/alerts/trigger-check')

    Returns:
        Full API URL (e.g., '/api/v1/admin/alerts/trigger-check')
    """
    # Simply concatenate the prefix and endpoint
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


# ==================== Authorization Tests ====================


@pytest.mark.asyncio
async def test_trigger_check_requires_auth(async_client_with_db: AsyncClient) -> None:
    """Test that trigger-check endpoint requires authentication."""
    response = await async_client_with_db.post(build_api_url("/admin/alerts/trigger-check"))
    assert_401_unauthorized(response, expected_detail="Not authenticated")


@pytest.mark.asyncio
async def test_trigger_check_requires_admin(
    async_client_with_db: AsyncClient,
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test that trigger-check endpoint requires admin role."""
    response = await async_client_with_db.post(
        build_api_url("/admin/alerts/trigger-check"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 403  # Forbidden - user is authenticated but lacks admin privileges
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_worker_status_requires_auth(async_client_with_db: AsyncClient) -> None:
    """Test that worker-status endpoint requires authentication."""
    response = await async_client_with_db.get(build_api_url("/admin/alerts/worker-status"))
    assert_401_unauthorized(response, expected_detail="Not authenticated")


@pytest.mark.asyncio
async def test_worker_status_requires_admin(
    async_client_with_db: AsyncClient,
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test that worker-status endpoint requires admin role."""
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/worker-status"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 403  # Forbidden - user is authenticated but lacks admin privileges
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_recent_logs_requires_auth(async_client_with_db: AsyncClient) -> None:
    """Test that recent-logs endpoint requires authentication."""
    response = await async_client_with_db.get(build_api_url("/admin/alerts/recent-logs"))
    assert_401_unauthorized(response, expected_detail="Not authenticated")


@pytest.mark.asyncio
async def test_recent_logs_requires_admin(
    async_client_with_db: AsyncClient,
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test that recent-logs endpoint requires admin role."""
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 403  # Forbidden - user is authenticated but lacks admin privileges
    assert response.json()["detail"] == "Admin privileges required"


# ==================== Trigger Check Endpoint Tests ====================


@pytest.mark.asyncio
@patch("app.api.admin.get_redis_client")
@patch("app.api.admin.AlertService")
async def test_trigger_check_success(
    mock_alert_service_class: MagicMock,
    mock_get_redis: MagicMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test successful manual alert check trigger."""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    # Mock AlertService
    mock_service = AsyncMock()
    mock_service.process_all_routes.return_value = {
        "routes_checked": 5,
        "alerts_sent": 2,
        "errors": 0,
    }
    mock_alert_service_class.return_value = mock_service

    response = await async_client_with_db.post(
        build_api_url("/admin/alerts/trigger-check"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["routes_checked"] == 5
    assert data["alerts_sent"] == 2
    assert data["errors"] == 0
    assert "2 alert(s) sent" in data["message"]

    # Verify Redis cleanup was called
    mock_redis.aclose.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.admin.get_redis_client")
@patch("app.api.admin.AlertService")
async def test_trigger_check_no_alerts(
    mock_alert_service_class: MagicMock,
    mock_get_redis: MagicMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test trigger check when no alerts are sent."""
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    mock_service = AsyncMock()
    mock_service.process_all_routes.return_value = {
        "routes_checked": 10,
        "alerts_sent": 0,
        "errors": 0,
    }
    mock_alert_service_class.return_value = mock_service

    response = await async_client_with_db.post(
        build_api_url("/admin/alerts/trigger-check"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["routes_checked"] == 10
    assert data["alerts_sent"] == 0
    assert data["errors"] == 0


@pytest.mark.asyncio
@patch("app.api.admin.get_redis_client")
@patch("app.api.admin.AlertService")
async def test_trigger_check_with_errors(
    mock_alert_service_class: MagicMock,
    mock_get_redis: MagicMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test trigger check when errors occur during processing."""
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    mock_service = AsyncMock()
    mock_service.process_all_routes.return_value = {
        "routes_checked": 8,
        "alerts_sent": 3,
        "errors": 2,
    }
    mock_alert_service_class.return_value = mock_service

    response = await async_client_with_db.post(
        build_api_url("/admin/alerts/trigger-check"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["errors"] == 2


# ==================== Worker Status Endpoint Tests ====================


@pytest.mark.asyncio
@patch("app.api.admin.get_redis_client")
@patch("app.api.admin.celery_app")
async def test_worker_status_healthy(
    mock_celery: MagicMock,
    mock_get_redis: AsyncMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test worker status when workers are healthy."""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # No cached clock (first run)
    mock_redis.setex = AsyncMock()
    mock_redis.aclose = AsyncMock()
    mock_get_redis.return_value = mock_redis

    # Mock Celery inspector
    mock_inspector = MagicMock()
    mock_inspector.active.return_value = {"worker1": [{"id": "task1"}]}
    mock_inspector.scheduled.return_value = {"worker1": [{"id": "task2"}, {"id": "task3"}]}
    mock_inspector.stats.return_value = {"worker1": {"clock": 12345, "total": {}}}
    mock_celery.control.inspect.return_value = mock_inspector

    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/worker-status"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_available"] is True
    assert data["active_tasks"] == 1
    assert data["scheduled_tasks"] == 2
    assert data["last_heartbeat"] is not None
    assert "healthy" in data["message"].lower()


@pytest.mark.asyncio
@patch("app.api.admin.celery_app")
async def test_worker_status_no_workers(
    mock_celery: MagicMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test worker status when no workers are available."""
    mock_inspector = MagicMock()
    mock_inspector.active.return_value = None
    mock_inspector.scheduled.return_value = None
    mock_inspector.stats.return_value = None
    mock_celery.control.inspect.return_value = mock_inspector

    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/worker-status"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_available"] is False
    assert data["active_tasks"] == 0
    assert data["scheduled_tasks"] == 0
    assert data["last_heartbeat"] is None
    assert "no workers" in data["message"].lower()


@pytest.mark.asyncio
@patch("app.api.admin.get_redis_client")
@patch("app.api.admin.celery_app")
async def test_worker_status_multiple_workers(
    mock_celery: MagicMock,
    mock_get_redis: AsyncMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test worker status with multiple workers."""
    # Mock Redis client with cached (clock, timestamp) tuple
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="10,2025-01-01T00:00:00+00:00")  # Cached clock,timestamp
    mock_redis.setex = AsyncMock()
    mock_redis.aclose = AsyncMock()
    mock_get_redis.return_value = mock_redis

    mock_inspector = MagicMock()
    mock_inspector.active.return_value = {
        "worker1": [{"id": "task1"}, {"id": "task2"}],
        "worker2": [{"id": "task3"}],
    }
    mock_inspector.scheduled.return_value = {
        "worker1": [{"id": "task4"}],
        "worker2": [],
    }
    mock_inspector.stats.return_value = {"worker1": {"clock": 42}, "worker2": {"clock": 43}}
    mock_celery.control.inspect.return_value = mock_inspector

    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/worker-status"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_available"] is True
    assert data["active_tasks"] == 3  # 2 + 1
    assert data["scheduled_tasks"] == 1  # 1 + 0
    assert data["last_heartbeat"] is not None  # Worker is responding (clock 42 > cached 10)


@pytest.mark.asyncio
@patch("app.api.admin.get_redis_client")
@patch("app.api.admin.celery_app")
async def test_worker_status_frozen_worker(
    mock_celery: MagicMock,
    mock_get_redis: AsyncMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test worker status when worker clock doesn't increment (frozen)."""
    # Mock Redis client with cached (clock, timestamp) - same clock value
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="100,2025-01-01T00:00:00+00:00")
    mock_redis.setex = AsyncMock()
    mock_redis.aclose = AsyncMock()
    mock_get_redis.return_value = mock_redis

    mock_inspector = MagicMock()
    mock_inspector.active.return_value = {"worker1": []}
    mock_inspector.scheduled.return_value = {"worker1": []}
    mock_inspector.stats.return_value = {"worker1": {"clock": 100}}  # Same clock as cached
    mock_celery.control.inspect.return_value = mock_inspector

    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/worker-status"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_available"] is True
    assert data["last_heartbeat"] is None  # Clock didn't increment - frozen
    assert "frozen" in data["message"].lower()


@pytest.mark.asyncio
@patch("app.api.admin.get_redis_client")
@patch("app.api.admin.celery_app")
async def test_worker_status_worker_restarted(
    mock_celery: MagicMock,
    mock_get_redis: AsyncMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test worker status when worker restarts (clock resets to lower value)."""
    # Mock Redis client with high cached clock value
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="10000,2025-01-01T00:00:00+00:00")
    mock_redis.setex = AsyncMock()
    mock_redis.aclose = AsyncMock()
    mock_get_redis.return_value = mock_redis

    mock_inspector = MagicMock()
    mock_inspector.active.return_value = {"worker1": [{"id": "task1"}]}
    mock_inspector.scheduled.return_value = {"worker1": []}
    mock_inspector.stats.return_value = {"worker1": {"clock": 42}}  # Clock reset (< cached)
    mock_celery.control.inspect.return_value = mock_inspector

    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/worker-status"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_available"] is True
    assert data["active_tasks"] == 1
    assert data["last_heartbeat"] is not None  # Worker restarted - treat as healthy
    assert "healthy" in data["message"].lower()


@pytest.mark.asyncio
@patch("app.api.admin.get_redis_client")
@patch("app.api.admin.celery_app")
async def test_worker_status_invalid_cached_data(
    mock_celery: MagicMock,
    mock_get_redis: AsyncMock,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test worker status when Redis cache has invalid data format."""
    # Mock Redis client with invalid cached data (missing comma)
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="not_a_valid_format")
    mock_redis.setex = AsyncMock()
    mock_redis.aclose = AsyncMock()
    mock_get_redis.return_value = mock_redis

    mock_inspector = MagicMock()
    mock_inspector.active.return_value = {"worker1": [{"id": "task1"}]}
    mock_inspector.scheduled.return_value = {"worker1": []}
    mock_inspector.stats.return_value = {"worker1": {"clock": 123}}
    mock_celery.control.inspect.return_value = mock_inspector

    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/worker-status"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["worker_available"] is True
    assert data["active_tasks"] == 1
    assert data["last_heartbeat"] is not None  # Treated as first check - healthy
    assert "healthy" in data["message"].lower()


# ==================== Recent Logs Endpoint Tests ====================


@pytest.mark.asyncio
async def test_recent_logs_empty(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test recent logs when no logs exist."""
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["logs"] == []
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_recent_logs_with_data(
    db_session: AsyncSession,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test recent logs returns notification logs."""
    # Create a test route
    route = UserRoute(
        user_id=test_user.id,
        name="Test Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.commit()
    await db_session.refresh(route)

    # Create notification logs
    logs = [
        NotificationLog(
            user_id=test_user.id,
            route_id=route.id,
            sent_at=datetime.now(UTC),
            method=NotificationMethod.EMAIL,
            status=NotificationStatus.SENT,
            error_message=None,
        ),
        NotificationLog(
            user_id=test_user.id,
            route_id=route.id,
            sent_at=datetime.now(UTC),
            method=NotificationMethod.SMS,
            status=NotificationStatus.FAILED,
            error_message="SMS service unavailable",
        ),
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["logs"]) == 2
    assert data["limit"] == 50
    assert data["offset"] == 0

    # Verify log details
    assert data["logs"][0]["method"] in ["email", "sms"]
    assert data["logs"][0]["status"] in ["sent", "failed"]
    assert UUID(data["logs"][0]["user_id"]) == test_user.id
    assert UUID(data["logs"][0]["route_id"]) == route.id


@pytest.mark.asyncio
async def test_recent_logs_pagination(
    db_session: AsyncSession,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test pagination of recent logs."""
    # Create a test route
    route = UserRoute(
        user_id=test_user.id,
        name="Test Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.commit()
    await db_session.refresh(route)

    # Create 10 notification logs
    for _ in range(10):
        log = NotificationLog(
            user_id=test_user.id,
            route_id=route.id,
            sent_at=datetime.now(UTC),
            method=NotificationMethod.EMAIL,
            status=NotificationStatus.SENT,
            error_message=None,
        )
        db_session.add(log)
    await db_session.commit()

    # Get first page (limit=5)
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?limit=5&offset=0"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["logs"]) == 5
    assert data["limit"] == 5
    assert data["offset"] == 0

    # Get second page
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?limit=5&offset=5"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["logs"]) == 5
    assert data["limit"] == 5
    assert data["offset"] == 5


@pytest.mark.asyncio
async def test_recent_logs_filter_by_status(
    db_session: AsyncSession,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test filtering logs by status."""
    # Create a test route
    route = UserRoute(
        user_id=test_user.id,
        name="Test Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.commit()
    await db_session.refresh(route)

    # Create logs with different statuses
    statuses = [NotificationStatus.SENT, NotificationStatus.SENT, NotificationStatus.FAILED]
    for status in statuses:
        log = NotificationLog(
            user_id=test_user.id,
            route_id=route.id,
            sent_at=datetime.now(UTC),
            method=NotificationMethod.EMAIL,
            status=status,
            error_message="Error" if status == NotificationStatus.FAILED else None,
        )
        db_session.add(log)
    await db_session.commit()

    # Filter by SENT status
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?status=sent"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["logs"]) == 2
    assert all(log["status"] == "sent" for log in data["logs"])

    # Filter by FAILED status
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?status=failed"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["logs"]) == 1
    assert data["logs"][0]["status"] == "failed"
    assert data["logs"][0]["error_message"] == "Error"


@pytest.mark.asyncio
async def test_recent_logs_ordering(
    db_session: AsyncSession,
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test that logs are ordered by sent_at descending (most recent first)."""
    # Create a test route
    route = UserRoute(
        user_id=test_user.id,
        name="Test Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.commit()
    await db_session.refresh(route)

    # Create logs with different timestamps
    base_time = datetime.now(UTC)
    timestamps = [
        base_time - timedelta(hours=2),
        base_time - timedelta(hours=1),
        base_time,
    ]

    for timestamp in timestamps:
        log = NotificationLog(
            user_id=test_user.id,
            route_id=route.id,
            sent_at=timestamp,
            method=NotificationMethod.EMAIL,
            status=NotificationStatus.SENT,
            error_message=None,
        )
        db_session.add(log)
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs"),
        headers=auth_headers_for_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 3

    # Verify descending order (most recent first)
    sent_times = [log["sent_at"] for log in data["logs"]]
    assert sent_times == sorted(sent_times, reverse=True)


@pytest.mark.asyncio
async def test_recent_logs_limit_validation(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test limit parameter validation."""
    # Test limit too low
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?limit=0"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 422  # Validation error

    # Test limit too high
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?limit=1001"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 422  # Validation error

    # Test valid limit
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?limit=100"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_recent_logs_offset_validation(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test offset parameter validation."""
    # Test negative offset
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?offset=-1"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 422  # Validation error

    # Test valid offset
    response = await async_client_with_db.get(
        build_api_url("/admin/alerts/recent-logs?offset=0"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 200
