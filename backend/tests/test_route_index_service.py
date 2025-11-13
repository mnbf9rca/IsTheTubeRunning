"""Tests for RouteIndexService."""

import uuid
from datetime import UTC, datetime

import pytest
from app.models.route import Route, RouteSegment
from app.models.route_index import RouteStationIndex
from app.models.tfl import Line
from app.models.user import User
from app.services.route_index_service import (
    RouteIndexService,
    deduplicate_preserving_order,
    find_stations_between,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.railway_network import TestRailwayNetwork

# =============================================================================
# Pure Function Tests
# =============================================================================


class TestPureFunctions:
    """Tests for pure function helpers."""

    def test_find_stations_between_forward_order(self) -> None:
        """Test finding stations in forward order."""
        stations = ["A", "B", "C", "D", "E"]
        result = find_stations_between(stations, "B", "D")
        assert result == ["B", "C", "D"]

    def test_find_stations_between_reverse_order(self) -> None:
        """Test finding stations in reverse order (should still return forward order)."""
        stations = ["A", "B", "C", "D", "E"]
        result = find_stations_between(stations, "D", "B")
        assert result == ["B", "C", "D"]

    def test_find_stations_between_same_station(self) -> None:
        """Test finding stations when from and to are the same."""
        stations = ["A", "B", "C"]
        result = find_stations_between(stations, "B", "B")
        assert result == ["B"]

    def test_find_stations_between_not_found(self) -> None:
        """Test finding stations when one is not in the list."""
        stations = ["A", "B", "C"]
        result = find_stations_between(stations, "A", "Z")
        assert result is None

    def test_find_stations_between_empty_list(self) -> None:
        """Test finding stations in empty list."""
        result = find_stations_between([], "A", "B")
        assert result is None

    def test_deduplicate_preserving_order(self) -> None:
        """Test deduplicating while preserving order."""
        items = ["A", "B", "A", "C", "B", "D"]
        result = deduplicate_preserving_order(items)
        assert result == ["A", "B", "C", "D"]

    def test_deduplicate_preserving_order_no_duplicates(self) -> None:
        """Test deduplicating list with no duplicates."""
        items = ["A", "B", "C"]
        result = deduplicate_preserving_order(items)
        assert result == ["A", "B", "C"]

    def test_deduplicate_preserving_order_empty(self) -> None:
        """Test deduplicating empty list."""
        result = deduplicate_preserving_order([])
        assert result == []


# =============================================================================
# Service Tests
# =============================================================================


class TestRouteIndexService:
    """Tests for RouteIndexService."""

    @pytest.mark.asyncio
    async def test_build_index_simple_two_stop_line(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test building index for simple two-stop route."""
        # Create test network
        line = TestRailwayNetwork.create_2stopline()
        station1 = TestRailwayNetwork.create_twostop_west()
        station2 = TestRailwayNetwork.create_twostop_east()

        db_session.add_all([line, station1, station2])
        await db_session.flush()

        # Create route with 2 segments
        route = Route(
            user_id=test_user.id,
            name="Test Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        segment1 = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station1.id,
            line_id=line.id,
        )
        segment2 = RouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station2.id,
            line_id=None,  # Destination segment
        )
        db_session.add_all([segment1, segment2])
        await db_session.commit()

        # Build index
        service = RouteIndexService(db_session)
        result = await service.build_route_station_index(route.id)

        # Verify result statistics
        assert result["segments_processed"] == 1
        assert result["entries_created"] == 2  # Both stations on 2stopline

        # Verify index entries were created
        index_result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        index_entries = index_result.scalars().all()

        assert len(index_entries) == 2
        station_naptans = {entry.station_naptan for entry in index_entries}
        assert station_naptans == {
            TestRailwayNetwork.STATION_TWOSTOP_WEST,
            TestRailwayNetwork.STATION_TWOSTOP_EAST,
        }
        # All entries should be for 2stopline
        assert all(entry.line_tfl_id == TestRailwayNetwork.LINE_2STOPLINE for entry in index_entries)

    @pytest.mark.asyncio
    async def test_build_index_parallel_line_multi_variant(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test building index for route on line with multiple variants (Bank/Charing pattern)."""
        # Create test network - parallelline has 4 variants (2 directions x 2 branches)
        line = TestRailwayNetwork.create_parallelline()
        station_north = TestRailwayNetwork.create_parallel_north()
        station_south = TestRailwayNetwork.create_parallel_south()
        station_split = TestRailwayNetwork.create_parallel_split()
        station_rejoin = TestRailwayNetwork.create_parallel_rejoin()
        station_bank1 = TestRailwayNetwork.create_via_bank_1()
        station_bank2 = TestRailwayNetwork.create_via_bank_2()
        station_charing1 = TestRailwayNetwork.create_via_charing_1()
        station_charing2 = TestRailwayNetwork.create_via_charing_2()

        db_session.add_all(
            [
                line,
                station_north,
                station_south,
                station_split,
                station_rejoin,
                station_bank1,
                station_bank2,
                station_charing1,
                station_charing2,
            ]
        )
        await db_session.flush()

        # Create route: parallel-north → parallel-south
        route = Route(
            user_id=test_user.id,
            name="North to South Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        segment1 = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station_north.id,
            line_id=line.id,
        )
        segment2 = RouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station_south.id,
            line_id=None,
        )
        db_session.add_all([segment1, segment2])
        await db_session.commit()

        # Build index
        service = RouteIndexService(db_session)
        result = await service.build_route_station_index(route.id)

        # Verify result statistics
        assert result["segments_processed"] == 1

        # Verify index entries - should include stations from BOTH Bank and Charing branches
        index_result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        index_entries = index_result.scalars().all()

        # Expected stations: north, split, bank1, bank2, rejoin, charing1, charing2, south
        # (Deduplicated from both southbound variants)
        station_naptans = {entry.station_naptan for entry in index_entries}
        expected_stations = {
            TestRailwayNetwork.STATION_PARALLEL_NORTH,
            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
            TestRailwayNetwork.STATION_VIA_BANK_1,
            TestRailwayNetwork.STATION_VIA_BANK_2,
            TestRailwayNetwork.STATION_VIA_CHARING_1,
            TestRailwayNetwork.STATION_VIA_CHARING_2,
            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
        }
        assert station_naptans == expected_stations

        # All entries should be for parallelline
        assert all(entry.line_tfl_id == TestRailwayNetwork.LINE_PARALLELLINE for entry in index_entries)

    @pytest.mark.asyncio
    async def test_build_index_forked_line_y_shaped(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test building index for route on Y-shaped forked line."""
        # Create test network
        line = TestRailwayNetwork.create_forkedline()
        station_west_fork = TestRailwayNetwork.create_west_fork()
        station_junction = TestRailwayNetwork.create_fork_junction()
        station_mid_1 = TestRailwayNetwork.create_fork_mid_1()
        station_south = TestRailwayNetwork.create_fork_south_end()
        station_west_fork_2 = TestRailwayNetwork.create_west_fork_2()

        db_session.add_all(
            [
                line,
                station_west_fork_2,
                station_west_fork,
                station_junction,
                station_mid_1,
                station_south,
            ]
        )
        await db_session.flush()

        # Create route: west-fork → fork-south-end (via junction)
        route = Route(
            user_id=test_user.id,
            name="West Branch Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        segment1 = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station_west_fork.id,
            line_id=line.id,
        )
        segment2 = RouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station_south.id,
            line_id=None,
        )
        db_session.add_all([segment1, segment2])
        await db_session.commit()

        # Build index
        service = RouteIndexService(db_session)
        await service.build_route_station_index(route.id)

        # Verify index entries
        index_result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        index_entries = index_result.scalars().all()

        # Expected: west-fork, fork-junction, fork-mid-1, fork-mid-2, fork-south-end
        station_naptans = {entry.station_naptan for entry in index_entries}
        expected_stations = {
            TestRailwayNetwork.STATION_WEST_FORK,
            TestRailwayNetwork.STATION_FORK_JUNCTION,
            TestRailwayNetwork.STATION_FORK_MID_1,
            TestRailwayNetwork.STATION_FORK_MID_2,
            TestRailwayNetwork.STATION_FORK_SOUTH_END,
        }
        assert station_naptans == expected_stations

    @pytest.mark.asyncio
    async def test_build_index_multi_segment_route(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test building index for route with multiple segments across different lines."""
        # Create test network - use two different lines
        line1 = TestRailwayNetwork.create_2stopline()
        line2 = TestRailwayNetwork.create_sharedline_a()

        station1 = TestRailwayNetwork.create_twostop_west()
        station2 = TestRailwayNetwork.create_twostop_east()
        station3 = TestRailwayNetwork.create_shareda_1()
        station4 = TestRailwayNetwork.create_shareda_2()

        db_session.add_all([line1, line2, station1, station2, station3, station4])
        await db_session.flush()

        # Create route with 4 segments across 2 lines
        route = Route(
            user_id=test_user.id,
            name="Multi-Line Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        segments = [
            RouteSegment(route_id=route.id, sequence=1, station_id=station1.id, line_id=line1.id),
            RouteSegment(route_id=route.id, sequence=2, station_id=station2.id, line_id=None),  # Interchange
            RouteSegment(route_id=route.id, sequence=3, station_id=station3.id, line_id=line2.id),
            RouteSegment(route_id=route.id, sequence=4, station_id=station4.id, line_id=None),  # Destination
        ]
        db_session.add_all(segments)
        await db_session.commit()

        # Build index
        service = RouteIndexService(db_session)
        result = await service.build_route_station_index(route.id)

        # Verify result statistics
        assert result["segments_processed"] == 3  # 4 segments = 3 pairs

        # Verify index entries
        index_result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        index_entries = index_result.scalars().all()

        # Group entries by line
        entries_by_line = {}
        for entry in index_entries:
            if entry.line_tfl_id not in entries_by_line:
                entries_by_line[entry.line_tfl_id] = []
            entries_by_line[entry.line_tfl_id].append(entry.station_naptan)

        # Should have entries for both lines
        assert TestRailwayNetwork.LINE_2STOPLINE in entries_by_line
        assert TestRailwayNetwork.LINE_SHAREDLINE_A in entries_by_line

        # 2stopline entries: twostop-west, twostop-east
        assert set(entries_by_line[TestRailwayNetwork.LINE_2STOPLINE]) == {
            TestRailwayNetwork.STATION_TWOSTOP_WEST,
            TestRailwayNetwork.STATION_TWOSTOP_EAST,
        }

    @pytest.mark.asyncio
    async def test_build_index_route_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test building index for non-existent route raises ValueError."""
        service = RouteIndexService(db_session)
        fake_route_id = uuid.uuid4()

        with pytest.raises(ValueError, match=r"Route .* not found"):
            await service.build_route_station_index(fake_route_id)

    @pytest.mark.asyncio
    async def test_build_index_route_with_insufficient_segments(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test building index for route with < 2 segments returns zero entries."""
        # Create route with only 1 segment
        route = Route(
            user_id=test_user.id,
            name="Single Segment Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        station = TestRailwayNetwork.create_twostop_west()
        line = TestRailwayNetwork.create_2stopline()
        db_session.add_all([station, line])
        await db_session.flush()

        segment = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station.id,
            line_id=line.id,
        )
        db_session.add(segment)
        await db_session.commit()

        # Build index
        service = RouteIndexService(db_session)
        result = await service.build_route_station_index(route.id)

        # Should return zero entries
        assert result["entries_created"] == 0
        assert result["segments_processed"] == 0

        # Verify no index entries created
        index_result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        assert len(index_result.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_build_index_replaces_existing_entries(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that building index deletes old entries before creating new ones."""
        # Create test network
        line = TestRailwayNetwork.create_2stopline()
        station1 = TestRailwayNetwork.create_twostop_west()
        station2 = TestRailwayNetwork.create_twostop_east()

        db_session.add_all([line, station1, station2])
        await db_session.flush()

        # Create route
        route = Route(
            user_id=test_user.id,
            name="Test Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        segment1 = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station1.id,
            line_id=line.id,
        )
        segment2 = RouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station2.id,
            line_id=None,
        )
        db_session.add_all([segment1, segment2])
        await db_session.commit()

        # Build index first time
        service = RouteIndexService(db_session)
        result1 = await service.build_route_station_index(route.id)
        assert result1["entries_created"] == 2

        # Build index again (simulating update)
        result2 = await service.build_route_station_index(route.id)
        assert result2["entries_created"] == 2

        # Verify still only 2 entries (old ones were deleted)
        index_result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        index_entries = index_result.scalars().all()
        assert len(index_entries) == 2

    @pytest.mark.asyncio
    async def test_build_index_line_with_no_routes_data(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test building index for line with no routes data continues processing."""
        # Create line with no routes data
        line = Line(
            tfl_id="testline",
            name="Test Line",
            mode="tube",
            routes=None,  # No routes data
            last_updated=datetime.now(UTC),
        )
        station1 = TestRailwayNetwork.create_twostop_west()
        station2 = TestRailwayNetwork.create_twostop_east()

        db_session.add_all([line, station1, station2])
        await db_session.flush()

        # Create route
        route = Route(
            user_id=test_user.id,
            name="Test Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        segment1 = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station1.id,
            line_id=line.id,
        )
        segment2 = RouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station2.id,
            line_id=None,
        )
        db_session.add_all([segment1, segment2])
        await db_session.commit()

        # Build index - should log warning but not fail
        service = RouteIndexService(db_session)
        result = await service.build_route_station_index(route.id)

        # Should return zero entries (failed to expand)
        assert result["entries_created"] == 0

    @pytest.mark.asyncio
    async def test_build_index_stations_not_found_in_variant(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test building index when stations not found in any route variant."""
        # Create line with routes that don't contain our test stations
        line = TestRailwayNetwork.create_forkedline()  # Has specific stations
        # But use stations from a different line
        station1 = TestRailwayNetwork.create_twostop_west()  # Not on forkedline
        station2 = TestRailwayNetwork.create_twostop_east()  # Not on forkedline

        db_session.add_all([line, station1, station2])
        await db_session.flush()

        # Create route
        route = Route(
            user_id=test_user.id,
            name="Test Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        segment1 = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station1.id,
            line_id=line.id,
        )
        segment2 = RouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station2.id,
            line_id=None,
        )
        db_session.add_all([segment1, segment2])
        await db_session.commit()

        # Build index - should log warning but not fail
        service = RouteIndexService(db_session)
        result = await service.build_route_station_index(route.id)

        # Should return zero entries (failed to expand)
        assert result["entries_created"] == 0

    @pytest.mark.asyncio
    async def test_build_index_transaction_rollback_on_error(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that database transaction is rolled back on error."""
        # Try to build index for non-existent route
        service = RouteIndexService(db_session)
        fake_route_id = uuid.uuid4()

        with pytest.raises(ValueError, match=r"Route .* not found"):
            await service.build_route_station_index(fake_route_id)

        # Session should still be usable after rollback
        result = await db_session.execute(select(Route))
        routes = result.scalars().all()
        assert isinstance(routes, list)  # Session still works

    @pytest.mark.asyncio
    async def test_build_index_stores_line_data_version(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that index entries store line.last_updated as line_data_version."""
        # Create test network
        line = TestRailwayNetwork.create_2stopline()
        station1 = TestRailwayNetwork.create_twostop_west()
        station2 = TestRailwayNetwork.create_twostop_east()

        db_session.add_all([line, station1, station2])
        await db_session.flush()

        # Create route
        route = Route(
            user_id=test_user.id,
            name="Test Route",
            active=True,
        )
        db_session.add(route)
        await db_session.flush()

        segment1 = RouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station1.id,
            line_id=line.id,
        )
        segment2 = RouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station2.id,
            line_id=None,
        )
        db_session.add_all([segment1, segment2])
        await db_session.commit()

        # Build index
        service = RouteIndexService(db_session)
        await service.build_route_station_index(route.id)

        # Verify line_data_version matches line.last_updated
        index_result = await db_session.execute(select(RouteStationIndex).where(RouteStationIndex.route_id == route.id))
        index_entries = index_result.scalars().all()

        assert len(index_entries) > 0
        for entry in index_entries:
            assert entry.line_data_version == line.last_updated
