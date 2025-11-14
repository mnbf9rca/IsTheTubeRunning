"""Tests for admin dashboard user management and analytics endpoints."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.notification import (
    NotificationLog,
    NotificationMethod,
    NotificationStatus,
)
from app.models.route import Route
from app.models.user import (
    EmailAddress,
    PhoneNumber,
    User,
    VerificationCode,
    VerificationType,
)
from app.services.admin_service import calculate_avg_routes, calculate_success_rate
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select as sql_select
from sqlalchemy.ext.asyncio import AsyncSession


def build_api_url(endpoint: str) -> str:
    """
    Build full API URL with version prefix.

    Args:
        endpoint: API endpoint path (e.g., '/admin/users')

    Returns:
        Full API URL (e.g., '/api/v1/admin/users')
    """
    prefix = settings.API_V1_PREFIX.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{prefix}{path}"


@pytest.fixture
async def async_client_with_db(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client with database dependency override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


# ==================== Authorization Tests ====================


@pytest.mark.asyncio
async def test_list_users_requires_auth(async_client_with_db: AsyncClient) -> None:
    """Test that list users endpoint requires authentication."""
    response = await async_client_with_db.get(build_api_url("/admin/users"))
    assert response.status_code == 403
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_list_users_requires_admin(
    async_client_with_db: AsyncClient,
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test that list users endpoint requires admin role."""
    response = await async_client_with_db.get(
        build_api_url("/admin/users"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_get_user_details_requires_auth(
    async_client_with_db: AsyncClient,
) -> None:
    """Test that get user details endpoint requires authentication."""
    user_id = uuid4()
    response = await async_client_with_db.get(build_api_url(f"/admin/users/{user_id}"))
    assert response.status_code == 403
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_user_details_requires_admin(
    async_client_with_db: AsyncClient,
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test that get user details endpoint requires admin role."""
    response = await async_client_with_db.get(
        build_api_url(f"/admin/users/{test_user.id}"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_anonymise_user_requires_auth(
    async_client_with_db: AsyncClient,
) -> None:
    """Test that anonymise user endpoint requires authentication."""
    user_id = uuid4()
    response = await async_client_with_db.delete(build_api_url(f"/admin/users/{user_id}"))
    assert response.status_code == 403
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_anonymise_user_requires_admin(
    async_client_with_db: AsyncClient,
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test that anonymise user endpoint requires admin role."""
    response = await async_client_with_db.delete(
        build_api_url(f"/admin/users/{test_user.id}"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_engagement_metrics_requires_auth(
    async_client_with_db: AsyncClient,
) -> None:
    """Test that engagement metrics endpoint requires authentication."""
    response = await async_client_with_db.get(build_api_url("/admin/analytics/engagement"))
    assert response.status_code == 403
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_engagement_metrics_requires_admin(
    async_client_with_db: AsyncClient,
    auth_headers_for_user: dict[str, str],
    test_user: User,
) -> None:
    """Test that engagement metrics endpoint requires admin role."""
    response = await async_client_with_db.get(
        build_api_url("/admin/analytics/engagement"),
        headers=auth_headers_for_user,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


# ==================== List Users Endpoint Tests ====================


@pytest.mark.asyncio
async def test_list_users_empty(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """Test listing users when only admin exists."""
    response = await async_client_with_db.get(
        build_api_url("/admin/users"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1  # At least the admin user
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert len(data["users"]) >= 1


@pytest.mark.asyncio
async def test_list_users_with_contacts(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    another_user: User,
    db_session: AsyncSession,
) -> None:
    """Test listing users with email and phone contacts."""
    # Add email and phone to another_user (not admin)
    email = EmailAddress(
        user_id=another_user.id,
        email="test@example.com",
        verified=True,
        is_primary=True,
    )
    phone = PhoneNumber(
        user_id=another_user.id,
        phone="+441234567890",
        verified=False,
        is_primary=True,
    )
    db_session.add(email)
    db_session.add(phone)
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/users"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2  # Admin + another_user

    # Find another_user in results
    another_user_data = next((u for u in data["users"] if u["id"] == str(another_user.id)), None)
    assert another_user_data is not None
    assert len(another_user_data["email_addresses"]) == 1
    assert another_user_data["email_addresses"][0]["email"] == "test@example.com"
    assert another_user_data["email_addresses"][0]["verified"] is True
    assert len(another_user_data["phone_numbers"]) == 1
    assert another_user_data["phone_numbers"][0]["phone"] == "+441234567890"
    assert another_user_data["phone_numbers"][0]["verified"] is False


@pytest.mark.asyncio
async def test_list_users_with_multiple_contacts(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    another_user: User,
    db_session: AsyncSession,
) -> None:
    """Test listing users with multiple email addresses and phone numbers."""
    # Add multiple emails to another_user
    email1 = EmailAddress(
        user_id=another_user.id,
        email="primary@example.com",
        verified=True,
        is_primary=True,
    )
    email2 = EmailAddress(
        user_id=another_user.id,
        email="secondary@example.com",
        verified=True,
        is_primary=False,
    )
    email3 = EmailAddress(
        user_id=another_user.id,
        email="unverified@example.com",
        verified=False,
        is_primary=False,
    )

    # Add multiple phones to another_user
    phone1 = PhoneNumber(
        user_id=another_user.id,
        phone="+441111111111",
        verified=True,
        is_primary=True,
    )
    phone2 = PhoneNumber(
        user_id=another_user.id,
        phone="+442222222222",
        verified=False,
        is_primary=False,
    )

    db_session.add_all([email1, email2, email3, phone1, phone2])
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/users"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Find another_user in results
    another_user_data = next((u for u in data["users"] if u["id"] == str(another_user.id)), None)
    assert another_user_data is not None

    # Check that all email addresses are included
    assert len(another_user_data["email_addresses"]) == 3
    emails = [e["email"] for e in another_user_data["email_addresses"]]
    assert "primary@example.com" in emails
    assert "secondary@example.com" in emails
    assert "unverified@example.com" in emails

    # Check email verification status and primary flags
    primary_email = next((e for e in another_user_data["email_addresses"] if e["is_primary"]), None)
    assert primary_email is not None
    assert primary_email["email"] == "primary@example.com"
    assert primary_email["verified"] is True

    # Check that all phone numbers are included
    assert len(another_user_data["phone_numbers"]) == 2
    phones = [p["phone"] for p in another_user_data["phone_numbers"]]
    assert "+441111111111" in phones
    assert "+442222222222" in phones

    # Check phone verification status and primary flags
    primary_phone = next((p for p in another_user_data["phone_numbers"] if p["is_primary"]), None)
    assert primary_phone is not None
    assert primary_phone["phone"] == "+441111111111"
    assert primary_phone["verified"] is True


@pytest.mark.asyncio
async def test_list_users_pagination(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """Test user listing pagination."""
    # Create additional users
    for i in range(5):
        user = User(external_id=f"test_user_{i}", auth_provider="auth0")
        db_session.add(user)
    await db_session.commit()

    # Test with limit=2
    response = await async_client_with_db.get(
        build_api_url("/admin/users?limit=2&offset=0"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["users"]) == 2
    assert data["total"] >= 6  # Admin + 5 test users

    # Test offset
    response = await async_client_with_db.get(
        build_api_url("/admin/users?limit=2&offset=2"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 2
    assert len(data["users"]) <= 2


@pytest.mark.asyncio
async def test_list_users_search_by_email(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test searching users by email address."""
    # Add unique email to test user
    email = EmailAddress(
        user_id=test_user.id,
        email="searchable@example.com",
        verified=True,
        is_primary=True,
    )
    db_session.add(email)
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/users?search=searchable"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any("searchable@example.com" in [e["email"] for e in u["email_addresses"]] for u in data["users"])


@pytest.mark.asyncio
async def test_list_users_search_by_external_id(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    test_user: User,
) -> None:
    """Test searching users by external_id."""
    response = await async_client_with_db.get(
        build_api_url(f"/admin/users?search={test_user.external_id[:10]}"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(u["id"] == str(test_user.id) for u in data["users"])


@pytest.mark.asyncio
async def test_list_users_exclude_deleted(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """Test that deleted users are excluded by default."""
    # Create a deleted user
    deleted_user = User(
        external_id="deleted_user",
        auth_provider="auth0",
        deleted_at=datetime.now(UTC),
    )
    db_session.add(deleted_user)
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/users"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert all(u["id"] != str(deleted_user.id) for u in data["users"])


@pytest.mark.asyncio
async def test_list_users_include_deleted(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """Test including deleted users with include_deleted=true."""
    # Create a deleted user
    deleted_user = User(
        external_id="deleted_user",
        auth_provider="auth0",
        deleted_at=datetime.now(UTC),
    )
    db_session.add(deleted_user)
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/users?include_deleted=true"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    # Should find the deleted user
    deleted_found = any(u["id"] == str(deleted_user.id) for u in data["users"])
    assert deleted_found

    # Check deleted_at field is present
    deleted_user_data = next((u for u in data["users"] if u["id"] == str(deleted_user.id)), None)
    assert deleted_user_data is not None
    assert deleted_user_data["deleted_at"] is not None


# ==================== Get User Details Endpoint Tests ====================


@pytest.mark.asyncio
async def test_get_user_details_success(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """Test getting detailed user information."""
    # Add email and phone to test user
    email = EmailAddress(
        user_id=test_user.id,
        email="detail@example.com",
        verified=True,
        is_primary=True,
    )
    phone = PhoneNumber(
        user_id=test_user.id,
        phone="+449876543210",
        verified=True,
        is_primary=True,
    )
    db_session.add(email)
    db_session.add(phone)
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url(f"/admin/users/{test_user.id}"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["external_id"] == test_user.external_id
    assert data["auth_provider"] == test_user.auth_provider
    assert "created_at" in data
    assert "updated_at" in data
    assert len(data["email_addresses"]) == 1
    assert data["email_addresses"][0]["email"] == "detail@example.com"
    assert len(data["phone_numbers"]) == 1
    assert data["phone_numbers"][0]["phone"] == "+449876543210"


@pytest.mark.asyncio
async def test_get_user_details_not_found(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
) -> None:
    """Test getting details for non-existent user."""
    fake_id = uuid4()
    response = await async_client_with_db.get(
        build_api_url(f"/admin/users/{fake_id}"),
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found."


# ==================== Anonymise User Endpoint Tests ====================


@pytest.mark.asyncio
async def test_anonymise_user_success(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """Test successful user anonymisation."""
    # Create a test user with PII
    user = User(external_id="to_delete", auth_provider="auth0")
    db_session.add(user)
    await db_session.flush()

    email = EmailAddress(
        user_id=user.id,
        email="delete@example.com",
        verified=True,
        is_primary=True,
    )
    phone = PhoneNumber(
        user_id=user.id,
        phone="+441111111111",
        verified=True,
        is_primary=True,
    )
    route = Route(user_id=user.id, name="Test Route", active=True, timezone="Europe/London")
    db_session.add_all([email, phone, route])
    await db_session.flush()  # Flush to get email.id

    # Now create verification code with valid contact_id
    code = VerificationCode(
        user_id=user.id,
        contact_id=email.id,
        code="123456",
        type=VerificationType.EMAIL,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        used=False,
    )
    db_session.add(code)
    await db_session.commit()

    response = await async_client_with_db.delete(
        build_api_url(f"/admin/users/{user.id}"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user_id"] == str(user.id)
    assert "anonymised" in data["message"].lower()

    # Verify user was anonymised
    await db_session.refresh(user)
    assert user.deleted_at is not None
    assert user.external_id == f"deleted_{user.id}"
    assert user.auth_provider == ""

    # Verify PII was deleted
    email_count = await db_session.execute(sql_select(EmailAddress).where(EmailAddress.user_id == user.id))
    assert len(email_count.scalars().all()) == 0

    phone_count = await db_session.execute(sql_select(PhoneNumber).where(PhoneNumber.user_id == user.id))
    assert len(phone_count.scalars().all()) == 0

    code_count = await db_session.execute(sql_select(VerificationCode).where(VerificationCode.user_id == user.id))
    assert len(code_count.scalars().all()) == 0

    # Verify route was deactivated but not deleted
    await db_session.refresh(route)
    assert route.active is False
    assert route.deleted_at is None  # Route structure preserved


@pytest.mark.asyncio
async def test_anonymise_user_not_found(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
) -> None:
    """Test anonymising non-existent user."""
    fake_id = uuid4()
    response = await async_client_with_db.delete(
        build_api_url(f"/admin/users/{fake_id}"),
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found."


@pytest.mark.asyncio
async def test_anonymise_user_already_deleted(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """Test anonymising already deleted user."""
    # Create a deleted user
    user = User(
        external_id="already_deleted",
        auth_provider="auth0",
        deleted_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()

    response = await async_client_with_db.delete(
        build_api_url(f"/admin/users/{user.id}"),
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "User is already deleted."


# ==================== Engagement Metrics Endpoint Tests ====================


@pytest.mark.asyncio
async def test_engagement_metrics_empty_database(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
) -> None:
    """Test engagement metrics with minimal data."""
    response = await async_client_with_db.get(
        build_api_url("/admin/analytics/engagement"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "user_counts" in data
    assert "route_stats" in data
    assert "notification_stats" in data
    assert "growth_metrics" in data

    # User counts
    assert data["user_counts"]["total_users"] >= 1  # At least admin
    assert data["user_counts"]["active_users"] >= 0
    assert data["user_counts"]["users_with_verified_email"] >= 0
    assert data["user_counts"]["users_with_verified_phone"] >= 0
    assert data["user_counts"]["admin_users"] >= 1

    # Route stats
    assert data["route_stats"]["total_routes"] >= 0
    assert data["route_stats"]["active_routes"] >= 0
    assert data["route_stats"]["avg_routes_per_user"] >= 0.0

    # Notification stats
    assert data["notification_stats"]["total_sent"] >= 0
    assert data["notification_stats"]["successful"] >= 0
    assert data["notification_stats"]["failed"] >= 0
    assert 0.0 <= data["notification_stats"]["success_rate"] <= 100.0

    # Growth metrics
    assert data["growth_metrics"]["new_users_last_7_days"] >= 0
    assert data["growth_metrics"]["new_users_last_30_days"] >= 0
    assert isinstance(data["growth_metrics"]["daily_signups_last_7_days"], list)


@pytest.mark.asyncio
async def test_engagement_metrics_with_data(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    another_user: User,
    db_session: AsyncSession,
) -> None:
    """Test engagement metrics with comprehensive test data."""
    # Add verified contacts
    email = EmailAddress(
        user_id=another_user.id,
        email="metrics@example.com",
        verified=True,
        is_primary=True,
    )
    phone = PhoneNumber(
        user_id=another_user.id,
        phone="+442222222222",
        verified=True,
        is_primary=True,
    )
    db_session.add_all([email, phone])

    # Add routes
    route1 = Route(
        user_id=another_user.id,
        name="Active Route",
        active=True,
        timezone="Europe/London",
    )
    route2 = Route(
        user_id=another_user.id,
        name="Inactive Route",
        active=False,
        timezone="Europe/London",
    )
    db_session.add_all([route1, route2])
    await db_session.flush()

    # Add notification logs
    log1 = NotificationLog(
        user_id=another_user.id,
        route_id=route1.id,
        sent_at=datetime.now(UTC),
        method=NotificationMethod.EMAIL,
        status=NotificationStatus.SENT,
    )
    log2 = NotificationLog(
        user_id=another_user.id,
        route_id=route1.id,
        sent_at=datetime.now(UTC),
        method=NotificationMethod.SMS,
        status=NotificationStatus.FAILED,
        error_message="Test error",
    )
    db_session.add_all([log1, log2])
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/analytics/engagement"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify counts
    assert data["user_counts"]["total_users"] >= 2  # Admin + another_user
    assert data["user_counts"]["active_users"] >= 1  # another_user with active route
    assert data["user_counts"]["users_with_verified_email"] >= 1
    assert data["user_counts"]["users_with_verified_phone"] >= 1

    assert data["route_stats"]["total_routes"] >= 2
    assert data["route_stats"]["active_routes"] >= 1
    assert data["route_stats"]["avg_routes_per_user"] > 0.0

    assert data["notification_stats"]["total_sent"] >= 2
    assert data["notification_stats"]["successful"] >= 1
    assert data["notification_stats"]["failed"] >= 1
    assert data["notification_stats"]["success_rate"] > 0.0


@pytest.mark.asyncio
async def test_engagement_metrics_notification_methods(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    another_user: User,
    db_session: AsyncSession,
) -> None:
    """Test notification stats are correctly grouped by method."""
    # Create a route
    route = Route(
        user_id=another_user.id,
        name="Test Route",
        active=True,
        timezone="Europe/London",
    )
    db_session.add(route)
    await db_session.flush()

    # Add notifications with different methods
    now = datetime.now(UTC)
    for _ in range(3):
        log = NotificationLog(
            user_id=another_user.id,
            route_id=route.id,
            sent_at=now,
            method=NotificationMethod.EMAIL,
            status=NotificationStatus.SENT,
        )
        db_session.add(log)

    for _ in range(2):
        log = NotificationLog(
            user_id=another_user.id,
            route_id=route.id,
            sent_at=now,
            method=NotificationMethod.SMS,
            status=NotificationStatus.SENT,
        )
        db_session.add(log)

    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/analytics/engagement"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    by_method = data["notification_stats"]["by_method_last_30_days"]
    assert by_method.get("email", 0) >= 3
    assert by_method.get("sms", 0) >= 2


@pytest.mark.asyncio
async def test_engagement_metrics_growth_tracking(
    async_client_with_db: AsyncClient,
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """Test growth metrics track new users correctly."""
    # Create users at different times
    now = datetime.now(UTC)
    old_user = User(
        external_id="old_user",
        auth_provider="auth0",
        created_at=now - timedelta(days=60),
    )
    recent_user = User(
        external_id="recent_user",
        auth_provider="auth0",
        created_at=now - timedelta(days=5),
    )
    new_user = User(
        external_id="new_user",
        auth_provider="auth0",
        created_at=now - timedelta(hours=1),
    )
    db_session.add_all([old_user, recent_user, new_user])
    await db_session.commit()

    response = await async_client_with_db.get(
        build_api_url("/admin/analytics/engagement"),
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    growth = data["growth_metrics"]
    # Both recent_user and new_user should be in last 7 days
    assert growth["new_users_last_7_days"] >= 2
    # All three should be in last 30 days
    assert growth["new_users_last_30_days"] >= 3
    # Should have daily signup data
    assert len(growth["daily_signups_last_7_days"]) >= 0


# ==================== Unit Tests for Pure Functions ====================


def test_calculate_success_rate_normal_values() -> None:
    """Test success rate calculation with normal values."""
    # 80% success rate
    assert calculate_success_rate(80, 100) == 80.0
    # 50% success rate
    assert calculate_success_rate(50, 100) == 50.0
    # 100% success rate
    assert calculate_success_rate(100, 100) == 100.0
    # 0% success rate
    assert calculate_success_rate(0, 100) == 0.0


def test_calculate_success_rate_edge_cases() -> None:
    """Test success rate calculation with edge cases."""
    # Zero total should return 0.0
    assert calculate_success_rate(10, 0) == 0.0
    # Negative total should return 0.0
    assert calculate_success_rate(10, -5) == 0.0
    # Single item
    assert calculate_success_rate(1, 1) == 100.0
    assert calculate_success_rate(0, 1) == 0.0


def test_calculate_success_rate_rounding() -> None:
    """Test success rate calculation rounds to 2 decimal places."""
    # 66.666... should round to 66.67
    assert calculate_success_rate(2, 3) == 66.67
    # 33.333... should round to 33.33
    assert calculate_success_rate(1, 3) == 33.33
    # 14.285714... should round to 14.29
    assert calculate_success_rate(1, 7) == 14.29


def test_calculate_avg_routes_normal_values() -> None:
    """Test average routes calculation with normal values."""
    # 2 routes per user on average
    assert calculate_avg_routes(10, 5) == 2.0
    # 1 route per user
    assert calculate_avg_routes(5, 5) == 1.0
    # 3.5 routes per user
    assert calculate_avg_routes(7, 2) == 3.5


def test_calculate_avg_routes_edge_cases() -> None:
    """Test average routes calculation with edge cases."""
    # Zero users should return 0.0
    assert calculate_avg_routes(10, 0) == 0.0
    # Negative users should return 0.0
    assert calculate_avg_routes(10, -5) == 0.0
    # Zero routes should return 0.0
    assert calculate_avg_routes(0, 5) == 0.0
    # Single user single route
    assert calculate_avg_routes(1, 1) == 1.0


def test_calculate_avg_routes_rounding() -> None:
    """Test average routes calculation rounds to 2 decimal places."""
    # 3.333... should round to 3.33
    assert calculate_avg_routes(10, 3) == 3.33
    # 2.666... should round to 2.67
    assert calculate_avg_routes(8, 3) == 2.67
    # 1.428571... should round to 1.43
    assert calculate_avg_routes(10, 7) == 1.43
