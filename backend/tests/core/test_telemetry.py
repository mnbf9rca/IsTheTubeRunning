"""Tests for OpenTelemetry telemetry module."""

import pytest
from app.core.telemetry import service_span
from opentelemetry.trace import SpanKind, StatusCode
from tests.helpers.otel import assert_span_status, get_recorded_spans


class TestServiceSpan:
    """Tests for service_span context manager."""

    def test_service_span_sets_ok_status_on_success(
        self,
        otel_enabled_provider: tuple,
    ) -> None:
        """Test that service_span sets OK status on successful completion."""
        _, exporter = otel_enabled_provider

        # Execute operation that succeeds
        with service_span("test.operation", "test-service"):
            pass  # Successful completion

        # Verify span was created with OK status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "test.operation"
        assert_span_status(span, StatusCode.OK)

    def test_service_span_sets_error_status_on_exception(
        self,
        otel_enabled_provider: tuple,
    ) -> None:
        """Test that SDK sets ERROR status when exception occurs in span."""
        _, exporter = otel_enabled_provider

        # Execute operation that raises exception
        error_msg = "Test error"
        with (
            pytest.raises(ValueError, match=error_msg),
            service_span("test.operation", "test-service"),
        ):
            raise ValueError(error_msg)

        # Verify span was created with ERROR status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "test.operation"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    def test_service_span_propagates_exception(
        self,
        otel_enabled_provider: tuple,
    ) -> None:
        """Test that service_span propagates exceptions (doesn't swallow them)."""
        _ = otel_enabled_provider

        # Verify exception propagates out of context manager
        error_msg = "Intentional test error"
        with (
            pytest.raises(RuntimeError, match=error_msg),
            service_span("test.operation", "test-service"),
        ):
            raise RuntimeError(error_msg)

    def test_service_span_sets_attributes(
        self,
        otel_enabled_provider: tuple,
    ) -> None:
        """Test that service_span sets attributes correctly."""
        _, exporter = otel_enabled_provider

        # Create span with various attribute types
        with service_span(
            "test.operation",
            "test-service",
            kind=SpanKind.CLIENT,
            user_id="user123",
            request_count=42,
            latency_ms=12.5,
            is_cached=True,
        ):
            pass

        # Verify span attributes
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "test.operation"
        assert span.kind == SpanKind.CLIENT
        assert span.attributes["peer.service"] == "test-service"
        assert span.attributes["user_id"] == "user123"
        assert span.attributes["request_count"] == 42
        assert span.attributes["latency_ms"] == 12.5
        assert span.attributes["is_cached"] is True

    def test_service_span_allows_additional_attributes(
        self,
        otel_enabled_provider: tuple,
    ) -> None:
        """Test that additional attributes can be set on yielded span."""
        _, exporter = otel_enabled_provider

        # Create span and add attribute during execution
        with service_span("test.operation", "test-service") as span:
            span.set_attribute("dynamic.attribute", "added-during-execution")

        # Verify both initial and dynamic attributes
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.attributes["peer.service"] == "test-service"
        assert span.attributes["dynamic.attribute"] == "added-during-execution"

    def test_service_span_default_span_kind_is_internal(
        self,
        otel_enabled_provider: tuple,
    ) -> None:
        """Test that default span kind is INTERNAL."""
        _, exporter = otel_enabled_provider

        # Create span without explicit kind
        with service_span("test.operation", "test-service"):
            pass

        # Verify default SpanKind.INTERNAL
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1
        assert spans[0].kind == SpanKind.INTERNAL

    def test_service_span_with_client_kind(
        self,
        otel_enabled_provider: tuple,
    ) -> None:
        """Test service_span with CLIENT span kind for external calls."""
        _, exporter = otel_enabled_provider

        # Create span with CLIENT kind (for external API calls)
        with service_span("external.api.call", "external-api", kind=SpanKind.CLIENT):
            pass

        # Verify SpanKind.CLIENT
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1
        assert spans[0].kind == SpanKind.CLIENT
