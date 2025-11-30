"""Tests for Admin Service OpenTelemetry instrumentation."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.schemas.admin import UserDetailResponse
from app.services.admin_service import AdminService
from fastapi import HTTPException
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from tests.helpers.otel import assert_span_status


class TestAdminServiceOtelSpans:
    """Test class for Admin Service OpenTelemetry instrumentation."""

    @pytest.mark.asyncio
    async def test_anonymise_user_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that anonymise_user creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

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

        await admin_svc.anonymise_user(user_id)

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
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
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception when user not found."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        # Mock get_user_details to raise HTTPException
        user_id = uuid.uuid4()
        admin_svc.get_user_details = AsyncMock(side_effect=HTTPException(status_code=404, detail="User not found"))

        with pytest.raises(HTTPException, match="User not found"):
            await admin_svc.anonymise_user(user_id)

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.anonymise_user"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_anonymise_user_records_exception_on_already_deleted(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception when user already deleted."""
        _, exporter = otel_enabled_provider

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

        with pytest.raises(HTTPException, match="User is already deleted"):
            await admin_svc.anonymise_user(user_id)

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.anonymise_user"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_anonymise_user_records_exception_on_database_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception on database errors."""
        _, exporter = otel_enabled_provider

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

        with pytest.raises(Exception, match="Database connection error"):
            await admin_svc.anonymise_user(user_id)

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.anonymise_user"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

        # Verify rollback was called
        assert mock_db.rollback.called

    @pytest.mark.asyncio
    async def test_get_users_paginated_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that get_users_paginated creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        # Mock users query result
        mock_users_result = MagicMock()
        mock_unique = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_unique.scalars.return_value = mock_scalars
        mock_users_result.unique.return_value = mock_unique

        # Set up execute to return different results for different queries
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_users_result])

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        _users, _total = await admin_svc.get_users_paginated(limit=10, offset=0, search="test")

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.get_users_paginated"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "admin-service"
        assert span.attributes["admin.operation"] == "get_users_paginated"
        assert span.attributes["admin.limit"] == 10
        assert span.attributes["admin.offset"] == 0
        assert span.attributes["admin.search_enabled"] is True
        assert span.attributes["admin.include_deleted"] is False
        assert span.attributes["admin.result_count"] == 0
        assert span.attributes["admin.total_count"] == 5

    @pytest.mark.asyncio
    async def test_get_users_paginated_records_exception_on_database_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception when database query fails."""
        _, exporter = otel_enabled_provider

        # Create mock database session that raises exception
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("Database query failed"))

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        with pytest.raises(Exception, match="Database query failed"):
            await admin_svc.get_users_paginated()

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.get_users_paginated"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)

    @pytest.mark.asyncio
    async def test_get_engagement_metrics_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that get_engagement_metrics creates a span with OK status on success."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        # Mock all private helper methods
        admin_svc._count_total_users = AsyncMock(return_value=100)
        admin_svc._count_active_users = AsyncMock(return_value=50)
        admin_svc._count_users_with_verified_email = AsyncMock(return_value=60)
        admin_svc._count_users_with_verified_phone = AsyncMock(return_value=30)
        admin_svc._count_admin_users = AsyncMock(return_value=5)
        admin_svc._count_total_routes = AsyncMock(return_value=150)
        admin_svc._count_active_routes = AsyncMock(return_value=120)
        admin_svc._get_routes_user_count = AsyncMock(return_value=(150, 50))
        admin_svc._count_total_notifications = AsyncMock(return_value=500)
        admin_svc._count_successful_notifications = AsyncMock(return_value=480)
        admin_svc._count_failed_notifications = AsyncMock(return_value=20)
        admin_svc._get_notifications_by_method = AsyncMock(return_value={"email": 300, "sms": 200})
        admin_svc._count_new_users_since = AsyncMock(return_value=10)
        admin_svc._get_daily_signups_since = AsyncMock(return_value=[])

        metrics = await admin_svc.get_engagement_metrics()

        # Verify metrics were returned
        assert metrics is not None
        assert metrics.user_counts.total_users == 100

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.get_engagement_metrics"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "admin-service"
        assert span.attributes["admin.operation"] == "get_engagement_metrics"

    @pytest.mark.asyncio
    async def test_get_engagement_metrics_records_exception_on_database_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception when database operation fails."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        # Create admin service
        admin_svc = AdminService(db=mock_db)

        # Mock helper method to raise exception
        admin_svc._count_total_users = AsyncMock(side_effect=Exception("Database connection lost"))

        with pytest.raises(Exception, match="Database connection lost"):
            await admin_svc.get_engagement_metrics()

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "admin.get_engagement_metrics"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)
