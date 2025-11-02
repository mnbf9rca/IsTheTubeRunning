"""Tests for TfL API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import settings
from app.main import app
from app.models.tfl import Line, Station, StationConnection
from app.models.user import User
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def async_client_with_auth(test_user: User, auth_headers_for_user: dict[str, str]) -> AsyncClient:
    """Create async client with authentication headers."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers_for_user,
    ) as client:
        yield client


# ==================== GET /tfl/lines Tests ====================


@patch("app.services.tfl_service.TfLService.fetch_lines")
async def test_get_lines_success(
    mock_fetch_lines: AsyncMock,
    async_client_with_auth: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test successful retrieval of tube lines."""
    # Setup mock data
    mock_lines = [
        Line(
            id=None,  # type: ignore[arg-type]
            tfl_id="victoria",
            name="Victoria",
            color="#0019A8",
            last_updated=datetime.now(UTC),
        ),
        Line(
            id=None,  # type: ignore[arg-type]
            tfl_id="northern",
            name="Northern",
            color="#000000",
            last_updated=datetime.now(UTC),
        ),
    ]
    mock_fetch_lines.return_value = mock_lines

    # Execute
    response = await async_client_with_auth.get(f"{settings.API_V1_PREFIX}/tfl/lines")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["tfl_id"] == "victoria"
    assert data[0]["name"] == "Victoria"
    assert data[0]["color"] == "#0019A8"
    assert data[1]["tfl_id"] == "northern"


async def test_get_lines_unauthenticated(async_client_with_auth: AsyncClient) -> None:
    """Test that unauthenticated requests are rejected."""
    # Create client without auth headers
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"{settings.API_V1_PREFIX}/tfl/lines")

    assert response.status_code == 403


# ==================== GET /tfl/stations Tests ====================


@patch("app.services.tfl_service.TfLService.fetch_stations")
async def test_get_stations_all(
    mock_fetch_stations: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test retrieving all stations."""
    # Setup mock data
    mock_stations = [
        Station(
            id=None,  # type: ignore[arg-type]
            tfl_id="940GZZLUKSX",
            name="King's Cross St. Pancras",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria", "northern"],
            last_updated=datetime.now(UTC),
        ),
    ]
    mock_fetch_stations.return_value = mock_stations

    # Execute
    response = await async_client_with_auth.get(f"{settings.API_V1_PREFIX}/tfl/stations")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tfl_id"] == "940GZZLUKSX"
    assert data[0]["name"] == "King's Cross St. Pancras"
    assert "victoria" in data[0]["lines"]
    assert "northern" in data[0]["lines"]


@patch("app.services.tfl_service.TfLService.fetch_stations")
async def test_get_stations_filtered_by_line(
    mock_fetch_stations: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test retrieving stations filtered by line."""
    # Setup mock data
    mock_stations = [
        Station(
            id=None,  # type: ignore[arg-type]
            tfl_id="940GZZLUVIC",
            name="Victoria",
            latitude=51.4965,
            longitude=-0.1447,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        ),
    ]
    mock_fetch_stations.return_value = mock_stations

    # Execute
    response = await async_client_with_auth.get(
        f"{settings.API_V1_PREFIX}/tfl/stations",
        params={"line_id": "victoria"},
    )

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tfl_id"] == "940GZZLUVIC"
    assert "victoria" in data[0]["lines"]

    # Verify service was called with line_id
    mock_fetch_stations.assert_called_once()
    call_kwargs = mock_fetch_stations.call_args[1]
    assert call_kwargs.get("line_tfl_id") == "victoria"


# ==================== GET /tfl/disruptions Tests ====================


@patch("app.services.tfl_service.TfLService.fetch_disruptions")
async def test_get_disruptions(
    mock_fetch_disruptions: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test retrieving current disruptions."""
    # Setup mock data
    mock_disruptions = [
        {
            "line_id": "victoria",
            "line_name": "Victoria",
            "status_severity": 5,
            "status_severity_description": "Severe Delays",
            "reason": "Signal failure at Victoria",
            "created_at": datetime.now(UTC).isoformat(),
        },
    ]
    mock_fetch_disruptions.return_value = mock_disruptions

    # Execute
    response = await async_client_with_auth.get(f"{settings.API_V1_PREFIX}/tfl/disruptions")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["line_id"] == "victoria"
    assert data[0]["status_severity"] == 5
    assert "Signal failure" in data[0]["reason"]


# ==================== POST /tfl/validate-route Tests ====================


@patch("app.services.tfl_service.TfLService.validate_route")
async def test_validate_route_success(
    mock_validate_route: AsyncMock,
    async_client_with_auth: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test successful route validation."""
    # Create test data for valid UUIDs
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
    await db_session.commit()

    # Mock validation response
    mock_validate_route.return_value = (True, "Route is valid.", None)

    # Execute
    request_data = {
        "segments": [
            {"station_id": str(station1.id), "line_id": str(line.id)},
            {"station_id": str(station2.id), "line_id": str(line.id)},
        ]
    }
    response = await async_client_with_auth.post(
        f"{settings.API_V1_PREFIX}/tfl/validate-route",
        json=request_data,
    )

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert "valid" in data["message"].lower()
    assert data["invalid_segment_index"] is None


@patch("app.services.tfl_service.TfLService.validate_route")
async def test_validate_route_invalid(
    mock_validate_route: AsyncMock,
    async_client_with_auth: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test route validation with invalid connection."""
    # Create test data
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
    await db_session.commit()

    # Mock validation response
    mock_validate_route.return_value = (False, "No connection found between stations.", 0)

    # Execute
    request_data = {
        "segments": [
            {"station_id": str(station1.id), "line_id": str(line.id)},
            {"station_id": str(station2.id), "line_id": str(line.id)},
        ]
    }
    response = await async_client_with_auth.post(
        f"{settings.API_V1_PREFIX}/tfl/validate-route",
        json=request_data,
    )

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "no connection" in data["message"].lower()
    assert data["invalid_segment_index"] == 0


async def test_validate_route_insufficient_segments(
    async_client_with_auth: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test route validation with too few segments."""
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

    # Execute with only one segment
    request_data = {"segments": [{"station_id": str(station1.id), "line_id": str(line.id)}]}
    response = await async_client_with_auth.post(
        f"{settings.API_V1_PREFIX}/tfl/validate-route",
        json=request_data,
    )

    # Verify validation error
    assert response.status_code == 422  # Validation error


# ==================== POST /admin/tfl/build-graph Tests ====================


@patch("app.services.tfl_service.TfLService.build_station_graph")
async def test_build_graph_success(
    mock_build_graph: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test successful station graph building."""
    # Mock build response
    mock_build_graph.return_value = {
        "lines_count": 11,
        "stations_count": 270,
        "connections_count": 1000,
    }

    # Execute
    response = await async_client_with_auth.post(f"{settings.API_V1_PREFIX}/admin/tfl/build-graph")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["lines_count"] == 11
    assert data["stations_count"] == 270
    assert data["connections_count"] == 1000
    assert "success" in data["message"].lower()


async def test_build_graph_unauthenticated(async_client_with_auth: AsyncClient) -> None:
    """Test that unauthenticated requests to admin endpoint are rejected."""
    # Create client without auth headers
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(f"{settings.API_V1_PREFIX}/admin/tfl/build-graph")

    assert response.status_code == 403


@patch("app.services.tfl_service.TfLService.build_station_graph")
async def test_build_graph_tfl_api_failure(
    mock_build_graph: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test graph building when TfL API fails."""
    # Mock build to raise exception
    mock_build_graph.side_effect = HTTPException(status_code=503, detail="TfL API unavailable")

    # Execute
    response = await async_client_with_auth.post(f"{settings.API_V1_PREFIX}/admin/tfl/build-graph")

    # Verify
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


# ==================== Integration Tests ====================


async def test_full_route_validation_flow(
    async_client_with_auth: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Integration test for full route validation flow."""
    # Create a complete route: st1 -> st2 -> st3
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

    # Create connections
    conn1 = StationConnection(from_station_id=station1.id, to_station_id=station2.id, line_id=line.id)
    conn2 = StationConnection(from_station_id=station2.id, to_station_id=station3.id, line_id=line.id)
    db_session.add_all([conn1, conn2])
    await db_session.commit()

    # Validate route
    request_data = {
        "segments": [
            {"station_id": str(station1.id), "line_id": str(line.id)},
            {"station_id": str(station2.id), "line_id": str(line.id)},
            {"station_id": str(station3.id), "line_id": str(line.id)},
        ]
    }
    response = await async_client_with_auth.post(
        f"{settings.API_V1_PREFIX}/tfl/validate-route",
        json=request_data,
    )

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
