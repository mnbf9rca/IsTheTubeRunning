"""Service for matching TfL disruptions to user routes."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.soft_delete_filters import add_active_filter
from app.models.tfl import AlertDisabledSeverity
from app.models.user_route import UserRouteSegment
from app.models.user_route_index import UserRouteStationIndex
from app.schemas.tfl import DisruptionResponse

# ==================== Pure Helper Functions ====================


def extract_line_station_pairs(disruption: DisruptionResponse) -> list[tuple[str, str]]:
    """
    Extract (line_id, station_naptan) tuples from disruption data.

    Pure function for easy testing without database dependencies.

    Args:
        disruption: Disruption response with optional affected_routes data

    Returns:
        List of (line_tfl_id, station_naptan) tuples to query index with.
        Empty list if no affected_routes data available.

    Example:
        >>> disruption = DisruptionResponse(
        ...     line_id="piccadilly",
        ...     line_name="Piccadilly",
        ...     mode="tube",
        ...     status_severity=10,
        ...     status_severity_description="Minor Delays",
        ...     affected_routes=[
        ...         AffectedRouteInfo(
        ...             name="Cockfosters → Heathrow T5",
        ...             direction="outbound",
        ...             affected_stations=["940GZZLURSQ", "940GZZLUHBN"]
        ...         )
        ...     ]
        ... )
        >>> extract_line_station_pairs(disruption)
        [('piccadilly', '940GZZLURSQ'), ('piccadilly', '940GZZLUHBN')]
    """
    if not disruption.affected_routes:
        return []

    pairs: list[tuple[str, str]] = []
    for affected_route in disruption.affected_routes:
        pairs.extend((disruption.line_id, station_naptan) for station_naptan in affected_route.affected_stations)

    return pairs


def disruption_affects_route(
    disruption_pairs: list[tuple[str, str]],
    route_pairs: set[tuple[str, str]],
) -> bool:
    """
    Check if disruption affects route by comparing (line, station) pairs.

    Pure function for easy testing without database dependencies.

    Args:
        disruption_pairs: List of (line_tfl_id, station_naptan) tuples from disruption
        route_pairs: Set of (line_tfl_id, station_naptan) tuples from route index

    Returns:
        True if any disruption pair matches a route pair (intersection exists)

    Example:
        >>> disruption_pairs = [('piccadilly', '940GZZLURSQ'), ('piccadilly', '940GZZLUHBN')]
        >>> route_pairs = {('piccadilly', '940GZZLURSQ'), ('piccadilly', '940GZZLULST')}
        >>> disruption_affects_route(disruption_pairs, route_pairs)
        True
        >>> route_pairs_no_match = {('district', '940GZZLUEMB')}
        >>> disruption_affects_route(disruption_pairs, route_pairs_no_match)
        False
    """
    return bool(route_pairs.intersection(disruption_pairs))


def calculate_affected_segments(
    route_segments: list[UserRouteSegment],
    matched_station_pairs: set[tuple[str, str]],
) -> list[int]:
    """
    Calculate which segment sequence numbers are affected.

    Pure function - no side effects.

    Args:
        route_segments: List of RouteSegment models (sorted by sequence)
        matched_station_pairs: Set of (line_tfl_id, station_naptan) pairs that matched

    Returns:
        List of segment sequence numbers (e.g., [0, 1, 2])

    Example:
        >>> segment1 = UserRouteSegment(
        ...     sequence=0,
        ...     line=Line(tfl_id="piccadilly"),
        ...     station=Station(tfl_id="940GZZLUKSX")
        ... )
        >>> segment2 = UserRouteSegment(
        ...     sequence=1,
        ...     line=Line(tfl_id="piccadilly"),
        ...     station=Station(tfl_id="940GZZLURSQ")
        ... )
        >>> matched_pairs = {("piccadilly", "940GZZLURSQ")}
        >>> calculate_affected_segments([segment1, segment2], matched_pairs)
        [1]
    """
    affected_sequences: list[int] = []

    for segment in route_segments:
        # Skip segments without line (destination segments)
        if not segment.line or not segment.station:
            continue

        # Check if this segment's (line, station) is in matched pairs
        segment_pair = (segment.line.tfl_id, segment.station.tfl_id)
        if segment_pair in matched_station_pairs:
            affected_sequences.append(segment.sequence)

    return affected_sequences


def calculate_affected_stations(
    route_index_pairs: set[tuple[str, str]],
    disruption_station_pairs: set[tuple[str, str]],
) -> list[str]:
    """
    Calculate which station NaPTAN codes are affected.

    Pure function - no side effects.

    Args:
        route_index_pairs: Set of (line_tfl_id, station_naptan) tuples from route
        disruption_station_pairs: Set of (line_tfl_id, station_naptan) tuples from disruption

    Returns:
        Sorted list of unique station NaPTAN codes

    Example:
        >>> route_pairs = {("piccadilly", "940GZZLUKSX"), ("piccadilly", "940GZZLURSQ")}
        >>> disruption_pairs = {("piccadilly", "940GZZLURSQ"), ("piccadilly", "940GZZLUHBN")}
        >>> calculate_affected_stations(route_pairs, disruption_pairs)
        ['940GZZLURSQ']
    """
    # Find intersection of pairs
    matched_pairs = route_index_pairs.intersection(disruption_station_pairs)

    # Extract unique station NaPTANs from matched pairs
    affected_naptans = {station_naptan for _, station_naptan in matched_pairs}

    # Return sorted list for consistent ordering
    return sorted(affected_naptans)


# ==================== Service Class ====================


class DisruptionMatchingService:
    """Service for matching TfL disruptions to user routes."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the disruption matching service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_route_index_pairs(self, route_id: UUID) -> set[tuple[str, str]]:
        """
        Get (line_tfl_id, station_naptan) pairs for a route from UserRouteStationIndex.

        Args:
            route_id: Route UUID

        Returns:
            Set of (line_tfl_id, station_naptan) tuples
        """
        query = select(
            UserRouteStationIndex.line_tfl_id,
            UserRouteStationIndex.station_naptan,
        ).where(UserRouteStationIndex.route_id == route_id)
        query = add_active_filter(query, UserRouteStationIndex)
        result = await self.db.execute(query)
        return {(row[0], row[1]) for row in result.all()}

    async def filter_alertable_disruptions(
        self,
        disruptions: list[DisruptionResponse],
    ) -> list[DisruptionResponse]:
        """
        Filter out non-alertable disruptions based on AlertDisabledSeverity.

        Args:
            disruptions: List of disruptions to filter

        Returns:
            Filtered list of alertable disruptions
        """
        if not disruptions:
            return []

        # Fetch disabled severity pairs from database
        disabled_result = await self.db.execute(select(AlertDisabledSeverity))
        disabled_severity_pairs = {(d.mode_id, d.severity_level) for d in disabled_result.scalars().all()}

        # Filter disruptions
        alertable_disruptions = []

        for disruption in disruptions:
            # Check if this (mode, severity) should be filtered
            if (disruption.mode, disruption.status_severity) not in disabled_severity_pairs:
                alertable_disruptions.append(disruption)

        return alertable_disruptions

    def match_disruptions_to_route(
        self,
        route_index_pairs: set[tuple[str, str]],
        all_disruptions: list[DisruptionResponse],
    ) -> list[DisruptionResponse]:
        """
        Match disruptions to a route using station-level matching.

        Uses pure helper functions for testability.

        Args:
            route_index_pairs: Route's (line_tfl_id, station_naptan) pairs
            all_disruptions: All current disruptions

        Returns:
            List of disruptions affecting this route
        """
        matched_disruptions: list[DisruptionResponse] = []

        for disruption in all_disruptions:
            # Extract disruption pairs
            disruption_pairs = extract_line_station_pairs(disruption)

            # Check if disruption affects this route
            if disruption_pairs and disruption_affects_route(disruption_pairs, route_index_pairs):
                matched_disruptions.append(disruption)

        return matched_disruptions
