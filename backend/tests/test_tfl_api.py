"""Tests for TfL API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from posixpath import join as urljoin_path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.tfl import Line, Station
from app.models.user import User
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def build_api_url(endpoint: str) -> str:
    """
    Build API URL by joining API prefix with endpoint path using posixpath.

    Properly handles slashes using standard library path joining.

    Args:
        endpoint: API endpoint path (e.g., "/tfl/lines" or "tfl/lines")

    Returns:
        Complete API path (e.g., "/api/v1/tfl/lines")
    """
    return urljoin_path(settings.API_V1_PREFIX, endpoint.lstrip("/"))


@pytest.fixture
async def async_client_with_auth(
    test_user: User,
    auth_headers_for_user: dict[str, str],
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    """Create async client with authentication headers."""

    # Override database dependency to use test database
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=auth_headers_for_user,
        ) as client:
            yield client
    finally:
        # Clean up override
        app.dependency_overrides.clear()


@pytest.fixture
async def async_client_with_admin(
    admin_user: tuple[User, Any],
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    """Create async client with admin authentication headers."""

    # Override database dependency to use test database
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=admin_headers,
        ) as client:
            yield client
    finally:
        # Clean up override
        app.dependency_overrides.clear()


# ==================== GET /tfl/lines Tests ====================


@patch("app.services.tfl_service.TfLService.fetch_lines")
async def test_get_lines_success(
    mock_fetch_lines: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test successful retrieval of tube lines."""
    # Setup mock data with fixed timestamp (no freezegun to avoid async event loop issues)
    fixed_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    mock_lines = [
        Line(
            id=uuid.uuid4(),
            tfl_id="victoria",
            name="Victoria",
            color="#0019A8",
            mode="tube",
            last_updated=fixed_time,
        ),
        Line(
            id=uuid.uuid4(),
            tfl_id="northern",
            name="Northern",
            color="#000000",
            mode="tube",
            last_updated=fixed_time,
        ),
    ]
    mock_fetch_lines.return_value = mock_lines

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/lines"))

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
        response = await client.get(build_api_url("/tfl/lines"))

    assert response.status_code == 403


# ==================== GET /tfl/stations Tests ====================


