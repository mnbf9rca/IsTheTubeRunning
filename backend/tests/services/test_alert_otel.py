"""Tests for Alert Service OpenTelemetry instrumentation."""

import uuid
from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.user_route import UserRoute, UserRouteSchedule
from app.services.alert_service import AlertService
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
        alert_svc._fetch_global_disruption_data = AsyncMock(return_value=([], set()))

        # Mock _process_single_route: succeed for first route, fail for second
        async def mock_process_route(route: UserRoute, disabled_severity_pairs: set) -> tuple[int, bool]:
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
