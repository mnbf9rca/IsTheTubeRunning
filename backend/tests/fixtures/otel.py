"""OpenTelemetry test fixtures."""

from collections.abc import Generator

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def in_memory_span_exporter() -> InMemorySpanExporter:
    """
    Create InMemorySpanExporter for capturing spans in tests.

    Returns:
        InMemorySpanExporter that stores spans in memory for verification
    """
    return InMemorySpanExporter()


@pytest.fixture
def test_tracer_provider(in_memory_span_exporter: InMemorySpanExporter) -> TracerProvider:
    """
    Create TracerProvider with InMemorySpanExporter for testing.

    Args:
        in_memory_span_exporter: Fixture providing span exporter

    Returns:
        TracerProvider configured for testing (no network calls)
    """
    resource = Resource(
        attributes={
            "service.name": "isthetuberunning-backend-test",
            "service.version": "0.1.0-test",
            "deployment.environment": "test",
        }
    )

    provider = TracerProvider(resource=resource)

    # Use SimpleSpanProcessor for synchronous span processing in tests
    # (BatchSpanProcessor is async and complicates test assertions)
    span_processor = SimpleSpanProcessor(in_memory_span_exporter)
    provider.add_span_processor(span_processor)

    return provider


@pytest.fixture(autouse=True)
def reset_tracer_provider() -> Generator[None]:
    """
    Reset OTEL telemetry module globals before and after each test.

    This ensures test isolation and prevents spans from leaking between tests.
    Similar to the database module reset pattern used in other tests.

    Yields:
        None
    """
    # Import here to avoid circular dependency at module level
    from app.celery import database as celery_database  # noqa: PLC0415
    from app.core import database, telemetry  # noqa: PLC0415  # Lazy import to avoid circular dependency
    from opentelemetry import trace as otel_trace  # noqa: PLC0415

    # Reset telemetry module globals
    telemetry._tracer_provider = None  # type: ignore[attr-defined]

    # Reset OpenTelemetry global tracer provider to allow tests to set their own
    otel_trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]

    # Reset database instrumentation flags (FastAPI and Celery worker)
    database._sqlalchemy_instrumented = False  # type: ignore[attr-defined]
    celery_database._worker_sqlalchemy_instrumented = False  # type: ignore[attr-defined]

    yield

    # Reset again after test to clean up
    telemetry._tracer_provider = None  # type: ignore[attr-defined]
    otel_trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    database._sqlalchemy_instrumented = False  # type: ignore[attr-defined]
    celery_database._worker_sqlalchemy_instrumented = False  # type: ignore[attr-defined]
