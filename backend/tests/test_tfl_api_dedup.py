"""Integration tests for GET /tfl/stations?deduplicated endpoint (Issue #67)."""

import posixpath
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.tfl import Station
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from tests.helpers.types import RailwayNetworkFixture


def build_api_url(endpoint: str) -> str:
    """
    Build API URL by joining API prefix with endpoint path using posixpath.

    Properly handles slashes using standard library path joining.

    Args:
        endpoint: API endpoint path (e.g., '/tfl/stations')

    Returns:
        Full API URL with version prefix (e.g., '/api/v1/tfl/stations')
    """
    return posixpath.join(settings.API_V1_PREFIX, endpoint.lstrip("/"))


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


class TestGetStationsDeduplicated:
    """Integration tests for GET /tfl/stations?deduplicated parameter."""

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_false(
        self, async_client_with_auth: AsyncClient, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should return all stations including hub children when deduplicated=false (default)."""
        # Use test network stations
        rail = test_railway_network.stations["hubnorth-overground"]
        tube = test_railway_network.stations["parallel-north"]
        standalone = test_railway_network.stations["via-bank-1"]
        mock_stations = [rail, tube, standalone]

        with patch("app.services.tfl_service.TfLService.fetch_stations", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_stations

            # Execute with deduplicated=false (default)
            response = await async_client_with_auth.get(build_api_url("/tfl/stations"))

            # Verify
            assert response.status_code == 200
            data = response.json()

            # Should return all 3 stations (2 hub children + 1 standalone)
            assert len(data) == 3

            # Verify all original tfl_ids are present
            tfl_ids = {station["tfl_id"] for station in data}
            assert tfl_ids == {"hubnorth-overground", "parallel-north", "via-bank-1"}

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_true(
        self, async_client_with_auth: AsyncClient, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should return hub-grouped stations when deduplicated=true."""
        # Use test network stations
        rail = test_railway_network.stations["hubnorth-overground"]
        tube = test_railway_network.stations["parallel-north"]
        standalone = test_railway_network.stations["via-bank-1"]
        mock_stations = [rail, tube, standalone]

        with patch("app.services.tfl_service.TfLService.fetch_stations", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_stations

            # Execute with deduplicated=true
            response = await async_client_with_auth.get(build_api_url("/tfl/stations?deduplicated=true"))

            # Verify
            assert response.status_code == 200
            data = response.json()

            # Should return 2 stations (1 hub representative + 1 standalone)
            assert len(data) == 2

            # Find hub representative
            hub_station = next(s for s in data if s["tfl_id"] == "HUBNORTH")
            assert hub_station["name"] == "North Interchange"
            assert hub_station["hub_naptan_code"] == "HUBNORTH"
            assert hub_station["hub_common_name"] == "North Interchange"
            # Lines should be aggregated and sorted
            assert hub_station["lines"] == ["asymmetricline", "parallelline"]

            # Find standalone
            standalone_result = next(s for s in data if s["tfl_id"] == "via-bank-1")
            assert standalone_result["name"] == "Via Bank 1"
            assert standalone_result["hub_naptan_code"] is None

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_with_line_filter(
        self, async_client_with_auth: AsyncClient, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should fetch all stations, deduplicate, then filter to show hubs with ALL their lines."""
        # Use test network stations - hub with stations on different lines
        tube = test_railway_network.stations["parallel-north"]  # parallelline
        rail = test_railway_network.stations["hubnorth-overground"]  # asymmetricline
        standalone = test_railway_network.stations["via-bank-1"]  # parallelline
        mock_stations = [tube, rail, standalone]

        with patch("app.services.tfl_service.TfLService.fetch_stations", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_stations

            # Execute with both line_id and deduplicated (filter by parallelline)
            response = await async_client_with_auth.get(
                build_api_url("/tfl/stations?line_id=parallelline&deduplicated=true")
            )

            # Verify
            assert response.status_code == 200
            data = response.json()

            # Should return 2 stations: North Interchange hub (serves parallelline) + Via Bank 1
            assert len(data) == 2

            # Find North Interchange hub in results
            north_hub = next(s for s in data if s["tfl_id"] == "HUBNORTH")
            # Hub should show ALL lines (parallelline + asymmetricline), not just parallelline
            assert set(north_hub["lines"]) == {"parallelline", "asymmetricline"}
            assert north_hub["name"] == "North Interchange"

            # Find Via Bank 1
            via_bank = next(s for s in data if s["tfl_id"] == "via-bank-1")
            assert via_bank["lines"] == ["parallelline"]

            # Verify fetch_stations was called with line_tfl_id=None (fetch all for deduplication)
            mock_fetch.assert_called_once_with(line_tfl_id=None)

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_all_standalone(
        self, async_client_with_auth: AsyncClient, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should return all stations when none are in hubs."""
        # Use test network standalone stations
        station1 = test_railway_network.stations["via-bank-1"]
        station2 = test_railway_network.stations["via-charing-1"]
        mock_stations = [station1, station2]

        with patch("app.services.tfl_service.TfLService.fetch_stations", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_stations

            # Execute with deduplicated=true
            response = await async_client_with_auth.get(build_api_url("/tfl/stations?deduplicated=true"))

            # Verify
            assert response.status_code == 200
            data = response.json()

            # Should return all 2 stations (no hubs to deduplicate)
            assert len(data) == 2
            tfl_ids = {s["tfl_id"] for s in data}
            assert tfl_ids == {"via-bank-1", "via-charing-1"}

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_empty_list(self, async_client_with_auth: AsyncClient) -> None:
        """Should handle empty stations list gracefully."""
        with patch("app.services.tfl_service.TfLService.fetch_stations", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            # Execute with deduplicated=true
            response = await async_client_with_auth.get(build_api_url("/tfl/stations?deduplicated=true"))

            # Verify
            assert response.status_code == 200
            data = response.json()
            assert data == []

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_sorted_alphabetically(self, async_client_with_auth: AsyncClient) -> None:
        """Should return stations sorted alphabetically by name."""
        # Mock stations with unsorted names
        mock_stations = [
            Station(
                id=uuid.uuid4(),
                tfl_id="ZZZ",
                name="Zebra Station",
                latitude=51.5,
                longitude=-0.1,
                lines=["victoria"],
                last_updated=datetime(2025, 1, 1, tzinfo=UTC),
                hub_naptan_code=None,
            ),
            Station(
                id=uuid.uuid4(),
                tfl_id="AAA",
                name="Apple Station",
                latitude=51.5,
                longitude=-0.1,
                lines=["northern"],
                last_updated=datetime(2025, 1, 1, tzinfo=UTC),
                hub_naptan_code=None,
            ),
            Station(
                id=uuid.uuid4(),
                tfl_id="MMM",
                name="Mango Station",
                latitude=51.5,
                longitude=-0.1,
                lines=["piccadilly"],
                last_updated=datetime(2025, 1, 1, tzinfo=UTC),
                hub_naptan_code=None,
            ),
        ]

        with patch("app.services.tfl_service.TfLService.fetch_stations", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_stations

            # Execute with deduplicated=true
            response = await async_client_with_auth.get(build_api_url("/tfl/stations?deduplicated=true"))

            # Verify
            assert response.status_code == 200
            data = response.json()

            # Should be sorted alphabetically
            assert len(data) == 3
            assert data[0]["name"] == "Apple Station"
            assert data[1]["name"] == "Mango Station"
            assert data[2]["name"] == "Zebra Station"
