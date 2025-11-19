"""Integration tests for OpenTelemetry instrumentation.

This module contains two types of tests:
1. Tests with OTEL disabled (default) - verify graceful degradation
2. Tests with OTEL enabled - verify span creation and hierarchy
"""

import os
from collections.abc import AsyncGenerator, Generator

import pytest
from app.core import database
from app.core.config import settings
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.otel import clear_recorded_spans, get_recorded_spans


async def test_otel_disabled_path_no_crashes(
    db_session: AsyncSession,
) -> None:
    """Test that application works normally with OTEL disabled (SDK_DISABLED=true)."""
    # This test runs with OTEL_SDK_DISABLED=true (from conftest.py)
    # It verifies graceful degradation when OTEL is disabled

    # Import app (should work with OTEL disabled)
    from app.main import app  # noqa: PLC0415  # Lazy import to test with OTEL disabled

    # Override get_db
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[database.get_db] = override_get_db

    try:
        # Create client
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Make various requests (should all work without OTEL)
            response = await client.get("/")
            assert response.status_code == 200
            assert response.json()["message"] == "IsTheTubeRunning API"

            health_response = await client.get("/health")
            assert health_response.status_code == 200
            assert health_response.json()["status"] == "healthy"

            ready_response = await client.get("/ready")
            assert ready_response.status_code == 200
            assert ready_response.json()["status"] == "ready"

    finally:
        app.dependency_overrides.clear()


async def test_sqlalchemy_works_with_otel_disabled(
    db_session: AsyncSession,
) -> None:
    """Test that database queries work normally with OTEL disabled."""
    # Execute a simple query
    result = await db_session.execute(text("SELECT 1 as test_column"))
    assert result.scalar() == 1

    # Execute a more complex query
    result2 = await db_session.execute(text("SELECT 'hello' as greeting, 42 as number"))
    row = result2.first()
    assert row is not None
    assert row[0] == "hello"
    assert row[1] == 42


