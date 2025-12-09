"""Alert processing service for checking disruptions and sending notifications."""

import contextlib
import hashlib
import json
from datetime import UTC, datetime, time, timedelta
from itertools import groupby
from typing import TYPE_CHECKING, Any
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog

if TYPE_CHECKING:
    from opentelemetry.trace import Span
from sqlalchemy import and_, func, inspect, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.redis import RedisClientProtocol
from app.core.telemetry import service_span
from app.helpers.disruption_helpers import disruption_affects_route, extract_line_station_pairs
from app.helpers.soft_delete_filters import add_active_filter, get_active_children_for_parents
from app.models.notification import (
    NotificationLog,
    NotificationMethod,
    NotificationPreference,
    NotificationStatus,
)
from app.models.tfl import AlertDisabledSeverity, Line, LineDisruptionStateLog
from app.models.user import EmailAddress, PhoneNumber, User
from app.models.user_route import UserRoute, UserRouteSchedule
from app.models.user_route_index import UserRouteStationIndex
from app.schemas.tfl import ClearedLineInfo, DisruptionResponse
from app.services.notification_service import NotificationService
from app.services.tfl_service import TfLService
from app.utils.pii import hash_pii

logger = structlog.get_logger(__name__)

# Alert state format version (for Redis state storage)
ALERT_STATE_VERSION = 2


# ==================== Pure Helper Functions ====================
# Pure functions with no side effects for easy testing


def get_day_code(weekday: int) -> str:
    """
    Convert Python weekday integer to day code string.

    Pure function for easy testing without datetime dependencies.

    Args:
        weekday: Python weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)

    Returns:
        Day code string (MON, TUE, WED, THU, FRI, SAT, SUN)

    Example:
        >>> get_day_code(0)
        'MON'
        >>> get_day_code(6)
        'SUN'
    """
    return ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][weekday]


def is_time_in_schedule_window(
    current_time: time,
    current_day: str,
    days_of_week: list[str],
    start_time: time,
    end_time: time,
) -> bool:
    """
    Check if current time and day fall within a schedule window.

    Pure function for easy testing without datetime dependencies.

    Args:
        current_time: Current time (already converted to route timezone)
        current_day: Current day code (MON, TUE, WED, etc.)
        days_of_week: List of active day codes for this schedule
        start_time: Schedule start time
        end_time: Schedule end time

    Returns:
        True if current time is within the schedule window, False otherwise

    Example:
        >>> import datetime
        >>> is_time_in_schedule_window(
        ...     datetime.time(9, 0),
        ...     "MON",
        ...     ["MON", "TUE", "WED"],
        ...     datetime.time(8, 0),
        ...     datetime.time(10, 0)
        ... )
        True
        >>> is_time_in_schedule_window(
        ...     datetime.time(11, 0),
        ...     "MON",
        ...     ["MON", "TUE", "WED"],
        ...     datetime.time(8, 0),
        ...     datetime.time(10, 0)
        ... )
        False
    """
    if current_day not in days_of_week:
        return False
    return start_time <= current_time <= end_time


def filter_alertable_disruptions(
    disruptions: list[DisruptionResponse],
    disabled_severity_pairs: set[tuple[str, int]],
) -> list[DisruptionResponse]:
    """
    Filter disruptions to only include those that should trigger alerts.

    Removes disruptions with severity levels configured as non-alertable
    (e.g., "Good Service" with severity_level=10).

    Pure function for easy testing without database dependencies.

    Args:
        disruptions: List of disruptions to filter
        disabled_severity_pairs: Set of (mode_id, severity_level) pairs to exclude

    Returns:
        List of disruptions that should trigger alerts

    Example:
        >>> from app.schemas.tfl import DisruptionResponse
        >>> from datetime import UTC, datetime
        >>> disruptions = [
        ...     DisruptionResponse(
        ...         line_id="victoria",
        ...         line_name="Victoria",
        ...         mode="tube",
        ...         status_severity=10,
        ...         status_severity_description="Good Service",
        ...         created_at=datetime.now(UTC),
        ...     ),
        ...     DisruptionResponse(
        ...         line_id="northern",
        ...         line_name="Northern",
        ...         mode="tube",
        ...         status_severity=5,
        ...         status_severity_description="Severe Delays",
        ...         reason="Signal failure",
        ...         created_at=datetime.now(UTC),
        ...     ),
        ... ]
        >>> disabled = {("tube", 10)}
        >>> result = filter_alertable_disruptions(disruptions, disabled)
        >>> len(result)
        1
        >>> result[0].line_id
        'northern'
    """
    return [
        disruption
        for disruption in disruptions
        if (disruption.mode, disruption.status_severity) not in disabled_severity_pairs
    ]


def detect_cleared_lines(
    stored_lines: dict[str, dict[str, object]],
    current_alertable_line_ids: set[str],
    all_route_disruptions: list[DisruptionResponse],
    cleared_states: set[tuple[str, int]],
) -> list[ClearedLineInfo]:
    """
    Detect lines that have cleared from disrupted state.

    Identifies lines that were previously alerted on but are now in a "cleared" state
    (e.g., Good Service, No Issues) rather than just a "suppressed" state (e.g., Service Closed).

    Pure function for easy testing without database or Redis dependencies.

    Args:
        stored_lines: Previously alerted lines from Redis state (line_id -> state dict)
        current_alertable_line_ids: Set of line_ids with current alertable disruptions
        all_route_disruptions: Unfiltered route disruptions (includes Good Service, etc.)
        cleared_states: Set of (mode_id, severity_level) pairs that represent "cleared"

    Returns:
        List of ClearedLineInfo objects for lines that have cleared

    Example:
        >>> from app.schemas.tfl import DisruptionResponse, ClearedLineInfo
        >>> from datetime import UTC, datetime
        >>> # Victoria was disrupted, now Good Service
        >>> stored = {
        ...     "victoria": {
        ...         "severity": 6,
        ...         "status": "Severe Delays",
        ...         "full_hash": "abc123",
        ...         "last_sent_at": "2024-01-01T10:00:00Z",
        ...     }
        ... }
        >>> current_alertable = set()  # No current disruptions
        >>> all_disruptions = [
        ...     DisruptionResponse(
        ...         line_id="victoria",
        ...         line_name="Victoria",
        ...         mode="tube",
        ...         status_severity=10,
        ...         status_severity_description="Good Service",
        ...     )
        ... ]
        >>> cleared = {("tube", 10)}  # Good Service is a cleared state
        >>> result = detect_cleared_lines(stored, current_alertable, all_disruptions, cleared)
        >>> len(result)
        1
        >>> result[0].line_id
        'victoria'
        >>> result[0].current_status
        'Good Service'
    """
    cleared_lines: list[ClearedLineInfo] = []

    # Build lookup maps for efficiency
    current_status_by_line: dict[str, DisruptionResponse] = {
        disruption.line_id: disruption for disruption in all_route_disruptions
    }

    # Check each previously-alerted line
    for line_id, stored_line in stored_lines.items():
        # Skip if still in alertable disruptions
        if line_id in current_alertable_line_ids:
            continue

        # Get current status for this line
        current_disruption = current_status_by_line.get(line_id)
        if not current_disruption:
            # Line not in current data - don't treat as cleared (could be API issue)
            continue

        # Check if current state is a "cleared" state
        state_pair = (current_disruption.mode, current_disruption.status_severity)
        if state_pair not in cleared_states:
            # Not in a cleared state - it's suppressed (e.g., Service Closed)
            continue

        # Line has cleared! Create info object
        previous_severity = stored_line.get("severity")
        previous_status = stored_line.get("status")

        # Validate stored data
        if not isinstance(previous_severity, int) or not isinstance(previous_status, str):
            # Corrupted stored data - skip
            continue

        cleared_line = ClearedLineInfo(
            line_id=current_disruption.line_id,
            line_name=current_disruption.line_name,
            mode=current_disruption.mode,
            previous_severity=previous_severity,
            previous_status=previous_status,
            current_severity=current_disruption.status_severity,
            current_status=current_disruption.status_severity_description,
        )
        cleared_lines.append(cleared_line)

    return cleared_lines


def init_alert_processing_stats() -> dict[str, int]:
    """
    Initialize alert processing statistics dictionary.

    Pure function for easy testing.

    Returns:
        Dictionary with routes_checked, alerts_sent, and errors all set to 0

    Example:
        >>> stats = init_alert_processing_stats()
        >>> stats
        {'routes_checked': 0, 'alerts_sent': 0, 'errors': 0}
    """
    return {
        "routes_checked": 0,
        "alerts_sent": 0,
        "errors": 0,
    }


