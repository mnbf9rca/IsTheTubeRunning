"""Alert processing service for checking disruptions and sending notifications."""

import hashlib
import json
from datetime import UTC, datetime
from itertools import groupby
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_, func, inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis import RedisClientProtocol
from app.core.telemetry import service_span
from app.helpers.disruption_helpers import disruption_affects_route, extract_line_station_pairs
from app.helpers.soft_delete_filters import add_active_filter
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
from app.schemas.tfl import DisruptionResponse
from app.services.notification_service import NotificationService
from app.services.tfl_service import TfLService

logger = structlog.get_logger(__name__)


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

        logger.info(
            "line_state_cache_warmup_complete",
            lines_hydrated=lines_hydrated,
            total_log_entries=len(logs),
        )

        return lines_hydrated

    except Exception as e:
        # Log error but don't block application startup
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
        try:
            logged_count = 0

            if not disruptions:
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

            return logged_count

        except Exception as e:
            logger.error(
                "log_line_disruption_states_failed",
                error=str(e),
                exc_info=e,
            )
            await self.db.rollback()
            # Don't raise - logging failures shouldn't block alert processing
            return 0

    async def process_all_routes(self) -> dict[str, Any]:  # noqa: PLR0915
        """
        Main entry point for processing all active routes.

        Checks all active routes, determines if they are in a schedule window,
        and sends alerts if disruptions are detected.

        Returns:
            Statistics dictionary with routes_checked, alerts_sent, and errors
        """
        with service_span("alert.process_all_routes", "alert-service") as span:
            logger.info("alert_processing_started")

            stats = {
                "routes_checked": 0,
                "alerts_sent": 0,
                "errors": 0,
            }

            try:
                routes = await self._get_active_routes()
                logger.info("active_routes_fetched", count=len(routes))

                # Fetch all line disruptions once and log state changes
                # Uses cache automatically, so subsequent per-route calls will be fast
                # Errors here are non-fatal - per-route processing will still work
                all_disruptions: list[DisruptionResponse] = []
                disabled_severity_pairs: set[tuple[str, int]] = set()

                try:
                    tfl_service = TfLService(db=self.db)
                    all_disruptions = await tfl_service.fetch_line_disruptions(use_cache=True)
                    logger.info("all_disruptions_fetched", count=len(all_disruptions))

                    # Log line disruption state changes (for troubleshooting and analytics)
                    await self._log_line_disruption_state_changes(all_disruptions)

                    # Fetch disabled severity pairs once for all routes
                    disabled_result = await self.db.execute(select(AlertDisabledSeverity))
                    disabled_severity_pairs = {(d.mode_id, d.severity_level) for d in disabled_result.scalars().all()}

                except Exception as e:
                    logger.error(
                        "disruption_logging_failed",
                        error=str(e),
                        exc_info=e,
                    )
                    # Don't track as error - per-route processing will handle its own disruptions
                    # This is just for centralized logging

                for route in routes:
                    try:
                        stats["routes_checked"] += 1

                        # Check if route is in an active schedule window
                        # schedules are eagerly loaded in _get_active_routes
                        active_schedule = await self._get_active_schedule(route, route.schedules)
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
                        disruptions, error_occurred = await self._get_route_disruptions(route, disabled_severity_pairs)

                        # Track error if one occurred
                        if error_occurred:
                            stats["errors"] += 1

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

                # Set span attributes at the end
                span.set_attribute("alert.routes_checked", stats["routes_checked"])
                span.set_attribute("alert.alerts_sent", stats["alerts_sent"])
                span.set_attribute("alert.errors", stats["errors"])

                logger.info("alert_processing_completed", **stats)
                return stats

            except Exception as e:
                logger.error("alert_processing_failed", error=str(e), exc_info=e)
                stats["errors"] += 1
                # Set span attributes even on error
                span.set_attribute("alert.routes_checked", stats["routes_checked"])
                span.set_attribute("alert.alerts_sent", stats["alerts_sent"])
                span.set_attribute("alert.errors", stats["errors"])
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
                    selectinload(UserRoute.schedules),
                    selectinload(UserRoute.notification_preferences),
                    selectinload(UserRoute.user).selectinload(User.email_addresses),
                )
            )
            return list(result.scalars().all())

        except Exception as e:
            logger.error("fetch_active_routes_failed", error=str(e), exc_info=e)
            return []

    async def _get_active_schedule(
        self,
        route: UserRoute,
        schedules: list[UserRouteSchedule] | None = None,
    ) -> UserRouteSchedule | None:
        """
        Check if the route is currently in any active schedule window.

        Converts UTC now to route's timezone and checks against schedule windows.

        Args:
            route: UserRoute to check schedules for
            schedules: Optional list of schedules. If None, uses route.schedules
                       (but requires schedules to be eagerly loaded)

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

            # Use provided schedules or fall back to route.schedules
            schedules_to_check = schedules if schedules is not None else route.schedules

            # Check each schedule
            for schedule in schedules_to_check:
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
    ) -> tuple[list[DisruptionResponse], bool]:
        """
        Get current disruptions affecting this route using inverted index.

        Uses station-level matching via UserRouteStationIndex for precision.
        Falls back to line-level matching only when TfL doesn't provide station data.

        Args:
            route: UserRoute to get disruptions for
            disabled_severity_pairs: Set of (mode_id, severity_level) pairs to filter out

        Returns:
            Tuple of (disruptions, error_occurred)
            - disruptions: List of disruptions affecting this specific route
            - error_occurred: True if an error occurred during processing
        """
        try:
            # Get this route's (line, station) pairs from index once
            route_index_pairs = await self._get_route_index_pairs(route.id)

            # Extract unique line IDs for fallback matching
            if route_index_pairs:
                route_line_ids = {line_tfl_id for line_tfl_id, _ in route_index_pairs}
            else:
                # Fallback: extract line IDs from segments if index is not populated
                # This handles newly created routes before index is built
                line_db_ids = {segment.line_id for segment in route.segments if segment.line_id}
                if line_db_ids:
                    result = await self.db.execute(select(Line.tfl_id).where(Line.id.in_(line_db_ids)))
                    route_line_ids = {row[0] for row in result.all()}
                else:
                    route_line_ids = set()

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

            # Filter disruptions by severity (remove non-alertable severities like "Good Service")
            route_disruptions = self._filter_alertable_disruptions(route_disruptions, disabled_severity_pairs)

            logger.debug(
                "route_disruptions_filtered",
                route_id=str(route.id),
                total_disruptions=len(all_disruptions),
                route_disruptions=len(route_disruptions),
            )

            return route_disruptions, False

        except Exception as e:
            logger.error(
                "get_route_disruptions_failed",
                route_id=str(route.id),
                error=str(e),
                exc_info=e,
            )
            return [], True

    def _filter_alertable_disruptions(
        self,
        disruptions: list[DisruptionResponse],
        disabled_severity_pairs: set[tuple[str, int]],
    ) -> list[DisruptionResponse]:
        """
        Filter disruptions to only include those that should trigger alerts.

        Removes disruptions with severity levels that are configured as non-alertable
        (e.g., "Good Service" with severity_level=10).

        Args:
            disruptions: List of disruptions to filter
            disabled_severity_pairs: Set of (mode_id, severity_level) pairs to filter out

        Returns:
            List of disruptions that should trigger alerts
        """
        if not disruptions:
            return []

        # Filter disruptions
        alertable_disruptions = []
        filtered_count = 0

        for disruption in disruptions:
            # Check if this (mode, severity) should be filtered
            if (disruption.mode, disruption.status_severity) in disabled_severity_pairs:
                filtered_count += 1
                logger.debug(
                    "disruption_filtered_by_severity",
                    line_id=disruption.line_id,
                    mode=disruption.mode,
                    severity=disruption.status_severity,
                    description=disruption.status_severity_description,
                )
            else:
                alertable_disruptions.append(disruption)

        if filtered_count > 0:
            logger.info(
                "disruptions_filtered_by_severity",
                total=len(disruptions),
                filtered=filtered_count,
                remaining=len(alertable_disruptions),
            )

        return alertable_disruptions

    async def _should_send_alert(
        self,
        route: UserRoute,
        user_id: UUID,
        schedule: UserRouteSchedule,
        disruptions: list[DisruptionResponse],
    ) -> bool:
        """
        Check if we should send an alert based on deduplication logic.

        Uses Redis to track disruption state within a schedule window.
        Compares current disruptions with stored state to detect changes.

        Args:
            route: UserRoute to check
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
                target=contact_info,
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
