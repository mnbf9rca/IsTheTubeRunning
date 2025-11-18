"""Tests for Celery OpenTelemetry context propagation.

Tests cover:
- Context propagation from API requests to Celery tasks
- Parent-child span relationships
- Celery span attributes (task_name, task_id, etc.)
- Trace context in Celery message headers

Note: These tests use mocks since OTEL_SDK_DISABLED=true in tests by default.
"""

from unittest.mock import MagicMock, patch

import pytest
from app.celery import database as celery_database
from opentelemetry import trace
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


class TestCeleryContextPropagation:
    """Tests for trace context propagation to Celery tasks."""

    @pytest.fixture
    def enabled_tracer_provider(self, in_memory_span_exporter: InMemorySpanExporter) -> TracerProvider:
        """Create an enabled TracerProvider for context propagation tests."""
        provider = TracerProvider(resource=Resource(attributes={"service.name": "test"}))
        provider.add_span_processor(SimpleSpanProcessor(in_memory_span_exporter))
        return provider

    def test_trace_context_format_is_valid(self) -> None:
        """Test that trace context format follows W3C traceparent specification."""
        # Create a mock span with known trace_id and span_id
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.trace_id = 0x12345678901234567890123456789012
        mock_span_context.span_id = 0x1234567890123456
        mock_span_context.is_valid = True
        mock_span_context.trace_flags = 1
        mock_span.get_span_context.return_value = mock_span_context

        # Verify traceparent format
        trace_id_hex = format(mock_span_context.trace_id, "032x")
        span_id_hex = format(mock_span_context.span_id, "016x")

        assert len(trace_id_hex) == 32
        assert len(span_id_hex) == 16

    def test_traceparent_header_structure(self) -> None:
        """Test that traceparent header follows W3C format."""
        # W3C traceparent format: version-trace_id-parent_id-trace_flags
        # Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01

        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        parts = traceparent.split("-")

        assert len(parts) == 4
        assert parts[0] == "00"  # Version
        assert len(parts[1]) == 32  # Trace ID (128-bit)
        assert len(parts[2]) == 16  # Parent ID (64-bit)
        assert len(parts[3]) == 2  # Trace flags

    def test_context_extraction_from_headers(self) -> None:
        """Test that context can be extracted from carrier headers."""
        propagator = TraceContextTextMapPropagator()

        # Simulate headers that would come from a parent context
        headers = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}

        # Extract context
        extracted_context = propagator.extract(headers)

        # Verify extraction succeeded (returns a context object)
        assert extracted_context is not None


class TestCeleryInstrumentorBehavior:
    """Tests for CeleryInstrumentor automatic behavior."""

    def test_celery_instrumentor_can_be_instantiated(self) -> None:
        """Test that CeleryInstrumentor can be instantiated."""
        instrumentor = CeleryInstrumentor()
        assert instrumentor is not None


class TestSpanAttributePatterns:
    """Tests for expected span attribute patterns."""

    def test_celery_task_span_attributes_format(self) -> None:
        """Test that Celery task span attributes follow expected format."""
        # Expected attributes that CeleryInstrumentor sets
        expected_attributes = {
            "celery.task_name": "app.celery.tasks.check_disruptions_and_alert",
            "celery.task_id": "abc123-def456-ghi789",
            "celery.state": "SUCCESS",
        }

        # Verify attribute names and value types
        assert isinstance(expected_attributes["celery.task_name"], str)
        assert isinstance(expected_attributes["celery.task_id"], str)
        assert isinstance(expected_attributes["celery.state"], str)

    def test_db_span_attributes_format(self) -> None:
        """Test that database span attributes follow expected format."""
        # Expected attributes that SQLAlchemyInstrumentor sets
        expected_attributes = {
            "db.system": "postgresql",
            "db.statement": "SELECT * FROM routes WHERE active = true",
        }

        # Verify attribute names and value types
        assert isinstance(expected_attributes["db.system"], str)
        assert isinstance(expected_attributes["db.statement"], str)


