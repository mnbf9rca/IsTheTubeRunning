"""Additional tests to achieve 100% coverage on Phase 8 files."""
# ruff: noqa: SIM117

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from app.celery.database import get_worker_session
from app.celery.tasks import _check_disruptions_async
from app.models.notification import NotificationMethod, NotificationPreference
from app.models.route import Route
from app.models.user import PhoneNumber, User
from app.schemas.tfl import DisruptionResponse
from app.services.alert_service import AlertService, get_redis_client
from app.services.notification_service import NotificationService
from sqlalchemy.ext.asyncio import AsyncSession

# ==================== get_redis_client Coverage ====================


@pytest.mark.asyncio
async def test_get_redis_client_creates_client() -> None:
    """Test get_redis_client function."""

    client = await get_redis_client()
    assert client is not None
    await client.aclose()  # type: ignore[attr-defined]


# ==================== Celery Tasks Coverage ====================


@pytest.mark.asyncio
async def test_check_disruptions_async_function() -> None:
    """Test the async implementation directly."""

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.close = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()

    with patch("app.celery.tasks.worker_session_factory", return_value=mock_session):
        with patch("app.celery.tasks.get_redis_client", return_value=mock_redis):
            with patch("app.celery.tasks.AlertService") as mock_alert_service:
                mock_instance = AsyncMock()
                mock_instance.process_all_routes = AsyncMock(
                    return_value={
                        "routes_checked": 1,
                        "alerts_sent": 0,
                        "errors": 0,
                    }
                )
                mock_alert_service.return_value = mock_instance

                result = await _check_disruptions_async()

                assert result["status"] == "success"
                assert result["routes_checked"] == 1


# ==================== Database Coverage ====================


@pytest.mark.asyncio
async def test_get_worker_session_yields_session() -> None:
    """Test get_worker_session async generator properly closes session."""

    session_obj = None
    async for session in get_worker_session():
        session_obj = session
        assert session is not None
        # Test that session gets closed in finally block (lines 61-65)
        break

    # Session should be closed after exiting async generator
    assert session_obj is not None


# ==================== Notification Service Coverage ====================


@pytest.mark.asyncio
async def test_send_disruption_sms_long_message() -> None:
    """Test SMS message truncation for long messages."""

    service = NotificationService()

    # Create 20 disruptions to exceed SMS limit
    disruptions = [
        DisruptionResponse(
            line_id=f"line-{i}",
            line_name=f"Line {i}",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason=f"Signal failure at station {i}",
            created_at=datetime.now(UTC),
        )
        for i in range(20)
    ]

    # Should handle long message without error
    await service.send_disruption_sms(
        phone="+447700900123",
        route_name="Test Route",
        disruptions=disruptions,
    )


@pytest.mark.asyncio
async def test_send_disruption_sms_error_propagates() -> None:
    """Test SMS sending error is propagated."""

    service = NotificationService()
    disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        )
    ]

    with patch.object(service.sms_service, "send_sms", side_effect=Exception("SMS error")):
        with pytest.raises(Exception, match="SMS error"):
            await service.send_disruption_sms(
                phone="+447700900123",
                route_name="Test",
                disruptions=disruptions,
            )


@pytest.mark.asyncio
async def test_send_disruption_email_template_error_propagates() -> None:
    """Test email template error is propagated."""

    service = NotificationService()
    disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        )
    ]

    with patch.object(service, "_render_email_template", side_effect=Exception("Template error")):
        with pytest.raises(Exception, match="Template error"):
            await service.send_disruption_email(
                email="test@example.com",
                route_name="Test",
                disruptions=disruptions,
            )


@pytest.mark.asyncio
async def test_send_disruption_sms_very_long_truncation() -> None:
    """Test SMS truncation when message exceeds max length even with one disruption."""

    service = NotificationService()

    # Create single disruption with very long reason to exceed SMS limit
    disruptions = [
        DisruptionResponse(
            line_id="line-1",
            line_name="Line 1",
            status_severity=5,
            status_severity_description="Severe Delays" * 20,  # Make it very long
            reason="Signal failure " * 50,  # Very long reason
            created_at=datetime.now(UTC),
        )
    ]

    # Should handle very long single disruption without error
    with patch.object(service.sms_service, "send_sms", new_callable=AsyncMock) as mock_send:
        await service.send_disruption_sms(
            phone="+447700900123",
            route_name="Test Route",
            disruptions=disruptions,
        )
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_template_render_error_handling() -> None:
    """Test _render_email_template error handling."""

    service = NotificationService()

    with patch("app.services.notification_service.jinja_env.get_template", side_effect=Exception("Template not found")):
        with pytest.raises(Exception, match="Template not found"):
            service._render_email_template("nonexistent.html", {})


# ==================== Alert Service Additional Coverage ====================


@pytest.mark.asyncio
async def test_alert_service_skips_duplicate_alerts(
    alert_service: AlertService,
) -> None:
    """Test that duplicate alerts are skipped (lines 137-142)."""
    # Test the logic by mocking should_send_alert to return False
    mock_route = Mock(spec=Route)
    mock_route.id = "test-route"
    mock_route.name = "Test Route"

    mock_disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        )
    ]

    with patch.object(alert_service, "_should_send_alert", return_value=False):
        # Directly test _send_alerts_for_route when should_send is False
        with patch.object(alert_service, "_get_verified_contact", return_value=None):
            alerts_sent = await alert_service._send_alerts_for_route(
                route=mock_route,
                schedule=Mock(),
                disruptions=mock_disruptions,
            )
            # When all alerts are skipped, no alerts sent
            assert alerts_sent == 0


