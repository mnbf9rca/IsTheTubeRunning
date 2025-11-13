"""Service for building and maintaining route station indexes."""

from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.route import Route, RouteSegment
from app.models.route_index import RouteStationIndex
from app.models.tfl import Line

logger = structlog.get_logger(__name__)


class RouteIndexService:
    """
    Service for building inverted indexes mapping (line, station) → routes.

    Enables O(log n) disruption lookup by expanding sparse route segments
    into complete station lists using Line.routes data.
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
           - Get Line.routes JSON for current.line_id
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
                msg = f"Route {route_id} not found"
                logger.error("route_not_found", route_id=str(route_id))
                raise ValueError(msg)

            # Delete existing index entries for this route
            await self._delete_existing_index(route_id)

            # Process segments and build index
            entries_created = await self._process_segments(route)

            # Commit transaction if requested
            if auto_commit:
                await self.db.commit()

            logger.info(
                "build_route_station_index_completed",
                route_id=str(route_id),
                entries_created=entries_created,
                segments_count=len(route.segments),
                auto_commit=auto_commit,
            )

            return {
                "entries_created": entries_created,
                "segments_processed": len(route.segments) - 1,  # Pairs count
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

    async def _load_route_with_segments(self, route_id: UUID) -> Route | None:
        """
        Load route with segments, stations, and lines eagerly loaded.

        Args:
            route_id: UUID of route to load

        Returns:
            Route instance or None if not found
        """
        result = await self.db.execute(
            select(Route)
            .where(Route.id == route_id)
            .options(
                selectinload(Route.segments).selectinload(RouteSegment.station),
                selectinload(Route.segments).selectinload(RouteSegment.line),
            )
        )
        return result.scalar_one_or_none()

    async def _delete_existing_index(self, route_id: UUID) -> None:
        """
        Delete all existing index entries for a route.

        Args:
            route_id: UUID of route
        """
        await self.db.execute(delete(RouteStationIndex).where(RouteStationIndex.route_id == route_id))
        logger.debug("deleted_existing_index", route_id=str(route_id))

    async def _process_segments(self, route: Route) -> int:
        """
        Process route segments and create index entries.

        Iterates through segment pairs, expands to intermediate stations,
        and creates index entries for each station.

        Args:
            route: Route instance with segments loaded

        Returns:
            Number of index entries created
        """
        segments = route.segments
        if len(segments) < 2:  # noqa: PLR2004
            logger.warning(
                "route_has_insufficient_segments",
                route_id=str(route.id),
                segment_count=len(segments),
            )
            return 0

        entries_created = 0

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

            # Get station IDs for searching Line.routes (use actual tfl_id, not hub code)
            # Line.routes contains actual station TfL IDs, not hub codes
            from_station_search_id = current_segment.station.tfl_id
            to_station_search_id = next_segment.station.tfl_id

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
                        RouteStationIndex(
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

        return entries_created

    async def _expand_segment_to_stations(
        self,
        from_station_naptan: str,
        to_station_naptan: str,
        line: Line,
    ) -> list[str]:
        """
        Expand segment to all intermediate stations using Line.routes data.

        Searches through all route variants in Line.routes and extracts
        stations between from_station and to_station (inclusive).
        If multiple variants contain the segment, returns stations from ALL variants.

        Args:
            from_station_naptan: Starting station NaPTAN code (may be hub code)
            to_station_naptan: Ending station NaPTAN code (may be hub code)
            line: Line instance with routes JSON

        Returns:
            List of station NaPTAN codes (deduplicated, order preserved)

        Raises:
            ValueError: If Line.routes is None/empty or no variant contains both stations
        """
        if not line.routes or "routes" not in line.routes:
            msg = f"Line {line.tfl_id} has no routes data"
            raise ValueError(msg)

        all_stations: list[str] = []
        variants_found = 0

        # Search through all route variants
        for variant in line.routes["routes"]:
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
            start_idx = min(from_idx, to_idx)
            end_idx = max(from_idx, to_idx)
            variant_stations = stations[start_idx : end_idx + 1]

            # Add stations from this variant (preserving order, deduplicating)
            for station in variant_stations:
                if station not in all_stations:
                    all_stations.append(station)

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

        logger.debug(
            "expanded_segment_summary",
            line=line.tfl_id,
            from_station=from_station_naptan,
            to_station=to_station_naptan,
            variants_matched=variants_found,
            total_unique_stations=len(all_stations),
        )

        return all_stations


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
