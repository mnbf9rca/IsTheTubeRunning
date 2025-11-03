"""TfL API service for fetching and caching transport data."""

import asyncio
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import structlog
from aiocache import Cache
from aiocache.serializers import PickleSerializer
from fastapi import HTTPException, status
from pydantic_tfl_api import LineClient, StopPointClient
from pydantic_tfl_api.core import ApiError, ResponseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tfl import Line, Station, StationConnection
from app.schemas.tfl import DisruptionResponse, RouteSegmentRequest

logger = structlog.get_logger(__name__)

# Default cache TTL values (in seconds) - used if TfL API doesn't provide cache headers
DEFAULT_LINES_CACHE_TTL = 86400  # 24 hours
DEFAULT_STATIONS_CACHE_TTL = 86400  # 24 hours
DEFAULT_DISRUPTIONS_CACHE_TTL = 120  # 2 minutes

# TfL API constants
TFL_GOOD_SERVICE_SEVERITY = 10  # Status severity value for "Good Service"
MIN_ROUTE_SEGMENTS = 2  # Minimum number of segments required for route validation


class TfLService:
    """Service for interacting with TfL API and managing transport data."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the TfL service.

        Args:
            db: Database session
        """
        self.db = db
        # Note: pydantic-tfl-api clients are synchronous
        self.line_client = LineClient(api_token=settings.TFL_API_KEY)
        self.stoppoint_client = StopPointClient(api_token=settings.TFL_API_KEY)

        # Initialize Redis cache for aiocache
        self.cache = Cache(
            Cache.REDIS,
            endpoint=self._parse_redis_host(),
            port=self._parse_redis_port(),
            serializer=PickleSerializer(),
            namespace="tfl",
        )

    def _parse_redis_host(self) -> str:
        """Extract Redis host from REDIS_URL."""
        # Format: redis://host:port/db or redis://host:port
        parsed = urlparse(settings.REDIS_URL)
        return parsed.hostname or "localhost"

    def _parse_redis_port(self) -> int:
        """Extract Redis port from REDIS_URL."""
        # Format: redis://host:port/db or redis://host:port
        parsed = urlparse(settings.REDIS_URL)
        return parsed.port or 6379

    def _handle_api_error(self, response: ResponseModel[Any] | ApiError) -> None:
        """
        Check if TfL API response is an error and raise HTTPException.

        Args:
            response: TfL API response object or ApiError

        Raises:
            HTTPException: If response is an ApiError
        """
        if isinstance(response, ApiError):
            error_msg = f"TfL API error: {response.message}"
            logger.error("tfl_api_error", message=response.message, status=response.http_status_code)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg,
            )

    def _extract_cache_ttl(self, response: ResponseModel[Any]) -> int:
        """
        Extract cache TTL from TfL API response.

        Uses shared_expires (s-maxage) for shared caches like Redis, falling back to
        content_expires (max-age) if shared_expires is not available.

        Args:
            response: TfL API response object

        Returns:
            TTL in seconds from shared_expires/content_expires, or 0 if not available
        """
        # Prefer shared_expires (s-maxage) for shared caches like Redis
        expires = None
        if hasattr(response, "shared_expires") and response.shared_expires:
            expires = response.shared_expires
            logger.debug("extracted_cache_ttl", source="shared_expires")
        elif hasattr(response, "content_expires") and response.content_expires:
            expires = response.content_expires
            logger.debug("extracted_cache_ttl", source="content_expires")

        if expires:
            ttl = int((expires - datetime.now(UTC)).total_seconds())
            if ttl > 0:
                logger.debug("cache_ttl_calculated", ttl=ttl)
                return ttl

        return 0  # Return 0 to indicate no TTL found

    async def fetch_lines(self, use_cache: bool = True) -> list[Line]:
        """
        Fetch all tube lines from TfL API or database cache.

        Args:
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of Line objects from database
        """
        cache_key = "lines:all"

        # Try cache first
        if use_cache:
            cached_lines: list[Line] | None = await self.cache.get(cache_key)
            if cached_lines is not None:
                logger.debug("lines_cache_hit", count=len(cached_lines))
                return cached_lines

        logger.info("fetching_lines_from_tfl_api")

        try:
            # Fetch from TfL API (synchronous call wrapped in executor)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self.line_client.GetByModeByPathModes,
                "tube",
            )

            # Check for API error
            self._handle_api_error(response)

            # Extract cache TTL from response
            # Type narrowing: _handle_api_error raises if response is ApiError, so it's safe here
            ttl = self._extract_cache_ttl(response) or DEFAULT_LINES_CACHE_TTL  # type: ignore[arg-type]

            # Clear existing lines from database
            await self.db.execute(delete(Line))

            # Process and store lines
            lines = []
            # response.content is a LineArray (RootModel), access via .root
            line_data_list = response.content.root  # type: ignore[union-attr]

            # TfL API doesn't provide color in GetByModeByPathModes response
            # Use a default color (can be updated later via different endpoint if needed)
            color = "#000000"  # Default black

            for line_data in line_data_list:
                line = Line(
                    tfl_id=line_data.id,
                    name=line_data.name,
                    color=color,
                    last_updated=datetime.now(UTC),
                )
                self.db.add(line)
                lines.append(line)

            await self.db.commit()

            # Refresh to get database IDs
            for line in lines:
                await self.db.refresh(line)

            # Cache the results
            await self.cache.set(cache_key, lines, ttl=ttl)

            logger.info("lines_fetched_and_cached", count=len(lines), ttl=ttl)
            return lines

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_lines_failed", error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch lines from TfL API.",
            ) from e

    async def fetch_stations(self, line_tfl_id: str | None = None, use_cache: bool = True) -> list[Station]:
        """
        Fetch stations from TfL API or database cache.

        Args:
            line_tfl_id: Optional TfL line ID to filter stations (e.g., "victoria")
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of Station objects from database
        """
        cache_key = f"stations:line:{line_tfl_id}" if line_tfl_id else "stations:all"

        # Try cache first
        if use_cache:
            cached_stations: list[Station] | None = await self.cache.get(cache_key)
            if cached_stations is not None:
                logger.debug("stations_cache_hit", line_tfl_id=line_tfl_id, count=len(cached_stations))
                return cached_stations

        logger.info("fetching_stations_from_tfl_api", line_tfl_id=line_tfl_id)

        try:
            if line_tfl_id:
                # Fetch stations via stop points for the line
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    self.stoppoint_client.GetByPathIdQueryPlaceTypes,
                    f"Line/{line_tfl_id}",
                    "",  # placeTypes parameter (empty for all types)
                )

                # Check for API error
                self._handle_api_error(response)

                # Type narrowing: _handle_api_error raises if response is ApiError, so it's safe here
                ttl = self._extract_cache_ttl(response) or DEFAULT_STATIONS_CACHE_TTL  # type: ignore[arg-type]
                # response.content is a PlaceArray (RootModel), access via .root
                stop_points = response.content.root  # type: ignore[union-attr]

                stations = []
                for stop_point in stop_points:
                    # Check if station exists in DB
                    result = await self.db.execute(select(Station).where(Station.tfl_id == stop_point.id))
                    station = result.scalar_one_or_none()

                    if station:
                        # Update existing station
                        if line_tfl_id not in station.lines:
                            station.lines = [*station.lines, line_tfl_id]
                        station.last_updated = datetime.now(UTC)
                    else:
                        # Create new station
                        station = Station(
                            tfl_id=stop_point.id,
                            name=stop_point.commonName,
                            latitude=stop_point.lat,
                            longitude=stop_point.lon,
                            lines=[line_tfl_id],
                            last_updated=datetime.now(UTC),
                        )
                        self.db.add(station)

                    stations.append(station)

                await self.db.commit()

                # Refresh to get database IDs
                for station in stations:
                    await self.db.refresh(station)

            else:
                # Fetch all stations from database
                result = await self.db.execute(select(Station))
                stations = list(result.scalars().all())
                ttl = DEFAULT_STATIONS_CACHE_TTL

            # Cache the results
            await self.cache.set(cache_key, stations, ttl=ttl)

            logger.info("stations_fetched_and_cached", line_tfl_id=line_tfl_id, count=len(stations), ttl=ttl)
            return stations

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_stations_failed", line_tfl_id=line_tfl_id, error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch stations from TfL API.",
            ) from e

    async def fetch_disruptions(self, use_cache: bool = True) -> list[DisruptionResponse]:
        """
        Fetch current disruptions from TfL API.

        Args:
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of disruption responses
        """
        cache_key = "disruptions:current"

        # Try cache first
        if use_cache:
            cached_disruptions: list[DisruptionResponse] | None = await self.cache.get(cache_key)
            if cached_disruptions is not None:
                logger.debug("disruptions_cache_hit", count=len(cached_disruptions))
                return cached_disruptions

        logger.info("fetching_disruptions_from_tfl_api")

        try:
            # Fetch line statuses for tube
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self.line_client.StatusByModeByPathModesQueryDetailQuerySeverityLevel,
                "tube",
            )

            # Check for API error
            self._handle_api_error(response)

            # Extract cache TTL from response
            # Type narrowing: _handle_api_error raises if response is ApiError, so it's safe here
            ttl = self._extract_cache_ttl(response) or DEFAULT_DISRUPTIONS_CACHE_TTL  # type: ignore[arg-type]

            # Process disruptions
            disruptions: list[DisruptionResponse] = []
            # response.content is a LineArray (RootModel), access via .root
            line_data_list = response.content.root  # type: ignore[union-attr]

            for line_data in line_data_list:
                if hasattr(line_data, "lineStatuses") and line_data.lineStatuses is not None:
                    disruptions.extend(
                        DisruptionResponse(
                            line_id=line_data.id,
                            line_name=line_data.name,
                            status_severity=line_status.statusSeverity,
                            status_severity_description=line_status.statusSeverityDescription,
                            reason=line_status.reason if hasattr(line_status, "reason") else None,
                            created_at=datetime.now(UTC),
                        )
                        for line_status in line_data.lineStatuses
                        if line_status.statusSeverity != TFL_GOOD_SERVICE_SEVERITY
                    )

            # Cache the results
            await self.cache.set(cache_key, disruptions, ttl=ttl)

            logger.info("disruptions_fetched_and_cached", count=len(disruptions), ttl=ttl)
            return disruptions

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_disruptions_failed", error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch disruptions from TfL API.",
            ) from e

    async def build_station_graph(self) -> dict[str, int]:
        """
        Build the station connection graph from TfL API data.

        This fetches the station sequences for all tube lines and populates
        the StationConnection table with bidirectional connections.

        Returns:
            Dictionary with build statistics (lines_count, stations_count, connections_count)
        """
        logger.info("building_station_graph_start")

        try:
            # Clear existing connections
            await self.db.execute(delete(StationConnection))
            await self.db.commit()

            # Fetch all lines first
            lines = await self.fetch_lines(use_cache=False)
            lines_count = len(lines)

            stations_set: set[str] = set()
            connections_count = 0

            # Process each line
            for line in lines:
                logger.info("processing_line_for_graph", line_name=line.name, line_tfl_id=line.tfl_id)

                # Fetch stations for this line
                try:
                    line_stations = await self.fetch_stations(line_tfl_id=line.tfl_id, use_cache=False)

                    # Create connections between consecutive stations
                    # Note: This is a simplified approach - actual route sequences would be better
                    for i in range(len(line_stations) - 1):
                        from_station = line_stations[i]
                        to_station = line_stations[i + 1]

                        stations_set.add(from_station.tfl_id)
                        stations_set.add(to_station.tfl_id)

                        # Create bidirectional connections
                        # Forward connection
                        connection_forward = StationConnection(
                            from_station_id=from_station.id,
                            to_station_id=to_station.id,
                            line_id=line.id,
                        )
                        self.db.add(connection_forward)

                        # Reverse connection
                        connection_reverse = StationConnection(
                            from_station_id=to_station.id,
                            to_station_id=from_station.id,
                            line_id=line.id,
                        )
                        self.db.add(connection_reverse)

                        connections_count += 2

                except Exception as e:
                    logger.warning(
                        "failed_to_process_line",
                        line_tfl_id=line.tfl_id,
                        error=str(e),
                    )
                    continue

            # Commit all connections
            await self.db.commit()

            result = {
                "lines_count": lines_count,
                "stations_count": len(stations_set),
                "connections_count": connections_count,
            }

            logger.info("building_station_graph_complete", **result)
            return result

        except Exception as e:
            logger.error("build_station_graph_failed", error=str(e), exc_info=e)
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to build station graph.",
            ) from e

    async def validate_route(self, segments: list[RouteSegmentRequest]) -> tuple[bool, str, int | None]:
        """
        Validate a route by checking if connections exist between segments.

        Uses BFS to check if a path exists between consecutive stations on the specified line.

        Args:
            segments: List of route segments (station + line pairs)

        Returns:
            Tuple of (is_valid, message, invalid_segment_index)
        """
        if len(segments) < MIN_ROUTE_SEGMENTS:
            return False, f"Route must have at least {MIN_ROUTE_SEGMENTS} segments (start and end).", None

        logger.info("validating_route", segments_count=len(segments))

        try:
            # Validate each segment connection
            for i in range(len(segments) - 1):
                current_segment = segments[i]
                next_segment = segments[i + 1]

                # Check if connection exists
                is_connected = await self._check_connection(
                    from_station_id=current_segment.station_id,
                    to_station_id=next_segment.station_id,
                    line_id=current_segment.line_id,
                )

                if not is_connected:
                    # Get station names for helpful error message
                    from_station = await self.db.get(Station, current_segment.station_id)
                    to_station = await self.db.get(Station, next_segment.station_id)
                    line = await self.db.get(Line, current_segment.line_id)

                    message = (
                        f"No connection found between '{from_station.name if from_station else 'Unknown'}' "
                        f"and '{to_station.name if to_station else 'Unknown'}' "
                        f"on {line.name if line else 'Unknown'} line."
                    )

                    logger.warning(
                        "route_validation_failed",
                        segment_index=i,
                        from_station_id=str(current_segment.station_id),
                        to_station_id=str(next_segment.station_id),
                        line_id=str(current_segment.line_id),
                    )

                    return False, message, i

            logger.info("route_validation_successful", segments_count=len(segments))
            return True, "Route is valid.", None

        except Exception as e:
            logger.error("validate_route_failed", error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to validate route.",
            ) from e

    async def _check_connection(
        self,
        from_station_id: uuid.UUID,
        to_station_id: uuid.UUID,
        line_id: uuid.UUID,
    ) -> bool:
        """
        Check if a direct or indirect connection exists between two stations on a line using BFS.

        Args:
            from_station_id: Starting station UUID
            to_station_id: Destination station UUID
            line_id: Line UUID

        Returns:
            True if connection exists, False otherwise
        """
        # BFS to find path
        visited: set[uuid.UUID] = set()
        queue: deque[uuid.UUID] = deque([from_station_id])
        visited.add(from_station_id)

        while queue:
            current_station_id = queue.popleft()

            # Check if we reached the destination
            if current_station_id == to_station_id:
                return True

            # Get all connections from current station on this line
            result = await self.db.execute(
                select(StationConnection).where(
                    StationConnection.from_station_id == current_station_id,
                    StationConnection.line_id == line_id,
                )
            )
            connections = result.scalars().all()

            # Add unvisited neighbors to queue
            for connection in connections:
                if connection.to_station_id not in visited:
                    visited.add(connection.to_station_id)
                    queue.append(connection.to_station_id)

        # No path found
        return False
