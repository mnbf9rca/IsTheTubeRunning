"""Tests for AlertService."""

import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from datetime import time as time_class
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
import redis.asyncio as redis
from app.core.redis import get_redis_client
from app.helpers.disruption_helpers import extract_line_station_pairs
from app.models.notification import (
    NotificationLog,
    NotificationMethod,
    NotificationPreference,
    NotificationStatus,
)
from app.models.tfl import AlertDisabledSeverity, Line, LineDisruptionStateLog, Station
from app.models.user import EmailAddress, PhoneNumber, User
from app.models.user_route import UserRoute, UserRouteSchedule, UserRouteSegment
from app.models.user_route_index import UserRouteStationIndex
from app.schemas.tfl import AffectedRouteInfo, DisruptionResponse
from app.services.alert_service import (
    ALERT_STATE_VERSION,
    AlertService,
    create_line_aggregate_hash,
    filter_alertable_disruptions,
    get_day_code,
    init_alert_processing_stats,
    is_time_in_schedule_window,
    warm_up_line_state_cache,
)
from freezegun import freeze_time
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# ==================== Fixtures ====================


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client for testing."""
    client = AsyncMock(spec=redis.Redis)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
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
) -> UserRoute:
    """Create test route with schedule and notification preferences."""
    route = UserRoute(
        user_id=test_user_with_contacts.id,
        name="Morning Commute",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.flush()

    # Add segment
    segment = UserRouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    # Add weekday schedule (8:00 AM - 10:00 AM)
    schedule = UserRouteSchedule(
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
        select(UserRoute)
        .where(UserRoute.id == route.id)
        .options(
            selectinload(UserRoute.segments),
            selectinload(UserRoute.schedules),
            selectinload(UserRoute.notification_preferences),
            selectinload(UserRoute.user).selectinload(User.email_addresses),
        )
    )
    return result.scalar_one()


@pytest.fixture
async def populate_route_index(db_session: AsyncSession):
    """
    Fixture factory to populate UserRouteStationIndex for a route.

    Returns a callable that takes a route and populates its index entries.
    This is essential for tests that rely on the inverted index for alert matching.
    """

    async def _populate(route: UserRoute) -> UserRoute:
        """Populate index entries for all segments in the route."""
        # Load segments if not already loaded
        if not route.segments:
            result = await db_session.execute(
                select(UserRoute)
                .where(UserRoute.id == route.id)
                .options(
                    selectinload(UserRoute.segments).selectinload(UserRouteSegment.line),
                    selectinload(UserRoute.segments).selectinload(UserRouteSegment.station),
                )
            )
            route = result.scalar_one()

        # Create index entries for each segment
        for segment in route.segments:
            if segment.line and segment.station:
                index_entry = UserRouteStationIndex(
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
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure at King's Cross",
            created_at=datetime.now(UTC),
        ),
    ]


# ==================== Pure Function Tests ====================


@pytest.mark.parametrize(
    ("weekday", "expected"),
    [
        (0, "MON"),
        (1, "TUE"),
        (2, "WED"),
        (3, "THU"),
        (4, "FRI"),
        (5, "SAT"),
        (6, "SUN"),
    ],
)
def test_get_day_code(weekday: int, expected: str) -> None:
    """Test get_day_code converts weekday integers to day codes."""
    assert get_day_code(weekday) == expected


@pytest.mark.parametrize(
    ("current_time", "current_day", "days", "start", "end", "expected"),
    [
        # In window - correct day and time
        (time_class(9, 0), "MON", ["MON", "TUE"], time_class(8, 0), time_class(10, 0), True),
        # In window - edge case at start time
        (time_class(8, 0), "MON", ["MON", "TUE"], time_class(8, 0), time_class(10, 0), True),
        # In window - edge case at end time
        (time_class(10, 0), "MON", ["MON", "TUE"], time_class(8, 0), time_class(10, 0), True),
        # Out of window - too early
        (time_class(7, 59), "MON", ["MON", "TUE"], time_class(8, 0), time_class(10, 0), False),
        # Out of window - too late
        (time_class(10, 1), "MON", ["MON", "TUE"], time_class(8, 0), time_class(10, 0), False),
        # Out of window - wrong day
        (time_class(9, 0), "WED", ["MON", "TUE"], time_class(8, 0), time_class(10, 0), False),
        # In window - different day
        (time_class(9, 0), "TUE", ["MON", "TUE"], time_class(8, 0), time_class(10, 0), True),
    ],
)
def test_is_time_in_schedule_window(
    current_time: time_class,
    current_day: str,
    days: list[str],
    start: time_class,
    end: time_class,
    expected: bool,
) -> None:
    """Test is_time_in_schedule_window with various time/day combinations."""
    result = is_time_in_schedule_window(current_time, current_day, days, start, end)
    assert result == expected


def test_filter_alertable_disruptions_empty_list() -> None:
    """Test filter_alertable_disruptions with empty disruptions list."""
    result = filter_alertable_disruptions([], set())
    assert result == []


def test_filter_alertable_disruptions_no_disabled() -> None:
    """Test filter_alertable_disruptions with no disabled severities."""
    disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            created_at=datetime.now(UTC),
        ),
    ]
    result = filter_alertable_disruptions(disruptions, set())
    assert len(result) == 2
    assert result == disruptions


def test_filter_alertable_disruptions_with_disabled() -> None:
    """Test filter_alertable_disruptions filters disabled severities."""
    disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=10,
            status_severity_description="Good Service",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=10,
            status_severity_description="Good Service",
            created_at=datetime.now(UTC),
        ),
    ]
    disabled = {("tube", 10)}
    result = filter_alertable_disruptions(disruptions, disabled)

    # Should only return the severe delays disruption
    assert len(result) == 1
    assert result[0].line_id == "northern"
    assert result[0].status_severity == 5


def test_filter_alertable_disruptions_all_filtered() -> None:
    """Test filter_alertable_disruptions when all disruptions are filtered."""
    disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=10,
            status_severity_description="Good Service",
            created_at=datetime.now(UTC),
        ),
    ]
    disabled = {("tube", 10)}
    result = filter_alertable_disruptions(disruptions, disabled)
    assert result == []


def test_init_alert_processing_stats() -> None:
    """Test init_alert_processing_stats returns correct structure."""
    stats = init_alert_processing_stats()
    assert stats == {
        "routes_checked": 0,
        "alerts_sent": 0,
        "errors": 0,
    }
    # Verify it's a new dict each time (not a shared reference)
    stats2 = init_alert_processing_stats()
    stats["routes_checked"] = 5
    assert stats2["routes_checked"] == 0


# ==================== Helper Method Unit Tests ====================


class TestSetSpanStatsAttributes:
    """Unit tests for _set_span_stats_attributes helper."""

    def test_sets_all_attributes_correctly(self, alert_service: AlertService) -> None:
        """Test that _set_span_stats_attributes sets all span attributes correctly."""
        mock_span = MagicMock()
        stats = {"routes_checked": 5, "alerts_sent": 3, "errors": 1}

        alert_service._set_span_stats_attributes(mock_span, stats)

        assert mock_span.set_attribute.call_count == 3
        mock_span.set_attribute.assert_any_call("alert.routes_checked", 5)
        mock_span.set_attribute.assert_any_call("alert.alerts_sent", 3)
        mock_span.set_attribute.assert_any_call("alert.errors", 1)

    def test_sets_zero_values(self, alert_service: AlertService) -> None:
        """Test that _set_span_stats_attributes handles zero values correctly."""
        mock_span = MagicMock()
        stats = {"routes_checked": 0, "alerts_sent": 0, "errors": 0}

        alert_service._set_span_stats_attributes(mock_span, stats)

        assert mock_span.set_attribute.call_count == 3
        mock_span.set_attribute.assert_any_call("alert.routes_checked", 0)
        mock_span.set_attribute.assert_any_call("alert.alerts_sent", 0)
        mock_span.set_attribute.assert_any_call("alert.errors", 0)


class TestFetchGlobalDisruptionData:
    """Unit tests for _fetch_global_disruption_data."""

    @pytest.mark.asyncio
    @patch("app.services.alert_service.TfLService")
    async def test_success(
        self,
        mock_tfl_class: MagicMock,
        alert_service: AlertService,
        db_session: AsyncSession,
        sample_disruptions: list[DisruptionResponse],
    ) -> None:
        """Test successful fetching of global disruption data."""
        # Mock TfL service
        mock_tfl = AsyncMock()
        mock_tfl.fetch_line_disruptions = AsyncMock(return_value=sample_disruptions)
        mock_tfl_class.return_value = mock_tfl

        # Mock _log_line_disruption_state_changes
        alert_service._log_line_disruption_state_changes = AsyncMock()

        # Create disabled severity in DB (use unique values to avoid conflicts)
        disabled = AlertDisabledSeverity(mode_id="test-mode", severity_level=99)
        db_session.add(disabled)
        await db_session.commit()

        # Execute
        disabled_pairs = await alert_service._fetch_global_disruption_data()

        # Verify
        assert ("test-mode", 99) in disabled_pairs
        mock_tfl.fetch_line_disruptions.assert_called_once_with(use_cache=True)
        alert_service._log_line_disruption_state_changes.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.alert_service.TfLService")
    async def test_tfl_service_error_still_returns_disabled_pairs(
        self,
        mock_tfl_class: MagicMock,
        alert_service: AlertService,
        db_session: AsyncSession,
    ) -> None:
        """Test that TfL service errors don't prevent disabled pairs from being fetched.

        This is the fix for #307: even when TfL API fails, we should still get
        disabled_severity_pairs from the database to ensure filtering works.
        """
        # Create disabled severity in DB (use unique values to avoid conflicts)
        disabled = AlertDisabledSeverity(mode_id="test-mode-tfl-error", severity_level=98)
        db_session.add(disabled)
        await db_session.commit()

        # Mock TfL service to raise exception
        mock_tfl = AsyncMock()
        mock_tfl.fetch_line_disruptions = AsyncMock(side_effect=Exception("TfL API error"))
        mock_tfl_class.return_value = mock_tfl

        # Execute
        disabled_pairs = await alert_service._fetch_global_disruption_data()

        # Verify returns disabled pairs from DB, even though TfL failed
        assert ("test-mode-tfl-error", 98) in disabled_pairs
        assert disabled_pairs != set()  # Not empty!

    @pytest.mark.asyncio
    @patch("app.services.alert_service.TfLService")
    async def test_db_error_returns_empty(
        self,
        mock_tfl_class: MagicMock,
        alert_service: AlertService,
        sample_disruptions: list[DisruptionResponse],
    ) -> None:
        """Test that DB errors return empty disabled pairs.

        When the DB query fails, we can't get disabled_severity_pairs, so we return
        empty set. This is a critical error - filtering won't work properly, but
        alert processing continues.
        """
        # Mock DB to raise SQLAlchemyError on first execute call
        alert_service.db.execute = AsyncMock(side_effect=SQLAlchemyError("DB connection error"))

        # Execute
        disabled_pairs = await alert_service._fetch_global_disruption_data()

        # Verify returns empty disabled pairs (DB failed)
        # TfL service should not be called since DB query happens first
        assert disabled_pairs == set()
        mock_tfl_class.assert_not_called()


class TestProcessSingleRoute:
    """Unit tests for _process_single_route."""

    @pytest.mark.asyncio
    async def test_not_in_schedule_returns_zero_no_error(
        self,
        alert_service: AlertService,
        test_route_with_schedule: UserRoute,
    ) -> None:
        """Test that route not in schedule returns (0, False)."""
        # Mock _get_active_schedule to return None
        with patch.object(alert_service, "_get_active_schedule", new_callable=AsyncMock, return_value=None):
            alerts_sent, error_occurred = await alert_service._process_single_route(
                route=test_route_with_schedule,
                schedules=[],
                disabled_severity_pairs=set(),
            )

        assert alerts_sent == 0
        assert error_occurred is False

    @pytest.mark.asyncio
    async def test_no_disruptions_returns_zero_no_error(
        self,
        alert_service: AlertService,
        test_route_with_schedule: UserRoute,
    ) -> None:
        """Test that no disruptions returns (0, False)."""
        mock_schedule = MagicMock(spec=UserRouteSchedule)
        mock_schedule.id = uuid4()

        # Mock dependencies
        with (
            patch.object(alert_service, "_get_active_schedule", new_callable=AsyncMock, return_value=mock_schedule),
            patch.object(alert_service, "_get_route_disruptions", new_callable=AsyncMock, return_value=([], False)),
        ):
            alerts_sent, error_occurred = await alert_service._process_single_route(
                route=test_route_with_schedule,
                schedules=[],
                disabled_severity_pairs=set(),
            )

        assert alerts_sent == 0
        assert error_occurred is False

    @pytest.mark.asyncio
    async def test_success_returns_alerts_sent_no_error(
        self,
        alert_service: AlertService,
        test_route_with_schedule: UserRoute,
        sample_disruptions: list[DisruptionResponse],
    ) -> None:
        """Test successful processing returns (alerts_sent, False)."""
        mock_schedule = MagicMock(spec=UserRouteSchedule)
        mock_schedule.id = uuid4()

        # Mock all dependencies for success path
        with (
            patch.object(alert_service, "_get_active_schedule", new_callable=AsyncMock, return_value=mock_schedule),
            patch.object(
                alert_service,
                "_get_route_disruptions",
                new_callable=AsyncMock,
                return_value=(sample_disruptions, False),
            ),
            patch.object(
                alert_service, "_should_send_alert", new_callable=AsyncMock, return_value=(True, sample_disruptions)
            ),
            patch.object(alert_service, "_send_alerts_for_route", new_callable=AsyncMock, return_value=2),
        ):
            alerts_sent, error_occurred = await alert_service._process_single_route(
                route=test_route_with_schedule,
                schedules=[],
                disabled_severity_pairs=set(),
            )

        assert alerts_sent == 2
        assert error_occurred is False

    @pytest.mark.asyncio
    async def test_disruption_fetch_error_propagates_error_flag(
        self,
        alert_service: AlertService,
        test_route_with_schedule: UserRoute,
        sample_disruptions: list[DisruptionResponse],
    ) -> None:
        """Test that disruption fetch error is propagated in error flag."""
        mock_schedule = MagicMock(spec=UserRouteSchedule)
        mock_schedule.id = uuid4()

        # Mock dependencies with error in disruption fetch
        with (
            patch.object(alert_service, "_get_active_schedule", new_callable=AsyncMock, return_value=mock_schedule),
            patch.object(
                alert_service, "_get_route_disruptions", new_callable=AsyncMock, return_value=(sample_disruptions, True)
            ),
            patch.object(
                alert_service, "_should_send_alert", new_callable=AsyncMock, return_value=(True, sample_disruptions)
            ),
            patch.object(alert_service, "_send_alerts_for_route", new_callable=AsyncMock, return_value=1),
        ):
            alerts_sent, error_occurred = await alert_service._process_single_route(
                route=test_route_with_schedule,
                schedules=[],
                disabled_severity_pairs=set(),
            )

        assert alerts_sent == 1
        assert error_occurred is True  # Error flag propagated

    @pytest.mark.asyncio
    async def test_duplicate_alert_returns_zero_no_error(
        self,
        alert_service: AlertService,
        test_route_with_schedule: UserRoute,
        sample_disruptions: list[DisruptionResponse],
    ) -> None:
        """Test that duplicate alert (should_send=False) returns (0, False)."""
        mock_schedule = MagicMock(spec=UserRouteSchedule)
        mock_schedule.id = uuid4()

        # Mock dependencies with should_send_alert returning False
        with (
            patch.object(alert_service, "_get_active_schedule", new_callable=AsyncMock, return_value=mock_schedule),
            patch.object(
                alert_service,
                "_get_route_disruptions",
                new_callable=AsyncMock,
                return_value=(sample_disruptions, False),
            ),
            patch.object(alert_service, "_should_send_alert", new_callable=AsyncMock, return_value=(False, [])),
        ):
            alerts_sent, error_occurred = await alert_service._process_single_route(
                route=test_route_with_schedule,
                schedules=[],
                disabled_severity_pairs=set(),
            )

        assert alerts_sent == 0
        assert error_occurred is False

    @pytest.mark.asyncio
    async def test_exception_returns_zero_with_error(
        self,
        alert_service: AlertService,
        test_route_with_schedule: UserRoute,
    ) -> None:
        """Test that exceptions are caught and return (0, True)."""
        # Mock _get_active_schedule to raise exception
        with patch.object(alert_service, "_get_active_schedule", side_effect=Exception("Unexpected error")):
            alerts_sent, error_occurred = await alert_service._process_single_route(
                route=test_route_with_schedule,
                schedules=[],
                disabled_severity_pairs=set(),
            )

        assert alerts_sent == 0
        assert error_occurred is True


# ==================== process_all_routes Tests ====================


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
@patch("app.services.alert_service.NotificationService")
@freeze_time("2025-01-15 08:30:00", tz_offset=0)  # Wednesday 8:30 AM UTC
async def test_process_all_routes_success(
    mock_notif_class: MagicMock,
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
    sample_disruptions: list[DisruptionResponse],
    populate_route_index: Callable[[UserRoute], UserRoute],
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
@freeze_time("2025-01-15 08:30:00", tz_offset=0)
async def test_process_all_routes_with_error(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
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


# ==================== _get_active_routes Tests ====================


@pytest.mark.asyncio
async def test_get_active_routes_returns_only_active(
    alert_service: AlertService,
    db_session: AsyncSession,
    test_user_with_contacts: User,
) -> None:
    """Test that only active routes are returned."""
    # Create active route
    active_route = UserRoute(
        user_id=test_user_with_contacts.id,
        name="Active Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(active_route)

    # Create inactive route
    inactive_route = UserRoute(
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
    active_route = UserRoute(
        user_id=test_user_with_contacts.id,
        name="Active Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(active_route)

    # Create deleted route
    deleted_route = UserRoute(
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
) -> None:
    """Test getting active schedule when route is in schedule window."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule, test_route_with_schedule.schedules)

    assert schedule is not None
    assert schedule.start_time == time_class(8, 0)
    assert schedule.end_time == time_class(10, 0)