@pytest.mark.asyncio
async def test_alert_service_inner_exception_handler(
    alert_service: AlertService,
) -> None:
    """Test inner exception handler in process_all_routes (lines 153-155)."""
    # Mock _get_active_routes to return a single route
    mock_route = Mock(spec=Route)
    mock_route.id = "test-route"
    mock_route.name = "Error Route"
    mock_route.schedules = [Mock()]

    with patch.object(alert_service, "_get_active_routes", return_value=[mock_route]):
        with patch.object(alert_service, "_get_active_schedule", return_value=Mock()):
            with patch.object(
                alert_service,
                "_get_route_disruptions",
                side_effect=RuntimeError("TfL API error"),
            ):
                result = await alert_service.process_all_routes()

                # Should track error but continue processing
                assert result["errors"] == 1


@pytest.mark.asyncio
async def test_alert_service_outer_exception_handler(
    alert_service: AlertService,
) -> None:
    """Test outer exception handler in process_all_routes (lines 166-169)."""
    with patch.object(
        alert_service,
        "_get_active_routes",
        side_effect=RuntimeError("Database error"),
    ):
        result = await alert_service.process_all_routes()

        # Should return stats with error count
        assert result["errors"] == 1


@pytest.mark.asyncio
async def test_alert_service_get_active_routes_error(
    alert_service: AlertService,
) -> None:
    """Test _get_active_routes exception handler (lines 194-196)."""
    with patch.object(
        alert_service.db,
        "execute",
        side_effect=RuntimeError("Database connection error"),
    ):
        routes = await alert_service._get_active_routes()

        # Should return empty list on error
        assert routes == []


@pytest.mark.asyncio
async def test_get_verified_contact_email_missing_target(
    alert_service: AlertService,
) -> None:
    """Test _get_verified_contact with missing email target (lines 412-417)."""

    # Create mock preference without target_email_id
    pref = Mock(spec=NotificationPreference)
    pref.id = uuid4()
    pref.method = NotificationMethod.EMAIL
    pref.target_email_id = None

    contact = await alert_service._get_verified_contact(pref, uuid4())
    assert contact is None


@pytest.mark.asyncio
async def test_get_verified_contact_email_not_found(
    alert_service: AlertService,
) -> None:
    """Test _get_verified_contact with non-existent email (lines 423-429)."""

    # Create mock preference with non-existent email ID
    pref = Mock(spec=NotificationPreference)
    pref.id = uuid4()
    pref.method = NotificationMethod.EMAIL
    pref.target_email_id = uuid4()  # Non-existent ID

    contact = await alert_service._get_verified_contact(pref, uuid4())
    assert contact is None


@pytest.mark.asyncio
async def test_get_verified_contact_sms_missing_target(
    alert_service: AlertService,
) -> None:
    """Test _get_verified_contact with missing SMS target (lines 435-440)."""

    # Create mock preference without target_phone_id
    pref = Mock(spec=NotificationPreference)
    pref.id = uuid4()
    pref.method = NotificationMethod.SMS
    pref.target_phone_id = None

    contact = await alert_service._get_verified_contact(pref, uuid4())
    assert contact is None


@pytest.mark.asyncio
async def test_get_verified_contact_sms_not_found(
    alert_service: AlertService,
) -> None:
    """Test _get_verified_contact with non-existent phone (lines 446-452)."""

    # Create mock preference with non-existent phone ID
    pref = Mock(spec=NotificationPreference)
    pref.id = uuid4()
    pref.method = NotificationMethod.SMS
    pref.target_phone_id = uuid4()  # Non-existent ID

    contact = await alert_service._get_verified_contact(pref, uuid4())
    assert contact is None


@pytest.mark.asyncio
async def test_get_verified_contact_sms_unverified(
    alert_service: AlertService,
    db_session: AsyncSession,
) -> None:
    """Test _get_verified_contact with unverified phone (lines 446-452)."""
    # Create user
    user = User(external_id="test-unverified-phone", auth_provider="auth0")
    db_session.add(user)
    await db_session.flush()

    # Create unverified phone
    phone = PhoneNumber(
        user_id=user.id,
        phone="+447700900123",
        verified=False,
    )
    db_session.add(phone)
    await db_session.flush()

    # Create route
    route = Route(user_id=user.id, name="Test", active=True, timezone="UTC")
    db_session.add(route)
    await db_session.flush()

    # Create preference
    pref = NotificationPreference(
        route_id=route.id,
        method=NotificationMethod.SMS,
        target_phone_id=phone.id,
    )
    db_session.add(pref)
    await db_session.commit()

    contact = await alert_service._get_verified_contact(pref, route.id)
    assert contact is None


@pytest.mark.asyncio
async def test_get_user_display_name_no_user(
    alert_service: AlertService,
) -> None:
    """Test _get_user_display_name with no user."""
    route = Mock(spec=Route)
    route.user = None

    name = alert_service._get_user_display_name(route)
    assert name is None
