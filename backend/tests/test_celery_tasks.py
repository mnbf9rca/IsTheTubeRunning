"""Tests for Celery tasks."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from app.celery.tasks import (
    _check_disruptions_async,
    _rebuild_indexes_async,
    check_disruptions_and_alert,
    rebuild_route_indexes_task,
)

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
    mock_redis.aclose = AsyncMock()
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
    mock_redis.aclose = AsyncMock()
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
    mock_redis.aclose = AsyncMock()
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
    mock_redis.aclose.assert_called_once()
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
    mock_redis.aclose = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService to raise error
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(side_effect=RuntimeError("Test error"))
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Test error"):
        await _check_disruptions_async()

    # Verify resources were still closed
    mock_redis.aclose.assert_called_once()
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
    mock_redis.aclose = AsyncMock()
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
    mock_redis.aclose = AsyncMock()
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
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_closes_session_when_redis_fails(
    mock_session_factory: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test that session is closed even when Redis client creation fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis to raise error
    mock_redis_func.side_effect = RuntimeError("Redis connection failed")

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Redis connection failed"):
        await _check_disruptions_async()

    # Verify session was still closed (line 98)
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_redis_client")
@patch("app.celery.tasks.worker_session_factory")
async def test_check_disruptions_async_closes_redis_when_service_fails(
    mock_session_factory: MagicMock,
    mock_redis_func: MagicMock,
    mock_alert_class: MagicMock,
) -> None:
    """Test that Redis is closed even when AlertService instantiation fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService to raise error on instantiation
    mock_alert_class.side_effect = RuntimeError("Service init failed")

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Service init failed"):
        await _check_disruptions_async()

    # Verify both resources were closed (lines 95-98)
    mock_redis.aclose.assert_called_once()
    mock_session.close.assert_called_once()


@patch("app.celery.tasks.asyncio.run")
def test_check_disruptions_task_success_path(mock_asyncio_run: MagicMock) -> None:
    """Test the synchronous task wrapper success path."""
    mock_result = {
        "status": "success",
        "routes_checked": 5,
        "alerts_sent": 2,
        "errors": 0,
    }
    mock_asyncio_run.return_value = mock_result

    result = check_disruptions_and_alert()

    assert result == mock_result
    mock_asyncio_run.assert_called_once()


@patch("app.celery.tasks.asyncio.run")
def test_check_disruptions_task_retry_on_error(mock_asyncio_run: MagicMock) -> None:
    """Test that task retries on exception (lines 55-63)."""
    # Mock asyncio.run to raise an exception
    mock_asyncio_run.side_effect = RuntimeError("Database connection lost")

    # Create a mock Celery task instance with retry method
    task_instance = check_disruptions_and_alert

    # Execute the task and expect retry exception
    with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
        task_instance()


@patch("app.celery.tasks.asyncio.run")
def test_check_disruptions_task_logs_on_success(mock_asyncio_run: MagicMock) -> None:
    """Test that task logs completion (lines 49-52)."""
    mock_result = {
        "status": "success",
        "routes_checked": 3,
        "alerts_sent": 1,
        "errors": 0,
    }
    mock_asyncio_run.return_value = mock_result

    with patch("app.celery.tasks.logger") as mock_logger:
        result = check_disruptions_and_alert()

        assert result == mock_result
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "check_disruptions_task_completed"


@patch("app.celery.tasks.asyncio.run")
def test_check_disruptions_task_logs_on_error(mock_asyncio_run: MagicMock) -> None:
    """Test that task logs errors before retry (lines 56-61)."""
    mock_asyncio_run.side_effect = RuntimeError("Test error")

    task_instance = check_disruptions_and_alert

    with patch("app.celery.tasks.logger") as mock_logger:
        with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
            task_instance()

        # Verify error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "check_disruptions_task_failed"


# ==================== rebuild_route_indexes_task Tests ====================