@patch("app.services.tfl_service.TfLService.fetch_stations")
async def test_get_stations_all(
    mock_fetch_stations: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test retrieving all stations."""
    # Setup mock data with fixed timestamp (no freezegun to avoid async event loop issues)
    fixed_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    mock_stations = [
        Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUKSX",
            name="King's Cross St. Pancras",
            latitude=51.5308,
            longitude=-0.1238,
            lines=["victoria", "northern"],
            last_updated=fixed_time,
        ),
    ]
    mock_fetch_stations.return_value = mock_stations

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/stations"))

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
    # Setup mock data with fixed timestamp (no freezegun to avoid async event loop issues)
    fixed_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    mock_stations = [
        Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUVIC",
            name="Victoria",
            latitude=51.4965,
            longitude=-0.1447,
            lines=["victoria"],
            last_updated=fixed_time,
        ),
    ]
    mock_fetch_stations.return_value = mock_stations

    # Execute
    response = await async_client_with_auth.get(
        build_api_url("/tfl/stations"),
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


@patch("app.services.tfl_service.TfLService.fetch_stations")
async def test_get_stations_with_invalid_line_id(
    mock_fetch_stations: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test retrieving stations with invalid/non-existent line_id."""
    # Mock empty result for invalid line
    mock_fetch_stations.return_value = []

    # Execute with invalid line_id
    response = await async_client_with_auth.get(
        build_api_url("/tfl/stations"),
        params={"line_id": "invalid-line"},
    )

    # Verify - should return 200 with empty list
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0

    # Verify service was called with the invalid line_id
    mock_fetch_stations.assert_called_once()
    call_kwargs = mock_fetch_stations.call_args[1]
    assert call_kwargs.get("line_tfl_id") == "invalid-line"


# ==================== GET /tfl/disruptions Tests ====================


@patch("app.services.tfl_service.TfLService.fetch_line_disruptions")
async def test_get_disruptions(
    mock_fetch_line_disruptions: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test retrieving current line-level disruptions."""
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
    mock_fetch_line_disruptions.return_value = mock_disruptions

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/disruptions"))

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
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", mode="tube", last_updated=datetime.now(UTC))
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
            {"station_tfl_id": station1.tfl_id, "line_tfl_id": line.tfl_id},
            {"station_tfl_id": station2.tfl_id, "line_tfl_id": line.tfl_id},
        ]
    }
    response = await async_client_with_auth.post(
        build_api_url("/tfl/validate-route"),
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
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", mode="tube", last_updated=datetime.now(UTC))
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
            {"station_tfl_id": station1.tfl_id, "line_tfl_id": line.tfl_id},
            {"station_tfl_id": station2.tfl_id, "line_tfl_id": line.tfl_id},
        ]
    }
    response = await async_client_with_auth.post(
        build_api_url("/tfl/validate-route"),
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
    line = Line(tfl_id="victoria", name="Victoria", color="#0019A8", mode="tube", last_updated=datetime.now(UTC))
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
    request_data = {"segments": [{"station_tfl_id": station1.tfl_id, "line_tfl_id": line.tfl_id}]}
    response = await async_client_with_auth.post(
        build_api_url("/tfl/validate-route"),
        json=request_data,
    )

    # Verify validation error
    assert response.status_code == 422  # Validation error


# ==================== POST /admin/tfl/build-graph Tests ====================


@patch("app.services.tfl_service.TfLService.build_station_graph")
async def test_build_graph_success(
    mock_build_graph: AsyncMock,
    async_client_with_admin: AsyncClient,
) -> None:
    """Test successful station graph building with admin user."""
    # Mock build response
    mock_build_graph.return_value = {
        "lines_count": 11,
        "stations_count": 270,
        "connections_count": 1000,
    }

    # Execute
    response = await async_client_with_admin.post(build_api_url("/admin/tfl/build-graph"))

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["lines_count"] == 11
    assert data["stations_count"] == 270
    assert data["connections_count"] == 1000
    assert "success" in data["message"].lower()


async def test_build_graph_unauthenticated(async_client_with_admin: AsyncClient) -> None:
    """Test that unauthenticated requests to admin endpoint are rejected."""
    # Create client without auth headers
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(build_api_url("/admin/tfl/build-graph"))

    assert response.status_code == 403  # FastAPI HTTPBearer returns 403 for missing credentials


async def test_build_graph_non_admin(async_client_with_auth: AsyncClient) -> None:
    """Test that non-admin authenticated users are rejected."""
    response = await async_client_with_auth.post(build_api_url("/admin/tfl/build-graph"))

    assert response.status_code == 403  # Forbidden (not admin)
    assert "admin" in response.json()["detail"].lower()


@patch("app.services.tfl_service.TfLService.build_station_graph")
async def test_build_graph_tfl_api_failure(
    mock_build_graph: AsyncMock,
    async_client_with_admin: AsyncClient,
) -> None:
    """Test graph building when TfL API fails."""
    # Mock build to raise exception
    mock_build_graph.side_effect = HTTPException(status_code=503, detail="TfL API unavailable")

    # Execute
    response = await async_client_with_admin.post(build_api_url("/admin/tfl/build-graph"))

    # Verify
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


@patch("app.services.tfl_service.TfLService.get_network_graph")
async def test_get_network_graph_success(
    mock_get_graph: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test getting the network graph."""
    # Mock successful graph retrieval
    mock_get_graph.return_value = {
        "940GZZLUOXC": [
            {
                "station_id": "abc123",
                "station_tfl_id": "940GZZLUBND",
                "station_name": "Bond Street",
                "line_id": "def456",
                "line_tfl_id": "central",
                "line_name": "Central",
            }
        ]
    }

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/network-graph"))

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert "940GZZLUOXC" in data
    assert len(data["940GZZLUOXC"]) == 1
    assert data["940GZZLUOXC"][0]["station_name"] == "Bond Street"


@patch("app.services.tfl_service.TfLService.get_network_graph")
async def test_get_network_graph_not_built(
    mock_get_graph: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_network_graph when graph not built yet."""
    # Mock graph not built (503 error)
    mock_get_graph.side_effect = HTTPException(
        status_code=503,
        detail="Station graph has not been built yet. Please contact administrator.",
    )

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/network-graph"))

    # Verify
    assert response.status_code == 503
    assert "graph has not been built" in response.json()["detail"].lower()


@patch("app.services.tfl_service.TfLService.get_network_graph")
async def test_get_network_graph_unexpected_error(
    mock_get_graph: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_network_graph when unexpected exception occurs."""
    # Mock unexpected exception (should be caught and return 500)
    mock_get_graph.side_effect = HTTPException(
        status_code=500,
        detail="Failed to fetch network graph.",
    )

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/network-graph"))

    # Verify
    assert response.status_code == 500
    assert "failed" in response.json()["detail"].lower()


# Note: Full integration tests removed per YAGNI principle
# Route validation is thoroughly tested at service layer (5 tests)
# API layer is tested with mocked services above


# ==================== GET /tfl/lines/{line_id}/routes Tests ====================


@patch("app.services.tfl_service.TfLService.get_line_routes")
async def test_get_line_routes_success(
    mock_get_line_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test successful retrieval of line route variants."""
    # Mock successful route retrieval
    mock_get_line_routes.return_value = {
        "line_tfl_id": "victoria",
        "routes": [
            {
                "name": "Walthamstow Central → Brixton",
                "service_type": "Regular",
                "direction": "inbound",
                "stations": ["940GZZLUWAC", "940GZZLUVIC", "940GZZLUBXN"],
            },
            {
                "name": "Brixton → Walthamstow Central",
                "service_type": "Regular",
                "direction": "outbound",
                "stations": ["940GZZLUBXN", "940GZZLUVIC", "940GZZLUWAC"],
            },
        ],
    }

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/lines/victoria/routes"))

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["line_tfl_id"] == "victoria"
    assert len(data["routes"]) == 2
    assert data["routes"][0]["name"] == "Walthamstow Central → Brixton"
    assert data["routes"][0]["direction"] == "inbound"
    assert data["routes"][0]["stations"] == ["940GZZLUWAC", "940GZZLUVIC", "940GZZLUBXN"]
    assert data["routes"][1]["name"] == "Brixton → Walthamstow Central"
    assert data["routes"][1]["direction"] == "outbound"

    # Verify service was called with correct line_id
    mock_get_line_routes.assert_called_once_with("victoria")


@patch("app.services.tfl_service.TfLService.get_line_routes")
async def test_get_line_routes_line_not_found(
    mock_get_line_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_line_routes endpoint when line does not exist."""
    # Mock 404 error
    mock_get_line_routes.side_effect = HTTPException(
        status_code=404,
        detail="Line 'nonexistent' not found.",
    )

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/lines/nonexistent/routes"))

    # Verify
    assert response.status_code == 404
    assert "Line 'nonexistent' not found" in response.json()["detail"]


@patch("app.services.tfl_service.TfLService.get_line_routes")
async def test_get_line_routes_routes_not_built(
    mock_get_line_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_line_routes endpoint when routes haven't been built yet."""
    # Mock 503 error
    mock_get_line_routes.side_effect = HTTPException(
        status_code=503,
        detail="Route data has not been built yet. Please contact administrator.",
    )

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/lines/victoria/routes"))

    # Verify
    assert response.status_code == 503
    assert "Route data has not been built yet" in response.json()["detail"]


@patch("app.services.tfl_service.TfLService.get_line_routes")
async def test_get_line_routes_empty_routes(
    mock_get_line_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_line_routes endpoint when line has no routes."""
    # Mock empty routes
    mock_get_line_routes.return_value = {
        "line_tfl_id": "victoria",
        "routes": [],
    }

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/lines/victoria/routes"))

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["line_tfl_id"] == "victoria"
    assert data["routes"] == []


async def test_get_line_routes_unauthenticated(
    async_client_with_auth: AsyncClient,
) -> None:
    """Test that unauthenticated requests to get_line_routes are rejected."""
    # Create client without auth headers
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(build_api_url("/tfl/lines/victoria/routes"))

    assert response.status_code == 403


@patch("app.services.tfl_service.TfLService.get_line_routes")
async def test_get_line_routes_server_error(
    mock_get_line_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_line_routes endpoint when server error occurs."""
    # Mock 500 error
    mock_get_line_routes.side_effect = HTTPException(
        status_code=500,
        detail="Failed to fetch routes for line 'victoria'.",
    )

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/lines/victoria/routes"))

    # Verify
    assert response.status_code == 500
    assert "Failed to fetch routes" in response.json()["detail"]


# ==================== GET /tfl/stations/{station_tfl_id}/routes Tests ====================


@patch("app.services.tfl_service.TfLService.get_station_routes")
async def test_get_station_routes_success(
    mock_get_station_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test successful retrieval of routes passing through a station."""
    # Mock successful station routes retrieval
    mock_get_station_routes.return_value = {
        "station_tfl_id": "940GZZLUVIC",
        "station_name": "Victoria",
        "routes": [
            {
                "line_tfl_id": "victoria",
                "line_name": "Victoria",
                "route_name": "Walthamstow Central → Brixton",
                "service_type": "Regular",
                "direction": "inbound",
            },
            {
                "line_tfl_id": "district",
                "line_name": "District",
                "route_name": "Upminster → Ealing Broadway",
                "service_type": "Regular",
                "direction": "inbound",
            },
        ],
    }

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/stations/940GZZLUVIC/routes"))

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["station_tfl_id"] == "940GZZLUVIC"
    assert data["station_name"] == "Victoria"
    assert len(data["routes"]) == 2

    # Verify first route
    assert data["routes"][0]["line_tfl_id"] == "victoria"
    assert data["routes"][0]["line_name"] == "Victoria"
    assert data["routes"][0]["route_name"] == "Walthamstow Central → Brixton"
    assert data["routes"][0]["service_type"] == "Regular"
    assert data["routes"][0]["direction"] == "inbound"

    # Verify second route
    assert data["routes"][1]["line_tfl_id"] == "district"
    assert data["routes"][1]["line_name"] == "District"

    # Verify service was called with correct station_tfl_id
    mock_get_station_routes.assert_called_once_with("940GZZLUVIC")


@patch("app.services.tfl_service.TfLService.get_station_routes")
async def test_get_station_routes_station_not_found(
    mock_get_station_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_station_routes endpoint when station does not exist."""
    # Mock 404 error
    mock_get_station_routes.side_effect = HTTPException(
        status_code=404,
        detail="Station '940GZZLUNONEXISTENT' not found.",
    )

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/stations/940GZZLUNONEXISTENT/routes"))

    # Verify
    assert response.status_code == 404
    assert "Station '940GZZLUNONEXISTENT' not found" in response.json()["detail"]


@patch("app.services.tfl_service.TfLService.get_station_routes")
async def test_get_station_routes_routes_not_built(
    mock_get_station_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_station_routes endpoint when routes haven't been built yet."""
    # Mock 503 error
    mock_get_station_routes.side_effect = HTTPException(
        status_code=503,
        detail="Route data has not been built yet. Please contact administrator.",
    )

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/stations/940GZZLUVIC/routes"))

    # Verify
    assert response.status_code == 503
    assert "Route data has not been built yet" in response.json()["detail"]


@patch("app.services.tfl_service.TfLService.get_station_routes")
async def test_get_station_routes_no_lines(
    mock_get_station_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_station_routes endpoint when station has no lines."""
    # Mock empty routes (station exists but no lines)
    mock_get_station_routes.return_value = {
        "station_tfl_id": "940GZZLUVIC",
        "station_name": "Victoria",
        "routes": [],
    }

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/stations/940GZZLUVIC/routes"))

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["station_tfl_id"] == "940GZZLUVIC"
    assert data["station_name"] == "Victoria"
    assert data["routes"] == []


async def test_get_station_routes_unauthenticated(
    async_client_with_auth: AsyncClient,
) -> None:
    """Test that unauthenticated requests to get_station_routes are rejected."""
    # Create client without auth headers
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(build_api_url("/tfl/stations/940GZZLUVIC/routes"))

    assert response.status_code == 403


@patch("app.services.tfl_service.TfLService.get_station_routes")
async def test_get_station_routes_server_error(
    mock_get_station_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_station_routes endpoint when server error occurs."""
    # Mock 500 error
    mock_get_station_routes.side_effect = HTTPException(
        status_code=500,
        detail="Failed to fetch routes for station '940GZZLUVIC'.",
    )

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/stations/940GZZLUVIC/routes"))

    # Verify
    assert response.status_code == 500
    assert "Failed to fetch routes" in response.json()["detail"]


@patch("app.services.tfl_service.TfLService.get_station_routes")
async def test_get_station_routes_multiple_routes_same_line(
    mock_get_station_routes: AsyncMock,
    async_client_with_auth: AsyncClient,
) -> None:
    """Test get_station_routes when station is on multiple route variants of same line."""
    # Mock multiple routes on same line (like Northern line branches)
    mock_get_station_routes.return_value = {
        "station_tfl_id": "940GZZLUCTN",
        "station_name": "Camden Town",
        "routes": [
            {
                "line_tfl_id": "northern",
                "line_name": "Northern",
                "route_name": "Edgware → Morden via Bank",
                "service_type": "Regular",
                "direction": "inbound",
            },
            {
                "line_tfl_id": "northern",
                "line_name": "Northern",
                "route_name": "High Barnet → Morden via Bank",
                "service_type": "Regular",
                "direction": "inbound",
            },
            {
                "line_tfl_id": "northern",
                "line_name": "Northern",
                "route_name": "Morden → Edgware via Bank",
                "service_type": "Regular",
                "direction": "outbound",
            },
        ],
    }

    # Execute
    response = await async_client_with_auth.get(build_api_url("/tfl/stations/940GZZLUCTN/routes"))

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["station_tfl_id"] == "940GZZLUCTN"
    assert data["station_name"] == "Camden Town"
    assert len(data["routes"]) == 3

    # Verify all routes are for Northern line
    assert all(route["line_tfl_id"] == "northern" for route in data["routes"])

    # Verify route names
    route_names = [route["route_name"] for route in data["routes"]]
    assert "Edgware → Morden via Bank" in route_names
    assert "High Barnet → Morden via Bank" in route_names
    assert "Morden → Edgware via Bank" in route_names