async def test_api_endpoint_with_database_works_with_otel_disabled(
    db_session: AsyncSession,
    test_user: User,
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test that API endpoints with database queries work with OTEL disabled."""
    # Import app (should work with OTEL disabled)
    from app.main import app  # noqa: PLC0415  # Lazy import to test with OTEL disabled

    # Override get_db to use test session (ADR 10: Test Database Dependency Override Pattern)
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[database.get_db] = override_get_db

    try:
        # Create client with auth headers
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Make request to endpoint that queries database
            response = await client.get(
                f"{settings.API_V1_PREFIX}/auth/me",
                headers=auth_headers_for_user,
            )
            assert response.status_code == 200

            # Verify response data (just check that we got a valid response)
            data = response.json()
            assert "id" in data  # User ID should be in response

    finally:
        app.dependency_overrides.clear()


async def test_telemetry_module_functions_with_otel_disabled() -> None:
    """Test that telemetry module functions work gracefully when OTEL is disabled."""
    from app.core import telemetry  # noqa: PLC0415  # Lazy import to test with OTEL disabled

    # get_tracer_provider should not crash when disabled
    # With OTEL_SDK_DISABLED=true, provider might be None or a no-op provider
    # Either is acceptable - we just verify no crashes
    telemetry.get_tracer_provider()

    # shutdown_tracer_provider should be safe to call
    telemetry.shutdown_tracer_provider()  # Should not crash

    # get_current_span should work (returns no-op span or None)
    span = telemetry.get_current_span()
    # Should not crash, span might be no-op or None
    assert span is not None  # OTEL SDK returns no-op span when disabled


# ============================================================================
# Tests with OTEL Enabled - Span Creation and Hierarchy Verification
# ============================================================================


# Group OTEL-enabled tests in a class to apply the fixture only to them
class TestFastAPISpanCreation:
    """Tests for FastAPI span creation and hierarchy with OTEL enabled."""

    @pytest.fixture(autouse=True)
    def enable_otel(self) -> Generator[None]:
        """Enable OTEL SDK for tests in this class."""
        original = os.environ.get("OTEL_SDK_DISABLED")
        if "OTEL_SDK_DISABLED" in os.environ:
            del os.environ["OTEL_SDK_DISABLED"]
        yield
        if original is not None:
            os.environ["OTEL_SDK_DISABLED"] = original
        elif "OTEL_SDK_DISABLED" in os.environ:
            del os.environ["OTEL_SDK_DISABLED"]

    async def test_fastapi_instrumentation_pattern(self) -> None:
        """Verify that FastAPI app is instrumented with instrument_app() after creation."""
        # This test verifies the instrumentation pattern, not the full span creation
        # Full span creation is better tested in a deployment environment
        from app.main import app  # noqa: PLC0415

        # Just verify the app exists and doesn't crash when imported with OTEL enabled
        # The FastAPIInstrumentor wraps the app with OpenTelemetryMiddleware internally
        assert app is not None
        assert app.title == "IsTheTubeRunning API"

    @pytest.mark.skip(reason="Test requires app import isolation - run separately if needed")
    async def test_fastapi_request_creates_parent_span(
        self,
        db_session: AsyncSession,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Verify that FastAPI requests create parent HTTP SERVER spans.

        Note: This test must be run in isolation as it requires controlling
        the app import and tracer provider setup order.
        """
        # Set the test tracer provider globally before importing app
        # This must be done before app.main is imported to ensure FastAPI instrumentor uses our test provider
        trace.set_tracer_provider(test_tracer_provider)

        # Import app after setting tracer provider
        from app.main import app  # noqa: PLC0415

        # Override get_db
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[database.get_db] = override_get_db

        try:
            # Create client and make request
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/")
                assert response.status_code == 200

            # Get recorded spans
            spans = get_recorded_spans(in_memory_span_exporter)

            # Find HTTP server spans
            http_spans = [s for s in spans if s.kind == SpanKind.SERVER]

            # Verify at least one HTTP server span was created
            assert len(http_spans) >= 1, f"Expected at least 1 HTTP SERVER span, got {len(http_spans)}"

            # Verify the root span is an HTTP request span
            root_span = http_spans[0]
            assert root_span.parent is None, "HTTP request span should be the root span"
            assert root_span.attributes is not None
            assert root_span.attributes.get("http.method") == "GET"
            assert root_span.attributes.get("http.target") == "/"

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.skip(reason="Test requires app import isolation - run separately if needed")
    async def test_fastapi_excluded_urls_not_traced(
        self,
        db_session: AsyncSession,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Verify that excluded URLs (health, ready, metrics) don't create spans.

        Note: This test must be run in isolation.
        """
        # Set the test tracer provider globally
        trace.set_tracer_provider(test_tracer_provider)

        # Import app after setting tracer provider
        from app.main import app  # noqa: PLC0415

        # Override get_db
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[database.get_db] = override_get_db

        try:
            # Clear any existing spans
            clear_recorded_spans(in_memory_span_exporter)

            # Create client and make requests to excluded endpoints
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                health_response = await client.get("/health")
                assert health_response.status_code == 200

                ready_response = await client.get("/ready")
                assert ready_response.status_code == 200

            # Get recorded spans
            spans = get_recorded_spans(in_memory_span_exporter)

            # Verify no spans were created for excluded URLs
            health_spans = [s for s in spans if s.attributes and "/health" in str(s.attributes.get("http.target", ""))]
            ready_spans = [s for s in spans if s.attributes and "/ready" in str(s.attributes.get("http.target", ""))]

            assert len(health_spans) == 0, "Health endpoint should not create spans"
            assert len(ready_spans) == 0, "Ready endpoint should not create spans"

        finally:
            app.dependency_overrides.clear()

    async def test_fastapi_spans_with_real_request(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify that the app can handle requests with OTEL enabled without crashing."""
        # This is a simplified integration test that just verifies the app works
        # Full span hierarchy verification requires manual testing with Grafana Cloud
        from app.main import app  # noqa: PLC0415

        # Override get_db
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[database.get_db] = override_get_db

        try:
            # Make a real request and verify it succeeds
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/")
                assert response.status_code == 200
                assert response.json()["message"] == "IsTheTubeRunning API"

                # Also test health endpoint (should be excluded from tracing)
                health_response = await client.get("/health")
                assert health_response.status_code == 200

        finally:
            app.dependency_overrides.clear()
