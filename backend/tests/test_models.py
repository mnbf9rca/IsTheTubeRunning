"""Tests for database models."""

from datetime import UTC, datetime, time, timedelta
from typing import Any

import pytest
from app.models import (
    AdminRole,
    AdminUser,
    EmailAddress,
    Line,
    NotificationLog,
    NotificationMethod,
    NotificationPreference,
    NotificationStatus,
    PhoneNumber,
    RouteStationIndex,
    Station,
    StationConnection,
    User,
    UserRoute,
    UserRouteSchedule,
    UserRouteSegment,
    VerificationCode,
    VerificationType,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.test_data import make_unique_email, make_unique_external_id, make_unique_phone


class TestUserModel:
    """Tests for User model and related models."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession) -> None:
        """Test creating a user."""
        external_id = make_unique_external_id()
        user = User(external_id=external_id, auth_provider="auth0")
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(
            select(User).where(User.external_id == external_id).where(User.auth_provider == "auth0")
        )
        saved_user = result.scalar_one()

        assert saved_user.id is not None
        assert saved_user.external_id == external_id
        assert saved_user.auth_provider == "auth0"
        assert saved_user.created_at is not None
        assert saved_user.updated_at is not None
        assert saved_user.deleted_at is None
        assert not saved_user.is_deleted

    @pytest.mark.asyncio
    async def test_user_soft_delete(self, db_session: AsyncSession) -> None:
        """Test soft delete functionality."""
        external_id = make_unique_external_id("auth0|softdelete")
        user = User(external_id=external_id, auth_provider="auth0")
        db_session.add(user)
        await db_session.commit()

        # Soft delete
        user.deleted_at = datetime.now(UTC)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.id == user.id))
        deleted_user = result.scalar_one()

        assert deleted_user.deleted_at is not None
        assert deleted_user.is_deleted

    @pytest.mark.asyncio
    async def test_email_address_relationship(self, db_session: AsyncSession) -> None:
        """Test user-email relationship."""
        external_id = make_unique_external_id("auth0|email_test")
        email_addr = make_unique_email()
        user = User(external_id=external_id, auth_provider="auth0")
        email = EmailAddress(user=user, email=email_addr, verified=True, is_primary=True)

        db_session.add(user)
        db_session.add(email)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.id == user.id))
        saved_user = result.scalar_one()
        await db_session.refresh(saved_user, ["email_addresses"])

        assert len(saved_user.email_addresses) == 1
        assert saved_user.email_addresses[0].email == email_addr
        assert saved_user.email_addresses[0].verified
        assert saved_user.email_addresses[0].is_primary

    @pytest.mark.asyncio
    async def test_phone_number_relationship(self, db_session: AsyncSession) -> None:
        """Test user-phone relationship."""
        external_id = make_unique_external_id("auth0|phone_test")
        phone_num = make_unique_phone()
        user = User(external_id=external_id, auth_provider="auth0")
        phone = PhoneNumber(user=user, phone=phone_num, verified=False, is_primary=True)

        db_session.add(user)
        db_session.add(phone)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.id == user.id))
        saved_user = result.scalar_one()
        await db_session.refresh(saved_user, ["phone_numbers"])

        assert len(saved_user.phone_numbers) == 1
        assert saved_user.phone_numbers[0].phone == phone_num
        assert not saved_user.phone_numbers[0].verified

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("model_class", "field_name"),
        [
            pytest.param(EmailAddress, "email", id="email"),
            pytest.param(PhoneNumber, "phone", id="phone"),
        ],
    )
    async def test_duplicate_user_contact_raises_error(
        self, db_session: AsyncSession, model_class: type, field_name: str
    ) -> None:
        """Test that duplicate emails/phones raise integrity error."""
        # Generate unique value for this test based on field type
        field_value = make_unique_email() if field_name == "email" else make_unique_phone()

        user1 = User(external_id=make_unique_external_id("auth0|user1"), auth_provider="auth0")
        user2 = User(external_id=make_unique_external_id("auth0|user2"), auth_provider="auth0")

        contact1_kwargs = {"user": user1, field_name: field_value, "verified": True, "is_primary": True}
        contact1 = model_class(**contact1_kwargs)

        db_session.add(user1)
        db_session.add(contact1)
        await db_session.commit()

        contact2_kwargs = {"user": user2, field_name: field_value, "verified": True, "is_primary": True}
        contact2 = model_class(**contact2_kwargs)
        db_session.add(user2)
        db_session.add(contact2)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestVerificationCode:
    """Tests for VerificationCode model."""

    @pytest.mark.asyncio
    async def test_verification_code_expiry(self, db_session: AsyncSession) -> None:
        """Test verification code expiry logic."""
        user = User(external_id=make_unique_external_id("auth0|verification"), auth_provider="auth0")
        email = EmailAddress(user=user, email=make_unique_email(), verified=False)

        db_session.add(user)
        db_session.add(email)
        await db_session.flush()  # Flush to assign IDs

        expired_code = VerificationCode(
            user=user,
            contact_id=email.id,
            code="123456",
            type=VerificationType.EMAIL,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
            used=False,
        )

        db_session.add(expired_code)
        await db_session.commit()

        assert expired_code.is_expired
        assert not expired_code.is_valid

    @pytest.mark.asyncio
    async def test_verification_code_valid(self, db_session: AsyncSession) -> None:
        """Test valid verification code."""
        user = User(external_id=make_unique_external_id("auth0|valid_code"), auth_provider="auth0")
        phone = PhoneNumber(user=user, phone=make_unique_phone(), verified=False)

        db_session.add(user)
        db_session.add(phone)
        await db_session.flush()  # Flush to assign IDs

        valid_code = VerificationCode(
            user=user,
            contact_id=phone.id,
            code="654321",
            type=VerificationType.SMS,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            used=False,
        )

        db_session.add(valid_code)
        await db_session.commit()

        assert not valid_code.is_expired
        assert valid_code.is_valid

    @pytest.mark.asyncio
    async def test_verification_code_used(self, db_session: AsyncSession) -> None:
        """Test used verification code."""
        user = User(external_id=make_unique_external_id("auth0|used_code"), auth_provider="auth0")
        email = EmailAddress(user=user, email=make_unique_email(), verified=False)

        db_session.add(user)
        db_session.add(email)
        await db_session.flush()  # Flush to assign IDs

        used_code = VerificationCode(
            user=user,
            contact_id=email.id,
            code="999999",
            type=VerificationType.EMAIL,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            used=True,
        )

        db_session.add(used_code)
        await db_session.commit()

        assert not used_code.is_valid


class TestTfLModels:
    """Tests for TfL data models."""

    @pytest.mark.asyncio
    async def test_create_line(self, db_session: AsyncSession) -> None:
        """Test creating a TfL line."""
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            last_updated=datetime.now(UTC),
        )

        db_session.add(line)
        await db_session.commit()

        result = await db_session.execute(select(Line).where(Line.tfl_id == "victoria"))
        saved_line = result.scalar_one()

        assert saved_line.name == "Victoria Line"

    @pytest.mark.asyncio
    async def test_create_station(self, db_session: AsyncSession) -> None:
        """Test creating a TfL station."""
        station = Station(
            tfl_id="940GZZLUVXL",
            name="Vauxhall",
            latitude=51.486,
            longitude=-0.125,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )

        db_session.add(station)
        await db_session.commit()

        result = await db_session.execute(select(Station).where(Station.tfl_id == "940GZZLUVXL"))
        saved_station = result.scalar_one()

        assert saved_station.name == "Vauxhall"
        assert "victoria" in saved_station.lines

    @pytest.mark.asyncio
    async def test_create_station_with_hub_fields(self, db_session: AsyncSession) -> None:
        """Test creating a TfL station with hub NaPTAN code fields."""
        station = Station(
            tfl_id="910GSEVNSIS",
            name="Seven Sisters Rail",
            latitude=51.5823,
            longitude=-0.0751,
            lines=["weaver"],
            last_updated=datetime.now(UTC),
            hub_naptan_code="HUBSVS",
            hub_common_name="Seven Sisters",
        )

        db_session.add(station)
        await db_session.commit()

        result = await db_session.execute(select(Station).where(Station.tfl_id == "910GSEVNSIS"))
        saved_station = result.scalar_one()

        assert saved_station.name == "Seven Sisters Rail"
        assert saved_station.hub_naptan_code == "HUBSVS"
        assert saved_station.hub_common_name == "Seven Sisters"

    @pytest.mark.asyncio
    async def test_create_station_without_hub_fields(self, db_session: AsyncSession) -> None:
        """Test creating a TfL station without hub fields (nullable)."""
        station = Station(
            tfl_id="940GZZLUWBN",
            name="Wimbledon",
            latitude=51.4214,
            longitude=-0.2064,
            lines=["district"],
            last_updated=datetime.now(UTC),
            # hub_naptan_code and hub_common_name are None (not all stations are hubs)
        )

        db_session.add(station)
        await db_session.commit()

        result = await db_session.execute(select(Station).where(Station.tfl_id == "940GZZLUWBN"))
        saved_station = result.scalar_one()

        assert saved_station.name == "Wimbledon"
        assert saved_station.hub_naptan_code is None
        assert saved_station.hub_common_name is None

    @pytest.mark.asyncio
    async def test_station_connection(self, db_session: AsyncSession) -> None:
        """Test station connection graph."""
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            last_updated=datetime.now(UTC),
        )
        station1 = Station(
            tfl_id="940GZZLUVXL",
            name="Vauxhall",
            latitude=51.486,
            longitude=-0.125,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            tfl_id="940GZZLUPCO",
            name="Pimlico",
            latitude=51.489,
            longitude=-0.133,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )

        connection = StationConnection(from_station=station1, to_station=station2, line=line)

        db_session.add_all([line, station1, station2, connection])
        await db_session.commit()

        result = await db_session.execute(select(StationConnection))
        saved_connection = result.scalar_one()

        assert saved_connection.from_station_id == station1.id
        assert saved_connection.to_station_id == station2.id
        assert saved_connection.line_id == line.id

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("model_class", "tfl_id", "extra_kwargs"),
        [
            pytest.param(
                Station, "940GZZLUVXL", {"latitude": 51.486, "longitude": -0.125, "lines": ["victoria"]}, id="station"
            ),
            pytest.param(Line, "victoria", {}, id="line"),
        ],
    )
    async def test_duplicate_tfl_id_raises_error(
        self, db_session: AsyncSession, model_class: type, tfl_id: str, extra_kwargs: dict[str, Any]
    ) -> None:
        """Test that duplicate tfl_id raises integrity error for stations and lines."""
        entity1 = model_class(
            tfl_id=tfl_id,
            name="First Entity",
            last_updated=datetime.now(UTC),
            **extra_kwargs,
        )
        db_session.add(entity1)
        await db_session.commit()

        entity2 = model_class(
            tfl_id=tfl_id,
            name="Duplicate Entity",
            last_updated=datetime.now(UTC),
            **extra_kwargs,
        )
        db_session.add(entity2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_duplicate_station_connection_raises_error(self, db_session: AsyncSession) -> None:
        """Test that duplicate station connections raise integrity error."""
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            last_updated=datetime.now(UTC),
        )
        station1 = Station(
            tfl_id="940GZZLUVXL",
            name="Vauxhall",
            latitude=51.486,
            longitude=-0.125,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            tfl_id="940GZZLUPCO",
            name="Pimlico",
            latitude=51.489,
            longitude=-0.133,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )

        connection1 = StationConnection(from_station=station1, to_station=station2, line=line)
        db_session.add_all([line, station1, station2, connection1])
        await db_session.commit()

        connection2 = StationConnection(from_station=station1, to_station=station2, line=line)
        db_session.add(connection2)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestRouteModels:
    """Tests for route models."""

    @pytest.mark.asyncio
    async def test_create_route_with_segments(self, db_session: AsyncSession) -> None:
        """Test creating a route with segments."""
        user = User(external_id=make_unique_external_id("auth0|route_test"), auth_provider="auth0")
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            last_updated=datetime.now(UTC),
        )
        station1 = Station(
            tfl_id="940GZZLUVXL",
            name="Vauxhall",
            latitude=51.486,
            longitude=-0.125,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            tfl_id="940GZZLUPCO",
            name="Pimlico",
            latitude=51.489,
            longitude=-0.133,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )

        db_session.add_all([user, line, station1, station2])
        await db_session.flush()  # Flush to get IDs

        route = UserRoute(user=user, name="Morning Commute", active=True)
        segment1 = UserRouteSegment(route=route, sequence=0, station_id=station1.id, line_id=line.id)
        segment2 = UserRouteSegment(route=route, sequence=1, station_id=station2.id, line_id=line.id)

        db_session.add_all([route, segment1, segment2])
        await db_session.commit()

        result = await db_session.execute(select(UserRoute).where(UserRoute.id == route.id))
        saved_route = result.scalar_one()
        await db_session.refresh(saved_route, ["segments"])

        assert saved_route.name == "Morning Commute"
        assert saved_route.active
        assert len(saved_route.segments) == 2
        assert saved_route.segments[0].sequence == 0
        assert saved_route.segments[1].sequence == 1

    @pytest.mark.asyncio
    async def test_route_schedule(self, db_session: AsyncSession) -> None:
        """Test route schedule."""
        user = User(external_id=make_unique_external_id("auth0|schedule_test"), auth_provider="auth0")
        route = UserRoute(user=user, name="Test Route", active=True)
        schedule = UserRouteSchedule(
            route=route,
            days_of_week=["MON", "TUE", "WED", "THU", "FRI"],
            start_time=time(8, 0),
            end_time=time(9, 30),
        )

        db_session.add_all([user, route, schedule])
        await db_session.commit()

        result = await db_session.execute(select(UserRouteSchedule).where(UserRouteSchedule.route_id == route.id))
        saved_schedule = result.scalar_one()

        assert saved_schedule.days_of_week == ["MON", "TUE", "WED", "THU", "FRI"]
        assert saved_schedule.start_time == time(8, 0)
        assert saved_schedule.end_time == time(9, 30)

    @pytest.mark.asyncio
    async def test_duplicate_route_segment_sequence_raises_error(self, db_session: AsyncSession) -> None:
        """Test that duplicate route segment sequence numbers raise integrity error."""
        user = User(external_id=make_unique_external_id("auth0|segment_test"), auth_provider="auth0")
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            last_updated=datetime.now(UTC),
        )
        station1 = Station(
            tfl_id="940GZZLUVXL",
            name="Vauxhall",
            latitude=51.486,
            longitude=-0.125,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            tfl_id="940GZZLUPCO",
            name="Pimlico",
            latitude=51.489,
            longitude=-0.133,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )

        db_session.add_all([user, line, station1, station2])
        await db_session.flush()

        route = UserRoute(user=user, name="Test Route", active=True)
        segment1 = UserRouteSegment(route=route, sequence=0, station_id=station1.id, line_id=line.id)
        segment2 = UserRouteSegment(route=route, sequence=0, station_id=station2.id, line_id=line.id)

        db_session.add_all([route, segment1, segment2])

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_route_segment_line_tfl_id_with_line(self, db_session: AsyncSession) -> None:
        """Test that line_tfl_id property returns the line's TfL ID when line exists."""
        user = User(external_id=make_unique_external_id("auth0|line_tfl_id_test"), auth_provider="auth0")
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            last_updated=datetime.now(UTC),
        )
        station = Station(
            tfl_id="940GZZLUVXL",
            name="Vauxhall",
            latitude=51.486,
            longitude=-0.125,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )

        db_session.add_all([user, line, station])
        await db_session.flush()

        route = UserRoute(user=user, name="Test Route", active=True)
        segment = UserRouteSegment(route=route, sequence=0, station_id=station.id, line_id=line.id)

        db_session.add_all([route, segment])
        await db_session.commit()
        await db_session.refresh(segment, attribute_names=["station", "line"])

        # Test the property returns the line's TfL ID
        assert segment.line_tfl_id == "victoria"
        assert segment.station_tfl_id == "940GZZLUVXL"

    @pytest.mark.asyncio
    async def test_route_segment_line_tfl_id_with_null_line(self, db_session: AsyncSession) -> None:
        """Test that line_tfl_id property returns None when line_id is NULL (destination segment).

        This is the critical test for issue #36 - ensures no AttributeError is raised
        when accessing line_tfl_id on a segment with NULL line_id.
        """
        user = User(external_id=make_unique_external_id("auth0|null_line_test"), auth_provider="auth0")
        station = Station(
            tfl_id="940GZZLUVXL",
            name="Vauxhall",
            latitude=51.486,
            longitude=-0.125,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )

        db_session.add_all([user, station])
        await db_session.flush()

        route = UserRoute(user=user, name="Test Route", active=True)
        # Create a destination segment with NULL line_id
        segment = UserRouteSegment(route=route, sequence=1, station_id=station.id, line_id=None)

        db_session.add_all([route, segment])
        await db_session.commit()
        await db_session.refresh(segment, attribute_names=["station", "line"])

        # This should NOT raise AttributeError (issue #36)
        assert segment.line_tfl_id is None
        assert segment.line is None
        assert segment.station_tfl_id == "940GZZLUVXL"

    @pytest.mark.asyncio
    async def test_route_with_mixed_segments_null_and_non_null_lines(self, db_session: AsyncSession) -> None:
        """Test a route with both regular segments (with lines) and a destination segment (without line)."""
        user = User(external_id=make_unique_external_id("auth0|mixed_segments"), auth_provider="auth0")
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            last_updated=datetime.now(UTC),
        )
        station1 = Station(
            tfl_id="940GZZLUVXL",
            name="Vauxhall",
            latitude=51.486,
            longitude=-0.125,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            tfl_id="940GZZLUPCO",
            name="Pimlico",
            latitude=51.489,
            longitude=-0.133,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )

        db_session.add_all([user, line, station1, station2])
        await db_session.flush()

        route = UserRoute(user=user, name="Mixed Segments Route", active=True)
        # Segment 0: Has a line (travel from Vauxhall on Victoria line)
        segment_0 = UserRouteSegment(route=route, sequence=0, station_id=station1.id, line_id=line.id)
        # Segment 1: Destination (arrive at Pimlico, no outgoing line)
        segment_1 = UserRouteSegment(route=route, sequence=1, station_id=station2.id, line_id=None)

        db_session.add_all([route, segment_0, segment_1])
        await db_session.commit()
        await db_session.refresh(segment_0, attribute_names=["station", "line"])
        await db_session.refresh(segment_1, attribute_names=["station", "line"])

        # First segment should have line_tfl_id
        assert segment_0.line_tfl_id == "victoria"
        assert segment_0.station_tfl_id == "940GZZLUVXL"

        # Second segment (destination) should have None for line_tfl_id
        assert segment_1.line_tfl_id is None
        assert segment_1.station_tfl_id == "940GZZLUPCO"