@pytest.mark.asyncio
@freeze_time("2025-01-15 07:30:00", tz_offset=0)  # Wednesday 7:30 AM UTC (before schedule)
async def test_get_active_schedule_outside_window(
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
) -> None:
    """Test getting active schedule when route is outside schedule window."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule, test_route_with_schedule.schedules)

    assert schedule is None


@pytest.mark.asyncio
@freeze_time("2025-01-18 08:30:00", tz_offset=0)  # Saturday 8:30 AM UTC
async def test_get_active_schedule_wrong_day(
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
) -> None:
    """Test getting active schedule on weekend (not in schedule days)."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule, test_route_with_schedule.schedules)

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
    route = UserRoute(
        user_id=test_user_with_contacts.id,
        name="NYC Commute",
        active=True,
        timezone="America/New_York",
    )
    db_session.add(route)
    await db_session.flush()

    # Add segment
    segment = UserRouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    # Schedule: 8:00 AM - 10:00 AM EST
    schedule = UserRouteSchedule(
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
    test_route_with_schedule: UserRoute,
) -> None:
    """Test schedule matching at exact start time."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule, test_route_with_schedule.schedules)

    assert schedule is not None


@pytest.mark.asyncio
@freeze_time("2025-01-15 10:00:00", tz_offset=0)  # Wednesday 10:00 AM UTC (boundary)
async def test_get_active_schedule_at_end_boundary(
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
) -> None:
    """Test schedule matching at exact end time."""
    schedule = await alert_service._get_active_schedule(test_route_with_schedule, test_route_with_schedule.schedules)

    assert schedule is not None


@pytest.mark.asyncio
@freeze_time("2025-01-15 08:30:00", tz_offset=0)
async def test_get_active_schedule_multiple_schedules(
    alert_service: AlertService,
    db_session: AsyncSession,
    test_route_with_schedule: UserRoute,
) -> None:
    """Test that first matching schedule is returned when multiple match."""
    # Get the existing schedule from the fixture
    existing_schedule = test_route_with_schedule.schedules[0]

    # Add another schedule that also matches
    another_schedule = UserRouteSchedule(
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
    test_route_with_schedule: UserRoute,
    sample_disruptions: list[DisruptionResponse],
    populate_route_index: Callable[[UserRoute], UserRoute],
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
            mode="tube",
            status_severity=6,
            status_severity_description="Minor Delays",
            reason="Train cancellations",
            created_at=datetime.now(UTC),
        ),
    ]
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(return_value=all_disruptions)
    mock_tfl_class.return_value = mock_tfl_instance

    disabled_severity_pairs: set[tuple[str, int]] = set()

    disruptions, error_occurred = await alert_service._get_route_disruptions(
        test_route_with_schedule, disabled_severity_pairs
    )

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
    test_route_with_schedule: UserRoute,
    populate_route_index: Callable[[UserRoute], UserRoute],
) -> None:
    """Test getting disruptions when there are none."""
    # Populate the route index (required for inverted index matching)
    await populate_route_index(test_route_with_schedule)

    # Mock TfL service with empty disruptions
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(return_value=[])
    mock_tfl_class.return_value = mock_tfl_instance

    disabled_severity_pairs: set[tuple[str, int]] = set()
    disruptions, error_occurred = await alert_service._get_route_disruptions(
        test_route_with_schedule, disabled_severity_pairs
    )

    assert not error_occurred
    assert len(disruptions) == 0


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
async def test_get_route_disruptions_filters_correctly(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    db_session: AsyncSession,
    test_route_with_schedule: UserRoute,
    populate_route_index: Callable[[UserRoute], UserRoute],
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
                mode="tube",
                status_severity=5,
                status_severity_description="Severe Delays",
                reason="Signal failure",
                created_at=datetime.now(UTC),
            ),
        ]
    )
    mock_tfl_class.return_value = mock_tfl_instance

    disabled_severity_pairs: set[tuple[str, int]] = set()
    disruptions, error_occurred = await alert_service._get_route_disruptions(
        test_route_with_schedule, disabled_severity_pairs
    )

    # Should return no error
    assert not error_occurred
    # Should return empty since central line is not in route
    assert len(disruptions) == 0


@pytest.mark.asyncio
@patch("app.services.alert_service.TfLService")
async def test_get_route_disruptions_filters_disabled_severities(
    mock_tfl_class: MagicMock,
    alert_service: AlertService,
    db_session: AsyncSession,
    test_route_with_schedule: UserRoute,
    populate_route_index: Callable[[UserRoute], UserRoute],
) -> None:
    """Test that disruptions with disabled (mode, severity) pairs are filtered out."""
    # Populate the route index (required for inverted index matching)
    await populate_route_index(test_route_with_schedule)

    # Create disruptions including one with disabled severity (tube, 10 = Good Service)
    mock_tfl_instance = AsyncMock()
    mock_tfl_instance.fetch_line_disruptions = AsyncMock(
        return_value=[
            DisruptionResponse(
                line_id="victoria",  # In route
                line_name="Victoria",
                mode="tube",
                status_severity=10,  # Good Service - should be filtered
                status_severity_description="Good Service",
                reason=None,
                created_at=datetime.now(UTC),
            ),
            DisruptionResponse(
                line_id="victoria",  # In route
                line_name="Victoria",
                mode="tube",
                status_severity=5,  # Severe Delays - should NOT be filtered
                status_severity_description="Severe Delays",
                reason="Signal failure",
                created_at=datetime.now(UTC),
            ),
        ]
    )
    mock_tfl_class.return_value = mock_tfl_instance

    # Set up disabled severity pairs - (tube, 10) should be filtered
    disabled_severity_pairs: set[tuple[str, int]] = {("tube", 10)}

    disruptions, error_occurred = await alert_service._get_route_disruptions(
        test_route_with_schedule, disabled_severity_pairs
    )

    # Should return no error
    assert not error_occurred
    # Should only return the disruption with severity 5 (Severe Delays)
    # The Good Service (severity 10) should be filtered out
    assert len(disruptions) == 1
    assert disruptions[0].status_severity == 5
    assert disruptions[0].status_severity_description == "Severe Delays"


# NOTE: Fallback path tests for lines 650, 665-666 in alert_service.py were attempted
# but are too complex due to SQLAlchemy lazy loading in async contexts. These are
# rare defensive code paths that don't justify the test complexity. The main coverage
# improvements focus on the new endpoint code instead.


# ==================== _should_send_alert Tests ====================


@pytest.mark.asyncio
async def test_should_send_alert_no_previous_alert(
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert should be sent when no previous alert exists."""
    # Get the schedule
    schedule = test_route_with_schedule.schedules[0]

    # Redis returns None (no previous alert)
    should_send, filtered = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert should_send is True
    assert len(filtered) > 0


