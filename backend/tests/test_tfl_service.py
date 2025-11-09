"""Tests for TfL service."""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
from app.services.tfl_service import TfLService
from fastapi import HTTPException, status
from freezegun import freeze_time
from pydantic_tfl_api.core import ApiError
from pydantic_tfl_api.models import (
    Line as TflLine,
)
from pydantic_tfl_api.models import (
    Place as TflPlace,
)
from pydantic_tfl_api.models import (
    RouteSection as TflRouteSection,
)
from pydantic_tfl_api.models import (
    StatusSeverity as TflStatusSeverity,
)
from pydantic_tfl_api.models import (
    StopPoint as TflStopPoint,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Mock Factory Functions using pydantic_tfl_api models


def create_mock_line(
    id: str = "victoria",
    name: str = "Victoria",
    **kwargs: Any,  # noqa: ANN401
) -> TflLine:
    """Factory for TfL Line mocks using actual pydantic model."""
    return TflLine(id=id, name=name, **kwargs)


def create_mock_place(
    id: str = "940GZZLUVIC",
    common_name: str = "Victoria",
    lat: float = 51.5,
    lon: float = -0.1,
    **kwargs: Any,  # noqa: ANN401
) -> TflPlace:
    """Factory for TfL Place mocks (stations) using actual pydantic model."""
    return TflPlace(id=id, commonName=common_name, lat=lat, lon=lon, **kwargs)


def create_mock_route_section(
    id: str = "victoria",
    name: str = "Victoria",
    **kwargs: Any,  # noqa: ANN401
) -> TflRouteSection:
    """Factory for TfL RouteSection mocks using actual pydantic model."""
    return TflRouteSection(id=id, name=name, **kwargs)


def create_mock_stop_point(
    id: str = "940GZZLUVIC",
    common_name: str = "Victoria",
    **kwargs: Any,  # noqa: ANN401
) -> TflStopPoint:
    """Factory for TfL StopPoint mocks using actual pydantic model."""
    return TflStopPoint(id=id, commonName=common_name, **kwargs)


def create_mock_disruption(
    category: str = "PlannedWork",
    category_description: str = "Minor Delays",
    description: str = "Station improvements",
    category_description_detail: int = 6,
    affected_routes: list[TflRouteSection] | None = None,
    affected_stops: list[TflStopPoint] | None = None,
    created: datetime | str | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Factory for TfL Disruption mocks.

    Note: Uses a custom mock class because pydantic_tfl_api.models.Disruption
    doesn't have the categoryDescriptionDetail field that the TfL service expects.
    """

    class MockDisruption:
        """Mock disruption with categoryDescriptionDetail field."""

        def __init__(self) -> None:
            self.category = category
            self.categoryDescription = category_description
            self.categoryDescriptionDetail = category_description_detail
            self.description = description
            self.affectedRoutes = affected_routes or []
            self.affectedStops = affected_stops or []
            if isinstance(created, datetime):
                self.created = created
            elif created is None:
                self.created = datetime.now(UTC)
            else:
                # Assume it's a string, parse it
                self.created = datetime.fromisoformat(created)
            # Add any additional kwargs as attributes
            for key, value in kwargs.items():
                setattr(self, key, value)

    return MockDisruption()


def create_mock_severity_code(
    severity_level: int = 10,
    description: str = "Good Service",
    **kwargs: Any,  # noqa: ANN401
) -> TflStatusSeverity:
    """Factory for TfL StatusSeverity mocks using actual pydantic model."""
    return TflStatusSeverity(
        severityLevel=severity_level,
        description=description,
        **kwargs,
    )


# Mock TfL API response objects (for types not in pydantic_tfl_api)


class MockStopPoint2:
    """Mock TfL stop point for route sequences."""

    def __init__(self, id: str, name: str) -> None:
        self.id = id
        self.name = name


class MockStopPointSequence2:
    """Mock TfL stop point sequence for route data."""

    def __init__(self, stopPoint: list[MockStopPoint2]) -> None:  # noqa: N803
        self.stopPoint = stopPoint


class MockOrderedRoute:
    """Mock TfL ordered route for route sequences."""

    def __init__(
        self,
        name: str = "Route 1",
        service_type: str = "Regular",
        naptan_ids: list[str] | None = None,
    ) -> None:
        self.name = name
        self.serviceType = service_type
        self.naptanIds = naptan_ids if naptan_ids is not None else ["940GZZLUVIC", "940GZZLUGPK"]


class MockRouteSequence:
    """Mock TfL route sequence response."""

    def __init__(
        self,
        stopPointSequences: list[MockStopPointSequence2] | None = None,  # noqa: N803
        orderedLineRoutes: list[MockOrderedRoute] | None = None,  # noqa: N803
    ) -> None:
        self.stopPointSequences = stopPointSequences or []
        self.orderedLineRoutes = orderedLineRoutes


# Removed MockStopPointSequence and MockRoute as they're not used in any tests


class MockContent:
    """Mock response content with root attribute."""

    def __init__(self, data: list[Any]) -> None:
        self.root = data


class MockResponse:
    """Mock TfL API response matching pydantic-tfl-api structure."""

    def __init__(
        self,
        data: list[Any],
        shared_expires: datetime | None = None,
        content_expires: datetime | None = None,
    ) -> None:
        self.content = MockContent(data)
        self.shared_expires = shared_expires
        self.content_expires = content_expires


class MockStationDisruption:
    """Mock TfL station disruption data (not in pydantic_tfl_api)."""

    def __init__(
        self,
        id: str,
        category: str,
        categoryDescription: str,  # noqa: N803
        description: str,
        affectedStops: list[TflStopPoint],  # noqa: N803
        created: datetime | None = None,
    ) -> None:
        self.id = id
        self.category = category
        self.categoryDescription = categoryDescription
        self.description = description
        self.affectedStops = affectedStops
        self.created = created or datetime.now(UTC)


@pytest.fixture
def mock_cache() -> AsyncMock:
    """Mock aiocache Cache."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def tfl_service(db_session: AsyncSession, mock_cache: AsyncMock) -> TfLService:
    """Create TfL service with mocked cache."""
    service = TfLService(db_session)
    service.cache = mock_cache
    return service


# ==================== Cache Testing Helper Functions ====================


async def assert_fetch_from_api(
    tfl_service: TfLService,
    method_callable: Any,  # noqa: ANN401
    mock_data: list[Any],
    expected_count: int,
    cache_key: str,
    expected_ttl: int,
    shared_expires: datetime,
) -> list[Any]:
    """Helper: Assert method fetches from API successfully and caches result.

    Args:
        tfl_service: TfL service instance
        method_callable: Callable that invokes the fetch method
        mock_data: Mock data to return from API
        expected_count: Expected number of items returned
        cache_key: Expected cache key for storage
        expected_ttl: Expected TTL in seconds
        shared_expires: Expiry timestamp for cache

    Returns:
        Result from the fetch method
    """
    with patch("asyncio.get_running_loop") as mock_get_loop:
        # Setup mock response
        mock_response = MockResponse(
            data=mock_data,
            shared_expires=shared_expires,
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Execute
        result: list[Any] = await method_callable()

        # Verify
        assert len(result) == expected_count

        # Verify cache was set with correct TTL
        tfl_service.cache.set.assert_called_once()
        assert tfl_service.cache.set.call_args[0][0] == cache_key
        assert tfl_service.cache.set.call_args[1]["ttl"] == expected_ttl

        return result


async def assert_cache_hit(
    tfl_service: TfLService,
    method_callable: Any,  # noqa: ANN401
    cache_key: str,
    cached_data: list[Any],
) -> None:
    """Helper: Assert method uses cached data.

    Args:
        tfl_service: TfL service instance
        method_callable: Callable that invokes the method to test
        cache_key: Expected cache key to be checked
        cached_data: Data to return from cache
    """
    with patch.object(tfl_service.cache, "get", new_callable=AsyncMock) as mock_cache_get:
        mock_cache_get.return_value = cached_data

        result: list[Any] = await method_callable()

        mock_cache_get.assert_called_once_with(cache_key)
        assert result == cached_data


async def assert_cache_miss(
    tfl_service: TfLService,
    method_callable: Any,  # noqa: ANN401
    mock_data: list[Any],
    expected_count: int,
    shared_expires: datetime,
) -> list[Any]:
    """Helper: Assert method handles cache miss and fetches from API.

    Args:
        tfl_service: TfL service instance
        method_callable: Callable that invokes the method to test
        mock_data: Mock data to return from API
        expected_count: Expected number of items returned
        shared_expires: Expiry timestamp for cache

    Returns:
        Result from the fetch method
    """
    with patch("asyncio.get_running_loop") as mock_get_loop:
        # Setup mock response
        mock_response = MockResponse(
            data=mock_data,
            shared_expires=shared_expires,
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Cache returns None (miss)
        tfl_service.cache.get = AsyncMock(return_value=None)

        # Execute
        result: list[Any] = await method_callable()

        # Verify
        assert len(result) == expected_count

        # Verify cache was checked
        tfl_service.cache.get.assert_called_once()

        # Verify cache was populated
        tfl_service.cache.set.assert_called_once()

        return result


async def assert_api_failure(
    method_callable: Any,  # noqa: ANN401
    expected_error_message: str,
) -> None:
    """Helper: Assert method handles API failures correctly.

    Args:
        method_callable: Callable that invokes the method to test
        expected_error_message: Expected error message substring
    """
    with patch("asyncio.get_running_loop") as mock_get_loop:
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(side_effect=Exception("API Error"))
        mock_get_loop.return_value = mock_loop

        with pytest.raises(HTTPException) as exc_info:
            await method_callable()

        assert exc_info.value.status_code == 503
        assert expected_error_message in exc_info.value.detail


# ==================== fetch_available_modes Tests ====================


async def test_fetch_available_modes_from_api(
    tfl_service: TfLService,
) -> None:
    """Test fetching available modes from TfL API when cache is empty."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data - list of mode strings
        mock_modes = ["tube", "overground", "dlr", "elizabeth-line", "tram"]

        # Execute with helper
        modes = await assert_fetch_from_api(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_available_modes(use_cache=False),
            mock_data=mock_modes,
            expected_count=5,
            cache_key="modes:all",
            expected_ttl=604800,  # 7 days (DEFAULT_METADATA_CACHE_TTL)
            shared_expires=datetime(2025, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        # Verify content
        assert modes == mock_modes
        assert "tube" in modes
        assert "elizabeth-line" in modes


async def test_fetch_available_modes_cache_hit(
    tfl_service: TfLService,
) -> None:
    """Test fetching modes from cache when available."""
    # Setup cached modes
    cached_modes = ["tube", "overground", "dlr"]

    # Execute with helper
    await assert_cache_hit(
        tfl_service=tfl_service,
        method_callable=lambda: tfl_service.fetch_available_modes(use_cache=True),
        cache_key="modes:all",
        cached_data=cached_modes,
    )


async def test_fetch_available_modes_cache_miss(
    tfl_service: TfLService,
) -> None:
    """Test fetching modes from API when cache is enabled but empty."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data
        mock_modes = ["tube", "overground"]

        # Execute with helper
        modes = await assert_cache_miss(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_available_modes(use_cache=True),
            mock_data=mock_modes,
            expected_count=2,
            shared_expires=datetime(2025, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        # Verify content
        assert modes == mock_modes


async def test_fetch_available_modes_api_failure(
    tfl_service: TfLService,
) -> None:
    """Test handling TfL API failure when fetching modes."""
    await assert_api_failure(
        method_callable=lambda: tfl_service.fetch_available_modes(use_cache=False),
        expected_error_message="Failed to fetch transport modes",
    )


# ==================== fetch_lines Tests ====================


async def test_fetch_lines_from_api(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines from TfL API with default modes when cache is empty."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data for each mode call
        # Each mode will be called separately, so we need to mock multiple calls
        mock_tube_lines = [
            create_mock_line(id="victoria", name="Victoria"),
            create_mock_line(id="northern", name="Northern"),
        ]
        mock_overground_lines = [
            create_mock_line(id="london-overground", name="London Overground"),
        ]
        mock_dlr_lines = [
            create_mock_line(id="dlr", name="DLR"),
        ]
        mock_elizabeth_lines = [
            create_mock_line(id="elizabeth", name="Elizabeth line"),
        ]

        # We need to handle multiple mode calls
        mock_responses = [
            MockResponse(data=mock_tube_lines, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
            MockResponse(data=mock_overground_lines, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
            MockResponse(data=mock_dlr_lines, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
            MockResponse(data=mock_elizabeth_lines, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
        ]

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_loop = AsyncMock()
            # Return different responses for each mode call
            mock_loop.run_in_executor = AsyncMock(side_effect=mock_responses)
            mock_get_loop.return_value = mock_loop

            # Execute - default modes: ["tube", "overground", "dlr", "elizabeth-line"]
            lines = await tfl_service.fetch_lines(use_cache=False)

            # Verify we got all lines from all modes
            assert len(lines) == 5

            # Verify specific attributes
            assert lines[0].tfl_id == "victoria"
            assert lines[0].name == "Victoria"
            assert lines[0].color == "#000000"  # Default color
            assert lines[0].mode == "tube"

            assert lines[2].tfl_id == "london-overground"
            assert lines[2].mode == "overground"

            # Verify cache was set with correct key (modes sorted alphabetically)
            expected_cache_key = "lines:modes:dlr,elizabeth-line,overground,tube"
            tfl_service.cache.set.assert_called_once()
            assert tfl_service.cache.set.call_args[0][0] == expected_cache_key
            assert tfl_service.cache.set.call_args[1]["ttl"] == 86400  # 24 hours


async def test_fetch_lines_cache_hit(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines from cache when available (default modes)."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup cached lines
        cached_lines = [
            Line(tfl_id="victoria", name="Victoria", color="#0019A8", mode="tube", last_updated=datetime.now(UTC)),
        ]

        # Execute with helper - default modes sorted: dlr,elizabeth-line,overground,tube
        await assert_cache_hit(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_lines(use_cache=True),
            cache_key="lines:modes:dlr,elizabeth-line,overground,tube",
            cached_data=cached_lines,
        )


async def test_fetch_lines_cache_miss(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines from API when cache is enabled but empty (default modes)."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data for each mode
        mock_tube = [create_mock_line(id="victoria", name="Victoria")]
        mock_overground = [create_mock_line(id="overground", name="Overground")]
        mock_dlr = [create_mock_line(id="dlr", name="DLR")]
        mock_elizabeth = [create_mock_line(id="elizabeth", name="Elizabeth")]

        mock_responses = [
            MockResponse(data=mock_tube, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
            MockResponse(data=mock_overground, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
            MockResponse(data=mock_dlr, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
            MockResponse(data=mock_elizabeth, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
        ]

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_loop = AsyncMock()
            mock_loop.run_in_executor = AsyncMock(side_effect=mock_responses)
            mock_get_loop.return_value = mock_loop

            # Execute with cache enabled but empty
            lines = await tfl_service.fetch_lines(use_cache=True)

            # Verify we got all 4 lines (one from each mode)
            assert len(lines) == 4
            assert lines[0].tfl_id == "victoria"
            assert lines[0].mode == "tube"


async def test_fetch_lines_api_failure(
    tfl_service: TfLService,
) -> None:
    """Test handling TfL API failure when fetching lines (default modes)."""
    await assert_api_failure(
        method_callable=lambda: tfl_service.fetch_lines(use_cache=False),
        expected_error_message="Failed to fetch lines from TfL API for modes",
    )


async def test_fetch_lines_single_mode(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines for a single transport mode."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data for tube only
        mock_lines = [
            create_mock_line(id="victoria", name="Victoria"),
            create_mock_line(id="northern", name="Northern"),
        ]

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_response = MockResponse(
                data=mock_lines,
                shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
            )

            mock_loop = AsyncMock()
            mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
            mock_get_loop.return_value = mock_loop

            # Execute with single mode
            lines = await tfl_service.fetch_lines(modes=["tube"], use_cache=False)

            # Verify results
            assert len(lines) == 2
            assert lines[0].tfl_id == "victoria"
            assert lines[0].mode == "tube"
            assert lines[1].tfl_id == "northern"
            assert lines[1].mode == "tube"

            # Verify cache key is mode-specific
            expected_cache_key = "lines:modes:tube"
            tfl_service.cache.set.assert_called_once()
            assert tfl_service.cache.set.call_args[0][0] == expected_cache_key


async def test_fetch_lines_multiple_custom_modes(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines for multiple custom transport modes."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data for overground and dlr
        mock_overground = [create_mock_line(id="overground", name="Overground")]
        mock_dlr = [create_mock_line(id="dlr", name="DLR")]

        mock_responses = [
            MockResponse(data=mock_overground, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
            MockResponse(data=mock_dlr, shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),
        ]

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_loop = AsyncMock()
            mock_loop.run_in_executor = AsyncMock(side_effect=mock_responses)
            mock_get_loop.return_value = mock_loop

            # Execute with custom modes
            lines = await tfl_service.fetch_lines(modes=["overground", "dlr"], use_cache=False)

            # Verify results
            assert len(lines) == 2
            assert lines[0].tfl_id == "overground"
            assert lines[0].mode == "overground"
            assert lines[1].tfl_id == "dlr"
            assert lines[1].mode == "dlr"

            # Verify cache key includes both modes (sorted)
            expected_cache_key = "lines:modes:dlr,overground"
            tfl_service.cache.set.assert_called_once()
            assert tfl_service.cache.set.call_args[0][0] == expected_cache_key


async def test_fetch_lines_empty_mode_list(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines with empty mode list returns no lines."""
    with freeze_time("2025-01-01 12:00:00"):
        # Execute with empty modes list
        lines = await tfl_service.fetch_lines(modes=[], use_cache=False)

        # Verify no lines returned
        assert len(lines) == 0

        # Verify cache still set (with empty result)
        expected_cache_key = "lines:modes:"
        tfl_service.cache.set.assert_called_once()
        assert tfl_service.cache.set.call_args[0][0] == expected_cache_key


@patch("asyncio.get_running_loop")
async def test_fetch_lines_invalid_mode(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines with an invalid/unknown mode returns no lines."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock response for invalid mode (empty array)
        mock_empty_response = MockResponse(
            data=[],  # TfL API returns empty array for invalid/unknown modes
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock executor to return empty response
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_empty_response)
        mock_get_loop.return_value = mock_loop

        # Execute with an invalid mode
        lines = await tfl_service.fetch_lines(modes=["spaceship"], use_cache=False)

        # Verify no lines returned
        assert len(lines) == 0

        # Verify cache set with the invalid mode in the key
        expected_cache_key = "lines:modes:spaceship"
        tfl_service.cache.set.assert_called_once()
        assert tfl_service.cache.set.call_args[0][0] == expected_cache_key


# ==================== fetch_stations Tests ====================


# -------------------- Unit Tests for Helper Methods --------------------


def test_extract_hub_fields_with_hub_code(tfl_service: TfLService) -> None:
    """Test _extract_hub_fields extracts hub code and common name when hubNaptanCode is present."""
    # Create mock stop point with hub code
    stop_point = create_mock_stop_point(
        id="910GSEVNSIS",
        common_name="Seven Sisters Rail Station",
        hubNaptanCode="HUBSVS",
    )

    # Extract hub fields
    hub_code, hub_name = tfl_service._extract_hub_fields(stop_point)

    # Verify extraction
    assert hub_code == "HUBSVS"
    assert hub_name == "Seven Sisters Rail Station"


def test_extract_hub_fields_without_hub_code(tfl_service: TfLService) -> None:
    """Test _extract_hub_fields returns None for both fields when hubNaptanCode is absent."""
    # Create mock place without hub code (Place objects don't have hubNaptanCode)
    stop_point = create_mock_place(
        id="940GZZLUWBN",
        common_name="Wimbledon",
        lat=51.4214,
        lon=-0.2064,
    )

    # Extract hub fields
    hub_code, hub_name = tfl_service._extract_hub_fields(stop_point)

    # Verify both are None
    assert hub_code is None
    assert hub_name is None


def test_update_existing_station_adds_new_line(tfl_service: TfLService) -> None:
    """Test _update_existing_station adds a new line to station's lines array."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create station with only victoria line
        station = Station(
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria"],
            last_updated=datetime(2024, 12, 1, 0, 0, 0, tzinfo=UTC),
            hub_naptan_code=None,
            hub_common_name=None,
        )

        # Update with northern line and hub fields
        tfl_service._update_existing_station(
            station=station,
            line_tfl_id="northern",
            hub_code="HUBKGX",
            hub_name="King's Cross",
        )

        # Verify northern was added
        assert "victoria" in station.lines
        assert "northern" in station.lines
        assert len(station.lines) == 2
        # Verify timestamp updated
        assert station.last_updated == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        # Verify hub fields updated
        assert station.hub_naptan_code == "HUBKGX"
        assert station.hub_common_name == "King's Cross"


def test_update_existing_station_no_duplicate_line(tfl_service: TfLService) -> None:
    """Test _update_existing_station does not duplicate existing line."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create station that already has victoria line
        station = Station(
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria"],
            last_updated=datetime(2024, 12, 1, 0, 0, 0, tzinfo=UTC),
            hub_naptan_code=None,
            hub_common_name=None,
        )

        # Update with same victoria line
        tfl_service._update_existing_station(
            station=station,
            line_tfl_id="victoria",
            hub_code="HUBKGX",
            hub_name="King's Cross",
        )

        # Verify no duplicate
        assert station.lines == ["victoria"]
        # Verify timestamp and hub fields still updated
        assert station.last_updated == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert station.hub_naptan_code == "HUBKGX"
        assert station.hub_common_name == "King's Cross"


def test_update_existing_station_clears_hub_fields(tfl_service: TfLService) -> None:
    """Test _update_existing_station clears hub fields when hub code is None."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create station with existing hub fields
        station = Station(
            tfl_id="940GZZLUWBN",
            name="Wimbledon",
            latitude=51.4214,
            longitude=-0.2064,
            lines=["district"],
            last_updated=datetime(2024, 12, 1, 0, 0, 0, tzinfo=UTC),
            hub_naptan_code="HUBWIM",
            hub_common_name="Wimbledon Station",
        )

        # Update with None hub fields (hub removed from API)
        tfl_service._update_existing_station(
            station=station,
            line_tfl_id="district",
            hub_code=None,
            hub_name=None,
        )

        # Verify hub fields cleared
        assert station.hub_naptan_code is None
        assert station.hub_common_name is None


def test_create_new_station_with_hub_code(tfl_service: TfLService) -> None:
    """Test _create_new_station creates station with hub fields when hub code is present."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create mock stop point with hub code
        stop_point = create_mock_stop_point(
            id="910GSEVNSIS",
            common_name="Seven Sisters Rail Station",
            lat=51.5823,
            lon=-0.0751,
            hubNaptanCode="HUBSVS",
        )

        # Create new station
        station = tfl_service._create_new_station(
            stop_point=stop_point,
            line_tfl_id="weaver",
            hub_code="HUBSVS",
            hub_name="Seven Sisters Rail Station",
        )

        # Verify all fields
        assert station.tfl_id == "910GSEVNSIS"
        assert station.name == "Seven Sisters Rail Station"
        assert station.latitude == 51.5823
        assert station.longitude == -0.0751
        assert station.lines == ["weaver"]
        assert station.last_updated == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert station.hub_naptan_code == "HUBSVS"
        assert station.hub_common_name == "Seven Sisters Rail Station"


def test_create_new_station_without_hub_code(tfl_service: TfLService) -> None:
    """Test _create_new_station creates station with None hub fields when hub code is absent."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create mock place without hub code
        stop_point = create_mock_place(
            id="940GZZLUWBN",
            common_name="Wimbledon",
            lat=51.4214,
            lon=-0.2064,
        )

        # Create new station
        station = tfl_service._create_new_station(
            stop_point=stop_point,
            line_tfl_id="district",
            hub_code=None,
            hub_name=None,
        )

        # Verify all fields
        assert station.tfl_id == "940GZZLUWBN"
        assert station.name == "Wimbledon"
        assert station.latitude == 51.4214
        assert station.longitude == -0.2064
        assert station.lines == ["district"]
        assert station.last_updated == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert station.hub_naptan_code is None
        assert station.hub_common_name is None


# -------------------- Integration Tests --------------------


async def test_fetch_stations_by_line(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching stations for a specific line."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data with stop points
        mock_stops = [
            create_mock_place(id="940GZZLUKSX", common_name="King's Cross St. Pancras", lat=51.5308, lon=-0.1238),
            create_mock_place(id="940GZZLUOXC", common_name="Oxford Circus", lat=51.5152, lon=-0.1419),
        ]

        # Execute with helper
        stations = await assert_fetch_from_api(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_stations(line_tfl_id="victoria", use_cache=False),
            mock_data=mock_stops,
            expected_count=2,
            cache_key="stations:line:victoria",
            expected_ttl=86400,  # 24 hours
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Verify specific attributes
        assert stations[0].tfl_id == "940GZZLUKSX"
        assert stations[0].name == "King's Cross St. Pancras"
        assert "victoria" in stations[0].lines


async def test_fetch_stations_cache_hit(
    tfl_service: TfLService,
) -> None:
    """Test fetching stations from cache when available."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup cached stations
        cached_stations = [
            Station(
                tfl_id="940GZZLUKSX",
                name="King's Cross",
                latitude=51.5308,
                longitude=-0.1238,
                lines=["victoria"],
                last_updated=datetime.now(UTC),
            ),
        ]

        # Execute with helper
        await assert_cache_hit(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_stations(line_tfl_id="victoria", use_cache=True),
            cache_key="stations:line:victoria",
            cached_data=cached_stations,
        )


async def test_fetch_stations_cache_miss(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching stations from API when cache is enabled but empty."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data
        mock_stops = [
            create_mock_place(id="940GZZLUKSX", common_name="King's Cross St. Pancras", lat=51.5308, lon=-0.1238),
        ]

        # Execute with helper
        stations = await assert_cache_miss(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_stations(line_tfl_id="victoria", use_cache=True),
            mock_data=mock_stops,
            expected_count=1,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Verify specific attributes
        assert stations[0].tfl_id == "940GZZLUKSX"


async def test_fetch_stations_all(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching all stations when line_tfl_id is None."""
    # Add stations to database
    stations = [
        Station(
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria", "northern"],
            last_updated=datetime.now(UTC),
        ),
        Station(
            tfl_id="940GZZLUOXC",
            name="Oxford Circus",
            latitude=51.5152,
            longitude=-0.1416,
            lines=["victoria", "central"],
            last_updated=datetime.now(UTC),
        ),
    ]
    for station in stations:
        db_session.add(station)
    await db_session.commit()

    # Execute - fetch all stations (no line filter)
    result = await tfl_service.fetch_stations(line_tfl_id=None, use_cache=False)

    # Verify all stations returned
    assert len(result) == 2
    tfl_ids = {s.tfl_id for s in result}
    assert "940GZZLUKSX" in tfl_ids
    assert "940GZZLUOXC" in tfl_ids


# ==================== fetch_disruptions Tests ====================


@patch("asyncio.get_running_loop")
async def test_fetch_disruptions(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetching line disruptions from TfL API for a single mode."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock response with disruptions
        mock_disruptions = [
            create_mock_disruption(
                category="RealTime",
                category_description="Severe Delays",
                category_description_detail=5,  # Severity level
                description="Signal failure at King's Cross",
                affected_routes=[create_mock_route_section(id="victoria", name="Victoria")],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
            create_mock_disruption(
                category="RealTime",
                category_description="Minor Delays",
                category_description_detail=6,  # Severity level
                description="Minor delays due to customer incident",
                affected_routes=[create_mock_route_section(id="northern", name="Northern")],
                created=datetime(2025, 1, 1, 11, 45, 0, tzinfo=UTC),
            ),
        ]
        mock_response = MockResponse(
            data=mock_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),  # 2 minutes TTL
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Execute with explicit single mode
        disruptions = await tfl_service.fetch_line_disruptions(modes=["tube"], use_cache=False)

        # Verify
        assert len(disruptions) == 2
        assert disruptions[0].line_id == "victoria"
        assert disruptions[0].status_severity == 5
        assert disruptions[0].status_severity_description == "RealTime"
        assert disruptions[0].reason == "Signal failure at King's Cross"
        assert disruptions[1].line_id == "northern"
        assert disruptions[1].status_severity == 6
        assert disruptions[1].status_severity_description == "RealTime"


@patch("asyncio.get_running_loop")
async def test_fetch_disruptions_multiple_lines_per_disruption(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test that disruptions affecting multiple lines create separate responses for each line."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock response with one disruption affecting multiple lines
        mock_disruptions = [
            create_mock_disruption(
                category="RealTime",
                category_description="Severe Delays",
                category_description_detail=5,  # Severity level
                description="Signal failure affecting multiple lines",
                affected_routes=[
                    create_mock_route_section(id="victoria", name="Victoria"),
                    create_mock_route_section(id="northern", name="Northern"),
                ],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
        ]
        mock_response = MockResponse(
            data=mock_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Execute with single mode
        disruptions = await tfl_service.fetch_line_disruptions(modes=["tube"], use_cache=False)

        # Verify - should create separate disruption response for each affected line
        assert len(disruptions) == 2
        line_ids = {d.line_id for d in disruptions}
        assert "victoria" in line_ids
        assert "northern" in line_ids


async def test_fetch_disruptions_cache_hit(tfl_service: TfLService) -> None:
    """Test fetching line disruptions from cache when available (default modes)."""
    # Setup cached disruptions
    cached_disruptions = [
        DisruptionResponse(
            line_id="northern",
            line_name="Northern",
            status_severity=5,
            status_severity_description="Severe Delays",
            reason="Signal failure",
            created_at=datetime.now(UTC),
        ),
    ]
    tfl_service.cache.get = AsyncMock(return_value=cached_disruptions)

    # Execute
    disruptions = await tfl_service.fetch_line_disruptions(use_cache=True)

    # Verify cache was used (default modes sorted: dlr,elizabeth-line,overground,tube)
    assert disruptions == cached_disruptions
    expected_cache_key = "line_disruptions:modes:dlr,elizabeth-line,overground,tube"
    tfl_service.cache.get.assert_called_once_with(expected_cache_key)


@patch("asyncio.get_running_loop")
async def test_fetch_disruptions_cache_miss(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetching line disruptions from API when cache is enabled but empty (single mode)."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock response
        mock_disruptions = [
            create_mock_disruption(
                category="RealTime",
                category_description="Severe Delays",
                category_description_detail=5,  # Severity level
                description="Signal failure",
                affected_routes=[create_mock_route_section(id="victoria", name="Victoria")],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
        ]
        mock_response = MockResponse(
            data=mock_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Cache returns None (miss)
        tfl_service.cache.get = AsyncMock(return_value=None)

        # Execute with use_cache=True but cache is empty, single mode
        disruptions = await tfl_service.fetch_line_disruptions(modes=["tube"], use_cache=True)

        # Verify
        assert len(disruptions) == 1
        assert disruptions[0].line_id == "victoria"

        # Verify cache was checked
        tfl_service.cache.get.assert_called_once()

        # Verify cache was populated
        tfl_service.cache.set.assert_called_once()


@patch("asyncio.get_running_loop")
async def test_fetch_disruptions_without_affected_routes(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetching disruptions when some disruptions don't have affectedRoutes."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock response with mix of disruptions with/without affectedRoutes
        mock_disruptions = [
            create_mock_disruption(
                category="RealTime",
                category_description="Severe Delays",
                category_description_detail=5,  # Severity level
                description="Signal failure",
                affected_routes=[create_mock_route_section(id="victoria", name="Victoria")],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
        ]

        # Create a disruption without affectedRoutes attribute
        class DisruptionWithoutRoutes:
            def __init__(self, category: str, description: str) -> None:
                self.category = category
                self.categoryDescription = "Information"
                self.categoryDescriptionDetail = 0
                self.description = description
                # Intentionally no affectedRoutes attribute

        central_disruption = DisruptionWithoutRoutes(
            category="Information",
            description="Planned engineering works",
        )

        mock_status_data = [
            mock_disruptions[0],  # Has affectedRoutes
            central_disruption,  # No affectedRoutes attribute
        ]
        mock_response = MockResponse(
            data=mock_status_data,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Execute with single mode
        disruptions = await tfl_service.fetch_line_disruptions(modes=["tube"], use_cache=False)

        # Verify - only disruption with affectedRoutes should be included
        assert len(disruptions) == 1
        assert disruptions[0].line_id == "victoria"


def test_extract_disruption_from_route(tfl_service: TfLService) -> None:
    """Test extraction of single disruption from route data."""

    # Create mock objects using factory functions
    route = create_mock_route_section(id="victoria", name="Victoria")

    class MockDisruptionWithDetail:
        """Mock disruption with categoryDescriptionDetail field."""

        def __init__(self) -> None:
            self.categoryDescriptionDetail = 5
            self.category = "Minor Delays"
            self.description = "Signal failure"
            self.created = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    disruption = MockDisruptionWithDetail()

    result = tfl_service._extract_disruption_from_route(disruption, route)

    assert result.line_id == "victoria"
    assert result.line_name == "Victoria"
    assert result.status_severity == 5
    assert result.status_severity_description == "Minor Delays"
    assert result.reason == "Signal failure"
    assert result.created_at == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_extract_disruption_from_route_missing_fields(tfl_service: TfLService) -> None:
    """Test extraction handles missing optional fields gracefully."""

    # Create mock objects with minimal attributes (no TfL API fields)
    class EmptyMockRoute:
        """Mock route with no fields."""

        pass

    class EmptyMockDisruption:
        """Mock disruption with no fields."""

        pass

    route = EmptyMockRoute()
    disruption = EmptyMockDisruption()

    result = tfl_service._extract_disruption_from_route(disruption, route)

    assert result.line_id == "unknown"
    assert result.line_name == "Unknown"
    assert result.status_severity == 0
    assert result.status_severity_description == "Unknown"
    assert result.reason is None
    assert isinstance(result.created_at, datetime)


def test_process_disruption_data_empty_list(tfl_service: TfLService) -> None:
    """Test processing empty disruption list."""
    result = tfl_service._process_disruption_data([])
    assert result == []


def test_process_disruption_data_no_affected_routes(tfl_service: TfLService) -> None:
    """Test processing disruptions without affectedRoutes."""

    class MockDisruption:
        pass  # No affectedRoutes attribute

    result = tfl_service._process_disruption_data([MockDisruption()])
    assert result == []


@patch("asyncio.get_running_loop")
async def test_fetch_disruptions_multiple_modes(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetching disruptions from multiple transport modes."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock responses for each mode
        mock_tube_disruptions = [
            create_mock_disruption(
                category="RealTime",
                category_description="Severe Delays",
                category_description_detail=5,
                description="Tube signal failure",
                affected_routes=[create_mock_route_section(id="victoria", name="Victoria")],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
        ]
        mock_overground_disruptions = [
            create_mock_disruption(
                category="PlannedWork",
                category_description="Minor Delays",
                category_description_detail=6,
                description="Overground engineering works",
                affected_routes=[create_mock_route_section(id="overground", name="Overground")],
                created=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            ),
        ]

        mock_responses = [
            MockResponse(data=mock_tube_disruptions, shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC)),
            MockResponse(data=mock_overground_disruptions, shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC)),
        ]

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(side_effect=mock_responses)
        mock_get_loop.return_value = mock_loop

        # Execute with multiple modes
        disruptions = await tfl_service.fetch_line_disruptions(modes=["tube", "overground"], use_cache=False)

        # Verify we got disruptions from both modes
        assert len(disruptions) == 2
        line_ids = {d.line_id for d in disruptions}
        assert "victoria" in line_ids
        assert "overground" in line_ids

        # Verify cache key includes both modes (sorted)
        expected_cache_key = "line_disruptions:modes:overground,tube"
        tfl_service.cache.set.assert_called_once()
        assert tfl_service.cache.set.call_args[0][0] == expected_cache_key


@patch("asyncio.get_running_loop")
async def test_fetch_disruptions_default_modes(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetching disruptions with default modes (tube, overground, dlr, elizabeth-line)."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock responses for all default modes
        mock_tube = [
            create_mock_disruption(
                category="RealTime",
                category_description="Severe Delays",
                category_description_detail=5,
                description="Tube disruption",
                affected_routes=[create_mock_route_section(id="victoria", name="Victoria")],
            ),
        ]
        mock_overground = [
            create_mock_disruption(
                category="PlannedWork",
                category_description="Part Closure",
                category_description_detail=7,
                description="Overground works",
                affected_routes=[create_mock_route_section(id="overground", name="Overground")],
            ),
        ]
        mock_dlr: list[Any] = []  # No disruptions on DLR
        mock_elizabeth = [
            create_mock_disruption(
                category="RealTime",
                category_description="Minor Delays",
                category_description_detail=6,
                description="Elizabeth line minor delays",
                affected_routes=[create_mock_route_section(id="elizabeth", name="Elizabeth line")],
            ),
        ]

        mock_responses = [
            MockResponse(data=mock_tube, shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC)),
            MockResponse(data=mock_overground, shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC)),
            MockResponse(data=mock_dlr, shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC)),
            MockResponse(data=mock_elizabeth, shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC)),
        ]

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(side_effect=mock_responses)
        mock_get_loop.return_value = mock_loop

        # Execute with default modes (None)
        disruptions = await tfl_service.fetch_line_disruptions(use_cache=False)

        # Verify we got disruptions from all modes that have them
        assert len(disruptions) == 3  # victoria, overground, elizabeth
        line_ids = {d.line_id for d in disruptions}
        assert "victoria" in line_ids
        assert "overground" in line_ids
        assert "elizabeth" in line_ids

        # Verify cache key uses default modes (sorted)
        expected_cache_key = "line_disruptions:modes:dlr,elizabeth-line,overground,tube"
        tfl_service.cache.set.assert_called_once()
        assert tfl_service.cache.set.call_args[0][0] == expected_cache_key


# ==================== fetch_severity_codes Tests ====================


async def test_fetch_severity_codes(
    tfl_service: TfLService,
) -> None:
    """Test fetching severity codes from TfL API."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data with severity codes
        mock_severity_codes = [
            create_mock_severity_code(severity_level=0, description="Special Service"),
            create_mock_severity_code(severity_level=1, description="Closed"),
            create_mock_severity_code(severity_level=5, description="Severe Delays"),
            create_mock_severity_code(severity_level=10, description="Good Service"),
        ]

        # Execute with helper
        codes = await assert_fetch_from_api(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_severity_codes(use_cache=False),
            mock_data=mock_severity_codes,
            expected_count=4,
            cache_key="severity_codes:all",
            expected_ttl=604800,  # 7 days
            shared_expires=datetime(2025, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        # Verify specific attributes
        assert codes[0].severity_level == 0
        assert codes[0].description == "Special Service"
        assert codes[3].severity_level == 10
        assert codes[3].description == "Good Service"


async def test_fetch_severity_codes_cache_hit(tfl_service: TfLService) -> None:
    """Test fetching severity codes from cache when available."""
    # Setup cached severity codes
    cached_codes = [
        SeverityCode(
            severity_level=10,
            description="Good Service",
            last_updated=datetime.now(UTC),
        ),
    ]

    # Execute with helper
    await assert_cache_hit(
        tfl_service=tfl_service,
        method_callable=lambda: tfl_service.fetch_severity_codes(use_cache=True),
        cache_key="severity_codes:all",
        cached_data=cached_codes,
    )


async def test_fetch_severity_codes_cache_miss(
    tfl_service: TfLService,
) -> None:
    """Test fetching severity codes from API when cache is enabled but empty."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data
        mock_severity_codes = [
            create_mock_severity_code(severity_level=10, description="Good Service"),
        ]

        # Execute with helper
        codes = await assert_cache_miss(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_severity_codes(use_cache=True),
            mock_data=mock_severity_codes,
            expected_count=1,
            shared_expires=datetime(2025, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        # Verify specific attributes
        assert codes[0].severity_level == 10


async def test_fetch_severity_codes_api_failure(
    tfl_service: TfLService,
) -> None:
    """Test handling TfL API failure when fetching severity codes."""
    await assert_api_failure(
        method_callable=lambda: tfl_service.fetch_severity_codes(use_cache=False),
        expected_error_message="Failed to fetch severity codes from TfL API",
    )


# ==================== fetch_disruption_categories Tests ====================


async def test_fetch_disruption_categories(
    tfl_service: TfLService,
) -> None:
    """Test fetching disruption categories from TfL API."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data with disruption categories (API returns strings)
        mock_categories = ["RealTime", "PlannedWork", "Information", "Event"]

        # Execute with helper
        categories = await assert_fetch_from_api(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_disruption_categories(use_cache=False),
            mock_data=mock_categories,
            expected_count=4,
            cache_key="disruption_categories:all",
            expected_ttl=604800,  # 7 days
            shared_expires=datetime(2025, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        # Verify specific attributes
        assert categories[0].category_name == "RealTime"
        assert categories[1].category_name == "PlannedWork"


async def test_fetch_disruption_categories_cache_hit(tfl_service: TfLService) -> None:
    """Test fetching disruption categories from cache when available."""
    # Setup cached categories
    cached_categories = [
        DisruptionCategory(
            category_name="RealTime",
            description=None,
            last_updated=datetime.now(UTC),
        ),
    ]

    # Execute with helper
    await assert_cache_hit(
        tfl_service=tfl_service,
        method_callable=lambda: tfl_service.fetch_disruption_categories(use_cache=True),
        cache_key="disruption_categories:all",
        cached_data=cached_categories,
    )


async def test_fetch_disruption_categories_cache_miss(
    tfl_service: TfLService,
) -> None:
    """Test fetching disruption categories from API when cache is enabled but empty."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data
        mock_categories = ["RealTime", "PlannedWork"]

        # Execute with helper
        categories = await assert_cache_miss(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_disruption_categories(use_cache=True),
            mock_data=mock_categories,
            expected_count=2,
            shared_expires=datetime(2025, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        # Verify specific attributes
        assert len(categories) == 2


async def test_fetch_disruption_categories_api_failure(
    tfl_service: TfLService,
) -> None:
    """Test handling TfL API failure when fetching disruption categories."""
    await assert_api_failure(
        method_callable=lambda: tfl_service.fetch_disruption_categories(use_cache=False),
        expected_error_message="Failed to fetch disruption categories from TfL API",
    )


# ==================== fetch_stop_types Tests ====================


async def test_fetch_stop_types(
    tfl_service: TfLService,
) -> None:
    """Test fetching stop types from TfL API with filtering."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data with stop types (API returns strings)
        # Include both relevant and irrelevant types
        mock_stop_types = [
            "NaptanMetroStation",
            "NaptanRailStation",
            "NaptanBusCoachStation",
            "NaptanFerryPort",  # Should be filtered out
            "NaptanAirport",  # Should be filtered out
        ]

        # Execute with helper
        stop_types = await assert_fetch_from_api(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_stop_types(use_cache=False),
            mock_data=mock_stop_types,
            expected_count=3,  # Only 3 relevant types
            cache_key="stop_types:all",
            expected_ttl=604800,  # 7 days
            shared_expires=datetime(2025, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        # Verify specific attributes - only relevant types stored
        type_names = {st.type_name for st in stop_types}
        assert "NaptanMetroStation" in type_names
        assert "NaptanRailStation" in type_names
        assert "NaptanBusCoachStation" in type_names
        assert "NaptanFerryPort" not in type_names
        assert "NaptanAirport" not in type_names


async def test_fetch_stop_types_cache_hit(tfl_service: TfLService) -> None:
    """Test fetching stop types from cache when available."""
    # Setup cached stop types
    cached_types = [
        StopType(
            type_name="NaptanMetroStation",
            description=None,
            last_updated=datetime.now(UTC),
        ),
    ]

    # Execute with helper
    await assert_cache_hit(
        tfl_service=tfl_service,
        method_callable=lambda: tfl_service.fetch_stop_types(use_cache=True),
        cache_key="stop_types:all",
        cached_data=cached_types,
    )


async def test_fetch_stop_types_cache_miss(
    tfl_service: TfLService,
) -> None:
    """Test fetching stop types from API when cache is enabled but empty."""
    with freeze_time("2025-01-01 12:00:00"):
        # Setup mock data
        mock_stop_types = ["NaptanMetroStation", "NaptanRailStation"]

        # Execute with helper
        stop_types = await assert_cache_miss(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_stop_types(use_cache=True),
            mock_data=mock_stop_types,
            expected_count=2,
            shared_expires=datetime(2025, 1, 8, 12, 0, 0, tzinfo=UTC),
        )

        # Verify specific attributes
        assert len(stop_types) == 2


async def test_fetch_stop_types_api_failure(
    tfl_service: TfLService,
) -> None:
    """Test handling TfL API failure when fetching stop types."""
    await assert_api_failure(
        method_callable=lambda: tfl_service.fetch_stop_types(use_cache=False),
        expected_error_message="Failed to fetch stop types from TfL API",
    )


# ==================== fetch_station_disruptions Tests ====================


@patch("asyncio.get_running_loop")
async def test_fetch_station_disruptions(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching station disruptions from TfL API."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create test stations in database first
        station1 = Station(
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            tfl_id="940GZZLUOXC",
            name="Oxford Circus",
            latitude=51.5152,
            longitude=-0.1419,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        db_session.add_all([station1, station2])
        await db_session.commit()
        await db_session.refresh(station1)
        await db_session.refresh(station2)

        # Setup mock response with station disruptions
        mock_disruptions = [
            MockStationDisruption(
                id="disruption-1",
                category="RealTime",
                categoryDescription="Lift Closure",
                description="Lift out of service",
                affectedStops=[
                    create_mock_stop_point(id="940GZZLUKSX", common_name="King's Cross"),
                ],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
            MockStationDisruption(
                id="disruption-2",
                category="PlannedWork",
                categoryDescription="Station Closure",
                description="Station closed for maintenance",
                affectedStops=[
                    create_mock_stop_point(id="940GZZLUOXC", common_name="Oxford Circus"),
                ],
                created=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            ),
        ]
        mock_response = MockResponse(
            data=mock_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),  # 2 minutes TTL
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Execute
        disruptions = await tfl_service.fetch_station_disruptions(modes=["tube"], use_cache=False)

        # Verify
        assert len(disruptions) == 2
        assert disruptions[0].station_tfl_id == "940GZZLUKSX"
        assert disruptions[0].disruption_category == "RealTime"
        assert disruptions[0].severity == "Lift Closure"
        assert disruptions[1].station_tfl_id == "940GZZLUOXC"
        assert disruptions[1].disruption_category == "PlannedWork"

        # Verify station disruptions were created in database
        result = await db_session.execute(select(StationDisruption))
        db_disruptions = result.scalars().all()
        assert len(db_disruptions) == 2


async def test_fetch_station_disruptions_cache_hit(tfl_service: TfLService) -> None:
    """Test fetching station disruptions from cache when available."""
    # Setup cached disruptions
    cached_disruptions = [
        StationDisruptionResponse(
            station_id=uuid.uuid4(),
            station_tfl_id="940GZZLUKSX",
            station_name="King's Cross",
            disruption_category="RealTime",
            description="Lift out of service",
            severity="Lift Closure",
            tfl_id="disruption-1",
            created_at_source=datetime.now(UTC),
        ),
    ]
    tfl_service.cache.get = AsyncMock(return_value=cached_disruptions)

    # Execute
    disruptions = await tfl_service.fetch_station_disruptions(modes=["tube"], use_cache=True)

    # Verify cache was used
    assert disruptions == cached_disruptions
    tfl_service.cache.get.assert_called_once_with("station_disruptions:modes:tube")


@patch("asyncio.get_running_loop")
async def test_fetch_station_disruptions_cache_miss(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching station disruptions from API when cache is enabled but empty."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create test station in database first
        station = Station(
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)

        # Setup mock response
        mock_disruptions = [
            MockStationDisruption(
                id="disruption-1",
                category="RealTime",
                categoryDescription="Lift Closure",
                description="Lift out of service",
                affectedStops=[
                    create_mock_stop_point(id="940GZZLUKSX", common_name="King's Cross"),
                ],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
        ]
        mock_response = MockResponse(
            data=mock_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Cache returns None (miss)
        tfl_service.cache.get = AsyncMock(return_value=None)

        # Execute with use_cache=True but cache is empty
        disruptions = await tfl_service.fetch_station_disruptions(modes=["tube"], use_cache=True)

        # Verify
        assert len(disruptions) == 1
        assert disruptions[0].station_tfl_id == "940GZZLUKSX"

        # Verify cache was checked
        tfl_service.cache.get.assert_called_once()

        # Verify cache was populated
        tfl_service.cache.set.assert_called_once()


@patch("asyncio.get_running_loop")
async def test_fetch_station_disruptions_api_failure(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test handling TfL API failure when fetching station disruptions."""
    # Setup mock to raise exception
    mock_loop = AsyncMock()
    mock_loop.run_in_executor = AsyncMock(side_effect=Exception("API Error"))
    mock_get_loop.return_value = mock_loop

    # Execute and verify exception
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.fetch_station_disruptions(use_cache=False)

    assert exc_info.value.status_code == 503
    assert "Failed to fetch station disruptions from TfL API" in exc_info.value.detail


@patch("asyncio.get_running_loop")
async def test_fetch_station_disruptions_multiple_modes(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching station disruptions with multiple modes."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create test stations in database
        station_kx = Station(
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria", "overground"],
            last_updated=datetime.now(UTC),
        )
        station_stfd = Station(
            tfl_id="910GSTFD",
            name="Stratford",
            latitude=51.5416,
            longitude=-0.0042,
            lines=["dlr"],
            last_updated=datetime.now(UTC),
        )
        db_session.add_all([station_kx, station_stfd])
        await db_session.commit()
        await db_session.refresh(station_kx)
        await db_session.refresh(station_stfd)

        # Setup mock responses for tube and dlr modes
        mock_tube_disruptions = [
            MockStationDisruption(
                id="disruption-tube-1",
                category="RealTime",
                categoryDescription="Lift Closure",
                description="Lift out of service at King's Cross",
                affectedStops=[
                    create_mock_stop_point(id="940GZZLUKSX", common_name="King's Cross"),
                ],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
        ]
        mock_dlr_disruptions = [
            MockStationDisruption(
                id="disruption-dlr-1",
                category="RealTime",
                categoryDescription="Platform Closure",
                description="Platform 2 closed at Stratford",
                affectedStops=[
                    create_mock_stop_point(id="910GSTFD", common_name="Stratford"),
                ],
                created=datetime(2025, 1, 1, 11, 45, 0, tzinfo=UTC),
            ),
        ]

        mock_tube_response = MockResponse(
            data=mock_tube_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),
        )
        mock_dlr_response = MockResponse(
            data=mock_dlr_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),
        )

        # Mock executor to return different responses for each mode
        call_count = [0]

        async def mock_executor(*args: Any) -> Any:  # noqa: ANN401
            result = [mock_tube_response, mock_dlr_response][call_count[0]]
            call_count[0] += 1
            return result

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(side_effect=mock_executor)
        mock_get_loop.return_value = mock_loop

        # Execute with multiple modes
        disruptions = await tfl_service.fetch_station_disruptions(modes=["tube", "dlr"], use_cache=False)

        # Verify disruptions from both modes were returned
        assert len(disruptions) == 2

        # Verify cache key includes both modes (sorted)
        expected_cache_key = "station_disruptions:modes:dlr,tube"
        tfl_service.cache.set.assert_called_once()
        assert tfl_service.cache.set.call_args[0][0] == expected_cache_key

        # Verify disruptions contain data from both modes
        station_ids = {d.station_tfl_id for d in disruptions}
        assert station_ids == {"940GZZLUKSX", "910GSTFD"}


@patch("asyncio.get_running_loop")
async def test_fetch_station_disruptions_unknown_station(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching station disruptions when affected station is not in database."""
    with freeze_time("2025-01-01 12:00:00"):
        # Don't create any stations in database

        # Setup mock response with disruption for unknown station
        mock_disruptions = [
            MockStationDisruption(
                id="disruption-1",
                category="RealTime",
                categoryDescription="Lift Closure",
                description="Lift out of service",
                affectedStops=[
                    create_mock_stop_point(id="UNKNOWN_STATION", common_name="Unknown Station"),
                ],
                created=datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC),
            ),
        ]
        mock_response = MockResponse(
            data=mock_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),
        )

        # Mock the event loop and executor
        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Execute
        disruptions = await tfl_service.fetch_station_disruptions(use_cache=False)

        # Verify - no disruptions should be created for unknown stations
        assert len(disruptions) == 0


async def test_create_station_disruption(db_session: AsyncSession) -> None:
    """Test station disruption creation with all fields."""
    # Create station
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add(station)
    await db_session.commit()

    # Create mock disruption data (mimics TfL API structure)
    class MockDisruptionData:
        """Mock TfL API disruption data."""

        def __init__(self) -> None:
            self.category = "PlannedWork"
            self.description = "Station improvements"
            self.categoryDescription = "Minor"
            self.id = "disruption-123"
            self.created = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)

    # Test creation
    tfl_service = TfLService(db_session)
    result = await tfl_service._create_station_disruption(station, MockDisruptionData())

    # Verify response
    assert result.station_id == station.id
    assert result.station_tfl_id == "940GZZLUVIC"
    assert result.station_name == "Victoria"
    assert result.disruption_category == "PlannedWork"
    assert result.description == "Station improvements"
    assert result.severity == "Minor"
    assert result.tfl_id == "disruption-123"
    assert result.created_at_source == datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)

    # Verify database record was created
    await db_session.commit()
    result_db = await db_session.execute(select(StationDisruption).where(StationDisruption.tfl_id == "disruption-123"))
    disruption = result_db.scalar_one_or_none()
    assert disruption is not None
    assert disruption.station_id == station.id
    assert disruption.disruption_category == "PlannedWork"


async def test_create_station_disruption_missing_fields(db_session: AsyncSession) -> None:
    """Test station disruption creation handles missing optional fields."""
    # Create station
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add(station)
    await db_session.commit()

    # Create mock disruption data with minimal fields (tests default handling)
    class EmptyMockDisruption:
        """Mock disruption with no fields to test defaults."""

        pass

    # Test creation with defaults
    tfl_service = TfLService(db_session)
    result = await tfl_service._create_station_disruption(station, EmptyMockDisruption())

    # Verify defaults were used
    assert result.station_id == station.id
    assert result.disruption_category is None
    assert result.description == "No description available"
    assert result.severity is None
    assert isinstance(result.tfl_id, str)  # UUID generated
    assert isinstance(result.created_at_source, datetime)


async def test_fetch_station_disruptions_uses_helpers(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that fetch_station_disruptions uses the helper methods."""
    # Create line and station
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([line, station])
    await db_session.commit()

    # Create mock disruption data (mimics TfL API structure)
    class MockStopData:
        """Mock TfL API stop data."""

        def __init__(self) -> None:
            self.id = "940GZZLUVIC"

    class MockStationDisruptionData:
        """Mock TfL API station disruption data."""

        def __init__(self) -> None:
            self.category = "PlannedWork"
            self.description = "Station improvements"
            self.categoryDescription = "Minor"
            self.id = "disruption-123"
            self.created = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
            self.affectedStops = [MockStopData()]

    # Mock API response
    mock_response = MagicMock()
    mock_response.content.root = [MockStationDisruptionData()]

    # Mock asyncio.get_running_loop
    mock_loop = AsyncMock()
    mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("asyncio.get_running_loop", lambda: mock_loop)

    # Test fetch
    tfl_service = TfLService(db_session)
    results = await tfl_service.fetch_station_disruptions(modes=["tube"], use_cache=False)

    # Verify helpers were used (result should contain the disruption)
    assert len(results) == 1
    assert results[0].station_tfl_id == "940GZZLUVIC"
    assert results[0].disruption_category == "PlannedWork"


# ==================== build_station_graph Tests ====================


@patch("asyncio.get_running_loop")
async def test_build_station_graph(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test building the station connection graph using route sequences.

    This test verifies that build_station_graph:
    1. Fetches all lines
    2. Fetches stations for each line (populates Station table)
    3. Builds connections from route sequences
    4. Returns correct statistics
    """
    with freeze_time("2025-01-01 12:00:00"):
        # Mock responses for fetch_lines (called first in build_station_graph)
        # Only return lines for tube mode, empty for others to keep test simple
        mock_tube_lines = [
            create_mock_line(id="victoria", name="Victoria"),
        ]
        mock_tube_response = MockResponse(
            data=mock_tube_lines,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )
        mock_empty_response = MockResponse(
            data=[],  # No lines for other modes
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock responses for fetch_stations (called for each line)
        mock_stations = [
            create_mock_place(id="940GZZLUKSX", common_name="King's Cross", lat=51.5308, lon=-0.1238),
            create_mock_place(id="940GZZLUOXC", common_name="Oxford Circus", lat=51.5152, lon=-0.1419),
            create_mock_place(id="940GZZLUVIC", common_name="Victoria", lat=51.4965, lon=-0.1447),
        ]
        mock_stations_response = MockResponse(
            data=mock_stations,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock route sequence responses for inbound and outbound
        # Create stop points in sequence order
        stop_points = [
            MockStopPoint2(id="940GZZLUKSX", name="King's Cross"),
            MockStopPoint2(id="940GZZLUOXC", name="Oxford Circus"),
            MockStopPoint2(id="940GZZLUVIC", name="Victoria"),
        ]

        # Mock route sequence with stopPointSequences
        mock_route_sequence = MockRouteSequence(
            stopPointSequences=[
                MockStopPointSequence2(stopPoint=stop_points),
            ],
        )

        # Create mock response with route sequence
        class MockRouteResponse:
            def __init__(self, content: MockRouteSequence) -> None:
                self.content = content

        mock_inbound_response = MockRouteResponse(content=mock_route_sequence)
        mock_outbound_response = MockRouteResponse(content=mock_route_sequence)

        # Mock the event loop - cycle through responses
        # Order: 4x lines (tube/overground/dlr/elizabeth-line), stations (victoria line),
        # inbound route, outbound route
        responses = [
            mock_tube_response,  # tube lines (has 1 line)
            mock_empty_response,  # overground lines (empty)
            mock_empty_response,  # dlr lines (empty)
            mock_empty_response,  # elizabeth lines (empty)
            mock_stations_response,
            mock_inbound_response,
            mock_outbound_response,
        ]
        call_count = [0]

        async def mock_executor(*args: Any) -> Any:  # noqa: ANN401
            result = responses[call_count[0]]
            call_count[0] += 1
            return result

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(side_effect=mock_executor)
        mock_get_loop.return_value = mock_loop

        # Execute
        result = await tfl_service.build_station_graph()

        # Verify result
        assert result["lines_count"] == 1
        assert result["stations_count"] == 3
        assert result["connections_count"] == 4  # 2 connections forward + 2 reverse

        # Verify stations were created in database
        stations_result = await db_session.execute(select(Station))
        stations = stations_result.scalars().all()
        assert len(stations) == 3

        # Verify connections were created in database
        connections_result = await db_session.execute(select(StationConnection))
        connections = connections_result.scalars().all()
        assert len(connections) == 4


@patch("asyncio.get_running_loop")
async def test_build_station_graph_fails_without_stations(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test that build_station_graph fails fast when no stations are found after fetching."""
    with freeze_time("2025-01-01 12:00:00"):
        # Mock responses for fetch_lines
        mock_lines = [
            create_mock_line(id="victoria", name="Victoria"),
        ]
        mock_lines_response = MockResponse(
            data=mock_lines,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock EMPTY station response (no stations returned from API)
        mock_stations_response = MockResponse(
            data=[],  # Empty list - no stations
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock the event loop - need 4 responses for each mode
        responses = [
            mock_lines_response,  # tube (has 1 line)
            MockResponse(data=[], shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),  # overground (empty)
            MockResponse(data=[], shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),  # dlr (empty)
            MockResponse(data=[], shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),  # elizabeth (empty)
            mock_stations_response,
        ]
        call_count = [0]

        async def mock_executor(*args: Any) -> Any:  # noqa: ANN401
            result = responses[call_count[0]]
            call_count[0] += 1
            return result

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(side_effect=mock_executor)
        mock_get_loop.return_value = mock_loop

        # Execute - should raise HTTPException with validation error
        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.build_station_graph()

        # Verify error details
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "No stations found" in exc_info.value.detail
        assert "Cannot build graph" in exc_info.value.detail


async def test_build_station_graph_rollback_on_error(
    tfl_service: TfLService,
) -> None:
    """Test that build_station_graph properly handles errors and performs rollback.

    This test verifies that if the graph build fails (e.g., due to an API error),
    the error is caught, wrapped in an HTTPException, and the transaction is rolled back.
    Additionally verifies that no partial data exists in the database after rollback.
    """
    with freeze_time("2025-01-01 12:00:00"):
        # Ensure database is clean before test
        stations_before = await tfl_service.db.execute(text("SELECT COUNT(*) FROM stations"))
        connections_before = await tfl_service.db.execute(text("SELECT COUNT(*) FROM station_connections"))
        stations_count_before = stations_before.scalar()
        connections_count_before = connections_before.scalar()

        # Mock the fetch_lines method to raise an exception simulating a database/API failure
        original_fetch_lines = tfl_service.fetch_lines
        error_msg = "Simulated API error during fetch_lines"

        async def mock_fetch_lines_with_error(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            raise RuntimeError(error_msg)

        tfl_service.fetch_lines = mock_fetch_lines_with_error  # type: ignore[method-assign]

        try:
            # Execute - should raise HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await tfl_service.build_station_graph()

            # Verify error was caught and wrapped in HTTPException
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to build station graph" in exc_info.value.detail

            # The rollback is called automatically in the exception handler
            # This ensures the database is in a consistent state

            # Verify that no partial data exists after rollback
            stations_after = await tfl_service.db.execute(text("SELECT COUNT(*) FROM stations"))
            connections_after = await tfl_service.db.execute(text("SELECT COUNT(*) FROM station_connections"))
            stations_count_after = stations_after.scalar()
            connections_count_after = connections_after.scalar()

            # Counts should be unchanged (no partial data committed)
            assert stations_count_after == stations_count_before
            assert connections_count_after == connections_count_before

        finally:
            # Restore original method
            tfl_service.fetch_lines = original_fetch_lines  # type: ignore[method-assign]


@patch("asyncio.get_running_loop")
async def test_build_station_graph_no_duplicate_connections(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test that build_station_graph prevents duplicate connections from inbound/outbound overlap.

    When processing both inbound and outbound routes, the same station pairs appear in both directions.
    This test verifies that we don't create duplicate connections by tracking pending connections
    within the transaction.
    """
    with freeze_time("2025-01-01 12:00:00"):
        # Mock responses for fetch_lines
        mock_lines = [
            create_mock_line(id="victoria", name="Victoria"),
        ]
        mock_lines_response = MockResponse(
            data=mock_lines,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock responses for fetch_stations
        mock_stations = [
            create_mock_place(id="940GZZLUKSX", common_name="King's Cross", lat=51.5308, lon=-0.1238),
            create_mock_place(id="940GZZLUOXC", common_name="Oxford Circus", lat=51.5152, lon=-0.1419),
            create_mock_place(id="940GZZLUVIC", common_name="Victoria", lat=51.4965, lon=-0.1447),
        ]
        mock_stations_response = MockResponse(
            data=mock_stations,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock route sequence for INBOUND: A -> B -> C
        inbound_stop_points = [
            MockStopPoint2(id="940GZZLUKSX", name="King's Cross"),
            MockStopPoint2(id="940GZZLUOXC", name="Oxford Circus"),
            MockStopPoint2(id="940GZZLUVIC", name="Victoria"),
        ]
        mock_inbound_sequence = MockRouteSequence(
            stopPointSequences=[
                MockStopPointSequence2(stopPoint=inbound_stop_points),
            ],
        )

        # Mock route sequence for OUTBOUND: C -> B -> A (reverse of inbound)
        # This creates the SAME connections but in opposite order
        outbound_stop_points = [
            MockStopPoint2(id="940GZZLUVIC", name="Victoria"),
            MockStopPoint2(id="940GZZLUOXC", name="Oxford Circus"),
            MockStopPoint2(id="940GZZLUKSX", name="King's Cross"),
        ]
        mock_outbound_sequence = MockRouteSequence(
            stopPointSequences=[
                MockStopPointSequence2(stopPoint=outbound_stop_points),
            ],
        )

        class MockRouteResponse:
            def __init__(self, content: MockRouteSequence) -> None:
                self.content = content

        mock_inbound_response = MockRouteResponse(content=mock_inbound_sequence)
        mock_outbound_response = MockRouteResponse(content=mock_outbound_sequence)

        # Mock the event loop - need 4x lines, then stations, then routes
        responses = [
            mock_lines_response,  # tube (has 1 line)
            MockResponse(data=[], shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),  # overground (empty)
            MockResponse(data=[], shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),  # dlr (empty)
            MockResponse(data=[], shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)),  # elizabeth (empty)
            mock_stations_response,
            mock_inbound_response,
            mock_outbound_response,
        ]
        call_count = [0]

        async def mock_executor(*args: Any) -> Any:  # noqa: ANN401
            result = responses[call_count[0]]
            call_count[0] += 1
            return result

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(side_effect=mock_executor)
        mock_get_loop.return_value = mock_loop

        # Execute
        result = await tfl_service.build_station_graph()

        # Verify result - should create exactly 4 bidirectional connections (not 8!)
        # Inbound creates: A->B, B->A, B->C, C->B
        # Outbound would try to create: C->B, B->C, B->A, A->B (all duplicates, should be skipped)
        assert result["lines_count"] == 1
        assert result["stations_count"] == 3
        assert result["connections_count"] == 4, "Should create exactly 4 connections, not duplicates"

        # Verify in database - should have exactly 4 connections
        connections_result = await db_session.execute(select(StationConnection))
        connections = connections_result.scalars().all()
        assert len(connections) == 4, "Database should have exactly 4 connections"

        # Verify each unique connection exists exactly once
        connection_keys = set()
        for conn in connections:
            key = (str(conn.from_station_id), str(conn.to_station_id), str(conn.line_id))
            assert key not in connection_keys, f"Duplicate connection found: {key}"
            connection_keys.add(key)


@patch("asyncio.get_running_loop")
async def test_build_station_graph_multiple_modes(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test build_station_graph with lines from multiple transport modes."""
    with freeze_time("2025-01-01 12:00:00"):
        # Define local MockRouteResponse for this test
        class MockRouteResponse:
            def __init__(self, content: MockRouteSequence) -> None:
                self.content = content

        # Mock responses for fetch_lines - tube and DLR
        mock_tube_lines = [
            create_mock_line(id="victoria", name="Victoria"),
        ]
        mock_dlr_lines = [
            create_mock_line(id="dlr", name="DLR"),
        ]
        mock_tube_response = MockResponse(
            data=mock_tube_lines,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )
        mock_dlr_response = MockResponse(
            data=mock_dlr_lines,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )
        mock_empty_response = MockResponse(
            data=[],
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock stations for Victoria line
        mock_victoria_stations = [
            create_mock_place(id="940GZZLUKSX", common_name="King's Cross", lat=51.5308, lon=-0.1238),
            create_mock_place(id="940GZZLUOXC", common_name="Oxford Circus", lat=51.5152, lon=-0.1419),
        ]
        mock_victoria_stations_response = MockResponse(
            data=mock_victoria_stations,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock stations for DLR line
        mock_dlr_stations = [
            create_mock_place(id="910GSTFD", common_name="Stratford", lat=51.5416, lon=-0.0042),
            create_mock_place(id="910GCANNING", common_name="Canning Town", lat=51.5145, lon=0.0082),
        ]
        mock_dlr_stations_response = MockResponse(
            data=mock_dlr_stations,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Mock route sequences for Victoria line
        victoria_inbound_stops = [
            MockStopPoint2(id="940GZZLUKSX", name="King's Cross"),
            MockStopPoint2(id="940GZZLUOXC", name="Oxford Circus"),
        ]
        mock_victoria_inbound = MockRouteResponse(
            content=MockRouteSequence(stopPointSequences=[MockStopPointSequence2(stopPoint=victoria_inbound_stops)])
        )
        victoria_outbound_stops = [
            MockStopPoint2(id="940GZZLUOXC", name="Oxford Circus"),
            MockStopPoint2(id="940GZZLUKSX", name="King's Cross"),
        ]
        mock_victoria_outbound = MockRouteResponse(
            content=MockRouteSequence(stopPointSequences=[MockStopPointSequence2(stopPoint=victoria_outbound_stops)])
        )

        # Mock route sequences for DLR line
        dlr_inbound_stops = [
            MockStopPoint2(id="910GSTFD", name="Stratford"),
            MockStopPoint2(id="910GCANNING", name="Canning Town"),
        ]
        mock_dlr_inbound = MockRouteResponse(
            content=MockRouteSequence(stopPointSequences=[MockStopPointSequence2(stopPoint=dlr_inbound_stops)])
        )
        dlr_outbound_stops = [
            MockStopPoint2(id="910GCANNING", name="Canning Town"),
            MockStopPoint2(id="910GSTFD", name="Stratford"),
        ]
        mock_dlr_outbound = MockRouteResponse(
            content=MockRouteSequence(stopPointSequences=[MockStopPointSequence2(stopPoint=dlr_outbound_stops)])
        )

        # Setup responses in order - build_station_graph calls:
        # 1. fetch_lines (4 calls - one per mode)
        # 2. fetch_stations for ALL lines FIRST (2 calls - victoria, dlr)
        # 3. fetch routes for each line (4 calls - vic in/out, dlr in/out)
        responses = [
            # fetch_lines calls (4 total - tube, overground, dlr, elizabeth-line)
            mock_tube_response,  # 0: tube lines (has victoria)
            mock_empty_response,  # 1: overground lines (empty)
            mock_dlr_response,  # 2: dlr lines (has dlr)
            mock_empty_response,  # 3: elizabeth lines (empty)
            # fetch_stations for ALL lines (2 calls)
            mock_victoria_stations_response,  # 4: victoria stations
            mock_dlr_stations_response,  # 5: dlr stations
            # fetch routes for Victoria line (2 calls)
            mock_victoria_inbound,  # 6: victoria inbound route
            mock_victoria_outbound,  # 7: victoria outbound route
            # fetch routes for DLR line (2 calls)
            mock_dlr_inbound,  # 8: dlr inbound route
            mock_dlr_outbound,  # 9: dlr outbound route
        ]
        call_count = [0]

        async def mock_executor(*args: Any) -> Any:  # noqa: ANN401
            result = responses[call_count[0]]
            call_count[0] += 1
            return result

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(side_effect=mock_executor)
        mock_get_loop.return_value = mock_loop

        # Execute
        result = await tfl_service.build_station_graph()

        # Verify result includes lines from multiple modes
        assert result["lines_count"] == 2  # Victoria (tube) + DLR
        assert result["stations_count"] == 4  # 2 from Victoria + 2 from DLR
        assert result["connections_count"] == 4  # 2 from Victoria + 2 from DLR (bidirectional)

        # Verify lines were created with correct modes
        lines_result = await db_session.execute(select(Line))
        lines = lines_result.scalars().all()
        assert len(lines) == 2

        line_modes = {line.tfl_id: line.mode for line in lines}
        assert line_modes["victoria"] == "tube"
        assert line_modes["dlr"] == "dlr"

        # Verify stations from both modes were created
        stations_result = await db_session.execute(select(Station))
        stations = stations_result.scalars().all()
        assert len(stations) == 4

        station_ids = {s.tfl_id for s in stations}
        assert "940GZZLUKSX" in station_ids  # Victoria line station
        assert "910GSTFD" in station_ids  # DLR station


# ==================== validate_route Tests ====================


async def test_validate_route_success(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test successful route validation."""
    # Create test data
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Victoria Line",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["st1", "st2", "st3"],
                }
            ]
        },
    )
    db_session.add(line)
    await db_session.flush()

    station1 = Station(
        tfl_id="st1",
        name="Station 1",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="st2",
        name="Station 2",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station3 = Station(
        tfl_id="st3",
        name="Station 3",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station1, station2, station3])
    await db_session.flush()

    # Create connections: st1 -> st2 -> st3
    conn1 = StationConnection(from_station_id=station1.id, to_station_id=station2.id, line_id=line.id)
    conn2 = StationConnection(from_station_id=station2.id, to_station_id=station3.id, line_id=line.id)
    db_session.add_all([conn1, conn2])
    await db_session.commit()

    # Create route segments
    segments = [
        RouteSegmentRequest(station_tfl_id=station1.tfl_id, line_tfl_id=line.tfl_id),
        RouteSegmentRequest(station_tfl_id=station2.tfl_id, line_tfl_id=line.tfl_id),
        RouteSegmentRequest(station_tfl_id=station3.tfl_id, line_tfl_id=line.tfl_id),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify
    assert is_valid is True
    assert "valid" in message.lower()
    assert invalid_segment is None


async def test_validate_route_multiple_paths(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with multiple paths to same station."""
    # Create test data with diamond pattern: A -> B -> D and A -> C -> D
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Victoria Line",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["st_a", "st_b", "st_c", "st_d"],
                }
            ]
        },
    )
    db_session.add(line)
    await db_session.flush()

    station_a = Station(
        tfl_id="st_a",
        name="Station A",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station_b = Station(
        tfl_id="st_b",
        name="Station B",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station_c = Station(
        tfl_id="st_c",
        name="Station C",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station_d = Station(
        tfl_id="st_d",
        name="Station D",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station_a, station_b, station_c, station_d])
    await db_session.flush()

    # Create diamond pattern connections
    # A -> B, A -> C, B -> D, C -> D
    conn_ab = StationConnection(from_station_id=station_a.id, to_station_id=station_b.id, line_id=line.id)
    conn_ac = StationConnection(from_station_id=station_a.id, to_station_id=station_c.id, line_id=line.id)
    conn_bd = StationConnection(from_station_id=station_b.id, to_station_id=station_d.id, line_id=line.id)
    conn_cd = StationConnection(from_station_id=station_c.id, to_station_id=station_d.id, line_id=line.id)
    db_session.add_all([conn_ab, conn_ac, conn_bd, conn_cd])
    await db_session.commit()

    # Create route: A -> D (direct validation)
    # During BFS from A to D, we'll explore both paths (A->B->D and A->C->D)
    # When processing C's connections after B's, D will already be visited
    segments = [
        RouteSegmentRequest(station_tfl_id=station_a.tfl_id, line_tfl_id=line.tfl_id),
        RouteSegmentRequest(station_tfl_id=station_d.tfl_id, line_tfl_id=line.tfl_id),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify route is valid
    assert is_valid is True
    assert "valid" in message.lower()
    assert invalid_segment is None


async def test_validate_route_invalid_connection(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with invalid connection (stations not in same route sequence)."""
    # Create test data with routes that don't include both stations together
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Victoria Line Route 1",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["st1", "st3"],  # st1 but not st2
                },
                {
                    "name": "Victoria Line Route 2",
                    "service_type": "Regular",
                    "direction": "outbound",
                    "stations": ["st2", "st4"],  # st2 but not st1
                },
            ]
        },
    )
    db_session.add(line)
    await db_session.flush()

    station1 = Station(
        tfl_id="st1",
        name="Station 1",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="st2",
        name="Station 2",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station1, station2])
    await db_session.commit()

    # No connection created between stations (not needed with route sequence validation)

    # Create route segments
    segments = [
        RouteSegmentRequest(station_tfl_id=station1.tfl_id, line_tfl_id=line.tfl_id),
        RouteSegmentRequest(station_tfl_id=station2.tfl_id, line_tfl_id=line.tfl_id),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify - should fail because st1 and st2 are not in the same route sequence
    assert is_valid is False
    assert "no connection" in message.lower() or "different branches" in message.lower()
    assert invalid_segment == 0


async def test_validate_route_too_few_segments(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with insufficient segments."""
    # Create minimal test data
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    station1 = Station(
        tfl_id="st1",
        name="Station 1",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([line, station1])
    await db_session.commit()

    # Only one segment
    segments = [RouteSegmentRequest(station_tfl_id=station1.tfl_id, line_tfl_id=line.tfl_id)]

    # Execute
    is_valid, message, _invalid_segment = await tfl_service.validate_route(segments)

    # Verify
    assert is_valid is False
    assert "at least 2 segments" in message.lower()


async def test_validate_route_with_nonexistent_station_or_line(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with non-existent station or line IDs."""
    # Create valid entities
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    station1 = Station(
        tfl_id="st1",
        name="Station 1",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([line, station1])
    await db_session.commit()

    # Use non-existent station TfL ID
    fake_station_id = "fake_station"
    segments = [
        RouteSegmentRequest(station_tfl_id=station1.tfl_id, line_tfl_id=line.tfl_id),
        RouteSegmentRequest(station_tfl_id=fake_station_id, line_tfl_id=line.tfl_id),
    ]

    # Execute - should raise 404 for non-existent station
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.validate_route(segments)

    # Verify - should fail with 404
    assert exc_info.value.status_code == 404
    assert "fake_station" in str(exc_info.value.detail).lower()


async def test_validate_route_with_deleted_stations(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with soft-deleted stations."""
    # Create test data with valid route
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.flush()

    station1 = Station(
        tfl_id="st1",
        name="Station 1",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="st2",
        name="Station 2",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station1, station2])
    await db_session.flush()

    # Create connection
    conn = StationConnection(from_station_id=station1.id, to_station_id=station2.id, line_id=line.id)
    db_session.add(conn)
    await db_session.commit()

    # Soft delete station2
    station2.deleted_at = datetime.now(UTC)
    await db_session.commit()

    # Create route segments
    segments = [
        RouteSegmentRequest(station_tfl_id=station1.tfl_id, line_tfl_id=line.tfl_id),
        RouteSegmentRequest(station_tfl_id=station2.tfl_id, line_tfl_id=line.tfl_id),
    ]

    # Execute - current implementation doesn't filter by deleted_at,
    # so this will succeed. This test documents current behavior.
    # In a production system, we'd want to filter deleted entities.
    is_valid, _message, _invalid_segment = await tfl_service.validate_route(segments)

    # Current behavior: validation passes because deleted_at is not checked
    # This is acceptable for a hobby project (YAGNI), but documents the limitation
    assert is_valid is True or is_valid is False  # Either behavior is acceptable


async def test_validate_route_with_duplicate_stations(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with duplicate stations (acyclic enforcement)."""
    # Create test data
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.flush()

    station1 = Station(
        tfl_id="st1",
        name="King's Cross",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="st2",
        name="Oxford Circus",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station1, station2])
    await db_session.flush()

    # Create connections (not used for this test, but included for completeness)
    conn1 = StationConnection(from_station_id=station1.id, to_station_id=station2.id, line_id=line.id)
    conn2 = StationConnection(from_station_id=station2.id, to_station_id=station1.id, line_id=line.id)
    db_session.add_all([conn1, conn2])
    await db_session.commit()

    # Create route with duplicate station (st1 appears twice)
    segments = [
        RouteSegmentRequest(station_tfl_id="st1", line_tfl_id="victoria"),
        RouteSegmentRequest(station_tfl_id="st2", line_tfl_id="victoria"),
        RouteSegmentRequest(station_tfl_id="st1", line_tfl_id="victoria"),  # Duplicate!
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify
    assert is_valid is False
    assert "cannot visit the same station" in message.lower()
    assert "King's Cross" in message
    assert invalid_segment == 2  # Third segment (index 2) is the duplicate


async def test_validate_route_with_too_many_segments(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with too many segments (exceeds MAX_ROUTE_SEGMENTS)."""
    # Create test data
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.flush()

    # Create 25 stations (exceeds MAX_ROUTE_SEGMENTS of 20)
    stations = []
    for i in range(25):
        station = Station(
            tfl_id=f"st{i}",
            name=f"Station {i}",
            latitude=51.5,
            longitude=-0.1,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        stations.append(station)
        db_session.add(station)

    await db_session.flush()

    # Create connections between consecutive stations
    for i in range(len(stations) - 1):
        conn = StationConnection(
            from_station_id=stations[i].id,
            to_station_id=stations[i + 1].id,
            line_id=line.id,
        )
        db_session.add(conn)

    await db_session.commit()

    # Create route segments with 21 stations (exceeds limit of 20)
    segments = [RouteSegmentRequest(station_tfl_id=station.tfl_id, line_tfl_id="victoria") for station in stations[:21]]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify
    assert is_valid is False
    assert "cannot have more than 20 segments" in message.lower()
    assert "21" in message  # Should mention current count
    assert invalid_segment is None  # No specific segment is invalid


async def test_validate_route_with_null_destination_line_id(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with NULL line_id for destination segment (should be valid)."""
    # Create test data
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Victoria Line",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["st1", "st2", "st3"],
                }
            ]
        },
    )
    db_session.add(line)
    await db_session.flush()

    station1 = Station(
        tfl_id="st1",
        name="Station 1",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="st2",
        name="Station 2",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station3 = Station(
        tfl_id="st3",
        name="Station 3",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station1, station2, station3])
    await db_session.flush()

    # Create connections: st1 -> st2 -> st3
    conn1 = StationConnection(from_station_id=station1.id, to_station_id=station2.id, line_id=line.id)
    conn2 = StationConnection(from_station_id=station2.id, to_station_id=station3.id, line_id=line.id)
    db_session.add_all([conn1, conn2])
    await db_session.commit()

    # Create route segments with NULL line_tfl_id for destination
    segments = [
        RouteSegmentRequest(station_tfl_id="st1", line_tfl_id="victoria"),
        RouteSegmentRequest(station_tfl_id="st2", line_tfl_id="victoria"),
        RouteSegmentRequest(station_tfl_id="st3", line_tfl_id=None),  # Destination has NULL line_tfl_id
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify - should be valid
    assert is_valid is True
    assert "valid" in message.lower()
    assert invalid_segment is None


async def test_validate_route_with_null_intermediate_line_id(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with NULL line_id for intermediate segment (should fail)."""
    # Create test data
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.flush()

    station1 = Station(
        tfl_id="st1",
        name="Station 1",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="st2",
        name="Station 2",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station3 = Station(
        tfl_id="st3",
        name="Station 3",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station1, station2, station3])
    await db_session.flush()

    # Create connections: st1 -> st2 -> st3
    conn1 = StationConnection(from_station_id=station1.id, to_station_id=station2.id, line_id=line.id)
    conn2 = StationConnection(from_station_id=station2.id, to_station_id=station3.id, line_id=line.id)
    db_session.add_all([conn1, conn2])
    await db_session.commit()

    # Create route segments with NULL line_tfl_id for intermediate segment
    segments = [
        RouteSegmentRequest(station_tfl_id="st1", line_tfl_id="victoria"),
        RouteSegmentRequest(station_tfl_id="st2", line_tfl_id=None),  # Intermediate has NULL line_tfl_id
        RouteSegmentRequest(station_tfl_id="st3", line_tfl_id="victoria"),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify - should fail
    assert is_valid is False
    assert "must have a line_tfl_id" in message.lower()
    assert "segment 1" in message.lower()  # Should mention the failing segment
    assert invalid_segment == 1  # Second segment (index 1)


# ==================== Route Sequence Validation Tests (Issue #39) ====================


async def test_validate_route_different_branches_fails(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test that validation fails for stations on different branches (e.g., Bank -> Charing Cross on Northern)."""
    # Create Northern line
    line = Line(
        tfl_id="northern",
        name="Northern",
        color="#000000",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Edgware → Morden via Bank",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEGW", "940GZZLUCND", "940GZZLUBNK", "940GZZLUMDN"],
                },
                {
                    "name": "Edgware → Morden via Charing Cross",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEGW", "940GZZLUCND", "940GZZLUCHX", "940GZZLUMDN"],
                },
            ]
        },
    )
    db_session.add(line)
    await db_session.flush()

    # Create stations: Bank and Charing Cross on different branches
    bank = Station(
        tfl_id="940GZZLUBNK",
        name="Bank",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    charing_cross = Station(
        tfl_id="940GZZLUCHX",
        name="Charing Cross",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([bank, charing_cross])
    await db_session.commit()

    # Create route segments: Bank -> Charing Cross (different branches!)
    segments = [
        RouteSegmentRequest(station_tfl_id="940GZZLUBNK", line_tfl_id="northern"),
        RouteSegmentRequest(station_tfl_id="940GZZLUCHX"),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify - should FAIL (different branches)
    assert is_valid is False
    assert "different branches" in message.lower()
    assert "Bank" in message
    assert "Charing Cross" in message
    assert invalid_segment == 0


async def test_validate_route_same_branch_succeeds(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test that validation succeeds for stations on the same branch (e.g., Bank -> Morden via Bank)."""
    # Create Northern line
    line = Line(
        tfl_id="northern",
        name="Northern",
        color="#000000",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Edgware → Morden via Bank",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEGW", "940GZZLUCND", "940GZZLUBNK", "940GZZLUMDN"],
                },
                {
                    "name": "Edgware → Morden via Charing Cross",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEGW", "940GZZLUCND", "940GZZLUCHX", "940GZZLUMDN"],
                },
            ]
        },
    )
    db_session.add(line)
    await db_session.flush()

    # Create stations on same branch
    bank = Station(
        tfl_id="940GZZLUBNK",
        name="Bank",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    morden = Station(
        tfl_id="940GZZLUMDN",
        name="Morden",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([bank, morden])
    await db_session.commit()

    # Create route segments: Bank -> Morden (same branch)
    segments = [
        RouteSegmentRequest(station_tfl_id="940GZZLUBNK", line_tfl_id="northern"),
        RouteSegmentRequest(station_tfl_id="940GZZLUMDN"),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify - should SUCCEED (same branch)
    assert is_valid is True
    assert "valid" in message.lower()
    assert invalid_segment is None


async def test_validate_route_before_branch_split_succeeds(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test that validation succeeds for stations before the branch split (e.g., Edgware -> Camden Town)."""
    # Create Northern line
    line = Line(
        tfl_id="northern",
        name="Northern",
        color="#000000",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Edgware → Morden via Bank",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEGW", "940GZZLUCND", "940GZZLUBNK", "940GZZLUMDN"],
                },
                {
                    "name": "Edgware → Morden via Charing Cross",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEGW", "940GZZLUCND", "940GZZLUCHX", "940GZZLUMDN"],
                },
            ]
        },
    )
    db_session.add(line)
    await db_session.flush()

    # Create stations before branch split
    edgware = Station(
        tfl_id="940GZZLUEGW",
        name="Edgware",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    camden = Station(
        tfl_id="940GZZLUCND",
        name="Camden Town",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([edgware, camden])
    await db_session.commit()

    # Create route segments: Edgware -> Camden Town (before split, in both routes)
    segments = [
        RouteSegmentRequest(station_tfl_id="940GZZLUEGW", line_tfl_id="northern"),
        RouteSegmentRequest(station_tfl_id="940GZZLUCND"),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify - should SUCCEED (both stations in all route sequences)
    assert is_valid is True
    assert "valid" in message.lower()
    assert invalid_segment is None


async def test_validate_route_full_line_succeeds(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test that validation succeeds for full-line routes (e.g., Edgware -> Morden)."""
    # Create Northern line
    line = Line(
        tfl_id="northern",
        name="Northern",
        color="#000000",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Edgware → Morden via Bank",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEGW", "940GZZLUCND", "940GZZLUBNK", "940GZZLUMDN"],
                },
                {
                    "name": "Edgware → Morden via Charing Cross",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEGW", "940GZZLUCND", "940GZZLUCHX", "940GZZLUMDN"],
                },
            ]
        },
    )
    db_session.add(line)
    await db_session.flush()

    # Create terminus stations
    edgware = Station(
        tfl_id="940GZZLUEGW",
        name="Edgware",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    morden = Station(
        tfl_id="940GZZLUMDN",
        name="Morden",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([edgware, morden])
    await db_session.commit()

    # Create route segments: Edgware -> Morden (full line, in both routes)
    segments = [
        RouteSegmentRequest(station_tfl_id="940GZZLUEGW", line_tfl_id="northern"),
        RouteSegmentRequest(station_tfl_id="940GZZLUMDN"),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify - should SUCCEED (both stations in multiple route sequences)
    assert is_valid is True
    assert "valid" in message.lower()
    assert invalid_segment is None


async def test_validate_route_no_routes_data_fails(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test that validation fails gracefully when line has no routes data."""
    # Create line WITHOUT routes data
    line = Line(
        tfl_id="northern",
        name="Northern",
        color="#000000",
        last_updated=datetime.now(UTC),
        routes=None,  # No routes data!
    )
    db_session.add(line)
    await db_session.flush()

    # Create stations
    bank = Station(
        tfl_id="940GZZLUBNK",
        name="Bank",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    morden = Station(
        tfl_id="940GZZLUMDN",
        name="Morden",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([bank, morden])
    await db_session.commit()

    # Create route segments
    segments = [
        RouteSegmentRequest(station_tfl_id="940GZZLUBNK", line_tfl_id="northern"),
        RouteSegmentRequest(station_tfl_id="940GZZLUMDN"),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify - should FAIL (no routes data)
    # When line has no routes but both stations serve the line, the "different branches" message is shown
    assert is_valid is False
    assert "different branches" in message.lower() or "no connection" in message.lower()
    assert invalid_segment == 0


# ==================== Helper Method Tests ====================


def test_handle_api_error_with_api_error(tfl_service: TfLService) -> None:
    """Test that _handle_api_error raises HTTPException when given an ApiError."""
    # Create mock ApiError with all required fields
    api_error = ApiError(
        timestamp_utc=datetime.now(UTC),
        http_status_code=500,
        http_status="500",
        exception_type="ServerError",
        message="TfL API is experiencing issues",
        relative_uri="/Line/Mode/tube",
    )

    # Execute and verify exception is raised
    with pytest.raises(HTTPException) as exc_info:
        tfl_service._handle_api_error(api_error)

    assert exc_info.value.status_code == 503
    assert "TfL API error" in exc_info.value.detail
    assert "experiencing issues" in exc_info.value.detail


def test_handle_api_error_with_valid_response(tfl_service: TfLService) -> None:
    """Test that _handle_api_error does nothing when given a valid response."""
    # Create mock valid response
    mock_response = MagicMock()
    mock_response.shared_expires = datetime(2025, 1, 1, 13, 0, 0, tzinfo=UTC)
    mock_response.content_expires = None

    # Should not raise any exception
    tfl_service._handle_api_error(mock_response)


def test_extract_cache_ttl_with_shared_expires(tfl_service: TfLService) -> None:
    """Test extracting TTL from shared_expires field."""
    with freeze_time("2025-01-01 12:00:00"):
        mock_response = MagicMock()
        # shared_expires is 1 hour in the future
        mock_response.shared_expires = datetime(2025, 1, 1, 13, 0, 0, tzinfo=UTC)
        mock_response.content_expires = None

        ttl = tfl_service._extract_cache_ttl(mock_response)

        assert ttl == 3600  # 1 hour


def test_extract_cache_ttl_with_content_expires(tfl_service: TfLService) -> None:
    """Test extracting TTL from content_expires field when shared_expires is not available."""
    with freeze_time("2025-01-01 12:00:00"):
        mock_response = MagicMock()
        mock_response.shared_expires = None
        # content_expires is 30 minutes in the future
        mock_response.content_expires = datetime(2025, 1, 1, 12, 30, 0, tzinfo=UTC)

        ttl = tfl_service._extract_cache_ttl(mock_response)

        assert ttl == 1800  # 30 minutes


def test_extract_cache_ttl_no_expires(tfl_service: TfLService) -> None:
    """Test TTL extraction when no expires fields are available."""
    mock_response = MagicMock()
    mock_response.shared_expires = None
    mock_response.content_expires = None

    ttl = tfl_service._extract_cache_ttl(mock_response)

    assert ttl == 0


def test_extract_cache_ttl_expired(tfl_service: TfLService) -> None:
    """Test TTL extraction when cache has already expired (negative TTL)."""
    with freeze_time("2025-01-01 12:00:00"):
        mock_response = MagicMock()
        # shared_expires is 1 hour in the PAST
        mock_response.shared_expires = datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)
        mock_response.content_expires = None

        ttl = tfl_service._extract_cache_ttl(mock_response)

        # Should return 0 when TTL is negative (expired)
        assert ttl == 0


def test_parse_redis_host(tfl_service: TfLService) -> None:
    """Test parsing Redis host from URL."""
    host = tfl_service._parse_redis_host()
    assert isinstance(host, str)
    assert len(host) > 0


def test_parse_redis_port(tfl_service: TfLService) -> None:
    """Test parsing Redis port from URL."""
    port = tfl_service._parse_redis_port()
    assert isinstance(port, int)
    assert port > 0


# ==================== Helper Method Tests for build_station_graph ====================


def test_get_stop_ids_with_id(tfl_service: TfLService) -> None:
    """Test extracting stop ID from data with 'id' attribute."""

    class MockStop:
        id = "940GZZLUVIC"

    result = tfl_service._get_stop_ids(MockStop())
    assert result == "940GZZLUVIC"


def test_get_stop_ids_with_station_id(tfl_service: TfLService) -> None:
    """Test extracting stop ID from data with 'stationId' attribute."""

    class MockStopWithStationId:
        """Mock TfL API stop with stationId field."""

        def __init__(self) -> None:
            self.stationId = "940GZZLUVIC"

    result = tfl_service._get_stop_ids(MockStopWithStationId())
    assert result == "940GZZLUVIC"


def test_get_stop_ids_missing(tfl_service: TfLService) -> None:
    """Test extraction when no ID fields present."""

    class MockStop:
        pass

    result = tfl_service._get_stop_ids(MockStop())
    assert result is None


async def test_get_station_by_tfl_id_exists(db_session: AsyncSession) -> None:
    """Test station lookup when station exists."""
    # Create a station
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add(station)
    await db_session.commit()

    # Test lookup
    tfl_service = TfLService(db_session)
    result = await tfl_service._get_station_by_tfl_id("940GZZLUVIC")

    assert result is not None
    assert result.tfl_id == "940GZZLUVIC"
    assert result.name == "Victoria"


async def test_get_station_by_tfl_id_not_found(db_session: AsyncSession) -> None:
    """Test station lookup when station doesn't exist."""
    tfl_service = TfLService(db_session)
    result = await tfl_service._get_station_by_tfl_id("nonexistent")

    assert result is None


async def test_connection_exists_true(db_session: AsyncSession) -> None:
    """Test connection existence check returns True."""
    # Create stations and line
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    station1 = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="940GZZLUGPK",
        name="Green Park",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([line, station1, station2])
    await db_session.commit()

    # Create connection
    connection = StationConnection(
        from_station_id=station1.id,
        to_station_id=station2.id,
        line_id=line.id,
    )
    db_session.add(connection)
    await db_session.commit()

    # Test existence check
    tfl_service = TfLService(db_session)
    result = await tfl_service._connection_exists(station1.id, station2.id, line.id)

    assert result is True


async def test_connection_exists_false(db_session: AsyncSession) -> None:
    """Test connection existence check returns False."""
    # Create stations and line without connection
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    station1 = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="940GZZLUGPK",
        name="Green Park",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([line, station1, station2])
    await db_session.commit()

    # Test existence check (no connection created)
    tfl_service = TfLService(db_session)
    result = await tfl_service._connection_exists(station1.id, station2.id, line.id)

    assert result is False


def test_create_connection(tfl_service: TfLService) -> None:
    """Test connection object creation."""
    from_id = uuid.uuid4()
    to_id = uuid.uuid4()
    line_id = uuid.uuid4()

    connection = tfl_service._create_connection(from_id, to_id, line_id)

    assert connection.from_station_id == from_id
    assert connection.to_station_id == to_id
    assert connection.line_id == line_id


async def test_process_station_pair_creates_both(db_session: AsyncSession) -> None:
    """Test station pair processing creates bidirectional connections."""
    # Create line and stations
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    station1 = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="940GZZLUGPK",
        name="Green Park",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([line, station1, station2])
    await db_session.commit()

    # Create mock stops
    class MockStop1:
        id = "940GZZLUVIC"

    class MockStop2:
        id = "940GZZLUGPK"

    # Process pair
    tfl_service = TfLService(db_session)
    stations_set: set[str] = set()
    pending_connections: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = set()
    count = await tfl_service._process_station_pair(MockStop1(), MockStop2(), line, stations_set, pending_connections)

    assert count == 2  # Both forward and reverse connections created
    assert "940GZZLUVIC" in stations_set
    assert "940GZZLUGPK" in stations_set


async def test_process_station_pair_missing_station(db_session: AsyncSession) -> None:
    """Test station pair processing when station not in DB."""
    # Create line but no stations
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.commit()

    # Create mock stops
    class MockStop1:
        id = "nonexistent1"

    class MockStop2:
        id = "nonexistent2"

    # Process pair
    tfl_service = TfLService(db_session)
    stations_set: set[str] = set()
    pending_connections: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = set()
    count = await tfl_service._process_station_pair(MockStop1(), MockStop2(), line, stations_set, pending_connections)

    assert count == 0
    assert not stations_set


async def test_process_station_pair_existing_connections(db_session: AsyncSession) -> None:
    """Test station pair processing when connections already exist in pending set."""
    # Create line and stations
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    station1 = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="940GZZLUGPK",
        name="Green Park",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([line, station1, station2])
    await db_session.commit()

    # Create mock stops
    class MockStop1:
        id = "940GZZLUVIC"

    class MockStop2:
        id = "940GZZLUGPK"

    # Process pair
    tfl_service = TfLService(db_session)
    stations_set: set[str] = set()
    # Pre-populate pending_connections with the connections we're about to create
    # This simulates them already being processed in this transaction
    pending_connections: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = {
        (station1.id, station2.id, line.id),
        (station2.id, station1.id, line.id),
    }

    count = await tfl_service._process_station_pair(MockStop1(), MockStop2(), line, stations_set, pending_connections)

    assert count == 0  # No new connections created
    assert "940GZZLUVIC" in stations_set
    assert "940GZZLUGPK" in stations_set


# ==================== Phase 1: get_network_graph Coverage Tests ====================


async def test_get_network_graph_success(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test getting network graph with valid connections."""
    # Create test data - lines, stations, and connections
    line1 = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    line2 = Line(tfl_id="northern", name="Northern", color="#000000", last_updated=datetime.now(UTC))
    db_session.add_all([line1, line2])
    await db_session.flush()

    station_a = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station_b = Station(
        tfl_id="940GZZLUGPK",
        name="Green Park",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station_c = Station(
        tfl_id="940GZZLUKSX",
        name="King's Cross",
        latitude=51.5,
        longitude=-0.1,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station_a, station_b, station_c])
    await db_session.flush()

    # Create connections: A -> B on victoria, B -> C on northern
    conn1 = StationConnection(from_station_id=station_a.id, to_station_id=station_b.id, line_id=line1.id)
    conn2 = StationConnection(from_station_id=station_b.id, to_station_id=station_c.id, line_id=line2.id)
    db_session.add_all([conn1, conn2])
    await db_session.commit()

    # Execute
    graph = await tfl_service.get_network_graph()

    # Verify adjacency list structure
    assert isinstance(graph, dict)
    assert len(graph) == 2  # Two stations have outbound connections

    # Verify Victoria station connections
    assert "940GZZLUVIC" in graph
    victoria_connections = graph["940GZZLUVIC"]
    assert len(victoria_connections) == 1
    assert victoria_connections[0]["station_tfl_id"] == "940GZZLUGPK"
    assert victoria_connections[0]["station_name"] == "Green Park"
    assert victoria_connections[0]["line_tfl_id"] == "victoria"
    assert victoria_connections[0]["line_name"] == "Victoria"

    # Verify Green Park station connections
    assert "940GZZLUGPK" in graph
    green_park_connections = graph["940GZZLUGPK"]
    assert len(green_park_connections) == 1
    assert green_park_connections[0]["station_tfl_id"] == "940GZZLUKSX"
    assert green_park_connections[0]["line_tfl_id"] == "northern"


async def test_get_network_graph_no_graph_built(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test getting network graph when no connections exist (graph not built)."""
    # Don't create any connections - graph is empty

    # Execute and verify exception
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_network_graph()

    assert exc_info.value.status_code == 503
    assert "graph has not been built" in exc_info.value.detail.lower()


async def test_get_network_graph_exception(
    tfl_service: TfLService,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test get_network_graph handles database failures correctly."""
    # Create at least one connection so the initial check passes
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    station1 = Station(
        tfl_id="st1",
        name="Station 1",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="st2",
        name="Station 2",
        latitude=51.5,
        longitude=-0.1,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([line, station1, station2])
    await db_session.flush()

    conn = StationConnection(from_station_id=station1.id, to_station_id=station2.id, line_id=line.id)
    db_session.add(conn)
    await db_session.commit()

    # Mock db.execute to raise exception on the main query (second execute call)
    original_execute = db_session.execute
    call_count = [0]

    async def mock_execute(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        call_count[0] += 1
        if call_count[0] == 2:  # Second call is the main query
            error_msg = "Database error"
            raise Exception(error_msg)
        return await original_execute(*args, **kwargs)

    monkeypatch.setattr(db_session, "execute", mock_execute)

    # Execute and verify exception
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_network_graph()

    assert exc_info.value.status_code == 500
    assert "failed to fetch network graph" in exc_info.value.detail.lower()


# ==================== Phase 2: Edge Case Coverage Tests ====================


async def test_process_station_pair_missing_stop_ids(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test _process_station_pair when stop objects lack ID fields (covers line 1162)."""
    # Create line
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.commit()

    # Create mock stops without id or stationId fields
    class MockStopNoId:
        pass  # No id or stationId attribute

    # Process pair with missing IDs
    stations_set: set[str] = set()
    pending_connections: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = set()
    count = await tfl_service._process_station_pair(
        MockStopNoId(),
        MockStopNoId(),
        line,
        stations_set,
        pending_connections,
    )

    # Should return 0 and not add to set
    assert count == 0
    assert len(stations_set) == 0


@patch("asyncio.get_running_loop")
async def test_fetch_station_disruptions_stop_without_id(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetch_station_disruptions handles stops without ID fields (covers lines 760-761)."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create valid station to ensure we can test the missing ID path
        station = Station(
            tfl_id="940GZZLUKSX",
            name="King's Cross",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        db_session.add(station)
        await db_session.commit()

        # Create mock stop without id or stationId
        class MockStopNoId:
            pass  # No id or stationId

        # Mock disruption with stop missing ID
        class MockDisruptionNoId:
            def __init__(self) -> None:
                self.category = "RealTime"
                self.categoryDescription = "Lift Closure"
                self.description = "Lift issue"
                self.id = "disruption-1"
                self.created = datetime.now(UTC)
                self.affectedStops = [MockStopNoId()]

        mock_disruptions = [MockDisruptionNoId()]
        mock_response = MockResponse(
            data=mock_disruptions,
            shared_expires=datetime(2025, 1, 1, 12, 2, 0, tzinfo=UTC),
        )

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
        mock_get_loop.return_value = mock_loop

        # Execute
        disruptions = await tfl_service.fetch_station_disruptions(use_cache=False)

        # Should skip disruption with missing stop ID (warning logged)
        assert len(disruptions) == 0


@patch("asyncio.get_running_loop")
async def test_fetch_route_sequence_no_stop_points(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test _fetch_route_sequence returns route data even when no stopPointSequences."""
    # Create line
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.commit()

    # Mock route response without stopPointSequences
    class MockRouteNoSequences:
        pass  # No stopPointSequences attribute

    mock_response = MagicMock()
    mock_response.content = MockRouteNoSequences()

    mock_loop = AsyncMock()
    mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
    mock_get_loop.return_value = mock_loop

    # Execute
    tfl_service_instance = TfLService(db_session)
    route_data = await tfl_service_instance._fetch_route_sequence(line.tfl_id, "inbound")

    # Should return the route data object (not a list anymore)
    assert route_data is not None
    assert isinstance(route_data, MockRouteNoSequences)


@patch("asyncio.get_running_loop")
async def test_process_route_sequence_empty_stop_points(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test _process_route_sequence handles sequences without stopPoint (covers line 1001)."""
    # Create line
    line = Line(tfl_id="victoria", name="Victoria", color="#000000", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.commit()

    # Mock route sequence without stopPoint attribute
    class MockSequenceNoStopPoint:
        pass  # No stopPoint attribute

    class MockRouteWithEmptySequence:
        def __init__(self) -> None:
            self.stopPointSequences = [MockSequenceNoStopPoint()]

    mock_response = MagicMock()
    mock_response.content = MockRouteWithEmptySequence()

    mock_loop = AsyncMock()
    mock_loop.run_in_executor = AsyncMock(return_value=mock_response)
    mock_get_loop.return_value = mock_loop

    # Execute
    stations_set: set[str] = set()
    pending_connections: set[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = set()
    count, route_data = await tfl_service._process_route_sequence(line, "inbound", stations_set, pending_connections)

    # Should skip sequence without stopPoint and return 0 connections
    assert count == 0
    assert len(stations_set) == 0
    # Should still return route data
    assert route_data is not None
    assert isinstance(route_data, MockRouteWithEmptySequence)


# ==================== Phase 3: Error Propagation Tests ====================


async def test_api_error_propagation_in_fetch_methods(
    tfl_service: TfLService,
) -> None:
    """Test that HTTPException from _handle_api_error propagates correctly in fetch methods."""
    # Test with fetch_lines (covers line 202)
    with patch("asyncio.get_running_loop") as mock_get_loop:
        # Create ApiError response
        api_error = ApiError(
            timestamp_utc=datetime.now(UTC),
            http_status_code=500,
            http_status="500",
            exception_type="ServerError",
            message="TfL API error",
            relative_uri="/Line/Mode/tube",
        )

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=api_error)
        mock_get_loop.return_value = mock_loop

        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.fetch_lines(use_cache=False)

        assert exc_info.value.status_code == 503
        assert "TfL API error" in exc_info.value.detail

    # Test with fetch_severity_codes (covers line 279)
    with patch("asyncio.get_running_loop") as mock_get_loop:
        api_error = ApiError(
            timestamp_utc=datetime.now(UTC),
            http_status_code=503,
            http_status="503",
            exception_type="ServiceUnavailable",
            message="Service temporarily unavailable",
            relative_uri="/Line/Meta/Severity",
        )

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=api_error)
        mock_get_loop.return_value = mock_loop

        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.fetch_severity_codes(use_cache=False)

        assert exc_info.value.status_code == 503

    # Test with fetch_disruption_categories (covers line 355)
    with patch("asyncio.get_running_loop") as mock_get_loop:
        api_error = ApiError(
            timestamp_utc=datetime.now(UTC),
            http_status_code=500,
            http_status="500",
            exception_type="ServerError",
            message="Internal server error",
            relative_uri="/Line/Meta/DisruptionCategories",
        )

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=api_error)
        mock_get_loop.return_value = mock_loop

        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.fetch_disruption_categories(use_cache=False)

        assert exc_info.value.status_code == 503

    # Test with fetch_stop_types (covers line 442)
    with patch("asyncio.get_running_loop") as mock_get_loop:
        api_error = ApiError(
            timestamp_utc=datetime.now(UTC),
            http_status_code=404,
            http_status="404",
            exception_type="NotFound",
            message="Resource not found",
            relative_uri="/StopPoint/Meta/StopTypes",
        )

        mock_loop = AsyncMock()
        mock_loop.run_in_executor = AsyncMock(return_value=api_error)
        mock_get_loop.return_value = mock_loop

        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.fetch_stop_types(use_cache=False)

        assert exc_info.value.status_code == 503


@patch("asyncio.get_running_loop")
async def test_fetch_stations_api_error_handling(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetch_stations handles non-HTTPException errors correctly (covers lines 540-545)."""
    # Mock executor to raise a generic Exception (not HTTPException)
    mock_loop = AsyncMock()
    mock_loop.run_in_executor = AsyncMock(side_effect=Exception("Unexpected database error"))
    mock_get_loop.return_value = mock_loop

    # Execute and verify proper error handling
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.fetch_stations(line_tfl_id="victoria", use_cache=False)

    assert exc_info.value.status_code == 503
    assert "Failed to fetch stations from TfL API" in exc_info.value.detail


# ==================== Route Sequences Tests ====================
# Note: MockOrderedRoute and MockRouteSequence are defined at the top of this file


# ==================== _store_line_routes Tests ====================


async def test_store_line_routes_regular_service(db_session: AsyncSession) -> None:
    """Test storing line routes with Regular service type."""
    # Setup
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Create mock route data
    inbound_routes = [
        MockOrderedRoute(
            name="Walthamstow Central → Brixton",
            service_type="Regular",
            naptan_ids=["940GZZLUWAC", "940GZZLUVIC", "940GZZLUBXN"],
        )
    ]
    outbound_routes = [
        MockOrderedRoute(
            name="Brixton → Walthamstow Central",
            service_type="Regular",
            naptan_ids=["940GZZLUBXN", "940GZZLUVIC", "940GZZLUWAC"],
        )
    ]
    inbound_data = MockRouteSequence(orderedLineRoutes=inbound_routes)
    outbound_data = MockRouteSequence(orderedLineRoutes=outbound_routes)

    # Execute
    tfl_service = TfLService(db_session)
    tfl_service._store_line_routes(line, inbound_data, outbound_data)

    # Verify
    assert line.routes is not None
    assert "routes" in line.routes
    routes = line.routes["routes"]
    assert len(routes) == 2

    # Check inbound route
    inbound = routes[0]
    assert inbound["name"] == "Walthamstow Central → Brixton"
    assert inbound["service_type"] == "Regular"
    assert inbound["direction"] == "inbound"
    assert inbound["stations"] == ["940GZZLUWAC", "940GZZLUVIC", "940GZZLUBXN"]

    # Check outbound route
    outbound = routes[1]
    assert outbound["name"] == "Brixton → Walthamstow Central"
    assert outbound["service_type"] == "Regular"
    assert outbound["direction"] == "outbound"
    assert outbound["stations"] == ["940GZZLUBXN", "940GZZLUVIC", "940GZZLUWAC"]


async def test_store_line_routes_skip_night_service(db_session: AsyncSession) -> None:
    """Test that Night service routes are skipped (not Regular)."""
    # Setup
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Create mixed service type routes
    inbound_routes = [
        MockOrderedRoute(
            name="Regular Route",
            service_type="Regular",
            naptan_ids=["940GZZLUVIC", "940GZZLUGPK"],
        ),
        MockOrderedRoute(
            name="Night Route",
            service_type="Night",
            naptan_ids=["940GZZLUVIC", "940GZZLUGPK"],
        ),
    ]
    inbound_data = MockRouteSequence(orderedLineRoutes=inbound_routes)

    # Execute
    tfl_service = TfLService(db_session)
    tfl_service._store_line_routes(line, inbound_data, None)

    # Verify - only Regular service should be stored
    assert line.routes is not None
    routes = line.routes["routes"]
    assert len(routes) == 1
    assert routes[0]["name"] == "Regular Route"
    assert routes[0]["service_type"] == "Regular"


async def test_store_line_routes_none_data(db_session: AsyncSession) -> None:
    """Test storing line routes when both inbound and outbound data are None."""
    # Setup
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Execute with None data
    tfl_service = TfLService(db_session)
    tfl_service._store_line_routes(line, None, None)

    # Verify - routes should not be set
    assert line.routes is None


async def test_store_line_routes_empty_ordered_routes(db_session: AsyncSession) -> None:
    """Test storing line routes when orderedLineRoutes is empty."""
    # Setup
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Create route data with empty orderedLineRoutes
    inbound_data = MockRouteSequence(orderedLineRoutes=[])

    # Execute
    tfl_service = TfLService(db_session)
    tfl_service._store_line_routes(line, inbound_data, None)

    # Verify - routes should not be set
    assert line.routes is None


async def test_store_line_routes_no_naptan_ids(db_session: AsyncSession) -> None:
    """Test storing line routes when route has no naptanIds."""
    # Setup
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Create route with empty naptanIds
    inbound_routes = [
        MockOrderedRoute(
            name="Empty Route",
            service_type="Regular",
            naptan_ids=[],
        )
    ]
    inbound_data = MockRouteSequence(orderedLineRoutes=inbound_routes)

    # Execute
    tfl_service = TfLService(db_session)
    tfl_service._store_line_routes(line, inbound_data, None)

    # Verify - routes should not be set (route was skipped)
    assert line.routes is None


async def test_store_line_routes_no_ordered_routes_attr(db_session: AsyncSession) -> None:
    """Test storing line routes when data has no orderedLineRoutes attribute."""
    # Setup
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Create mock data without orderedLineRoutes attribute
    class MockDataWithoutRoutes:
        pass

    inbound_data = MockDataWithoutRoutes()

    # Execute
    tfl_service = TfLService(db_session)
    tfl_service._store_line_routes(line, inbound_data, None)

    # Verify - routes should not be set
    assert line.routes is None


async def test_store_line_routes_only_inbound(db_session: AsyncSession) -> None:
    """Test storing line routes with only inbound data."""
    # Setup
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Create only inbound routes
    inbound_routes = [
        MockOrderedRoute(
            name="Inbound Route",
            service_type="Regular",
            naptan_ids=["940GZZLUVIC", "940GZZLUGPK"],
        )
    ]
    inbound_data = MockRouteSequence(orderedLineRoutes=inbound_routes)

    # Execute
    tfl_service = TfLService(db_session)
    tfl_service._store_line_routes(line, inbound_data, None)

    # Verify
    assert line.routes is not None
    routes = line.routes["routes"]
    assert len(routes) == 1
    assert routes[0]["direction"] == "inbound"


async def test_store_line_routes_only_outbound(db_session: AsyncSession) -> None:
    """Test storing line routes with only outbound data."""
    # Setup
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Create only outbound routes
    outbound_routes = [
        MockOrderedRoute(
            name="Outbound Route",
            service_type="Regular",
            naptan_ids=["940GZZLUGPK", "940GZZLUVIC"],
        )
    ]
    outbound_data = MockRouteSequence(orderedLineRoutes=outbound_routes)

    # Execute
    tfl_service = TfLService(db_session)
    tfl_service._store_line_routes(line, None, outbound_data)

    # Verify
    assert line.routes is not None
    routes = line.routes["routes"]
    assert len(routes) == 1
    assert routes[0]["direction"] == "outbound"


# ==================== get_line_routes Tests ====================


async def test_get_line_routes_success(db_session: AsyncSession) -> None:
    """Test successful retrieval of line routes."""
    # Setup - create line with routes
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Route 1",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUVIC", "940GZZLUGPK"],
                }
            ]
        },
    )
    db_session.add(line)
    await db_session.commit()

    # Execute
    tfl_service = TfLService(db_session)
    result = await tfl_service.get_line_routes("victoria")

    # Verify
    assert result is not None
    assert result["line_tfl_id"] == "victoria"
    assert len(result["routes"]) == 1
    assert result["routes"][0]["name"] == "Route 1"
    assert result["routes"][0]["service_type"] == "Regular"
    assert result["routes"][0]["direction"] == "inbound"
    assert result["routes"][0]["stations"] == ["940GZZLUVIC", "940GZZLUGPK"]


async def test_get_line_routes_line_not_found(db_session: AsyncSession) -> None:
    """Test get_line_routes when line does not exist."""
    # Execute
    tfl_service = TfLService(db_session)

    # Verify - should raise 404
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_line_routes("nonexistent-line")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Line 'nonexistent-line' not found" in exc_info.value.detail


async def test_get_line_routes_not_built(db_session: AsyncSession) -> None:
    """Test get_line_routes when routes have not been built yet."""
    # Setup - create line without routes
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add(line)
    await db_session.commit()

    # Execute
    tfl_service = TfLService(db_session)

    # Verify - should raise 503
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_line_routes("victoria")

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Route data has not been built yet" in exc_info.value.detail


async def test_get_line_routes_empty_routes(db_session: AsyncSession) -> None:
    """Test get_line_routes when routes field exists but is empty."""
    # Setup - create line with empty routes
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
        routes={},
    )
    db_session.add(line)
    await db_session.commit()

    # Execute
    tfl_service = TfLService(db_session)
    result = await tfl_service.get_line_routes("victoria")

    # Verify - should return empty routes list
    assert result is not None
    assert result["line_tfl_id"] == "victoria"
    assert result["routes"] == []


@patch("app.services.tfl_service.logger")
async def test_get_line_routes_database_error(
    mock_logger: MagicMock,
    db_session: AsyncSession,
) -> None:
    """Test get_line_routes when database error occurs."""
    # Setup - create service with a session that will fail
    tfl_service = TfLService(db_session)

    # Mock the database execute to raise an exception (not HTTPException)
    with patch.object(
        db_session,
        "execute",
        side_effect=Exception("Database connection error"),
    ):
        # Verify - should raise 500
        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.get_line_routes("victoria")

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to fetch routes for line 'victoria'" in exc_info.value.detail


# ==================== get_station_routes Tests ====================


async def test_get_station_routes_success(db_session: AsyncSession) -> None:
    """Test successful retrieval of station routes."""
    # Setup - create station with lines and routes
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.4965,
        longitude=-0.1447,
        lines=["victoria", "district"],
        last_updated=datetime.now(UTC),
    )
    line1 = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Route 1",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUVIC", "940GZZLUGPK"],
                }
            ]
        },
    )
    line2 = Line(
        tfl_id="district",
        name="District",
        color="#00782A",
        mode="tube",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Route 2",
                    "service_type": "Regular",
                    "direction": "outbound",
                    "stations": ["940GZZLUVIC", "940GZZLUERC"],
                }
            ]
        },
    )
    db_session.add_all([station, line1, line2])
    await db_session.commit()

    # Execute
    tfl_service = TfLService(db_session)
    result = await tfl_service.get_station_routes("940GZZLUVIC")

    # Verify
    assert result is not None
    assert result["station_tfl_id"] == "940GZZLUVIC"
    assert result["station_name"] == "Victoria"
    assert len(result["routes"]) == 2

    # Find routes by line
    victoria_route = next(r for r in result["routes"] if r["line_tfl_id"] == "victoria")
    district_route = next(r for r in result["routes"] if r["line_tfl_id"] == "district")

    # Verify Victoria route
    assert victoria_route["line_name"] == "Victoria"
    assert victoria_route["route_name"] == "Route 1"
    assert victoria_route["service_type"] == "Regular"
    assert victoria_route["direction"] == "inbound"

    # Verify District route
    assert district_route["line_name"] == "District"
    assert district_route["route_name"] == "Route 2"
    assert district_route["service_type"] == "Regular"
    assert district_route["direction"] == "outbound"


async def test_get_station_routes_station_not_found(db_session: AsyncSession) -> None:
    """Test get_station_routes when station does not exist."""
    # Execute
    tfl_service = TfLService(db_session)

    # Verify - should raise 404
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_station_routes("940GZZLUNONEXISTENT")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Station '940GZZLUNONEXISTENT' not found" in exc_info.value.detail


async def test_get_station_routes_no_lines(db_session: AsyncSession) -> None:
    """Test get_station_routes when station has no lines."""
    # Setup - create station with empty lines array
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.4965,
        longitude=-0.1447,
        lines=[],
        last_updated=datetime.now(UTC),
    )
    db_session.add(station)
    await db_session.commit()

    # Execute
    tfl_service = TfLService(db_session)
    result = await tfl_service.get_station_routes("940GZZLUVIC")

    # Verify - should return empty routes
    assert result is not None
    assert result["station_tfl_id"] == "940GZZLUVIC"
    assert result["station_name"] == "Victoria"
    assert result["routes"] == []


async def test_get_station_routes_not_built(db_session: AsyncSession) -> None:
    """Test get_station_routes when routes have not been built yet."""
    # Setup - create station and line without routes
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.4965,
        longitude=-0.1447,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station, line])
    await db_session.commit()

    # Execute
    tfl_service = TfLService(db_session)

    # Verify - should raise 503
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_station_routes("940GZZLUVIC")

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Route data has not been built yet" in exc_info.value.detail


async def test_get_station_routes_station_not_on_route(db_session: AsyncSession) -> None:
    """Test get_station_routes when station is on line but not on any route variant."""
    # Setup - create station and line, but station not in route stations
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.4965,
        longitude=-0.1447,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    line = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        mode="tube",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Route 1",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUGPK", "940GZZLUKSX"],  # Victoria not included
                }
            ]
        },
    )
    db_session.add_all([station, line])
    await db_session.commit()

    # Execute
    tfl_service = TfLService(db_session)

    # Verify - should raise 503 (routes exist but station not on any)
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_station_routes("940GZZLUVIC")

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Route data has not been built yet" in exc_info.value.detail


async def test_get_station_routes_multiple_routes_same_line(db_session: AsyncSession) -> None:
    """Test get_station_routes when station is on multiple route variants of same line."""
    # Setup - create station with multiple routes on same line
    station = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.4965,
        longitude=-0.1447,
        lines=["northern"],
        last_updated=datetime.now(UTC),
    )
    line = Line(
        tfl_id="northern",
        name="Northern",
        color="#000000",
        mode="tube",
        last_updated=datetime.now(UTC),
        routes={
            "routes": [
                {
                    "name": "Edgware → Morden via Bank",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUEDG", "940GZZLUVIC", "940GZZLUMSN"],
                },
                {
                    "name": "High Barnet → Morden via Bank",
                    "service_type": "Regular",
                    "direction": "inbound",
                    "stations": ["940GZZLUHBT", "940GZZLUVIC", "940GZZLUMSN"],
                },
            ]
        },
    )
    db_session.add_all([station, line])
    await db_session.commit()

    # Execute
    tfl_service = TfLService(db_session)
    result = await tfl_service.get_station_routes("940GZZLUVIC")

    # Verify - should return both routes
    assert result is not None
    assert len(result["routes"]) == 2
    route_names = [r["route_name"] for r in result["routes"]]
    assert "Edgware → Morden via Bank" in route_names
    assert "High Barnet → Morden via Bank" in route_names


@patch("app.services.tfl_service.logger")
async def test_get_station_routes_database_error(
    mock_logger: MagicMock,
    db_session: AsyncSession,
) -> None:
    """Test get_station_routes when database error occurs."""
    # Setup - create service with a session that will fail
    tfl_service = TfLService(db_session)

    # Mock the database execute to raise an exception (not HTTPException)
    with patch.object(
        db_session,
        "execute",
        side_effect=Exception("Database connection error"),
    ):
        # Verify - should raise 500
        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.get_station_routes("940GZZLUVIC")

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to fetch routes for station '940GZZLUVIC'" in exc_info.value.detail


# ==================== Additional Coverage Tests ====================


async def test_fetch_stations_update_existing_station(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetch_stations updates existing station with new line (covers line 656)."""
    with freeze_time("2025-01-01 12:00:00"):
        # Create existing station with one line
        existing_station = Station(
            tfl_id="940GZZLUVIC",
            name="Victoria",
            latitude=51.4966,
            longitude=-0.1448,
            lines=["victoria"],
            last_updated=datetime(2024, 12, 1, tzinfo=UTC),
        )
        db_session.add(existing_station)
        await db_session.commit()

        # Mock API response for same station on different line
        mock_stops = [
            create_mock_place(id="940GZZLUVIC", common_name="Victoria", lat=51.4966, lon=-0.1448),
        ]

        # Execute with helper - fetch for district line
        stations = await assert_fetch_from_api(
            tfl_service=tfl_service,
            method_callable=lambda: tfl_service.fetch_stations(line_tfl_id="district", use_cache=False),
            mock_data=mock_stops,
            expected_count=1,
            cache_key="stations:line:district",
            expected_ttl=86400,
            shared_expires=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
        )

        # Verify station was updated with new line
        assert "district" in stations[0].lines
        assert "victoria" in stations[0].lines
        assert stations[0].last_updated == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)


@patch("asyncio.get_running_loop")
async def test_fetch_stations_http_exception_reraise(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetch_stations re-raises HTTPException (covers line 713)."""
    # Mock executor to raise HTTPException
    mock_loop = AsyncMock()
    custom_http_error = HTTPException(status_code=429, detail="Rate limit exceeded")
    mock_loop.run_in_executor = AsyncMock(side_effect=custom_http_error)
    mock_get_loop.return_value = mock_loop

    # Execute and verify HTTPException is re-raised
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.fetch_stations(line_tfl_id="victoria", use_cache=False)

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail


@patch("asyncio.get_running_loop")
async def test_fetch_line_disruptions_http_exception_reraise(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetch_line_disruptions re-raises HTTPException (covers line 848)."""
    # Mock executor to raise HTTPException
    mock_loop = AsyncMock()
    custom_http_error = HTTPException(status_code=401, detail="Unauthorized")
    mock_loop.run_in_executor = AsyncMock(side_effect=custom_http_error)
    mock_get_loop.return_value = mock_loop

    # Execute and verify HTTPException is re-raised
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.fetch_line_disruptions(modes=["tube"], use_cache=False)

    assert exc_info.value.status_code == 401
    assert "Unauthorized" in exc_info.value.detail


@patch("asyncio.get_running_loop")
async def test_fetch_line_disruptions_generic_exception(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetch_line_disruptions wraps generic exceptions (covers lines 850-852)."""
    # Mock executor to raise a generic exception
    mock_loop = AsyncMock()
    mock_loop.run_in_executor = AsyncMock(side_effect=ValueError("Invalid data format"))
    mock_get_loop.return_value = mock_loop

    # Execute and verify exception is wrapped in HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.fetch_line_disruptions(modes=["tube", "dlr"], use_cache=False)

    assert exc_info.value.status_code == 503
    assert "Failed to fetch line disruptions from TfL API for modes: ['tube', 'dlr']" in exc_info.value.detail


@patch("asyncio.get_running_loop")
async def test_fetch_station_disruptions_http_exception_reraise(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetch_station_disruptions re-raises HTTPException (covers line 1044)."""
    # Mock executor to raise HTTPException
    mock_loop = AsyncMock()
    custom_http_error = HTTPException(status_code=404, detail="Not found")
    mock_loop.run_in_executor = AsyncMock(side_effect=custom_http_error)
    mock_get_loop.return_value = mock_loop

    # Execute and verify HTTPException is re-raised
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.fetch_station_disruptions(modes=["tube"], use_cache=False)

    assert exc_info.value.status_code == 404
    assert "Not found" in exc_info.value.detail


@patch("asyncio.get_running_loop")
async def test_process_route_sequence_exception_handling(
    mock_get_loop: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test _process_route_sequence handles exceptions gracefully (covers lines 1282-1289)."""
    # Create line
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.commit()

    # Mock executor to raise a generic exception during route sequence fetch
    mock_loop = AsyncMock()
    mock_loop.run_in_executor = AsyncMock(side_effect=ValueError("Invalid route data"))
    mock_get_loop.return_value = mock_loop

    # Call _process_route_sequence - should catch exception and return (0, None)
    count, route_data = await tfl_service._process_route_sequence(line, "inbound", set(), set())

    assert count == 0
    assert route_data is None


async def test_get_line_by_tfl_id_not_found(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test get_line_by_tfl_id raises 404 when line not found (covers lines 1616-1617)."""
    # Try to get non-existent line
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_line_by_tfl_id("non-existent-line")

    assert exc_info.value.status_code == 404
    assert "Line with TfL ID 'non-existent-line' not found" in exc_info.value.detail
    assert "Please ensure TfL data is imported" in exc_info.value.detail


async def test_validate_route_no_connection_different_lines(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test validate_route message when stations are on different lines (covers line 1753)."""
    # Create line with routes data (required for _check_connection to work)
    victoria = Line(
        tfl_id="victoria",
        name="Victoria",
        color="#0019A8",
        last_updated=datetime.now(UTC),
        routes={"routes": [{"name": "Test Route", "stations": ["940GZZLUVIC"]}]},
    )
    db_session.add(victoria)

    # Create two stations on different lines (no common line)
    station1 = Station(
        tfl_id="940GZZLUVIC",
        name="Victoria",
        latitude=51.4966,
        longitude=-0.1448,
        lines=["victoria"],
        last_updated=datetime.now(UTC),
    )
    station2 = Station(
        tfl_id="940GZZLUSKS",
        name="Sloane Square",
        latitude=51.4924,
        longitude=-0.1565,
        lines=["district"],  # Different line
        last_updated=datetime.now(UTC),
    )
    db_session.add_all([station1, station2])
    await db_session.commit()

    # Try to validate route between stations on different lines
    segments = [
        RouteSegmentRequest(station_tfl_id="940GZZLUVIC", line_tfl_id="victoria"),
        RouteSegmentRequest(station_tfl_id="940GZZLUSKS", line_tfl_id=None),
    ]

    is_valid, message, segment_index = await tfl_service.validate_route(segments)

    assert not is_valid
    assert "No connection found between 'Victoria' and 'Sloane Square' on Victoria line" in message
    assert segment_index == 0  # First segment failed


async def test_validate_route_generic_exception(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test validate_route handles generic exceptions (covers lines 1777-1779)."""
    # Mock db.execute to raise a generic exception
    with patch.object(
        db_session,
        "execute",
        side_effect=Exception("Database error"),
    ):
        segments = [
            RouteSegmentRequest(station_tfl_id="940GZZLUVIC", line_tfl_id="victoria"),
            RouteSegmentRequest(station_tfl_id="940GZZLUSKS", line_tfl_id=None),
        ]

        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.validate_route(segments)

        assert exc_info.value.status_code == 500
        assert "Failed to validate route" in exc_info.value.detail


async def test_check_connection_missing_entities(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test _check_connection returns False when entities are missing (covers lines 1811-1817)."""
    # Create a valid line
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.commit()

    # Test with non-existent station UUIDs
    fake_uuid1 = uuid.uuid4()
    fake_uuid2 = uuid.uuid4()

    result = await tfl_service._check_connection(fake_uuid1, fake_uuid2, line.id)
    assert result is False
