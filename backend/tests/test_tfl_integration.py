"""Integration tests for TfL API service - calls real TfL API."""

import pytest
from app.core.config import Settings
from app.models.tfl import (
    DisruptionCategory,
    Line,
    SeverityCode,
    Station,
    StationConnection,
    StationDisruption,
    StopType,
)
from app.services.tfl_service import TfLService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
async def test_integration_fetch_lines(db_session: AsyncSession, settings_fixture: Settings) -> None:
    """Integration test: fetch real tube lines from TfL API."""
    if not settings_fixture.TFL_API_KEY:
        pytest.skip("TFL_API_KEY not set - skipping integration test")

    service = TfLService(db_session)

    # Call real API (use_cache=False to ensure fresh data)
    lines = await service.fetch_lines(use_cache=False)

    # Basic assertions - verify structure and data exists
    assert len(lines) > 0, "Should fetch at least one tube line"
    assert all(hasattr(line, "tfl_id") for line in lines), "All lines should have tfl_id"
    assert all(hasattr(line, "name") for line in lines), "All lines should have name"
    assert all(line.tfl_id for line in lines), "All lines should have non-empty tfl_id"
    assert all(line.name for line in lines), "All lines should have non-empty name"

    # Verify database persistence
    result = await db_session.execute(select(Line))
    db_lines = result.scalars().all()
    assert len(db_lines) > 0, "Lines should be persisted to database"
    assert len(db_lines) == len(lines), "All fetched lines should be in database"


@pytest.mark.integration
async def test_integration_fetch_stations(db_session: AsyncSession, settings_fixture: Settings) -> None:
    """Integration test: fetch real stations for a tube line from TfL API."""
    if not settings_fixture.TFL_API_KEY:
        pytest.skip("TFL_API_KEY not set - skipping integration test")

    service = TfLService(db_session)

    # First fetch lines to get a valid line ID
    lines = await service.fetch_lines(use_cache=False)
    assert len(lines) > 0, "Should have at least one line to test with"

    # Use the first line for testing (e.g., "victoria")
    test_line = lines[0]

    # Call real API to fetch stations for this line
    stations = await service.fetch_stations(
        line_tfl_id=test_line.tfl_id, use_cache=False, skip_database_validation=True
    )

    # Basic assertions
    assert len(stations) > 0, f"Should fetch at least one station for {test_line.name} line"
    assert all(hasattr(station, "tfl_id") for station in stations), "All stations should have tfl_id"
    assert all(hasattr(station, "name") for station in stations), "All stations should have name"
    assert all(hasattr(station, "latitude") for station in stations), "All stations should have latitude"
    assert all(hasattr(station, "longitude") for station in stations), "All stations should have longitude"
    assert all(test_line.tfl_id in station.lines for station in stations), "All stations should include the line"

    # Verify database persistence
    result = await db_session.execute(select(Station).where(Station.tfl_id == stations[0].tfl_id))
    db_station = result.scalar_one_or_none()
    assert db_station is not None, "Stations should be persisted to database"


@pytest.mark.integration
async def test_integration_fetch_severity_codes(db_session: AsyncSession, settings_fixture: Settings) -> None:
    """Integration test: fetch real severity codes from TfL API."""
    if not settings_fixture.TFL_API_KEY:
        pytest.skip("TFL_API_KEY not set - skipping integration test")

    service = TfLService(db_session)

    # Call real API
    codes = await service.fetch_severity_codes(use_cache=False)

    # Basic assertions
    assert len(codes) > 0, "Should fetch at least one severity code"
    assert all(hasattr(code, "severity_level") for code in codes), "All codes should have severity_level"
    assert all(hasattr(code, "description") for code in codes), "All codes should have description"
    assert all(isinstance(code.severity_level, int) for code in codes), "severity_level should be int"
    assert all(code.description for code in codes), "All codes should have non-empty description"

    # Verify database persistence
    result = await db_session.execute(select(SeverityCode))
    db_codes = result.scalars().all()
    assert len(db_codes) > 0, "Severity codes should be persisted to database"
    assert len(db_codes) == len(codes), "All fetched codes should be in database"


@pytest.mark.integration
async def test_integration_fetch_disruption_categories(db_session: AsyncSession, settings_fixture: Settings) -> None:
    """Integration test: fetch real disruption categories from TfL API."""
    if not settings_fixture.TFL_API_KEY:
        pytest.skip("TFL_API_KEY not set - skipping integration test")

    service = TfLService(db_session)

    # Call real API
    categories = await service.fetch_disruption_categories(use_cache=False)

    # Basic assertions
    assert len(categories) > 0, "Should fetch at least one disruption category"
    assert all(hasattr(category, "category_name") for category in categories), (
        "All categories should have category_name"
    )
    assert all(category.category_name for category in categories), "All categories should have non-empty category_name"

    # Verify database persistence
    result = await db_session.execute(select(DisruptionCategory))
    db_categories = result.scalars().all()
    assert len(db_categories) > 0, "Disruption categories should be persisted to database"
    assert len(db_categories) == len(categories), "All fetched categories should be in database"


