"""OpenTelemetry test fixtures."""

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan


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
    from app.core import database, telemetry  # noqa: PLC0415  # Lazy import to avoid circular dependency

    # Reset telemetry module globals
    telemetry._tracer_provider = None  # type: ignore[attr-defined]

    # Reset database instrumentation flag
    database._sqlalchemy_instrumented = False  # type: ignore[attr-defined]

    yield

    # Reset again after test to clean up
    telemetry._tracer_provider = None  # type: ignore[attr-defined]
    database._sqlalchemy_instrumented = False  # type: ignore[attr-defined]


def get_recorded_spans(exporter: InMemorySpanExporter) -> list["ReadableSpan"]:
    """
    Get all recorded spans from the exporter.

    Helper function for retrieving and asserting spans in tests.

    Args:
        exporter: InMemorySpanExporter to retrieve spans from

    Returns:
        List of recorded spans

    Example:
        >>> spans = get_recorded_spans(in_memory_span_exporter)
        >>> assert len(spans) == 1
        >>> assert spans[0].name == "GET /health"
    """
    return exporter.get_finished_spans()


def clear_recorded_spans(exporter: InMemorySpanExporter) -> None:
    """
    Clear all recorded spans from the exporter.

    Useful for resetting span state between test phases.

    Args:
        exporter: InMemorySpanExporter to clear
    """
    exporter.clear()