class TestNotificationModels:
    """Tests for notification models."""

    @pytest.mark.asyncio
    async def test_notification_preference(self, db_session: AsyncSession) -> None:
        """Test notification preference."""
        user = User(external_id=make_unique_external_id("auth0|notif_test"), auth_provider="auth0")
        email = EmailAddress(user=user, email=make_unique_email(), verified=True, is_primary=True)
        route = UserRoute(user=user, name="Test Route", active=True)

        db_session.add_all([user, email, route])
        await db_session.flush()  # Flush to get IDs

        preference = NotificationPreference(route=route, method=NotificationMethod.EMAIL, target_email_id=email.id)

        db_session.add(preference)
        await db_session.commit()

        result = await db_session.execute(
            select(NotificationPreference).where(NotificationPreference.route_id == route.id)
        )
        saved_pref = result.scalar_one()

        assert saved_pref.method == NotificationMethod.EMAIL
        assert saved_pref.target_email_id == email.id
        assert saved_pref.target_phone_id is None

    @pytest.mark.asyncio
    async def test_notification_log(self, db_session: AsyncSession) -> None:
        """Test notification log."""
        user = User(external_id=make_unique_external_id("auth0|log_test"), auth_provider="auth0")
        route = UserRoute(user=user, name="Test Route", active=True)
        log = NotificationLog(
            user=user,
            route=route,
            sent_at=datetime.now(UTC),
            method=NotificationMethod.EMAIL,
            status=NotificationStatus.SENT,
        )

        db_session.add_all([user, route, log])
        await db_session.commit()

        result = await db_session.execute(select(NotificationLog).where(NotificationLog.user_id == user.id))
        saved_log = result.scalar_one()

        assert saved_log.method == NotificationMethod.EMAIL
        assert saved_log.status == NotificationStatus.SENT
        assert saved_log.error_message is None

    @pytest.mark.asyncio
    async def test_notification_preference_with_both_targets_raises_error(self, db_session: AsyncSession) -> None:
        """Test that NotificationPreference with both target_email_id and target_phone_id raises error."""
        user = User(external_id=make_unique_external_id("auth0|both_targets"), auth_provider="auth0")
        email = EmailAddress(user=user, email=make_unique_email(), verified=True, is_primary=True)
        phone = PhoneNumber(user=user, phone=make_unique_phone(), verified=True, is_primary=True)
        route = UserRoute(user=user, name="Test Route", active=True)

        db_session.add_all([user, email, phone, route])
        await db_session.flush()

        preference = NotificationPreference(
            route=route,
            method=NotificationMethod.EMAIL,
            target_email_id=email.id,
            target_phone_id=phone.id,
        )

        db_session.add(preference)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestAdminModel:
    """Tests for admin model."""

    @pytest.mark.asyncio
    async def test_create_admin(self, db_session: AsyncSession) -> None:
        """Test creating an admin user."""
        user = User(external_id=make_unique_external_id("auth0|admin_test"), auth_provider="auth0")
        db_session.add(user)
        await db_session.flush()  # Flush to get user.id before creating admin

        admin = AdminUser(
            user_id=user.id,
            role=AdminRole.ADMIN,
            granted_at=datetime.now(UTC),
        )

        db_session.add(admin)
        await db_session.commit()

        result = await db_session.execute(select(AdminUser).where(AdminUser.user_id == user.id))
        saved_admin = result.scalar_one()

        assert saved_admin.role == AdminRole.ADMIN
        assert saved_admin.granted_at is not None

    @pytest.mark.asyncio
    async def test_duplicate_admin_user_raises_error(self, db_session: AsyncSession) -> None:
        """Test that duplicate admin users raise integrity error."""
        user = User(external_id=make_unique_external_id("auth0|dup_admin"), auth_provider="auth0")
        db_session.add(user)
        await db_session.flush()

        admin1 = AdminUser(
            user_id=user.id,
            role=AdminRole.ADMIN,
            granted_at=datetime.now(UTC),
        )
        db_session.add(admin1)
        await db_session.commit()

        admin2 = AdminUser(
            user_id=user.id,
            role=AdminRole.SUPERADMIN,
            granted_at=datetime.now(UTC),
        )
        db_session.add(admin2)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestRouteStationIndex:
    """Tests for RouteStationIndex model."""

    @pytest.mark.asyncio
    async def test_create_index_entry(self, db_session: AsyncSession) -> None:
        """Test creating a route station index entry."""
        user = User(external_id=make_unique_external_id("auth0|index_test"), auth_provider="auth0")
        route = UserRoute(user=user, name="Test Route", active=True)

        db_session.add_all([user, route])
        await db_session.commit()

        # Create index entry
        index_entry = RouteStationIndex(
            route_id=route.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLUKSX",
            line_data_version=datetime.now(UTC),
        )
        db_session.add(index_entry)
        await db_session.commit()

        # Verify entry was saved
        result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        saved_entry = result.scalar_one()

        assert saved_entry.id is not None
        assert saved_entry.route_id == route.id
        assert saved_entry.line_tfl_id == "piccadilly"
        assert saved_entry.station_naptan == "940GZZLUKSX"
        assert saved_entry.line_data_version is not None
        assert saved_entry.created_at is not None
        assert saved_entry.updated_at is not None
        assert saved_entry.deleted_at is None

    @pytest.mark.asyncio
    async def test_multiple_entries_same_station(self, db_session: AsyncSession) -> None:
        """Test that multiple routes can have entries for the same (line, station) combination."""
        user = User(external_id=make_unique_external_id("auth0|multi_routes"), auth_provider="auth0")
        route1 = UserRoute(user=user, name="Route 1", active=True)
        route2 = UserRoute(user=user, name="Route 2", active=True)

        db_session.add_all([user, route1, route2])
        await db_session.commit()

        version = datetime.now(UTC)

        # Create index entries for both routes for the same station
        entry1 = RouteStationIndex(
            route_id=route1.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLUKSX",
            line_data_version=version,
        )
        entry2 = RouteStationIndex(
            route_id=route2.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLUKSX",
            line_data_version=version,
        )

        db_session.add_all([entry1, entry2])
        await db_session.commit()

        # Verify both entries exist
        result = await db_session.execute(
            select(RouteStationIndex).where(
                RouteStationIndex.line_tfl_id == "piccadilly",
                RouteStationIndex.station_naptan == "940GZZLUKSX",
            )
        )
        entries = result.scalars().all()

        assert len(entries) == 2
        route_ids = {entry.route_id for entry in entries}
        assert route_ids == {route1.id, route2.id}

    @pytest.mark.asyncio
    async def test_cascade_delete_on_route_deletion(self, db_session: AsyncSession) -> None:
        """Test that index entries are deleted when the route is deleted."""
        user = User(external_id=make_unique_external_id("auth0|cascade_test"), auth_provider="auth0")
        route = UserRoute(user=user, name="Test Route", active=True)

        db_session.add_all([user, route])
        await db_session.commit()

        # Create multiple index entries for this route
        version = datetime.now(UTC)
        entry1 = RouteStationIndex(
            route_id=route.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLUKSX",
            line_data_version=version,
        )
        entry2 = RouteStationIndex(
            route_id=route.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLURSQ",
            line_data_version=version,
        )

        db_session.add_all([entry1, entry2])
        await db_session.commit()

        # Verify entries exist
        result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        entries_before = result.scalars().all()
        assert len(entries_before) == 2

        # Delete the route
        await db_session.delete(route)
        await db_session.commit()

        # Verify all index entries were CASCADE deleted
        result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        entries_after = result.scalars().all()
        assert len(entries_after) == 0

    @pytest.mark.asyncio
    async def test_index_relationship(self, db_session: AsyncSession) -> None:
        """Test the relationship between RouteStationIndex and UserRoute."""
        user = User(external_id=make_unique_external_id("auth0|relationship_test"), auth_provider="auth0")
        route = UserRoute(user=user, name="Test Route", active=True)

        db_session.add_all([user, route])
        await db_session.commit()

        # Create index entry
        index_entry = RouteStationIndex(
            route_id=route.id,
            line_tfl_id="victoria",
            station_naptan="940GZZLUVXL",
            line_data_version=datetime.now(UTC),
        )
        db_session.add(index_entry)
        await db_session.commit()

        # Test relationship access
        await db_session.refresh(index_entry, ["route"])
        assert index_entry.route is not None
        assert index_entry.route.id == route.id
        assert index_entry.route.name == "Test Route"

    @pytest.mark.asyncio
    async def test_index_query_by_line_and_station(self, db_session: AsyncSession) -> None:
        """Test querying index by line and station (the primary use case)."""
        user = User(external_id=make_unique_external_id("auth0|query_test"), auth_provider="auth0")
        route1 = UserRoute(user=user, name="Route 1", active=True)
        route2 = UserRoute(user=user, name="Route 2", active=True)
        route3 = UserRoute(user=user, name="Route 3", active=True)

        db_session.add_all([user, route1, route2, route3])
        await db_session.commit()

        version = datetime.now(UTC)

        # Create index entries for different routes and stations
        entries = [
            RouteStationIndex(
                route_id=route1.id, line_tfl_id="piccadilly", station_naptan="940GZZLUKSX", line_data_version=version
            ),
            RouteStationIndex(
                route_id=route1.id, line_tfl_id="piccadilly", station_naptan="940GZZLURSQ", line_data_version=version
            ),
            RouteStationIndex(
                route_id=route2.id, line_tfl_id="piccadilly", station_naptan="940GZZLUKSX", line_data_version=version
            ),
            RouteStationIndex(
                route_id=route3.id, line_tfl_id="victoria", station_naptan="940GZZLUVXL", line_data_version=version
            ),
        ]

        db_session.add_all(entries)
        await db_session.commit()

        # Query: Which routes pass through King's Cross (940GZZLUKSX) on Piccadilly line?
        result = await db_session.execute(
            select(RouteStationIndex).where(
                RouteStationIndex.line_tfl_id == "piccadilly",
                RouteStationIndex.station_naptan == "940GZZLUKSX",
            )
        )
        matching_entries = result.scalars().all()

        # Should match route1 and route2 (both pass through this station)
        assert len(matching_entries) == 2
        matching_route_ids = {entry.route_id for entry in matching_entries}
        assert matching_route_ids == {route1.id, route2.id}

    @pytest.mark.asyncio
    async def test_index_staleness_query(self, db_session: AsyncSession) -> None:
        """Test querying for stale index entries by line_data_version."""
        user = User(external_id=make_unique_external_id("auth0|staleness_test"), auth_provider="auth0")
        route1 = UserRoute(user=user, name="Route 1", active=True)
        route2 = UserRoute(user=user, name="Route 2", active=True)

        db_session.add_all([user, route1, route2])
        await db_session.commit()

        # Create entries with different line_data_version values
        old_version = datetime.now(UTC) - timedelta(days=7)
        new_version = datetime.now(UTC)

        entry1 = RouteStationIndex(
            route_id=route1.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLUKSX",
            line_data_version=old_version,
        )
        entry2 = RouteStationIndex(
            route_id=route2.id,
            line_tfl_id="piccadilly",
            station_naptan="940GZZLURSQ",
            line_data_version=new_version,
        )

        db_session.add_all([entry1, entry2])
        await db_session.commit()

        # Query for entries older than 1 day
        cutoff = datetime.now(UTC) - timedelta(days=1)
        result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.line_data_version < cutoff))
        stale_entries = result.scalars().all()

        # Should only find entry1 (old_version)
        assert len(stale_entries) == 1
        assert stale_entries[0].route_id == route1.id
