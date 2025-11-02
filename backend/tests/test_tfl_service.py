"""Tests for TfL service."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.tfl import Line, Station, StationConnection
from app.schemas.tfl import RouteSegmentRequest
from app.services.tfl_service import TfLService
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# Mock TfL API response objects
class MockStopPoint:
    """Mock TfL stop point data."""

    def __init__(self, id: str, name: str, lat: float, lon: float) -> None:
        self.id = id
        self.name = name
        self.lat = lat
        self.lon = lon


class MockLineData:
    """Mock TfL line data."""

    def __init__(self, id: str, name: str, colour: str) -> None:
        self.id = id
        self.name = name
        self.colour = colour


class MockLineStatus:
    """Mock TfL line status."""

    def __init__(self, status_severity: int, status_severity_description: str, reason: str | None = None) -> None:
        self.status_severity = status_severity
        self.status_severity_description = status_severity_description
        self.reason = reason


class MockLineStatusData:
    """Mock TfL line status response."""

    def __init__(self, id: str, name: str, statuses: list[MockLineStatus]) -> None:
        self.id = id
        self.name = name
        self.line_statuses = statuses


class MockStopPointSequence:
    """Mock TfL stop point sequence."""

    def __init__(self, stop_points: list[MockStopPoint]) -> None:
        self.stop_points = stop_points


class MockRoute:
    """Mock TfL route."""

    def __init__(self, sequences: list[MockStopPointSequence]) -> None:
        self.stop_point_sequences = sequences


class MockResponse:
    """Mock TfL API response."""

    def __init__(self, data: list[Any], cache_control: str | None = None) -> None:
        self.data = data
        self.cache_control = cache_control


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


# ==================== fetch_lines Tests ====================


@patch("app.services.tfl_service.LineClient")
async def test_fetch_lines_from_api(
    mock_line_api: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines from TfL API when cache is empty."""
    # Setup mock response
    mock_lines = [
        MockLineData(id="victoria", name="Victoria", colour="0019A8"),
        MockLineData(id="northern", name="Northern", colour="000000"),
    ]
    mock_response = MockResponse(data=mock_lines, cache_control="max-age=86400")
    mock_line_api_instance = AsyncMock()
    mock_line_api_instance.get_line_mode_by_mode = AsyncMock(return_value=mock_response)
    mock_line_api.return_value = mock_line_api_instance

    # Execute
    lines = await tfl_service.fetch_lines(use_cache=True)

    # Verify
    assert len(lines) == 2
    assert lines[0].tfl_id == "victoria"
    assert lines[0].name == "Victoria"
    assert lines[0].color == "#0019A8"
    assert lines[1].tfl_id == "northern"
    assert lines[1].name == "Northern"
    assert lines[1].color == "#000000"

    # Verify cache was set with correct TTL
    tfl_service.cache.set.assert_called_once()
    assert tfl_service.cache.set.call_args[0][0] == "lines:all"
    assert tfl_service.cache.set.call_args[1]["ttl"] == 86400