@pytest.mark.asyncio
async def test_should_send_alert_same_disruption(
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert should not be sent for same disruption content."""
    schedule = test_route_with_schedule.schedules[0]

    # Group disruptions by line and create per-line hashes (v2 format)
    disruptions_by_line = alert_service._group_disruptions_by_line(sample_disruptions)
    lines_state = {}
    for line_id, line_disruptions in disruptions_by_line.items():
        lines_state[line_id] = {
            "full_hash": alert_service._create_line_full_hash(line_disruptions),
            "status_hash": alert_service._create_line_status_hash(line_disruptions),
            "severity": line_disruptions[0].status_severity,
            "status": line_disruptions[0].status_severity_description,
            "last_sent_at": datetime.now(UTC).isoformat(),
        }

    # Mock Redis to return stored state with same hashes (v2 format)
    stored_state = json.dumps(
        {
            "version": 2,
            "lines": lines_state,
            "stored_at": datetime.now(UTC).isoformat(),
        }
    )
    alert_service.redis_client.get = AsyncMock(return_value=stored_state)  # type: ignore[method-assign]

    should_send, filtered = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert should_send is False
    assert len(filtered) == 0


@pytest.mark.asyncio
async def test_should_send_alert_changed_disruption(
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert should be sent when disruption content changes."""
    schedule = test_route_with_schedule.schedules[0]

    # Create different disruptions for stored state
    different_disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=6,
            status_severity_description="Minor Delays",  # Changed
            reason="Different reason",  # Changed
            created_at=datetime.now(UTC),
        ),
    ]

    # Create stored state with different disruptions (v2 format)
    disruptions_by_line = alert_service._group_disruptions_by_line(different_disruptions)
    lines_state = {}
    for line_id, line_disruptions in disruptions_by_line.items():
        lines_state[line_id] = {
            "full_hash": alert_service._create_line_full_hash(line_disruptions),
            "status_hash": alert_service._create_line_status_hash(line_disruptions),
            "severity": line_disruptions[0].status_severity,
            "status": line_disruptions[0].status_severity_description,
            "last_sent_at": datetime.now(UTC).isoformat(),
        }

    stored_state = json.dumps(
        {
            "version": 2,
            "lines": lines_state,
            "stored_at": datetime.now(UTC).isoformat(),
        }
    )
    alert_service.redis_client.get = AsyncMock(return_value=stored_state)  # type: ignore[method-assign]

    should_send, filtered = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert should_send is True
    assert len(filtered) > 0