def test_rebuild_indexes_task_registered() -> None:
    """Test that rebuild_route_indexes_task function exists."""
    # This is a simple test to ensure the task exists
    assert rebuild_route_indexes_task is not None


@pytest.mark.asyncio
@patch("app.celery.tasks.RouteIndexService")
@patch("app.celery.tasks.worker_session_factory")
async def test_rebuild_indexes_async_success_single_route(
    mock_session_factory: MagicMock,
    mock_service_class: MagicMock,
) -> None:
    """Test successful execution for a single route."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock RouteIndexService
    mock_service_instance = AsyncMock()
    mock_service_instance.rebuild_routes = AsyncMock(
        return_value={
            "rebuilt_count": 1,
            "failed_count": 0,
            "errors": [],
        }
    )
    mock_service_class.return_value = mock_service_instance

    # Execute async function with single route
    test_route_id = "550e8400-e29b-41d4-a716-446655440000"
    result = await _rebuild_indexes_async(test_route_id)

    # Verify result
    assert result["status"] == "success"
    assert result["rebuilt_count"] == 1
    assert result["failed_count"] == 0
    assert result["errors"] == []

    # Verify RouteIndexService was instantiated correctly
    mock_service_class.assert_called_once_with(mock_session)

    # Verify rebuild_routes was called with correct UUID
    mock_service_instance.rebuild_routes.assert_called_once()
    call_args = mock_service_instance.rebuild_routes.call_args
    assert call_args[0][0] == UUID(test_route_id)
    assert call_args[1]["auto_commit"] is True


@pytest.mark.asyncio
@patch("app.celery.tasks.RouteIndexService")
@patch("app.celery.tasks.worker_session_factory")
async def test_rebuild_indexes_async_success_all_routes(
    mock_session_factory: MagicMock,
    mock_service_class: MagicMock,
) -> None:
    """Test successful execution for all routes."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock RouteIndexService
    mock_service_instance = AsyncMock()
    mock_service_instance.rebuild_routes = AsyncMock(
        return_value={
            "rebuilt_count": 10,
            "failed_count": 0,
            "errors": [],
        }
    )
    mock_service_class.return_value = mock_service_instance

    # Execute async function with no route_id (rebuild all)
    result = await _rebuild_indexes_async(None)

    # Verify result
    assert result["status"] == "success"
    assert result["rebuilt_count"] == 10
    assert result["failed_count"] == 0
    assert result["errors"] == []

    # Verify rebuild_routes was called with None
    mock_service_instance.rebuild_routes.assert_called_once()
    call_args = mock_service_instance.rebuild_routes.call_args
    assert call_args[0][0] is None
    assert call_args[1]["auto_commit"] is True


@pytest.mark.asyncio
@patch("app.celery.tasks.RouteIndexService")
@patch("app.celery.tasks.worker_session_factory")
async def test_rebuild_indexes_async_partial_failure(
    mock_session_factory: MagicMock,
    mock_service_class: MagicMock,
) -> None:
    """Test async function when some routes fail."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock RouteIndexService with partial failure
    mock_service_instance = AsyncMock()
    mock_service_instance.rebuild_routes = AsyncMock(
        return_value={
            "rebuilt_count": 8,
            "failed_count": 2,
            "errors": ["Route 1 failed", "Route 2 failed"],
        }
    )
    mock_service_class.return_value = mock_service_instance

    # Execute async function
    result = await _rebuild_indexes_async(None)

    # Verify result shows partial_failure
    assert result["status"] == "partial_failure"
    assert result["rebuilt_count"] == 8
    assert result["failed_count"] == 2
    assert len(result["errors"]) == 2


@pytest.mark.asyncio
@patch("app.celery.tasks.worker_session_factory")
async def test_rebuild_indexes_async_invalid_uuid(
    mock_session_factory: MagicMock,
) -> None:
    """Test that invalid UUID string raises ValueError."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Execute with invalid UUID string
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        await _rebuild_indexes_async("not-a-valid-uuid")

    # Verify session was still closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.RouteIndexService")
