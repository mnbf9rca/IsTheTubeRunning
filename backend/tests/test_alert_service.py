"""Tests for AlertService."""

import json
from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
import redis.asyncio as redis
from app.models.notification import (
    NotificationLog,
    NotificationMethod,
    NotificationPreference,
    NotificationStatus,
)
from app.models.route import Route, RouteSchedule, RouteSegment
from app.models.tfl import Line, Station
from app.models.user import EmailAddress, PhoneNumber, User
from app.schemas.tfl import DisruptionResponse
from app.services.alert_service import AlertService, get_redis_client
from freezegun import freeze_time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# ==================== Fixtures ====================


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client for testing."""
    client = AsyncMock(spec=redis.Redis)
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock()
    return client


@pytest.fixture
def alert_service(db_session: AsyncSession, mock_redis: AsyncMock) -> AlertService:
    """Create AlertService instance with mocked Redis."""
    return AlertService(db=db_session, redis_client=mock_redis)


@pytest.fixture
async def test_user_with_contacts(db_session: AsyncSession) -> User:
    """Create test user with email and phone contacts."""
    user = User(external_id="test-user-alerts", auth_provider="auth0")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Add verified email
    email = EmailAddress(user_id=user.id, email="test@example.com", verified=True, is_primary=True)
    db_session.add(email)

    # Add verified phone
    phone = PhoneNumber(user_id=user.id, phone="+1234567890", verified=True, is_primary=True)
    db_session.add(phone)

    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest.fixture
async def test_line(db_session: AsyncSession) -> Line:
    """Create test line."""
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.commit()
    await db_session.refresh(line)
    return line


@pytest.fixture
async def test_station(db_session: AsyncSession) -> Station:
    """Create test station."""
    station = Station(
        tfl_id="940GZZLUKSX",
        name="King's Cross",
        latitude=51.5308,
        longitude=-0.1238,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add(station)
    await db_session.commit()
    await db_session.refresh(station)
    return station


@pytest.fixture
async def test_route_with_schedule(
    db_session: AsyncSession,
    test_user_with_contacts: User,
    test_line: Line,
    test_station: Station,
) -> Route:
    """Create test route with schedule and notification preferences."""
    route = Route(
        user_id=test_user_with_contacts.id,
        name="Morning Commute",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.flush()

    # Add segment
    segment = RouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    # Add weekday schedule (8:00 AM - 10:00 AM)
    schedule = RouteSchedule(
        route_id=route.id,
        days_of_week=["MON", "TUE", "WED", "THU", "FRI"],
        start_time=time(8, 0),
        end_time=time(10, 0),
    )
    db_session.add(schedule)

    # Add email notification preference
    email_result = await db_session.execute(
        select(EmailAddress).where(EmailAddress.user_id == test_user_with_contacts.id)
    )
    email = email_result.scalar_one()

    notification_pref = NotificationPreference(
        route_id=route.id,
        method=NotificationMethod.EMAIL,
        target_email_id=email.id,
    )
    db_session.add(notification_pref)

    await db_session.commit()

    # Reload with relationships using selectinload
    result = await db_session.execute(
        select(Route)
        .where(Route.id == route.id)
        .options(
            selectinload(Route.segments),
            selectinload(Route.schedules),
            selectinload(Route.notification_preferences),
            selectinload(Route.user).selectinload(User.email_addresses),
        )
    )
    return result.scalar_one()


@pytest.fixture
def sample_disruptions() -> list[DisruptionResponse]:
    """Sample disruptions for testing."""
    return [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure at King's Cross",
            created_at=datetime.now(UTC),
        ),
    ]


# ==================== process_all_routes Tests ====================


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
@patch("app.services.alert_service.NotificationService")
@freeze_time("2025-01-15 08:30:00", tz_offset=0)  # Wednesday 8:30 AM UTC
async def test_process_all_routes_success(
    mock_notif_class: MagicMock,
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test successful processing of all routes."""
    # Mock TfL service
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_disruptions = AsyncMock(return_value=sample_disruptions)
    mock_tfl_class.return_value = mock_tfl_instance

    # Mock notification service
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock()
    mock_notif_class.return_value = mock_notif_instance

    # Execute
    result = await alert_service.process_all_routes()

    # Verify
    assert result["routes_checked"] == 1
    assert result["alerts_sent"] == 1
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_process_all_routes_no_active_routes(alert_service: AlertService) -> None:
    """Test processing when there are no active routes."""
    result = await alert_service.process_all_routes()

    assert result["routes_checked"] == 0
    assert result["alerts_sent"] == 0
    assert result["errors"] == 0


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
@freeze_time("2025-01-15 12:00:00", tz_offset=0)  # Wednesday 12:00 PM UTC (outside schedule)
async def test_process_all_routes_not_in_schedule(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test processing when route is not in schedule window."""
    # Mock TfL service
    mock_tfl_instance = AsyncMock()
    mock_tfl_class.return_value = mock_tfl_instance

    result = await alert_service.process_all_routes()

    # Route checked but not in schedule, so no disruptions fetched
    assert result["routes_checked"] == 1
    assert result["alerts_sent"] == 0
    assert result["errors"] == 0


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
@freeze_time("2025-01-15 08:30:00", tz_offset=0)  # Wednesday 8:30 AM UTC
async def test_process_all_routes_no_disruptions(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test processing when there are no disruptions."""
    # Mock TfL service with empty disruptions
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_disruptions = AsyncMock(return_value=[])
    mock_tfl_class.return_value = mock_tfl_instance

    result = await alert_service.process_all_routes()

    assert result["routes_checked"] == 1
    assert result["alerts_sent"] == 0
    assert result["errors"] == 0


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
@freeze_time("2025-01-15 08:30:00", tz_offset=0)
async def test_process_all_routes_with_error(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test that errors in individual routes don't stop processing."""
    # Mock TfL service to raise error
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_disruptions = AsyncMock(side_effect=Exception("TfL API error"))
    mock_tfl_class.return_value = mock_tfl_instance

    result = await alert_service.process_all_routes()

    assert result["routes_checked"] == 1
    assert result["alerts_sent"] == 0
    assert result["errors"] == 1


# ==================== _get_active_routes Tests ====================


@pytest.mark.asyncio
async def test_get_active_routes_returns_only_active(
    alert_service: AlertService,
    db_session: AsyncSession,
    test_user_with_contacts: User,
) -> None:
    """Test that only active routes are returned."""
    # Create active route
    active_route = Route(
        user_id=test_user_with_contacts.id,
        name="Active Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(active_route)

    # Create inactive route
    inactive_route = Route(
        user_id=test_user_with_contacts.id,
        name="Inactive Route",
        active=False,
        timezone="Europe/London",
    )
    db_session.add(inactive_route)

    await db_session.commit()

    routes = await alert_service._get_active_routes()

    assert len(routes) == 1
    assert routes[0].name == "Active Route"


@pytest.mark.asyncio
async def test_get_active_routes_filters_deleted(
    alert_service: AlertService,
    db_session: AsyncSession,
    test_user_with_contacts: User,
) -> None:
    """Test that deleted routes are filtered out."""
    # Create active route
    active_route = Route(
        user_id=test_user_with_contacts.id,
        name="Active Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(active_route)

    # Create deleted route
    deleted_route = Route(
        user_id=test_user_with_contacts.id,
        name="Deleted Route",
        active=True,
        timezone="Europe/London",
        deleted_at=datetime.now(UTC),
    )
    db_session.add(deleted_route)

    await db_session.commit()

    routes = await alert_service._get_active_routes()

    assert len(routes) == 1
    assert routes[0].name == "Active Route"


@pytest.mark.asyncio
async def test_get_active_routes_preloads_relationships(
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test that relationships are preloaded."""
    routes = await alert_service._get_active_routes()

    assert len(routes) == 1
    route = routes[0]

    # Verify relationships are loaded (won't cause additional queries)
    assert route.segments is not None
    assert route.schedules is not None
    assert route.notification_preferences is not None
    assert route.user is not None


# ==================== _get_active_schedule Tests ====================


@pytest.mark.asyncio
@freeze_time("2025-01-15 08:30:00", tz_offset=0)  # Wednesday 8:30 AM UTC
async def test_get_active_schedule_in_window(
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test getting active schedule when route is in schedule window."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule)

    assert schedule is not None
    assert schedule.start_time == time(8, 0)
    assert schedule.end_time == time(10, 0)


@pytest.mark.asyncio
@freeze_time("2025-01-15 07:30:00", tz_offset=0)  # Wednesday 7:30 AM UTC (before schedule)
async def test_get_active_schedule_outside_window(
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test getting active schedule when route is outside schedule window."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule)

    assert schedule is None


@pytest.mark.asyncio
@freeze_time("2025-01-18 08:30:00", tz_offset=0)  # Saturday 8:30 AM UTC
async def test_get_active_schedule_wrong_day(
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test getting active schedule on weekend (not in schedule days)."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule)

    assert schedule is None


@pytest.mark.asyncio
@freeze_time("2025-01-15 14:00:00")  # Wednesday 14:00 UTC = 9:00 AM EST (within 8-10 AM schedule)
async def test_get_active_schedule_different_timezone(
    alert_service: AlertService,
    db_session: AsyncSession,
    test_user_with_contacts: User,
    test_line: Line,
    test_station: Station,
) -> None:
    """Test schedule checking with different timezone (America/New_York)."""
    # Create route with New York timezone
    route = Route(
        user_id=test_user_with_contacts.id,
        name="NYC Commute",
        active=True,
        timezone="America/New_York",
    )
    db_session.add(route)
    await db_session.flush()

    # Add segment
    segment = RouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    # Schedule: 8:00 AM - 10:00 AM EST
    schedule = RouteSchedule(
        route_id=route.id,
        days_of_week=["MON", "TUE", "WED", "THU", "FRI"],
        start_time=time(8, 0),
        end_time=time(10, 0),
    )
    db_session.add(schedule)
    await db_session.commit()
    await db_session.refresh(route)

    # Current time: 9:00 AM EST = 2:00 PM UTC (within schedule)
    active_schedule = await alert_service._get_active_schedule(route, [schedule])

    assert active_schedule is not None


@pytest.mark.asyncio
@freeze_time("2025-01-15 08:00:00", tz_offset=0)  # Wednesday 8:00 AM UTC (boundary)
async def test_get_active_schedule_at_start_boundary(
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test schedule matching at exact start time."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule)

    assert schedule is not None


@pytest.mark.asyncio
@freeze_time("2025-01-15 10:00:00", tz_offset=0)  # Wednesday 10:00 AM UTC (boundary)
async def test_get_active_schedule_at_end_boundary(
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test schedule matching at exact end time."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule)

    assert schedule is not None


@pytest.mark.asyncio
@freeze_time("2025-01-15 08:30:00", tz_offset=0)
async def test_get_active_schedule_multiple_schedules(
    alert_service: AlertService,
    db_session: AsyncSession,
    test_route_with_schedule: Route,
) -> None:
    """Test that first matching schedule is returned when multiple match."""
    # Get the existing schedule from the fixture
    existing_schedule = test_route_with_schedule.schedules[0]

    # Add another schedule that also matches
    another_schedule = RouteSchedule(
        route_id=test_route_with_schedule.id,
        days_of_week=["MON", "TUE", "WED", "THU", "FRI"],
        start_time=time(8, 0),
        end_time=time(12, 0),
    )
    db_session.add(another_schedule)
    await db_session.commit()
    await db_session.refresh(another_schedule)

    # Pass both schedules explicitly to avoid lazy loading
    schedule = await alert_service._get_active_schedule(test_route_with_schedule, [existing_schedule, another_schedule])

    # Should return one of the matching schedules
    assert schedule is not None


# ==================== _get_route_disruptions Tests ====================


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
async def test_get_route_disruptions_returns_relevant(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that only disruptions for route's lines are returned."""
    # Mock TfL service
    mock_tfl_instance = AsyncMock()
    # Return disruptions for multiple lines
    all_disruptions = [
        *sample_disruptions,
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            status_severity=6,
            status_severity_description="Minor Delays",
            reason="Train cancellations",
            created_at=datetime.now(UTC),
        ),
    ]
    mock_tfl_instance.fetch_disruptions = AsyncMock(return_value=all_disruptions)
    mock_tfl_class.return_value = mock_tfl_instance

    disruptions, error_occurred = await alert_service._get_route_disruptions(test_route_with_schedule)

    # Should return no error
    assert not error_occurred
    # Should only return victoria line disruptions (route only has victoria)
    assert len(disruptions) == 1
    assert disruptions[0].line_id == "victoria"


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
async def test_get_route_disruptions_empty(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
) -> None:
    """Test getting disruptions when there are none."""
    # Mock TfL service with empty disruptions
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_disruptions = AsyncMock(return_value=[])
    mock_tfl_class.return_value = mock_tfl_instance

    disruptions, error_occurred = await alert_service._get_route_disruptions(test_route_with_schedule)

    assert not error_occurred
    assert len(disruptions) == 0


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
async def test_get_route_disruptions_filters_correctly(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    db_session: AsyncSession,
    test_route_with_schedule: Route,
) -> None:
    """Test that disruptions are filtered to route's lines only."""
    # Create a disruption for a line not in the route
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_disruptions = AsyncMock(
        return_value=[
            DisruptionResponse(
                line_id="central",  # Not in route
                line_name="Central",
                status_severity=5,
                status_severity_description="Severe Delays",
                reason="Signal failure",
                created_at=datetime.now(UTC),
            ),
        ]
    )
    mock_tfl_class.return_value = mock_tfl_instance

    disruptions, error_occurred = await alert_service._get_route_disruptions(test_route_with_schedule)

    # Should return no error
    assert not error_occurred
    # Should return empty since central line is not in route
    assert len(disruptions) == 0


# ==================== _should_send_alert Tests ====================


@pytest.mark.asyncio
async def test_should_send_alert_no_previous_alert(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert should be sent when no previous alert exists."""
    # Get the schedule
    schedule = test_route_with_schedule.schedules[0]

    # Redis returns None (no previous alert)
    should_send = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert should_send is True


@pytest.mark.asyncio
async def test_should_send_alert_same_disruption(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert should not be sent for same disruption content."""
    schedule = test_route_with_schedule.schedules[0]

    # Create hash of current disruptions
    current_hash = alert_service._create_disruption_hash(sample_disruptions)

    # Mock Redis to return stored state with same hash
    stored_state = json.dumps(
        {
            "hash": current_hash,
            "disruptions": [
                {
                    "line_id": d.line_id,
                    "status": d.status_severity_description,
                    "reason": d.reason or "",
                }
                for d in sample_disruptions
            ],
            "stored_at": datetime.now(UTC).isoformat(),
        }
    )
    alert_service.redis_client.get = AsyncMock(return_value=stored_state)  # type: ignore[method-assign]

    should_send = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert should_send is False


@pytest.mark.asyncio
async def test_should_send_alert_changed_disruption(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert should be sent when disruption content changes."""
    schedule = test_route_with_schedule.schedules[0]

    # Create different disruptions
    different_disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=6,
            status_severity_description="Minor Delays",  # Changed
            reason="Different reason",  # Changed
            created_at=datetime.now(UTC),
        ),
    ]
    different_hash = alert_service._create_disruption_hash(different_disruptions)

    # Mock Redis to return stored state with different hash
    stored_state = json.dumps(
        {
            "hash": different_hash,
            "disruptions": [],
            "stored_at": datetime.now(UTC).isoformat(),
        }
    )
    alert_service.redis_client.get = AsyncMock(return_value=stored_state)  # type: ignore[method-assign]

    should_send = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert should_send is True


@pytest.mark.asyncio
async def test_should_send_alert_redis_error(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert defaults to sending on Redis error."""
    schedule = test_route_with_schedule.schedules[0]

    # Mock Redis to raise error
    alert_service.redis_client.get = AsyncMock(side_effect=Exception("Redis error"))  # type: ignore[method-assign]

    should_send = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # Should default to sending (better to over-notify than under-notify)
    assert should_send is True


@pytest.mark.asyncio
async def test_should_send_alert_invalid_stored_data(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert is sent when stored data is invalid."""
    schedule = test_route_with_schedule.schedules[0]

    # Mock Redis to return invalid JSON
    alert_service.redis_client.get = AsyncMock(return_value="invalid json")  # type: ignore[method-assign]

    should_send = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert should_send is True


# ==================== _send_alerts_for_route Tests ====================


@pytest.mark.asyncio
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_for_route_success(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
    db_session: AsyncSession,
) -> None:
    """Test successful alert sending."""
    # Mock notification service
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock()
    mock_notif_class.return_value = mock_notif_instance

    schedule = test_route_with_schedule.schedules[0]

    alerts_sent = await alert_service._send_alerts_for_route(
        route=test_route_with_schedule,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert alerts_sent == 1

    # Verify notification was sent
    mock_notif_instance.send_disruption_email.assert_called_once()

    # Verify notification log was created
    result = await db_session.execute(
        select(NotificationLog).where(NotificationLog.route_id == test_route_with_schedule.id)
    )
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].status == NotificationStatus.SENT


@pytest.mark.asyncio
async def test_send_alerts_no_preferences(
    alert_service: AlertService,
    db_session: AsyncSession,
    test_user_with_contacts: User,
    test_line: Line,
    test_station: Station,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that no alerts are sent when route has no notification preferences."""
    # Create route without notification preferences
    route = Route(
        user_id=test_user_with_contacts.id,
        name="No Prefs Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.flush()

    segment = RouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    schedule = RouteSchedule(
        route_id=route.id,
        days_of_week=["MON", "TUE", "WED", "THU", "FRI"],
        start_time=time(8, 0),
        end_time=time(10, 0),
    )
    db_session.add(schedule)
    await db_session.commit()
    await db_session.refresh(route)

    alerts_sent = await alert_service._send_alerts_for_route(
        route=route,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert alerts_sent == 0


@pytest.mark.asyncio
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_unverified_contact(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    db_session: AsyncSession,
    test_user_with_contacts: User,
    test_line: Line,
    test_station: Station,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alerts are not sent to unverified contacts."""
    # Create unverified email
    unverified_email = EmailAddress(
        user_id=test_user_with_contacts.id,
        email="unverified@example.com",
        verified=False,  # Not verified
    )
    db_session.add(unverified_email)
    await db_session.flush()

    # Create route with preference to unverified email
    route = Route(
        user_id=test_user_with_contacts.id,
        name="Unverified Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.flush()

    segment = RouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    schedule = RouteSchedule(
        route_id=route.id,
        days_of_week=["MON", "TUE", "WED", "THU", "FRI"],
        start_time=time(8, 0),
        end_time=time(10, 0),
    )
    db_session.add(schedule)

    notification_pref = NotificationPreference(
        route_id=route.id,
        method=NotificationMethod.EMAIL,
        target_email_id=unverified_email.id,
    )
    db_session.add(notification_pref)
    await db_session.commit()
    await db_session.refresh(route)

    # Mock notification service (should not be called)
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock()
    mock_notif_class.return_value = mock_notif_instance

    alerts_sent = await alert_service._send_alerts_for_route(
        route=route,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # No alerts sent
    assert alerts_sent == 0

    # Notification service was not called
    mock_notif_instance.send_disruption_email.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_notification_failure(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
    db_session: AsyncSession,
) -> None:
    """Test that notification failures are logged but don't stop processing."""
    # Mock notification service to fail
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock(side_effect=Exception("SMTP error"))
    mock_notif_class.return_value = mock_notif_instance

    schedule = test_route_with_schedule.schedules[0]

    alerts_sent = await alert_service._send_alerts_for_route(
        route=test_route_with_schedule,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # No alerts sent successfully
    assert alerts_sent == 0

    # Verify failed notification log was created
    result = await db_session.execute(
        select(NotificationLog).where(NotificationLog.route_id == test_route_with_schedule.id)
    )
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].status == NotificationStatus.FAILED
    assert logs[0].error_message is not None
    assert "SMTP error" in logs[0].error_message


@pytest.mark.asyncio
@freeze_time("2025-01-13 09:00:00", tz_offset=0)  # 9:00 AM UTC on Monday (within 8-10 AM schedule)
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_stores_state_in_redis(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert state is stored in Redis after successful send."""
    # Mock notification service
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock()
    mock_notif_class.return_value = mock_notif_instance

    schedule = test_route_with_schedule.schedules[0]

    await alert_service._send_alerts_for_route(
        route=test_route_with_schedule,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # Verify Redis setex was called
    alert_service.redis_client.setex.assert_called_once()  # type: ignore[attr-defined]


# ==================== _store_alert_state Tests ====================


@pytest.mark.asyncio
@freeze_time("2025-01-15 08:30:00", tz_offset=0)  # 8:30 AM UTC
async def test_store_alert_state_correct_ttl(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert state is stored with correct TTL."""
    schedule = test_route_with_schedule.schedules[0]  # 8:00 - 10:00

    await alert_service._store_alert_state(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # Verify setex was called with correct TTL (1.5 hours = 5400 seconds)
    alert_service.redis_client.setex.assert_called_once()  # type: ignore[attr-defined]
    call_args = alert_service.redis_client.setex.call_args  # type: ignore[attr-defined]
    ttl = call_args[0][1]
    assert ttl == 5400  # 90 minutes until 10:00 AM


@pytest.mark.asyncio
@freeze_time("2025-01-15 10:30:00", tz_offset=0)  # 10:30 AM UTC (after schedule end)
async def test_store_alert_state_schedule_ended(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert state is not stored when schedule has already ended."""
    schedule = test_route_with_schedule.schedules[0]  # 8:00 - 10:00

    await alert_service._store_alert_state(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # Verify setex was not called (TTL would be 0 or negative)
    alert_service.redis_client.setex.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
@freeze_time("2025-01-15 08:30:00", tz_offset=0)
async def test_store_alert_state_stores_disruption_hash(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that stored state includes disruption hash."""
    schedule = test_route_with_schedule.schedules[0]

    await alert_service._store_alert_state(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # Get the stored data
    call_args = alert_service.redis_client.setex.call_args  # type: ignore[attr-defined]
    stored_json = call_args[0][2]
    stored_data = json.loads(stored_json)

    # Verify hash is present
    assert "hash" in stored_data
    assert len(stored_data["hash"]) == 64  # SHA256 hex digest


# ==================== _create_disruption_hash Tests ====================


def test_create_disruption_hash_stable(alert_service: AlertService) -> None:
    """Test that same disruptions create same hash."""
    disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions)
    hash2 = alert_service._create_disruption_hash(disruptions)

    assert hash1 == hash2


def test_create_disruption_hash_different_for_different_content(alert_service: AlertService) -> None:
    """Test that different disruptions create different hashes."""
    disruptions1 = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]

    disruptions2 = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=6,
            status_severity_description="Minor Delays",  # Different
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions1)
    hash2 = alert_service._create_disruption_hash(disruptions2)

    assert hash1 != hash2


def test_create_disruption_hash_empty_disruptions(alert_service: AlertService) -> None:
    """Test hash creation for empty disruptions."""
    hash_value = alert_service._create_disruption_hash([])

    assert isinstance(hash_value, str)
    assert len(hash_value) == 64  # SHA256 hex digest


def test_create_disruption_hash_order_independent(alert_service: AlertService) -> None:
    """Test that disruptions in different order produce same hash (sorted by line_id)."""
    disruptions1 = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            status_severity=6,
            status_severity_description="Minor Delays",
            reason="Train cancellations",
            created_at=datetime.now(UTC),
        ),
    ]

    disruptions2 = [
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            status_severity=6,
            status_severity_description="Minor Delays",
            reason="Train cancellations",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions1)
    hash2 = alert_service._create_disruption_hash(disruptions2)

    assert hash1 == hash2


# ==================== Additional Coverage Tests ====================


@pytest.mark.asyncio
async def test_get_redis_client() -> None:
    """Test get_redis_client creates a Redis client."""
    client = await get_redis_client()

    assert client is not None
    assert isinstance(client, redis.Redis)
    await client.aclose()


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
        ),
    ]

    with (
        patch.object(alert_service, "_should_send_alert", return_value=False),
        patch.object(alert_service, "_get_verified_contact", return_value=None),
    ):
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

    with (
        patch.object(alert_service, "_get_active_routes", return_value=[mock_route]),
        patch.object(alert_service, "_get_active_schedule", return_value=Mock()),
        patch.object(
            alert_service,
            "_get_route_disruptions",
            side_effect=RuntimeError("TfL API error"),
        ),
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


@pytest.mark.asyncio
async def test_get_active_schedule_exception_handling(
    alert_service: AlertService,
) -> None:
    """Test _get_active_schedule exception handling (lines 255-262)."""
    mock_route = Mock(spec=Route)
    mock_route.id = uuid4()
    mock_route.timezone = "Invalid/Timezone"  # Invalid timezone will cause error
    mock_route.schedules = [Mock()]

    # This should handle the exception and return None
    schedule = await alert_service._get_active_schedule(mock_route)
    assert schedule is None


@pytest.mark.asyncio
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_for_route_no_preferences(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
) -> None:
    """Test _send_alerts_for_route with no notification preferences (lines 594-599)."""
    mock_route = Mock(spec=Route)
    mock_route.id = uuid4()
    mock_route.name = "Test Route"
    mock_route.notification_preferences = []  # No preferences

    mock_schedule = Mock()
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

    alerts_sent = await alert_service._send_alerts_for_route(
        route=mock_route,
        schedule=mock_schedule,
        disruptions=disruptions,
    )

    # Should return 0 when no preferences
    assert alerts_sent == 0


@pytest.mark.asyncio
@freeze_time("2025-01-13 09:00:00", tz_offset=0)
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_for_route_sms_notification(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
    db_session: AsyncSession,
) -> None:
    """Test SMS notification path (lines 544-545)."""
    # Add SMS preference to route
    phone = PhoneNumber(
        user_id=test_route_with_schedule.user_id,
        phone="+447700900123",
        verified=True,
    )
    db_session.add(phone)
    await db_session.flush()

    sms_pref = NotificationPreference(
        route_id=test_route_with_schedule.id,
        method=NotificationMethod.SMS,
        target_phone_id=phone.id,
    )
    db_session.add(sms_pref)
    await db_session.commit()

    # Refresh route to load preferences
    await db_session.refresh(test_route_with_schedule, ["notification_preferences"])

    # Mock notification service
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_sms = AsyncMock()
    mock_notif_class.return_value = mock_notif_instance

    schedule = test_route_with_schedule.schedules[0]

    await alert_service._send_alerts_for_route(
        route=test_route_with_schedule,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # Verify SMS was sent
    mock_notif_instance.send_disruption_sms.assert_called_once()


@pytest.mark.asyncio
@freeze_time("2025-01-13 09:00:00", tz_offset=0)
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_for_route_preference_exception(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test unexpected exception in preference processing (lines 635-637)."""
    # Mock notification service to raise unexpected error
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock(side_effect=RuntimeError("Unexpected error"))
    mock_notif_class.return_value = mock_notif_instance

    schedule = test_route_with_schedule.schedules[0]

    # Should handle exception and continue
    alerts_sent = await alert_service._send_alerts_for_route(
        route=test_route_with_schedule,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # Should return 0 due to error
    assert alerts_sent == 0


@pytest.mark.asyncio
@freeze_time("2025-01-15 08:30:00", tz_offset=0)
async def test_store_alert_state_exception_handling(
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test _store_alert_state exception handling (lines 758-759)."""
    schedule = test_route_with_schedule.schedules[0]

    # Mock Redis to raise error on setex
    alert_service.redis_client.setex = AsyncMock(side_effect=RuntimeError("Redis error"))  # type: ignore[method-assign]

    # Should handle exception gracefully (logs error but doesn't crash)
    try:
        await alert_service._store_alert_state(
            route=test_route_with_schedule,
            user_id=test_route_with_schedule.user_id,
            schedule=schedule,
            disruptions=sample_disruptions,
        )
        # If we get here, exception was handled
    except RuntimeError:
        # Should not raise
        pytest.fail("Exception was not handled")
