"""Tests for Verification Service OpenTelemetry instrumentation."""

import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.user import VerificationType
from app.services import verification_service
from app.services.verification_service import VerificationService
from fastapi import HTTPException
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


class TestVerificationServiceOtelSpans:
    """Test class for Verification Service OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_create_and_send_code_creates_span_with_ok_status(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that create_and_send_code creates a span with OK status on success."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(verification_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        # Mock email service
        mock_email_service = AsyncMock()
        mock_email_service.send_verification_email = AsyncMock()

        # Create verification service
        verification_svc = VerificationService(db=mock_db)
        verification_svc.email_service = mock_email_service

        # Mock check_verification_rate_limit to pass
        verification_svc.check_verification_rate_limit = AsyncMock()
        verification_svc.record_verification_code_request = AsyncMock()

        contact_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with patch("opentelemetry.trace.get_tracer", return_value=test_tracer):
            await verification_svc.create_and_send_code(
                contact_id=contact_id,
                user_id=user_id,
                contact_type=VerificationType.EMAIL,
                contact_value="test@example.com",
            )

        # Verify span was created with OK status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "verification.create_and_send_code"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "verification-service"
        assert span.attributes["verification.contact_id"] == str(contact_id)
        assert span.attributes["verification.user_id"] == str(user_id)
        assert span.attributes["verification.contact_type"] == "email"

    @pytest.mark.asyncio
    async def test_create_and_send_code_sms_creates_span(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that create_and_send_code creates a span for SMS verification."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(verification_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        # Mock SMS service
        mock_sms_service = AsyncMock()
        mock_sms_service.send_verification_sms = AsyncMock()

        # Create verification service
        verification_svc = VerificationService(db=mock_db)
        verification_svc.sms_service = mock_sms_service

        # Mock rate limiting
        verification_svc.check_verification_rate_limit = AsyncMock()
        verification_svc.record_verification_code_request = AsyncMock()

        contact_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with patch("opentelemetry.trace.get_tracer", return_value=test_tracer):
            await verification_svc.create_and_send_code(
                contact_id=contact_id,
                user_id=user_id,
                contact_type=VerificationType.SMS,
                contact_value="+14155551234",
            )

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "verification.create_and_send_code"
        assert span.attributes is not None
        assert span.attributes["verification.contact_type"] == "sms"
        assert_span_status(span, StatusCode.OK)

    @pytest.mark.asyncio
    async def test_create_and_send_code_records_exception_on_email_error(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception when email sending fails."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(verification_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        # Mock email service to raise exception
        mock_email_service = AsyncMock()
        mock_email_service.send_verification_email = AsyncMock(side_effect=Exception("SMTP connection error"))

        # Create verification service
        verification_svc = VerificationService(db=mock_db)
        verification_svc.email_service = mock_email_service

        # Mock rate limiting
        verification_svc.check_verification_rate_limit = AsyncMock()
        verification_svc.record_verification_code_request = AsyncMock()

        contact_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            pytest.raises(HTTPException, match="Failed to send verification code"),
        ):
            await verification_svc.create_and_send_code(
                contact_id=contact_id,
                user_id=user_id,
                contact_type=VerificationType.EMAIL,
                contact_value="test@example.com",
            )

        # Verify span has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "verification.create_and_send_code"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_create_and_send_code_records_exception_on_rate_limit(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception when rate limit exceeded."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(verification_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()

        # Create verification service
        verification_svc = VerificationService(db=mock_db)

        # Mock check_verification_rate_limit to raise HTTPException
        verification_svc.check_verification_rate_limit = AsyncMock(
            side_effect=HTTPException(status_code=429, detail="Rate limit exceeded")
        )

        contact_id = uuid.uuid4()
        user_id = uuid.uuid4()

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            pytest.raises(HTTPException, match="Rate limit exceeded"),
        ):
            await verification_svc.create_and_send_code(
                contact_id=contact_id,
                user_id=user_id,
                contact_type=VerificationType.EMAIL,
                contact_value="test@example.com",
            )

        # Verify span has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "verification.create_and_send_code"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)
