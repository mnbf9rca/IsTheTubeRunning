"""Tests for Celery tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.celery.tasks import _check_disruptions_async, check_disruptions_and_alert

# ==================== check_disruptions_and_alert Tests ====================


def test_check_disruptions_task_registered() -> None:
    """Test that task function exists."""
    # This is a simple test to ensure the task exists
    assert check_disruptions_and_alert is not None


@pytest.mark.asyncio
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_success(
    mock_session_factory: MagicMock,
    mock_redis_func: MagicMock,
    mock_alert_class: MagicMock,
) -> None:
    """Test successful execution of _check_disruptions_async function."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(
        return_value={
            "routes_checked": 5,
            "alerts_sent": 2,
            "errors": 0,
        }
    )
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function
    result = await _check_disruptions_async()

    # Verify result
    assert result["status"] == "success"
    assert result["routes_checked"] == 5
    assert result["alerts_sent"] == 2
    assert result["errors"] == 0

    # Verify AlertService was instantiated correctly
    mock_alert_class.assert_called_once_with(db=mock_session, redis_client=mock_redis)

    # Verify process_all_routes was called
    mock_alert_instance.process_all_routes.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_returns_stats(
    mock_session_factory: MagicMock,
    mock_redis_func: MagicMock,
    mock_alert_class: MagicMock,
) -> None:
    """Test that async function returns correct statistics structure."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService with different stats
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(
        return_value={
            "routes_checked": 10,
            "alerts_sent": 3,
            "errors": 1,
        }
    )
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function
    result = await _check_disruptions_async()

    # Verify result structure
    assert "status" in result
    assert "routes_checked" in result
    assert "alerts_sent" in result
    assert "errors" in result
    assert result["status"] == "success"


@pytest.mark.asyncio
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_closes_resources(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test that async function properly closes Redis and database connections."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(
        return_value={
            "routes_checked": 0,
            "alerts_sent": 0,
            "errors": 0,
        }
    )
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function
    await _check_disruptions_async()

    # Verify resources were closed
    mock_redis.close.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_closes_resources_on_error(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test that async function closes resources even when error occurs."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService to raise error
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(side_effect=RuntimeError("Test error"))
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Test error"):
        await _check_disruptions_async()

    # Verify resources were still closed
    mock_redis.close.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_no_routes_checked(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test async function when no routes are checked (no active routes)."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService with no routes
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(
        return_value={
            "routes_checked": 0,
            "alerts_sent": 0,
            "errors": 0,
        }
    )
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function
    result = await _check_disruptions_async()

    # Verify result
    assert result["status"] == "success"
    assert result["routes_checked"] == 0
    assert result["alerts_sent"] == 0
    assert result["errors"] == 0


@pytest.mark.asyncio
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_with_errors(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test async function when some routes have errors but function completes."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService with partial errors
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(
        return_value={
            "routes_checked": 10,
            "alerts_sent": 5,
            "errors": 2,  # Some routes had errors
        }
    )
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function
    result = await _check_disruptions_async()

    # Verify result includes errors
    assert result["status"] == "success"
    assert result["routes_checked"] == 10
    assert result["alerts_sent"] == 5
    assert result["errors"] == 2


@pytest.mark.asyncio
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_calls_alert_service_correctly(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test that async function instantiates AlertService with correct parameters."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(
        return_value={
            "routes_checked": 0,
            "alerts_sent": 0,
            "errors": 0,
        }
    )
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function
    await _check_disruptions_async()

    # Verify AlertService was called with correct parameters
    mock_alert_class.assert_called_once()
    call_kwargs = mock_alert_class.call_args.kwargs
    assert call_kwargs["db"] == mock_session
    assert call_kwargs["redis_client"] == mock_redis


@pytest.mark.asyncio
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_redis_connection_error(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test async function behavior when Redis connection fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client to raise error
    mock_redis_func.side_effect = ConnectionError("Redis connection failed")

    # Mock AlertService (won't be reached)
    mock_alert_instance = AsyncMock()
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function and expect error
    with pytest.raises(ConnectionError, match="Redis connection failed"):
        await _check_disruptions_async()

    # Session should still be closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_session_factory_error(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test async function behavior when database session creation fails."""
    # Mock session factory to raise error
    mock_session_factory.side_effect = ConnectionError("Database connection failed")

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService (won't be reached)
    mock_alert_instance = AsyncMock()
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function and expect error
    with pytest.raises(ConnectionError, match="Database connection failed"):
        await _check_disruptions_async()
