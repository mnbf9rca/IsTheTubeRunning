"""Tests for Alert Service OpenTelemetry instrumentation."""

import uuid
from collections.abc import Generator
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.user_route import UserRoute, UserRouteSchedule
from app.services import alert_service
from app.services.alert_service import AlertService
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from tests.helpers.otel import assert_span_status, get_recorded_spans


# Re-enable OTEL for these tests
@pytest.fixture(autouse=True)
def enable_otel_for_tests(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Enable OTEL SDK for tests in this module."""
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    return


class TestAlertServiceProcessAllRoutesOtelSpans:
    """Test class for Alert Service process_all_routes() OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_process_all_routes_creates_span_with_ok_status(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that process_all_routes creates a span with OK status on success."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(alert_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Mock all internal methods to avoid complex execution
        alert_svc._get_active_routes = AsyncMock(return_value=[])
        alert_svc._log_line_disruption_state_changes = AsyncMock()

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            patch("app.services.alert_service.TfLService") as mock_tfl_service_class,
        ):
            # Mock TfL service
            mock_tfl_svc = AsyncMock()
            mock_tfl_svc.fetch_line_disruptions = AsyncMock(return_value=[])
            mock_tfl_service_class.return_value = mock_tfl_svc

            # Mock database execute for AlertDisabledSeverity
            mock_execute_result = AsyncMock()
            mock_scalars = AsyncMock()
            mock_scalars.all.return_value = []
            mock_execute_result.scalars.return_value = mock_scalars
            mock_db.execute.return_value = mock_execute_result

            result = await alert_svc.process_all_routes()

        # Verify result
        assert result["routes_checked"] == 0
        assert result["alerts_sent"] == 0
        assert result["errors"] == 0

        # Verify span was created with OK status
        spans = get_recorded_spans(exporter)
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
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span has OK status even when processing has errors (graceful degradation)."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(alert_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # Create alert service
        alert_svc = AlertService(db=mock_db, redis_client=mock_redis)

        # Mock method to raise exception
        alert_svc._get_active_routes = AsyncMock(side_effect=Exception("Database connection error"))

        with patch("opentelemetry.trace.get_tracer", return_value=test_tracer):
            result = await alert_svc.process_all_routes()

        # Verify result has error tracked
        assert result["errors"] == 1

        # Verify span has OK status (graceful error handling - method doesn't raise)
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.process_all_routes"
        assert_span_status(span, StatusCode.OK)  # Method returns successfully with errors tracked
        # Verify error count is captured in attributes
        assert span.attributes is not None
        assert span.attributes["alert.errors"] == 1


class TestAlertServiceSendAlertsForRouteOtelSpans:
    """Test class for Alert Service _send_alerts_for_route() OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_send_alerts_for_route_creates_span_with_ok_status(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that _send_alerts_for_route creates a span with OK status on success."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(alert_service.__name__)

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

        with patch("opentelemetry.trace.get_tracer", return_value=test_tracer):
            result = await alert_svc._send_alerts_for_route(
                route=mock_route,
                schedule=mock_schedule,
                disruptions=mock_disruptions,
            )

        # Verify result
        assert result == 0  # No alerts sent (no preferences)

        # Verify span was created with OK status
        spans = get_recorded_spans(exporter)
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
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span captures preference count correctly."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(alert_service.__name__)

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

        with patch("opentelemetry.trace.get_tracer", return_value=test_tracer):
            await alert_svc._send_alerts_for_route(
                route=mock_route,
                schedule=mock_schedule,
                disruptions=mock_disruptions,
            )

        # Verify span attributes include preference count
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.attributes is not None
        assert span.attributes["alert.preference_count"] == 2
        assert span.attributes["alert.disruption_count"] == 1

    @pytest.mark.asyncio
    async def test_send_alerts_for_route_handles_exception_gracefully(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span has OK status even when errors occur (graceful degradation)."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(alert_service.__name__)

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

        with patch("opentelemetry.trace.get_tracer", return_value=test_tracer):
            result = await alert_svc._send_alerts_for_route(
                route=mock_route,
                schedule=mock_schedule,
                disruptions=mock_disruptions,
            )

        # Verify result is 0 on error (graceful degradation)
        assert result == 0

        # Verify span has OK status (method handles exceptions internally)
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "alert.send_for_route"
        assert_span_status(span, StatusCode.OK)  # Method returns successfully even with errors
        # Verify attributes show 0 alerts sent
        assert span.attributes is not None
        assert span.attributes["alert.alerts_sent"] == 0

        # Verify rollback was called
        assert mock_db.rollback.called
