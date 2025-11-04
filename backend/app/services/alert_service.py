"""Alert processing service for checking disruptions and sending notifications."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import redis.asyncio as redis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.notification import (
    NotificationLog,
    NotificationMethod,
    NotificationStatus,
)
from app.models.route import Route, RouteSchedule
from app.models.tfl import Line
from app.models.user import EmailAddress, PhoneNumber, User
from app.schemas.tfl import DisruptionResponse
from app.services.notification_service import NotificationService
from app.services.tfl_service import TfLService

logger = structlog.get_logger(__name__)


async def get_redis_client() -> redis.Redis[str]:
    """
    Create Redis client for alert deduplication.

    Returns:
        Redis client instance
    """
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


class AlertService:
    """Service for processing route alerts and sending notifications."""

    def __init__(self, db: AsyncSession, redis_client: redis.Redis[str]) -> None:
        """
        Initialize the alert service.

        Args:
            db: Database session
            redis_client: Redis client for deduplication
        """
        self.db = db
        self.redis_client = redis_client

    async def process_all_routes(self) -> dict[str, Any]:
        """
        Main entry point for processing all active routes.

        Checks all active routes, determines if they are in a schedule window,
        and sends alerts if disruptions are detected.

        Returns:
            Statistics dictionary with routes_checked, alerts_sent, and errors
        """
        logger.info("alert_processing_started")

        stats = {
            "routes_checked": 0,
            "alerts_sent": 0,
            "errors": 0,
        }

        try:
            routes = await self._get_active_routes()
            logger.info("active_routes_fetched", count=len(routes))

            for route in routes:
                try:
                    stats["routes_checked"] += 1

                    # Check if route is in an active schedule window
                    active_schedule = await self._get_active_schedule(route)
                    if not active_schedule:
                        logger.debug(
                            "route_not_in_schedule",
                            route_id=str(route.id),
                            route_name=route.name,
                        )
                        continue

                    logger.info(
                        "route_in_active_schedule",
                        route_id=str(route.id),
                        route_name=route.name,
                        schedule_id=str(active_schedule.id),
                    )

                    # Get disruptions for this route
                    disruptions = await self._get_route_disruptions(route)

                    # Skip if no disruptions
                    if not disruptions:
                        logger.debug(
                            "no_disruptions_for_route",
                            route_id=str(route.id),
                            route_name=route.name,
                        )
                        continue

                    logger.info(
                        "disruptions_found_for_route",
                        route_id=str(route.id),
                        route_name=route.name,
                        disruption_count=len(disruptions),
                    )

                    # Check if we should send alert (deduplication)
                    should_send = await self._should_send_alert(
                        route=route,
                        user_id=route.user_id,
                        schedule=active_schedule,
                        disruptions=disruptions,
                    )

                    if not should_send:
                        logger.debug(
                            "alert_skipped_duplicate",
                            route_id=str(route.id),
                            route_name=route.name,
                        )
                        continue

                    # Send alerts
                    alerts_sent = await self._send_alerts_for_route(
                        route=route,
                        schedule=active_schedule,
                        disruptions=disruptions,
                    )

                    stats["alerts_sent"] += alerts_sent

                except Exception as e:
                    stats["errors"] += 1
                    logger.error(
                        "route_processing_failed",
                        route_id=str(route.id),
                        error=str(e),
                        exc_info=e,
                    )
                    # Continue processing other routes

            logger.info("alert_processing_completed", **stats)
            return stats

        except Exception as e:
            logger.error("alert_processing_failed", error=str(e), exc_info=e)
            stats["errors"] += 1
            return stats

    async def _get_active_routes(self) -> list[Route]:
        """
        Get all active routes with their relationships.

        Returns:
            List of active Route objects with segments, schedules, preferences, and user loaded
        """
        try:
            result = await self.db.execute(
                select(Route)
                .where(
                    Route.active == True,  # noqa: E712
                    Route.deleted_at.is_(None),
                )
                .options(
                    selectinload(Route.segments),
                    selectinload(Route.schedules),
                    selectinload(Route.notification_preferences),
                    selectinload(Route.user).selectinload(User.email_addresses),
                )
            )
            return list(result.scalars().all())

        except Exception as e:
            logger.error("fetch_active_routes_failed", error=str(e), exc_info=e)
            return []

    async def _get_active_schedule(self, route: Route) -> RouteSchedule | None:
        """
        Check if the route is currently in any active schedule window.

        Converts UTC now to route's timezone and checks against schedule windows.

        Args:
            route: Route to check schedules for

        Returns:
            The first matching active schedule, or None if not in any schedule
        """
        try:
            # Get current time in route's timezone
            route_tz = ZoneInfo(route.timezone)
            now_utc = datetime.now(UTC)
            now_local = now_utc.astimezone(route_tz)

            current_time = now_local.time()
            current_day = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][now_local.weekday()]

            logger.debug(
                "checking_schedule",
                route_id=str(route.id),
                timezone=route.timezone,
                current_time=current_time.isoformat(),
                current_day=current_day,
            )

            # Check each schedule
            for schedule in route.schedules:
                # Check if current day is in schedule's days
                if current_day not in schedule.days_of_week:
                    continue

                # Check if current time is within schedule window
                if schedule.start_time <= current_time <= schedule.end_time:
                    logger.info(
                        "active_schedule_found",
                        route_id=str(route.id),
                        schedule_id=str(schedule.id),
                        start_time=schedule.start_time.isoformat(),
                        end_time=schedule.end_time.isoformat(),
                    )
                    return schedule

            return None

        except Exception as e:
            logger.error(
                "get_active_schedule_failed",
                route_id=str(route.id),
                error=str(e),
                exc_info=e,
            )
            return None

    async def _get_route_disruptions(self, route: Route) -> list[DisruptionResponse]:
        """
        Get current disruptions affecting this route.

        Fetches disruptions from TfL and filters to lines used in route segments.

        Args:
            route: Route to get disruptions for

        Returns:
            List of disruptions affecting the route's lines
        """
        try:
            # Create TfL service instance
            tfl_service = TfLService(db=self.db)

            # Fetch all disruptions (uses cache automatically)
            all_disruptions = await tfl_service.fetch_disruptions(use_cache=True)

            # Get unique line IDs from route segments
            # Need to join with Line model to get tfl_id
            line_ids = set()
            for segment in route.segments:
                result = await self.db.execute(select(Line.tfl_id).where(Line.id == segment.line_id))
                line_tfl_id = result.scalar_one_or_none()
                if line_tfl_id:
                    line_ids.add(line_tfl_id)

            # Filter disruptions to only those affecting route's lines
            route_disruptions = [d for d in all_disruptions if d.line_id in line_ids]

            logger.debug(
                "route_disruptions_filtered",
                route_id=str(route.id),
                total_disruptions=len(all_disruptions),
                route_disruptions=len(route_disruptions),
                route_lines=list(line_ids),
            )

            return route_disruptions

        except Exception as e:
            logger.error(
                "get_route_disruptions_failed",
                route_id=str(route.id),
                error=str(e),
                exc_info=e,
            )
            return []

    async def _should_send_alert(
        self,
        route: Route,
        user_id: UUID,
        schedule: RouteSchedule,
        disruptions: list[DisruptionResponse],
    ) -> bool:
        """
        Check if we should send an alert based on deduplication logic.

        Uses Redis to track disruption state within a schedule window.
        Compares current disruptions with stored state to detect changes.

        Args:
            route: Route to check
            user_id: User ID for deduplication key
            schedule: Active schedule
            disruptions: Current disruptions

        Returns:
            True if alert should be sent, False if duplicate
        """
        try:
            # Build Redis key for this route/user/schedule combination
            redis_key = f"alert:{route.id}:{user_id}:{schedule.id}"

            # Check if key exists in Redis
            stored_state = await self.redis_client.get(redis_key)

            if not stored_state:
                # No previous alert, should send
                logger.debug(
                    "no_previous_alert_state",
                    route_id=str(route.id),
                    redis_key=redis_key,
                )
                return True

            # Parse stored state and compare with current disruptions
            try:
                stored_data = json.loads(stored_state)
                stored_hash = stored_data.get("hash", "")
            except (json.JSONDecodeError, AttributeError):
                # Invalid stored data, send alert
                logger.warning(
                    "invalid_stored_alert_state",
                    route_id=str(route.id),
                    redis_key=redis_key,
                )
                return True

            # Create hash of current disruptions
            current_hash = self._create_disruption_hash(disruptions)

            # Compare hashes
            if current_hash == stored_hash:
                logger.debug(
                    "disruption_state_unchanged",
                    route_id=str(route.id),
                    redis_key=redis_key,
                )
                return False

            logger.info(
                "disruption_state_changed",
                route_id=str(route.id),
                redis_key=redis_key,
                stored_hash=stored_hash,
                current_hash=current_hash,
            )
            return True

        except Exception as e:
            logger.error(
                "should_send_alert_check_failed",
                route_id=str(route.id),
                error=str(e),
                exc_info=e,
            )
            # On error, default to sending alert (better to over-notify than under-notify)
            return True

    async def _send_alerts_for_route(  # noqa: PLR0912, PLR0915
        self,
        route: Route,
        schedule: RouteSchedule,
        disruptions: list[DisruptionResponse],
    ) -> int:
        """
        Send alerts for a route to all configured notification preferences.

        Args:
            route: Route to send alerts for
            schedule: Active schedule
            disruptions: Disruptions to notify about

        Returns:
            Number of alerts successfully sent
        """
        alerts_sent = 0

        try:
            # Check if route has notification preferences
            if not route.notification_preferences:
                logger.warning(
                    "no_notification_preferences",
                    route_id=str(route.id),
                    route_name=route.name,
                )
                return 0

            # Process each notification preference
            for pref in route.notification_preferences:
                try:
                    # Get contact information based on method
                    if pref.method == NotificationMethod.EMAIL:
                        if not pref.target_email_id:
                            logger.warning(
                                "email_preference_missing_target",
                                pref_id=str(pref.id),
                                route_id=str(route.id),
                            )
                            continue

                        email_result = await self.db.execute(
                            select(EmailAddress).where(EmailAddress.id == pref.target_email_id)
                        )
                        email_address = email_result.scalar_one_or_none()

                        if not email_address or not email_address.verified:
                            logger.warning(
                                "email_not_verified",
                                pref_id=str(pref.id),
                                route_id=str(route.id),
                                email_id=str(pref.target_email_id) if pref.target_email_id else None,
                            )
                            continue

                        contact_info = email_address.email

                    elif pref.method == NotificationMethod.SMS:
                        if not pref.target_phone_id:
                            logger.warning(
                                "sms_preference_missing_target",
                                pref_id=str(pref.id),
                                route_id=str(route.id),
                            )
                            continue

                        phone_result = await self.db.execute(
                            select(PhoneNumber).where(PhoneNumber.id == pref.target_phone_id)
                        )
                        phone_number = phone_result.scalar_one_or_none()

                        if not phone_number or not phone_number.verified:
                            logger.warning(
                                "phone_not_verified",
                                pref_id=str(pref.id),
                                route_id=str(route.id),
                                phone_id=str(pref.target_phone_id) if pref.target_phone_id else None,
                            )
                            continue

                        contact_info = phone_number.phone

                    else:
                        logger.warning(
                            "unknown_notification_method",
                            pref_id=str(pref.id),
                            method=pref.method,
                        )
                        continue

                    # Send notification via NotificationService
                    notification_service = NotificationService()

                    try:
                        if pref.method == NotificationMethod.EMAIL:
                            # Get user name for email greeting from primary email
                            user_name = None
                            if route.user and route.user.email_addresses:
                                # Find primary email or use first email
                                primary_email = next(
                                    (e for e in route.user.email_addresses if e.is_primary),
                                    route.user.email_addresses[0] if route.user.email_addresses else None,
                                )
                                if primary_email:
                                    user_name = primary_email.email

                            await notification_service.send_disruption_email(
                                email=contact_info,
                                route_name=route.name,
                                disruptions=disruptions,
                                user_name=user_name,
                            )
                        elif pref.method == NotificationMethod.SMS:
                            await notification_service.send_disruption_sms(
                                phone=contact_info,
                                route_name=route.name,
                                disruptions=disruptions,
                            )

                        # Create notification log entry (SENT status)
                        notification_log = NotificationLog(
                            user_id=route.user_id,
                            route_id=route.id,
                            sent_at=datetime.now(UTC),
                            method=pref.method,
                            status=NotificationStatus.SENT,
                            error_message=None,
                        )
                        self.db.add(notification_log)

                        alerts_sent += 1

                        logger.info(
                            "alert_sent_successfully",
                            method=pref.method.value,
                            target=contact_info,
                            route_id=str(route.id),
                            route_name=route.name,
                            disruption_count=len(disruptions),
                        )

                    except Exception as send_error:
                        logger.error(
                            "notification_send_failed",
                            pref_id=str(pref.id),
                            route_id=str(route.id),
                            method=pref.method.value,
                            error=str(send_error),
                            exc_info=send_error,
                        )

                        # Create notification log entry (FAILED status)
                        notification_log = NotificationLog(
                            user_id=route.user_id,
                            route_id=route.id,
                            sent_at=datetime.now(UTC),
                            method=pref.method,
                            status=NotificationStatus.FAILED,
                            error_message=str(send_error),
                        )
                        self.db.add(notification_log)

                        # Don't increment alerts_sent on failure
                        continue

                except Exception as e:
                    # Catch any other unexpected errors in preference processing
                    logger.error(
                        "preference_processing_failed",
                        pref_id=str(pref.id),
                        route_id=str(route.id),
                        error=str(e),
                        exc_info=e,
                    )

            # Commit all notification logs
            await self.db.commit()

            # If any alerts were sent successfully, store the disruption state in Redis
            if alerts_sent > 0:
                await self._store_alert_state(
                    route=route,
                    user_id=route.user_id,
                    schedule=schedule,
                    disruptions=disruptions,
                )

            logger.info(
                "alerts_sent_for_route",
                route_id=str(route.id),
                route_name=route.name,
                alerts_sent=alerts_sent,
            )

            return alerts_sent

        except Exception as e:
            logger.error(
                "send_alerts_for_route_failed",
                route_id=str(route.id),
                error=str(e),
                exc_info=e,
            )
            await self.db.rollback()
            return 0

    async def _store_alert_state(
        self,
        route: Route,
        user_id: UUID,
        schedule: RouteSchedule,
        disruptions: list[DisruptionResponse],
    ) -> None:
        """
        Store alert state in Redis with TTL until schedule end time.

        This enables hybrid deduplication: within a window, content-based deduplication
        prevents spam; between windows, expired keys allow fresh alerts.

        Args:
            route: Route the alert was sent for
            user_id: User ID for deduplication key
            schedule: Active schedule
            disruptions: Disruptions that were alerted
        """
        try:
            # Calculate TTL: seconds from now until schedule.end_time in route's timezone
            route_tz = ZoneInfo(route.timezone)
            now_utc = datetime.now(UTC)
            now_local = now_utc.astimezone(route_tz)

            # Create datetime for schedule end time today
            end_datetime = datetime.combine(now_local.date(), schedule.end_time, tzinfo=route_tz)

            # If end time has already passed today, set TTL to 0 (expire immediately)
            if end_datetime <= now_local:
                ttl_seconds = 0
                logger.warning(
                    "schedule_end_time_passed",
                    route_id=str(route.id),
                    schedule_id=str(schedule.id),
                    end_time=schedule.end_time.isoformat(),
                    current_time=now_local.time().isoformat(),
                )
            else:
                ttl_seconds = int((end_datetime - now_local).total_seconds())

            # Create disruption state
            disruption_hash = self._create_disruption_hash(disruptions)
            state_data = {
                "hash": disruption_hash,
                "disruptions": [
                    {
                        "line_id": d.line_id,
                        "status": d.status_severity_description,
                        "reason": d.reason or "",
                    }
                    for d in disruptions
                ],
                "stored_at": now_utc.isoformat(),
            }

            # Build Redis key
            redis_key = f"alert:{route.id}:{user_id}:{schedule.id}"

            # Store in Redis with TTL
            if ttl_seconds > 0:
                await self.redis_client.setex(
                    redis_key,
                    ttl_seconds,
                    json.dumps(state_data),
                )
                logger.info(
                    "alert_state_stored",
                    route_id=str(route.id),
                    redis_key=redis_key,
                    ttl_seconds=ttl_seconds,
                    disruption_hash=disruption_hash,
                )
            else:
                # TTL is 0 or negative, don't store (or store with minimal TTL)
                logger.debug(
                    "alert_state_not_stored",
                    route_id=str(route.id),
                    redis_key=redis_key,
                    reason="schedule_ended",
                )

        except Exception as e:
            logger.error(
                "store_alert_state_failed",
                route_id=str(route.id),
                error=str(e),
                exc_info=e,
            )
            # Don't raise - failure to store state shouldn't prevent alert sending

    def _create_disruption_hash(self, disruptions: list[DisruptionResponse]) -> str:
        """
        Create a stable hash of disruptions for comparison.

        Sorts disruptions by line_id to ensure consistent ordering,
        then hashes the relevant fields.

        Args:
            disruptions: List of disruptions

        Returns:
            SHA256 hash (hex digest) of disruption state
        """
        # Sort disruptions by line_id for stable ordering
        sorted_disruptions = sorted(disruptions, key=lambda d: d.line_id)

        # Build hash input from relevant fields
        hash_input = []
        for disruption in sorted_disruptions:
            hash_input.append(
                {
                    "line_id": disruption.line_id,
                    "status": disruption.status_severity_description,
                    "reason": disruption.reason or "",
                }
            )

        # Create JSON string and hash it
        hash_string = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
