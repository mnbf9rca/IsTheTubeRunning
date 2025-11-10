"""Integration tests for GET /tfl/stations?deduplicated endpoint (Issue #67)."""

import posixpath
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.tfl import Station
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


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
    async def test_get_stations_deduplicated_false(self, async_client_with_auth: AsyncClient) -> None:
        """Should return all stations including hub children when deduplicated=false (default)."""
        # Mock stations with hub children
        mock_stations = [
            Station(
                id=uuid.uuid4(),
                tfl_id="910GSEVNSIS",
                name="Seven Sisters (Rail)",
                latitude=51.58,
                longitude=-0.07,
                lines=["overground"],
                last_updated=datetime(2025, 1, 1, tzinfo=UTC),
                hub_naptan_code="HUBSVS",
                hub_common_name="Seven Sisters",
            ),
            Station(
                id=uuid.uuid4(),
                tfl_id="940GZZLUSVS",
                name="Seven Sisters",
                latitude=51.58,
                longitude=-0.07,
                lines=["victoria"],
                last_updated=datetime(2025, 1, 2, tzinfo=UTC),
                hub_naptan_code="HUBSVS",
                hub_common_name="Seven Sisters",
            ),
            Station(
                id=uuid.uuid4(),
                tfl_id="940GZZLUOXC",
                name="Oxford Circus",
                latitude=51.52,
                longitude=-0.14,
                lines=["piccadilly", "bakerloo"],
                last_updated=datetime(2025, 1, 3, tzinfo=UTC),
                hub_naptan_code=None,
                hub_common_name=None,
            ),
        ]

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
            assert tfl_ids == {"910GSEVNSIS", "940GZZLUSVS", "940GZZLUOXC"}

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_true(self, async_client_with_auth: AsyncClient) -> None:
        """Should return hub-grouped stations when deduplicated=true."""
        # Mock stations with hub children
        mock_stations = [
            Station(
                id=uuid.uuid4(),
                tfl_id="910GSEVNSIS",
                name="Seven Sisters (Rail)",
                latitude=51.58,
                longitude=-0.07,
                lines=["overground"],
                last_updated=datetime(2025, 1, 1, tzinfo=UTC),
                hub_naptan_code="HUBSVS",
                hub_common_name="Seven Sisters",
            ),
            Station(
                id=uuid.uuid4(),
                tfl_id="940GZZLUSVS",
                name="Seven Sisters",
                latitude=51.58,
                longitude=-0.07,
                lines=["victoria"],
                last_updated=datetime(2025, 1, 2, tzinfo=UTC),
                hub_naptan_code="HUBSVS",
                hub_common_name="Seven Sisters",
            ),
            Station(
                id=uuid.uuid4(),
                tfl_id="940GZZLUOXC",
                name="Oxford Circus",
                latitude=51.52,
                longitude=-0.14,
                lines=["piccadilly", "bakerloo"],
                last_updated=datetime(2025, 1, 3, tzinfo=UTC),
                hub_naptan_code=None,
                hub_common_name=None,
            ),
        ]

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
            hub_station = next(s for s in data if s["tfl_id"] == "HUBSVS")
            assert hub_station["name"] == "Seven Sisters"
            assert hub_station["hub_naptan_code"] == "HUBSVS"
            assert hub_station["hub_common_name"] == "Seven Sisters"
            # Lines should be aggregated and sorted
            assert hub_station["lines"] == ["overground", "victoria"]

            # Find standalone
            standalone = next(s for s in data if s["tfl_id"] == "940GZZLUOXC")
            assert standalone["name"] == "Oxford Circus"
            assert standalone["hub_naptan_code"] is None

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_with_line_filter(self, async_client_with_auth: AsyncClient) -> None:
        """Should fetch all stations, deduplicate, then filter to show hubs with ALL their lines."""
        # Mock ALL stations including hub children on different lines
        mock_stations = [
            # Seven Sisters hub - Tube station on Victoria line
            Station(
                id=uuid.uuid4(),
                tfl_id="940GZZLUSVS",
                name="Seven Sisters",
                latitude=51.58,
                longitude=-0.07,
                lines=["victoria"],
                last_updated=datetime(2025, 1, 2, tzinfo=UTC),
                hub_naptan_code="HUBSVS",
                hub_common_name="Seven Sisters",
            ),
            # Seven Sisters hub - Rail station on Weaver line
            Station(
                id=uuid.uuid4(),
                tfl_id="910GSEVNSIS",
                name="Seven Sisters (Rail)",
                latitude=51.58,
                longitude=-0.07,
                lines=["weaver"],
                last_updated=datetime(2025, 1, 1, tzinfo=UTC),
                hub_naptan_code="HUBSVS",
                hub_common_name="Seven Sisters",
            ),
            # Standalone station on Victoria line
            Station(
                id=uuid.uuid4(),
                tfl_id="940GZZLUOXC",
                name="Oxford Circus",
                latitude=51.52,
                longitude=-0.14,
                lines=["victoria"],
                last_updated=datetime(2025, 1, 3, tzinfo=UTC),
                hub_naptan_code=None,
                hub_common_name=None,
            ),
        ]

        with patch("app.services.tfl_service.TfLService.fetch_stations", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_stations

            # Execute with both line_id and deduplicated
            response = await async_client_with_auth.get(
                build_api_url("/tfl/stations?line_id=victoria&deduplicated=true")
            )

            # Verify
            assert response.status_code == 200
            data = response.json()

            # Should return 2 stations: Seven Sisters hub (serves victoria) + Oxford Circus
            assert len(data) == 2

            # Find Seven Sisters hub in results
            seven_sisters = next(s for s in data if s["tfl_id"] == "HUBSVS")
            # Hub should show ALL lines (victoria + weaver), not just victoria
            assert set(seven_sisters["lines"]) == {"victoria", "weaver"}
            assert seven_sisters["name"] == "Seven Sisters"

            # Find Oxford Circus
            oxford_circus = next(s for s in data if s["tfl_id"] == "940GZZLUOXC")
            assert oxford_circus["lines"] == ["victoria"]

            # Verify fetch_stations was called with line_tfl_id=None (fetch all for deduplication)
            mock_fetch.assert_called_once_with(line_tfl_id=None)

    @pytest.mark.asyncio
    async def test_get_stations_deduplicated_all_standalone(self, async_client_with_auth: AsyncClient) -> None:
        """Should return all stations when none are in hubs."""
        # Mock only standalone stations
        mock_stations = [
            Station(
                id=uuid.uuid4(),
                tfl_id="940GZZLUOXC",
                name="Oxford Circus",
                latitude=51.52,
                longitude=-0.14,
                lines=["piccadilly"],
                last_updated=datetime(2025, 1, 1, tzinfo=UTC),
                hub_naptan_code=None,
            ),
            Station(
                id=uuid.uuid4(),
                tfl_id="940GZZLUPCO",
                name="Piccadilly Circus",
                latitude=51.51,
                longitude=-0.13,
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

            # Should return all 2 stations (no hubs to deduplicate)
            assert len(data) == 2
            tfl_ids = {s["tfl_id"] for s in data}
            assert tfl_ids == {"940GZZLUOXC", "940GZZLUPCO"}

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
