"""Tests for Alert Service OpenTelemetry instrumentation."""

import uuid
from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.user_route import UserRoute, UserRouteSchedule
from app.schemas.tfl import DisruptionResponse
from app.services.alert_service import AlertService, warm_up_line_state_cache
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from tests.helpers.otel import assert_span_status


class TestAlertServiceProcessAllRoutesOtelSpans:
    """Test class for Alert Service process_all_routes() OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_process_all_routes_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that process_all_routes creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Mock the new helper methods after refactoring
        alert_svc._get_active_routes = AsyncMock(return_value=[])
        alert_svc._fetch_global_disruption_data = AsyncMock(return_value=([], set()))

        await alert_svc.process_all_routes()

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.process_all_routes"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "alert-service"
        assert span.attributes["alert.routes_checked"] == 0
        assert span.attributes["alert.alerts_sent"] == 0
        assert span.attributes["alert.errors"] == 0

    @pytest.mark.asyncio
    async def test_process_all_routes_handles_exception_gracefully(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span has OK status even when processing has errors (graceful degradation)."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Mock method to raise exception
        alert_svc._get_active_routes = AsyncMock(side_effect=Exception("Database connection error"))

        await alert_svc.process_all_routes()

        # Verify span has OK status (graceful error handling - method doesn't raise)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.process_all_routes"
        assert_span_status(span, StatusCode.OK)  # Method returns successfully with errors tracked
        # Verify error count is captured in attributes
        assert span.attributes is not None
        assert span.attributes["alert.errors"] == 1

    @pytest.mark.asyncio
    async def test_process_all_routes_mixed_success_and_failure(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that process_all_routes records stats and span attributes for mixed success/failure routes."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Mock database execute for get_active_children_for_parents query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # No schedules
        mock_db.execute.return_value = mock_result

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create two fake routes - one succeeds, one fails
        successful_route = MagicMock(spec=UserRoute)
        successful_route.id = uuid.uuid4()
        successful_route.name = "Successful Route"

        failing_route = MagicMock(spec=UserRoute)
        failing_route.id = uuid.uuid4()
        failing_route.name = "Failing Route"

        # Mock _get_active_routes to return both routes
        alert_svc._get_active_routes = AsyncMock(return_value=[successful_route, failing_route])

        # Mock _fetch_global_disruption_data (refactored method)
        alert_svc._fetch_global_disruption_data = AsyncMock(return_value=set())

        # Mock _process_single_route: succeed for first route, fail for second
        # Updated signature includes schedules parameter
        async def mock_process_route(
            route: UserRoute,
            schedules: list,
            disabled_severity_pairs: set,
        ) -> tuple[int, bool]:
            if route is successful_route:
                return 3, False  # 3 alerts sent, no error
            if route is failing_route:
                return 0, True  # No alerts sent, error occurred
            return 0, False

        alert_svc._process_single_route = AsyncMock(side_effect=mock_process_route)

        # Act
        stats = await alert_svc.process_all_routes()

        # Assert stats reflect both success and failure
        assert stats["routes_checked"] == 2
        assert stats["alerts_sent"] == 3  # Only from successful route
        assert stats["errors"] == 1  # One route failed

        # Assert OTEL span attributes reflect the same accounting
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.process_all_routes"
        assert_span_status(span, StatusCode.OK)  # Overall process still succeeds

        attrs = span.attributes
        assert attrs is not None
        assert attrs["alert.routes_checked"] == 2
        assert attrs["alert.alerts_sent"] == 3
        assert attrs["alert.errors"] == 1


class TestAlertServiceSendAlertsForRouteOtelSpans:
    """Test class for Alert Service _send_alerts_for_route() OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_send_alerts_for_route_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that _send_alerts_for_route creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_redis = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock route
        route_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_route = MagicMock(spec=UserRoute)
        mock_route.id = route_id
        mock_route.user_id = user_id
        mock_route.name = "Test Route"
        mock_route.notification_preferences = []  # No preferences
        mock_route.timezone = "Europe/London"

        # Create mock schedule
        schedule_id = uuid.uuid4()
        mock_schedule = MagicMock(spec=UserRouteSchedule)
        mock_schedule.id = schedule_id
        mock_schedule.start_time = time(9, 0)
        mock_schedule.end_time = time(17, 0)

        # Mock disruptions
        mock_disruptions = []

        await alert_svc._send_alerts_for_route(
            route=mock_route,
            schedule=mock_schedule,
            disruptions=mock_disruptions,
        )

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.send_for_route"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "alert-service"
        assert span.attributes["alert.route_id"] == str(route_id)
        assert span.attributes["alert.route_name"] == "Test Route"
        assert span.attributes["alert.disruption_count"] == 0
        assert span.attributes["alert.preference_count"] == 0
        assert span.attributes["alert.alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_send_alerts_for_route_with_preferences(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span captures preference count correctly."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_redis = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock route with preferences
        route_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_route = MagicMock(spec=UserRoute)
        mock_route.id = route_id
        mock_route.user_id = user_id
        mock_route.name = "Test Route"
        mock_route.timezone = "Europe/London"

        # Create mock preferences
        mock_pref1 = MagicMock()
        mock_pref1.id = uuid.uuid4()
        mock_pref2 = MagicMock()
        mock_pref2.id = uuid.uuid4()
        mock_route.notification_preferences = [mock_pref1, mock_pref2]

        # Create mock schedule
        schedule_id = uuid.uuid4()
        mock_schedule = MagicMock(spec=UserRouteSchedule)
        mock_schedule.id = schedule_id
        mock_schedule.start_time = time(9, 0)
        mock_schedule.end_time = time(17, 0)

        # Mock disruptions
        mock_disruptions = [MagicMock()]

        # Mock helper methods
        alert_svc._get_verified_contact = AsyncMock(return_value=None)  # No contact info
        alert_svc._store_alert_state = AsyncMock()

        await alert_svc._send_alerts_for_route(
            route=mock_route,
            schedule=mock_schedule,
            disruptions=mock_disruptions,
        )

        # Verify span attributes include preference count
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.attributes is not None
        assert span.attributes["alert.preference_count"] == 2
        assert span.attributes["alert.disruption_count"] == 1

    @pytest.mark.asyncio
    async def test_send_alerts_for_route_handles_exception_gracefully(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span has OK status even when errors occur (graceful degradation)."""
        _, exporter = otel_enabled_provider

        # Create mock database session that fails on commit
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock(side_effect=Exception("Database error"))
        mock_db.rollback = AsyncMock()
        mock_redis = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock route with preferences to trigger commit path
        route_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_route = MagicMock(spec=UserRoute)
        mock_route.id = route_id
        mock_route.user_id = user_id
        mock_route.name = "Test Route"
        mock_route.timezone = "Europe/London"

        # Add mock preference to trigger database commit
        mock_pref = MagicMock()
        mock_pref.id = uuid.uuid4()
        mock_route.notification_preferences = [mock_pref]

        # Create mock schedule
        schedule_id = uuid.uuid4()
        mock_schedule = MagicMock(spec=UserRouteSchedule)
        mock_schedule.id = schedule_id
        mock_schedule.start_time = time(9, 0)
        mock_schedule.end_time = time(17, 0)

        mock_disruptions = []

        # Mock helper method to return None (no contact)
        alert_svc._get_verified_contact = AsyncMock(return_value=None)

        await alert_svc._send_alerts_for_route(
            route=mock_route,
            schedule=mock_schedule,
            disruptions=mock_disruptions,
        )

        # Verify span has OK status (method handles exceptions internally)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.send_for_route"
        assert_span_status(span, StatusCode.OK)  # Method returns successfully even with errors
        # Verify attributes show 0 alerts sent
        assert span.attributes is not None
        assert span.attributes["alert.alerts_sent"] == 0

        # Verify rollback was called
        assert mock_db.rollback.called

    @pytest.mark.asyncio
    async def test_send_alerts_for_route_inspect_fallback(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span works correctly when inspect() fails (plain Mock without SQLAlchemy state)."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_redis = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Use a plain MagicMock without spec (forces inspect() to fail and use fallback)
        route_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_route = MagicMock()  # No spec - inspect will fail
        mock_route.id = route_id
        mock_route.user_id = user_id
        mock_route.name = "Test Route (no SQLAlchemy state)"
        mock_route.timezone = "Europe/London"

        # Set preferences directly (fallback path will use these)
        mock_pref1 = MagicMock()
        mock_pref1.id = uuid.uuid4()
        mock_pref2 = MagicMock()
        mock_pref2.id = uuid.uuid4()
        mock_route.notification_preferences = [mock_pref1, mock_pref2]

        # Create mock schedule
        schedule_id = uuid.uuid4()
        mock_schedule = MagicMock(spec=UserRouteSchedule)
        mock_schedule.id = schedule_id
        mock_schedule.start_time = time(9, 0)
        mock_schedule.end_time = time(17, 0)

        # Mock disruptions
        mock_disruptions = [MagicMock()]

        # Mock helper methods
        alert_svc._get_verified_contact = AsyncMock(return_value=None)
        alert_svc._store_alert_state = AsyncMock()

        await alert_svc._send_alerts_for_route(
            route=mock_route,
            schedule=mock_schedule,
            disruptions=mock_disruptions,
        )

        # Verify span was created
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.send_for_route"
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes captured preferences from fallback path
        assert span.attributes is not None
        assert span.attributes["alert.preference_count"] == 2  # Should use fallback and count prefs
        assert span.attributes["alert.disruption_count"] == 1
        assert span.attributes["alert.alerts_sent"] == 0  # None sent due to no contact


class TestAlertServiceLogLineStateChangesOtelSpans:
    """Test class for Alert Service _log_line_disruption_state_changes() OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_log_line_state_changes_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that _log_line_disruption_state_changes creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        # Create mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # No previous hash
        mock_redis.set = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock disruptions

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=14,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="jubilee",
                line_name="Jubilee",
                mode="tube",
                status_severity=12,
                status_severity_description="Minor Delays",
                reason="Earlier incident",
            ),
        ]

        logged_count = await alert_svc._log_line_disruption_state_changes(disruptions)

        assert logged_count == 2  # Both disruptions should be logged

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.log_line_state_changes"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "alert-service"
        assert span.attributes["alert.operation"] == "log_line_state_changes"
        assert span.attributes["alert.disruption_count"] == 2
        assert span.attributes["alert.logged_count"] == 2

    @pytest.mark.asyncio
    async def test_log_line_state_changes_handles_exception_gracefully(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span has OK status even when database error occurs (graceful handling)."""
        _, exporter = otel_enabled_provider

        # Create mock database session that raises exception on add
        mock_db = AsyncMock()
        mock_db.add = MagicMock(side_effect=Exception("Database connection lost"))
        mock_db.rollback = AsyncMock()

        # Create mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock disruptions

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=14,
                status_severity_description="Severe Delays",
            ),
        ]

        # Method should return 0 instead of raising
        logged_count = await alert_svc._log_line_disruption_state_changes(disruptions)

        assert logged_count == 0  # Graceful failure returns 0

        # Verify span has OK status (method handles exceptions internally)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.log_line_state_changes"
        assert_span_status(span, StatusCode.OK)  # Still OK because method doesn't raise

        # Verify attributes show 0 logged count
        assert span.attributes is not None
        assert span.attributes["alert.logged_count"] == 0

        # Verify rollback was called
        assert mock_db.rollback.called


class TestWarmUpLineStateCacheOtelSpans:
    """Test class for warm_up_line_state_cache() OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_warm_up_cache_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that warm_up_line_state_cache creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # Empty logs
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Create mock Redis client
        mock_redis = AsyncMock()

        # Call the function
        lines_hydrated = await warm_up_line_state_cache(mock_db, mock_redis)

        assert lines_hydrated == 0  # No lines to hydrate

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.warm_up_cache"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "alert-service"
        assert span.attributes["cache.operation"] == "warmup"
        assert span.attributes["cache.lines_hydrated"] == 0
        assert span.attributes["cache.total_log_entries"] == 0
        assert span.attributes["cache.success"] is True

    @pytest.mark.asyncio
    async def test_warm_up_cache_handles_error_gracefully(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span has OK status when database error is handled gracefully."""
        _, exporter = otel_enabled_provider

        # Create mock database session that fails
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("Database connection error"))

        # Create mock Redis client
        mock_redis = AsyncMock()

        # Function should return 0 instead of raising (graceful error handling)
        lines_hydrated = await warm_up_line_state_cache(mock_db, mock_redis)

        assert lines_hydrated == 0  # Graceful failure returns 0

        # Verify span has OK status (exception was caught and handled)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.warm_up_cache"
        assert_span_status(span, StatusCode.OK)

        # Verify attributes show failure with error details
        assert span.attributes is not None
        assert span.attributes["cache.success"] is False
        assert span.attributes["cache.lines_hydrated"] == 0
        assert span.attributes["cache.total_log_entries"] == 0
        assert span.attributes["cache.error"] is True
        assert span.attributes["cache.error_type"] == "Exception"


class TestAlertServiceShouldSendAlertOtelSpans:
    """Test class for AlertService._should_send_alert() OTEL instrumentation."""

    @pytest.mark.asyncio
    async def test_should_send_alert_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that _should_send_alert creates a span with OK status."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        # Create mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # No previous state

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock route
        route_id = uuid.uuid4()
        user_id = uuid.uuid4()
        schedule_id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = route_id
        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id

        # Call the method
        should_send, _filtered, _stored_lines = await alert_svc._should_send_alert(
            route=mock_route,
            user_id=user_id,
            schedule=mock_schedule,
            disruptions=[],
        )

        assert should_send is False  # No disruptions = no alert

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.should_send_check"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "alert-service"
        assert span.attributes["alert.route_id"] == str(route_id)
        assert span.attributes["alert.user_id"] == str(user_id)
        assert span.attributes["alert.schedule_id"] == str(schedule_id)
        assert span.attributes["alert.has_previous_state"] is False
        assert span.attributes["alert.state_changed"] is False
        assert span.attributes["alert.result"] is False

    @pytest.mark.asyncio
    async def test_should_send_alert_handles_error_gracefully(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span has OK status when Redis error is handled gracefully."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        # Create mock Redis client that fails
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock route
        route_id = uuid.uuid4()
        user_id = uuid.uuid4()
        schedule_id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = route_id
        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id

        # Method handles exception gracefully
        should_send, _filtered, _stored_lines = await alert_svc._should_send_alert(
            route=mock_route,
            user_id=user_id,
            schedule=mock_schedule,
            disruptions=[],
        )

        assert should_send is True  # Failsafe: return True on Redis error

        # Verify span has OK status (exception was caught and handled)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.should_send_check"
        assert_span_status(span, StatusCode.OK)

        # Verify attributes show result=True (send on error) with error details
        assert span.attributes is not None
        assert span.attributes["alert.has_previous_state"] is False  # Unknown due to error
        assert span.attributes["alert.state_changed"] is True  # Conservative fallback
        assert span.attributes["alert.result"] is True
        assert span.attributes["alert.error"] is True
        assert span.attributes["alert.error_type"] == "Exception"


class TestAlertServiceStoreAlertStateOtelSpans:
    """Test class for AlertService._store_alert_state() OTEL instrumentation."""

    @pytest.mark.asyncio
    async def test_store_alert_state_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that _store_alert_state creates a span with OK status."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        # Create mock Redis client
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock route
        route_id = uuid.uuid4()
        user_id = uuid.uuid4()
        schedule_id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = route_id
        mock_route.timezone = "Europe/London"
        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.end_time = time(23, 59)  # End time in future

        # Call the method
        await alert_svc._store_alert_state(
            route=mock_route,
            user_id=user_id,
            schedule=mock_schedule,
            disruptions=[],
        )

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.store_state"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "alert-service"
        assert span.attributes["alert.route_id"] == str(route_id)
        assert span.attributes["alert.user_id"] == str(user_id)
        assert span.attributes["alert.schedule_id"] == str(schedule_id)
        assert span.attributes["alert.disruption_count"] == 0
        assert "alert.ttl_seconds" in span.attributes

    @pytest.mark.asyncio
    async def test_store_alert_state_handles_error_gracefully(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span has OK status when Redis error is handled gracefully."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        # Create mock Redis client that fails
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis connection error"))

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Create mock route
        route_id = uuid.uuid4()
        user_id = uuid.uuid4()
        schedule_id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = route_id
        mock_route.timezone = "Europe/London"
        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.end_time = time(23, 59)  # End time in future

        # Method handles exception gracefully (doesn't raise)
        await alert_svc._store_alert_state(
            route=mock_route,
            user_id=user_id,
            schedule=mock_schedule,
            disruptions=[],
        )

        # Verify span has OK status (exception was caught and handled)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.store_state"
        assert_span_status(span, StatusCode.OK)
