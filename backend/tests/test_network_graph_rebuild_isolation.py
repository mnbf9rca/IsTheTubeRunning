"""
Tests for network graph rebuild isolation using soft delete pattern.

These tests verify that the soft delete pattern eliminates the 503 window during
network graph rebuilds (Issue #230). The key scenarios tested are:

1. get_network_graph() correctly filters soft-deleted connections
2. Soft-deleted records are properly marked with deleted_at timestamp
3. _connection_exists() only considers active connections
"""

from datetime import UTC, datetime

import pytest
from app.models.tfl import Line, Station, StationConnection
from app.services.tfl_service import TfLService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Helper Functions


async def create_test_line(db_session: AsyncSession, tfl_id: str = "victoria", name: str = "Victoria") -> Line:
    """Create a test line in the database."""
    line = Line(tfl_id=tfl_id, name=name, mode="tube", last_updated=datetime.now(UTC))
    db_session.add(line)
    await db_session.commit()
    await db_session.refresh(line)
    return line


async def create_test_station(
    db_session: AsyncSession,
    tfl_id: str = "940GZZLUVIC",
    name: str = "Victoria Underground Station",
    latitude: float = 51.4963,
    longitude: float = -0.1441,
) -> Station:
    """Create a test station in the database."""
    station = Station(
        tfl_id=tfl_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
        lines=[],
        last_updated=datetime.now(UTC),
    )
    db_session.add(station)
    await db_session.commit()
    await db_session.refresh(station)
    return station


async def create_test_connection(
    db_session: AsyncSession,
    from_station: Station,
    to_station: Station,
    line: Line,
) -> StationConnection:
    """Create a test station connection in the database."""
    connection = StationConnection(
        from_station_id=from_station.id,
        to_station_id=to_station.id,
        line_id=line.id,
    )
    db_session.add(connection)
    await db_session.commit()
    await db_session.refresh(connection)
    return connection


async def count_active_connections(db_session: AsyncSession) -> int:
    """Count active (non-deleted) station connections."""
    result = await db_session.execute(select(StationConnection).where(StationConnection.deleted_at.is_(None)))
    return len(result.scalars().all())


async def count_deleted_connections(db_session: AsyncSession) -> int:
    """Count soft-deleted station connections."""
    result = await db_session.execute(select(StationConnection).where(StationConnection.deleted_at.isnot(None)))
    return len(result.scalars().all())


async def count_all_connections(db_session: AsyncSession) -> int:
    """Count all station connections (active + deleted)."""
    result = await db_session.execute(select(StationConnection))
    return len(result.scalars().all())


# Test Fixtures


@pytest.fixture
async def setup_initial_graph(db_session: AsyncSession) -> tuple[Line, Station, Station, StationConnection]:
    """Set up an initial graph with one line, two stations, and one connection."""
    line = await create_test_line(db_session, tfl_id="victoria", name="Victoria")
    station1 = await create_test_station(db_session, tfl_id="940GZZLUVIC", name="Victoria")
    station2 = await create_test_station(db_session, tfl_id="940GZZLUGPK", name="Green Park")
    connection = await create_test_connection(db_session, station1, station2, line)

    return line, station1, station2, connection


# Tests


@pytest.mark.asyncio
async def test_get_network_graph_filters_soft_deleted_connections(
    db_session: AsyncSession,
    setup_initial_graph: tuple[Line, Station, Station, StationConnection],
) -> None:
    """Test that get_network_graph() filters out soft-deleted connections."""
    _line, station1, station2, connection = setup_initial_graph

    # Create TfL service
    tfl_service = TfLService(db=db_session)

    # Get network graph - should return the active connection
    graph = await tfl_service.get_network_graph()
    assert station1.tfl_id in graph
    assert len(graph[station1.tfl_id]) == 1
    assert graph[station1.tfl_id][0].station_tfl_id == station2.tfl_id

    # Soft delete the connection
    connection.deleted_at = datetime.now(UTC)
    await db_session.commit()

    # Get network graph again - should raise 503 (no active connections)
    with pytest.raises(HTTPException) as exc_info:
        await tfl_service.get_network_graph()
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_soft_deleted_connections_behavior(
    db_session: AsyncSession,
    setup_initial_graph: tuple[Line, Station, Station, StationConnection],
) -> None:
    """
    Test that soft-deleted connections accumulate and can be queried separately.

    This verifies the database behavior for soft delete - connections are marked
    with deleted_at timestamp but remain in the table.
    """
    line, _station1, station2, initial_connection = setup_initial_graph

    # Verify initial state
    assert await count_active_connections(db_session) == 1
    assert await count_deleted_connections(db_session) == 0

    # Soft delete the connection manually (simulating what build_station_graph does)
    initial_connection.deleted_at = datetime.now(UTC)
    await db_session.commit()

    # Verify soft delete worked
    assert await count_active_connections(db_session) == 0  # No active connections
    assert await count_deleted_connections(db_session) == 1  # One deleted connection
    assert await count_all_connections(db_session) == 1  # Still exists in table

    # Create a new connection with different endpoints (simulating rebuild creating new connections)
    # Note: We use different stations because the partial unique index on (from, to, line)
    # WHERE deleted_at IS NULL allows this (soft-deleted connections excluded from index)
    station3 = await create_test_station(db_session, tfl_id="940GZZLUOXC", name="Oxford Circus")
    await create_test_connection(db_session, station2, station3, line)

    # Verify we now have both old (deleted) and new (active) connections
    assert await count_active_connections(db_session) == 1  # New connection
    assert await count_deleted_connections(db_session) == 1  # Old connection still there
    assert await count_all_connections(db_session) == 2  # Total: 1 active + 1 deleted


@pytest.mark.asyncio
async def test_connection_exists_ignores_soft_deleted(
    db_session: AsyncSession,
    setup_initial_graph: tuple[Line, Station, Station, StationConnection],
) -> None:
    """Test that _connection_exists() only checks active connections."""
    line, station1, station2, connection = setup_initial_graph

    tfl_service = TfLService(db=db_session)

    # Verify connection exists when active
    exists = await tfl_service._connection_exists(station1.id, station2.id, line.id)
    assert exists is True

    # Soft delete the connection
    connection.deleted_at = datetime.now(UTC)
    await db_session.commit()

    # Verify connection does NOT exist after soft delete
    exists = await tfl_service._connection_exists(station1.id, station2.id, line.id)
    assert exists is False


@pytest.mark.asyncio
async def test_new_connections_have_null_deleted_at(
    db_session: AsyncSession,
    setup_initial_graph: tuple[Line, Station, Station, StationConnection],
) -> None:
    """Test that newly created connections have deleted_at=NULL by default."""
    line, _station1, station2, _initial_connection = setup_initial_graph

    # Create a new connection (simulating what build_station_graph does)
    station3 = await create_test_station(db_session, tfl_id="940GZZLUOXC", name="Oxford Circus")
    new_connection = await create_test_connection(db_session, station2, station3, line)

    # Verify the new connection has deleted_at=NULL
    assert new_connection.deleted_at is None

    # Verify we can query it as an active connection
    result = await db_session.execute(select(StationConnection).where(StationConnection.deleted_at.is_(None)))
    active_connections = result.scalars().all()
    assert len(active_connections) == 2  # Initial + new connection
    assert new_connection.id in {conn.id for conn in active_connections}
