"""TfL API service for fetching and caching transport data."""

import asyncio
import uuid
from datetime import UTC, datetime
from functools import partial
from typing import Any
from urllib.parse import urlparse

import structlog
from aiocache import Cache
from aiocache.serializers import PickleSerializer
from fastapi import HTTPException, status
from pydantic_tfl_api import LineClient, StopPointClient
from pydantic_tfl_api.core import ApiError, ResponseModel
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.models.tfl import (
    DisruptionCategory,
    Line,
    SeverityCode,
    Station,
    StationConnection,
    StationDisruption,
    StopType,
)
from app.schemas.tfl import DisruptionResponse, RouteSegmentRequest, StationDisruptionResponse

logger = structlog.get_logger(__name__)

# Default cache TTL values (in seconds) - used if TfL API doesn't provide cache headers
DEFAULT_LINES_CACHE_TTL = 86400  # 24 hours
DEFAULT_STATIONS_CACHE_TTL = 86400  # 24 hours
DEFAULT_DISRUPTIONS_CACHE_TTL = 120  # 2 minutes
DEFAULT_METADATA_CACHE_TTL = 604800  # 7 days

# TfL API constants
TFL_GOOD_SERVICE_SEVERITY = 10  # Status severity value for "Good Service"
MIN_ROUTE_SEGMENTS = 2  # Minimum number of segments required for route validation
MAX_ROUTE_SEGMENTS = 20  # Maximum number of segments allowed for route validation
DEFAULT_MODES = ["tube", "overground", "dlr", "elizabeth-line"]  # Default transport modes to fetch


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

    def _build_modes_cache_key(self, prefix: str, modes: list[str]) -> str:
        """
        Build a cache key for multi-mode endpoints.

        Args:
            prefix: Cache key prefix (e.g., "lines", "line_disruptions")
            modes: List of transport modes

        Returns:
            Formatted cache key with sorted modes
        """
        sorted_modes = ",".join(sorted(modes))
        return f"{prefix}:modes:{sorted_modes}"

    async def fetch_available_modes(self, use_cache: bool = True) -> list[str]:
        """
        Fetch all available transport modes from TfL API.

        Uses the MetaModes endpoint to dynamically discover all transport modes
        available in the TfL network (e.g., tube, overground, dlr, elizabeth-line).

        Args:
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of mode strings (e.g., ["tube", "overground", "dlr"])
        """
        cache_key = "modes:all"

        # Try cache first
        if use_cache:
            cached_modes: list[str] | None = await self.cache.get(cache_key)
            if cached_modes is not None:
                logger.debug("modes_cache_hit", count=len(cached_modes))
                return cached_modes

        logger.info("fetching_modes_from_tfl_api")

        try:
            # Fetch from TfL API (synchronous call wrapped in executor)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self.line_client.MetaModes,
            )

            # Check for API error
            self._handle_api_error(response)

            # Extract modes from response
            # response.content.root is a list of mode strings
            modes: list[str] = list(response.content.root)  # type: ignore[union-attr,arg-type]

            # Use default cache TTL for metadata (7 days)
            # Modes don't change frequently
            ttl = DEFAULT_METADATA_CACHE_TTL

            # Cache the results
            await self.cache.set(cache_key, modes, ttl=ttl)

            logger.info("modes_fetched_and_cached", count=len(modes), ttl=ttl, modes=modes)
            return modes

        except Exception as e:
            logger.error("failed_to_fetch_modes", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch transport modes: {e!s}",
            ) from e

    async def fetch_lines(
        self,
        modes: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[Line]:
        """
        Fetch lines from TfL API for specified transport modes.

        Args:
            modes: List of transport modes to fetch (e.g., ["tube", "overground", "dlr"]).
                   If None, defaults to ["tube", "overground", "dlr", "elizabeth-line"].
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of Line objects from database
        """
        # Default to major transport modes if not specified
        if modes is None:
            modes = DEFAULT_MODES

        cache_key = self._build_modes_cache_key("lines", modes)

        # Try cache first
        if use_cache:
            cached_lines: list[Line] | None = await self.cache.get(cache_key)
            if cached_lines is not None:
                logger.debug("lines_cache_hit", count=len(cached_lines), modes=modes)
                return cached_lines

        logger.info("fetching_lines_from_tfl_api", modes=modes)

        try:
            # Clear existing lines from database
            await self.db.execute(delete(Line))

            # Fetch lines for each mode
            all_lines = []
            ttl = DEFAULT_LINES_CACHE_TTL

            loop = asyncio.get_running_loop()

            for mode in modes:
                logger.debug("fetching_lines_for_mode", mode=mode)

                # Fetch from TfL API (synchronous call wrapped in executor)
                response = await loop.run_in_executor(
                    None,
                    self.line_client.GetByModeByPathModes,
                    mode,
                )

                # Check for API error
                self._handle_api_error(response)

                # Extract cache TTL from response (use minimum TTL across all modes)
                mode_ttl = self._extract_cache_ttl(response) or DEFAULT_LINES_CACHE_TTL  # type: ignore[arg-type]
                ttl = min(ttl, mode_ttl)

                # Process lines for this mode
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
                        mode=mode,
                        last_updated=datetime.now(UTC),
                    )
                    self.db.add(line)
                    all_lines.append(line)

                logger.debug("mode_lines_processed", mode=mode, count=len(line_data_list))

            await self.db.commit()

            # Refresh to get database IDs
            for line in all_lines:
                await self.db.refresh(line)

            # Cache the results
            await self.cache.set(cache_key, all_lines, ttl=ttl)

            logger.info(
                "lines_fetched_and_cached",
                count=len(all_lines),
                modes=modes,
                ttl=ttl,
            )
            return all_lines

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_lines_failed", error=str(e), modes=modes, exc_info=e)
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch lines from TfL API for modes: {modes}",
            ) from e

    async def fetch_severity_codes(self, use_cache: bool = True) -> list[SeverityCode]:
        """
        Fetch severity codes metadata from TfL API.

        Args:
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of SeverityCode objects from database
        """
        cache_key = "severity_codes:all"

        # Try cache first
        if use_cache:
            cached_codes: list[SeverityCode] | None = await self.cache.get(cache_key)
            if cached_codes is not None:
                logger.debug("severity_codes_cache_hit", count=len(cached_codes))
                return cached_codes

        logger.info("fetching_severity_codes_from_tfl_api")

        try:
            # Fetch from TfL API (synchronous call wrapped in executor)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self.line_client.MetaSeverity,
            )

            # Check for API error
            self._handle_api_error(response)

            # Extract cache TTL from response
            ttl = self._extract_cache_ttl(response) or DEFAULT_METADATA_CACHE_TTL  # type: ignore[arg-type]

            # Process and upsert severity codes (avoids race conditions)
            # response.content is a SeverityCodeArray (RootModel), access via .root
            severity_data_list = response.content.root  # type: ignore[union-attr]

            now = datetime.now(UTC)
            for severity_data in severity_data_list:
                # Use PostgreSQL INSERT ... ON CONFLICT to atomically upsert
                stmt = insert(SeverityCode).values(
                    severity_level=severity_data.severityLevel,
                    description=severity_data.description,
                    last_updated=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["severity_level"],
                    set_={
                        "description": stmt.excluded.description,
                        "last_updated": stmt.excluded.last_updated,
                    },
                )
                await self.db.execute(stmt)

            await self.db.commit()

            # Fetch all codes from database to return
            result = await self.db.execute(select(SeverityCode))
            codes = list(result.scalars().all())

            # Cache the results
            await self.cache.set(cache_key, codes, ttl=ttl)

            logger.info("severity_codes_fetched_and_cached", count=len(codes), ttl=ttl)
            return codes

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_severity_codes_failed", error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch severity codes from TfL API.",
            ) from e

    async def fetch_disruption_categories(self, use_cache: bool = True) -> list[DisruptionCategory]:
        """
        Fetch disruption categories metadata from TfL API.

        Args:
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of DisruptionCategory objects from database
        """
        cache_key = "disruption_categories:all"

        # Try cache first
        if use_cache:
            cached_categories: list[DisruptionCategory] | None = await self.cache.get(cache_key)
            if cached_categories is not None:
                logger.debug("disruption_categories_cache_hit", count=len(cached_categories))
                return cached_categories

        logger.info("fetching_disruption_categories_from_tfl_api")

        try:
            # Fetch from TfL API (synchronous call wrapped in executor)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self.line_client.MetaDisruptionCategories,
            )

            # Check for API error
            self._handle_api_error(response)

            # Extract cache TTL from response
            ttl = self._extract_cache_ttl(response) or DEFAULT_METADATA_CACHE_TTL  # type: ignore[arg-type]

            # Process and upsert disruption categories (avoids race conditions)
            # response.content is a RootModel array, access via .root
            category_data_list = response.content.root  # type: ignore[union-attr]

            now = datetime.now(UTC)
            for category_data in category_data_list:
                # Use PostgreSQL INSERT ... ON CONFLICT to atomically upsert
                stmt = insert(DisruptionCategory).values(
                    category_name=category_data,
                    description=None,  # API only provides category name
                    last_updated=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["category_name"],
                    set_={
                        "last_updated": stmt.excluded.last_updated,
                    },
                )
                await self.db.execute(stmt)

            await self.db.commit()

            # Fetch all categories from database to return
            result = await self.db.execute(select(DisruptionCategory))
            categories = list(result.scalars().all())

            # Cache the results
            await self.cache.set(cache_key, categories, ttl=ttl)

            logger.info("disruption_categories_fetched_and_cached", count=len(categories), ttl=ttl)
            return categories

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_disruption_categories_failed", error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch disruption categories from TfL API.",
            ) from e

    async def fetch_stop_types(self, use_cache: bool = True) -> list[StopType]:
        """
        Fetch stop types metadata from TfL API.

        Args:
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of StopType objects from database (filtered to relevant types)
        """
        cache_key = "stop_types:all"

        # Try cache first
        if use_cache:
            cached_types: list[StopType] | None = await self.cache.get(cache_key)
            if cached_types is not None:
                logger.debug("stop_types_cache_hit", count=len(cached_types))
                return cached_types

        logger.info("fetching_stop_types_from_tfl_api")

        try:
            # Fetch from TfL API (synchronous call wrapped in executor)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self.stoppoint_client.MetaStopTypes,
            )

            # Check for API error
            self._handle_api_error(response)

            # Extract cache TTL from response
            ttl = self._extract_cache_ttl(response) or DEFAULT_METADATA_CACHE_TTL  # type: ignore[arg-type]

            # Process and upsert stop types (avoids race conditions)
            # response.content is a RootModel array, access via .root
            type_data_list = response.content.root  # type: ignore[union-attr]

            # Filter to relevant types for our use case
            # These types cover tube, rail, and bus stations which are the main transport modes
            # we're interested in for this application. To extend to other types (e.g., tram, ferry),
            # add the appropriate Naptan type to this set.
            relevant_types = {"NaptanMetroStation", "NaptanRailStation", "NaptanBusCoachStation"}

            now = datetime.now(UTC)
            for type_data in type_data_list:
                # type_data might be a string or object - handle both cases
                type_name = type_data if isinstance(type_data, str) else getattr(type_data, "stopType", str(type_data))

                # Only store relevant types
                if type_name in relevant_types:
                    # Use PostgreSQL INSERT ... ON CONFLICT to atomically upsert
                    stmt = insert(StopType).values(
                        type_name=type_name,
                        description=None,  # API typically only provides type name
                        last_updated=now,
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["type_name"],
                        set_={
                            "last_updated": stmt.excluded.last_updated,
                        },
                    )
                    await self.db.execute(stmt)

            await self.db.commit()

            # Fetch all relevant types from database to return
            result = await self.db.execute(select(StopType).where(StopType.type_name.in_(relevant_types)))
            types = list(result.scalars().all())

            # Cache the results
            await self.cache.set(cache_key, types, ttl=ttl)

            logger.info("stop_types_fetched_and_cached", count=len(types), ttl=ttl)
            return types

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_stop_types_failed", error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch stop types from TfL API.",
            ) from e

    async def _extract_hub_fields(self, stop_point: Any) -> tuple[str | None, str | None]:  # noqa: ANN401
        """
        Extract hub NaPTAN code and fetch hub common name from TfL API.

        Hub information is used to identify cross-mode interchange stations.
        If a hub NaPTAN code exists, makes an API call to fetch the hub details
        and extracts the common name (e.g., "Seven Sisters" for hub "HUBSVS").

        The API call is executed in a thread pool to avoid blocking the event loop.
        The pydantic-tfl-api client is thread-safe as it uses httpx for HTTP requests.

        Args:
            stop_point: Stop point object from TfL API

        Returns:
            Tuple of (hub_naptan_code, hub_common_name)
        """
        hub_code = getattr(stop_point, "hubNaptanCode", None)
        hub_name = None

        # Fetch hub details from API if hub code exists
        if hub_code:
            try:
                loop = asyncio.get_running_loop()
                # Use partial to pass keyword arguments to the API call
                api_call = partial(
                    self.stoppoint_client.GetByPathIdsQueryIncludeCrowdingData,
                    ids=hub_code,
                    includeCrowdingData=False,
                )
                response = await loop.run_in_executor(None, api_call)
                if not isinstance(response, ApiError) and response.content and response.content.root:
                    hub_data = response.content.root[0]
                    hub_name = getattr(hub_data, "commonName", None)
            except Exception as e:
                # Log error but don't fail - hub name is optional
                logger.warning(
                    "failed_to_fetch_hub_details",
                    hub_code=hub_code,
                    error=str(e),
                )

        return hub_code, hub_name

    def _update_existing_station(
        self,
        station: Station,
        line_tfl_id: str,
        hub_code: str | None,
        hub_name: str | None,
    ) -> None:
        """
        Update existing station with line and hub information.

        Args:
            station: Existing station object to update
            line_tfl_id: TfL line ID to add to station's lines
            hub_code: Hub NaPTAN code (or None)
            hub_name: Hub common name (or None)
        """
        if line_tfl_id not in station.lines:
            station.lines = [*station.lines, line_tfl_id]
        station.last_updated = datetime.now(UTC)
        station.hub_naptan_code = hub_code
        station.hub_common_name = hub_name

    def _create_new_station(
        self,
        stop_point: Any,  # noqa: ANN401
        line_tfl_id: str,
        hub_code: str | None,
        hub_name: str | None,
    ) -> Station:
        """
        Create new station from stop point data.

        Args:
            stop_point: Stop point object from TfL API
            line_tfl_id: TfL line ID for the station
            hub_code: Hub NaPTAN code (or None)
            hub_name: Hub common name (or None)

        Returns:
            New Station object (not yet added to session)
        """
        return Station(
            tfl_id=stop_point.id,
            name=stop_point.commonName,
            latitude=stop_point.lat,
            longitude=stop_point.lon,
            lines=[line_tfl_id],
            last_updated=datetime.now(UTC),
            hub_naptan_code=hub_code,
            hub_common_name=hub_name,
        )

    async def _fetch_stations_from_api(self, line_tfl_id: str) -> tuple[list[Station], int]:
        """
        Fetch stations for a line from TfL API and update database.

        This fetches ALL stations on a line, including non-TfL-operated National Rail stations.

        Args:
            line_tfl_id: TfL line ID to fetch stations for

        Returns:
            Tuple of (list of Station objects, cache TTL in seconds)
        """
        # Fetch stations for the line using LineClient with tflOperatedNationalRailStationsOnly=False
        # This ensures we get ALL stations, not just TfL-operated ones
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            self.line_client.StopPointsByPathIdQueryTflOperatedNationalRailStationsOnly,
            line_tfl_id,
            False,  # tflOperatedNationalRailStationsOnly=False to get ALL stations
        )

        # Check for API error
        self._handle_api_error(response)

        # Type narrowing: _handle_api_error raises if response is ApiError, so it's safe here
        ttl = self._extract_cache_ttl(response) or DEFAULT_STATIONS_CACHE_TTL  # type: ignore[arg-type]
        # response.content is a PlaceArray (RootModel), access via .root
        stop_points = response.content.root  # type: ignore[union-attr]

        stations = []
        # Note: This implementation queries the database inside the loop (N+1 pattern).
        # For this hobby project, this is acceptable because:
        # - TfL lines typically have 20-60 stations (small N)
        # - This operation is infrequent (cached station data, runs ~daily)
        # - Database queries are fast (local DB, indexed tfl_id)
        # Bulk fetching could be considered if performance monitoring indicates a problem.
        for stop_point in stop_points:
            # Filter stations by mode - only keep stations with at least one mode in DEFAULT_MODES
            modes = getattr(stop_point, "modes", []) or []  # Handle None case
            if not any(mode in DEFAULT_MODES for mode in modes):
                logger.debug(
                    "station_filtered_by_mode",
                    station_id=stop_point.id,
                    station_name=stop_point.commonName,
                    modes=modes,
                    reason="no_overlap_with_default_modes",
                )
                continue

            # Check if station exists in DB
            result = await self.db.execute(select(Station).where(Station.tfl_id == stop_point.id))
            station = result.scalar_one_or_none()

            # Extract hub fields once
            hub_code, hub_name = await self._extract_hub_fields(stop_point)

            # Log hub detection
            if hub_code:
                logger.debug(
                    "hub_detected",
                    station_id=stop_point.id,
                    station_name=stop_point.commonName,
                    hub_code=hub_code,
                    hub_name=hub_name,
                )

            if station:
                # Update existing station
                self._update_existing_station(station, line_tfl_id, hub_code, hub_name)
            else:
                # Create new station
                station = self._create_new_station(stop_point, line_tfl_id, hub_code, hub_name)
                self.db.add(station)

            stations.append(station)

        await self.db.commit()

        # Refresh to get database IDs
        for station in stations:
            await self.db.refresh(station)

        return stations, ttl

    async def fetch_stations(self, line_tfl_id: str | None = None, use_cache: bool = True) -> list[Station]:
        """
        Fetch stations from TfL API or database cache.

        This method fetches ALL stations on a line, including non-TfL-operated National Rail stations,
        by setting tflOperatedNationalRailStationsOnly=False.

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
                stations, ttl = await self._fetch_stations_from_api(line_tfl_id)
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

    def _extract_disruption_from_route(
        self,
        disruption_data: Any,  # noqa: ANN401
        route: Any,  # noqa: ANN401
    ) -> DisruptionResponse:
        """
        Extract disruption information for a specific route.

        Args:
            disruption_data: Raw disruption data from TfL API
            route: Affected route data

        Returns:
            DisruptionResponse object
        """
        line_id = getattr(route, "id", "unknown")
        line_name = getattr(route, "name", "Unknown")

        return DisruptionResponse(
            line_id=line_id,
            line_name=line_name,
            status_severity=getattr(disruption_data, "categoryDescriptionDetail", 0),
            status_severity_description=getattr(disruption_data, "category", "Unknown"),
            reason=getattr(disruption_data, "description", None),
            created_at=getattr(disruption_data, "created", datetime.now(UTC)),
        )

    def _process_disruption_data(
        self,
        disruption_data_list: list[Any],
    ) -> list[DisruptionResponse]:
        """
        Process raw disruption data into structured responses.

        Args:
            disruption_data_list: List of raw disruption data from TfL API

        Returns:
            List of processed disruption responses
        """
        disruptions: list[DisruptionResponse] = []

        for disruption_data in disruption_data_list:
            if not hasattr(disruption_data, "affectedRoutes") or not disruption_data.affectedRoutes:
                continue

            for route in disruption_data.affectedRoutes:
                disruption = self._extract_disruption_from_route(disruption_data, route)
                disruptions.append(disruption)

        return disruptions

    async def fetch_line_disruptions(
        self,
        modes: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[DisruptionResponse]:
        """
        Fetch current line-level disruptions from TfL API for specified modes.

        Uses the DisruptionByMode endpoint to get detailed disruption information
        for all specified transport modes.

        Args:
            modes: List of transport modes to fetch disruptions for.
                   If None, defaults to ["tube", "overground", "dlr", "elizabeth-line"].
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of disruption responses
        """
        # Default to major transport modes if not specified
        if modes is None:
            modes = DEFAULT_MODES

        cache_key = self._build_modes_cache_key("line_disruptions", modes)

        # Try cache first
        if use_cache:
            cached_disruptions: list[DisruptionResponse] | None = await self.cache.get(cache_key)
            if cached_disruptions is not None:
                logger.debug("line_disruptions_cache_hit", count=len(cached_disruptions), modes=modes)
                return cached_disruptions

        logger.info("fetching_line_disruptions_from_tfl_api", modes=modes)

        try:
            all_disruptions = []
            ttl = DEFAULT_DISRUPTIONS_CACHE_TTL
            loop = asyncio.get_running_loop()

            # Fetch disruptions for each mode
            for mode in modes:
                logger.debug("fetching_disruptions_for_mode", mode=mode)

                response = await loop.run_in_executor(
                    None,
                    self.line_client.DisruptionByModeByPathModes,
                    mode,
                )

                # Check for API error
                self._handle_api_error(response)

                # Extract cache TTL from response (use minimum TTL across all modes)
                mode_ttl = self._extract_cache_ttl(response) or DEFAULT_DISRUPTIONS_CACHE_TTL  # type: ignore[arg-type]
                ttl = min(ttl, mode_ttl)

                # Process disruptions using helper method
                # response.content is a RootModel array of disruptions, access via .root
                disruption_data_list = response.content.root  # type: ignore[union-attr]
                mode_disruptions = self._process_disruption_data(disruption_data_list)
                all_disruptions.extend(mode_disruptions)

                logger.debug("mode_disruptions_processed", mode=mode, count=len(mode_disruptions))

            # Cache the results
            await self.cache.set(cache_key, all_disruptions, ttl=ttl)

            logger.info(
                "line_disruptions_fetched_and_cached",
                count=len(all_disruptions),
                modes=modes,
                ttl=ttl,
            )
            return all_disruptions

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_line_disruptions_failed", error=str(e), modes=modes, exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch line disruptions from TfL API for modes: {modes}",
            ) from e

    async def _create_station_disruption(
        self,
        station: Station,
        disruption_data: Any,  # noqa: ANN401
    ) -> StationDisruptionResponse:
        """
        Create station disruption in database and return response.

        Args:
            station: Station object from database
            disruption_data: Raw disruption data from TfL API

        Returns:
            StationDisruptionResponse object
        """
        # Extract disruption details with defaults
        category = getattr(disruption_data, "category", None)
        description = getattr(disruption_data, "description", "No description available")
        severity = getattr(disruption_data, "categoryDescription", None)
        tfl_id = getattr(disruption_data, "id", str(uuid.uuid4()))
        created_at_source = getattr(disruption_data, "created", datetime.now(UTC))

        # Store in database
        station_disruption = StationDisruption(
            station_id=station.id,
            disruption_category=category,
            description=description,
            severity=severity,
            tfl_id=tfl_id,
            created_at_source=created_at_source,
        )
        self.db.add(station_disruption)

        # Create response object
        return StationDisruptionResponse(
            station_id=station.id,
            station_tfl_id=station.tfl_id,
            station_name=station.name,
            disruption_category=category,
            description=description,
            severity=severity,
            tfl_id=tfl_id,
            created_at_source=created_at_source,
        )

    async def _lookup_station_for_disruption(self, stop: Any) -> Station | None:  # noqa: ANN401
        """
        Look up station in database for a disruption stop.

        Args:
            stop: Stop point data object from TfL API

        Returns:
            Station object or None if not found or invalid
        """
        stop_tfl_id = self._get_stop_ids(stop)

        if not stop_tfl_id:
            logger.warning("station_disruption_missing_tfl_id", stop_data=str(stop))
            return None

        result = await self.db.execute(select(Station).where(Station.tfl_id == stop_tfl_id))
        station = result.scalar_one_or_none()

        if not station:
            logger.debug(
                "station_not_found_for_disruption",
                stop_tfl_id=stop_tfl_id,
            )
            return None

        return station

    async def _process_station_disruption_data(
        self,
        disruption_data_list: list[Any],
    ) -> list[StationDisruptionResponse]:
        """
        Process disruption data for a single mode.

        Args:
            disruption_data_list: List of raw disruption data from TfL API

        Returns:
            List of station disruption responses
        """
        mode_disruptions: list[StationDisruptionResponse] = []

        for disruption_data in disruption_data_list:
            # Extract affected stops from disruption
            if hasattr(disruption_data, "affectedStops") and disruption_data.affectedStops:
                for stop in disruption_data.affectedStops:
                    # Look up station in database by TfL ID
                    station = await self._lookup_station_for_disruption(stop)

                    if not station:
                        continue

                    # Create disruption using helper method
                    disruption_response = await self._create_station_disruption(station, disruption_data)
                    mode_disruptions.append(disruption_response)

        return mode_disruptions

    async def fetch_station_disruptions(
        self,
        modes: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[StationDisruptionResponse]:
        """
        Fetch current station-level disruptions from TfL API for specified modes.

        Uses the StopPoint DisruptionByMode endpoint to get disruptions affecting
        specific stations, including route blocked stops.

        Args:
            modes: List of transport modes to fetch disruptions for.
                   If None, defaults to ["tube", "overground", "dlr", "elizabeth-line"].
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of station disruption responses
        """
        # Default to major transport modes if not specified
        if modes is None:
            modes = DEFAULT_MODES

        cache_key = self._build_modes_cache_key("station_disruptions", modes)

        # Try cache first
        if use_cache:
            cached_disruptions: list[StationDisruptionResponse] | None = await self.cache.get(cache_key)
            if cached_disruptions is not None:
                logger.debug("station_disruptions_cache_hit", count=len(cached_disruptions), modes=modes)
                return cached_disruptions

        logger.info("fetching_station_disruptions_from_tfl_api", modes=modes)

        try:
            # Clear existing station disruptions within the same transaction to minimize the gap
            await self.db.execute(delete(StationDisruption))

            all_disruptions: list[StationDisruptionResponse] = []
            ttl = DEFAULT_DISRUPTIONS_CACHE_TTL
            loop = asyncio.get_running_loop()

            # Fetch station disruptions for each mode
            for mode in modes:
                logger.debug("fetching_station_disruptions_for_mode", mode=mode)

                response = await loop.run_in_executor(
                    None,
                    self.stoppoint_client.DisruptionByModeByPathModesQueryIncludeRouteBlockedStops,
                    mode,
                    True,  # includeRouteBlockedStops=True to get all station-level issues
                )

                # Check for API error
                self._handle_api_error(response)

                # Extract cache TTL from response (use minimum TTL across all modes)
                mode_ttl = self._extract_cache_ttl(response) or DEFAULT_DISRUPTIONS_CACHE_TTL  # type: ignore[arg-type]
                ttl = min(ttl, mode_ttl)

                # Process station disruptions using helper method
                # response.content is a RootModel array of disruptions, access via .root
                disruption_data_list = response.content.root  # type: ignore[union-attr]
                mode_disruptions = await self._process_station_disruption_data(disruption_data_list)
                all_disruptions.extend(mode_disruptions)

                logger.debug("mode_station_disruptions_processed", mode=mode)

            # Commit database changes
            await self.db.commit()

            # Cache the results
            await self.cache.set(cache_key, all_disruptions, ttl=ttl)

            logger.info(
                "station_disruptions_fetched_and_cached",
                count=len(all_disruptions),
                modes=modes,
                ttl=ttl,
            )
            return all_disruptions

        except HTTPException:
            raise
        except Exception as e:
            logger.error("fetch_station_disruptions_failed", error=str(e), modes=modes, exc_info=e)
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch station disruptions from TfL API for modes: {modes}",
            ) from e

    def _get_stop_ids(self, stop: Any) -> str | None:  # noqa: ANN401
        """
        Extract stop ID from stop point data.

        Args:
            stop: Stop point data object

        Returns:
            Stop ID or None if not found
        """
        if hasattr(stop, "id"):
            return str(stop.id)
        if hasattr(stop, "stationId"):
            return str(stop.stationId)
        logger.warning(
            "stop_id_extraction_failed",
            message="Neither 'id' nor 'stationId' found in stop object",
            stop_data=str(stop),
        )
        return None

    async def _get_station_by_tfl_id(self, tfl_id: str) -> Station | None:
        """
        Look up station in database by TfL ID.

        Args:
            tfl_id: TfL station identifier

        Returns:
            Station object or None if not found
        """
        result = await self.db.execute(select(Station).where(Station.tfl_id == tfl_id))
        return result.scalar_one_or_none()

    async def _connection_exists(
        self,
        from_station_id: uuid.UUID,
        to_station_id: uuid.UUID,
        line_id: uuid.UUID,
    ) -> bool:
        """
        Check if a station connection already exists.

        Args:
            from_station_id: Source station database ID
            to_station_id: Destination station database ID
            line_id: Line database ID

        Returns:
            True if connection exists, False otherwise
        """
        result = await self.db.execute(
            select(StationConnection).where(
                StationConnection.from_station_id == from_station_id,
                StationConnection.to_station_id == to_station_id,
                StationConnection.line_id == line_id,
            )
        )
        return result.scalar_one_or_none() is not None

    def _create_connection(
        self,
        from_station_id: uuid.UUID,
        to_station_id: uuid.UUID,
        line_id: uuid.UUID,
    ) -> StationConnection:
        """
        Create a station connection object.

        Args:
            from_station_id: Source station database ID
            to_station_id: Destination station database ID
            line_id: Line database ID

        Returns:
            StationConnection object (not yet added to session)
        """
        return StationConnection(
            from_station_id=from_station_id,
            to_station_id=to_station_id,
            line_id=line_id,
        )

    async def _process_station_pair(
        self,
        current_stop: Any,  # noqa: ANN401
        next_stop: Any,  # noqa: ANN401
        line: Line,
        stations_set: set[str],
        pending_connections: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]],
    ) -> int:
        """
        Process a pair of consecutive stations and create bidirectional connections.

        Args:
            current_stop: Current stop point data
            next_stop: Next stop point data
            line: Line object
            stations_set: Set to track unique station IDs
            pending_connections: Set to track pending connections (from_id, to_id, line_id)

        Returns:
            Number of new connections created (0, 1, or 2)
        """
        # Extract stop IDs
        current_stop_id = self._get_stop_ids(current_stop)
        next_stop_id = self._get_stop_ids(next_stop)

        if not current_stop_id or not next_stop_id:
            return 0

        # Look up stations
        from_station = await self._get_station_by_tfl_id(current_stop_id)
        to_station = await self._get_station_by_tfl_id(next_stop_id)

        if not from_station or not to_station:
            logger.debug(
                "station_not_found_for_connection",
                from_stop_id=current_stop_id,
                to_stop_id=next_stop_id,
                line_tfl_id=line.tfl_id,
            )
            return 0

        # Track stations
        stations_set.add(from_station.tfl_id)
        stations_set.add(to_station.tfl_id)

        connections_created = 0

        # Create forward connection if needed (check pending set to avoid duplicates in same transaction)
        forward_key = (from_station.id, to_station.id, line.id)
        if forward_key not in pending_connections:
            connection = self._create_connection(from_station.id, to_station.id, line.id)
            self.db.add(connection)
            pending_connections.add(forward_key)
            connections_created += 1

        # Create reverse connection if needed (check pending set to avoid duplicates in same transaction)
        reverse_key = (to_station.id, from_station.id, line.id)
        if reverse_key not in pending_connections:
            connection = self._create_connection(to_station.id, from_station.id, line.id)
            self.db.add(connection)
            pending_connections.add(reverse_key)
            connections_created += 1

        return connections_created

    async def _fetch_route_sequence(
        self,
        line_tfl_id: str,
        direction: str,
    ) -> Any:  # noqa: ANN401
        """
        Fetch route sequence for a line and direction from TfL API.

        Args:
            line_tfl_id: TfL line identifier
            direction: "inbound" or "outbound"

        Returns:
            RouteSequence object containing stopPointSequences and orderedLineRoutes

        Raises:
            Exception: If API call fails
        """
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            self.line_client.RouteSequenceByPathIdPathDirectionQueryServiceTypesQueryExcludeCrowding,
            line_tfl_id,
            direction,
            "",  # serviceTypes (empty for all)
            True,  # excludeCrowding
        )

        # Check for API error
        self._handle_api_error(response)

        # Return full route sequence data (contains both stopPointSequences and orderedLineRoutes)
        return response.content  # type: ignore[union-attr]

    async def _process_route_sequence(
        self,
        line: Line,
        direction: str,
        stations_set: set[str],
        pending_connections: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]],
    ) -> tuple[int, Any]:
        """
        Process route sequence for a line and direction.

        Args:
            line: Line object
            direction: "inbound" or "outbound"
            stations_set: Set to track unique station IDs
            pending_connections: Set to track pending connections (from_id, to_id, line_id)

        Returns:
            Tuple of (connections_count, route_data)
                - connections_count: Number of connections created
                - route_data: Full RouteSequence object (contains orderedLineRoutes)
        """
        try:
            route_data = await self._fetch_route_sequence(line.tfl_id, direction)
            connections_count = 0

            # Extract stopPointSequences for connection building
            if hasattr(route_data, "stopPointSequences") and route_data.stopPointSequences:
                sequences = list(route_data.stopPointSequences)

                for sequence in sequences:
                    if not hasattr(sequence, "stopPoint") or not sequence.stopPoint:
                        continue

                    stop_points = sequence.stopPoint

                    # Process consecutive station pairs
                    for i in range(len(stop_points) - 1):
                        connections_count += await self._process_station_pair(
                            stop_points[i],
                            stop_points[i + 1],
                            line,
                            stations_set,
                            pending_connections,
                        )

            return connections_count, route_data

        except Exception as e:
            logger.warning(
                "failed_to_process_direction",
                line_tfl_id=line.tfl_id,
                direction=direction,
                error=str(e),
            )
            return 0, None

    def _store_line_routes(
        self,
        line: Line,
        inbound_route_data: Any | None,  # noqa: ANN401
        outbound_route_data: Any | None,  # noqa: ANN401
    ) -> None:
        """
        Extract and store route variants from RouteSequence data.

        Filters to only "Regular" service types and stores ordered station lists
        for each route variant in the Line.routes JSON field.

        Args:
            line: Line object to update
            inbound_route_data: RouteSequence data for inbound direction (may be None)
            outbound_route_data: RouteSequence data for outbound direction (may be None)
        """
        routes = []

        # Process both directions
        for direction, route_data in [
            ("inbound", inbound_route_data),
            ("outbound", outbound_route_data),
        ]:
            if not route_data or not hasattr(route_data, "orderedLineRoutes"):
                continue

            ordered_routes = route_data.orderedLineRoutes
            if not ordered_routes:
                continue

            # Filter and transform routes
            for ordered_route in ordered_routes:
                # Only store "Regular" service types (defer Night services for MVP)
                service_type = getattr(ordered_route, "serviceType", None)
                if service_type != "Regular":
                    logger.debug(
                        "skipping_non_regular_service",
                        line_tfl_id=line.tfl_id,
                        service_type=service_type,
                        route_name=getattr(ordered_route, "name", "Unknown"),
                    )
                    continue

                # Extract route data
                route_name = getattr(ordered_route, "name", f"Unknown {direction} route")
                naptan_ids = getattr(ordered_route, "naptanIds", [])

                if not naptan_ids:
                    logger.debug(
                        "skipping_route_without_stations",
                        line_tfl_id=line.tfl_id,
                        route_name=route_name,
                    )
                    continue

                # Store route variant
                routes.append(
                    {
                        "name": route_name,
                        "service_type": service_type,
                        "direction": direction,
                        "stations": naptan_ids,
                    }
                )

        # Update line's routes field (stored as JSON in database)
        if routes:
            line.routes = {"routes": routes}
            logger.info(
                "stored_line_routes",
                line_tfl_id=line.tfl_id,
                routes_count=len(routes),
            )
        else:
            logger.warning(
                "no_regular_routes_found",
                line_tfl_id=line.tfl_id,
            )

    async def build_station_graph(self) -> dict[str, int]:
        """
        Build the station connection graph from TfL API data using actual route sequences.

        This fetches the route sequences (inbound and outbound) for all tube lines
        from the TfL API and populates the StationConnection table with bidirectional
        connections based on the actual order of stations on each route.

        Returns:
            Dictionary with build statistics (lines_count, stations_count, connections_count, hubs_count)

        Raises:
            HTTPException: 500 if graph building fails (old connections preserved via rollback)
            HTTPException: 500 if no stations found after fetching (validation failure)
        """
        logger.info("building_station_graph_start")

        try:
            # Fetch all lines
            lines = await self.fetch_lines(use_cache=False)
            logger.info("lines_fetched", lines_count=len(lines))

            # Fetch stations for all lines BEFORE building connections
            # This ensures stations exist in the database for connection creation
            for line in lines:
                logger.info("fetching_stations_for_line", line_tfl_id=line.tfl_id, line_name=line.name)
                await self.fetch_stations(line_tfl_id=line.tfl_id, use_cache=False)

            # Validate that stations were populated
            station_count_result = await self.db.execute(select(func.count()).select_from(Station))
            station_count = station_count_result.scalar_one()

            if station_count == 0:
                logger.error("no_stations_found_after_fetch")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No stations found after fetching from TfL API. Cannot build graph.",
                )

            logger.info("stations_validated", station_count=station_count)

            # Clear existing connections (within transaction - will rollback if building fails)
            await self.db.execute(delete(StationConnection))
            # Required: flush prevents unique constraint violations when rebuilding connections.
            # Without this, SQLAlchemy may reorder operations causing duplicate key errors.
            await self.db.flush()
            logger.info("existing_connections_cleared")

            stations_set: set[str] = set()
            pending_connections: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = set()
            connections_count = 0

            # Process each line
            for line in lines:
                logger.info("processing_line_for_graph", line_name=line.name, line_tfl_id=line.tfl_id)

                # Process both directions and collect route data
                # Note: Duplicate connections are prevented by pending_connections set
                # Even if inbound and outbound routes overlap, we won't create duplicates
                inbound_route_data = None
                outbound_route_data = None

                for direction in ["inbound", "outbound"]:
                    conn_count, route_data = await self._process_route_sequence(
                        line,
                        direction,
                        stations_set,
                        pending_connections,
                    )
                    connections_count += conn_count

                    # Store route data for later processing
                    if direction == "inbound":
                        inbound_route_data = route_data
                    else:
                        outbound_route_data = route_data

                # Extract and store route sequences for this line
                self._store_line_routes(line, inbound_route_data, outbound_route_data)

            # Commit all changes (delete + new connections) atomically
            # If we reach here, everything succeeded
            await self.db.commit()

            # Invalidate all station and line caches since we've rebuilt the graph
            # This ensures subsequent API calls get fresh data from the database
            await self.cache.delete("stations:all")
            for line in lines:
                await self.cache.delete(f"stations:line:{line.tfl_id}")
            # Also clear lines cache in case metadata changed
            await self.cache.delete("lines")
            logger.info("invalidated_all_tfl_caches", lines_invalidated=len(lines))

            # Count stations with hub NaPTAN codes (interchange stations)
            hubs_count_result = await self.db.execute(
                select(func.count()).select_from(Station).where(Station.hub_naptan_code.isnot(None))
            )
            hubs_count = hubs_count_result.scalar_one()

            build_result = {
                "lines_count": len(lines),
                "stations_count": len(stations_set),
                "connections_count": connections_count,
                "hubs_count": hubs_count,
            }

            logger.info("building_station_graph_complete", **build_result)
            return build_result

        except HTTPException:
            # Re-raise HTTP exceptions (validation failures)
            await self.db.rollback()
            raise
        except Exception as e:
            logger.error("build_station_graph_failed", error=str(e), exc_info=e)
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to build station graph.",
            ) from e

    async def get_network_graph(self) -> dict[str, list[dict[str, Any]]]:
        """
        Get the station network graph as an adjacency list for GUI route building.

        Returns a mapping of station TfL IDs to their connected stations with line information.
        This helps the GUI constrain user choices to valid next stations.

        Returns:
            Dictionary mapping station_tfl_id to list of connected stations:
            {
                "station_tfl_id": [
                    {
                        "station_id": UUID,
                        "station_tfl_id": str,
                        "station_name": str,
                        "line_id": UUID,
                        "line_tfl_id": str,
                        "line_name": str,
                    },
                    ...
                ]
            }

        Raises:
            HTTPException: 503 if graph hasn't been built yet
        """
        logger.info("fetching_network_graph")

        try:
            # Check if graph exists
            result = await self.db.execute(select(StationConnection).limit(1))
            if not result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Station graph has not been built yet. Please contact administrator.",
                )

            # Get all connections with from_station, to_station, and line data using aliased joins
            from_station_alias = aliased(Station)
            to_station_alias = aliased(Station)

            result = await self.db.execute(
                select(StationConnection, from_station_alias, to_station_alias, Line)
                .join(from_station_alias, from_station_alias.id == StationConnection.from_station_id)
                .join(to_station_alias, to_station_alias.id == StationConnection.to_station_id)
                .join(Line, Line.id == StationConnection.line_id)
            )
            connections = result.all()

            # Build adjacency list
            graph: dict[str, list[dict[str, Any]]] = {}

            for connection_row in connections:
                # Access aliased stations using index positions (StationConnection, FromStation, ToStation, Line)
                from_station = connection_row[1]
                to_station = connection_row[2]
                line = connection_row[3]

                # Initialize list if needed
                if from_station.tfl_id not in graph:
                    graph[from_station.tfl_id] = []

                # Add connection
                graph[from_station.tfl_id].append(
                    {
                        "station_id": str(to_station.id),
                        "station_tfl_id": to_station.tfl_id,
                        "station_name": to_station.name,
                        "line_id": str(line.id),
                        "line_tfl_id": line.tfl_id,
                        "line_name": line.name,
                    }
                )

            logger.info("network_graph_fetched", stations_count=len(graph))
            return graph

        except HTTPException:
            raise
        except Exception as e:
            logger.error("get_network_graph_failed", error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch network graph.",
            ) from e

    async def get_station_by_tfl_id(self, tfl_id: str) -> Station:
        """
        Get station from database by TfL ID.

        Args:
            tfl_id: TfL station ID (e.g., '940GZZLUOXC' for Oxford Circus)

        Returns:
            Station object from database

        Raises:
            HTTPException(404): If station not found in database
        """
        result = await self.db.execute(select(Station).where(Station.tfl_id == tfl_id))
        station = result.scalar_one_or_none()

        if station is None:
            logger.warning("station_not_found_by_tfl_id", tfl_id=tfl_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Station with TfL ID '{tfl_id}' not found. "
                    "Please ensure TfL data is imported via /admin/tfl/build-graph endpoint."
                ),
            )

        return station

    async def get_line_by_tfl_id(self, tfl_id: str) -> Line:
        """
        Get line from database by TfL ID.

        Args:
            tfl_id: TfL line ID (e.g., 'victoria', 'northern', 'central')

        Returns:
            Line object from database

        Raises:
            HTTPException(404): If line not found in database
        """
        result = await self.db.execute(select(Line).where(Line.tfl_id == tfl_id))
        line = result.scalar_one_or_none()

        if line is None:
            logger.warning("line_not_found_by_tfl_id", tfl_id=tfl_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Line with TfL ID '{tfl_id}' not found. "
                    "Please ensure TfL data is imported via /admin/tfl/build-graph endpoint."
                ),
            )

        return line

    async def validate_route(  # noqa: PLR0912
        self, segments: list[RouteSegmentRequest]
    ) -> tuple[bool, str, int | None]:
        """
        Validate a route by checking if connections exist between segments.

        Uses BFS to check if a path exists between consecutive stations on the specified line.
        Also enforces acyclic routes (no duplicate stations) and maximum segment limits.

        Args:
            segments: List of route segments (station + line pairs)

        Returns:
            Tuple of (is_valid, message, invalid_segment_index)
        """
        # Check minimum segments
        if len(segments) < MIN_ROUTE_SEGMENTS:
            return False, f"Route must have at least {MIN_ROUTE_SEGMENTS} segments (start and end).", None

        # Check maximum segments
        if len(segments) > MAX_ROUTE_SEGMENTS:
            return (
                False,
                f"Route cannot have more than {MAX_ROUTE_SEGMENTS} segments. "
                f"Current route has {len(segments)} segments.",
                None,
            )

        # Check for duplicate stations (enforce acyclic routes)
        station_tfl_ids = [segment.station_tfl_id for segment in segments]
        unique_stations = set(station_tfl_ids)

        if len(unique_stations) != len(station_tfl_ids):
            # Find the duplicate station
            seen: set[str] = set()
            for idx, station_tfl_id in enumerate(station_tfl_ids):
                if station_tfl_id in seen:
                    # Get station name for error message
                    station = await self.get_station_by_tfl_id(station_tfl_id)
                    station_name = station.name if station else "Unknown"

                    logger.warning(
                        "route_validation_failed_duplicate_station",
                        station_tfl_id=station_tfl_id,
                        station_name=station_name,
                        segment_index=idx,
                    )

                    return (
                        False,
                        f"Route cannot visit the same station ('{station_name}') more than once. "
                        f"Duplicate found at segment {idx + 1}.",
                        idx,
                    )
                seen.add(station_tfl_id)

        # Validate that only the final segment can have NULL line_tfl_id
        # All intermediate segments (0 to len-2) must have a line to travel on
        for i in range(len(segments) - 1):
            if segments[i].line_tfl_id is None:
                logger.warning(
                    "route_validation_failed_null_intermediate_line",
                    segment_index=i,
                    station_tfl_id=segments[i].station_tfl_id,
                )
                return (
                    False,
                    f"Segment {i} must have a line_tfl_id. "
                    "Only the final segment (destination) can have NULL line_tfl_id.",
                    i,
                )

        logger.info("validating_route", segments_count=len(segments))

        try:
            # Bulk fetch all stations and lines to avoid redundant lookups
            unique_station_ids = {seg.station_tfl_id for seg in segments}
            # Filter out None values from line_tfl_ids (destination segments have no line)
            unique_line_ids = {seg.line_tfl_id for seg in segments if seg.line_tfl_id is not None}

            # Fetch all stations
            stations_map = {}
            for tfl_id in unique_station_ids:
                station = await self.get_station_by_tfl_id(tfl_id)
                stations_map[tfl_id] = station

            # Fetch all lines
            lines_map = {}
            for tfl_id in unique_line_ids:
                line = await self.get_line_by_tfl_id(tfl_id)
                lines_map[tfl_id] = line

            # Validate each segment connection using cached data
            for i in range(len(segments) - 1):
                current_segment = segments[i]
                next_segment = segments[i + 1]

                # Use cached station and line objects
                from_station = stations_map[current_segment.station_tfl_id]
                to_station = stations_map[next_segment.station_tfl_id]
                # We already validated that intermediate segments have non-null line_tfl_id
                assert current_segment.line_tfl_id is not None  # For type checker
                line = lines_map[current_segment.line_tfl_id]

                # Check if connection exists
                is_connected = await self._check_connection(
                    from_station_id=from_station.id,
                    to_station_id=to_station.id,
                    line_id=line.id,
                )

                if not is_connected:
                    # Check if both stations serve the same line (different branches scenario)
                    from_lines = set(from_station.lines)
                    to_lines = set(to_station.lines)
                    common_lines = from_lines & to_lines

                    if line.tfl_id in common_lines:
                        # Stations are on the same line but different branches
                        message = (
                            f"'{from_station.name}' and '{to_station.name}' are both on the "
                            f"{line.name} line, but they are on different branches that don't connect directly. "
                            f"You may need to select intermediate stations or change lines at an interchange."
                        )
                    else:
                        # Stations are on different lines or connection doesn't exist
                        message = (
                            f"No connection found between '{from_station.name}' "
                            f"and '{to_station.name}' "
                            f"on {line.name} line."
                        )

                    logger.warning(
                        "route_validation_failed",
                        segment_index=i,
                        from_station_tfl_id=current_segment.station_tfl_id,
                        to_station_tfl_id=next_segment.station_tfl_id,
                        line_tfl_id=current_segment.line_tfl_id,
                        from_station_name=from_station.name,
                        to_station_name=to_station.name,
                    )

                    return False, message, i

            logger.info("route_validation_successful", segments_count=len(segments))
            return True, "Route is valid.", None

        except HTTPException:
            # Re-raise HTTP exceptions (e.g., 404 from get_station_by_tfl_id)
            raise
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
        Check if two stations are reachable on the same route sequence.

        This validates that both stations exist in at least one route sequence
        for the specified line, preventing cross-branch travel (e.g., Bank → Charing Cross
        on Northern line, which are on different branches).

        Args:
            from_station_id: Starting station UUID
            to_station_id: Destination station UUID
            line_id: Line UUID

        Returns:
            True if both stations exist in the same route sequence, False otherwise
        """
        # Get station and line objects
        from_station = await self.db.get(Station, from_station_id)
        to_station = await self.db.get(Station, to_station_id)
        line = await self.db.get(Line, line_id)

        if not from_station or not to_station or not line:
            logger.warning(
                "check_connection_missing_entity",
                from_station_id=from_station_id,
                to_station_id=to_station_id,
                line_id=line_id,
            )
            return False

        # Check if route sequences exist for this line
        if not line.routes or "routes" not in line.routes:
            logger.warning(
                "check_connection_no_routes",
                line_tfl_id=line.tfl_id,
                line_name=line.name,
            )
            return False

        # Check each route sequence to see if both stations exist in the same one
        routes = line.routes["routes"]
        for route in routes:
            stations = route.get("stations", [])

            # Check if both stations exist in this route sequence
            if from_station.tfl_id in stations and to_station.tfl_id in stations:
                logger.debug(
                    "connection_found_in_route",
                    route_name=route.get("name", "Unknown"),
                    from_station=from_station.name,
                    to_station=to_station.name,
                )
                # Allow travel in either direction within the route sequence
                return True

        # Stations not found in any common route sequence
        logger.debug(
            "connection_not_found_different_branches",
            from_station=from_station.name,
            to_station=to_station.name,
            line_name=line.name,
        )
        return False

    async def get_line_routes(self, line_tfl_id: str) -> dict[str, Any] | None:
        """
        Get route variants for a specific line.

        Args:
            line_tfl_id: TfL line ID (e.g., "victoria", "elizabeth-line")

        Returns:
            Line routes data (line_tfl_id and list of route variants) or None if not found

        Raises:
            HTTPException: 404 if line not found, 503 if routes haven't been built yet
        """
        logger.info("fetching_line_routes", line_tfl_id=line_tfl_id)

        try:
            # Look up line by TfL ID
            result = await self.db.execute(select(Line).where(Line.tfl_id == line_tfl_id))
            line = result.scalar_one_or_none()

            if not line:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Line '{line_tfl_id}' not found.",
                )

            # Check if routes have been built (None means not built, {} means no routes found)
            if line.routes is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Route data has not been built yet. Please contact administrator.",
                )

            # Return line routes data
            return {
                "line_tfl_id": line.tfl_id,
                "routes": line.routes.get("routes", []),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error("get_line_routes_failed", line_tfl_id=line_tfl_id, error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch routes for line '{line_tfl_id}'.",
            ) from e

    async def get_station_routes(self, station_tfl_id: str) -> dict[str, Any] | None:
        """
        Get all routes passing through a specific station.

        Args:
            station_tfl_id: TfL station ID (e.g., "940GZZLUVIC")

        Returns:
            Station routes data (station_tfl_id, station_name, and list of routes)
            or None if not found

        Raises:
            HTTPException: 404 if station not found, 503 if routes haven't been built yet
        """
        logger.info("fetching_station_routes", station_tfl_id=station_tfl_id)

        try:
            # Look up station by TfL ID
            result = await self.db.execute(select(Station).where(Station.tfl_id == station_tfl_id))
            station = result.scalar_one_or_none()

            if not station:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Station '{station_tfl_id}' not found.",
                )

            # Get all lines that serve this station
            line_tfl_ids = station.lines
            if not line_tfl_ids:
                # Station exists but has no lines (shouldn't happen, but handle gracefully)
                return {
                    "station_tfl_id": station.tfl_id,
                    "station_name": station.name,
                    "routes": [],
                }

            # Fetch all lines that serve this station
            lines_result = await self.db.execute(select(Line).where(Line.tfl_id.in_(line_tfl_ids)))
            lines: list[Line] = list(lines_result.scalars().all())

            # Collect routes that pass through this station
            station_routes: list[dict[str, str]] = []
            for line in lines:
                if line.routes is None:
                    continue

                routes = line.routes.get("routes", [])
                station_routes.extend(
                    {
                        "line_tfl_id": line.tfl_id,
                        "line_name": line.name,
                        "route_name": route.get("name", "Unknown"),
                        "service_type": route.get("service_type", "Unknown"),
                        "direction": route.get("direction", "Unknown"),
                    }
                    for route in routes
                    if station_tfl_id in route.get("stations", [])
                )

            # Check if any routes were found
            if not station_routes and lines:
                # Lines exist but no routes built yet
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Route data has not been built yet. Please contact administrator.",
                )

            return {
                "station_tfl_id": station.tfl_id,
                "station_name": station.name,
                "routes": station_routes,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error("get_station_routes_failed", station_tfl_id=station_tfl_id, error=str(e), exc_info=e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch routes for station '{station_tfl_id}'.",
            ) from e
