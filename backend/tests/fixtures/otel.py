"""OpenTelemetry test fixtures."""

from collections.abc import Generator

import pytest
from opentelemetry import trace
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


@pytest.fixture
def otel_enabled_provider(monkeypatch: pytest.MonkeyPatch) -> Generator[TracerProvider]:
    """Fixture that provides a clean TracerProvider with OTEL enabled for testing.

    Sets up:
    - OTEL_ENABLED=True
    - DEBUG=True (skip endpoint validation)
    - OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=None
    - OTEL_SDK_DISABLED unset (enables SDK)
    - Clean tracer provider state

    Yields:
        TracerProvider configured for testing

    Note:
        All environment and settings changes are automatically restored by
        monkeypatch after the test. Manual cleanup only needed for module state.
    """
    # Import here to avoid circular dependency
    from app.core import telemetry  # noqa: PLC0415
    from app.core.config import settings  # noqa: PLC0415

    # Enable OTEL SDK (disabled by default in conftest.py)
    # monkeypatch automatically restores this after the test
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)

    # Configure settings (automatically restored by monkeypatch)
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", None)

    # Reset provider state
    telemetry._tracer_provider = None  # type: ignore[attr-defined]

    # Create provider
    provider = telemetry.get_tracer_provider()
    assert provider is not None

    # Reset OTEL global state and set provider directly
    # Bypass set_tracer_provider() which has override protection
    trace._TRACER_PROVIDER = provider  # type: ignore[attr-defined]

    yield provider

    # Cleanup: reset state (autouse fixture will handle final cleanup)
    telemetry._tracer_provider = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]


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

    # Reset telemetry module globals
    telemetry._tracer_provider = None  # type: ignore[attr-defined]

    # Reset OpenTelemetry global tracer provider to allow tests to set their own
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]

    # Reset database instrumentation flags (FastAPI and Celery worker)
    database._sqlalchemy_instrumented = False  # type: ignore[attr-defined]
    celery_database._worker_sqlalchemy_instrumented = False  # type: ignore[attr-defined]

    yield

    # Reset again after test to clean up
    telemetry._tracer_provider = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    database._sqlalchemy_instrumented = False  # type: ignore[attr-defined]
    celery_database._worker_sqlalchemy_instrumented = False  # type: ignore[attr-defined]
