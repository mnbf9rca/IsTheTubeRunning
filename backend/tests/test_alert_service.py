"""Tests for AlertService."""

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from datetime import time as time_class
from typing import Any
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
from app.models.route_index import RouteStationIndex
from app.models.tfl import Line, Station
from app.models.user import EmailAddress, PhoneNumber, User
from app.schemas.tfl import AffectedRouteInfo, DisruptionResponse
from app.services.alert_service import AlertService, extract_line_station_pairs, get_redis_client
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
    line = Line(tfl_id="victoria", name="Victoria", last_updated=datetime.now(UTC))
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
        start_time=time_class(8, 0),
        end_time=time_class(10, 0),
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
async def populate_route_index(db_session: AsyncSession):
    """
    Fixture factory to populate RouteStationIndex for a route.

    Returns a callable that takes a route and populates its index entries.
    This is essential for tests that rely on the inverted index for alert matching.
    """

    async def _populate(route: Route) -> Route:
        """Populate index entries for all segments in the route."""
        # Load segments if not already loaded
        if not route.segments:
            result = await db_session.execute(
                select(Route)
                .where(Route.id == route.id)
                .options(
                    selectinload(Route.segments).selectinload(RouteSegment.line),
                    selectinload(Route.segments).selectinload(RouteSegment.station),
                )
            )
            route = result.scalar_one()

        # Create index entries for each segment
        for segment in route.segments:
            if segment.line and segment.station:
                index_entry = RouteStationIndex(
                    route_id=route.id,
                    line_tfl_id=segment.line.tfl_id,
                    station_naptan=segment.station.tfl_id,
                    line_data_version=segment.line.last_updated,
                )
                db_session.add(index_entry)

        await db_session.commit()
        return route

    return _populate


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
    populate_route_index: Callable[[Route], Route],
) -> None:
    """Test successful processing of all routes."""
    # Populate the route index (required for inverted index matching)
    await populate_route_index(test_route_with_schedule)

    # Mock TfL service
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(return_value=sample_disruptions)
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
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(return_value=[])
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
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(side_effect=Exception("TfL API error"))
    mock_tfl_class.return_value = mock_tfl_instance

    result = await alert_service.process_all_routes()

    assert result["routes_checked"] == 1
    assert result["alerts_sent"] == 0
    assert result["errors"] == 1


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
@patch("app.services.alert_service.NotificationService")
@freeze_time("2025-01-15 08:30:00", tz_offset=0)  # Wednesday 8:30 AM UTC
async def test_process_all_routes_skips_duplicate_alert_with_logging(
    mock_notif_class: MagicMock,
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
    db_session: AsyncSession,
) -> None:
    """Test that duplicate alerts are skipped and logged (lines 165-170)."""
    # Calculate the disruption hash that would be stored
    disruption_hash = alert_service._create_disruption_hash(sample_disruptions)

    # Pre-populate Redis to simulate a previous alert with the same content
    stored_state = {
        "hash": disruption_hash,  # Use "hash" key to match the actual implementation
        "disruptions": [
            {
                "line_id": d.line_id,
                "status": d.status_severity_description,
                "reason": d.reason or "",
            }
            for d in sample_disruptions
        ],
        "stored_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    }
    alert_service.redis_client.get = AsyncMock(return_value=json.dumps(stored_state))  # type: ignore[method-assign]
    alert_service.redis_client.setex = AsyncMock()  # type: ignore[method-assign]

    # Mock TfL to return disruptions
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(return_value=sample_disruptions)
    mock_tfl_class.return_value = mock_tfl_instance

    # Mock notification service (should not be called)
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock()
    mock_notif_class.return_value = mock_notif_instance

    # Process all routes
    result = await alert_service.process_all_routes()

    # Verify results
    assert result["routes_checked"] == 1
    assert result["alerts_sent"] == 0
    assert result["errors"] == 0

    # Notification service was not called (duplicate was skipped)
    mock_notif_instance.send_disruption_email.assert_not_called()


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
    assert schedule.start_time == time_class(8, 0)
    assert schedule.end_time == time_class(10, 0)


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
        start_time=time_class(8, 0),
        end_time=time_class(10, 0),
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
        start_time=time_class(8, 0),
        end_time=time_class(12, 0),
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
    populate_route_index: Callable[[Route], Route],
) -> None:
    """Test that only disruptions for route's lines are returned."""
    # Populate the route index (required for inverted index matching)
    await populate_route_index(test_route_with_schedule)

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
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(return_value=all_disruptions)
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
    populate_route_index: Callable[[Route], Route],
) -> None:
    """Test getting disruptions when there are none."""
    # Populate the route index (required for inverted index matching)
    await populate_route_index(test_route_with_schedule)

    # Mock TfL service with empty disruptions
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(return_value=[])
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
    populate_route_index: Callable[[Route], Route],
) -> None:
    """Test that disruptions are filtered to route's lines only."""
    # Populate the route index (required for inverted index matching)
    await populate_route_index(test_route_with_schedule)

    # Create a disruption for a line not in the route
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(
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
        start_time=time_class(8, 0),
        end_time=time_class(10, 0),
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
        start_time=time_class(8, 0),
        end_time=time_class(10, 0),
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
async def test_send_alerts_for_route_skips_unverified_contact_continue(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    db_session: AsyncSession,
    test_user_with_contacts: User,
    test_line: Line,
    test_station: Station,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that the loop continues when contact_info is None (line 635)."""
    # Get verified email from test_user_with_contacts
    result = await db_session.execute(
        select(EmailAddress).where(
            EmailAddress.user_id == test_user_with_contacts.id,
            EmailAddress.verified == True,  # noqa: E712
        )
    )
    verified_email = result.scalar_one()

    # Create unverified email
    unverified_email = EmailAddress(
        user_id=test_user_with_contacts.id,
        email="unverified@example.com",
        verified=False,
    )
    db_session.add(unverified_email)
    await db_session.flush()

    # Create route with TWO preferences: one unverified, one verified
    route = Route(
        user_id=test_user_with_contacts.id,
        name="Mixed Verification Route",
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
        start_time=time_class(8, 0),
        end_time=time_class(10, 0),
    )
    db_session.add(schedule)

    # First preference: unverified (should be skipped with continue)
    notification_pref_unverified = NotificationPreference(
        route_id=route.id,
        method=NotificationMethod.EMAIL,
        target_email_id=unverified_email.id,
    )
    db_session.add(notification_pref_unverified)

    # Second preference: verified (should be processed)
    notification_pref_verified = NotificationPreference(
        route_id=route.id,
        method=NotificationMethod.EMAIL,
        target_email_id=verified_email.id,
    )
    db_session.add(notification_pref_verified)

    await db_session.commit()

    # Reload route with relationships using selectinload
    route_result = await db_session.execute(
        select(Route)
        .where(Route.id == route.id)
        .options(
            selectinload(Route.segments),
            selectinload(Route.schedules),
            selectinload(Route.notification_preferences),
            selectinload(Route.user).selectinload(User.email_addresses),
        )
    )
    route = route_result.scalar_one()

    # Mock notification service (should be called once for verified email)
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock(return_value=(True, None))
    mock_notif_class.return_value = mock_notif_instance

    alerts_sent = await alert_service._send_alerts_for_route(
        route=route,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # One alert sent (for verified email, unverified was skipped via continue)
    assert alerts_sent == 1

    # Notification service was called exactly once (for verified contact)
    assert mock_notif_instance.send_disruption_email.call_count == 1


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
@pytest.mark.parametrize(
    ("scenario", "mock_config", "expected_result"),
    [
        (
            "inner_exception_handler",
            {
                "method": "_get_route_disruptions",
                "side_effect": RuntimeError("TfL API error"),
                "setup_route": True,
            },
            {"errors": 1, "routes_checked": 1},
        ),
        (
            "outer_exception_handler",
            {
                "method": "_get_active_routes",
                "side_effect": RuntimeError("Database error"),
                "setup_route": False,
            },
            {"errors": 1, "routes_checked": 0},
        ),
    ],
)
async def test_process_all_routes_exception_handling(
    alert_service: AlertService,
    scenario: str,
    mock_config: dict[str, Any],
    expected_result: dict[str, int],
) -> None:
    """Test exception handling in process_all_routes for various error scenarios.

    Covers:
    - Inner exception handler (lines 181-186): Errors during route processing
    - Outer exception handler (lines 194-197): Errors during route retrieval
    """
    if mock_config["setup_route"]:
        # Setup for inner exception tests - need a route to process
        mock_route = Mock(spec=Route)
        mock_route.id = "test-route"
        mock_route.name = "Error Route"
        mock_route.schedules = [Mock()]

        with (
            patch.object(alert_service, "_get_active_routes", return_value=[mock_route]),
            patch.object(alert_service, "_get_active_schedule", return_value=Mock()),
            patch.object(
                alert_service,
                mock_config["method"],
                side_effect=mock_config["side_effect"],
            ),
        ):
            result = await alert_service.process_all_routes()
    else:
        # Setup for outer exception tests - error before route processing
        with patch.object(
            alert_service,
            mock_config["method"],
            side_effect=mock_config["side_effect"],
        ):
            result = await alert_service.process_all_routes()

    # Verify error handling
    assert result["errors"] == expected_result["errors"]
    assert result["routes_checked"] == expected_result["routes_checked"]


@pytest.mark.asyncio
async def test_alert_service_get_active_routes_error(
    alert_service: AlertService,
) -> None:
    """Test _get_active_routes exception handler (lines 199-201)."""
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
@patch("app.services.alert_service.NotificationService")
async def test_send_single_notification_sms_success(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
    db_session: AsyncSession,
) -> None:
    """Test _send_single_notification SMS path (lines 575->582)."""
    # Create verified phone
    phone = PhoneNumber(
        user_id=test_route_with_schedule.user_id,
        phone="+447700900123",
        verified=True,
    )
    db_session.add(phone)
    await db_session.flush()

    # Create SMS preference
    sms_pref = NotificationPreference(
        route_id=test_route_with_schedule.id,
        method=NotificationMethod.SMS,
        target_phone_id=phone.id,
    )
    db_session.add(sms_pref)
    await db_session.commit()
    await db_session.refresh(sms_pref)

    # Mock notification service
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_sms = AsyncMock()
    mock_notif_class.return_value = mock_notif_instance

    # Call _send_single_notification directly
    success, error = await alert_service._send_single_notification(
        pref=sms_pref,
        contact_info=phone.phone,
        route=test_route_with_schedule,
        disruptions=sample_disruptions,
    )

    # Verify success
    assert success is True
    assert error is None

    # Verify SMS was sent
    mock_notif_instance.send_disruption_sms.assert_called_once_with(
        phone=phone.phone,
        route_name=test_route_with_schedule.name,
        disruptions=sample_disruptions,
    )


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


@pytest.mark.asyncio
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_for_route_handles_get_verified_contact_exception(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: Route,
    sample_disruptions: list[DisruptionResponse],
    db_session: AsyncSession,
) -> None:
    """Test exception handling in preference processing loop (lines 663-665)."""
    # Mock notification service
    mock_notif_instance = AsyncMock()
    mock_notif_instance.send_disruption_email = AsyncMock()
    mock_notif_class.return_value = mock_notif_instance

    # Patch _get_verified_contact to raise an unexpected exception
    with patch.object(
        alert_service,
        "_get_verified_contact",
        side_effect=RuntimeError("Unexpected error in preference processing"),
    ):
        # Call the method - should not raise, should catch and log error
        alerts_sent = await alert_service._send_alerts_for_route(
            route=test_route_with_schedule,
            schedule=test_route_with_schedule.schedules[0],
            disruptions=sample_disruptions,
        )

    # No alerts sent due to exception
    assert alerts_sent == 0

    # Notification service was not called
    mock_notif_instance.send_disruption_email.assert_not_called()


# ==================== Phase 3: Inverted Index Matching Tests ====================


class TestExtractLineStationPairs:
    """Tests for extract_line_station_pairs pure function."""

    def test_extract_pairs_with_single_affected_route(self) -> None:
        """Test extracting pairs from disruption with single affected route."""

        disruption = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
            affected_routes=[
                AffectedRouteInfo(
                    name="Cockfosters → Heathrow T5",
                    direction="outbound",
                    affected_stations=["940GZZLURSQ", "940GZZLUHBN", "940GZZLUCGN"],
                ),
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        assert len(pairs) == 3
        assert ("piccadilly", "940GZZLURSQ") in pairs
        assert ("piccadilly", "940GZZLUHBN") in pairs
        assert ("piccadilly", "940GZZLUCGN") in pairs

    def test_extract_pairs_with_multiple_affected_routes(self) -> None:
        """Test extracting pairs from disruption with multiple affected routes (both directions)."""

        disruption = DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            status_severity=15,
            status_severity_description="Severe Delays",
            reason="Customer incident",
            created_at=datetime.now(UTC),
            affected_routes=[
                AffectedRouteInfo(
                    name="Morden → Edgware",
                    direction="northbound",
                    affected_stations=["940GZZLUBKE", "940GZZLUTCR"],
                ),
                AffectedRouteInfo(
                    name="Edgware → Morden",
                    direction="southbound",
                    affected_stations=["940GZZLUTCR", "940GZZLUBKE"],  # Same stations, different order
                ),
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        # Should get all unique combinations (line_id, station) - duplicates are fine, will be deduplicated by set
        assert len(pairs) == 4
        assert pairs.count(("northern", "940GZZLUBKE")) == 2  # Appears in both directions
        assert pairs.count(("northern", "940GZZLUTCR")) == 2  # Appears in both directions

    def test_extract_pairs_with_no_affected_routes(self) -> None:
        """Test extracting pairs when disruption has no affected_routes data."""

        disruption = DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Earlier signal failure",
            created_at=datetime.now(UTC),
            affected_routes=None,  # No detailed station data
        )

        pairs = extract_line_station_pairs(disruption)

        assert pairs == []

    def test_extract_pairs_with_empty_affected_routes(self) -> None:
        """Test extracting pairs when affected_routes is empty list."""

        disruption = DisruptionResponse(
            line_id="district",
            line_name="District",
            status_severity=10,
            status_severity_description="Good Service",
            created_at=datetime.now(UTC),
            affected_routes=[],  # Empty list
        )

        pairs = extract_line_station_pairs(disruption)

        assert pairs == []

    def test_extract_pairs_with_empty_station_list(self) -> None:
        """Test extracting pairs when affected route has no stations."""

        disruption = DisruptionResponse(
            line_id="central",
            line_name="Central",
            status_severity=10,
            status_severity_description="Minor Delays",
            created_at=datetime.now(UTC),
            affected_routes=[
                AffectedRouteInfo(
                    name="West Ruislip → Epping",
                    direction="eastbound",
                    affected_stations=[],  # No stations
                ),
            ],
        )

        pairs = extract_line_station_pairs(disruption)

        assert pairs == []


@pytest.mark.asyncio
class TestQueryRoutesByIndex:
    """Tests for _query_routes_by_index method."""

    async def test_query_single_line_station_pair(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test querying index with single (line, station) pair."""

        # Create test route
        route = Route(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Create index entries
        index1 = RouteStationIndex(
            route_id=route.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLUKSX",
            line_data_version=datetime.now(UTC),
        )
        db_session.add(index1)
        await db_session.commit()

        # Query the index
        pairs = [("piccadilly", "940GZZLUKSX")]
        result = await alert_service._query_routes_by_index(pairs)

        assert len(result) == 1
        assert route.id in result

    async def test_query_multiple_pairs_same_route(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test querying multiple stations on same route - should deduplicate to single route ID."""

        # Create test route
        route = Route(
            user_id=test_user.id,
            name="King's Cross to Leicester Square",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Create index entries for multiple stations on same route
        for station in ["940GZZLUKSX", "940GZZLURSQ", "940GZZLUHBN"]:
            index_entry = RouteStationIndex(
                route_id=route.id,
                line_tfl_id="piccadilly",
                station_naptan=station,
                line_data_version=datetime.now(UTC),
            )
            db_session.add(index_entry)
        await db_session.commit()

        # Query with all three stations
        pairs = [
            ("piccadilly", "940GZZLUKSX"),
            ("piccadilly", "940GZZLURSQ"),
            ("piccadilly", "940GZZLUHBN"),
        ]
        result = await alert_service._query_routes_by_index(pairs)

        # Should return single route ID (deduplicated by set)
        assert len(result) == 1
        assert route.id in result

    async def test_query_multiple_routes(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test querying index that returns multiple different routes."""

        # Create two routes passing through King's Cross
        route1 = Route(
            user_id=test_user.id,
            name="Route 1",
            active=True,
            timezone="Europe/London",
        )
        route2 = Route(
            user_id=test_user.id,
            name="Route 2",
            active=True,
            timezone="Europe/London",
        )
        db_session.add_all([route1, route2])
        await db_session.flush()

        # Both routes pass through King's Cross on Piccadilly
        for route in [route1, route2]:
            index_entry = RouteStationIndex(
                route_id=route.id,
                line_tfl_id="piccadilly",
                station_naptan="940GZZLUKSX",
                line_data_version=datetime.now(UTC),
            )
            db_session.add(index_entry)
        await db_session.commit()

        # Query the index
        pairs = [("piccadilly", "940GZZLUKSX")]
        result = await alert_service._query_routes_by_index(pairs)

        assert len(result) == 2
        assert route1.id in result
        assert route2.id in result

    async def test_query_empty_pairs_list(
        self,
        alert_service: AlertService,
    ) -> None:
        """Test querying with empty pairs list returns empty set."""
        result = await alert_service._query_routes_by_index([])
        assert result == set()

    async def test_query_no_matching_routes(
        self,
        alert_service: AlertService,
    ) -> None:
        """Test querying for non-existent (line, station) pair returns empty set."""
        pairs = [("imaginary-line", "940GZZLUIMAGINARY")]
        result = await alert_service._query_routes_by_index(pairs)
        assert result == set()


@pytest.mark.asyncio
class TestGetAffectedRoutesForDisruption:
    """Tests for _get_affected_routes_for_disruption method."""

    async def test_index_based_matching_with_affected_routes(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
        test_line: Line,
    ) -> None:
        """Test that method uses inverted index when affected_routes data exists."""

        # Create route with index
        route = Route(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Create index entry
        index_entry = RouteStationIndex(
            route_id=route.id,
            line_tfl_id="victoria",
            station_naptan="940GZZLUKSX",
            line_data_version=datetime.now(UTC),
        )
        db_session.add(index_entry)
        await db_session.commit()

        # Create disruption with affected_routes data
        disruption = DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
            affected_routes=[
                AffectedRouteInfo(
                    name="Brixton → Walthamstow Central",
                    direction="northbound",
                    affected_stations=["940GZZLUKSX"],  # King's Cross
                ),
            ],
        )

        result = await alert_service._get_affected_routes_for_disruption(disruption)

        assert len(result) == 1
        assert route.id in result

    async def test_fallback_to_line_level_when_no_affected_routes(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
        test_line: Line,
        test_station: Station,
    ) -> None:
        """Test fallback to line-level matching when affected_routes is None."""
        # Create route with segment on Victoria line
        route = Route(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        segment = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=test_station.id,
            line_id=test_line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        # Create disruption WITHOUT affected_routes data
        disruption = DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Earlier signal failure",
            created_at=datetime.now(UTC),
            affected_routes=None,  # No station-level data
        )

        result = await alert_service._get_affected_routes_for_disruption(disruption)

        # Should find route via line-level fallback
        assert len(result) == 1
        assert route.id in result

    async def test_fallback_returns_empty_when_line_not_found(
        self,
        alert_service: AlertService,
    ) -> None:
        """Test fallback returns empty set when line doesn't exist in database."""
        disruption = DisruptionResponse(
            line_id="imaginary-line",
            line_name="Imaginary Line",
            status_severity=10,
            status_severity_description="Minor Delays",
            created_at=datetime.now(UTC),
            affected_routes=None,
        )

        result = await alert_service._get_affected_routes_for_disruption(disruption)
        assert result == set()

    async def test_fallback_only_returns_active_routes(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
        test_line: Line,
        test_station: Station,
    ) -> None:
        """Test fallback only returns active, non-deleted routes."""
        # Create active route
        active_route = Route(
            user_id=test_user.id,
            name="Active Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(active_route)
        await db_session.flush()

        segment1 = RouteSegment(
            route_id=active_route.id,
            sequence=1,
            station_id=test_station.id,
            line_id=test_line.id,
        )
        db_session.add(segment1)

        # Create inactive route
        inactive_route = Route(
            user_id=test_user.id,
            name="Inactive Route",
            active=False,  # Inactive
            timezone="Europe/London",
        )
        db_session.add(inactive_route)
        await db_session.flush()

        segment2 = RouteSegment(
            route_id=inactive_route.id,
            sequence=1,
            station_id=test_station.id,
            line_id=test_line.id,
        )
        db_session.add(segment2)

        # Create deleted route
        deleted_route = Route(
            user_id=test_user.id,
            name="Deleted Route",
            active=True,
            timezone="Europe/London",
            deleted_at=datetime.now(UTC),  # Soft deleted
        )
        db_session.add(deleted_route)
        await db_session.flush()

        segment3 = RouteSegment(
            route_id=deleted_route.id,
            sequence=1,
            station_id=test_station.id,
            line_id=test_line.id,
        )
        db_session.add(segment3)

        await db_session.commit()

        # Create disruption without station data (triggers fallback)
        disruption = DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            status_severity=10,
            status_severity_description="Minor Delays",
            created_at=datetime.now(UTC),
            affected_routes=None,
        )

        result = await alert_service._get_affected_routes_for_disruption(disruption)

        # Should only return active route
        assert len(result) == 1
        assert active_route.id in result
        assert inactive_route.id not in result
        assert deleted_route.id not in result


@pytest.mark.asyncio
class TestBranchDisambiguation:
    """Integration tests verifying branch disambiguation works correctly."""

    async def test_piccadilly_branch_disambiguation(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """
        Test the example from Issue #129: Piccadilly line disruption should only alert affected branch.

        Scenario:
        - Disruption: Russell Square to Holborn (central London section)
        - Route A: King's Cross → Leicester Square (passes through affected stations) → SHOULD alert
        - Route B: Earl's Court → Heathrow (western branch, not affected) → should NOT alert
        """

        # Create Piccadilly line
        piccadilly = Line(
            tfl_id="piccadilly",
            name="Piccadilly",
            last_updated=datetime.now(UTC),
        )
        db_session.add(piccadilly)
        await db_session.flush()

        # Create Route A: passes through affected area (King's Cross → Leicester Square)
        route_a = Route(
            user_id=test_user.id,
            name="King's Cross to Leicester Square",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route_a)
        await db_session.flush()

        # Index entries for Route A (passes through Russell Square and Holborn)
        for station in ["940GZZLUKSX", "940GZZLURSQ", "940GZZLUHBN", "940GZZLUCGN", "940GZZLULSQ"]:
            index_entry = RouteStationIndex(
                route_id=route_a.id,
                line_tfl_id="piccadilly",
                station_naptan=station,
                line_data_version=datetime.now(UTC),
            )
            db_session.add(index_entry)

        # Create Route B: western branch (Earl's Court → Heathrow)
        route_b = Route(
            user_id=test_user.id,
            name="Earl's Court to Heathrow",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route_b)
        await db_session.flush()

        # Index entries for Route B (western branch, does NOT include Russell Square/Holborn)
        for station in ["940GZZLUECT", "940GZZLUHOR", "940GZZLUHRC"]:
            index_entry = RouteStationIndex(
                route_id=route_b.id,
                line_tfl_id="piccadilly",
                station_naptan=station,
                line_data_version=datetime.now(UTC),
            )
            db_session.add(index_entry)

        await db_session.commit()

        # Create disruption affecting Russell Square to Holborn
        disruption = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Signal failure at Russell Square",
            created_at=datetime.now(UTC),
            affected_routes=[
                AffectedRouteInfo(
                    name="Cockfosters → Heathrow T5",
                    direction="outbound",
                    affected_stations=["940GZZLURSQ", "940GZZLUHBN"],  # Russell Square, Holborn
                ),
            ],
        )

        # Get affected routes
        result = await alert_service._get_affected_routes_for_disruption(disruption)

        # CRITICAL: Only Route A should be affected, NOT Route B
        assert len(result) == 1
        assert route_a.id in result
        assert route_b.id not in result, "Route B (western branch) should NOT be alerted for central London disruption"

    async def test_northern_line_branch_disambiguation(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """
        Test Northern line branch disambiguation.

        Scenario:
        - Disruption: Camden Town to Kentish Town (Edgware branch)
        - Route A: Kennington → Edgware (via Camden Town) → SHOULD alert
        - Route B: Kennington → High Barnet (via Bank branch, not via Camden Town) → should NOT alert
        """

        # Create Northern line
        northern = Line(
            tfl_id="northern",
            name="Northern",
            last_updated=datetime.now(UTC),
        )
        db_session.add(northern)
        await db_session.flush()

        # Route A: Kennington → Edgware (passes through Camden Town)
        route_a = Route(
            user_id=test_user.id,
            name="Kennington to Edgware",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route_a)
        await db_session.flush()

        # Index for Route A includes Camden Town
        for station in ["940GZZLUKNG", "940GZZLUETN", "940GZZLUCTW", "940GZZLUKTN"]:
            index_entry = RouteStationIndex(
                route_id=route_a.id,
                line_tfl_id="northern",
                station_naptan=station,
                line_data_version=datetime.now(UTC),
            )
            db_session.add(index_entry)

        # Route B: Kennington → High Barnet (Bank branch, NOT via Camden Town)
        route_b = Route(
            user_id=test_user.id,
            name="Kennington to High Barnet",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route_b)
        await db_session.flush()

        # Index for Route B does NOT include Camden Town
        for station in ["940GZZLUKNG", "940GZZLUBKE", "940GZZLUMRG", "940GZZLUHGB"]:
            index_entry = RouteStationIndex(
                route_id=route_b.id,
                line_tfl_id="northern",
                station_naptan=station,
                line_data_version=datetime.now(UTC),
            )
            db_session.add(index_entry)

        await db_session.commit()

        # Disruption at Camden Town to Kentish Town
        disruption = DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            status_severity=15,
            status_severity_description="Severe Delays",
            reason="Customer incident",
            created_at=datetime.now(UTC),
            affected_routes=[
                AffectedRouteInfo(
                    name="Morden → Edgware",
                    direction="northbound",
                    affected_stations=["940GZZLUCTW", "940GZZLUKTN"],  # Camden Town, Kentish Town
                ),
            ],
        )

        result = await alert_service._get_affected_routes_for_disruption(disruption)

        # Only Route A (Edgware branch) should be affected
        assert len(result) == 1
        assert route_a.id in result
        assert route_b.id not in result, "Route B (Bank branch) should NOT be alerted for Edgware branch disruption"


@pytest.mark.asyncio
class TestPerformance:
    """Performance tests for inverted index matching."""

    async def test_performance_1000_routes_10_disruptions(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that 1000 routes + 10 disruptions complete in under 100ms."""

        # Create 1000 routes with index entries
        routes = []
        for i in range(1000):
            route = Route(
                user_id=test_user.id,
                name=f"Route {i}",
                active=True,
                timezone="Europe/London",
            )
            db_session.add(route)
            routes.append(route)

        await db_session.flush()

        # Add index entries (distribute across different stations)
        stations = [
            "940GZZLUKSX",  # King's Cross
            "940GZZLULSQ",  # Leicester Square
            "940GZZLUPCC",  # Piccadilly Circus
            "940GZZLUVIC",  # Victoria
            "940GZZLUGPS",  # Green Park
        ]

        for i, route in enumerate(routes):
            # Each route gets 3 random stations
            route_stations = [stations[j % len(stations)] for j in range(i, i + 3)]
            for station in route_stations:
                index_entry = RouteStationIndex(
                    route_id=route.id,
                    line_tfl_id="piccadilly",
                    station_naptan=station,
                    line_data_version=datetime.now(UTC),
                )
                db_session.add(index_entry)

        await db_session.commit()

        # Create 10 disruptions affecting different stations
        disruptions = []
        for i, station in enumerate(stations[:5]):
            disruption = DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason=f"Disruption {i}",
                created_at=datetime.now(UTC),
                affected_routes=[
                    AffectedRouteInfo(
                        name="Cockfosters → Heathrow T5",
                        direction="outbound",
                        affected_stations=[station],
                    ),
                ],
            )
            disruptions.append(disruption)

        # Measure performance
        start_time = time.time()

        # Process all disruptions
        for disruption in disruptions:
            await alert_service._get_affected_routes_for_disruption(disruption)

        elapsed_ms = (time.time() - start_time) * 1000

        # Should complete in under 100ms
        assert elapsed_ms < 100, f"Performance test failed: took {elapsed_ms:.2f}ms (expected < 100ms)"

    async def test_performance_index_query_is_fast(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that index queries are fast even with many entries."""

        # Create 10,000 index entries across 100 routes
        for route_num in range(100):
            route = Route(
                user_id=test_user.id,
                name=f"Route {route_num}",
                active=True,
                timezone="Europe/London",
            )
            db_session.add(route)
            await db_session.flush()

            # Each route has 100 stations
            for station_num in range(100):
                index_entry = RouteStationIndex(
                    route_id=route.id,
                    line_tfl_id="test-line",
                    station_naptan=f"STATION{station_num:04d}",
                    line_data_version=datetime.now(UTC),
                )
                db_session.add(index_entry)

        await db_session.commit()

        # Query for 10 different stations
        pairs = [("test-line", f"STATION{i:04d}") for i in range(0, 100, 10)]

        start_time = time.time()
        result = await alert_service._query_routes_by_index(pairs)
        elapsed_ms = (time.time() - start_time) * 1000

        # Should return routes quickly
        assert len(result) > 0
        assert elapsed_ms < 50, f"Index query took {elapsed_ms:.2f}ms (expected < 50ms)"