@pytest.mark.integration
async def test_integration_fetch_stop_types(db_session: AsyncSession, settings_fixture: Settings) -> None:
    """Integration test: fetch real stop types from TfL API."""
    if not settings_fixture.TFL_API_KEY:
        pytest.skip("TFL_API_KEY not set - skipping integration test")

    service = TfLService(db_session)

    # Call real API
    types = await service.fetch_stop_types(use_cache=False)

    # Basic assertions - note: we filter to relevant types only
    assert len(types) > 0, "Should fetch at least one stop type"
    assert all(hasattr(stop_type, "type_name") for stop_type in types), "All types should have type_name"
    assert all(stop_type.type_name for stop_type in types), "All types should have non-empty type_name"

    # Verify we only get relevant types (as defined in service)
    relevant_types = {"NaptanMetroStation", "NaptanRailStation", "NaptanBusCoachStation"}
    for stop_type in types:
        assert stop_type.type_name in relevant_types, f"Should only return relevant types, got {stop_type.type_name}"

    # Verify database persistence
    result = await db_session.execute(select(StopType))
    db_types = result.scalars().all()
    assert len(db_types) > 0, "Stop types should be persisted to database"
    assert len(db_types) == len(types), "All fetched types should be in database"


@pytest.mark.integration
async def test_integration_fetch_line_disruptions(db_session: AsyncSession, settings_fixture: Settings) -> None:
    """Integration test: fetch real line-level disruptions from TfL API."""
    if not settings_fixture.TFL_API_KEY:
        pytest.skip("TFL_API_KEY not set - skipping integration test")

    service = TfLService(db_session)

    # Call real API
    disruptions = await service.fetch_line_disruptions(use_cache=False)

    # Note: disruptions may be empty if there are no current disruptions - this is expected
    # Just verify the call succeeds and returns the expected structure
    assert isinstance(disruptions, list), "Should return a list of disruptions"

    if len(disruptions) > 0:
        # If there are disruptions, verify their structure
        assert all(hasattr(d, "line_id") for d in disruptions), "All disruptions should have line_id"
        assert all(hasattr(d, "line_name") for d in disruptions), "All disruptions should have line_name"
        assert all(hasattr(d, "status_severity_description") for d in disruptions), (
            "All disruptions should have status_severity_description"
        )


@pytest.mark.integration
async def test_integration_fetch_station_disruptions(db_session: AsyncSession, settings_fixture: Settings) -> None:
    """Integration test: fetch real station-level disruptions from TfL API."""
    if not settings_fixture.TFL_API_KEY:
        pytest.skip("TFL_API_KEY not set - skipping integration test")

    service = TfLService(db_session)

    # First, we need to populate stations so the service can match disruptions to them
    lines = await service.fetch_lines(use_cache=False)
    if len(lines) > 0:
        # Fetch stations for at least one line to populate the database
        await service.fetch_stations(line_tfl_id=lines[0].tfl_id, use_cache=False, skip_database_validation=True)

    # Call real API
    disruptions = await service.fetch_station_disruptions(use_cache=False)

    # Note: disruptions may be empty if there are no current station disruptions - this is expected
    # Just verify the call succeeds and returns the expected structure
    assert isinstance(disruptions, list), "Should return a list of station disruptions"

    # Verify database persistence (should be cleared and repopulated)
    result = await db_session.execute(select(StationDisruption))
    db_disruptions = result.scalars().all()
    assert len(db_disruptions) == len(disruptions), "Database should match API response"

    if len(disruptions) > 0:
        # If there are disruptions, verify their structure
        assert all(hasattr(d, "station_id") for d in disruptions), "All disruptions should have station_id"
        assert all(hasattr(d, "station_tfl_id") for d in disruptions), "All disruptions should have station_tfl_id"
        assert all(hasattr(d, "station_name") for d in disruptions), "All disruptions should have station_name"
        assert all(hasattr(d, "description") for d in disruptions), "All disruptions should have description"


@pytest.mark.integration
async def test_integration_build_station_graph(db_session: AsyncSession, settings_fixture: Settings) -> None:
    """Integration test: build real station connection graph from TfL API.

    Note: This test may take longer as it fetches route sequences for all lines
    and populates stations first.
    """
    if not settings_fixture.TFL_API_KEY:
        pytest.skip("TFL_API_KEY not set - skipping integration test")

    service = TfLService(db_session)

    # First, fetch lines and populate stations for each line
    # This is required because build_station_graph needs stations in the database
    # lines = await service.fetch_lines(use_cache=False)
    # for line in lines[:3]:  # Only fetch stations for first 3 lines to keep test fast
    #     await service.fetch_stations(line_tfl_id=line.tfl_id, use_cache=False)

    # Now call build_station_graph - this builds connections from route sequences
    result = await service.build_station_graph()

    # Basic assertions on the result
    assert "lines_count" in result, "Result should include lines_count"
    assert "stations_count" in result, "Result should include stations_count"
    assert "connections_count" in result, "Result should include connections_count"

    assert result["lines_count"] > 0, "Should process at least one line"
    assert result["stations_count"] > 0, "Should find at least one station"
    assert result["connections_count"] > 0, "Should create at least one connection"

    # Verify database has connections
    db_result = await db_session.execute(select(StationConnection))
    db_connections = db_result.scalars().all()
    assert len(db_connections) > 0, "Connections should be persisted to database"
    assert len(db_connections) == result["connections_count"], "Connection count should match"

    # Verify connections have proper structure
    sample_connection = db_connections[0]
    assert hasattr(sample_connection, "from_station_id"), "Connection should have from_station_id"
    assert hasattr(sample_connection, "to_station_id"), "Connection should have to_station_id"
    assert hasattr(sample_connection, "line_id"), "Connection should have line_id"
