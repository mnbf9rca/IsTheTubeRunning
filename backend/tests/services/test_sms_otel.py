"""Tests for SmsService OpenTelemetry instrumentation."""

from unittest.mock import AsyncMock, patch

import pytest
from app.services.sms_service import SmsService
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from tests.helpers.otel import assert_span_status


class TestSmsServiceOtelSpans:
    """Test SmsService OpenTelemetry spans."""

    @pytest.mark.asyncio
    async def test_send_sms_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that send_sms creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        service = SmsService()
        test_phone = "+447700900123"
        test_message = "Test SMS message"

        # Mock file I/O to prevent actual file writes
        with patch("app.services.sms_service.SMS_LOG_FILE", None):
            await service.send_sms(test_phone, test_message)

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "sms.send"
        assert span.kind == SpanKind.CLIENT
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "sms"

        # Verify recipient_hash format and non-reversibility
        recipient_hash = span.attributes["sms.recipient_hash"]
        assert isinstance(recipient_hash, str)
        assert len(recipient_hash) == 12  # First 12 chars of hash
        assert recipient_hash.isalnum()  # Hex characters
        assert recipient_hash != test_phone  # Not raw PII
        assert recipient_hash != test_phone.replace("+", "")  # Not raw PII without prefix

        assert span.attributes["sms.message_length"] == len(test_message)
        assert span.attributes["sms.stub"] is True

    @pytest.mark.asyncio
    async def test_send_sms_records_exception_on_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that send_sms records exception when operation fails."""
        _, exporter = otel_enabled_provider

        service = SmsService()
        test_phone = "+447700900123"
        test_message = "Test SMS message"

        # Mock the file write to raise an exception
        with (
            patch("app.services.sms_service.SMS_LOG_FILE", "/fake/path/sms_log.txt"),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_executor = AsyncMock()
            mock_executor.side_effect = RuntimeError("File write error")
            mock_loop.return_value.run_in_executor = mock_executor

            with pytest.raises(RuntimeError, match="File write error"):
                await service.send_sms(test_phone, test_message)

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "sms.send"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)
