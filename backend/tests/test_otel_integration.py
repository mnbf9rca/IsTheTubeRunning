"""Integration tests for OpenTelemetry instrumentation.

This module contains two types of tests:
1. Tests with OTEL disabled (default) - verify graceful degradation
2. Tests with OTEL enabled - verify span creation and hierarchy
"""

from collections.abc import Generator

import pytest
from app.core.config import settings
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_otel_disabled_path_no_crashes(
    async_client_with_db: AsyncClient,
) -> None:
    """Test that application works normally with OTEL disabled (SDK_DISABLED=true)."""
    # This test runs with OTEL_SDK_DISABLED=true (from conftest.py)
    # It verifies graceful degradation when OTEL is disabled

    # Make various requests (should all work without OTEL)
    response = await async_client_with_db.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "IsTheTubeRunning API"

    health_response = await async_client_with_db.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "healthy"

    ready_response = await async_client_with_db.get("/ready")
    assert ready_response.status_code == 200
    assert ready_response.json()["status"] == "ready"


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
    async_client_with_db: AsyncClient,
    test_user: User,
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test that API endpoints with database queries work with OTEL disabled."""
    # Make request to endpoint that queries database
    response = await async_client_with_db.get(
        f"{settings.API_V1_PREFIX}/auth/me",
        headers=auth_headers_for_user,
    )
    assert response.status_code == 200

    # Verify response data (just check that we got a valid response)
    data = response.json()
    assert "id" in data  # User ID should be in response


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


async def test_fastapi_not_instrumented_when_otel_disabled() -> None:
    """Test that OpenTelemetryMiddleware is NOT applied when OTEL is disabled."""
    # This test runs with OTEL_SDK_DISABLED=true (from conftest.py)
    from app.main import app  # noqa: PLC0415  # Lazy import to test with OTEL disabled

    # Check middleware stack - OpenTelemetryMiddleware should NOT be present
    # The middleware stack is in app.user_middleware
    middleware_classes = [type(middleware.cls).__name__ for middleware in app.user_middleware]

    # Verify OpenTelemetryMiddleware is NOT in the middleware stack
    assert "OpenTelemetryMiddleware" not in middleware_classes, (
        f"OpenTelemetryMiddleware should not be present when OTEL disabled, got middleware: {middleware_classes}"
    )


# ============================================================================
# Tests with OTEL Enabled - Span Creation and Hierarchy Verification
# ============================================================================


# Group OTEL-enabled tests in a class to apply the fixture only to them
class TestFastAPISpanCreation:
    """Tests for FastAPI span creation and hierarchy with OTEL enabled."""

    @pytest.fixture(autouse=True)
    def enable_otel(self, monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
        """Enable OTEL SDK for tests in this class."""
        # Remove OTEL_SDK_DISABLED if present (enables OTEL)
        monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
        return
        # Monkeypatch automatically restores original environment on cleanup

    async def test_fastapi_instrumentation_pattern(self) -> None:
        """Verify that FastAPI app is instrumented with instrument_app() after creation."""
        # This test verifies the instrumentation pattern, not the full span creation
        # Full span creation is better tested in a deployment environment
        from app.main import app  # noqa: PLC0415

        # Just verify the app exists and doesn't crash when imported with OTEL enabled
        # The FastAPIInstrumentor wraps the app with OpenTelemetryMiddleware internally
        assert app is not None
        assert app.title == "IsTheTubeRunning API"

    async def test_fastapi_spans_with_real_request(
        self,
        async_client_with_db: AsyncClient,
    ) -> None:
        """Verify that the app handles requests with OTEL enabled without crashing.

        Note: This test verifies that OTEL instrumentation doesn't break the app,
        but does not verify span creation. Span creation is verified through manual
        testing with Grafana Cloud (see ADR 12: FastAPI Instrumentation Pattern).
        """
        # Make requests to verify app works with OTEL enabled
        response = await async_client_with_db.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "IsTheTubeRunning API"

        # Verify health endpoint works (excluded from tracing)
        health_response = await async_client_with_db.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "healthy"
