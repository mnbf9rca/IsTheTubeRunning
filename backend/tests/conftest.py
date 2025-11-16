"""Pytest configuration and fixtures."""

import os
import tempfile

# Set DEBUG=true for all tests BEFORE any app imports
# This must be done before app.core.config loads settings
os.environ["DEBUG"] = "true"
os.environ["SMS_LOG_DIR"] = tempfile.gettempdir()  # For SMS service tests

import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import quote_plus, urlunparse

import pytest
from alembic import command
from alembic.config import Config
from app.core.auth import clear_jwks_cache, set_mock_jwks
from app.core.config import Settings, settings
from app.core.database import get_db
from app.core.utils import convert_async_db_url_to_sync
from app.main import app
from app.models.admin import AdminRole, AdminUser

# Import for type hints in test factories
from app.models.tfl import Station
from app.models.user import User
from app.services.alert_service import AlertService
from app.utils.admin_helpers import grant_admin
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm.session import SessionTransaction
from sqlalchemy.pool import NullPool

from tests.helpers.jwt_helpers import MockJWTGenerator
from tests.helpers.network_helpers import build_connections_from_routes
from tests.helpers.railway_network import TestRailwayNetwork
from tests.helpers.types import RailwayNetworkFixture


@dataclass
class TestDatabaseContext:
    """
    Structured container for test database resources.

    Contains the async engine, session factory, and database name
    for use across test fixtures.
    """

    engine: Any  # AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    db_name: str


# Database connection configuration for tests
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "postgres"


@pytest.fixture(scope="session")
def db_engine() -> Generator[TestDatabaseContext]:
    """
    Create test database using DatabaseJanitor with transaction-based isolation.

    Runs Alembic migrations once per session using direct command execution.
    DatabaseJanitor manages database lifecycle and cleanup automatically.

    Yields:
        TestDatabaseContext: Structured object containing engine, session factory, and db name
    """
    # Generate unique database name to avoid conflicts
    test_db_name = f"test_{uuid.uuid4().hex[:8]}"

    # DatabaseJanitor handles DB creation and cleanup automatically
    with DatabaseJanitor(
        user=DB_USER,
        host=DB_HOST,
        port=DB_PORT,
        dbname=test_db_name,
        version="18",  # PostgreSQL version
        password=DB_PASSWORD,
    ):
        # Build async connection URL
        user_part = f"{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        host_part = f"{quote_plus(DB_HOST)}:{DB_PORT}"
        netloc = f"{user_part}@{host_part}"
        async_db_url = urlunparse(("postgresql+asyncpg", netloc, f"/{quote_plus(test_db_name)}", "", "", ""))

        # Create async engine with NullPool (ADR 27: prevents event loop issues)
        engine = create_async_engine(async_db_url, echo=False, poolclass=NullPool)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Run Alembic migrations directly (not via subprocess)
        alembic_cfg = Config()
        # Use absolute path to alembic directory
        alembic_dir = Path(__file__).resolve().parent.parent / "alembic"
        alembic_cfg.set_main_option("script_location", str(alembic_dir))

        # Set database URL for Alembic (use sync URL for migrations)
        sync_db_url = convert_async_db_url_to_sync(async_db_url)
        alembic_cfg.set_main_option("sqlalchemy.url", sync_db_url)

        # Suppress Alembic output during tests unless debugging
        if not os.environ.get("ALEMBIC_VERBOSE"):
            alembic_cfg.set_main_option("configure_logger", "false")

        # Run all migrations to create tables
        try:
            command.upgrade(alembic_cfg, "head")
        except Exception as e:
            msg = f"Alembic migration failed: {e}"
            raise RuntimeError(msg) from e

        yield TestDatabaseContext(engine=engine, session_factory=session_factory, db_name=test_db_name)

        # Cleanup handled by DatabaseJanitor context manager


