"""Integration tests for OpenTelemetry instrumentation.

Note: These tests focus on verifying that OTEL instrumentation doesn't break
the application. Comprehensive span verification is complex in pytest due to
SDK initialization timing and is better tested in a deployment environment.
"""

from collections.abc import AsyncGenerator

from app.core import database
from app.core.config import settings
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
    async_client: AsyncClient,
    test_user: User,
    auth_headers_for_user: dict[str, str],
) -> None:
    """Test that API endpoints with database queries work with OTEL disabled."""
    # Make request to endpoint that queries database
    response = await async_client.get(
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