# Pure helper functions for testability
def create_line_aggregate_hash(disruptions: list[DisruptionResponse]) -> str:
    """
    Create aggregate hash for all statuses of a single line.

    Sorts disruptions by (severity, description, reason) for deterministic ordering.
    This ensures that multiple statuses for the same line (e.g., "Minor Delays" and
    "Part Suspended") produce a consistent hash regardless of API response order.

    Pure function for easy testing without database dependencies.

    Args:
        disruptions: List of disruptions for a single line (all must have same line_id)

    Returns:
        SHA256 hash string (64 characters)

    Example:
        >>> disruptions = [
        ...     DisruptionResponse(line_id="northern", status_severity=10,
        ...                        status_severity_description="Minor Delays", reason="Signal failure"),
        ...     DisruptionResponse(line_id="northern", status_severity=20,
        ...                        status_severity_description="Part Suspended", reason="Signal failure"),
        ... ]
        >>> hash1 = create_line_aggregate_hash(disruptions)
        >>> # Same disruptions in different order produce same hash
        >>> hash2 = create_line_aggregate_hash(list(reversed(disruptions)))
        >>> hash1 == hash2
        True
    """
    # Defensive: ensure all disruptions have the same line_id
    if disruptions and len({d.line_id for d in disruptions}) > 1:
        msg = "All disruptions must have the same line_id"
        raise ValueError(msg)

    # Sort disruptions by (severity, description, reason) for deterministic ordering
    sorted_statuses = sorted(
        disruptions,
        key=lambda d: (d.status_severity, d.status_severity_description, d.reason or ""),
    )

    # Build hash input from sorted disruptions
    # Normalize reasons: strip whitespace and treat empty/whitespace-only as empty string
    hash_input = [
        {
            "severity": d.status_severity,
            "status": d.status_severity_description,
            "reason": (d.reason or "").strip() or "",
        }
        for d in sorted_statuses
    ]

    # Create JSON string and hash it
    hash_string = json.dumps(hash_input, sort_keys=True)
    return hashlib.sha256(hash_string.encode()).hexdigest()


async def warm_up_line_state_cache(db: AsyncSession, redis_client: RedisClientProtocol) -> int:
    """
    Populate Redis with latest aggregate state hash per line from database.

    Called during application lifespan to rehydrate Redis cache after restart.
    This prevents re-logging existing states on first poll after server restart.

    For each line, fetches all log entries at the most recent detected_at timestamp
    (which may include multiple statuses for the same line), computes the aggregate
    hash, and stores it in Redis.

    Args:
        db: Database session for querying line_disruption_state_logs table
        redis_client: Redis client for cache storage

    Returns:
        Number of unique lines hydrated into Redis cache

    Example:
        >>> redis_client = await get_redis_client()
        >>> count = await warm_up_line_state_cache(db, redis_client)
        >>> print(count)
        12  # 12 unique lines with cached state
    """
    with service_span("alert.warm_up_cache", "alert-service") as span:
        span.set_attribute("cache.operation", "warmup")

        try:
            # Subquery to find max detected_at for each line_id
            # This represents the most recent polling moment for each line
            subq = (
                select(
                    LineDisruptionStateLog.line_id,
                    func.max(LineDisruptionStateLog.detected_at).label("max_detected_at"),
                )
                .group_by(LineDisruptionStateLog.line_id)
                .subquery()
            )

            # Get all log entries at the max timestamp for each line
            # (multiple statuses per line at same timestamp due to batch logging)
            stmt = select(LineDisruptionStateLog).join(
                subq,
                and_(
                    LineDisruptionStateLog.line_id == subq.c.line_id,
                    LineDisruptionStateLog.detected_at == subq.c.max_detected_at,
                ),
            )

            result = await db.execute(stmt)
            logs = list(result.scalars().all())

            if not logs:
                logger.info("line_state_cache_warmup_empty", message="no historical states to hydrate")
                span.set_attribute("cache.lines_hydrated", 0)
                span.set_attribute("cache.total_log_entries", 0)
                span.set_attribute("cache.success", True)
                return 0

            # Group logs by line_id and extract aggregate hash
            # All records for the same line at the same detected_at share the same state_hash
            # (since they're all part of the same aggregate state logged in one batch)
            logs_sorted = sorted(logs, key=lambda log: log.line_id)
            lines_hydrated = 0

            for line_id, group in groupby(logs_sorted, key=lambda log: log.line_id):
                statuses = list(group)

                # All statuses for this line have the same state_hash (aggregate hash)
                # Just pick the first one - they're all identical for records at same detected_at
                aggregate_hash = statuses[0].state_hash

                # Store in Redis (no TTL - persists until state changes)
                redis_key = f"line_state:{line_id}"
                await redis_client.set(redis_key, aggregate_hash)

                lines_hydrated += 1

            span.set_attribute("cache.lines_hydrated", lines_hydrated)
            span.set_attribute("cache.total_log_entries", len(logs))
            span.set_attribute("cache.success", True)

            logger.info(
                "line_state_cache_warmup_complete",
                lines_hydrated=lines_hydrated,
                total_log_entries=len(logs),
            )

            return lines_hydrated

        except Exception as e:
            # Log error but don't block application startup
            span.set_attribute("cache.success", False)
            span.set_attribute("cache.lines_hydrated", 0)
            span.set_attribute("cache.total_log_entries", 0)
            span.set_attribute("cache.error", True)
            span.set_attribute("cache.error_type", type(e).__name__)
            logger.error(
                "line_state_cache_warmup_failed",
                error=str(e),
                exc_info=e,
            )
            return 0