@patch("app.services.tfl_service.LineClient")
async def test_fetch_lines_cache_hit(
    mock_line_api: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching lines from cache when available."""
    # Setup cached lines
    cached_lines = [
        Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC)),
    ]
    tfl_service.cache.get = AsyncMock(return_value=cached_lines)

    # Execute
    lines = await tfl_service.fetch_lines(use_cache=True)

    # Verify
    assert len(lines) == 1
    assert lines[0].tfl_id == "victoria"

    # Verify API was not called
    mock_line_api.return_value.get_line_mode_by_mode.assert_not_called()


@patch("app.services.tfl_service.LineClient")
async def test_fetch_lines_api_failure(
    mock_line_api: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test handling TfL API failure when fetching lines."""
    # Setup mock to raise exception
    mock_line_api_instance = AsyncMock()
    mock_line_api_instance.get_line_mode_by_mode = AsyncMock(side_effect=Exception("API Error"))
    mock_line_api.return_value = mock_line_api_instance

    # Execute and verify exception
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.fetch_lines(use_cache=False)

    assert exc_info.value.status_code == 503
    assert "Failed to fetch lines from TfL API" in exc_info.value.detail


# ==================== fetch_stations Tests ====================


@patch("app.services.tfl_service.StopPointClient")
@patch("app.services.tfl_service.LineClient")
async def test_fetch_stations_by_line(
    mock_line_api: MagicMock,
    mock_stoppoint_api: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test fetching stations for a specific line."""
    # Setup mock responses
    mock_stops = [
        MockStopPoint(id="940GZZLUKSX", name="King's Cross St. Pancras", lat=51.5308, lon=-0.1238),
        MockStopPoint(id="940GZZLUOXC", name="Oxford Circus", lat=51.5152, lon=-0.1419),
    ]
    mock_sequence = MockStopPointSequence(stop_points=mock_stops)
    mock_route = MockRoute(sequences=[mock_sequence])
    mock_response = MockResponse(data=[mock_route], cache_control="max-age=86400")

    mock_line_api_instance = AsyncMock()
    mock_line_api_instance.get_line_route_by_ids_and_direction = AsyncMock(return_value=mock_response)
    mock_line_api.return_value = mock_line_api_instance

    mock_stoppoint_api_instance = AsyncMock()
    mock_stoppoint_api_instance.get_stop_point = AsyncMock(return_value=mock_stops[0])
    mock_stoppoint_api.return_value = mock_stoppoint_api_instance

    # Execute
    stations = await tfl_service.fetch_stations(line_tfl_id="victoria", use_cache=False)

    # Verify
    assert len(stations) == 2
    assert stations[0].tfl_id == "940GZZLUKSX"
    assert stations[0].name == "King's Cross St. Pancras"
    assert "victoria" in stations[0].lines


@patch("app.services.tfl_service.LineClient")
async def test_fetch_stations_cache_hit(
    mock_line_api: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetching stations from cache when available."""
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
    tfl_service.cache.get = AsyncMock(return_value=cached_stations)

    # Execute
    stations = await tfl_service.fetch_stations(line_tfl_id="victoria", use_cache=True)

    # Verify
    assert len(stations) == 1
    assert stations[0].tfl_id == "940GZZLUKSX"

    # Verify API was not called
    mock_line_api.return_value.get_line_route_by_ids_and_direction.assert_not_called()


# ==================== fetch_disruptions Tests ====================


@patch("app.services.tfl_service.LineClient")
async def test_fetch_disruptions(
    mock_line_api: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test fetching disruptions from TfL API."""
    # Setup mock response with disruptions
    mock_statuses = [
        MockLineStatus(status_severity=5, status_severity_description="Severe Delays", reason="Signal failure"),
        MockLineStatus(status_severity=6, status_severity_description="Minor Delays"),
    ]
    mock_status_data = [
        MockLineStatusData(id="victoria", name="Victoria", statuses=[mock_statuses[0]]),
        MockLineStatusData(id="northern", name="Northern", statuses=[mock_statuses[1]]),
    ]
    mock_response = MockResponse(data=mock_status_data, cache_control="max-age=120")

    mock_line_api_instance = AsyncMock()
    mock_line_api_instance.get_line_mode_status_by_mode = AsyncMock(return_value=mock_response)
    mock_line_api.return_value = mock_line_api_instance

    # Execute
    disruptions = await tfl_service.fetch_disruptions(use_cache=False)

    # Verify
    assert len(disruptions) == 2
    assert disruptions[0].line_id == "victoria"
    assert disruptions[0].status_severity == 5
    assert disruptions[0].reason == "Signal failure"
    assert disruptions[1].line_id == "northern"
    assert disruptions[1].status_severity == 6


@patch("app.services.tfl_service.LineClient")
async def test_fetch_disruptions_good_service_filtered(
    mock_line_api: MagicMock,
    tfl_service: TfLService,
) -> None:
    """Test that 'Good Service' statuses are filtered out."""
    # Setup mock response with mix of good and bad services
    mock_statuses = [
        MockLineStatus(status_severity=10, status_severity_description="Good Service"),
        MockLineStatus(status_severity=5, status_severity_description="Severe Delays", reason="Signal failure"),
    ]
    mock_status_data = [
        MockLineStatusData(id="victoria", name="Victoria", statuses=[mock_statuses[0]]),
        MockLineStatusData(id="northern", name="Northern", statuses=[mock_statuses[1]]),
    ]
    mock_response = MockResponse(data=mock_status_data, cache_control="max-age=120")

    mock_line_api_instance = AsyncMock()
    mock_line_api_instance.get_line_mode_status_by_mode = AsyncMock(return_value=mock_response)
    mock_line_api.return_value = mock_line_api_instance

    # Execute
    disruptions = await tfl_service.fetch_disruptions(use_cache=False)

    # Verify only the severe delay is included
    assert len(disruptions) == 1
    assert disruptions[0].line_id == "northern"
    assert disruptions[0].status_severity == 5


# ==================== build_station_graph Tests ====================


@patch("app.services.tfl_service.StopPointClient")
@patch("app.services.tfl_service.LineClient")
async def test_build_station_graph(
    mock_line_api: MagicMock,
    mock_stoppoint_api: MagicMock,
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test building the station connection graph."""
    # Create test lines first
    line1 = Line(tfl_id="victoria", name="Victoria", color="#0019A8", last_updated=datetime.now(UTC))
    line2 = Line(tfl_id="northern", name="Northern", color="#000000", last_updated=datetime.now(UTC))
    db_session.add(line1)
    db_session.add(line2)
    await db_session.commit()
    await db_session.refresh(line1)
    await db_session.refresh(line2)

    # Setup mock response for victoria line
    mock_stops_victoria = [
        MockStopPoint(id="940GZZLUKSX", name="King's Cross", lat=51.5308, lon=-0.1238),
        MockStopPoint(id="940GZZLUOXC", name="Oxford Circus", lat=51.5152, lon=-0.1419),
        MockStopPoint(id="940GZZLUVIC", name="Victoria", lat=51.4965, lon=-0.1447),
    ]
    mock_sequence_victoria = MockStopPointSequence(stop_points=mock_stops_victoria)
    mock_route_victoria = MockRoute(sequences=[mock_sequence_victoria])
    mock_response_victoria = MockResponse(data=[mock_route_victoria])

    # Setup mock response for northern line
    mock_stops_northern = [
        MockStopPoint(id="940GZZLUKSX", name="King's Cross", lat=51.5308, lon=-0.1238),
        MockStopPoint(id="940GZZLUTCR", name="Tottenham Court Road", lat=51.5165, lon=-0.1308),
    ]
    mock_sequence_northern = MockStopPointSequence(stop_points=mock_stops_northern)
    mock_route_northern = MockRoute(sequences=[mock_sequence_northern])
    mock_response_northern = MockResponse(data=[mock_route_northern])

    # Mock get_line_route_by_ids_and_direction to return different responses per line
    async def mock_get_route(ids: list[str], direction: str) -> MockResponse:
        if ids[0] == "victoria":
            return mock_response_victoria
        return mock_response_northern

    mock_line_api_instance = AsyncMock()
    mock_line_api_instance.get_line_route_by_ids_and_direction = AsyncMock(side_effect=mock_get_route)
    mock_line_api.return_value = mock_line_api_instance

    # Mock lines response for initial fetch
    mock_lines_response = MockResponse(
        data=[
            MockLineData(id="victoria", name="Victoria", colour="0019A8"),
            MockLineData(id="northern", name="Northern", colour="000000"),
        ]
    )
    mock_line_api_instance.get_line_mode_by_mode = AsyncMock(return_value=mock_lines_response)

    # Execute
    result = await tfl_service.build_station_graph()

    # Verify result
    assert result["lines_count"] == 2
    assert result["stations_count"] >= 3  # At least 3 unique stations
    assert result["connections_count"] > 0

    # Verify connections were created in database
    connections_result = await db_session.execute(select(StationConnection))
    connections = connections_result.scalars().all()
    assert len(connections) > 0

    # Verify stations were created
    stations_result = await db_session.execute(select(Station))
    stations = stations_result.scalars().all()
    assert len(stations) >= 3


# ==================== validate_route Tests ====================


async def test_validate_route_success(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test successful route validation."""
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

    # Create route segments
    segments = [
        RouteSegmentRequest(station_id=station1.id, line_id=line.id),
        RouteSegmentRequest(station_id=station2.id, line_id=line.id),
        RouteSegmentRequest(station_id=station3.id, line_id=line.id),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify
    assert is_valid is True
    assert "valid" in message.lower()
    assert invalid_segment is None


async def test_validate_route_invalid_connection(
    tfl_service: TfLService,
    db_session: AsyncSession,
) -> None:
    """Test route validation with invalid connection."""
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
    db_session.add_all([station1, station2])
    await db_session.commit()

    # No connection created between stations

    # Create route segments
    segments = [
        RouteSegmentRequest(station_id=station1.id, line_id=line.id),
        RouteSegmentRequest(station_id=station2.id, line_id=line.id),
    ]

    # Execute
    is_valid, message, invalid_segment = await tfl_service.validate_route(segments)

    # Verify
    assert is_valid is False
    assert "no connection" in message.lower()
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
    segments = [RouteSegmentRequest(station_id=station1.id, line_id=line.id)]

    # Execute
    is_valid, message, _invalid_segment = await tfl_service.validate_route(segments)

    # Verify
    assert is_valid is False
    assert "at least 2 segments" in message.lower()


# ==================== Helper Method Tests ====================


def test_extract_cache_ttl_with_max_age(tfl_service: TfLService) -> None:
    """Test extracting TTL from cache-control header."""
    mock_response = MagicMock()
    mock_response.cache_control = "max-age=3600, public"

    ttl = tfl_service._extract_cache_ttl(mock_response)

    assert ttl == 3600


def test_extract_cache_ttl_no_header(tfl_service: TfLService) -> None:
    """Test TTL extraction when no cache-control header."""
    mock_response = MagicMock()
    mock_response.cache_control = None

    ttl = tfl_service._extract_cache_ttl(mock_response)

    assert ttl == 0


def test_extract_cache_ttl_no_max_age(tfl_service: TfLService) -> None:
    """Test TTL extraction when cache-control has no max-age."""
    mock_response = MagicMock()
    mock_response.cache_control = "public, must-revalidate"

    ttl = tfl_service._extract_cache_ttl(mock_response)

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
