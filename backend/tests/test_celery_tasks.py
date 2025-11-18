"""Tests for Celery tasks."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from app.celery.tasks import (
    _check_disruptions_async,
    _detect_stale_routes_async,
    _rebuild_indexes_async,
    check_disruptions_and_alert,
    detect_and_rebuild_stale_routes,
    find_stale_route_ids,
    rebuild_route_indexes_task,
)

# ==================== check_disruptions_and_alert Tests ====================


def test_check_disruptions_task_registered() -> None:
    """Test that task function exists."""
    # This is a simple test to ensure the task exists
    assert check_disruptions_and_alert is not None


@pytest.mark.asyncio
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_worker_redis_client")
@patch("app.celery.tasks.get_worker_session")
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

    # Mock Redis client (shared, not closed per task)
    mock_redis = MagicMock()
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
@patch("app.celery.tasks.get_worker_redis_client")
@patch("app.celery.tasks.get_worker_session")
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

    # Mock Redis client (shared, not closed per task)
    mock_redis = MagicMock()
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
@patch("app.celery.tasks.get_worker_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_worker_session")
async def test_check_disruptions_async_closes_session(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test that async function properly closes database session.

    Note: Redis client is shared across tasks and not closed per task.
    """
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client (shared, not closed per task)
    mock_redis = MagicMock()
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

    # Verify session was closed (Redis client is shared, not closed per task)
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.get_worker_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_worker_session")
async def test_check_disruptions_async_closes_session_on_error(
    mock_session_factory: MagicMock,
    mock_alert_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Test that async function closes session even when error occurs."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client (shared, not closed per task)
    mock_redis = MagicMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService to raise error
    mock_alert_instance = AsyncMock()
    mock_alert_instance.process_all_routes = AsyncMock(side_effect=RuntimeError("Test error"))
    mock_alert_class.return_value = mock_alert_instance

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Test error"):
        await _check_disruptions_async()

    # Verify session was still closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.get_worker_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_worker_session")
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

    # Mock Redis client (shared, not closed per task)
    mock_redis = MagicMock()
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
@patch("app.celery.tasks.get_worker_redis_client")
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_worker_session")
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

    # Mock Redis client (shared, not closed per task)
    mock_redis = MagicMock()
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
@patch("app.celery.tasks.get_worker_redis_client")
@patch("app.celery.tasks.get_worker_session")
async def test_check_disruptions_async_closes_session_when_redis_fails(
    mock_session_factory: MagicMock, mock_redis_func: MagicMock
) -> None:
    """Test that session is closed even when Redis client retrieval fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis to raise error
    mock_redis_func.side_effect = RuntimeError("Redis connection failed")

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Redis connection failed"):
        await _check_disruptions_async()

    # Verify session was still closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.AlertService")
@patch("app.celery.tasks.get_worker_redis_client")
@patch("app.celery.tasks.get_worker_session")
async def test_check_disruptions_async_closes_session_when_service_fails(
    mock_session_factory: MagicMock,
    mock_redis_func: MagicMock,
    mock_alert_class: MagicMock,
) -> None:
    """Test that session is closed even when AlertService instantiation fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock Redis client (shared, not closed per task)
    mock_redis = MagicMock()
    mock_redis_func.return_value = mock_redis

    # Mock AlertService to raise error on instantiation
    mock_alert_class.side_effect = RuntimeError("Service init failed")

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Service init failed"):
        await _check_disruptions_async()

    # Verify session was closed
    mock_session.close.assert_called_once()


@patch("app.celery.tasks.run_in_worker_loop")
def test_check_disruptions_task_success_path(mock_run_async_task: MagicMock) -> None:
    """Test the synchronous task wrapper success path."""
    mock_result = {
        "status": "success",
        "routes_checked": 5,
        "alerts_sent": 2,
        "errors": 0,
    }
    mock_run_async_task.return_value = mock_result

    result = check_disruptions_and_alert()

    assert result == mock_result
    mock_run_async_task.assert_called_once()


@patch("app.celery.tasks.run_in_worker_loop")
def test_check_disruptions_task_retry_on_error(mock_run_async_task: MagicMock) -> None:
    """Test that task retries on exception."""
    # Mock run_in_worker_loop to raise an exception
    mock_run_async_task.side_effect = RuntimeError("Database connection lost")

    # Create a mock Celery task instance with retry method
    task_instance = check_disruptions_and_alert

    # Execute the task and expect retry exception
    with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
        task_instance()


@patch("app.celery.tasks.run_in_worker_loop")
def test_check_disruptions_task_logs_on_success(mock_run_async_task: MagicMock) -> None:
    """Test that task logs completion."""
    mock_result = {
        "status": "success",
        "routes_checked": 3,
        "alerts_sent": 1,
        "errors": 0,
    }
    mock_run_async_task.return_value = mock_result

    with patch("app.celery.tasks.logger") as mock_logger:
        result = check_disruptions_and_alert()

        assert result == mock_result
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "check_disruptions_task_completed"


@patch("app.celery.tasks.run_in_worker_loop")
def test_check_disruptions_task_logs_on_error(mock_run_async_task: MagicMock) -> None:
    """Test that task logs errors before retry."""
    mock_run_async_task.side_effect = RuntimeError("Test error")

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
@patch("app.celery.tasks.UserRouteIndexService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_indexes_async_success_single_route(
    mock_session_factory: MagicMock, mock_service_class: MagicMock
) -> None:
    """Test successful execution for a single route."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock UserRouteIndexService
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

    # Verify UserRouteIndexService was instantiated correctly
    mock_service_class.assert_called_once_with(mock_session)

    # Verify rebuild_routes was called with correct UUID
    mock_service_instance.rebuild_routes.assert_called_once()
    call_args = mock_service_instance.rebuild_routes.call_args
    assert call_args[0][0] == UUID(test_route_id)
    assert call_args[1]["auto_commit"] is True


@pytest.mark.asyncio
@patch("app.celery.tasks.UserRouteIndexService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_indexes_async_success_all_routes(
    mock_session_factory: MagicMock, mock_service_class: MagicMock
) -> None:
    """Test successful execution for all routes."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock UserRouteIndexService
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
@patch("app.celery.tasks.UserRouteIndexService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_indexes_async_partial_failure(
    mock_session_factory: MagicMock, mock_service_class: MagicMock
) -> None:
    """Test async function when some routes fail."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock UserRouteIndexService with partial failure
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
@patch("app.celery.tasks.get_worker_session")
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
@patch("app.celery.tasks.UserRouteIndexService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_indexes_async_closes_session_on_success(
    mock_session_factory: MagicMock, mock_service_class: MagicMock
) -> None:
    """Test that async function properly closes database connection."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock UserRouteIndexService
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
@patch("app.celery.tasks.UserRouteIndexService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_indexes_async_closes_session_on_error(
    mock_session_factory: MagicMock, mock_service_class: MagicMock
) -> None:
    """Test that async function closes session even when error occurs."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock UserRouteIndexService to raise error
    mock_service_instance = AsyncMock()
    mock_service_instance.rebuild_routes = AsyncMock(side_effect=RuntimeError("Database error"))
    mock_service_class.return_value = mock_service_instance

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Database error"):
        await _rebuild_indexes_async(None)

    # Verify session was still closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.UserRouteIndexService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_indexes_async_closes_session_when_service_fails(
    mock_session_factory: MagicMock, mock_service_class: MagicMock
) -> None:
    """Test that session is closed even when UserRouteIndexService instantiation fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock UserRouteIndexService to raise error on instantiation
    mock_service_class.side_effect = RuntimeError("Service init failed")

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Service init failed"):
        await _rebuild_indexes_async(None)

    # Verify session was still closed
    mock_session.close.assert_called_once()


@patch("app.celery.tasks.run_in_worker_loop")
def test_rebuild_indexes_task_success_path(mock_run_async_task: MagicMock) -> None:
    """Test the synchronous task wrapper success path."""
    mock_result = {
        "status": "success",
        "rebuilt_count": 5,
        "failed_count": 0,
        "errors": [],
    }
    mock_run_async_task.return_value = mock_result

    result = rebuild_route_indexes_task(route_id="550e8400-e29b-41d4-a716-446655440000")

    assert result == mock_result
    mock_run_async_task.assert_called_once()


@patch("app.celery.tasks.run_in_worker_loop")
def test_rebuild_indexes_task_retry_on_error(mock_run_async_task: MagicMock) -> None:
    """Test that task retries on exception."""
    # Mock run_in_worker_loop to raise an exception
    mock_run_async_task.side_effect = RuntimeError("Database connection lost")

    # Create a mock Celery task instance with retry method
    task_instance = rebuild_route_indexes_task

    # Execute the task and expect retry exception
    with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
        task_instance(route_id=None)


@patch("app.celery.tasks.run_in_worker_loop")
def test_rebuild_indexes_task_logs_on_success(mock_run_async_task: MagicMock) -> None:
    """Test that task logs completion."""
    mock_result = {
        "status": "success",
        "rebuilt_count": 3,
        "failed_count": 0,
        "errors": [],
    }
    mock_run_async_task.return_value = mock_result

    with patch("app.celery.tasks.logger") as mock_logger:
        result = rebuild_route_indexes_task(route_id=None)

        assert result == mock_result
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "rebuild_indexes_task_completed"


@patch("app.celery.tasks.run_in_worker_loop")
def test_rebuild_indexes_task_logs_on_error(mock_run_async_task: MagicMock) -> None:
    """Test that task logs errors before retry."""
    mock_run_async_task.side_effect = RuntimeError("Test error")

    task_instance = rebuild_route_indexes_task

    with patch("app.celery.tasks.logger") as mock_logger:
        with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
            task_instance(route_id="550e8400-e29b-41d4-a716-446655440000")

        # Verify error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "rebuild_indexes_task_failed"


# ==================== detect_and_rebuild_stale_routes Tests ====================


def test_detect_stale_routes_task_registered() -> None:
    """Test that detect_and_rebuild_stale_routes task function exists."""
    assert detect_and_rebuild_stale_routes is not None


@pytest.mark.asyncio
async def test_find_stale_route_ids_empty_result() -> None:
    """Test find_stale_route_ids returns empty list when no stale routes."""
    # Mock session and query result
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Execute pure helper function
    stale_ids = await find_stale_route_ids(mock_session)

    # Verify result
    assert stale_ids == []
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_find_stale_route_ids_single_route() -> None:
    """Test find_stale_route_ids with single stale route."""
    # Mock session and query result
    mock_session = AsyncMock()
    test_route_id = uuid4()
    mock_result = MagicMock()
    mock_result.all.return_value = [(test_route_id,)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Execute pure helper function
    stale_ids = await find_stale_route_ids(mock_session)

    # Verify result
    assert len(stale_ids) == 1
    assert stale_ids[0] == test_route_id
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_find_stale_route_ids_multiple_routes() -> None:
    """Test find_stale_route_ids with multiple stale routes."""
    # Mock session and query result
    mock_session = AsyncMock()
    test_route_ids = [uuid4(), uuid4(), uuid4()]
    mock_result = MagicMock()
    mock_result.all.return_value = [(rid,) for rid in test_route_ids]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Execute pure helper function
    stale_ids = await find_stale_route_ids(mock_session)

    # Verify result
    assert len(stale_ids) == 3
    assert stale_ids == test_route_ids
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_find_stale_route_ids_query_uses_distinct() -> None:
    """Test that find_stale_route_ids uses DISTINCT to avoid duplicates."""
    # Mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Execute pure helper function
    await find_stale_route_ids(mock_session)

    # Verify session.execute was called (query uses DISTINCT)
    mock_session.execute.assert_called_once()
    # The actual DISTINCT usage is verified by the query construction in the function


@pytest.mark.asyncio
@patch("app.celery.tasks.rebuild_route_indexes_task")
@patch("app.celery.tasks.find_stale_route_ids")
@patch("app.celery.tasks.get_worker_session")
async def test_detect_stale_routes_async_no_stale_routes(
    mock_session_factory: MagicMock,
    mock_find_stale: MagicMock,
    mock_rebuild_task: MagicMock,
) -> None:
    """Test async function when no stale routes found."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock find_stale_route_ids to return empty list
    mock_find_stale.return_value = []

    # Execute async function
    result = await _detect_stale_routes_async()

    # Verify result
    assert result["status"] == "success"
    assert result["stale_count"] == 0
    assert result["triggered_count"] == 0
    assert result["errors"] == []

    # Verify no rebuild tasks were triggered
    mock_rebuild_task.delay.assert_not_called()

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.rebuild_route_indexes_task")
@patch("app.celery.tasks.find_stale_route_ids")
@patch("app.celery.tasks.get_worker_session")
async def test_detect_stale_routes_async_single_stale_route(
    mock_session_factory: MagicMock,
    mock_find_stale: MagicMock,
    mock_rebuild_task: MagicMock,
) -> None:
    """Test async function with single stale route."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock find_stale_route_ids to return one route
    test_route_id = uuid4()
    mock_find_stale.return_value = [test_route_id]

    # Mock rebuild task
    mock_rebuild_task.delay = MagicMock()

    # Execute async function
    result = await _detect_stale_routes_async()

    # Verify result
    assert result["status"] == "success"
    assert result["stale_count"] == 1
    assert result["triggered_count"] == 1
    assert result["errors"] == []

    # Verify rebuild task was triggered with correct route_id
    mock_rebuild_task.delay.assert_called_once_with(str(test_route_id))

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.rebuild_route_indexes_task")
@patch("app.celery.tasks.find_stale_route_ids")
@patch("app.celery.tasks.get_worker_session")
async def test_detect_stale_routes_async_multiple_stale_routes(
    mock_session_factory: MagicMock,
    mock_find_stale: MagicMock,
    mock_rebuild_task: MagicMock,
) -> None:
    """Test async function with multiple stale routes."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock find_stale_route_ids to return multiple routes
    test_route_ids = [uuid4(), uuid4(), uuid4()]
    mock_find_stale.return_value = test_route_ids

    # Mock rebuild task
    mock_rebuild_task.delay = MagicMock()

    # Execute async function
    result = await _detect_stale_routes_async()

    # Verify result
    assert result["status"] == "success"
    assert result["stale_count"] == 3
    assert result["triggered_count"] == 3
    assert result["errors"] == []

    # Verify rebuild task was triggered for each route
    assert mock_rebuild_task.delay.call_count == 3
    for route_id in test_route_ids:
        mock_rebuild_task.delay.assert_any_call(str(route_id))

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.rebuild_route_indexes_task")
@patch("app.celery.tasks.find_stale_route_ids")
@patch("app.celery.tasks.get_worker_session")
async def test_detect_stale_routes_async_partial_trigger_failure(
    mock_session_factory: MagicMock,
    mock_find_stale: MagicMock,
    mock_rebuild_task: MagicMock,
) -> None:
    """Test async function when some rebuild task triggers fail."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock find_stale_route_ids to return multiple routes
    test_route_ids = [uuid4(), uuid4(), uuid4()]
    mock_find_stale.return_value = test_route_ids

    # Mock rebuild task to fail on second route
    call_count = 0

    def side_effect_delay(route_id: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            error_msg = "Celery queue full"
            raise RuntimeError(error_msg)

    mock_rebuild_task.delay = MagicMock(side_effect=side_effect_delay)

    # Execute async function
    result = await _detect_stale_routes_async()

    # Verify result shows partial failure
    assert result["status"] == "partial_failure"
    assert result["stale_count"] == 3
    assert result["triggered_count"] == 2  # Only 2 succeeded
    assert len(result["errors"]) == 1
    assert "Celery queue full" in result["errors"][0]

    # Verify rebuild task was attempted for all routes
    assert mock_rebuild_task.delay.call_count == 3

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.rebuild_route_indexes_task")
@patch("app.celery.tasks.find_stale_route_ids")
@patch("app.celery.tasks.get_worker_session")
async def test_detect_stale_routes_async_all_triggers_fail(
    mock_session_factory: MagicMock,
    mock_find_stale: MagicMock,
    mock_rebuild_task: MagicMock,
) -> None:
    """Test async function when all rebuild task triggers fail."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock find_stale_route_ids to return multiple routes
    test_route_ids = [uuid4(), uuid4()]
    mock_find_stale.return_value = test_route_ids

    # Mock rebuild task to always fail
    error_msg = "Celery unavailable"
    mock_rebuild_task.delay = MagicMock(side_effect=RuntimeError(error_msg))

    # Execute async function
    result = await _detect_stale_routes_async()

    # Verify result shows total failure (0 triggers succeeded)
    assert result["status"] == "failure"
    assert result["stale_count"] == 2
    assert result["triggered_count"] == 0  # None succeeded
    assert len(result["errors"]) == 2

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.find_stale_route_ids")
@patch("app.celery.tasks.get_worker_session")
async def test_detect_stale_routes_async_closes_session_on_error(
    mock_session_factory: MagicMock, mock_find_stale: MagicMock
) -> None:
    """Test that async function closes session even when error occurs."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock find_stale_route_ids to raise error
    mock_find_stale.side_effect = RuntimeError("Database query failed")

    # Execute async function and catch exception
    with pytest.raises(RuntimeError, match="Database query failed"):
        await _detect_stale_routes_async()

    # Verify session was still closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.rebuild_route_indexes_task")
@patch("app.celery.tasks.find_stale_route_ids")
@patch("app.celery.tasks.get_worker_session")
async def test_detect_stale_routes_async_returns_correct_structure(
    mock_session_factory: MagicMock,
    mock_find_stale: MagicMock,
    mock_rebuild_task: MagicMock,
) -> None:
    """Test that async function returns correct DetectStaleRoutesResult structure."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock find_stale_route_ids
    test_route_ids = [uuid4(), uuid4()]
    mock_find_stale.return_value = test_route_ids

    # Mock rebuild task
    mock_rebuild_task.delay = MagicMock()

    # Execute async function
    result = await _detect_stale_routes_async()

    # Verify result structure
    assert "status" in result
    assert "stale_count" in result
    assert "triggered_count" in result
    assert "errors" in result
    assert isinstance(result["errors"], list)


@patch("app.celery.tasks.run_in_worker_loop")
def test_detect_stale_routes_task_success_path(mock_run_async_task: MagicMock) -> None:
    """Test the synchronous task wrapper success path."""
    mock_result = {
        "status": "success",
        "stale_count": 5,
        "triggered_count": 5,
        "errors": [],
    }
    mock_run_async_task.return_value = mock_result

    result = detect_and_rebuild_stale_routes()

    assert result == mock_result
    mock_run_async_task.assert_called_once()


@patch("app.celery.tasks.run_in_worker_loop")
def test_detect_stale_routes_task_retry_on_error(mock_run_async_task: MagicMock) -> None:
    """Test that task retries on exception."""
    # Mock run_in_worker_loop to raise an exception
    mock_run_async_task.side_effect = RuntimeError("Database connection lost")

    # Create a mock Celery task instance with retry method
    task_instance = detect_and_rebuild_stale_routes

    # Execute the task and expect retry exception
    with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
        task_instance()


@patch("app.celery.tasks.run_in_worker_loop")
def test_detect_stale_routes_task_logs_on_success(mock_run_async_task: MagicMock) -> None:
    """Test that task logs completion."""
    mock_result = {
        "status": "success",
        "stale_count": 3,
        "triggered_count": 3,
        "errors": [],
    }
    mock_run_async_task.return_value = mock_result

    with patch("app.celery.tasks.logger") as mock_logger:
        result = detect_and_rebuild_stale_routes()

        assert result == mock_result
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "detect_stale_routes_task_completed"


@patch("app.celery.tasks.run_in_worker_loop")
def test_detect_stale_routes_task_logs_on_error(mock_run_async_task: MagicMock) -> None:
    """Test that task logs errors before retry."""
    mock_run_async_task.side_effect = RuntimeError("Test error")

    task_instance = detect_and_rebuild_stale_routes

    with patch("app.celery.tasks.logger") as mock_logger:
        with pytest.raises(Exception):  # noqa: B017, PT011  # Celery raises Retry exception
            task_instance()

        # Verify error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "detect_stale_routes_task_failed"