@pytest.fixture
async def db_session(db_engine: TestDatabaseContext) -> AsyncGenerator[AsyncSession]:
    """
    Create isolated database session using nested transactions (SAVEPOINTs).

    Each test runs in a SAVEPOINT that is automatically recreated after each
    commit/rollback, allowing tests to call session.commit() and session.rollback()
    while maintaining isolation. This supports testing IntegrityError and other
    database error scenarios.

    The pattern:
    1. Create connection and start outer transaction
    2. Session bound to that connection
    3. begin_nested() creates initial SAVEPOINT
    4. after_transaction_end listener recreates SAVEPOINT after each release
    5. Test commits/rollbacks only affect the current SAVEPOINT
    6. Earlier committed work remains in the outer transaction
    7. Outer transaction is rolled back after test (cleanup)

    Args:
        db_engine: Session-scoped test database context

    Yields:
        Async SQLAlchemy session with SAVEPOINT isolation
    """
    # Create connection and start outer transaction
    async with db_engine.engine.connect() as connection:
        transaction = await connection.begin()

        # Create a session bound to this connection
        async_session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session_factory() as session:
            # Start initial nested transaction (SAVEPOINT)
            await session.begin_nested()

            # Register listener to recreate SAVEPOINT after each commit/rollback
            @event.listens_for(session.sync_session, "after_transaction_end")
            def _restart_savepoint(sess: Session, trans: SessionTransaction) -> None:
                """Recreate SAVEPOINT after it's released (committed or rolled back)."""
                # Recreate nested transaction if this was a nested transaction
                # and the session is still active (not in the middle of closing)
                if trans.nested and sess.is_active:
                    sess.begin_nested()

            yield session

        # Rollback outer transaction for cleanup
        with suppress(Exception):
            if transaction.is_active:
                await transaction.rollback()


@pytest.fixture
async def fresh_db_session() -> AsyncGenerator[AsyncSession]:
    """
    Fresh database with migrations for each test (IntegrityError recovery tests).

    Creates a new test database per test, runs Alembic migrations, provides a session,
    and cleans up. This allows IntegrityError recovery tests to work correctly because
    commits are REAL database commits to a real database, not just transaction commits.

    Use this fixture only for tests that require IntegrityError recovery (duplicate
    constraint violations). Standard tests should use db_session for better performance.

    Trade-off: ~2s per test vs ~0.1s with db_session, but enables testing critical
    error recovery code paths.

    Yields:
        Async SQLAlchemy session with full migrated schema
    """
    # Generate unique database name
    test_db_name = f"test_{uuid.uuid4().hex[:8]}"

    with DatabaseJanitor(
        user=DB_USER,
        host=DB_HOST,
        port=DB_PORT,
        dbname=test_db_name,
        version="18",
        password=DB_PASSWORD,
    ):
        # Build async connection URL (reuse existing pattern)
        user_part = f"{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        host_part = f"{quote_plus(DB_HOST)}:{DB_PORT}"
        netloc = f"{user_part}@{host_part}"
        async_db_url = urlunparse(("postgresql+asyncpg", netloc, f"/{quote_plus(test_db_name)}", "", "", ""))

        # Run Alembic migrations (same as db_engine fixture)
        alembic_cfg = Config()
        alembic_dir = Path(__file__).resolve().parent.parent / "alembic"
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", convert_async_db_url_to_sync(async_db_url))

        if not os.environ.get("ALEMBIC_VERBOSE"):
            alembic_cfg.set_main_option("configure_logger", "false")

        try:
            command.upgrade(alembic_cfg, "head")
        except Exception as e:
            msg = f"Alembic migration failed: {e}"
            raise RuntimeError(msg) from e

        # Create async engine and session
        engine = create_async_engine(async_db_url, echo=False, poolclass=NullPool)
        async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session_factory() as session:
            yield session

        await engine.dispose()