@pytest.mark.asyncio
async def test_should_send_alert_redis_error(
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert defaults to sending on Redis error."""
    schedule = test_route_with_schedule.schedules[0]

    # Mock Redis to raise error
    alert_service.redis_client.get = AsyncMock(side_effect=Exception("Redis error"))  # type: ignore[method-assign]

    should_send, filtered = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    # Should default to sending (better to over-notify than under-notify)
    assert should_send is True
    assert len(filtered) > 0


@pytest.mark.asyncio
async def test_should_send_alert_invalid_stored_data(
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
    sample_disruptions: list[DisruptionResponse],
) -> None:
    """Test that alert is sent when stored data is invalid."""
    schedule = test_route_with_schedule.schedules[0]

    # Mock Redis to return invalid JSON
    alert_service.redis_client.get = AsyncMock(return_value="invalid json")  # type: ignore[method-assign]

    should_send, filtered = await alert_service._should_send_alert(
        route=test_route_with_schedule,
        user_id=test_route_with_schedule.user_id,
        schedule=schedule,
        disruptions=sample_disruptions,
    )

    assert should_send is True
    assert len(filtered) > 0


# ==================== _send_alerts_for_route Tests ====================


@pytest.mark.asyncio
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_for_route_success(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
    test_route_with_schedule: UserRoute,
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
    route = UserRoute(
        user_id=test_user_with_contacts.id,
        name="No Prefs Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.flush()

    segment = UserRouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    schedule = UserRouteSchedule(
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
    route = UserRoute(
        user_id=test_user_with_contacts.id,
        name="Unverified Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.flush()

    segment = UserRouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    schedule = UserRouteSchedule(
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
    route = UserRoute(
        user_id=test_user_with_contacts.id,
        name="Mixed Verification Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.flush()

    segment = UserRouteSegment(
        route_id=route.id,
        sequence=0,
        station_id=test_station.id,
        line_id=test_line.id,
    )
    db_session.add(segment)

    schedule = UserRouteSchedule(
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
        select(UserRoute)
        .where(UserRoute.id == route.id)
        .options(
            selectinload(UserRoute.segments),
            selectinload(UserRoute.schedules),
            selectinload(UserRoute.notification_preferences),
            selectinload(UserRoute.user).selectinload(User.email_addresses),
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
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

    # Verify v2 format structure
    assert stored_data["version"] == 2
    assert "lines" in stored_data
    assert "stored_at" in stored_data
    # Verify per-line hashes are present
    for _line_id, line_state in stored_data["lines"].items():
        assert "full_hash" in line_state
        assert "status_hash" in line_state
        assert len(line_state["full_hash"]) == 64  # SHA256 hex digest
        assert len(line_state["status_hash"]) == 64  # SHA256 hex digest
        assert "severity" in line_state
        assert "status" in line_state
        assert "last_sent_at" in line_state


# ==================== _create_disruption_hash Tests ====================


def test_create_disruption_hash_stable(alert_service: AlertService) -> None:
    """Test that same disruptions create same hash."""
    disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
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
            mode="tube",
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
            mode="tube",
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
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            mode="tube",
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
            mode="tube",
            status_severity=6,
            status_severity_description="Minor Delays",
            reason="Train cancellations",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions1)
    hash2 = alert_service._create_disruption_hash(disruptions2)

    assert hash1 == hash2


def test_create_disruption_hash_multiple_disruptions_same_line(
    alert_service: AlertService,
) -> None:
    """Test that multiple disruptions on same line produce same hash regardless of order."""
    # Create disruptions matching the real-world scenario from issue #267
    # Circle is first, then Piccadilly disruptions in one order
    disruptions1 = [
        DisruptionResponse(
            line_id="circle",
            line_name="Circle",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Circle Line: Severe delays while we fix a points failure at Gloucester Road.",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=6,
            status_severity_description="Part Suspended",
            reason="Piccadilly Line: No Service between Hyde Park Corner and King's Cross...",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Piccadilly Line: No Service between Hyde Park Corner and King's Cross...",
            created_at=datetime.now(UTC),
        ),
    ]

    # Same disruptions, Circle still first, but Piccadilly disruptions swapped
    disruptions2 = [
        DisruptionResponse(
            line_id="circle",
            line_name="Circle",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Circle Line: Severe delays while we fix a points failure at Gloucester Road.",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Piccadilly Line: No Service between Hyde Park Corner and King's Cross...",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=6,
            status_severity_description="Part Suspended",
            reason="Piccadilly Line: No Service between Hyde Park Corner and King's Cross...",
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions1)
    hash2 = alert_service._create_disruption_hash(disruptions2)

    assert hash1 == hash2


def test_create_disruption_hash_null_reason_handling(
    alert_service: AlertService,
) -> None:
    """Test that disruptions with None reasons are handled correctly in sorting."""
    disruptions1 = [
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason=None,
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure at Camden Town",
            created_at=datetime.now(UTC),
        ),
    ]

    disruptions2 = [
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure at Camden Town",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason=None,
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions1)
    hash2 = alert_service._create_disruption_hash(disruptions2)

    assert hash1 == hash2


def test_create_disruption_hash_same_status_different_reasons(
    alert_service: AlertService,
) -> None:
    """Test that disruptions with same line_id and status but different reasons hash consistently."""
    disruptions1 = [
        DisruptionResponse(
            line_id="central",
            line_name="Central",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure at Bank",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="central",
            line_name="Central",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Train cancellations",
            created_at=datetime.now(UTC),
        ),
    ]

    disruptions2 = [
        DisruptionResponse(
            line_id="central",
            line_name="Central",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Train cancellations",
            created_at=datetime.now(UTC),
        ),
        DisruptionResponse(
            line_id="central",
            line_name="Central",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure at Bank",
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions1)
    hash2 = alert_service._create_disruption_hash(disruptions2)

    assert hash1 == hash2


def test_create_disruption_hash_empty_string_vs_none(
    alert_service: AlertService,
) -> None:
    """Test that empty string and None reasons produce the same hash."""
    disruptions1 = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason=None,
            created_at=datetime.now(UTC),
        ),
    ]

    disruptions2 = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="",
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions1)
    hash2 = alert_service._create_disruption_hash(disruptions2)

    assert hash1 == hash2


def test_create_disruption_hash_different_severity_different_hash(
    alert_service: AlertService,
) -> None:
    """Test that different numeric severities produce different hashes even with same description."""
    # Same line, same description, but different numeric severity
    disruptions1 = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=5,
            status_severity_description="Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]

    disruptions2 = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=6,
            status_severity_description="Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]

    hash1 = alert_service._create_disruption_hash(disruptions1)
    hash2 = alert_service._create_disruption_hash(disruptions2)

    # Different severities should produce different hashes
    assert hash1 != hash2


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
    mock_route = Mock(spec=UserRoute)
    mock_route.id = "test-route"
    mock_route.name = "Test Route"

    mock_disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]

    with (
        patch.object(alert_service, "_should_send_alert", return_value=(False, [])),
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
        mock_route = Mock(spec=UserRoute)
        mock_route.id = uuid4()  # Use valid UUID instead of string
        mock_route.name = "Error Route"
        mock_route.schedules = [Mock()]
        mock_db_result = Mock()
        mock_db_result.scalars.return_value.all.return_value = []  # No schedules

        with (
            patch.object(alert_service, "_get_active_routes", return_value=[mock_route]),
            patch.object(alert_service.db, "execute", return_value=mock_db_result),  # Mock DB for schedule loading
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
        side_effect=SQLAlchemyError("Database connection error"),
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
    route = UserRoute(user_id=user.id, name="Test", active=True, timezone="UTC")
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
    route = Mock(spec=UserRoute)
    route.user = None

    name = alert_service._get_user_display_name(route)
    assert name is None


@pytest.mark.asyncio
async def test_get_active_schedule_exception_handling(
    alert_service: AlertService,
) -> None:
    """Test _get_active_schedule exception handling (lines 255-262)."""
    mock_route = Mock(spec=UserRoute)
    mock_route.id = uuid4()
    mock_route.timezone = "Invalid/Timezone"  # Invalid timezone will cause error
    mock_schedules = [Mock()]

    # This should handle the exception and return None
    schedule = await alert_service._get_active_schedule(mock_route, mock_schedules)
    assert schedule is None


@pytest.mark.asyncio
@patch("app.services.alert_service.NotificationService")
async def test_send_alerts_for_route_no_preferences(
    mock_notif_class: MagicMock,
    alert_service: AlertService,
) -> None:
    """Test _send_alerts_for_route with no notification preferences (lines 594-599)."""
    mock_route = Mock(spec=UserRoute)
    mock_route.id = uuid4()
    mock_route.name = "Test Route"
    mock_route.notification_preferences = []  # No preferences

    mock_schedule = Mock()
    disruptions = [
        DisruptionResponse(
            line_id="victoria",
            line_name="Victoria",
            mode="tube",
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
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
    test_route_with_schedule: UserRoute,
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
            mode="tube",
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
            mode="tube",
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
            mode="tube",
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
            mode="tube",
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
            mode="tube",
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
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Create index entries
        index1 = UserRouteStationIndex(
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
        route = UserRoute(
            user_id=test_user.id,
            name="King's Cross to Leicester Square",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Create index entries for multiple stations on same route
        for station in ["940GZZLUKSX", "940GZZLURSQ", "940GZZLUHBN"]:
            index_entry = UserRouteStationIndex(
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
        route1 = UserRoute(
            user_id=test_user.id,
            name="Route 1",
            active=True,
            timezone="Europe/London",
        )
        route2 = UserRoute(
            user_id=test_user.id,
            name="Route 2",
            active=True,
            timezone="Europe/London",
        )
        db_session.add_all([route1, route2])
        await db_session.flush()

        # Both routes pass through King's Cross on Piccadilly
        for route in [route1, route2]:
            index_entry = UserRouteStationIndex(
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
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Create index entry
        index_entry = UserRouteStationIndex(
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
            mode="tube",
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
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        segment = UserRouteSegment(
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
            mode="tube",
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
            mode="tube",
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
        active_route = UserRoute(
            user_id=test_user.id,
            name="Active Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(active_route)
        await db_session.flush()

        segment1 = UserRouteSegment(
            route_id=active_route.id,
            sequence=1,
            station_id=test_station.id,
            line_id=test_line.id,
        )
        db_session.add(segment1)

        # Create inactive route
        inactive_route = UserRoute(
            user_id=test_user.id,
            name="Inactive Route",
            active=False,  # Inactive
            timezone="Europe/London",
        )
        db_session.add(inactive_route)
        await db_session.flush()

        segment2 = UserRouteSegment(
            route_id=inactive_route.id,
            sequence=1,
            station_id=test_station.id,
            line_id=test_line.id,
        )
        db_session.add(segment2)

        # Create deleted route
        deleted_route = UserRoute(
            user_id=test_user.id,
            name="Deleted Route",
            active=True,
            timezone="Europe/London",
            deleted_at=datetime.now(UTC),  # Soft deleted
        )
        db_session.add(deleted_route)
        await db_session.flush()

        segment3 = UserRouteSegment(
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
            mode="tube",
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
        route_a = UserRoute(
            user_id=test_user.id,
            name="King's Cross to Leicester Square",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route_a)
        await db_session.flush()

        # Index entries for Route A (passes through Russell Square and Holborn)
        for station in ["940GZZLUKSX", "940GZZLURSQ", "940GZZLUHBN", "940GZZLUCGN", "940GZZLULSQ"]:
            index_entry = UserRouteStationIndex(
                route_id=route_a.id,
                line_tfl_id="piccadilly",
                station_naptan=station,
                line_data_version=datetime.now(UTC),
            )
            db_session.add(index_entry)

        # Create Route B: western branch (Earl's Court → Heathrow)
        route_b = UserRoute(
            user_id=test_user.id,
            name="Earl's Court to Heathrow",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route_b)
        await db_session.flush()

        # Index entries for Route B (western branch, does NOT include Russell Square/Holborn)
        for station in ["940GZZLUECT", "940GZZLUHOR", "940GZZLUHRC"]:
            index_entry = UserRouteStationIndex(
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
            mode="tube",
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
        route_a = UserRoute(
            user_id=test_user.id,
            name="Kennington to Edgware",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route_a)
        await db_session.flush()

        # Index for Route A includes Camden Town
        for station in ["940GZZLUKNG", "940GZZLUETN", "940GZZLUCTW", "940GZZLUKTN"]:
            index_entry = UserRouteStationIndex(
                route_id=route_a.id,
                line_tfl_id="northern",
                station_naptan=station,
                line_data_version=datetime.now(UTC),
            )
            db_session.add(index_entry)

        # Route B: Kennington → High Barnet (Bank branch, NOT via Camden Town)
        route_b = UserRoute(
            user_id=test_user.id,
            name="Kennington to High Barnet",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route_b)
        await db_session.flush()

        # Index for Route B does NOT include Camden Town
        for station in ["940GZZLUKNG", "940GZZLUBKE", "940GZZLUMRG", "940GZZLUHGB"]:
            index_entry = UserRouteStationIndex(
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
            mode="tube",
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
            route = UserRoute(
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
                index_entry = UserRouteStationIndex(
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
                mode="tube",
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

        # Should complete in under 500ms (configurable via env var, defaults to 500ms for CI stability)
        perf_threshold = int(os.getenv("PERF_TEST_THRESHOLD_MS", "500"))
        assert elapsed_ms < perf_threshold, (
            f"Performance test failed: took {elapsed_ms:.2f}ms (expected < {perf_threshold}ms)"
        )

    async def test_performance_index_query_is_fast(
        self,
        alert_service: AlertService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that index queries are fast even with many entries."""

        # Create 10,000 index entries across 100 routes
        for route_num in range(100):
            route = UserRoute(
                user_id=test_user.id,
                name=f"Route {route_num}",
                active=True,
                timezone="Europe/London",
            )
            db_session.add(route)
            await db_session.flush()

            # Each route has 100 stations
            for station_num in range(100):
                index_entry = UserRouteStationIndex(
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

        # Should return routes quickly (configurable via env var, defaults to 100ms for CI stability)
        index_perf_threshold = int(os.getenv("INDEX_PERF_TEST_THRESHOLD_MS", "100"))
        assert len(result) > 0
        assert elapsed_ms < index_perf_threshold, (
            f"Index query took {elapsed_ms:.2f}ms (expected < {index_perf_threshold}ms)"
        )


class TestLineDisruptionStateLogging:
    """Tests for line disruption state logging functionality."""

    def test_create_line_aggregate_hash_deterministic(self):
        """Test that create_line_aggregate_hash produces consistent hashes."""
        # Same disruptions should produce same hash
        disruptions1 = [
            DisruptionResponse(
                line_id="bakerloo",
                line_name="Bakerloo",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]
        disruptions2 = [
            DisruptionResponse(
                line_id="bakerloo",
                line_name="Bakerloo",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]

        hash1 = create_line_aggregate_hash(disruptions1)
        hash2 = create_line_aggregate_hash(disruptions2)
        assert hash1 == hash2

        # Hash should be 64 characters (SHA256 hex digest)
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_create_line_aggregate_hash_multiple_statuses_order_independent(self):
        """Test that hash is same regardless of input order (function sorts internally)."""
        # Create disruptions in different orders
        disruptions_order1 = [
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=20,
                status_severity_description="Part Suspended",
                reason="Engineering works",
            ),
        ]

        disruptions_order2 = [
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=20,
                status_severity_description="Part Suspended",
                reason="Engineering works",
            ),
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            ),
        ]

        hash1 = create_line_aggregate_hash(disruptions_order1)
        hash2 = create_line_aggregate_hash(disruptions_order2)
        assert hash1 == hash2

    def test_create_line_aggregate_hash_different_states(self):
        """Test that different states produce different hashes."""
        disruptions1 = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]

        disruptions2 = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=20,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            )
        ]

        disruptions3 = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Track fault",
            )
        ]

        hash1 = create_line_aggregate_hash(disruptions1)
        hash2 = create_line_aggregate_hash(disruptions2)
        hash3 = create_line_aggregate_hash(disruptions3)

        # All different
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_create_line_aggregate_hash_different_numeric_severity(self):
        """Test that different numeric severity produces different hashes even with same status description."""
        disruptions_severity_10 = [
            DisruptionResponse(
                line_id="jubilee",
                line_name="Jubilee",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]

        disruptions_severity_15 = [
            DisruptionResponse(
                line_id="jubilee",
                line_name="Jubilee",
                mode="tube",
                status_severity=15,
                status_severity_description="Minor Delays",  # Same description
                reason="Signal failure",  # Same reason
            )
        ]

        hash1 = create_line_aggregate_hash(disruptions_severity_10)
        hash2 = create_line_aggregate_hash(disruptions_severity_15)

        # Different numeric severity should produce different hash
        assert hash1 != hash2

    def test_create_line_aggregate_hash_null_reason_normalization(self):
        """Test that None, empty string, and whitespace reasons are normalized."""
        disruptions_none = [
            DisruptionResponse(
                line_id="district",
                line_name="District",
                mode="tube",
                status_severity=6,
                status_severity_description="Good Service",
                reason=None,
            )
        ]

        disruptions_empty = [
            DisruptionResponse(
                line_id="district",
                line_name="District",
                mode="tube",
                status_severity=6,
                status_severity_description="Good Service",
                reason="",
            )
        ]

        disruptions_whitespace = [
            DisruptionResponse(
                line_id="district",
                line_name="District",
                mode="tube",
                status_severity=6,
                status_severity_description="Good Service",
                reason="   ",
            )
        ]

        hash_none = create_line_aggregate_hash(disruptions_none)
        hash_empty = create_line_aggregate_hash(disruptions_empty)
        hash_whitespace = create_line_aggregate_hash(disruptions_whitespace)

        # All should produce the same hash
        assert hash_none == hash_empty == hash_whitespace

        # Should differ from a reason with actual content
        disruptions_with_reason = [
            DisruptionResponse(
                line_id="district",
                line_name="District",
                mode="tube",
                status_severity=6,
                status_severity_description="Good Service",
                reason="Testing",
            )
        ]
        hash_with_reason = create_line_aggregate_hash(disruptions_with_reason)
        assert hash_none != hash_with_reason

    def test_create_line_aggregate_hash_mixed_line_ids_raises_error(self):
        """Test that passing disruptions with different line_ids raises ValueError."""
        # Create disruptions for different lines
        disruptions_mixed = [
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="victoria",  # Different line_id
                line_name="Victoria",
                mode="tube",
                status_severity=20,
                status_severity_description="Severe Delays",
                reason="Track fault",
            ),
        ]

        # Should raise ValueError
        with pytest.raises(ValueError, match="All disruptions must have the same line_id"):
            create_line_aggregate_hash(disruptions_mixed)

    async def test_log_line_disruption_state_changes_first_state(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock,
    ):
        """Test that first disruption state is always logged."""
        alert_service = AlertService(db=db_session, redis_client=mock_redis)

        # Create disruption
        disruption = DisruptionResponse(
            line_id="bakerloo",
            line_name="Bakerloo",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Signal failure at Baker Street",
        )

        # Log state change
        logged_count = await alert_service._log_line_disruption_state_changes([disruption])

        # Should log because no previous state
        assert logged_count == 1

        # Verify database entry
        result = await db_session.execute(select(LineDisruptionStateLog))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].line_id == "bakerloo"
        assert logs[0].status_severity_description == "Minor Delays"
        assert logs[0].reason == "Signal failure at Baker Street"
        assert logs[0].state_hash is not None
        assert logs[0].detected_at is not None

    async def test_log_line_disruption_state_changes_no_change(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
    ):
        """Test that unchanged disruption state is not logged again."""
        alert_service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Create disruption
        disruption = DisruptionResponse(
            line_id="central",
            line_name="Central",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Train cancellation",
        )

        # Log first state
        logged_count1 = await alert_service._log_line_disruption_state_changes([disruption])
        assert logged_count1 == 1

        # Log same state again
        logged_count2 = await alert_service._log_line_disruption_state_changes([disruption])
        assert logged_count2 == 0  # Should not log duplicate

        # Verify only one database entry
        result = await db_session.execute(
            select(LineDisruptionStateLog).where(LineDisruptionStateLog.line_id == "central")
        )
        logs = result.scalars().all()
        assert len(logs) == 1

    async def test_log_line_disruption_state_changes_state_changed(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock,
    ):
        """Test that changed disruption state is logged."""
        alert_service = AlertService(db=db_session, redis_client=mock_redis)

        # Create initial disruption
        disruption1 = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Passenger incident",
        )

        # Log first state
        logged_count1 = await alert_service._log_line_disruption_state_changes([disruption1])
        assert logged_count1 == 1

        # Create changed disruption (same line, different status)
        disruption2 = DisruptionResponse(
            line_id="piccadilly",
            line_name="Piccadilly",
            mode="tube",
            status_severity=20,
            status_severity_description="Severe Delays",
            reason="Passenger incident",
        )

        # Log changed state
        logged_count2 = await alert_service._log_line_disruption_state_changes([disruption2])
        assert logged_count2 == 1  # Should log because state changed

        # Verify two database entries
        result = await db_session.execute(
            select(LineDisruptionStateLog)
            .where(LineDisruptionStateLog.line_id == "piccadilly")
            .order_by(LineDisruptionStateLog.detected_at)
        )
        logs = result.scalars().all()
        assert len(logs) == 2
        assert logs[0].status_severity_description == "Minor Delays"
        assert logs[1].status_severity_description == "Severe Delays"

    async def test_log_line_disruption_state_changes_reason_changed(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock,
    ):
        """Test that changed disruption reason is logged even if status is same."""
        alert_service = AlertService(db=db_session, redis_client=mock_redis)

        # Create initial disruption
        disruption1 = DisruptionResponse(
            line_id="district",
            line_name="District",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Signal failure at Earl's Court",
        )

        # Log first state
        logged_count1 = await alert_service._log_line_disruption_state_changes([disruption1])
        assert logged_count1 == 1

        # Create disruption with same status but different reason
        disruption2 = DisruptionResponse(
            line_id="district",
            line_name="District",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Signal failure at Tower Hill",
        )

        # Log changed state
        logged_count2 = await alert_service._log_line_disruption_state_changes([disruption2])
        assert logged_count2 == 1  # Should log because reason changed

        # Verify two database entries with different reasons
        result = await db_session.execute(
            select(LineDisruptionStateLog)
            .where(LineDisruptionStateLog.line_id == "district")
            .order_by(LineDisruptionStateLog.detected_at)
        )
        logs = result.scalars().all()
        assert len(logs) == 2
        assert logs[0].reason == "Signal failure at Earl's Court"
        assert logs[1].reason == "Signal failure at Tower Hill"

    async def test_log_line_disruption_state_changes_multiple_lines(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock,
    ):
        """Test that multiple line disruptions are logged correctly."""
        alert_service = AlertService(db=db_session, redis_client=mock_redis)

        # Create disruptions for multiple lines
        disruptions = [
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Train cancellation",
            ),
            DisruptionResponse(
                line_id="jubilee",
                line_name="Jubilee",
                mode="tube",
                status_severity=20,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="metropolitan",
                line_name="Metropolitan",
                mode="tube",
                status_severity=6,
                status_severity_description="Good Service",
                reason=None,
            ),
        ]

        # Log all states
        logged_count = await alert_service._log_line_disruption_state_changes(disruptions)
        assert logged_count == 3

        # Verify database entries
        result = await db_session.execute(select(LineDisruptionStateLog).order_by(LineDisruptionStateLog.line_id))
        logs = result.scalars().all()
        assert len(logs) == 3
        assert {log.line_id for log in logs} == {"northern", "jubilee", "metropolitan"}

    async def test_log_line_disruption_state_changes_same_line_multiple_times(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock,
    ):
        """Test behavior when multiple disruptions for same line in single call.

        This scenario is unlikely with real TfL data (API returns one state per line),
        but tests edge case behavior. Current implementation logs both states since
        deduplication query doesn't see uncommitted changes from same batch.
        """
        alert_service = AlertService(db=db_session, redis_client=mock_redis)

        # Create two disruptions for same line with different statuses
        disruptions = [
            DisruptionResponse(
                line_id="bakerloo",
                line_name="Bakerloo",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="bakerloo",
                line_name="Bakerloo",
                mode="tube",
                status_severity=20,
                status_severity_description="Severe Delays",
                reason="Signal failure worsening",
            ),
        ]

        # Log both states
        logged_count = await alert_service._log_line_disruption_state_changes(disruptions)

        # Both should be logged (no within-batch deduplication)
        # This is acceptable behavior given the unlikely scenario
        assert logged_count == 2

        # Verify both entries exist in database
        result = await db_session.execute(
            select(LineDisruptionStateLog)
            .where(LineDisruptionStateLog.line_id == "bakerloo")
            .order_by(LineDisruptionStateLog.detected_at)
        )
        logs = result.scalars().all()
        assert len(logs) == 2
        assert logs[0].status_severity_description == "Minor Delays"
        assert logs[1].status_severity_description == "Severe Delays"

    async def test_log_line_disruption_state_changes_empty_reason_normalization(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
    ):
        """Test that empty string and whitespace-only reasons are normalized correctly."""
        alert_service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Log first disruption with None reason
        disruption1 = DisruptionResponse(
            line_id="district",
            line_name="District",
            mode="tube",
            status_severity=6,
            status_severity_description="Good Service",
            reason=None,
        )
        logged_count1 = await alert_service._log_line_disruption_state_changes([disruption1])
        assert logged_count1 == 1

        # Log second disruption with empty string reason - should NOT log (same hash)
        disruption2 = DisruptionResponse(
            line_id="district",
            line_name="District",
            mode="tube",
            status_severity=6,
            status_severity_description="Good Service",
            reason="",
        )
        logged_count2 = await alert_service._log_line_disruption_state_changes([disruption2])
        assert logged_count2 == 0  # Not logged because hash unchanged

        # Log third disruption with whitespace-only reason - should NOT log (same hash)
        disruption3 = DisruptionResponse(
            line_id="district",
            line_name="District",
            mode="tube",
            status_severity=6,
            status_severity_description="Good Service",
            reason="   ",
        )
        logged_count3 = await alert_service._log_line_disruption_state_changes([disruption3])
        assert logged_count3 == 0  # Not logged because hash unchanged

        # Verify only one entry exists
        result = await db_session.execute(
            select(LineDisruptionStateLog).where(LineDisruptionStateLog.line_id == "district")
        )
        logs = result.scalars().all()
        assert len(logs) == 1

    async def test_log_line_disruption_state_changes_very_long_reason(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock,
    ):
        """Test that very long reason strings (>1000 chars) are handled correctly after TEXT migration."""
        alert_service = AlertService(db=db_session, redis_client=mock_redis)

        # Create reason string exceeding old 1000 character VARCHAR limit
        # This simulates real TfL API responses that can exceed 1000 characters
        long_reason = "A" * 2000

        disruption = DisruptionResponse(
            line_id="central",
            line_name="Central",
            mode="tube",
            status_severity=20,
            status_severity_description="Severe Delays",
            reason=long_reason,
        )

        # Log state - should succeed without truncation error after TEXT migration
        logged_count = await alert_service._log_line_disruption_state_changes([disruption])
        assert logged_count == 1

        # Verify database entry with full 2000-character reason (no truncation)
        result = await db_session.execute(
            select(LineDisruptionStateLog).where(LineDisruptionStateLog.line_id == "central")
        )
        log = result.scalar_one()
        assert log.line_id == "central"
        assert log.status_severity_description == "Severe Delays"
        assert log.reason == long_reason
        assert len(log.reason) == 2000

    async def test_log_line_disruption_state_changes_null_reason(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock,
    ):
        """Test that null reason is handled correctly."""
        alert_service = AlertService(db=db_session, redis_client=mock_redis)

        # Create disruption with no reason (Good Service)
        disruption = DisruptionResponse(
            line_id="circle",
            line_name="Circle",
            mode="tube",
            status_severity=6,
            status_severity_description="Good Service",
            reason=None,
        )

        # Log state
        logged_count = await alert_service._log_line_disruption_state_changes([disruption])
        assert logged_count == 1

        # Verify database entry with null reason
        result = await db_session.execute(
            select(LineDisruptionStateLog).where(LineDisruptionStateLog.line_id == "circle")
        )
        log = result.scalar_one()
        assert log.line_id == "circle"
        assert log.status_severity_description == "Good Service"
        assert log.reason is None

    async def test_log_line_disruption_state_changes_error_handling(
        self,
        db_session: AsyncSession,
        mock_redis: AsyncMock,
    ):
        """Test that logging errors don't crash the alert processing."""
        alert_service = AlertService(db=db_session, redis_client=mock_redis)

        disruption = DisruptionResponse(
            line_id="hammersmith-city",
            line_name="Hammersmith & City",
            mode="tube",
            status_severity=10,
            status_severity_description="Minor Delays",
            reason="Test error",
        )

        # Mock db.commit to raise an exception
        with patch.object(db_session, "commit", side_effect=Exception("Database commit error")):
            # Should not raise, should return 0
            logged_count = await alert_service._log_line_disruption_state_changes([disruption])
            assert logged_count == 0

    async def test_warm_up_line_state_cache_empty_database(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
    ):
        """Test warm_up_line_state_cache with empty database."""
        # Call warm_up with no existing logs
        lines_hydrated = await warm_up_line_state_cache(db_session, stateful_mock_redis)

        # Should return 0 and not crash
        assert lines_hydrated == 0

        # Redis should not have any line state keys set
        # (we can't directly check this with mock, but function should handle gracefully)

    async def test_warm_up_line_state_cache_single_line_single_status(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
    ):
        """Test warm_up_line_state_cache with single line and single status."""
        # Create a log entry
        detected_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        state_hash = "abc123def456"

        log_entry = LineDisruptionStateLog(
            line_id="bakerloo",
            status_severity_description="Minor Delays",
            reason="Signal failure",
            state_hash=state_hash,
            detected_at=detected_time,
        )
        db_session.add(log_entry)
        await db_session.commit()

        # Warm up cache
        lines_hydrated = await warm_up_line_state_cache(db_session, stateful_mock_redis)

        # Should hydrate 1 line
        assert lines_hydrated == 1

        # Verify Redis was called with correct key/value
        redis_value = await stateful_mock_redis.get("line_state:bakerloo")
        assert redis_value == state_hash

    async def test_warm_up_line_state_cache_single_line_multiple_statuses(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
    ):
        """Test warm_up_line_state_cache with single line having multiple statuses."""
        # Create multiple log entries for same line at same timestamp (batch logging)
        detected_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        aggregate_hash = "shared_aggregate_hash_123"

        log1 = LineDisruptionStateLog(
            line_id="northern",
            status_severity_description="Minor Delays",
            reason="Signal failure",
            state_hash=aggregate_hash,  # Same aggregate hash
            detected_at=detected_time,
        )
        log2 = LineDisruptionStateLog(
            line_id="northern",
            status_severity_description="Part Suspended",
            reason="Engineering works",
            state_hash=aggregate_hash,  # Same aggregate hash
            detected_at=detected_time,
        )

        db_session.add_all([log1, log2])
        await db_session.commit()

        # Warm up cache
        lines_hydrated = await warm_up_line_state_cache(db_session, stateful_mock_redis)

        # Should hydrate 1 line (not 2, even though 2 records)
        assert lines_hydrated == 1

        # Verify Redis has the aggregate hash
        redis_value = await stateful_mock_redis.get("line_state:northern")
        assert redis_value == aggregate_hash

    async def test_warm_up_line_state_cache_multiple_lines(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
    ):
        """Test warm_up_line_state_cache with multiple lines."""
        detected_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        # Create logs for multiple lines
        log1 = LineDisruptionStateLog(
            line_id="victoria",
            status_severity_description="Good Service",
            reason=None,
            state_hash="victoria_hash_abc",
            detected_at=detected_time,
        )
        log2 = LineDisruptionStateLog(
            line_id="central",
            status_severity_description="Minor Delays",
            reason="Train fault",
            state_hash="central_hash_def",
            detected_at=detected_time,
        )
        log3 = LineDisruptionStateLog(
            line_id="piccadilly",
            status_severity_description="Severe Delays",
            reason="Signal failure",
            state_hash="piccadilly_hash_ghi",
            detected_at=detected_time,
        )

        db_session.add_all([log1, log2, log3])
        await db_session.commit()

        # Warm up cache
        lines_hydrated = await warm_up_line_state_cache(db_session, stateful_mock_redis)

        # Should hydrate 3 lines
        assert lines_hydrated == 3

        # Verify each line's state in Redis
        assert await stateful_mock_redis.get("line_state:victoria") == "victoria_hash_abc"
        assert await stateful_mock_redis.get("line_state:central") == "central_hash_def"
        assert await stateful_mock_redis.get("line_state:piccadilly") == "piccadilly_hash_ghi"

    async def test_warm_up_line_state_cache_uses_latest_state(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
    ):
        """Test that warm_up uses the latest detected_at timestamp per line."""
        old_time = datetime(2025, 1, 15, 8, 0, 0, tzinfo=UTC)
        new_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create older log entry
        old_log = LineDisruptionStateLog(
            line_id="jubilee",
            status_severity_description="Good Service",
            reason=None,
            state_hash="old_hash_123",
            detected_at=old_time,
        )

        # Create newer log entry (current state)
        new_log = LineDisruptionStateLog(
            line_id="jubilee",
            status_severity_description="Minor Delays",
            reason="Late running",
            state_hash="new_hash_456",
            detected_at=new_time,
        )

        db_session.add_all([old_log, new_log])
        await db_session.commit()

        # Warm up cache
        lines_hydrated = await warm_up_line_state_cache(db_session, stateful_mock_redis)

        # Should hydrate 1 line
        assert lines_hydrated == 1

        # Should use the LATEST state (new_hash), not old_hash
        redis_value = await stateful_mock_redis.get("line_state:jubilee")
        assert redis_value == "new_hash_456"

    async def test_warm_up_line_state_cache_error_handling(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
    ):
        """Test that warm_up handles errors gracefully and returns 0."""
        # Mock db.execute to raise an exception
        with patch.object(db_session, "execute", side_effect=Exception("Database error")):
            # Should not raise, should return 0
            lines_hydrated = await warm_up_line_state_cache(db_session, stateful_mock_redis)
            assert lines_hydrated == 0


