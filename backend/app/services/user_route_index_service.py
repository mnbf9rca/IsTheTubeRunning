"""Service for building and maintaining route station indexes."""

from typing import TypedDict
from uuid import UUID

import structlog
from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tfl import Line, Station
from app.models.user_route import UserRoute, UserRouteSegment
from app.models.user_route_index import UserRouteStationIndex

logger = structlog.get_logger(__name__)


class RebuildRoutesResult(TypedDict):
    """Result from rebuild_routes operation."""

    rebuilt_count: int
    failed_count: int
    errors: list[str]


class UserRouteIndexService:
    """
    Service for building inverted indexes mapping (line, station) → routes.

    Enables O(log n) disruption lookup by expanding sparse route segments
    into complete station lists using Line.route_variants data.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize service with database session.

        Args:
            db: Async database session
        """
        self.db = db

    async def build_route_station_index(
        self,
        route_id: UUID,
        *,
        auto_commit: bool = True,
    ) -> dict[str, int]:
        """
        Build inverted index for a route by expanding segments to all intermediate stations.

        Algorithm:
        1. Delete existing index entries for this route (in transaction)
        2. Load route with segments (ordered by sequence)
        3. For each segment pair (current → next):
           - Get Line.route_variants JSON for current.line_id
           - Find ALL route variants containing BOTH stations
           - For EACH matching variant:
             - Extract all stations between current and next (inclusive)
             - Create index entry for each (line_tfl_id, station_naptan)
        4. Optionally commit transaction (if auto_commit=True)

        Note: If multiple route variants exist (e.g., Northern Line Bank/Charing Cross branches),
        we store ALL stations from ALL variants. This means alerts trigger if ANY branch is disrupted.

        Args:
            route_id: UUID of route to index
            auto_commit: If True, commits the transaction. If False, caller must commit.

        Returns:
            Dictionary with statistics:
                - entries_created: Number of index entries created
                - segments_processed: Number of segment pairs processed

        Raises:
            ValueError: If route not found or has invalid segments
        """
        logger.info("build_route_station_index_started", route_id=str(route_id))

        try:
            # Load route with segments and related data
            route = await self._load_route_with_segments(route_id)
            if not route:
                msg = f"UserRoute {route_id} not found"
                logger.error("route_not_found", route_id=str(route_id))
                raise ValueError(msg)

            # Delete existing index entries for this route
            await self._delete_existing_index(route_id)

            # Process segments and build index
            entries_created, pairs_processed = await self._process_segments(route)

            # Commit transaction if requested
            if auto_commit:
                await self.db.commit()

            logger.info(
                "build_route_station_index_completed",
                route_id=str(route_id),
                entries_created=entries_created,
                pairs_processed=pairs_processed,
                segments_count=len(route.segments),
                auto_commit=auto_commit,
            )

            return {
                "entries_created": entries_created,
                "segments_processed": pairs_processed,
            }

        except Exception as exc:
            if auto_commit:
                await self.db.rollback()
            logger.error(
                "build_route_station_index_failed",
                route_id=str(route_id),
                error=str(exc),
            )
            raise

    async def rebuild_routes(
        self,
        route_id: UUID | None = None,
        *,
        auto_commit: bool = True,
    ) -> RebuildRoutesResult:
        """
        Rebuild route station indexes for single route or all routes.

        This is a convenience method that wraps build_route_station_index()
        with error handling and statistics collection. Used by both the admin
        endpoint and Celery tasks to ensure consistent behavior.

        Args:
            route_id: Optional route UUID. If provided, rebuilds only that route.
                      If None, rebuilds all routes.
            auto_commit: If True, commits transactions. If False, caller must commit.

        Returns:
            Dictionary with statistics:
                - rebuilt_count: Number of routes successfully rebuilt
                - failed_count: Number of routes that failed to rebuild
                - errors: List of error messages for failed rebuilds
        """
        rebuilt_count = 0
        failed_count = 0
        errors: list[str] = []

        try:
            if route_id:
                # Rebuild single route
                try:
                    await self.build_route_station_index(route_id, auto_commit=auto_commit)
                    rebuilt_count = 1
                except Exception as exc:
                    failed_count = 1
                    errors.append(f"UserRoute {route_id}: {exc!s}")
                    logger.error(
                        "rebuild_single_route_failed",
                        route_id=str(route_id),
                        error=str(exc),
                    )
            else:
                # Rebuild all routes (exclude soft-deleted)
                result = await self.db.execute(select(UserRoute).where(UserRoute.deleted_at.is_(None)))
                routes = result.scalars().all()

                for route in routes:
                    try:
                        await self.build_route_station_index(route.id, auto_commit=auto_commit)
                        rebuilt_count += 1
                    except Exception as exc:
                        failed_count += 1
                        errors.append(f"UserRoute {route.id}: {exc!s}")
                        logger.error(
                            "rebuild_route_failed",
                            route_id=str(route.id),
                            error=str(exc),
                        )

            logger.info(
                "rebuild_routes_completed",
                route_id=str(route_id) if route_id else "all",
                rebuilt_count=rebuilt_count,
                failed_count=failed_count,
            )

            return {
                "rebuilt_count": rebuilt_count,
                "failed_count": failed_count,
                "errors": errors,
            }

        except Exception as exc:
            logger.error(
                "rebuild_routes_failed",
                route_id=str(route_id) if route_id else "all",
                error=str(exc),
            )
            raise

    async def _load_route_with_segments(self, route_id: UUID) -> UserRoute | None:
        """
        Load route with segments, stations, and lines eagerly loaded.

        Args:
            route_id: UUID of route to load

        Returns:
            UserRoute instance or None if not found
        """
        # Note: Segments MUST be ordered by sequence for _process_segments to work correctly.
        # The ordering is enforced by the UserRoute.segments relationship default (see route.py:68).
        # This is critical - if segments are unordered, _process_segments would create incorrect
        # index entries linking non-adjacent stations.
        result = await self.db.execute(
            select(UserRoute)
            .where(
                UserRoute.id == route_id,
                UserRoute.deleted_at.is_(None),
            )
            .options(
                selectinload(UserRoute.segments).selectinload(UserRouteSegment.station),
                selectinload(UserRoute.segments).selectinload(UserRouteSegment.line),
            )
        )
        return result.scalar_one_or_none()

    async def _delete_existing_index(self, route_id: UUID) -> None:
        """
        Soft delete all existing index entries for a route.

        Args:
            route_id: UUID of route
        """
        # Soft delete existing index entries (Issue #233)
        await self.db.execute(
            update(UserRouteStationIndex)
            .where(
                UserRouteStationIndex.route_id == route_id,
                UserRouteStationIndex.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        logger.debug("soft_deleted_existing_index", route_id=str(route_id))

    async def _resolve_station_for_line(
        self,
        station: Station,
        line: Line,
    ) -> str:
        """
        Resolve station to hub-equivalent on the specified line.

        If station is in a hub, returns the tfl_id of the hub station that serves
        this line. Otherwise returns the station's own tfl_id.

        This is deterministic - there's only one station in a hub that serves a
        given line (stations in the same hub serve different lines/modes).

        Args:
            station: Station that may be in a hub
            line: Line we're traveling on

        Returns:
            TfL ID of the station to use for Line.route_variants lookup
        """
        # If station not in a hub, use it directly
        if not station.hub_naptan_code:
            return station.tfl_id

        # Query for station in this hub that serves this line
        # Simple WHERE clause as user suggested - hub + line uniquely identifies station
        # Use PostgreSQL JSONB containment operator (@>) for JSON array query
        result = await self.db.execute(
            select(Station)
            .where(
                Station.hub_naptan_code == station.hub_naptan_code,
                cast(Station.lines, JSONB).contains([line.tfl_id]),
            )
            .limit(1)
        )
        hub_station = result.scalar_one_or_none()

        if hub_station:
            # Log when we resolve to a different station (hub interchange)
            if hub_station.tfl_id != station.tfl_id:
                logger.debug(
                    "hub_station_resolved_for_index",
                    original_station=station.tfl_id,
                    resolved_station=hub_station.tfl_id,
                    hub=station.hub_naptan_code,
                    line=line.tfl_id,
                )
            return hub_station.tfl_id

        # No hub station on this line - this is a data consistency error
        # Should not happen if validation passed; indicates either:
        # 1. Validation logic is broken
        # 2. Data changed between validation and index building
        # 3. Hub data is inconsistent
        logger.error(
            "hub_station_not_on_line",
            station=station.tfl_id,
            hub=station.hub_naptan_code,
            line=line.tfl_id,
        )
        msg = (
            f"Station {station.tfl_id} is in hub {station.hub_naptan_code} "
            f"but no station in that hub serves line {line.tfl_id}"
        )
        raise ValueError(msg)

    async def _process_segments(self, route: UserRoute) -> tuple[int, int]:
        """
        Process route segments and create index entries.

        Iterates through segment pairs, expands to intermediate stations,
        and creates index entries for each station.

        Args:
            route: UserRoute instance with segments loaded

        Returns:
            Tuple of (entries_created, pairs_processed) where:
                - entries_created: Number of index entries created
                - pairs_processed: Number of segment pairs actually processed
        """
        segments = route.segments
        if len(segments) < 2:  # noqa: PLR2004
            logger.warning(
                "route_has_insufficient_segments",
                route_id=str(route.id),
                segment_count=len(segments),
            )
            return 0, 0

        entries_created = 0
        pairs_processed = 0

        # Process each consecutive segment pair
        for i in range(len(segments) - 1):
            current_segment = segments[i]
            next_segment = segments[i + 1]

            # Skip if current segment has no line (destination-only segment)
            if not current_segment.line:
                logger.debug(
                    "skipping_segment_no_line",
                    route_id=str(route.id),
                    sequence=current_segment.sequence,
                )
                continue

            # Skip if either segment is missing station data
            if not current_segment.station or not next_segment.station:
                logger.warning(
                    "skipping_segment_missing_station",
                    route_id=str(route.id),
                    current_sequence=current_segment.sequence,
                    next_sequence=next_segment.sequence,
                    current_station_missing=current_segment.station is None,
                    next_station_missing=next_segment.station is None,
                )
                continue

            # Track that we're processing this pair
            pairs_processed += 1

            # Resolve stations to hub-equivalents on the line if needed
            # If a station is in a hub, we need to find the station in that hub
            # that actually serves the line we're traveling on
            from_station_search_id = await self._resolve_station_for_line(
                current_segment.station,
                current_segment.line,
            )
            to_station_search_id = await self._resolve_station_for_line(
                next_segment.station,
                current_segment.line,
            )

            # Expand segment pair to intermediate stations
            try:
                station_naptans = await self._expand_segment_to_stations(
                    from_station_search_id,
                    to_station_search_id,
                    current_segment.line,
                )

                # Create index entries for all intermediate stations
                for station_naptan in station_naptans:
                    self.db.add(
                        UserRouteStationIndex(
                            route_id=route.id,
                            line_tfl_id=current_segment.line.tfl_id,
                            station_naptan=station_naptan,
                            line_data_version=current_segment.line.last_updated,
                        )
                    )
                    entries_created += 1

                logger.debug(
                    "expanded_segment",
                    route_id=str(route.id),
                    from_station=from_station_search_id,
                    to_station=to_station_search_id,
                    line=current_segment.line.tfl_id,
                    stations_found=len(station_naptans),
                )

            except ValueError as exc:
                logger.warning(
                    "segment_expansion_failed",
                    route_id=str(route.id),
                    from_station=from_station_search_id,
                    to_station=to_station_search_id,
                    line=current_segment.line.tfl_id if current_segment.line else None,
                    error=str(exc),
                )
                # Continue processing other segments rather than failing entire index build
                continue

        return entries_created, pairs_processed

    async def _expand_segment_to_stations(
        self,
        from_station_naptan: str,
        to_station_naptan: str,
        line: Line,
    ) -> list[str]:
        """
        Expand segment to all intermediate stations using Line.route_variants data.

        Searches through all route variants in Line.route_variants and extracts
        stations between from_station and to_station (inclusive).
        If multiple variants contain the segment, returns stations from ALL variants.

        Args:
            from_station_naptan: Starting station NaPTAN code (may be hub code)
            to_station_naptan: Ending station NaPTAN code (may be hub code)
            line: Line instance with routes JSON

        Returns:
            List of station NaPTAN codes (deduplicated, order preserved)

        Raises:
            ValueError: If Line.route_variants is None/empty or no variant contains both stations
        """
        if not line.route_variants or "routes" not in line.route_variants:
            msg = f"Line {line.tfl_id} has no routes data"
            raise ValueError(msg)

        all_stations: list[str] = []
        variants_found = 0

        # Search through all route variants
        for variant in line.route_variants["routes"]:
            stations = variant.get("stations", [])
            if not stations:
                continue

            # Find positions of from and to stations in this variant
            try:
                from_idx = stations.index(from_station_naptan)
                to_idx = stations.index(to_station_naptan)
            except ValueError:
                # This variant doesn't contain both stations, try next variant
                continue

            # Extract all stations between from and to (inclusive)
            # Note: We don't use find_stations_between() here because we need to:
            # (1) search multiple route variants and collect results from ALL matches
            # (2) continue searching if a variant doesn't contain both stations
            # The inline logic is clearer for this multi-variant search pattern.
            start_idx = min(from_idx, to_idx)
            end_idx = max(from_idx, to_idx)
            variant_stations = stations[start_idx : end_idx + 1]

            # Collect stations from this variant (will deduplicate after loop)
            all_stations.extend(variant_stations)

            variants_found += 1
            logger.debug(
                "found_matching_variant",
                line=line.tfl_id,
                variant_name=variant.get("name", "unknown"),
                from_station=from_station_naptan,
                to_station=to_station_naptan,
                stations_in_variant=len(variant_stations),
            )

        if variants_found == 0:
            msg = f"No route variant on line {line.tfl_id} contains both {from_station_naptan} and {to_station_naptan}"
            raise ValueError(msg)

        # Deduplicate stations while preserving order (using pure function)
        unique_stations = deduplicate_preserving_order(all_stations)

        logger.debug(
            "expanded_segment_summary",
            line=line.tfl_id,
            from_station=from_station_naptan,
            to_station=to_station_naptan,
            variants_matched=variants_found,
            total_unique_stations=len(unique_stations),
        )

        return unique_stations


# =============================================================================
# Pure Function Helpers
# =============================================================================


def find_stations_between(
    stations: list[str],
    from_station: str,
    to_station: str,
) -> list[str] | None:
    """
    Find all stations between from_station and to_station in an ordered list.

    Pure function with no side effects.

    Args:
        stations: Ordered list of station NaPTAN codes
        from_station: Starting station NaPTAN code
        to_station: Ending station NaPTAN code

    Returns:
        List of stations between from and to (inclusive), or None if both stations not found

    Examples:
        >>> stations = ["A", "B", "C", "D", "E"]
        >>> find_stations_between(stations, "B", "D")
        ['B', 'C', 'D']
        >>> find_stations_between(stations, "D", "B")  # Reversed order
        ['B', 'C', 'D']
        >>> find_stations_between(stations, "A", "Z")  # Not found
        None
    """
    try:
        from_idx = stations.index(from_station)
        to_idx = stations.index(to_station)
    except ValueError:
        return None

    start_idx = min(from_idx, to_idx)
    end_idx = max(from_idx, to_idx)
    return stations[start_idx : end_idx + 1]


def deduplicate_preserving_order(items: list[str]) -> list[str]:
    """
    Remove duplicates from list while preserving first occurrence order.

    Pure function with no side effects.

    Args:
        items: List of strings (may contain duplicates)

    Returns:
        List with duplicates removed, order preserved

    Examples:
        >>> deduplicate_preserving_order(["A", "B", "A", "C", "B"])
        ['A', 'B', 'C']
        >>> deduplicate_preserving_order([])
        []
    """
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
