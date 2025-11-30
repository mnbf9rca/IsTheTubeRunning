"""Tests for Email Service OpenTelemetry instrumentation."""

from unittest.mock import AsyncMock, patch

import aiosmtplib
import pytest
from app.services.email_service import EmailService
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from tests.helpers.otel import assert_span_status


class TestEmailServiceOtelSpans:
    """Test class for Email Service OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_send_email_async_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that _send_email_async creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        # Create email service instance
        email_svc = EmailService()

        # Mock SMTP operations
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock()
        mock_smtp.send_message = AsyncMock()

        # Test email sending with span
        with patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp):
            await email_svc._send_email_async(
                to="test@example.com",
                subject="Test Subject",
                html_content="<p>Test HTML</p>",
                text_content="Test plain text",
            )

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert span.kind == SpanKind.CLIENT
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "smtp"
        assert span.attributes["smtp.host"] == email_svc.smtp_host
        assert span.attributes["smtp.port"] == email_svc.smtp_port
        assert span.attributes["email.recipient"] == "test@example.com"
        assert span.attributes["email.subject"] == "Test Subject"

    @pytest.mark.asyncio
    async def test_send_email_async_records_exception_on_timeout(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception on timeout."""
        _, exporter = otel_enabled_provider

        email_svc = EmailService()

        # Mock SMTP to raise TimeoutError
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock(side_effect=TimeoutError("Connection timeout"))

        with (
            patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp),
            pytest.raises(TimeoutError, match="Connection timeout"),
        ):
            await email_svc._send_email_async(
                to="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
                text_content="Test",
            )

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_send_email_async_records_exception_on_oserror(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception on network/socket errors."""
        _, exporter = otel_enabled_provider

        email_svc = EmailService()

        # Mock SMTP to raise OSError
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock(side_effect=OSError("Network unreachable"))

        with (
            patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp),
            pytest.raises(OSError, match="Network unreachable"),
        ):
            await email_svc._send_email_async(
                to="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
                text_content="Test",
            )

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_send_email_async_records_exception_on_smtp_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception on SMTP protocol errors."""
        _, exporter = otel_enabled_provider

        email_svc = EmailService()

        # Mock SMTP to raise SMTPException
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock(side_effect=aiosmtplib.SMTPAuthenticationError(535, "Invalid credentials"))

        with (
            patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp),
            pytest.raises(aiosmtplib.SMTPException),
        ):
            await email_svc._send_email_async(
                to="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
                text_content="Test",
            )

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_send_verification_email_creates_span(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that send_verification_email creates span via _send_email_async."""
        _, exporter = otel_enabled_provider

        email_svc = EmailService()

        # Mock SMTP operations
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock()
        mock_smtp.send_message = AsyncMock()

        with patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp):
            await email_svc.send_verification_email(
                email="user@example.com",
                code="123456",
            )

        # Verify span was created (send_verification_email calls _send_email_async)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert_span_status(span, StatusCode.OK)
