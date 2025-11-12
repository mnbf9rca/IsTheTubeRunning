"""Unit tests for TfLService.deduplicate_stations_by_hub() method (Issue #67)."""

import uuid
from datetime import UTC, datetime

import pytest
from app.models.tfl import Station
from app.services.tfl_service import TfLService
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.types import RailwayNetworkFixture


@pytest.fixture
def tfl_service(db_session: AsyncSession) -> TfLService:
    """Create TfLService instance for testing."""
    return TfLService(db_session)


class TestDeduplicateStationsByHub:
    """Tests for deduplicate_stations_by_hub() service method (Issue #67)."""

    def test_deduplicate_stations_by_hub_with_mixed_stations(
        self, tfl_service: TfLService, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should group hub stations and preserve standalone stations."""
        # Hub stations (HUBNORTH)
        rail = test_railway_network.stations["hubnorth-overground"]
        tube = test_railway_network.stations["parallel-north"]
        # Standalone station
        standalone = test_railway_network.stations["via-bank-1"]

        result = tfl_service.deduplicate_stations_by_hub([rail, tube, standalone])

        # Should have 2 stations (1 hub representative + 1 standalone)
        assert len(result) == 2

        # Find hub representative (by tfl_id == hub code)
        hub_rep = next(s for s in result if s.tfl_id == "HUBNORTH")
        assert hub_rep.name == "North Interchange"
        assert set(hub_rep.lines) == {"asymmetricline", "parallelline"}  # Aggregated
        assert hub_rep.hub_naptan_code == "HUBNORTH"
        assert hub_rep.hub_common_name == "North Interchange"

        # Find standalone
        standalone_result = next(s for s in result if s.tfl_id == "via-bank-1")
        assert standalone_result.name == "Via Bank 1"
        assert standalone_result.lines == ["parallelline"]  # Unchanged from input

    def test_deduplicate_stations_by_hub_all_standalone(
        self, tfl_service: TfLService, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should return all stations unchanged when none are in hubs."""
        station1 = test_railway_network.stations["via-bank-1"]
        station2 = test_railway_network.stations["via-charing-1"]

        result = tfl_service.deduplicate_stations_by_hub([station1, station2])

        # Should have both stations (no deduplication occurred)
        assert len(result) == 2
        tfl_ids = {s.tfl_id for s in result}
        assert tfl_ids == {"via-bank-1", "via-charing-1"}

    def test_deduplicate_stations_by_hub_all_hub_stations(
        self, tfl_service: TfLService, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should deduplicate when all stations are in hubs."""
        rail = test_railway_network.stations["hubnorth-overground"]
        tube = test_railway_network.stations["parallel-north"]

        result = tfl_service.deduplicate_stations_by_hub([rail, tube])

        # Should have 1 station (hub representative only)
        assert len(result) == 1
        assert result[0].tfl_id == "HUBNORTH"
        assert result[0].name == "North Interchange"
        assert set(result[0].lines) == {"asymmetricline", "parallelline"}

    def test_deduplicate_stations_by_hub_multiple_hubs(
        self, tfl_service: TfLService, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should correctly group multiple separate hubs."""
        # Hub 1: HUBNORTH
        hub1_station1 = test_railway_network.stations["hubnorth-overground"]
        hub1_station2 = test_railway_network.stations["parallel-north"]
        # Hub 2: HUBCENTRAL
        hub2_station1 = test_railway_network.stations["fork-mid-1"]
        hub2_station2 = test_railway_network.stations["hubcentral-dlr"]

        result = tfl_service.deduplicate_stations_by_hub([hub1_station1, hub1_station2, hub2_station1, hub2_station2])

        # Should have 2 stations (2 hub representatives)
        assert len(result) == 2

        # Find North Hub
        north_hub = next(s for s in result if s.tfl_id == "HUBNORTH")
        assert north_hub.name == "North Interchange"
        assert set(north_hub.lines) == {"asymmetricline", "parallelline"}

        # Find Central Hub
        central_hub = next(s for s in result if s.tfl_id == "HUBCENTRAL")
        assert central_hub.name == "Central Hub"
        assert set(central_hub.lines) == {"forkedline", "2stopline"}

    def test_deduplicate_stations_by_hub_sorting(self, tfl_service: TfLService) -> None:
        """Should return stations sorted alphabetically by name."""
        # Create stations with names that would have different sort order
        zebra = Station(
            id=uuid.uuid4(),
            tfl_id="ZZZ",
            name="Zebra Station",
            latitude=51.5,
            longitude=-0.1,
            lines=["victoria"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code=None,
        )
        apple = Station(
            id=uuid.uuid4(),
            tfl_id="AAA",
            name="Apple Station",
            latitude=51.5,
            longitude=-0.1,
            lines=["northern"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code=None,
        )
        mango = Station(
            id=uuid.uuid4(),
            tfl_id="MMM",
            name="Mango Station",
            latitude=51.5,
            longitude=-0.1,
            lines=["piccadilly"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code=None,
        )

        result = tfl_service.deduplicate_stations_by_hub([zebra, apple, mango])

        # Should be sorted alphabetically by name
        assert len(result) == 3
        assert result[0].name == "Apple Station"
        assert result[1].name == "Mango Station"
        assert result[2].name == "Zebra Station"

    def test_deduplicate_stations_by_hub_empty_list(self, tfl_service: TfLService) -> None:
        """Should handle empty list gracefully."""
        result = tfl_service.deduplicate_stations_by_hub([])

        assert result == []

    def test_deduplicate_stations_by_hub_single_hub_child(
        self, tfl_service: TfLService, test_railway_network: "RailwayNetworkFixture"
    ) -> None:
        """Should still deduplicate hub even if only one child station."""
        station = test_railway_network.stations["parallel-north"]

        result = tfl_service.deduplicate_stations_by_hub([station])

        assert len(result) == 1
        assert result[0].tfl_id == "HUBNORTH"  # Uses hub code even for single child
        assert result[0].name == "North Interchange"
        assert result[0].lines == ["parallelline"]