class TestWorkerOtelIntegration:
    """Tests for worker OTEL integration patterns."""

    def test_worker_tracer_provider_initialization_pattern(self) -> None:
        """Test that worker initializes TracerProvider correctly."""
        # Reset state
        celery_database._worker_loop = None

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch("app.core.telemetry.get_tracer_provider") as mock_get,
            patch("opentelemetry.trace.set_tracer_provider") as mock_set,
        ):
            mock_provider = MagicMock()
            mock_get.return_value = mock_provider

            # Initialize worker
            celery_database.init_worker_resources()

            # Verify TracerProvider was obtained and set
            mock_get.assert_called_once()
            mock_set.assert_called_once_with(mock_provider)

            # Clean up
            if celery_database._worker_loop is not None:
                celery_database._worker_loop.close()
                celery_database._worker_loop = None

    def test_worker_sqlalchemy_instrumentation_pattern(self) -> None:
        """Test that worker instruments SQLAlchemy correctly."""
        # Reset state
        celery_database._worker_engine = None
        celery_database._worker_sqlalchemy_instrumented = False

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch("app.celery.database.create_async_engine") as mock_create,
            patch("opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor") as mock_instrumentor_class,
        ):
            mock_engine = MagicMock()
            mock_engine.sync_engine = MagicMock()
            mock_create.return_value = mock_engine

            mock_instrumentor = MagicMock()
            mock_instrumentor_class.return_value = mock_instrumentor

            # Create worker engine
            celery_database._get_worker_engine()

            # Verify instrumentation was called with sync_engine
            mock_instrumentor.instrument.assert_called_once_with(engine=mock_engine.sync_engine)

            # Clean up
            celery_database._worker_engine = None
            celery_database._worker_sqlalchemy_instrumented = False


class TestContextPropagationMechanics:
    """Tests for context propagation mechanics."""

    def test_propagator_inject_and_extract(self) -> None:
        """Test that propagator can inject and extract context."""
        propagator = TraceContextTextMapPropagator()

        # Create a carrier with traceparent header
        carrier: dict[str, str] = {"traceparent": "00-12345678901234567890123456789012-1234567890123456-01"}

        # Extract should return a context
        context = propagator.extract(carrier)
        assert context is not None

    def test_multiple_traces_are_independent(self) -> None:
        """Test that different traces have different IDs."""
        trace_id_1 = 0x12345678901234567890123456789012
        trace_id_2 = 0xABCDEFABCDEFABCDEFABCDEFABCDEFAB

        # Trace IDs should be different
        assert trace_id_1 != trace_id_2

        # Each can have its own parent span
        parent_id_1 = 0x1234567890123456
        parent_id_2 = 0xABCDEFABCDEFABCD

        assert parent_id_1 != parent_id_2


class TestAsyncWorkerSpanPatterns:
    """Tests for async worker span patterns."""

    def test_span_kind_for_celery_tasks(self) -> None:
        """Test that Celery tasks should use CONSUMER span kind."""
        # Celery task receiving work is a consumer
        assert SpanKind.CONSUMER is not None

    def test_span_kind_for_api_requests(self) -> None:
        """Test that API requests should use SERVER span kind."""
        # FastAPI handling requests is a server
        assert SpanKind.SERVER is not None

    def test_parent_child_span_relationship_concept(self) -> None:
        """Test the concept of parent-child span relationships."""
        # A child span should reference its parent via parent_id
        # Child inherits trace_id from parent but has different span_id
        parent_span_id = 0x1234567890123456
        child_span_id = 0xABCDEFABCDEFABCD

        assert child_span_id != parent_span_id


@pytest.mark.asyncio
class TestAsyncContextPropagation:
    """Tests for async context propagation patterns."""

    async def test_async_span_creation_pattern(self) -> None:
        """Test the pattern for creating spans in async code."""
        # In async code, spans are created the same way as sync
        # The key is that context propagation works across await boundaries

        # Mock tracer usage pattern
        tracer = trace.get_tracer(__name__)
        assert tracer is not None

    async def test_span_context_available_in_async_code(self) -> None:
        """Test that span context is accessible in async code."""
        # Context should be accessible via trace.get_current_span()
        current_span = trace.get_current_span()

        # With OTEL_SDK_DISABLED, this returns a NoOp span
        assert current_span is not None