@patch("app.celery.tasks.worker_session_factory")
async def test_rebuild_indexes_async_closes_session_on_success(
    mock_session_factory: MagicMock,
    mock_service_class: MagicMock,
) -> None:
    """Test that async function properly closes database connection."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock RouteIndexService
    mock_service_instance = AsyncMock()
    mock_service_instance.rebuild_routes = AsyncMock(
        return_value={
            "rebuilt_count": 5,
            "failed_count": 0,
            "errors": [],
        }
    )
    mock_service_class.return_value = mock_service_instance

    # Execute async function
    await _rebuild_indexes_async(None)

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.RouteIndexService")
@patch("app.celery.tasks.worker_session_factory")
async def test_rebuild_indexes_async_closes_session_on_error(
    mock_session_factory: MagicMock,
    mock_service_class: MagicMock,
) -> None:
    """Test that async function closes session even when error occurs."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock RouteIndexService to raise error
    mock_service_instance = AsyncMock()
    mock_service_instance.rebuild_routes = AsyncMock(side_effect=RuntimeError("Database error"))
    mock_service_class.return_value = mock_service_instance

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Database error"):
        await _rebuild_indexes_async(None)

    # Verify session was still closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.RouteIndexService")
@patch("app.celery.tasks.worker_session_factory")
async def test_rebuild_indexes_async_closes_session_when_service_fails(
    mock_session_factory: MagicMock,
    mock_service_class: MagicMock,
) -> None:
    """Test that session is closed even when RouteIndexService instantiation fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock RouteIndexService to raise error on instantiation
    mock_service_class.side_effect = RuntimeError("Service init failed")

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Service init failed"):
        await _rebuild_indexes_async(None)

    # Verify session was still closed
    mock_session.close.assert_called_once()


@patch("app.celery.tasks.asyncio.run")
def test_rebuild_indexes_task_success_path(mock_asyncio_run: MagicMock) -> None:
    """Test the synchronous task wrapper success path."""
    mock_result = {
        "status": "success",
        "rebuilt_count": 5,
        "failed_count": 0,
        "errors": [],
    }
    mock_asyncio_run.return_value = mock_result

    result = rebuild_route_indexes_task(route_id="550e8400-e29b-41d4-a716-446655440000")

    assert result == mock_result
    mock_asyncio_run.assert_called_once()


@patch("app.celery.tasks.asyncio.run")
def test_rebuild_indexes_task_retry_on_error(mock_asyncio_run: MagicMock) -> None:
    """Test that task retries on exception."""
    # Mock asyncio.run to raise an exception
    mock_asyncio_run.side_effect = RuntimeError("Database connection lost")

    # Create a mock Celery task instance with retry method
    task_instance = rebuild_route_indexes_task

    # Execute the task and expect retry exception
    with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
        task_instance(route_id=None)


@patch("app.celery.tasks.asyncio.run")
def test_rebuild_indexes_task_logs_on_success(mock_asyncio_run: MagicMock) -> None:
    """Test that task logs completion."""
    mock_result = {
        "status": "success",
        "rebuilt_count": 3,
        "failed_count": 0,
        "errors": [],
    }
    mock_asyncio_run.return_value = mock_result

    with patch("app.celery.tasks.logger") as mock_logger:
        result = rebuild_route_indexes_task(route_id=None)

        assert result == mock_result
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "rebuild_indexes_task_completed"


@patch("app.celery.tasks.asyncio.run")
def test_rebuild_indexes_task_logs_on_error(mock_asyncio_run: MagicMock) -> None:
    """Test that task logs errors before retry."""
    mock_asyncio_run.side_effect = RuntimeError("Test error")

    task_instance = rebuild_route_indexes_task

    with patch("app.celery.tasks.logger") as mock_logger:
        with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
            task_instance(route_id="550e8400-e29b-41d4-a716-446655440000")

        # Verify error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "rebuild_indexes_task_failed"