class AlertService:
    """Service for processing route alerts and sending notifications."""

    def __init__(self, db: AsyncSession, redis_client: RedisClientProtocol) -> None:
        """
        Initialize the alert service.

        Args:
            db: Database session
            redis_client: Redis client for deduplication
        """
        self.db = db
        self.redis_client = redis_client

    async def _log_line_disruption_state_changes(
        self,
        disruptions: list[DisruptionResponse],
    ) -> int:
        """
        Log line disruption state changes to database for troubleshooting and analytics.

        Groups disruptions by line and compares aggregate state hash against Redis cache.
        Only logs when the aggregate state for a line changes (e.g., new status added,
        status removed, or status details changed).

        Multiple statuses for the same line (e.g., "Minor Delays" + "Part Suspended")
        are stored as separate database records but share the same detected_at timestamp.

        Args:
            disruptions: List of current disruptions from TfL API

        Returns:
            Number of state changes logged (new log entries created)

        Example:
            >>> # First call with disruptions
            >>> await service._log_line_disruption_state_changes([disruption1, disruption2])
            2  # Logged because first state
            >>> # Second call with same disruptions
            >>> await service._log_line_disruption_state_changes([disruption1, disruption2])
            0  # Not logged because aggregate hash unchanged
            >>> # Third call with different aggregate state
            >>> await service._log_line_disruption_state_changes([disruption1, disruption3])
            2  # Logged because aggregate state changed
        """
        with service_span(
            "alert.log_line_state_changes",
            "alert-service",
        ) as span:
            span.set_attribute("alert.operation", "log_line_state_changes")
            span.set_attribute("alert.disruption_count", len(disruptions))

            try:
                logged_count = 0

                if not disruptions:
                    span.set_attribute("alert.logged_count", 0)
                    return 0

                # Use single timestamp for all records in this batch
                # This represents the polling moment and groups related statuses
                batch_detected_at = datetime.now(UTC)

                # Group disruptions by line_id
                disruptions_sorted = sorted(disruptions, key=lambda d: d.line_id)
                disruptions_by_line = {
                    line_id: list(group) for line_id, group in groupby(disruptions_sorted, key=lambda d: d.line_id)
                }

                # Process each line's aggregate state
                for line_id, line_disruptions in disruptions_by_line.items():
                    # Compute aggregate hash for this line's current state
                    current_hash = create_line_aggregate_hash(line_disruptions)

                    # Check Redis for last known aggregate hash for this line
                    redis_key = f"line_state:{line_id}"
                    last_hash = await self.redis_client.get(redis_key)

                    # Only log if aggregate state changed
                    if current_hash != last_hash:
                        # Log each status as a separate database record
                        for disruption in line_disruptions:
                            new_log = LineDisruptionStateLog(
                                line_id=line_id,
                                status_severity_description=disruption.status_severity_description,
                                reason=disruption.reason or None,
                                state_hash=current_hash,  # Store aggregate hash, not individual
                                detected_at=batch_detected_at,
                            )
                            self.db.add(new_log)
                            logged_count += 1

                        # Update Redis with new aggregate hash (no TTL - persists until state changes)
                        # Note: Redis is updated before commit intentionally. If commit fails,
                        # Redis will be ahead of DB, but the next poll will re-detect the state
                        # change (since DB won't have the new hash). This prioritizes preventing
                        # duplicate logs over strict consistency.
                        await self.redis_client.set(redis_key, current_hash)

                        logger.info(
                            "line_aggregate_state_changed",
                            line_id=line_id,
                            status_count=len(line_disruptions),
                            previous_hash=last_hash,
                            new_hash=current_hash,
                        )
                    else:
                        logger.debug(
                            "line_aggregate_state_unchanged",
                            line_id=line_id,
                            status_count=len(line_disruptions),
                            state_hash=current_hash,
                        )

                # Commit all new log entries
                if logged_count > 0:
                    await self.db.commit()
                    logger.info("line_disruption_states_logged", count=logged_count)

                span.set_attribute("alert.logged_count", logged_count)
                return logged_count

            except Exception as e:
                logger.error(
                    "log_line_disruption_states_failed",
                    error=str(e),
                    exc_info=e,
                )
                span.record_exception(e)
                await self.db.rollback()
                span.set_attribute("alert.logged_count", 0)
                # Don't raise - logging failures shouldn't block alert processing
                return 0

    def _set_span_stats_attributes(self, span: "Span", stats: dict[str, int]) -> None:
        """
        Set alert processing statistics as span attributes.

        Args:
            span: OpenTelemetry span to set attributes on
            stats: Statistics dictionary with routes_checked, alerts_sent, errors
        """
        span.set_attribute("alert.routes_checked", stats["routes_checked"])
        span.set_attribute("alert.alerts_sent", stats["alerts_sent"])
        span.set_attribute("alert.errors", stats["errors"])

    async def process_all_routes(self) -> dict[str, Any]:
        """
        Main entry point for processing all active routes.

        Orchestrates the alert processing workflow:
        1. Fetch all active routes
        2. Fetch global disruption data (cached, reused for all routes)
        3. Process each route individually
        4. Return statistics

        Returns:
            Statistics dictionary with routes_checked, alerts_sent, and errors
        """
        with service_span("alert.process_all_routes", "alert-service") as span:
            logger.info("alert_processing_started")
            stats = init_alert_processing_stats()

            try:
                # Fetch all active routes with relationships
                routes = await self._get_active_routes()
                logger.info("active_routes_fetched", count=len(routes))

                # Batch load active schedules for all routes (filtered for soft-delete)
                route_ids = [route.id for route in routes]
                schedules_by_route = await get_active_children_for_parents(
                    self.db, UserRouteSchedule, UserRouteSchedule.route_id, route_ids
                )
                logger.debug("active_schedules_loaded", route_count=len(routes))

                # Fetch global disruption data once for all routes
                # Errors are non-fatal - returns empty data on failure
                disabled_severity_pairs, cleared_states = await self._fetch_global_disruption_data()

                # Process each route individually
                for route in routes:
                    stats["routes_checked"] += 1

                    # Get active schedules for this route
                    route_schedules = schedules_by_route.get(route.id, [])

                    # Process this route and collect results
                    alerts_sent, error_occurred = await self._process_single_route(
                        route=route,
                        schedules=route_schedules,
                        disabled_severity_pairs=disabled_severity_pairs,
                        cleared_states=cleared_states,
                    )

                    stats["alerts_sent"] += alerts_sent
                    if error_occurred:
                        stats["errors"] += 1

                logger.info("alert_processing_completed", **stats)

            except Exception as e:
                logger.error("alert_processing_failed", error=str(e), exc_info=e)
                stats["errors"] += 1

            finally:
                # Always set span attributes, even on error
                self._set_span_stats_attributes(span, stats)

            return stats

    async def _get_active_routes(self) -> list[UserRoute]:
        """
        Get all active routes with their relationships.

        Returns:
            List of active UserRoute objects with segments, schedules, preferences, and user loaded
        """
        try:
            result = await self.db.execute(
                select(UserRoute)
                .where(
                    UserRoute.active == True,  # noqa: E712
                    UserRoute.deleted_at.is_(None),
                )
                .options(
                    selectinload(UserRoute.segments),
                    # NOTE: Schedules are loaded separately with soft-delete filter
                    # to avoid including soft-deleted schedules (Issue #233, PR #360)
                    selectinload(UserRoute.notification_preferences),
                    selectinload(UserRoute.user).selectinload(User.email_addresses),
                )
            )
            return list(result.scalars().all())

        except SQLAlchemyError as e:
            logger.error("fetch_active_routes_failed", error=str(e), exc_info=e)
            return []

    async def _fetch_global_disruption_data(self) -> tuple[set[tuple[str, int]], set[tuple[str, int]]]:
        """
        Fetch all disruptions and disabled severities once for all routes.

        This method fetches global disruption data that can be reused across all routes:
        - All line disruptions (cached by TfL service)
        - Disabled severity pairs for filtering
        - Cleared state pairs (for detecting when lines return to normal)

        Internally uses disruptions for state change logging.

        Errors are non-fatal - returns empty data on failure so per-route processing can continue.

        Returns:
            Tuple of (disabled_severity_pairs, cleared_states)
            - disabled_severity_pairs: Set of (mode_id, severity_level) pairs that should not trigger alerts
            - cleared_states: Set of (mode_id, severity_level) pairs that represent cleared/normal states
        """
        disabled_severity_pairs: set[tuple[str, int]] = set()
        cleared_states: set[tuple[str, int]] = set()

        # Step 1: ALWAYS fetch disabled severity pairs and cleared states first (critical for filtering)
        # This query must succeed regardless of TfL API status
        try:
            disabled_result = await self.db.execute(select(AlertDisabledSeverity))
            all_disabled_severities = disabled_result.scalars().all()
            disabled_severity_pairs = {(d.mode_id, d.severity_level) for d in all_disabled_severities}
            cleared_states = {(d.mode_id, d.severity_level) for d in all_disabled_severities if d.is_cleared_state}
        except SQLAlchemyError as e:
            logger.error(
                "fetch_disabled_severities_failed",
                error=str(e),
                exc_info=e,
                critical=True,
            )
            # Return empty sets on DB failure - this is a critical error
            # Per-route processing will still work but won't filter properly
            return disabled_severity_pairs, cleared_states

        # Step 2: Try to fetch disruptions for state logging (optional, for analytics)
        # Failure here should not prevent alert processing
        try:
            tfl_service = TfLService(db=self.db)
            all_disruptions = await tfl_service.fetch_line_disruptions(use_cache=True)
            logger.info("all_disruptions_fetched", count=len(all_disruptions))

            # Log line disruption state changes (for troubleshooting and analytics)
            await self._log_line_disruption_state_changes(all_disruptions)

        except Exception as e:
            logger.error(
                "disruption_state_logging_failed",
                error=str(e),
                exc_info=e,
            )
            # Don't track as error - per-route processing will handle its own disruptions
            # This is just for centralized logging

        return disabled_severity_pairs, cleared_states

    async def _get_active_schedule(
        self,
        route: UserRoute,
        schedules: list[UserRouteSchedule],
    ) -> UserRouteSchedule | None:
        """
        Check if the route is currently in any active schedule window.

        Converts UTC now to route's timezone and checks against schedule windows.

        Args:
            route: UserRoute to check schedules for
            schedules: List of active (non-deleted) schedules for the route

        Returns:
            The first matching active schedule, or None if not in any schedule
        """
        try:
            # Get current time in route's timezone
            route_tz = ZoneInfo(route.timezone)
            now_utc = datetime.now(UTC)
            now_local = now_utc.astimezone(route_tz)

            current_time = now_local.time()
            current_day = get_day_code(now_local.weekday())

            logger.debug(
                "checking_schedule",
                route_id=str(route.id),
                timezone=route.timezone,
                current_time=current_time.isoformat(),
                current_day=current_day,
            )

            # Check provided schedules (already filtered for soft-delete by caller)
            schedules_to_check = schedules

            # Check each schedule
            for schedule in schedules_to_check:
                # Check if current time is within schedule window
                if is_time_in_schedule_window(
                    current_time=current_time,
                    current_day=current_day,
                    days_of_week=schedule.days_of_week,
                    start_time=schedule.start_time,
                    end_time=schedule.end_time,
                ):
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

    async def _query_routes_by_index(
        self,
        line_station_pairs: list[tuple[str, str]],
    ) -> set[UUID]:
        """
        Query inverted index for routes passing through (line, station) combinations.

        Args:
            line_station_pairs: List of (line_tfl_id, station_naptan) tuples

        Returns:
            Set of unique route IDs matching any of the pairs
        """
        if not line_station_pairs:
            return set()

        # Build a single query with OR conditions for all (line, station) pairs
        conditions = [
            and_(
                UserRouteStationIndex.line_tfl_id == line_tfl_id,
                UserRouteStationIndex.station_naptan == station_naptan,
            )
            for line_tfl_id, station_naptan in line_station_pairs
        ]

        query = select(UserRouteStationIndex.route_id).where(or_(*conditions))
        query = add_active_filter(query, UserRouteStationIndex)
        result = await self.db.execute(query)
        route_ids = {row[0] for row in result.all()}

        logger.info(
            "index_query_completed",
            total_pairs_queried=len(line_station_pairs),
            unique_routes_found=len(route_ids),
        )

        return route_ids

    async def _get_route_index_pairs(self, route_id: UUID) -> set[tuple[str, str]]:
        """
        Get (line_tfl_id, station_naptan) pairs for a specific route from the index.

        Args:
            route_id: UserRoute ID to get index pairs for

        Returns:
            Set of (line_tfl_id, station_naptan) tuples for this route
        """
        query = select(
            UserRouteStationIndex.line_tfl_id,
            UserRouteStationIndex.station_naptan,
        ).where(UserRouteStationIndex.route_id == route_id)
        query = add_active_filter(query, UserRouteStationIndex)
        result = await self.db.execute(query)
        return {(row[0], row[1]) for row in result.all()}

    async def _get_affected_routes_for_disruption(
        self,
        disruption: DisruptionResponse,
    ) -> set[UUID]:
        """
        Find routes affected by disruption using inverted index.

        Algorithm:
        1. If disruption.affected_routes exists (station-level data):
           - Query index for each (line_id, station_naptan) combination
           - Return union of matching route_ids (deduplication automatic via set)
        2. Else (no detailed station data - SHOULD BE RARE):
           - Fall back to line-level matching (current behavior)
           - Log warning as this indicates missing TfL data

        Complexity: O(affected_stations x log(index_size))
        NOT O(routes) - key optimization!

        Args:
            disruption: Disruption response from TfL

        Returns:
            Set of route IDs affected by this disruption
        """
        # Extract (line, station) pairs from disruption
        if line_station_pairs := extract_line_station_pairs(disruption):
            # Use inverted index for station-level matching
            logger.debug(
                "using_index_for_disruption_matching",
                disruption_line=disruption.line_id,
                station_count=len(line_station_pairs),
            )

            affected_route_ids = await self._query_routes_by_index(line_station_pairs)

            logger.info(
                "index_based_matching_completed",
                disruption_line=disruption.line_id,
                affected_stations=len(line_station_pairs),
                matching_routes=len(affected_route_ids),
            )

            return affected_route_ids

        # FALLBACK: No station-level data available
        # This should be rare with current TfL API but can happen for some disruption types
        logger.warning(
            "no_station_data_falling_back_to_line_level",
            disruption_line=disruption.line_id,
            disruption_severity=disruption.status_severity_description,
            reason=disruption.reason,
        )

        # Fall back to line-level matching: find all routes using this line
        result = await self.db.execute(select(Line.id).where(Line.tfl_id == disruption.line_id))
        line_db_id = result.scalar_one_or_none()

        if not line_db_id:
            logger.error(
                "line_not_found_in_database",
                disruption_line=disruption.line_id,
            )
            return set()

        # Query all routes that have segments on this line
        result = await self.db.execute(
            select(UserRoute.id)
            .where(
                UserRoute.segments.any(line_id=line_db_id),
                UserRoute.active.is_(True),
                UserRoute.deleted_at.is_(None),
            )
            .distinct()
        )
        affected_route_ids = {row[0] for row in result.all()}

        logger.info(
            "line_level_fallback_completed",
            disruption_line=disruption.line_id,
            matching_routes=len(affected_route_ids),
        )

        return affected_route_ids

    async def _get_route_disruptions(
        self,
        route: UserRoute,
        disabled_severity_pairs: set[tuple[str, int]],
    ) -> tuple[list[DisruptionResponse], list[DisruptionResponse], bool]:
        """
        Get current disruptions affecting this route using inverted index.

        Uses station-level matching via UserRouteStationIndex for precision.
        Falls back to line-level matching only when TfL doesn't provide station data.

        Args:
            route: UserRoute to get disruptions for
            disabled_severity_pairs: Set of (mode_id, severity_level) pairs to filter out

        Returns:
            Tuple of (filtered_disruptions, unfiltered_disruptions, error_occurred)
            - filtered_disruptions: Alertable disruptions (non-disabled severities)
            - unfiltered_disruptions: All route disruptions (for cleared line detection)
            - error_occurred: True if an error occurred during processing
        """
        try:
            # Get this route's (line, station) pairs from index once
            route_index_pairs = await self._get_route_index_pairs(route.id)

            # Extract unique line IDs for fallback matching
            route_line_ids: set[str]
            if route_index_pairs:
                route_line_ids = {line_tfl_id for line_tfl_id, _ in route_index_pairs}
            else:
                # Fallback: extract line IDs from segments if index is not populated
                # This handles newly created routes before index is built
                line_db_ids = {segment.line_id for segment in route.segments if segment.line_id}
                route_line_ids = set()
                if line_db_ids:
                    result = await self.db.execute(select(Line.tfl_id).where(Line.id.in_(line_db_ids)))
                    route_line_ids = {row[0] for row in result.all()}

            # Create TfL service instance
            tfl_service = TfLService(db=self.db)

            # Fetch all line disruptions (uses cache automatically)
            all_disruptions = await tfl_service.fetch_line_disruptions(use_cache=True)

            # Check each disruption against this route's index pairs
            route_disruptions: list[DisruptionResponse] = []

            for disruption in all_disruptions:
                # Check if disruption affects this route
                if disruption_pairs := extract_line_station_pairs(disruption):
                    # Station-level matching: check for intersection
                    if disruption_affects_route(disruption_pairs, route_index_pairs):
                        route_disruptions.append(disruption)
                # Fallback: line-level matching when no station data available
                elif disruption.line_id in route_line_ids:
                    route_disruptions.append(disruption)

            # Keep unfiltered disruptions for cleared line detection
            unfiltered_route_disruptions = route_disruptions.copy()

            # Filter disruptions by severity (remove non-alertable severities like "Good Service")
            before_filter_count = len(route_disruptions)
            route_disruptions = filter_alertable_disruptions(route_disruptions, disabled_severity_pairs)
            filtered_count = before_filter_count - len(route_disruptions)

            logger.debug(
                "route_disruptions_filtered",
                route_id=str(route.id),
                total_disruptions=len(all_disruptions),
                route_disruptions=len(route_disruptions),
                filtered_count=filtered_count,
            )

            return route_disruptions, unfiltered_route_disruptions, False

        except Exception as e:
            logger.error(
                "get_route_disruptions_failed",
                route_id=str(route.id),
                error=str(e),
                exc_info=e,
            )
            return [], [], True

    async def _get_cleared_states(self) -> set[tuple[str, int]]:
        """
        Get (mode_id, severity_level) pairs that represent cleared states.

        Cleared states are severities marked with is_cleared_state=True
        in the alert_disabled_severities table (e.g., Good Service, No Issues).

        Returns:
            Set of (mode_id, severity_level) tuples for cleared states
        """
        try:
            result = await self.db.execute(
                select(AlertDisabledSeverity).where(AlertDisabledSeverity.is_cleared_state == True)  # noqa: E712
            )
            cleared_states = {(d.mode_id, d.severity_level) for d in result.scalars().all()}
            logger.debug("cleared_states_fetched", count=len(cleared_states))
            return cleared_states
        except Exception as e:
            logger.error(
                "fetch_cleared_states_failed",
                error=str(e),
                exc_info=e,
            )
            # Return empty set on error - cleared detection will be skipped
            return set()

    async def _should_send_alert(
        self,
        route: UserRoute,
        user_id: UUID,
        schedule: UserRouteSchedule,
        disruptions: list[DisruptionResponse],
    ) -> tuple[bool, list[DisruptionResponse], dict[str, dict[str, object]]]:
        """
        Check if we should send an alert, with per-line cooldown logic.

        Uses Redis to track per-line disruption state within a schedule window.
        Applies cooldown to prevent spam from TfL API flickering, but bypasses
        cooldown if severity/status changes (important updates go through immediately).

        Args:
            route: UserRoute to check
            user_id: User ID for deduplication key
            schedule: Active schedule
            disruptions: Current disruptions

        Returns:
            Tuple of (should_send, filtered_disruptions, stored_lines):
            - should_send: True if alert should be sent, False if all lines are within cooldown
            - filtered_disruptions: Only disruptions for lines that passed cooldown check
            - stored_lines: Previously alerted lines from Redis state (for cleared detection)
        """
        with service_span("alert.should_send_check", "alert-service") as span:
            span.set_attribute("alert.route_id", str(route.id))
            span.set_attribute("alert.user_id", str(user_id))
            span.set_attribute("alert.schedule_id", str(schedule.id))

            try:
                # Build Redis key for this route/user/schedule combination
                redis_key = f"alert:{route.id}:{user_id}:{schedule.id}"

                # Check if key exists in Redis
                stored_state = await self.redis_client.get(redis_key)
                stored_lines: dict[str, dict[str, object]] = {}

                if stored_state:
                    try:
                        stored_data = json.loads(stored_state)
                        # Ignore non-v2 state (will expire within schedule window anyway)
                        if stored_data.get("version") == ALERT_STATE_VERSION:
                            stored_lines = stored_data.get("lines", {})
                    except (json.JSONDecodeError, AttributeError):
                        logger.warning(
                            "invalid_stored_alert_state",
                            route_id=str(route.id),
                            redis_key=redis_key,
                        )

                # Group current disruptions by line
                disruptions_by_line = self._group_disruptions_by_line(disruptions)

                now_utc = datetime.now(UTC)
                cooldown = timedelta(minutes=settings.ALERT_COOLDOWN_MINUTES)

                # Check each line against stored state and cooldown
                lines_to_alert = [
                    line_id
                    for line_id, line_disruptions in disruptions_by_line.items()
                    if self._check_line_alert_needed(
                        line_id=line_id,
                        line_disruptions=line_disruptions,
                        stored_line=stored_lines.get(line_id),
                        now_utc=now_utc,
                        cooldown=cooldown,
                        route_id=str(route.id),
                    )
                ]

                if not lines_to_alert:
                    # No lines passed the check
                    logger.debug(
                        "all_lines_within_cooldown",
                        route_id=str(route.id),
                        total_lines=len(disruptions_by_line),
                    )
                    span.set_attribute("alert.has_previous_state", bool(stored_lines))
                    span.set_attribute("alert.state_changed", False)
                    span.set_attribute("alert.result", False)
                    span.set_attribute("alert.lines_checked", len(disruptions_by_line))
                    span.set_attribute("alert.lines_to_alert", 0)
                    return False, [], stored_lines

                # Filter disruptions to only include lines that passed the check
                filtered_disruptions = [d for d in disruptions if d.line_id in lines_to_alert]

                logger.info(
                    "alert_approved",
                    route_id=str(route.id),
                    lines_to_alert=lines_to_alert,
                    total_lines=len(disruptions_by_line),
                )
                span.set_attribute("alert.has_previous_state", bool(stored_lines))
                span.set_attribute("alert.state_changed", True)
                span.set_attribute("alert.result", True)
                span.set_attribute("alert.lines_checked", len(disruptions_by_line))
                span.set_attribute("alert.lines_to_alert", len(lines_to_alert))

                return True, filtered_disruptions, stored_lines

            except Exception as e:
                logger.error(
                    "should_send_alert_check_failed",
                    route_id=str(route.id),
                    error=str(e),
                    exc_info=e,
                )
                # Set consistent attributes for telemetry even in error case
                span.set_attribute("alert.has_previous_state", False)  # Unknown due to error
                span.set_attribute("alert.state_changed", True)  # Treating as changed (conservative)
                span.set_attribute("alert.result", True)
                span.set_attribute("alert.error", True)
                span.set_attribute("alert.error_type", type(e).__name__)
                # On error, default to sending alert (better to over-notify than under-notify)
                return True, disruptions, {}

    async def _get_verified_contact(  # noqa: PLR0911
        self,
        pref: NotificationPreference,
        route_id: UUID,
    ) -> str | None:
        """
        Get verified contact information for a notification preference.

        Args:
            pref: Notification preference
            route_id: UserRoute ID for logging

        Returns:
            Contact string (email or phone) if verified, None otherwise
        """
        if pref.method == NotificationMethod.EMAIL:
            if not pref.target_email_id:
                logger.warning(
                    "email_preference_missing_target",
                    pref_id=str(pref.id),
                    route_id=str(route_id),
                )
                return None

            email_result = await self.db.execute(select(EmailAddress).where(EmailAddress.id == pref.target_email_id))
            email_address = email_result.scalar_one_or_none()

            if not email_address or not email_address.verified:
                logger.warning(
                    "email_not_verified",
                    pref_id=str(pref.id),
                    route_id=str(route_id),
                    email_id=str(pref.target_email_id) if pref.target_email_id else None,
                )
                return None

            return email_address.email

        if pref.method == NotificationMethod.SMS:
            if not pref.target_phone_id:
                logger.warning(
                    "sms_preference_missing_target",
                    pref_id=str(pref.id),
                    route_id=str(route_id),
                )
                return None

            phone_result = await self.db.execute(select(PhoneNumber).where(PhoneNumber.id == pref.target_phone_id))
            phone_number = phone_result.scalar_one_or_none()

            if not phone_number or not phone_number.verified:
                logger.warning(
                    "phone_not_verified",
                    pref_id=str(pref.id),
                    route_id=str(route_id),
                    phone_id=str(pref.target_phone_id) if pref.target_phone_id else None,
                )
                return None

            return phone_number.phone

        # Edge case: Unknown notification method
        # This code path is unreachable in practice because NotificationMethod is an enum
        # validated by Pydantic. This defensive logging remains for completeness.
        logger.warning(
            "unknown_notification_method",
            pref_id=str(pref.id),
            method=pref.method,
        )
        return None

    def _get_user_display_name(self, route: UserRoute) -> str | None:
        """
        Get user display name from their primary email address.

        Args:
            route: UserRoute with user relationship loaded

        Returns:
            User's email or None
        """
        if not route.user or not route.user.email_addresses:
            return None

        # Find primary email or use first email
        primary_email = next(
            (e for e in route.user.email_addresses if e.is_primary),
            route.user.email_addresses[0] if route.user.email_addresses else None,
        )

        return primary_email.email if primary_email else None

    def _create_notification_log(
        self,
        user_id: UUID,
        route_id: UUID,
        method: NotificationMethod,
        status: NotificationStatus,
        error_message: str | None = None,
    ) -> None:
        """
        Create a notification log entry and add to database session.

        Args:
            user_id: User ID
            route_id: UserRoute ID
            method: Notification method
            status: Notification status
            error_message: Optional error message
        """
        notification_log = NotificationLog(
            user_id=user_id,
            route_id=route_id,
            sent_at=datetime.now(UTC),
            method=method,
            status=status,
            error_message=error_message,
        )
        self.db.add(notification_log)

    async def _send_single_notification(
        self,
        pref: NotificationPreference,
        contact_info: str,
        route: UserRoute,
        disruptions: list[DisruptionResponse],
    ) -> tuple[bool, str | None]:
        """
        Send a single notification via the appropriate method.

        Args:
            pref: Notification preference
            contact_info: Contact string (email or phone)
            route: UserRoute being alerted
            disruptions: List of disruptions

        Returns:
            Tuple of (success, error_message)
            - success: True if sent successfully, False otherwise
            - error_message: Error message if failed, None if successful
        """
        try:
            notification_service = NotificationService()

            if pref.method == NotificationMethod.EMAIL:
                user_name = self._get_user_display_name(route)
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

            logger.info(
                "alert_sent_successfully",
                method=pref.method.value,
                target_hash=hash_pii(contact_info),
                route_id=str(route.id),
                route_name=route.name,
                disruption_count=len(disruptions),
            )
            return True, None

        except Exception as send_error:
            logger.error(
                "notification_send_failed",
                pref_id=str(pref.id),
                route_id=str(route.id),
                method=pref.method.value,
                error=str(send_error),
                exc_info=send_error,
            )
            return False, str(send_error)

    async def _send_single_status_update(
        self,
        pref: NotificationPreference,
        contact_info: str,
        route: UserRoute,
        cleared_lines: list[ClearedLineInfo],
        still_disrupted: list[DisruptionResponse],
    ) -> tuple[bool, str | None]:
        """
        Send a single status update notification via the appropriate method.

        Args:
            pref: Notification preference
            contact_info: Contact string (email or phone)
            route: UserRoute being updated
            cleared_lines: Lines that have returned to normal service
            still_disrupted: Lines that remain disrupted

        Returns:
            Tuple of (success, error_message)
            - success: True if sent successfully, False otherwise
            - error_message: Error message if failed, None if successful
        """
        try:
            notification_service = NotificationService()

            if pref.method == NotificationMethod.EMAIL:
                user_name = self._get_user_display_name(route)
                await notification_service.send_status_update_email(
                    email=contact_info,
                    route_name=route.name,
                    cleared_lines=cleared_lines,
                    still_disrupted=still_disrupted,
                    user_name=user_name,
                )
            elif pref.method == NotificationMethod.SMS:
                await notification_service.send_status_update_sms(
                    phone=contact_info,
                    route_name=route.name,
                    cleared_lines=cleared_lines,
                    still_disrupted=still_disrupted,
                )

            logger.info(
                "status_update_sent_successfully",
                method=pref.method.value,
                target_hash=hash_pii(contact_info),
                route_id=str(route.id),
                route_name=route.name,
                cleared_count=len(cleared_lines),
                still_disrupted_count=len(still_disrupted),
            )
            return True, None

        except Exception as send_error:
            logger.error(
                "status_update_send_failed",
                pref_id=str(pref.id),
                route_id=str(route.id),
                method=pref.method.value,
                error=str(send_error),
                exc_info=send_error,
            )
            return False, str(send_error)

    async def _send_status_update_notifications(
        self,
        route: UserRoute,
        schedule: UserRouteSchedule,
        cleared_lines: list[ClearedLineInfo],
        still_disrupted: list[DisruptionResponse],
    ) -> int:
        """
        Send status update notifications for a route to all configured notification preferences.

        Args:
            route: UserRoute to send status updates for
            schedule: Active schedule
            cleared_lines: Lines that have returned to normal service
            still_disrupted: Lines that remain disrupted

        Returns:
            Number of status updates successfully sent
        """
        with service_span(
            "alert.send_status_update",
            "alert-service",
        ) as span:
            # Set span attributes
            span.set_attribute("alert.route_id", str(route.id))
            span.set_attribute("alert.route_name", route.name)
            span.set_attribute("alert.cleared_count", len(cleared_lines))
            span.set_attribute("alert.still_disrupted_count", len(still_disrupted))

            updates_sent = 0
            # Initialize prefs outside try block so it's accessible in except block
            prefs: list[NotificationPreference] = []

            try:
                # Get notification preferences safely (may not be loaded in async context)
                try:
                    insp = inspect(route)
                    prefs = [] if "notification_preferences" in insp.unloaded else route.notification_preferences or []
                except Exception:
                    # Can't inspect (e.g., Mock object in tests) - try direct access
                    prefs = route.notification_preferences or []

                # Check if route has notification preferences
                if not prefs:
                    logger.warning(
                        "no_notification_preferences_for_status_update",
                        route_id=str(route.id),
                        route_name=route.name,
                    )
                    span.set_attribute("alert.preference_count", 0)
                    span.set_attribute("alert.updates_sent", 0)
                    return 0

                # Process each notification preference
                for pref in prefs:
                    try:
                        # Get verified contact information
                        contact_info = await self._get_verified_contact(pref, route.id)
                        if not contact_info:
                            continue

                        # Send status update notification
                        success, error_message = await self._send_single_status_update(
                            pref=pref,
                            contact_info=contact_info,
                            route=route,
                            cleared_lines=cleared_lines,
                            still_disrupted=still_disrupted,
                        )

                        # Create notification log
                        if success:
                            self._create_notification_log(
                                user_id=route.user_id,
                                route_id=route.id,
                                method=pref.method,
                                status=NotificationStatus.SENT,
                            )
                            updates_sent += 1
                        else:
                            self._create_notification_log(
                                user_id=route.user_id,
                                route_id=route.id,
                                method=pref.method,
                                status=NotificationStatus.FAILED,
                                error_message=error_message,
                            )

                    except Exception as e:
                        # Catch any other unexpected errors in preference processing
                        logger.error(
                            "preference_processing_failed_for_status_update",
                            pref_id=str(pref.id),
                            route_id=str(route.id),
                            error=str(e),
                            exc_info=e,
                        )

                # Commit all notification logs
                await self.db.commit()

                # If any status updates were sent successfully, remove cleared lines from Redis state
                if updates_sent > 0:
                    await self._update_alert_state_remove_cleared(
                        route=route,
                        user_id=route.user_id,
                        schedule=schedule,
                        cleared_line_ids=[cl.line_id for cl in cleared_lines],
                    )

                # Set span attributes at the end
                span.set_attribute("alert.preference_count", len(prefs))
                span.set_attribute("alert.updates_sent", updates_sent)

                logger.info(
                    "status_updates_sent_for_route",
                    route_id=str(route.id),
                    route_name=route.name,
                    updates_sent=updates_sent,
                )

                return updates_sent

            except Exception as e:
                logger.error(
                    "send_status_updates_for_route_failed",
                    route_id=str(route.id),
                    error=str(e),
                    exc_info=e,
                )
                await self.db.rollback()
                # Set span attributes even on error (preserve prefs count if we got it)
                try:
                    pref_count = len(prefs) if isinstance(prefs, list) else 0
                except (TypeError, AttributeError):
                    pref_count = 0
                span.set_attribute("alert.preference_count", pref_count)
                span.set_attribute("alert.updates_sent", updates_sent)
                return 0

    async def _update_alert_state_remove_cleared(
        self,
        route: UserRoute,
        user_id: UUID,
        schedule: UserRouteSchedule,
        cleared_line_ids: list[str],
    ) -> None:
        """
        Remove cleared lines from the alert state in Redis.

        After sending status update notifications for cleared lines,
        we remove them from the stored state so we don't continue tracking them.

        Args:
            route: UserRoute the status update was sent for
            user_id: User ID for deduplication key
            schedule: Active schedule
            cleared_line_ids: List of line IDs that have cleared
        """
        with service_span("alert.remove_cleared_from_state", "alert-service") as span:
            span.set_attribute("alert.route_id", str(route.id))
            span.set_attribute("alert.user_id", str(user_id))
            span.set_attribute("alert.schedule_id", str(schedule.id))
            span.set_attribute("alert.cleared_count", len(cleared_line_ids))

            try:
                # Build Redis key
                redis_key = f"alert:{route.id}:{user_id}:{schedule.id}"

                # Get existing state
                existing_state = await self.redis_client.get(redis_key)
                if not existing_state:
                    logger.debug(
                        "no_existing_state_to_update",
                        route_id=str(route.id),
                        redis_key=redis_key,
                    )
                    return

                # Parse existing state
                try:
                    state_data = json.loads(existing_state)
                    if state_data.get("version") != ALERT_STATE_VERSION:
                        logger.warning(
                            "incompatible_state_version_on_update",
                            route_id=str(route.id),
                            redis_key=redis_key,
                            version=state_data.get("version"),
                        )
                        return

                    lines_state = state_data.get("lines", {})

                    # Remove cleared lines from state
                    for line_id in cleared_line_ids:
                        if line_id in lines_state:
                            del lines_state[line_id]

                    # Update state data
                    state_data["lines"] = lines_state

                    # Calculate TTL for updated state (same logic as _store_alert_state)
                    route_tz = ZoneInfo(route.timezone)
                    now_utc = datetime.now(UTC)
                    now_local = now_utc.astimezone(route_tz)
                    end_datetime = datetime.combine(now_local.date(), schedule.end_time, tzinfo=route_tz)

                    ttl_seconds = 0 if end_datetime <= now_local else int((end_datetime - now_local).total_seconds())

                    # Store updated state back to Redis
                    if ttl_seconds > 0 and lines_state:
                        # Only store if we have TTL and remaining lines
                        await self.redis_client.setex(
                            redis_key,
                            ttl_seconds,
                            json.dumps(state_data),
                        )
                        logger.info(
                            "cleared_lines_removed_from_state",
                            route_id=str(route.id),
                            redis_key=redis_key,
                            cleared_line_ids=cleared_line_ids,
                            remaining_lines=list(lines_state.keys()),
                        )
                    else:
                        # No lines left or TTL expired - delete the key
                        await self.redis_client.delete(redis_key)
                        logger.info(
                            "alert_state_deleted_no_remaining_lines",
                            route_id=str(route.id),
                            redis_key=redis_key,
                            cleared_line_ids=cleared_line_ids,
                        )

                except (json.JSONDecodeError, AttributeError) as e:
                    logger.warning(
                        "failed_to_parse_existing_state_on_update",
                        route_id=str(route.id),
                        redis_key=redis_key,
                        error=str(e),
                    )

            except Exception as e:
                logger.error(
                    "failed_to_update_alert_state",
                    route_id=str(route.id),
                    error=str(e),
                    exc_info=e,
                )
                # Don't raise - state cleanup failure shouldn't break the flow

    async def _process_single_route(
        self,
        route: UserRoute,
        schedules: list[UserRouteSchedule],
        disabled_severity_pairs: set[tuple[str, int]],
        cleared_states: set[tuple[str, int]],
    ) -> tuple[int, bool]:
        """
        Process a single route: check schedule, get disruptions, send alerts.

        This method encapsulates all the logic for processing one route, including:
        - Checking if the route is in an active schedule window
        - Fetching disruptions relevant to the route
        - Checking if an alert should be sent (deduplication)
        - Sending alerts to configured notification preferences

        Args:
            route: UserRoute to process (with segments, preferences loaded)
            schedules: Active (non-deleted) schedules for this route
            disabled_severity_pairs: Set of (mode_id, severity_level) pairs to filter out
            cleared_states: Set of (mode_id, severity_level) pairs that represent cleared/normal states

        Returns:
            Tuple of (alerts_sent, error_occurred)
        """
        try:
            # Check if route is in an active schedule window
            active_schedule = await self._get_active_schedule(route, schedules)
            if not active_schedule:
                logger.debug(
                    "route_not_in_schedule",
                    route_id=str(route.id),
                    route_name=route.name,
                )
                return 0, False

            logger.info(
                "route_in_active_schedule",
                route_id=str(route.id),
                route_name=route.name,
                schedule_id=str(active_schedule.id),
            )

            # Get disruptions for this route (both filtered and unfiltered)
            disruptions, all_route_disruptions, error_occurred = await self._get_route_disruptions(
                route, disabled_severity_pairs
            )

            # Skip if no disruptions at all (need to check cleared lines even if no alertable disruptions)
            if not disruptions and not all_route_disruptions:
                logger.debug(
                    "no_disruptions_for_route",
                    route_id=str(route.id),
                    route_name=route.name,
                )
                return 0, error_occurred

            if disruptions:
                logger.info(
                    "disruptions_found_for_route",
                    route_id=str(route.id),
                    route_name=route.name,
                    disruption_count=len(disruptions),
                )

            # Check if we should send alert (per-line cooldown deduplication)
            should_send, filtered_disruptions, stored_lines = await self._should_send_alert(
                route=route,
                user_id=route.user_id,
                schedule=active_schedule,
                disruptions=disruptions,
            )

            # Detect cleared lines (lines that were previously alerted but now in cleared state)
            cleared_lines: list[ClearedLineInfo] = []
            if stored_lines and all_route_disruptions and cleared_states:
                # Get current alertable line IDs
                current_alertable_line_ids = {d.line_id for d in disruptions}

                # Detect cleared lines using pure function
                cleared_lines = detect_cleared_lines(
                    stored_lines=stored_lines,
                    current_alertable_line_ids=current_alertable_line_ids,
                    all_route_disruptions=all_route_disruptions,
                    cleared_states=cleared_states,
                )

                if cleared_lines:
                    logger.info(
                        "cleared_lines_detected",
                        route_id=str(route.id),
                        route_name=route.name,
                        cleared_count=len(cleared_lines),
                        cleared_line_ids=[cl.line_id for cl in cleared_lines],
                    )
                    # Send status update notifications
                    await self._send_status_update_notifications(
                        route=route,
                        schedule=active_schedule,
                        cleared_lines=cleared_lines,
                        still_disrupted=disruptions,  # Current alertable disruptions
                    )

            # If no new disruptions AND no cleared lines, skip
            if not should_send and not cleared_lines:
                logger.debug(
                    "alert_skipped_no_changes",
                    route_id=str(route.id),
                    route_name=route.name,
                )
                return 0, error_occurred

            # Send alerts if we have new disruptions
            alerts_sent = 0
            if should_send:
                # Send alerts (only for lines that passed cooldown check)
                alerts_sent = await self._send_alerts_for_route(
                    route=route,
                    schedule=active_schedule,
                    disruptions=filtered_disruptions,
                )

            return alerts_sent, error_occurred

        except Exception as e:
            logger.error(
                "route_processing_failed",
                route_id=str(route.id),
                error=str(e),
                exc_info=e,
            )
            return 0, True

    async def _send_alerts_for_route(
        self,
        route: UserRoute,
        schedule: UserRouteSchedule,
        disruptions: list[DisruptionResponse],
    ) -> int:
        """
        Send alerts for a route to all configured notification preferences.

        Args:
            route: UserRoute to send alerts for
            schedule: Active schedule
            disruptions: Disruptions to notify about

        Returns:
            Number of alerts successfully sent
        """
        with service_span(
            "alert.send_for_route",
            "alert-service",
        ) as span:
            # Set span attributes
            span.set_attribute("alert.route_id", str(route.id))
            span.set_attribute("alert.route_name", route.name)
            span.set_attribute("alert.disruption_count", len(disruptions))

            alerts_sent = 0
            # Initialize prefs outside try block so it's accessible in except block
            prefs: list[NotificationPreference] = []

            try:
                # Get notification preferences safely (may not be loaded in async context)
                try:
                    insp = inspect(route)
                    prefs = [] if "notification_preferences" in insp.unloaded else route.notification_preferences or []
                except Exception:
                    # Can't inspect (e.g., Mock object in tests) - try direct access
                    prefs = route.notification_preferences or []

                # Check if route has notification preferences
                if not prefs:
                    logger.warning(
                        "no_notification_preferences",
                        route_id=str(route.id),
                        route_name=route.name,
                    )
                    span.set_attribute("alert.preference_count", 0)
                    span.set_attribute("alert.alerts_sent", 0)
                    return 0

                # Process each notification preference
                for pref in prefs:
                    try:
                        # Get verified contact information
                        contact_info = await self._get_verified_contact(pref, route.id)
                        if not contact_info:
                            continue

                        # Send notification
                        success, error_message = await self._send_single_notification(
                            pref=pref,
                            contact_info=contact_info,
                            route=route,
                            disruptions=disruptions,
                        )

                        # Create notification log
                        if success:
                            self._create_notification_log(
                                user_id=route.user_id,
                                route_id=route.id,
                                method=pref.method,
                                status=NotificationStatus.SENT,
                            )
                            alerts_sent += 1
                        else:
                            self._create_notification_log(
                                user_id=route.user_id,
                                route_id=route.id,
                                method=pref.method,
                                status=NotificationStatus.FAILED,
                                error_message=error_message,
                            )

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

                # Set span attributes at the end
                span.set_attribute("alert.preference_count", len(prefs))
                span.set_attribute("alert.alerts_sent", alerts_sent)

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
                # Set span attributes even on error (preserve prefs count if we got it)
                try:
                    pref_count = len(prefs) if isinstance(prefs, list) else 0
                except (TypeError, AttributeError):
                    pref_count = 0
                span.set_attribute("alert.preference_count", pref_count)
                span.set_attribute("alert.alerts_sent", alerts_sent)
                return 0

    async def _store_alert_state(
        self,
        route: UserRoute,
        user_id: UUID,
        schedule: UserRouteSchedule,
        disruptions: list[DisruptionResponse],
    ) -> None:
        """
        Store alert state in Redis with TTL until schedule end time.

        This enables hybrid deduplication: within a window, content-based deduplication
        prevents spam; between windows, expired keys allow fresh alerts.

        Args:
            route: UserRoute the alert was sent for
            user_id: User ID for deduplication key
            schedule: Active schedule
            disruptions: Disruptions that were alerted
        """
        with service_span("alert.store_state", "alert-service") as span:
            span.set_attribute("alert.route_id", str(route.id))
            span.set_attribute("alert.user_id", str(user_id))
            span.set_attribute("alert.schedule_id", str(schedule.id))
            span.set_attribute("alert.disruption_count", len(disruptions))

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

                span.set_attribute("alert.ttl_seconds", ttl_seconds)

                # Build per-line state with dual hashes
                disruptions_by_line = self._group_disruptions_by_line(disruptions)
                lines_state = {}

                for line_id, line_disruptions in disruptions_by_line.items():
                    # Get representative values (first disruption's severity/status)
                    first = line_disruptions[0]
                    lines_state[line_id] = {
                        "full_hash": self._create_line_full_hash(line_disruptions),
                        "status_hash": self._create_line_status_hash(line_disruptions),
                        "severity": first.status_severity,
                        "status": first.status_severity_description,
                        "last_sent_at": now_utc.isoformat(),
                    }

                # Build Redis key
                redis_key = f"alert:{route.id}:{user_id}:{schedule.id}"

                # Merge with existing state (preserve lines we didn't alert about).
                # Note: No freshness validation needed because:
                # 1. TTL expires at schedule end time, so stale data doesn't persist across windows
                # 2. Re-appearing disruptions will have different full_hash/status_hash, bypassing cooldown
                existing_state = await self.redis_client.get(redis_key)
                if existing_state:
                    with contextlib.suppress(json.JSONDecodeError, AttributeError):
                        data = json.loads(existing_state)
                        if data.get("version") == ALERT_STATE_VERSION:
                            # Preserve lines that weren't in this alert
                            for line_id, line_data in data.get("lines", {}).items():
                                if line_id not in lines_state:
                                    lines_state[line_id] = line_data

                # Create new state data in v2 format
                state_data = {
                    "version": ALERT_STATE_VERSION,
                    "lines": lines_state,
                    "stored_at": now_utc.isoformat(),
                }

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
                        lines_count=len(lines_state),
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

        Sorts disruptions by (line_id, status_severity, status_severity_description, reason)
        to ensure fully deterministic ordering even when a single line has
        multiple disruptions, then hashes the relevant fields including numeric severity.

        Args:
            disruptions: List of disruptions

        Returns:
            SHA256 hash (hex digest) of disruption state
        """
        # Sort by (line_id, numeric severity, description, reason) for fully deterministic ordering
        sorted_disruptions = sorted(
            disruptions,
            key=lambda d: (
                d.line_id,
                d.status_severity,
                d.status_severity_description,
                d.reason or "",
            ),
        )

        # Build hash input from relevant fields including numeric severity
        hash_input = [
            {
                "line_id": disruption.line_id,
                "severity": disruption.status_severity,
                "status": disruption.status_severity_description,
                "reason": disruption.reason or "",
            }
            for disruption in sorted_disruptions
        ]

        # Create JSON string and hash it
        hash_string = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()

    def _group_disruptions_by_line(
        self,
        disruptions: list[DisruptionResponse],
    ) -> dict[str, list[DisruptionResponse]]:
        """
        Group disruptions by line_id for per-line cooldown logic.

        Args:
            disruptions: List of disruptions to group

        Returns:
            Dictionary mapping line_id to list of disruptions for that line
        """
        result: dict[str, list[DisruptionResponse]] = {}
        for d in disruptions:
            result.setdefault(d.line_id, []).append(d)
        return result

    def _validate_stored_line_timestamp(
        self,
        stored_line: dict[str, object],
        route_id: str,
        line_id: str,
    ) -> datetime | None:
        """
        Validate and parse the last_sent_at timestamp from stored line state.

        Args:
            stored_line: Previously stored state for this line
            route_id: Route ID for logging
            line_id: TfL line ID for logging

        Returns:
            Parsed datetime if valid, None if invalid/missing
        """
        last_sent_str = stored_line.get("last_sent_at")
        if not isinstance(last_sent_str, str):
            logger.warning(
                "invalid_last_sent_at_type",
                route_id=route_id,
                line_id=line_id,
                value_type=type(last_sent_str).__name__,
            )
            return None
        try:
            return datetime.fromisoformat(last_sent_str)
        except ValueError:
            logger.warning(
                "invalid_last_sent_at_format",
                route_id=route_id,
                line_id=line_id,
                value=last_sent_str,
            )
            return None

    def _check_line_alert_needed(
        self,
        line_id: str,
        line_disruptions: list[DisruptionResponse],
        stored_line: dict[str, object] | None,
        now_utc: datetime,
        cooldown: timedelta,
        route_id: str,
    ) -> bool:
        """
        Check if an alert is needed for a specific line.

        Args:
            line_id: TfL line ID
            line_disruptions: Current disruptions for this line
            stored_line: Previously stored state for this line (if any)
            now_utc: Current UTC time
            cooldown: Cooldown duration to apply for reason-only changes
            route_id: Route ID for logging

        Returns:
            True if alert should be sent, False if within cooldown
        """
        current_full_hash = self._create_line_full_hash(line_disruptions)

        # New line or corrupted state - always alert
        if stored_line is None:
            logger.info("alert_new_line_detected", route_id=route_id, line_id=line_id)
            return True

        required_fields = ["full_hash", "status_hash", "last_sent_at"]
        if any(field not in stored_line for field in required_fields):
            logger.warning(
                "stored_line_missing_required_fields",
                route_id=route_id,
                line_id=line_id,
                missing_fields=[f for f in required_fields if f not in stored_line],
            )
            return True

        # No change - skip
        if current_full_hash == stored_line.get("full_hash"):
            return False

        # Content changed - check if severity/status changed (bypass cooldown)
        current_status_hash = self._create_line_status_hash(line_disruptions)
        severity_changed = current_status_hash != stored_line.get("status_hash")
        if severity_changed:
            logger.info(
                "line_severity_changed",
                route_id=route_id,
                line_id=line_id,
                new_hash=current_status_hash,
                old_hash=stored_line.get("status_hash"),
            )
            return True

        # Only reason text changed - validate timestamp and apply cooldown
        last_sent = self._validate_stored_line_timestamp(stored_line, route_id, line_id)
        cooldown_expired = last_sent is None or now_utc >= last_sent + cooldown

        if cooldown_expired and last_sent is not None:
            logger.info(
                "line_reason_changed_cooldown_expired",
                route_id=route_id,
                line_id=line_id,
                cooldown_minutes=cooldown.total_seconds() / 60,
            )

        return cooldown_expired

    def _create_line_full_hash(
        self,
        disruptions_for_line: list[DisruptionResponse],
    ) -> str:
        """
        Create hash including reason text (current behavior, for "all changes" mode).

        Sorts disruptions by (severity, status, reason) for deterministic ordering,
        then hashes all fields including the full reason text.

        Args:
            disruptions_for_line: List of disruptions for a single line

        Returns:
            SHA256 hash (hex digest) of line state including reason
        """
        sorted_disruptions = sorted(
            disruptions_for_line,
            key=lambda d: (
                d.status_severity,
                d.status_severity_description,
                d.reason or "",
            ),
        )

        hash_input = [
            {
                "severity": d.status_severity,
                "status": d.status_severity_description,
                "reason": d.reason or "",
            }
            for d in sorted_disruptions
        ]

        hash_string = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()

    def _create_line_status_hash(
        self,
        disruptions_for_line: list[DisruptionResponse],
    ) -> str:
        """
        Create hash excluding reason text (for "severity only" mode, future #308).

        Sorts disruptions by (severity, status) only, then hashes without reason.
        This enables future user preference to only alert on severity/status changes.

        Args:
            disruptions_for_line: List of disruptions for a single line

        Returns:
            SHA256 hash (hex digest) of line state excluding reason
        """
        sorted_disruptions = sorted(
            disruptions_for_line,
            key=lambda d: (d.status_severity, d.status_severity_description),
        )

        hash_input = [
            {"severity": d.status_severity, "status": d.status_severity_description} for d in sorted_disruptions
        ]

        hash_string = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
