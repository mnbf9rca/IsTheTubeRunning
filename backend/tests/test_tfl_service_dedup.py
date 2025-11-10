"""Unit tests for TfLService.deduplicate_stations_by_hub() method (Issue #67)."""

import uuid
from datetime import UTC, datetime

import pytest
from app.models.tfl import Station
from app.services.tfl_service import TfLService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def tfl_service(db_session: AsyncSession) -> TfLService:
    """Create TfLService instance for testing."""
    return TfLService(db_session)


class TestDeduplicateStationsByHub:
    """Tests for deduplicate_stations_by_hub() service method (Issue #67)."""

    def test_deduplicate_stations_by_hub_with_mixed_stations(self, tfl_service: TfLService) -> None:
        """Should group hub stations and preserve standalone stations."""
        # Hub stations (Seven Sisters)
        rail = Station(
            id=uuid.uuid4(),
            tfl_id="910GSEVNSIS",
            name="Seven Sisters (Rail)",
            latitude=51.58,
            longitude=-0.07,
            lines=["overground"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code="HUBSVS",
            hub_common_name="Seven Sisters",
        )
        tube = Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUSVS",
            name="Seven Sisters",
            latitude=51.58,
            longitude=-0.07,
            lines=["victoria"],
            last_updated=datetime(2025, 1, 15, tzinfo=UTC),
            hub_naptan_code="HUBSVS",
            hub_common_name="Seven Sisters",
        )
        # Standalone station
        standalone = Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUOXC",
            name="Oxford Circus",
            latitude=51.52,
            longitude=-0.14,
            lines=["bakerloo", "piccadilly"],  # Keep in sorted order like TfL data
            last_updated=datetime(2025, 1, 10, tzinfo=UTC),
            hub_naptan_code=None,
            hub_common_name=None,
        )

        result = tfl_service.deduplicate_stations_by_hub([rail, tube, standalone])

        # Should have 2 stations (1 hub representative + 1 standalone)
        assert len(result) == 2

        # Find hub representative (by tfl_id == hub code)
        hub_rep = next(s for s in result if s.tfl_id == "HUBSVS")
        assert hub_rep.name == "Seven Sisters"
        assert hub_rep.lines == ["overground", "victoria"]  # Aggregated and sorted
        assert hub_rep.last_updated == datetime(2025, 1, 15, tzinfo=UTC)  # Most recent
        assert hub_rep.hub_naptan_code == "HUBSVS"
        assert hub_rep.hub_common_name == "Seven Sisters"

        # Find standalone
        standalone_result = next(s for s in result if s.tfl_id == "940GZZLUOXC")
        assert standalone_result.name == "Oxford Circus"
        assert standalone_result.lines == ["bakerloo", "piccadilly"]  # Unchanged from input

    def test_deduplicate_stations_by_hub_all_standalone(self, tfl_service: TfLService) -> None:
        """Should return all stations unchanged when none are in hubs."""
        station1 = Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUOXC",
            name="Oxford Circus",
            latitude=51.52,
            longitude=-0.14,
            lines=["piccadilly"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code=None,
        )
        station2 = Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUPCO",
            name="Piccadilly Circus",
            latitude=51.51,
            longitude=-0.13,
            lines=["piccadilly"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code=None,
        )

        result = tfl_service.deduplicate_stations_by_hub([station1, station2])

        # Should have both stations (no deduplication occurred)
        assert len(result) == 2
        tfl_ids = {s.tfl_id for s in result}
        assert tfl_ids == {"940GZZLUOXC", "940GZZLUPCO"}

    def test_deduplicate_stations_by_hub_all_hub_stations(self, tfl_service: TfLService) -> None:
        """Should deduplicate when all stations are in hubs."""
        rail = Station(
            id=uuid.uuid4(),
            tfl_id="910GSEVNSIS",
            name="Seven Sisters (Rail)",
            latitude=51.58,
            longitude=-0.07,
            lines=["overground"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code="HUBSVS",
            hub_common_name="Seven Sisters",
        )
        tube = Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUSVS",
            name="Seven Sisters",
            latitude=51.58,
            longitude=-0.07,
            lines=["victoria"],
            last_updated=datetime(2025, 1, 15, tzinfo=UTC),
            hub_naptan_code="HUBSVS",
            hub_common_name="Seven Sisters",
        )

        result = tfl_service.deduplicate_stations_by_hub([rail, tube])

        # Should have 1 station (hub representative only)
        assert len(result) == 1
        assert result[0].tfl_id == "HUBSVS"
        assert result[0].name == "Seven Sisters"
        assert result[0].lines == ["overground", "victoria"]

    def test_deduplicate_stations_by_hub_multiple_hubs(self, tfl_service: TfLService) -> None:
        """Should correctly group multiple separate hubs."""
        # Hub 1: Seven Sisters
        hub1_station1 = Station(
            id=uuid.uuid4(),
            tfl_id="910GSEVNSIS",
            name="Seven Sisters (Rail)",
            latitude=51.58,
            longitude=-0.07,
            lines=["overground"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code="HUBSVS",
            hub_common_name="Seven Sisters",
        )
        hub1_station2 = Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUSVS",
            name="Seven Sisters",
            latitude=51.58,
            longitude=-0.07,
            lines=["victoria"],
            last_updated=datetime(2025, 1, 2, tzinfo=UTC),
            hub_naptan_code="HUBSVS",
            hub_common_name="Seven Sisters",
        )
        # Hub 2: Canada Water (example - made up for testing)
        hub2_station1 = Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUCWR",
            name="Canada Water",
            latitude=51.49,
            longitude=-0.05,
            lines=["jubilee"],
            last_updated=datetime(2025, 1, 3, tzinfo=UTC),
            hub_naptan_code="HUBCWR",
            hub_common_name="Canada Water",
        )
        hub2_station2 = Station(
            id=uuid.uuid4(),
            tfl_id="910GCNDAW",
            name="Canada Water (Rail)",
            latitude=51.49,
            longitude=-0.05,
            lines=["overground"],
            last_updated=datetime(2025, 1, 4, tzinfo=UTC),
            hub_naptan_code="HUBCWR",
            hub_common_name="Canada Water",
        )

        result = tfl_service.deduplicate_stations_by_hub([hub1_station1, hub1_station2, hub2_station1, hub2_station2])

        # Should have 2 stations (2 hub representatives)
        assert len(result) == 2

        # Find Seven Sisters hub
        seven_sisters = next(s for s in result if s.tfl_id == "HUBSVS")
        assert seven_sisters.name == "Seven Sisters"
        assert seven_sisters.lines == ["overground", "victoria"]
        assert seven_sisters.last_updated == datetime(2025, 1, 2, tzinfo=UTC)  # Most recent

        # Find Canada Water hub
        canada_water = next(s for s in result if s.tfl_id == "HUBCWR")
        assert canada_water.name == "Canada Water"
        assert canada_water.lines == ["jubilee", "overground"]
        assert canada_water.last_updated == datetime(2025, 1, 4, tzinfo=UTC)  # Most recent

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

    def test_deduplicate_stations_by_hub_single_hub_child(self, tfl_service: TfLService) -> None:
        """Should still deduplicate hub even if only one child station."""
        station = Station(
            id=uuid.uuid4(),
            tfl_id="940GZZLUSVS",
            name="Seven Sisters",
            latitude=51.58,
            longitude=-0.07,
            lines=["victoria"],
            last_updated=datetime(2025, 1, 1, tzinfo=UTC),
            hub_naptan_code="HUBSVS",
            hub_common_name="Seven Sisters",
        )

        result = tfl_service.deduplicate_stations_by_hub([station])

        assert len(result) == 1
        assert result[0].tfl_id == "HUBSVS"  # Uses hub code even for single child
        assert result[0].name == "Seven Sisters"
        assert result[0].lines == ["victoria"]