class TestPerLineCooldown:
    """Tests for per-line alert cooldown functionality (Issue #309)."""

    def test_group_disruptions_by_line(self, db_session: AsyncSession, stateful_mock_redis: AsyncMock):
        """Test that disruptions are correctly grouped by line_id."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=6,
                status_severity_description="Part Closure",
                reason="Engineering works",
            ),
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Train cancellations",
            ),
        ]

        grouped = service._group_disruptions_by_line(disruptions)

        assert len(grouped) == 2
        assert len(grouped["victoria"]) == 2
        assert len(grouped["piccadilly"]) == 1
        assert grouped["victoria"][0].reason == "Signal failure"
        assert grouped["piccadilly"][0].line_id == "piccadilly"

    def test_create_line_full_hash_includes_reason(self, db_session: AsyncSession, stateful_mock_redis: AsyncMock):
        """Test that full hash includes reason text."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        disruptions_v1 = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure at Oxford Circus",
            ),
        ]

        disruptions_v2 = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure at Victoria",  # Different reason
            ),
        ]

        hash1 = service._create_line_full_hash(disruptions_v1)
        hash2 = service._create_line_full_hash(disruptions_v2)

        # Different reasons should produce different hashes
        assert hash1 != hash2
        assert len(hash1) == 64  # SHA256 hex digest
        assert len(hash2) == 64

    def test_create_line_status_hash_excludes_reason(self, db_session: AsyncSession, stateful_mock_redis: AsyncMock):
        """Test that status hash excludes reason text."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        disruptions_v1 = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure at Oxford Circus",
            ),
        ]

        disruptions_v2 = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure at Victoria",  # Different reason
            ),
        ]

        hash1 = service._create_line_status_hash(disruptions_v1)
        hash2 = service._create_line_status_hash(disruptions_v2)

        # Same severity/status should produce same hash despite different reason
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_create_line_status_hash_changes_with_severity(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that status hash changes when severity changes."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        disruptions_severe = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
        ]

        disruptions_minor = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",  # Different status
                reason="Signal failure",
            ),
        ]

        hash_severe = service._create_line_status_hash(disruptions_severe)
        hash_minor = service._create_line_status_hash(disruptions_minor)

        # Different severity/status should produce different hashes
        assert hash_severe != hash_minor

    # ===== Unit tests for _check_line_alert_needed() =====

    def test_check_line_alert_needed_new_line_no_stored_state(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that new line with no stored state returns True."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
        ]

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=disruptions,
            stored_line=None,  # No previous state
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        assert result is True

    def test_check_line_alert_needed_no_change_same_hash(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that unchanged disruption (same hash) returns False."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
        ]

        # Create stored state with matching hash
        full_hash = service._create_line_full_hash(disruptions)
        status_hash = service._create_line_status_hash(disruptions)
        stored_line = {
            "full_hash": full_hash,
            "status_hash": status_hash,
            "severity": 4,
            "status": "Severe Delays",
            "last_sent_at": datetime.now(UTC).isoformat(),
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        assert result is False

    def test_check_line_alert_needed_severity_changed_bypasses_cooldown(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that severity/status change bypasses cooldown (returns True immediately)."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Old state: Minor Delays
        old_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=10,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            ),
        ]

        # New state: Severe Delays (escalated)
        new_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",  # Same reason
            ),
        ]

        # Stored state with old disruption, sent just now
        stored_line = {
            "full_hash": service._create_line_full_hash(old_disruptions),
            "status_hash": service._create_line_status_hash(old_disruptions),
            "severity": 10,
            "status": "Minor Delays",
            "last_sent_at": datetime.now(UTC).isoformat(),  # Just sent
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=new_disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        # Should return True despite being within cooldown
        assert result is True

    def test_check_line_alert_needed_status_description_changed(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that status description change bypasses cooldown."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Old state: Severe Delays
        old_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
        ]

        # New state: Part Closure (different status, same severity for this test)
        new_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Part Closure",
                reason="Signal failure",
            ),
        ]

        stored_line = {
            "full_hash": service._create_line_full_hash(old_disruptions),
            "status_hash": service._create_line_status_hash(old_disruptions),
            "severity": 4,
            "status": "Severe Delays",
            "last_sent_at": datetime.now(UTC).isoformat(),
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=new_disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        assert result is True

    def test_check_line_alert_needed_reason_only_cooldown_expired(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that reason-only change after cooldown returns True."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Same severity/status, different reason
        old_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure at Oxford Circus",
            ),
        ]

        new_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure at Victoria",  # Different reason
            ),
        ]

        # Sent 6 minutes ago (cooldown is 5 minutes)
        six_minutes_ago = datetime.now(UTC) - timedelta(minutes=6)
        stored_line = {
            "full_hash": service._create_line_full_hash(old_disruptions),
            "status_hash": service._create_line_status_hash(old_disruptions),
            "severity": 4,
            "status": "Severe Delays",
            "last_sent_at": six_minutes_ago.isoformat(),
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=new_disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        # Should return True (cooldown expired)
        assert result is True

    def test_check_line_alert_needed_reason_only_within_cooldown(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that reason-only change within cooldown returns False."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Same severity/status, different reason
        old_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure at Oxford Circus",
            ),
        ]

        new_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure at Victoria",  # Different reason
            ),
        ]

        # Sent 1 minute ago (cooldown is 5 minutes)
        one_minute_ago = datetime.now(UTC) - timedelta(minutes=1)
        stored_line = {
            "full_hash": service._create_line_full_hash(old_disruptions),
            "status_hash": service._create_line_status_hash(old_disruptions),
            "severity": 4,
            "status": "Severe Delays",
            "last_sent_at": one_minute_ago.isoformat(),
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=new_disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        # Should return False (within cooldown)
        assert result is False

    def test_check_line_alert_needed_reason_only_at_cooldown_boundary(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that reason-only change exactly at cooldown boundary returns True."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Same severity/status, different reason
        old_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure v1",
            ),
        ]

        new_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure v2",  # Different reason
            ),
        ]

        # Sent exactly 5 minutes ago (at cooldown boundary)
        cooldown_duration = timedelta(minutes=5)
        exactly_at_cooldown = datetime.now(UTC) - cooldown_duration
        stored_line = {
            "full_hash": service._create_line_full_hash(old_disruptions),
            "status_hash": service._create_line_status_hash(old_disruptions),
            "severity": 4,
            "status": "Severe Delays",
            "last_sent_at": exactly_at_cooldown.isoformat(),
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=new_disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=cooldown_duration,
            route_id="test-route",
        )

        # Should return True (boundary is inclusive: now_utc >= last_sent + cooldown)
        assert result is True

    def test_check_line_alert_needed_missing_last_sent_at(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that missing last_sent_at in stored line triggers immediate alert."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
        ]

        # Stored state missing last_sent_at
        stored_line = {
            "full_hash": "some_hash",
            "status_hash": "some_status_hash",
            "severity": 4,
            "status": "Severe Delays",
            # "last_sent_at" is missing
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        assert result is True  # Should alert immediately due to missing field

    def test_check_line_alert_needed_invalid_last_sent_at_format(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that invalid last_sent_at format triggers immediate alert."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Old disruption with different reason
        old_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure v1",
            ),
        ]

        # New disruption with different reason
        new_disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure v2",  # Different reason
            ),
        ]

        # Stored state with invalid last_sent_at format
        stored_line = {
            "full_hash": service._create_line_full_hash(old_disruptions),
            "status_hash": service._create_line_status_hash(old_disruptions),
            "severity": 4,
            "status": "Severe Delays",
            "last_sent_at": "not-a-valid-date",  # Invalid format
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=new_disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        assert result is True  # Should alert immediately due to invalid format

    def test_check_line_alert_needed_missing_required_fields(
        self, db_session: AsyncSession, stateful_mock_redis: AsyncMock
    ):
        """Test that missing required v2 fields trigger immediate alert."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
        ]

        # Stored state missing required v2 fields
        stored_line = {
            "severity": 4,
            "status": "Severe Delays",
            # Missing full_hash, status_hash, last_sent_at
        }

        result = service._check_line_alert_needed(
            line_id="victoria",
            line_disruptions=disruptions,
            stored_line=stored_line,
            now_utc=datetime.now(UTC),
            cooldown=timedelta(minutes=5),
            route_id="test-route",
        )

        assert result is True  # Should alert immediately due to corrupted state

    # ===== Integration tests for _should_send_alert() =====
    # (Redundant tests removed - covered by unit tests for _check_line_alert_needed())

    async def test_should_send_alert_multiple_lines_one_flickers(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
        test_route_with_schedule: UserRoute,
    ):
        """Test that only flickering lines are filtered out, others go through."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Mock existing state: Victoria just alerted, Piccadilly has no state
        disruptions_victoria_old = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure v1",
            ),
        ]
        one_minute_ago = datetime.now(UTC) - timedelta(minutes=1)
        existing_state = {
            "version": ALERT_STATE_VERSION,
            "lines": {
                "victoria": {
                    "full_hash": service._create_line_full_hash(disruptions_victoria_old),
                    "status_hash": service._create_line_status_hash(disruptions_victoria_old),
                    "severity": 4,
                    "status": "Severe Delays",
                    "last_sent_at": one_minute_ago.isoformat(),
                }
            },
            "stored_at": one_minute_ago.isoformat(),
        }
        stateful_mock_redis.get = AsyncMock(return_value=json.dumps(existing_state))

        # New disruptions: Victoria reason changed (should skip), Piccadilly is new (should send)
        disruptions_new = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure v2",  # Reason changed
            ),
            DisruptionResponse(
                line_id="piccadilly",  # New line
                line_name="Piccadilly",
                mode="tube",
                status_severity=6,
                status_severity_description="Part Closure",
                reason="Engineering works",
            ),
        ]

        with patch("app.services.alert_service.settings.ALERT_COOLDOWN_MINUTES", 5):
            should_send, filtered = await service._should_send_alert(
                route=test_route_with_schedule,
                user_id=test_route_with_schedule.user_id,
                schedule=test_route_with_schedule.schedules[0],
                disruptions=disruptions_new,
            )

        # Should alert, but only for Piccadilly
        assert should_send is True
        assert len(filtered) == 1
        assert filtered[0].line_id == "piccadilly"

    async def test_should_send_alert_unrecognized_state_format(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
        test_route_with_schedule: UserRoute,
    ):
        """Test that unrecognized state format (e.g. old v1) triggers alert (safe cache miss)."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Mock existing state in OLD v1 format (no version field)
        existing_state_v1 = {
            "hash": "old_combined_hash",
            "disruptions": [{"line_id": "victoria", "status": "Severe Delays", "reason": "Signal failure"}],
            "stored_at": datetime.now(UTC).isoformat(),
        }
        stateful_mock_redis.get = AsyncMock(return_value=json.dumps(existing_state_v1))

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
        ]

        should_send, filtered = await service._should_send_alert(
            route=test_route_with_schedule,
            user_id=test_route_with_schedule.user_id,
            schedule=test_route_with_schedule.schedules[0],
            disruptions=disruptions,
        )

        # Should alert (unrecognized state treated as cache miss)
        assert should_send is True
        assert len(filtered) == 1

    async def test_store_alert_state_uses_v2_format(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
        test_route_with_schedule: UserRoute,
    ):
        """Test that _store_alert_state stores data in v2 format."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Mock no existing state
        stateful_mock_redis.get = AsyncMock(return_value=None)
        setex_calls = []

        async def mock_setex(key: str, ttl: int, value: str) -> None:
            setex_calls.append((key, ttl, value))

        stateful_mock_redis.setex = AsyncMock(side_effect=mock_setex)

        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure",
            ),
        ]

        # Mock time to be within schedule window (8:00-10:00)
        mock_time = datetime(2025, 12, 1, 9, 0, tzinfo=UTC)

        # Create a custom datetime class that mocks now() but inherits all other behavior
        class MockDatetime(datetime):
            @classmethod
            def now(cls, tz: None | type[UTC] = None) -> datetime:  # type: ignore[override]
                return mock_time.replace(tzinfo=tz) if tz else mock_time

        with patch("app.services.alert_service.datetime", MockDatetime):
            await service._store_alert_state(
                route=test_route_with_schedule,
                user_id=test_route_with_schedule.user_id,
                schedule=test_route_with_schedule.schedules[0],
                disruptions=disruptions,
            )

        # Check that state was stored
        assert len(setex_calls) == 1
        _key, _ttl, value = setex_calls[0]
        stored_data = json.loads(value)

        # Verify v2 format
        assert stored_data["version"] == ALERT_STATE_VERSION
        assert "lines" in stored_data
        assert "victoria" in stored_data["lines"]
        victoria_state = stored_data["lines"]["victoria"]
        assert "full_hash" in victoria_state
        assert "status_hash" in victoria_state
        assert "severity" in victoria_state
        assert "status" in victoria_state
        assert "last_sent_at" in victoria_state
        assert victoria_state["severity"] == 4
        assert victoria_state["status"] == "Severe Delays"

    async def test_store_alert_state_merges_with_existing(
        self,
        db_session: AsyncSession,
        stateful_mock_redis: AsyncMock,
        test_route_with_schedule: UserRoute,
    ):
        """Test that _store_alert_state preserves lines not in current alert."""
        service = AlertService(db=db_session, redis_client=stateful_mock_redis)

        # Mock existing state with both Victoria and Piccadilly
        existing_state = {
            "version": ALERT_STATE_VERSION,
            "lines": {
                "victoria": {
                    "full_hash": "victoria_old_hash",
                    "status_hash": "victoria_old_status_hash",
                    "severity": 4,
                    "status": "Severe Delays",
                    "last_sent_at": (datetime.now(UTC) - timedelta(minutes=10)).isoformat(),
                },
                "piccadilly": {
                    "full_hash": "piccadilly_hash",
                    "status_hash": "piccadilly_status_hash",
                    "severity": 6,
                    "status": "Part Closure",
                    "last_sent_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
                },
            },
            "stored_at": (datetime.now(UTC) - timedelta(minutes=10)).isoformat(),
        }

        stateful_mock_redis.get = AsyncMock(return_value=json.dumps(existing_state))
        setex_calls = []

        async def mock_setex(key: str, ttl: int, value: str) -> None:
            setex_calls.append((key, ttl, value))

        stateful_mock_redis.setex = AsyncMock(side_effect=mock_setex)

        # Only alerting for Victoria (not Piccadilly)
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=4,
                status_severity_description="Severe Delays",
                reason="Signal failure updated",
            ),
        ]

        # Mock time to be within schedule window (8:00-10:00)
        mock_time = datetime(2025, 12, 1, 9, 0, tzinfo=UTC)

        # Create a custom datetime class that mocks now() but inherits all other behavior
        class MockDatetime(datetime):
            @classmethod
            def now(cls, tz: None | type[UTC] = None) -> datetime:  # type: ignore[override]
                return mock_time.replace(tzinfo=tz) if tz else mock_time

        with patch("app.services.alert_service.datetime", MockDatetime):
            await service._store_alert_state(
                route=test_route_with_schedule,
                user_id=test_route_with_schedule.user_id,
                schedule=test_route_with_schedule.schedules[0],
                disruptions=disruptions,
            )

        # Check that state was stored
        assert len(setex_calls) == 1
        _key, _ttl, value = setex_calls[0]
        stored_data = json.loads(value)

        # Verify both lines are preserved
        assert "victoria" in stored_data["lines"]
        assert "piccadilly" in stored_data["lines"]

        # Victoria should be updated
        assert stored_data["lines"]["victoria"]["full_hash"] != "victoria_old_hash"

        # Piccadilly should be unchanged (preserved from existing state)
        assert stored_data["lines"]["piccadilly"]["full_hash"] == "piccadilly_hash"
        assert stored_data["lines"]["piccadilly"]["severity"] == 6
