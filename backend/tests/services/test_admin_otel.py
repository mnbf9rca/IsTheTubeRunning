"""Tests for Admin Service OpenTelemetry instrumentation."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.schemas.admin import UserDetailResponse
from app.services import admin_service
from app.services.admin_service import AdminService
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


class TestAdminServiceOtelSpans:
    """Test class for Admin Service OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_anonymise_user_creates_span_with_ok_status(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that anonymise_user creates a span with OK status on success."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(admin_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        # Create mock user
        user_id = uuid.uuid4()
        mock_user = UserDetailResponse(
            id=user_id,
            external_id="auth0|123456",
            auth_provider="auth0",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deleted_at=None,
            email_addresses=[],
            phone_numbers=[],
            route_count=1,
            active_route_count=1,
        )

        # Mock get_user_details to return the mock user
        admin_svc.get_user_details = AsyncMock(return_value=mock_user)

        with patch("opentelemetry.trace.get_tracer", return_value=test_tracer):
            await admin_svc.anonymise_user(user_id)

        # Verify span was created with OK status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.anonymise_user"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "admin-service"
        assert span.attributes["admin.user_id"] == str(user_id)
        assert span.attributes["admin.operation"] == "anonymise_user"

        # Verify database operations were called
        assert mock_db.execute.call_count >= 5  # At least 5 delete/update operations
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_anonymise_user_records_exception_on_user_not_found(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception when user not found."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(admin_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        # Mock get_user_details to raise HTTPException
        user_id = uuid.uuid4()
        admin_svc.get_user_details = AsyncMock(side_effect=HTTPException(status_code=404, detail="User not found"))

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            pytest.raises(HTTPException, match="User not found"),
        ):
            await admin_svc.anonymise_user(user_id)

        # Verify span has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.anonymise_user"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_anonymise_user_records_exception_on_already_deleted(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception when user already deleted."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(admin_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        # Create mock user that's already deleted
        user_id = uuid.uuid4()
        mock_user = UserDetailResponse(
            id=user_id,
            external_id=f"deleted_{user_id}",
            auth_provider="",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deleted_at=datetime.now(UTC),  # Already deleted!
            email_addresses=[],
            phone_numbers=[],
            route_count=0,
            active_route_count=0,
        )

        # Mock get_user_details to return already-deleted user
        admin_svc.get_user_details = AsyncMock(return_value=mock_user)

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            pytest.raises(HTTPException, match="User is already deleted"),
        ):
            await admin_svc.anonymise_user(user_id)

        # Verify span has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.anonymise_user"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_anonymise_user_records_exception_on_database_error(
        self,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception on database errors."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(admin_service.__name__)

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("Database connection error"))
        mock_db.rollback = AsyncMock()

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        # Create mock user
        user_id = uuid.uuid4()
        mock_user = UserDetailResponse(
            id=user_id,
            external_id="auth0|123456",
            auth_provider="auth0",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deleted_at=None,
            email_addresses=[],
            phone_numbers=[],
            route_count=1,
            active_route_count=1,
        )

        # Mock get_user_details to return the mock user
        admin_svc.get_user_details = AsyncMock(return_value=mock_user)

        with (
            patch("opentelemetry.trace.get_tracer", return_value=test_tracer),
            pytest.raises(Exception, match="Database connection error"),
        ):
            await admin_svc.anonymise_user(user_id)

        # Verify span has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.anonymise_user"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

        # Verify rollback was called
        assert mock_db.rollback.called
