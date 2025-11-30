"""Admin service for user management and analytics."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import String, and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.telemetry import service_span
from app.models.admin import AdminUser
from app.models.notification import NotificationLog, NotificationPreference, NotificationStatus
from app.models.user import EmailAddress, PhoneNumber, User, VerificationCode
from app.models.user_route import UserRoute
from app.schemas.admin import (
    DailySignup,
    EngagementMetrics,
    GrowthMetrics,
    NotificationStatMetrics,
    RouteStatMetrics,
    UserCountMetrics,
)

# ==================== Pure Calculation Functions ====================


def calculate_success_rate(successful: int, total: int) -> float:
    """
    Calculate success rate as a percentage.

    Pure function with no side effects - can be unit tested independently.

    Args:
        successful: Number of successful items
        total: Total number of items

    Returns:
        Success rate as a percentage (0.0 to 100.0), rounded to 2 decimal places
    """
    return 0.0 if total <= 0 else round((successful / total) * 100, 2)


def calculate_avg_routes(total_routes: int, users_with_routes: int) -> float:
    """
    Calculate average routes per user.

    Pure function with no side effects - can be unit tested independently.

    Args:
        total_routes: Total number of routes
        users_with_routes: Number of users who have at least one route

    Returns:
        Average routes per user, rounded to 2 decimal places
    """
    if users_with_routes <= 0:
        return 0.0
    return round(total_routes / users_with_routes, 2)


class AdminService:
    """Service for admin operations and analytics."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the admin service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_users_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[User], int]:
        """
        Get paginated list of users with optional search and filters.

        Args:
            limit: Maximum number of users to return (1-1000)
            offset: Number of users to skip
            search: Optional search term (searches UUID, email, phone, and external_id)
            include_deleted: Whether to include soft-deleted users

        Returns:
            Tuple of (list of users, total count)
        """
        with service_span(
            "admin.get_users_paginated",
            "admin-service",
        ) as span:
            span.set_attribute("admin.operation", "get_users_paginated")
            span.set_attribute("admin.limit", limit)
            span.set_attribute("admin.offset", offset)
            span.set_attribute("admin.search_enabled", bool(search))
            span.set_attribute("admin.include_deleted", include_deleted)
            # Build count query (separate from main query to avoid cartesian product)
            count_query = select(func.count(func.distinct(User.id)))

            # Filter deleted users unless explicitly included
            if not include_deleted:
                count_query = count_query.where(User.deleted_at.is_(None))

            # Apply search if provided
            if search:
                # Search in UUID (cast to text for partial matching), external_id, email, or phone
                search_term = f"%{search}%"
                count_query = (
                    count_query.outerjoin(User.email_addresses)
                    .outerjoin(User.phone_numbers)
                    .where(
                        or_(
                            func.cast(User.id, String).ilike(search_term),
                            User.external_id.ilike(search_term),
                            EmailAddress.email.ilike(search_term),
                            PhoneNumber.phone.ilike(search_term),
                        )
                    )
                )

            # Get total count
            result = await self.db.execute(count_query)
            total = result.scalar() or 0

            # Build main query with relationships loaded
            query = select(User).options(
                selectinload(User.email_addresses),
                selectinload(User.phone_numbers),
            )

            # Apply same filters as count query
            if not include_deleted:
                query = query.where(User.deleted_at.is_(None))

            if search:
                search_term = f"%{search}%"
                query = (
                    query.outerjoin(User.email_addresses)
                    .outerjoin(User.phone_numbers)
                    .where(
                        or_(
                            func.cast(User.id, String).ilike(search_term),
                            User.external_id.ilike(search_term),
                            EmailAddress.email.ilike(search_term),
                            PhoneNumber.phone.ilike(search_term),
                        )
                    )
                    .distinct()
                )

            # Get paginated results
            query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)
            result = await self.db.execute(query)
            users_list: list[User] = list(result.unique().scalars().all())  # type: ignore[arg-type]

            # Set result counts as span attributes
            span.set_attribute("admin.result_count", len(users_list))
            span.set_attribute("admin.total_count", total)

            return users_list, total

    async def get_user_details(self, user_id: uuid.UUID) -> User:
        """
        Get detailed information about a user including relationships.

        Args:
            user_id: User UUID

        Returns:
            User object with all relationships loaded

        Raises:
            HTTPException: 404 if user not found
        """
        query = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.email_addresses),
                selectinload(User.phone_numbers),
            )
        )

        result = await self.db.execute(query)
        if not (user := result.scalar_one_or_none()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return user

    async def anonymise_user(self, user_id: uuid.UUID) -> None:
        """
        Anonymise a user by deleting PII and deactivating routes.

        This is a privacy-focused deletion that:
        - Deletes email addresses, phone numbers, verification codes (PII)
        - Anonymises external_id to "deleted_{user_id}"
        - Clears auth_provider
        - Deactivates all user routes (stops alerts)
        - Sets deleted_at timestamp
        - Preserves notification logs and route structure for analytics

        Args:
            user_id: User UUID to anonymise

        Raises:
            HTTPException: 404 if user not found, 400 if already deleted
        """
        with service_span(
            "admin.anonymise_user",
            "admin-service",
        ) as span:
            # Set span attributes
            span.set_attribute("admin.user_id", str(user_id))
            span.set_attribute("admin.operation", "anonymise_user")
            # Check if user exists
            user = await self.get_user_details(user_id)

            # Check if already deleted
            if user.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User is already deleted.",
                )

            # Wrap all operations in a transaction to ensure atomicity
            try:
                # Begin anonymisation process
                # 1. Delete verification codes first (they reference emails/phones via contact_id)
                await self.db.execute(delete(VerificationCode).where(VerificationCode.user_id == user_id))

                # 2. Delete email addresses
                await self.db.execute(delete(EmailAddress).where(EmailAddress.user_id == user_id))

                # 3. Delete phone numbers
                await self.db.execute(delete(PhoneNumber).where(PhoneNumber.user_id == user_id))

                # 4. Delete notification preferences
                # Note: CASCADE from email/phone deletion would handle this, but we're explicit
                # for clarity. Preferences without active contacts/user are not actionable;
                # NotificationLog preserves historical behavior data for analytics.
                await self.db.execute(
                    delete(NotificationPreference).where(
                        NotificationPreference.route_id.in_(select(UserRoute.id).where(UserRoute.user_id == user_id))
                    )
                )

                # 5. Deactivate all routes
                await self.db.execute(update(UserRoute).where(UserRoute.user_id == user_id).values(active=False))

                # 6. Update user: anonymise external_id, clear auth_provider, set deleted_at
                await self.db.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        external_id=f"deleted_{user_id}",
                        auth_provider="",
                        deleted_at=datetime.now(UTC),
                    )
                )

                # Commit all changes atomically
                await self.db.commit()
            except Exception:
                # Rollback on any failure to ensure no partial deletion
                await self.db.rollback()
                raise

    # ==================== Private Helper Methods for Metrics ====================

    async def _count_total_users(self) -> int:
        """Count total non-deleted users."""
        result = await self.db.execute(select(func.count(User.id)).where(User.deleted_at.is_(None)))
        return result.scalar() or 0

    async def _count_active_users(self) -> int:
        """Count users with at least one active route."""
        result = await self.db.execute(
            select(func.count(func.distinct(UserRoute.user_id))).where(
                and_(
                    UserRoute.active.is_(True),
                    UserRoute.deleted_at.is_(None),
                )
            )
        )
        return result.scalar() or 0

    async def _count_users_with_verified_email(self) -> int:
        """Count users with at least one verified email address."""
        result = await self.db.execute(
            select(func.count(func.distinct(EmailAddress.user_id))).where(EmailAddress.verified.is_(True))
        )
        return result.scalar() or 0

    async def _count_users_with_verified_phone(self) -> int:
        """Count users with at least one verified phone number."""
        result = await self.db.execute(
            select(func.count(func.distinct(PhoneNumber.user_id))).where(PhoneNumber.verified.is_(True))
        )
        return result.scalar() or 0

    async def _count_admin_users(self) -> int:
        """Count non-deleted admin users."""
        result = await self.db.execute(select(func.count(AdminUser.id)).where(AdminUser.deleted_at.is_(None)))
        return result.scalar() or 0

    async def _count_total_routes(self) -> int:
        """Count total non-deleted routes."""
        result = await self.db.execute(select(func.count(UserRoute.id)).where(UserRoute.deleted_at.is_(None)))
        return result.scalar() or 0

    async def _count_active_routes(self) -> int:
        """Count active non-deleted routes."""
        result = await self.db.execute(
            select(func.count(UserRoute.id)).where(
                and_(
                    UserRoute.active.is_(True),
                    UserRoute.deleted_at.is_(None),
                )
            )
        )
        return result.scalar() or 0

    async def _get_routes_user_count(self) -> tuple[int, int]:
        """
        Get total routes and distinct user count for average calculation.

        Returns:
            Tuple of (total_routes, users_with_routes)
        """
        result = await self.db.execute(
            select(
                func.count(UserRoute.id).label("total_routes"),
                func.count(func.distinct(UserRoute.user_id)).label("users_with_routes"),
            ).where(UserRoute.deleted_at.is_(None))
        )
        row = result.one()
        return row.total_routes, row.users_with_routes

    async def _count_total_notifications(self) -> int:
        """Count all notification log entries."""
        result = await self.db.execute(select(func.count(NotificationLog.id)))
        return result.scalar() or 0

    async def _count_successful_notifications(self) -> int:
        """Count successfully sent notifications."""
        result = await self.db.execute(
            select(func.count(NotificationLog.id)).where(NotificationLog.status == NotificationStatus.SENT)
        )
        return result.scalar() or 0

    async def _count_failed_notifications(self) -> int:
        """Count failed notifications."""
        result = await self.db.execute(
            select(func.count(NotificationLog.id)).where(NotificationLog.status == NotificationStatus.FAILED)
        )
        return result.scalar() or 0

    async def _get_notifications_by_method(self, since: datetime) -> dict[str, int]:
        """
        Get notification counts grouped by method since a given datetime.

        Args:
            since: Only count notifications sent on or after this datetime

        Returns:
            Dictionary mapping method name to count
        """
        result = await self.db.execute(
            select(
                NotificationLog.method,
                func.count(NotificationLog.id).label("count"),
            )
            .where(NotificationLog.sent_at >= since)
            .group_by(NotificationLog.method)
        )
        # SQLAlchemy row attributes are dynamic - mypy can't infer the type
        by_method: dict[str, int] = {row.method.value: row.count for row in result}  # type: ignore[misc]
        return by_method

    async def _count_new_users_since(self, since: datetime) -> int:
        """
        Count new users created since a given datetime.

        Args:
            since: Only count users created on or after this datetime

        Returns:
            Count of new non-deleted users
        """
        result = await self.db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.created_at >= since,
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar() or 0

    async def _get_daily_signups_since(self, since: datetime) -> list[DailySignup]:
        """
        Get daily signup counts since a given datetime.

        Args:
            since: Only count users created on or after this datetime

        Returns:
            List of DailySignup objects with date and count
        """
        day_column = func.date_trunc("day", User.created_at).label("day")
        result = await self.db.execute(
            select(
                day_column,
                func.count(User.id).label("count"),
            )
            .where(
                and_(
                    User.created_at >= since,
                    User.deleted_at.is_(None),
                )
            )
            .group_by(day_column)
            .order_by(day_column)
        )
        return [DailySignup(date=row.day.isoformat(), count=row.count) for row in result]

    async def get_engagement_metrics(self) -> EngagementMetrics:
        """
        Get comprehensive engagement metrics for the admin dashboard.

        Returns:
            EngagementMetrics containing:
            - user_counts: Total, active (with routes), verified contacts
            - route_stats: Total, active, average per user
            - notification_stats: Sent, failed, success rate, by method
            - growth_metrics: New users by time period
        """
        with service_span(
            "admin.get_engagement_metrics",
            "admin-service",
        ) as span:
            span.set_attribute("admin.operation", "get_engagement_metrics")
            # Calculate datetime thresholds once
            now = datetime.now(UTC)
            seven_days_ago = now - timedelta(days=7)
            thirty_days_ago = now - timedelta(days=30)

            # Gather user count metrics
            user_counts = UserCountMetrics(
                total_users=await self._count_total_users(),
                active_users=await self._count_active_users(),
                users_with_verified_email=await self._count_users_with_verified_email(),
                users_with_verified_phone=await self._count_users_with_verified_phone(),
                admin_users=await self._count_admin_users(),
            )

            # Gather route statistics
            total_routes = await self._count_total_routes()
            active_routes = await self._count_active_routes()
            route_count, user_count = await self._get_routes_user_count()

            route_stats = RouteStatMetrics(
                total_routes=total_routes,
                active_routes=active_routes,
                avg_routes_per_user=calculate_avg_routes(route_count, user_count),
            )

            # Gather notification statistics
            total_sent = await self._count_total_notifications()
            successful = await self._count_successful_notifications()
            failed = await self._count_failed_notifications()
            by_method = await self._get_notifications_by_method(thirty_days_ago)

            notification_stats = NotificationStatMetrics(
                total_sent=total_sent,
                successful=successful,
                failed=failed,
                success_rate=calculate_success_rate(successful, total_sent),
                by_method_last_30_days=by_method,
            )

            # Gather growth metrics
            growth_metrics = GrowthMetrics(
                new_users_last_7_days=await self._count_new_users_since(seven_days_ago),
                new_users_last_30_days=await self._count_new_users_since(thirty_days_ago),
                daily_signups_last_7_days=await self._get_daily_signups_since(seven_days_ago),
            )

            return EngagementMetrics(
                user_counts=user_counts,
                route_stats=route_stats,
                notification_stats=notification_stats,
                growth_metrics=growth_metrics,
            )
