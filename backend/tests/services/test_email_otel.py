"""Tests for Email Service OpenTelemetry instrumentation."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import aiosmtplib
import pytest
from app.services import email_service
from app.services.email_service import EmailService
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from tests.helpers.otel import assert_span_status, get_recorded_spans


# Re-enable OTEL for these tests
# conftest.py sets OTEL_SDK_DISABLED=true by default
@pytest.fixture(autouse=True)
def enable_otel_for_tests(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Enable OTEL SDK for tests in this module."""
    # Remove OTEL_SDK_DISABLED if present (enables OTEL)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    return
    # Monkeypatch automatically restores original environment on cleanup


class TestEmailServiceOtelSpans:
    """Test class for Email Service OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_send_email_async_creates_span_with_ok_status(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that _send_email_async creates a span with OK status on success."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(email_service.__name__)

        # Create email service instance
        email_svc = EmailService()

        # Mock SMTP operations
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock()
        mock_smtp.send_message = AsyncMock()

        # Test email sending with span
        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp),
        ):
            await email_svc._send_email_async(
                to="test@example.com",
                subject="Test Subject",
                html_content="<p>Test HTML</p>",
                text_content="Test plain text",
            )

        # Verify span was created with OK status
        spans = get_recorded_spans(exporter)
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
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception and has ERROR status on timeout."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(email_service.__name__)

        email_svc = EmailService()

        # Mock SMTP to raise TimeoutError
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(side_effect=TimeoutError("SMTP timeout"))
        mock_smtp.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp),
            pytest.raises(TimeoutError, match="SMTP timeout"),
        ):
            await email_svc._send_email_async(
                to="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
                text_content="Test",
            )

        # Verify span has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_send_email_async_records_exception_on_oserror(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception on network/connection errors."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(email_service.__name__)

        email_svc = EmailService()

        # Mock SMTP to raise OSError (network error)
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(side_effect=OSError("Connection refused"))
        mock_smtp.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp),
            pytest.raises(OSError, match="Connection refused"),
        ):
            await email_svc._send_email_async(
                to="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
                text_content="Test",
            )

        # Verify span has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_send_email_async_records_exception_on_smtp_error(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception on SMTP protocol errors."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(email_service.__name__)

        email_svc = EmailService()

        # Mock SMTP to raise SMTPException
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock(side_effect=aiosmtplib.SMTPAuthenticationError(535, "Invalid credentials"))

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
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
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_send_verification_email_creates_span(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that send_verification_email creates a span (via send_email -> _send_email_async)."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(email_service.__name__)

        email_svc = EmailService()

        # Mock SMTP operations
        mock_smtp = AsyncMock()
        mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
        mock_smtp.__aexit__ = AsyncMock(return_value=None)
        mock_smtp.login = AsyncMock()
        mock_smtp.send_message = AsyncMock()

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            patch("app.services.email_service.aiosmtplib.SMTP", return_value=mock_smtp),
        ):
            await email_svc.send_verification_email("test@example.com", "123456")

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "email.send"
        assert span.kind == SpanKind.CLIENT
        assert_span_status(span, StatusCode.OK)

        # Verify attributes include the verification email subject
        assert span.attributes is not None
        assert span.attributes["email.recipient"] == "test@example.com"
        assert "Verify Your Email" in span.attributes["email.subject"]
