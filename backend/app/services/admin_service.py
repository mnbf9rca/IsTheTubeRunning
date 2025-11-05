"""Admin service for user management and analytics."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admin import AdminUser
from app.models.notification import NotificationLog, NotificationStatus
from app.models.route import Route
from app.models.user import EmailAddress, PhoneNumber, User, VerificationCode


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
            search: Optional search term (searches email and external_id)
            include_deleted: Whether to include soft-deleted users

        Returns:
            Tuple of (list of users, total count)
        """
        # Build base query
        query = select(User).options(
            selectinload(User.email_addresses),
            selectinload(User.phone_numbers),
        )

        # Filter deleted users unless explicitly included
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))

        # Apply search if provided
        if search:
            # Search in external_id or email addresses
            search_term = f"%{search}%"
            query = (
                query.outerjoin(User.email_addresses)
                .where(
                    or_(
                        User.external_id.ilike(search_term),
                        EmailAddress.email.ilike(search_term),
                    )
                )
                .distinct()
            )

        # Get total count (use COUNT(DISTINCT user.id) to avoid inflation from joins)
        count_query = select(func.count(func.distinct(User.id))).select_from(query.subquery())
        result = await self.db.execute(count_query)
        total = result.scalar() or 0

        # Get paginated results
        query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        users_list: list[User] = list(result.unique().scalars().all())  # type: ignore[arg-type]

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

            # 4. Deactivate all routes
            await self.db.execute(update(Route).where(Route.user_id == user_id).values(active=False))

            # 5. Update user: anonymise external_id, clear auth_provider, set deleted_at
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

    async def get_engagement_metrics(self) -> dict[str, Any]:
        """
        Get comprehensive engagement metrics for the admin dashboard.

        Returns:
            Dictionary containing:
            - user_counts: Total, active (with routes), verified contacts
            - route_stats: Total, active, average per user
            - notification_stats: Sent, failed, success rate, by method
            - growth_metrics: New users by time period
        """
        # Initialize metrics structure
        metrics: dict[str, Any] = {
            "user_counts": {},
            "route_stats": {},
            "notification_stats": {},
            "growth_metrics": {},
        }

        # ==================== User Counts ====================
        # Total users (non-deleted)
        result = await self.db.execute(select(func.count(User.id)).where(User.deleted_at.is_(None)))
        metrics["user_counts"]["total_users"] = result.scalar() or 0

        # Users with active routes
        result = await self.db.execute(
            select(func.count(func.distinct(Route.user_id))).where(
                and_(
                    Route.active.is_(True),
                    Route.deleted_at.is_(None),
                )
            )
        )
        metrics["user_counts"]["active_users"] = result.scalar() or 0

        # Users with verified email
        result = await self.db.execute(
            select(func.count(func.distinct(EmailAddress.user_id))).where(EmailAddress.verified.is_(True))
        )
        metrics["user_counts"]["users_with_verified_email"] = result.scalar() or 0

        # Users with verified phone
        result = await self.db.execute(
            select(func.count(func.distinct(PhoneNumber.user_id))).where(PhoneNumber.verified.is_(True))
        )
        metrics["user_counts"]["users_with_verified_phone"] = result.scalar() or 0

        # Admin users
        result = await self.db.execute(select(func.count(AdminUser.id)).where(AdminUser.deleted_at.is_(None)))
        metrics["user_counts"]["admin_users"] = result.scalar() or 0

        # ==================== Route Statistics ====================
        # Total routes (non-deleted)
        result = await self.db.execute(select(func.count(Route.id)).where(Route.deleted_at.is_(None)))
        metrics["route_stats"]["total_routes"] = result.scalar() or 0

        # Active routes
        result = await self.db.execute(
            select(func.count(Route.id)).where(
                and_(
                    Route.active.is_(True),
                    Route.deleted_at.is_(None),
                )
            )
        )
        metrics["route_stats"]["active_routes"] = result.scalar() or 0

        # Average routes per user (only users with routes)
        result = await self.db.execute(
            select(
                func.count(Route.id).label("total_routes"),
                func.count(func.distinct(Route.user_id)).label("users_with_routes"),
            ).where(Route.deleted_at.is_(None))
        )
        row = result.one()
        if row.users_with_routes and row.users_with_routes > 0:
            metrics["route_stats"]["avg_routes_per_user"] = round(row.total_routes / row.users_with_routes, 2)
        else:
            metrics["route_stats"]["avg_routes_per_user"] = 0.0

        # ==================== Notification Statistics ====================
        # Total notifications sent
        result = await self.db.execute(select(func.count(NotificationLog.id)))
        metrics["notification_stats"]["total_sent"] = result.scalar() or 0

        # Successful notifications
        result = await self.db.execute(
            select(func.count(NotificationLog.id)).where(NotificationLog.status == NotificationStatus.SENT)
        )
        successful = result.scalar() or 0
        metrics["notification_stats"]["successful"] = successful

        # Failed notifications
        result = await self.db.execute(
            select(func.count(NotificationLog.id)).where(NotificationLog.status == NotificationStatus.FAILED)
        )
        failed = result.scalar() or 0
        metrics["notification_stats"]["failed"] = failed

        # Success rate
        total_notifications = metrics["notification_stats"]["total_sent"]
        if total_notifications > 0:
            metrics["notification_stats"]["success_rate"] = round((successful / total_notifications) * 100, 2)
        else:
            metrics["notification_stats"]["success_rate"] = 0.0

        # Notifications by method (last 30 days)
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        result = await self.db.execute(
            select(
                NotificationLog.method,
                func.count(NotificationLog.id).label("count"),
            )
            .where(NotificationLog.sent_at >= thirty_days_ago)
            .group_by(NotificationLog.method)
        )
        by_method = {row.method.value: row.count for row in result}
        metrics["notification_stats"]["by_method_last_30_days"] = by_method

        # ==================== Growth Metrics ====================
        # New users last 7 days
        seven_days_ago = datetime.now(UTC) - timedelta(days=7)
        result = await self.db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.created_at >= seven_days_ago,
                    User.deleted_at.is_(None),
                )
            )
        )
        metrics["growth_metrics"]["new_users_last_7_days"] = result.scalar() or 0

        # New users last 30 days
        result = await self.db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.created_at >= thirty_days_ago,
                    User.deleted_at.is_(None),
                )
            )
        )
        metrics["growth_metrics"]["new_users_last_30_days"] = result.scalar() or 0

        # New users by day (last 7 days)
        day_column = func.date_trunc("day", User.created_at).label("day")
        result = await self.db.execute(
            select(
                day_column,
                func.count(User.id).label("count"),
            )
            .where(
                and_(
                    User.created_at >= seven_days_ago,
                    User.deleted_at.is_(None),
                )
            )
            .group_by(day_column)
            .order_by(day_column)
        )
        daily_signups = [{"date": row.day.isoformat(), "count": row.count} for row in result]
        metrics["growth_metrics"]["daily_signups_last_7_days"] = daily_signups

        return metrics
