"""Service for matching TfL disruptions to user routes."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.disruption_helpers import (
    disruption_affects_route,
    extract_line_station_pairs,
)
from app.helpers.soft_delete_filters import add_active_filter
from app.models.tfl import AlertDisabledSeverity
from app.models.user_route_index import UserRouteStationIndex
from app.schemas.tfl import DisruptionResponse

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

        # Filter disruptions (list comprehension for efficiency)
        return [
            disruption
            for disruption in disruptions
            if (disruption.mode, disruption.status_severity) not in disabled_severity_pairs
        ]

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
