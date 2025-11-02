"""Tests for database models."""

from datetime import UTC, datetime, time, timedelta

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
    Route,
    RouteSchedule,
    RouteSegment,
    Station,
    StationConnection,
    User,
    VerificationCode,
    VerificationType,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class TestUserModel:
    """Tests for User model and related models."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession) -> None:
        """Test creating a user."""
        user = User(auth0_id="auth0|12345")
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.auth0_id == "auth0|12345"))
        saved_user = result.scalar_one()

        assert saved_user.id is not None
        assert saved_user.auth0_id == "auth0|12345"
        assert saved_user.created_at is not None
        assert saved_user.updated_at is not None
        assert saved_user.deleted_at is None
        assert not saved_user.is_deleted

    @pytest.mark.asyncio
    async def test_user_soft_delete(self, db_session: AsyncSession) -> None:
        """Test soft delete functionality."""
        user = User(auth0_id="auth0|softdelete")
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
        user = User(auth0_id="auth0|email_test")
        email = EmailAddress(user=user, email="test@example.com", verified=True, is_primary=True)

        db_session.add(user)
        db_session.add(email)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.id == user.id))
        saved_user = result.scalar_one()
        await db_session.refresh(saved_user, ["email_addresses"])

        assert len(saved_user.email_addresses) == 1
        assert saved_user.email_addresses[0].email == "test@example.com"
        assert saved_user.email_addresses[0].verified
        assert saved_user.email_addresses[0].is_primary

    @pytest.mark.asyncio
    async def test_phone_number_relationship(self, db_session: AsyncSession) -> None:
        """Test user-phone relationship."""
        user = User(auth0_id="auth0|phone_test")
        phone = PhoneNumber(user=user, phone="+447700900000", verified=False, is_primary=True)

        db_session.add(user)
        db_session.add(phone)
        await db_session.commit()

        result = await db_session.execute(select(User).where(User.id == user.id))
        saved_user = result.scalar_one()
        await db_session.refresh(saved_user, ["phone_numbers"])

        assert len(saved_user.phone_numbers) == 1
        assert saved_user.phone_numbers[0].phone == "+447700900000"
        assert not saved_user.phone_numbers[0].verified

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("model_class", "field_name", "field_value"),
        [
            pytest.param(EmailAddress, "email", "duplicate@example.com", id="email"),
            pytest.param(PhoneNumber, "phone", "+447700900000", id="phone"),
        ],
    )
    async def test_duplicate_user_contact_raises_error(
        self, db_session: AsyncSession, model_class: type, field_name: str, field_value: str
    ) -> None:
        """Test that duplicate emails/phones raise integrity error."""
        user1 = User(auth0_id="auth0|user1")
        user2 = User(auth0_id="auth0|user2")

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
        user = User(auth0_id="auth0|verification")
        expired_code = VerificationCode(
            user=user,
            code="123456",
            type=VerificationType.EMAIL,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
            used=False,
        )

        db_session.add(user)
        db_session.add(expired_code)
        await db_session.commit()

        assert expired_code.is_expired
        assert not expired_code.is_valid

    @pytest.mark.asyncio
    async def test_verification_code_valid(self, db_session: AsyncSession) -> None:
        """Test valid verification code."""
        user = User(auth0_id="auth0|valid_code")
        valid_code = VerificationCode(
            user=user,
            code="654321",
            type=VerificationType.SMS,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            used=False,
        )

        db_session.add(user)
        db_session.add(valid_code)
        await db_session.commit()

        assert not valid_code.is_expired
        assert valid_code.is_valid

    @pytest.mark.asyncio
    async def test_verification_code_used(self, db_session: AsyncSession) -> None:
        """Test used verification code."""
        user = User(auth0_id="auth0|used_code")
        used_code = VerificationCode(
            user=user,
            code="999999",
            type=VerificationType.EMAIL,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            used=True,
        )

        db_session.add(user)
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
            color="#0019A8",
            last_updated=datetime.now(UTC),
        )

        db_session.add(line)
        await db_session.commit()

        result = await db_session.execute(select(Line).where(Line.tfl_id == "victoria"))
        saved_line = result.scalar_one()

        assert saved_line.name == "Victoria Line"
        assert saved_line.color == "#0019A8"

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
    async def test_station_connection(self, db_session: AsyncSession) -> None:
        """Test station connection graph."""
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            color="#0019A8",
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
            pytest.param(Line, "victoria", {"color": "#0019A8"}, id="line"),
        ],
    )
    async def test_duplicate_tfl_id_raises_error(
        self, db_session: AsyncSession, model_class: type, tfl_id: str, extra_kwargs: dict
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
            color="#0019A8",
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
        user = User(auth0_id="auth0|route_test")
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            color="#0019A8",
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

        route = Route(user=user, name="Morning Commute", active=True)
        segment1 = RouteSegment(route=route, sequence=0, station_id=station1.id, line_id=line.id)
        segment2 = RouteSegment(route=route, sequence=1, station_id=station2.id, line_id=line.id)

        db_session.add_all([route, segment1, segment2])
        await db_session.commit()

        result = await db_session.execute(select(Route).where(Route.id == route.id))
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
        user = User(auth0_id="auth0|schedule_test")
        route = Route(user=user, name="Test Route", active=True)
        schedule = RouteSchedule(
            route=route,
            days_of_week=["MON", "TUE", "WED", "THU", "FRI"],
            start_time=time(8, 0),
            end_time=time(9, 30),
        )

        db_session.add_all([user, route, schedule])
        await db_session.commit()

        result = await db_session.execute(select(RouteSchedule).where(RouteSchedule.route_id == route.id))
        saved_schedule = result.scalar_one()

        assert saved_schedule.days_of_week == ["MON", "TUE", "WED", "THU", "FRI"]
        assert saved_schedule.start_time == time(8, 0)
        assert saved_schedule.end_time == time(9, 30)

    @pytest.mark.asyncio
    async def test_duplicate_route_segment_sequence_raises_error(self, db_session: AsyncSession) -> None:
        """Test that duplicate route segment sequence numbers raise integrity error."""
        user = User(auth0_id="auth0|segment_test")
        line = Line(
            tfl_id="victoria",
            name="Victoria Line",
            color="#0019A8",
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

        route = Route(user=user, name="Test Route", active=True)
        segment1 = RouteSegment(route=route, sequence=0, station_id=station1.id, line_id=line.id)
        segment2 = RouteSegment(route=route, sequence=0, station_id=station2.id, line_id=line.id)

        db_session.add_all([route, segment1, segment2])

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestNotificationModels:
    """Tests for notification models."""

    @pytest.mark.asyncio
    async def test_notification_preference(self, db_session: AsyncSession) -> None:
        """Test notification preference."""
        user = User(auth0_id="auth0|notif_test")
        email = EmailAddress(user=user, email="notif@example.com", verified=True, is_primary=True)
        route = Route(user=user, name="Test Route", active=True)

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
        user = User(auth0_id="auth0|log_test")
        route = Route(user=user, name="Test Route", active=True)
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
        user = User(auth0_id="auth0|both_targets")
        email = EmailAddress(user=user, email="test@example.com", verified=True, is_primary=True)
        phone = PhoneNumber(user=user, phone="+447700900000", verified=True, is_primary=True)
        route = Route(user=user, name="Test Route", active=True)

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
        user = User(auth0_id="auth0|admin_test")
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
        user = User(auth0_id="auth0|dup_admin")
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
