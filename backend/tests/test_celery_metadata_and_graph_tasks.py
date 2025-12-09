"""Tests for metadata refresh and graph rebuild Celery tasks."""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.celery.tasks import (
    _rebuild_graph_async,
    _refresh_metadata_async,
)
from app.services.tfl_service import MetadataChangeDetectedError

# ==================== refresh_tfl_metadata_task Tests ====================


@pytest.mark.asyncio
@patch("app.celery.tasks.TfLService")
@patch("app.celery.tasks.get_worker_session")
async def test_refresh_metadata_async_success_no_changes(
    mock_session_factory: MagicMock,
    mock_tfl_service_class: MagicMock,
) -> None:
    """Test successful metadata refresh with no changes detected."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock TfLService
    mock_tfl_service = AsyncMock()
    mock_tfl_service.refresh_metadata_with_change_detection = AsyncMock(
        return_value=(10, 5, 3)  # counts: severity_codes, categories, stop_types
    )
    mock_tfl_service_class.return_value = mock_tfl_service

    # Execute async function
    result = await _refresh_metadata_async()

    # Verify result
    assert result["status"] == "success"
    assert result["severity_codes_count"] == 10
    assert result["disruption_categories_count"] == 5
    assert result["stop_types_count"] == 3
    assert result["changes_detected"] is False
    assert result["error"] is None

    # Verify TfLService was instantiated correctly
    mock_tfl_service_class.assert_called_once_with(db=mock_session)

    # Verify refresh method was called
    mock_tfl_service.refresh_metadata_with_change_detection.assert_called_once()

    # Verify session was committed and closed
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.TfLService")
@patch("app.celery.tasks.get_worker_session")
async def test_refresh_metadata_async_changes_detected(
    mock_session_factory: MagicMock,
    mock_tfl_service_class: MagicMock,
) -> None:
    """Test metadata refresh when changes are detected."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock TfLService to raise MetadataChangeDetectedError
    mock_tfl_service = AsyncMock()
    test_error = MetadataChangeDetectedError(
        "TfL metadata changed unexpectedly: severity_codes",
        details={
            "changed_types": ["severity_codes"],
            "severity_codes": {
                "before_count": 10,
                "after_count": 11,
                "before_hash": "abc123",
                "after_hash": "def456",
            },
        },
    )
    mock_tfl_service.refresh_metadata_with_change_detection = AsyncMock(side_effect=test_error)
    mock_tfl_service_class.return_value = mock_tfl_service

    # Execute async function - should NOT raise exception, should return error result
    result = await _refresh_metadata_async()

    # Verify result indicates changes detected
    assert result["status"] == "changes_detected"
    assert result["changes_detected"] is True
    assert result["error"] is not None
    assert "severity_codes" in result["error"]

    # Verify session was closed (but not committed due to exception)
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.TfLService")
@patch("app.celery.tasks.get_worker_session")
async def test_refresh_metadata_async_ensures_session_cleanup(
    mock_session_factory: MagicMock,
    mock_tfl_service_class: MagicMock,
) -> None:
    """Test that session is always closed even on generic exception."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock TfLService to raise generic exception
    mock_tfl_service = AsyncMock()
    mock_tfl_service.refresh_metadata_with_change_detection = AsyncMock(side_effect=Exception("Database error"))
    mock_tfl_service_class.return_value = mock_tfl_service

    # Execute async function - generic exceptions will propagate up
    # The test suppresses them to verify session cleanup still happens
    with contextlib.suppress(Exception):
        await _refresh_metadata_async()

    # Verify session was closed
    mock_session.close.assert_called_once()


# ==================== rebuild_network_graph_task Tests ====================


@pytest.mark.asyncio
@patch("app.celery.tasks.detect_and_rebuild_stale_routes")
@patch("app.celery.tasks.TfLService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_graph_async_success(
    mock_session_factory: MagicMock,
    mock_tfl_service_class: MagicMock,
    mock_stale_detection_task: MagicMock,
) -> None:
    """Test successful graph rebuild."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock TfLService
    mock_tfl_service = AsyncMock()
    mock_tfl_service.build_station_graph = AsyncMock(
        return_value={
            "lines_count": 12,
            "connections_count": 500,
        }
    )
    mock_tfl_service_class.return_value = mock_tfl_service

    # Mock stale detection task
    mock_stale_detection_task.delay = MagicMock()

    # Execute async function
    result = await _rebuild_graph_async()

    # Verify result
    assert result["status"] == "success"
    assert result["lines_count"] == 12
    assert result["connections_count"] == 500
    assert result["stale_detection_triggered"] is True
    assert result["error"] is None

    # Verify TfLService was instantiated correctly
    mock_tfl_service_class.assert_called_once_with(db=mock_session)

    # Verify build_station_graph was called
    mock_tfl_service.build_station_graph.assert_called_once()

    # Verify stale detection was triggered
    mock_stale_detection_task.delay.assert_called_once()

    # Verify session was committed and closed
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.detect_and_rebuild_stale_routes")
@patch("app.celery.tasks.TfLService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_graph_async_handles_stale_detection_failure(
    mock_session_factory: MagicMock,
    mock_tfl_service_class: MagicMock,
    mock_stale_detection_task: MagicMock,
) -> None:
    """Test that graph rebuild continues even if stale detection triggering fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock TfLService
    mock_tfl_service = AsyncMock()
    mock_tfl_service.build_station_graph = AsyncMock(return_value={"lines_count": 12, "connections_count": 500})
    mock_tfl_service_class.return_value = mock_tfl_service

    # Mock stale detection task to fail
    mock_stale_detection_task.delay = MagicMock(side_effect=Exception("Task queue error"))

    # Execute async function - should not fail
    result = await _rebuild_graph_async()

    # Verify result shows graph rebuild succeeded but stale detection failed
    assert result["status"] == "success"
    assert result["lines_count"] == 12
    assert result["stale_detection_triggered"] is False  # Failed to trigger
    assert result["error"] is None  # Graph rebuild itself succeeded

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.TfLService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_graph_async_handles_build_failure(
    mock_session_factory: MagicMock,
    mock_tfl_service_class: MagicMock,
) -> None:
    """Test that graph rebuild handles build failures gracefully."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock TfLService to fail
    mock_tfl_service = AsyncMock()
    mock_tfl_service.build_station_graph = AsyncMock(side_effect=Exception("TfL API error"))
    mock_tfl_service_class.return_value = mock_tfl_service

    # Execute async function
    result = await _rebuild_graph_async()

    # Verify result indicates failure
    assert result["status"] == "failure"
    assert result["lines_count"] == 0
    assert result["connections_count"] == 0
    assert result["stale_detection_triggered"] is False
    assert result["error"] is not None
    assert "TfL API error" in result["error"]

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.celery.tasks.TfLService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_graph_async_ensures_session_cleanup_on_failure(
    mock_session_factory: MagicMock,
    mock_tfl_service_class: MagicMock,
) -> None:
    """Test that session is always closed even when graph rebuild fails."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock TfLService to raise exception
    mock_tfl_service = AsyncMock()
    mock_tfl_service.build_station_graph = AsyncMock(side_effect=Exception("Network error"))
    mock_tfl_service_class.return_value = mock_tfl_service

    # Execute async function
    result = await _rebuild_graph_async()

    # Verify result shows failure
    assert result["status"] == "failure"

    # Verify session was closed (even though build failed)
    mock_session.close.assert_called_once()

    # Verify commit was NOT called (no successful build)
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
@patch("app.celery.tasks.detect_and_rebuild_stale_routes")
@patch("app.celery.tasks.TfLService")
@patch("app.celery.tasks.get_worker_session")
async def test_rebuild_graph_async_full_success_flow(
    mock_session_factory: MagicMock,
    mock_tfl_service_class: MagicMock,
    mock_stale_detection_task: MagicMock,
) -> None:
    """Test complete success flow: graph rebuild + stale detection + cleanup."""
    # Mock database session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session_factory.return_value = mock_session

    # Mock TfLService
    mock_tfl_service = AsyncMock()
    mock_tfl_service.build_station_graph = AsyncMock(
        return_value={
            "lines_count": 15,
            "connections_count": 650,
        }
    )
    mock_tfl_service_class.return_value = mock_tfl_service

    # Mock stale detection task
    mock_stale_detection_task.delay = MagicMock()

    # Execute async function
    result = await _rebuild_graph_async()

    # Verify complete flow
    assert result["status"] == "success"
    assert result["lines_count"] == 15
    assert result["connections_count"] == 650
    assert result["stale_detection_triggered"] is True
    assert result["error"] is None

    # Verify all steps executed in order
    mock_tfl_service_class.assert_called_once()
    mock_tfl_service.build_station_graph.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_stale_detection_task.delay.assert_called_once()
    mock_session.close.assert_called_once()