@pytest.fixture
async def fresh_async_client(fresh_db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """
    Async HTTP client using fresh database session.

    Pairs with fresh_db_session fixture for IntegrityError recovery tests.

    Args:
        fresh_db_session: Fresh database session fixture

    Yields:
        Async HTTP client configured for testing
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield fresh_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client() -> Generator[TestClient]:
    """
    FastAPI synchronous test client for making HTTP requests.

    Yields:
        Synchronous test client with app context
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient]:
    """
    FastAPI asynchronous HTTP client for async endpoint testing.

    Yields:
        Async HTTP client with ASGI transport
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# Auth fixtures


@pytest.fixture
def mock_jwks() -> dict[str, Any]:
    """
    Provide mock JWKS for dependency injection in tests.

    Returns:
        Mock JWKS dictionary with test public keys
    """
    return MockJWTGenerator.get_mock_jwks()


@pytest.fixture(scope="session", autouse=True)
def setup_mock_jwks() -> None:
    """
    Initialize mock JWKS for DEBUG mode JWT verification.

    Automatically runs once per test session to configure RSA key pairs
    for mock JWT signature verification in tests.
    """
    jwks = MockJWTGenerator.get_mock_jwks()
    set_mock_jwks(jwks)


@pytest.fixture
def reset_jwks_cache() -> Generator[None]:
    """
    Reset JWKS cache before and after test.

    This fixture ensures tests start with a clean JWKS cache state
    and cleans up after to prevent test pollution.

    Yields:
        None
    """
    # Reset cache before test
    clear_jwks_cache()
    yield
    # Reset cache after test
    clear_jwks_cache()


@pytest.fixture
def mock_jwt_token() -> str:
    """
    RS256-signed mock JWT token with test user ID.

    Generates a properly signed JWT token using ephemeral RSA keys,
    matching production JWT structure for realistic testing.

    Returns:
        Valid RS256 JWT token string with test claims
    """
    # Use unique ID for this fixture to avoid collisions
    unique_external_id = f"auth0|mock_jwt_{uuid.uuid4().hex[:8]}"
    return MockJWTGenerator.generate(auth0_id=unique_external_id)


@pytest.fixture
def auth_headers(mock_jwt_token: str) -> dict[str, str]:
    """
    HTTP Authorization headers with Bearer token.

    Args:
        mock_jwt_token: RS256-signed JWT token fixture

    Returns:
        Dictionary with Authorization header for authenticated requests
    """
    return {"Authorization": f"Bearer {mock_jwt_token}"}


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """
    Persisted test user with unique external ID.

    Creates a user in the test database with a unique external_id
    to prevent collisions when multiple tests run concurrently or sequentially.

    Args:
        db_session: Isolated database session for this test

    Returns:
        User instance persisted in test database
    """
    # Generate unique external_id to prevent collisions across tests
    unique_external_id = f"auth0|test_user_{uuid.uuid4().hex[:8]}"
    user = User(external_id=unique_external_id, auth_provider="auth0")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def another_user(db_session: AsyncSession) -> User:
    """
    Second persisted test user for multi-user test scenarios.

    Creates another user in the test database with a unique external_id
    for testing cross-user interactions.

    Args:
        db_session: Isolated database session for this test

    Returns:
        User instance persisted in test database
    """
    # Generate unique external_id to prevent collisions
    unique_external_id = f"auth0|another_user_{uuid.uuid4().hex[:8]}"
    user = User(external_id=unique_external_id, auth_provider="auth0")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_for_user(test_user: User) -> dict[str, str]:
    """
    HTTP Authorization headers with Bearer token for the test_user fixture.

    Generates a JWT token that matches the test_user's external_id,
    ensuring authenticated API requests are associated with the correct user.

    Args:
        test_user: Test user fixture

    Returns:
        Dictionary with Authorization header for authenticated requests
    """
    token = MockJWTGenerator.generate(auth0_id=test_user.external_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authenticated_client(auth_headers: dict[str, str]) -> TestClient:
    """
    Synchronous test client pre-configured with authentication.

    Args:
        auth_headers: Authorization Bearer token headers

    Returns:
        TestClient with auth headers applied to all requests
    """
    client = TestClient(app)
    client.headers.update(auth_headers)
    return client


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def alert_service(db_session: AsyncSession, mock_redis: AsyncMock) -> AlertService:
    """Create AlertService instance with mocked Redis."""
    return AlertService(db=db_session, redis_client=mock_redis)


# Admin fixtures


@pytest.fixture
async def admin_user(db_session: AsyncSession, test_user: User) -> tuple[User, AdminUser]:
    """
    Create an admin user for testing admin endpoints.

    This fixture uses the shared admin_helpers.grant_admin() function to maintain
    DRY principles with the CLI tool. For creating admin users in tests, you can
    also use admin_helpers.create_admin_user() directly.

    Note: For local development, use the CLI tool instead:
        uv run python -m app.cli create-admin

    Returns:
        Tuple of (User, AdminUser) for admin-authenticated tests
    """
    admin = await grant_admin(db_session, user_id=test_user.id, role=AdminRole.ADMIN)
    return test_user, admin


# Settings fixture for integration tests


@pytest.fixture
def settings_fixture() -> Settings:
    """
    Provide settings instance for tests.

    Used primarily by integration tests to check for API keys and other configuration.

    Returns:
        Settings instance
    """
    return settings


# Test data factories and shared test railway network
# TestRailwayNetwork and create_test_station are imported at the top of this file


@pytest.fixture
async def test_railway_network(db_session: AsyncSession) -> RailwayNetworkFixture:
    """
    Create and persist complete test railway network to database (function-scoped).

    Builds the full TestRailwayNetwork with all stations, lines, and StationConnection
    graph. This fixture is function-scoped to maintain test isolation - each test gets
    a fresh network instance that is rolled back after the test.

    Network structure:
    - 43 stations (standardized test network)
    - 8 lines across 4 modes (tube, overground, dlr, elizabeth-line)
    - 2 hubs (HUB_NORTH: 4-mode, HUB_CENTRAL: 2-mode)
    - ~72 bidirectional StationConnection records

    Returns:
        Dictionary with structure:
        {
            "stations": dict[tfl_id -> Station],
            "lines": dict[tfl_id -> Line],
            "hubs": dict[hub_code -> list[Station]],
            "connections": list[StationConnection],
            "stats": {stations_count, lines_count, hubs_count, connections_count}
        }
    """
    # 1. Create all stations
    stations_list = [
        # Comprehensive network stations
        TestRailwayNetwork.create_parallel_north(),
        TestRailwayNetwork.create_hubnorth_overground(),
        TestRailwayNetwork.create_hubnorth_elizabeth(),
        TestRailwayNetwork.create_hubnorth_bus(),
        TestRailwayNetwork.create_fork_mid_1(),
        TestRailwayNetwork.create_hubcentral_dlr(),
        TestRailwayNetwork.create_fork_junction(),
        TestRailwayNetwork.create_parallel_split(),
        TestRailwayNetwork.create_parallel_rejoin(),
        TestRailwayNetwork.create_shared_station(),
        TestRailwayNetwork.create_west_fork_2(),
        TestRailwayNetwork.create_west_fork(),
        TestRailwayNetwork.create_east_fork_2(),
        TestRailwayNetwork.create_east_fork(),
        TestRailwayNetwork.create_fork_mid_2(),
        TestRailwayNetwork.create_fork_south_end(),
        TestRailwayNetwork.create_via_bank_1(),
        TestRailwayNetwork.create_via_bank_2(),
        TestRailwayNetwork.create_via_charing_1(),
        TestRailwayNetwork.create_via_charing_2(),
        TestRailwayNetwork.create_parallel_south(),
        TestRailwayNetwork.create_asym_west(),
        TestRailwayNetwork.create_asym_regular_1(),
        TestRailwayNetwork.create_asym_skip_station(),
        TestRailwayNetwork.create_asym_regular_2(),
        TestRailwayNetwork.create_asym_east(),
        TestRailwayNetwork.create_twostop_west(),
        TestRailwayNetwork.create_twostop_east(),
        TestRailwayNetwork.create_shareda_1(),
        TestRailwayNetwork.create_shareda_2(),
        TestRailwayNetwork.create_shareda_4(),
        TestRailwayNetwork.create_shareda_5(),
        TestRailwayNetwork.create_sharedb_1(),
        TestRailwayNetwork.create_sharedb_2(),
        TestRailwayNetwork.create_sharedb_4(),
        TestRailwayNetwork.create_sharedb_5(),
        TestRailwayNetwork.create_sharedc_1(),
        TestRailwayNetwork.create_sharedc_2(),
        TestRailwayNetwork.create_sharedc_4(),
        TestRailwayNetwork.create_sharedc_5(),
        TestRailwayNetwork.create_elizabeth_west(),
        TestRailwayNetwork.create_elizabeth_mid(),
        TestRailwayNetwork.create_elizabeth_east(),
    ]

    # 2. Create all lines
    lines_list = [
        TestRailwayNetwork.create_forkedline(),
        TestRailwayNetwork.create_parallelline(),
        TestRailwayNetwork.create_asymmetricline(),
        TestRailwayNetwork.create_2stopline(),
        TestRailwayNetwork.create_sharedline_a(),
        TestRailwayNetwork.create_sharedline_b(),
        TestRailwayNetwork.create_sharedline_c(),
        TestRailwayNetwork.create_elizabethline(),
    ]

    # 3. Add to session and flush to get IDs
    db_session.add_all(stations_list)
    db_session.add_all(lines_list)
    await db_session.flush()

    # 4. Build station ID mapping (tfl_id -> UUID)
    station_id_map = {station.tfl_id: station.id for station in stations_list}

    # 5. Build StationConnection graph
    all_connections = []
    for line in lines_list:
        connections = build_connections_from_routes(line, station_id_map)
        all_connections.extend(connections)

    # 6. Add connections to session
    db_session.add_all(all_connections)

    # 7. Flush to make data available (will be rolled back after test)
    await db_session.flush()

    # 8. Organize return structure
    stations_dict = {station.tfl_id: station for station in stations_list}
    lines_dict = {line.tfl_id: line for line in lines_list}

    # 9. Group stations by hub
    hubs_dict: dict[str, list[Station]] = {}
    for station in stations_list:
        if station.hub_naptan_code:
            if station.hub_naptan_code not in hubs_dict:
                hubs_dict[station.hub_naptan_code] = []
            hubs_dict[station.hub_naptan_code].append(station)

    # 10. Calculate stats
    stats = {
        "stations_count": len(stations_list),
        "lines_count": len(lines_list),
        "hubs_count": len(hubs_dict),
        "connections_count": len(all_connections),
    }

    return RailwayNetworkFixture(
        stations=stations_dict,
        lines=lines_dict,
        hubs=hubs_dict,
        connections=all_connections,
        stats=stats,
    )
