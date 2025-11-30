"""Tests for Notification Service OpenTelemetry instrumentation."""

from unittest.mock import AsyncMock, patch

import pytest
from app.schemas.tfl import DisruptionResponse
from app.services.notification_service import NotificationService
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from tests.helpers.otel import assert_span_status


class TestNotificationServiceOtelSpans:
    """Test class for Notification Service OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_send_disruption_email_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that send_disruption_email creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        # Create notification service instance
        notif_svc = NotificationService()

        # Mock the email service's send_email method
        with patch.object(notif_svc.email_service, "send_email", new_callable=AsyncMock):
            # Create sample disruptions
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
                    status_severity=16,
                    status_severity_description="Part Closure",
                    reason="Planned engineering works",
                ),
            ]

            await notif_svc.send_disruption_email(
                email="test@example.com",
                route_name="Home to Work",
                disruptions=disruptions,
                user_name="Test User",
            )

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        # Should have 2 spans: notification.send_disruption_email (parent) and email.send (child)
        assert len(spans) >= 1

        # Find the notification span
        notif_span = next(s for s in spans if s.name == "notification.send_disruption_email")
        assert notif_span.kind == SpanKind.INTERNAL
        assert_span_status(notif_span, StatusCode.OK)

        # Verify span attributes
        assert notif_span.attributes is not None
        assert notif_span.attributes["peer.service"] == "notification-service"
        assert notif_span.attributes["notification.type"] == "email"
        assert "notification.recipient_hash" in notif_span.attributes
        assert len(notif_span.attributes["notification.recipient_hash"]) == 12
        assert notif_span.attributes["notification.route_name"] == "Home to Work"
        assert notif_span.attributes["notification.disruption_count"] == 2

    @pytest.mark.asyncio
    async def test_send_disruption_email_records_exception_on_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception when email sending fails."""
        _, exporter = otel_enabled_provider

        notif_svc = NotificationService()

        # Prepare test data
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=14,
                status_severity_description="Severe Delays",
            ),
        ]

        # Mock email service to raise an exception
        with (
            patch.object(
                notif_svc.email_service,
                "send_email",
                new_callable=AsyncMock,
                side_effect=Exception("SMTP connection failed"),
            ),
            pytest.raises(Exception, match="SMTP connection failed"),
        ):
            await notif_svc.send_disruption_email(
                email="test@example.com",
                route_name="Home to Work",
                disruptions=disruptions,
            )

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) >= 1

        notif_span = next(s for s in spans if s.name == "notification.send_disruption_email")
        assert_span_status(notif_span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_send_disruption_sms_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that send_disruption_sms creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        notif_svc = NotificationService()

        # Mock the SMS service's send_sms method
        with patch.object(notif_svc.sms_service, "send_sms", new_callable=AsyncMock):
            disruptions = [
                DisruptionResponse(
                    line_id="victoria",
                    line_name="Victoria",
                    mode="tube",
                    status_severity=14,
                    status_severity_description="Severe Delays",
                    reason="Signal failure",
                ),
            ]

            await notif_svc.send_disruption_sms(
                phone="+447700900000",
                route_name="Home to Work",
                disruptions=disruptions,
            )

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) >= 1

        sms_span = next(s for s in spans if s.name == "notification.send_disruption_sms")
        assert sms_span.kind == SpanKind.INTERNAL
        assert_span_status(sms_span, StatusCode.OK)

        # Verify span attributes
        assert sms_span.attributes is not None
        assert sms_span.attributes["peer.service"] == "notification-service"
        assert sms_span.attributes["notification.type"] == "sms"
        assert "notification.recipient_hash" in sms_span.attributes
        assert len(sms_span.attributes["notification.recipient_hash"]) == 12
        assert sms_span.attributes["notification.route_name"] == "Home to Work"
        assert sms_span.attributes["notification.disruption_count"] == 1
        # Message length should be set after message construction
        assert "notification.message_length" in sms_span.attributes
        assert sms_span.attributes["notification.message_length"] > 0

    @pytest.mark.asyncio
    async def test_send_disruption_sms_records_exception_on_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception when SMS sending fails."""
        _, exporter = otel_enabled_provider

        notif_svc = NotificationService()

        # Prepare test data
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=14,
                status_severity_description="Severe Delays",
            ),
        ]

        # Mock SMS service to raise an exception
        with (
            patch.object(
                notif_svc.sms_service,
                "send_sms",
                new_callable=AsyncMock,
                side_effect=Exception("SMS gateway unavailable"),
            ),
            pytest.raises(Exception, match="SMS gateway unavailable"),
        ):
            await notif_svc.send_disruption_sms(
                phone="+447700900000",
                route_name="Home to Work",
                disruptions=disruptions,
            )

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) >= 1

        sms_span = next(s for s in spans if s.name == "notification.send_disruption_sms")
        assert_span_status(sms_span, StatusCode.ERROR, check_exception=True)
