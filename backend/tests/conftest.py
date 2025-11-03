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
from urllib.parse import quote_plus, urlunparse

import pytest
from alembic import command
from alembic.config import Config
from app.core.auth import clear_jwks_cache, set_mock_jwks
from app.core.utils import convert_async_db_url_to_sync
from app.main import app
from app.models.user import User
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.helpers.jwt_helpers import MockJWTGenerator


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
    Create isolated database session for each test using transaction rollback.

    Uses the session-scoped test database and wraps each test in a transaction
    that is rolled back after the test completes, ensuring test isolation.

    Args:
        db_engine: Session-scoped test database context

    Yields:
        Async SQLAlchemy session with transaction isolation
    """
    # Create a connection and start a transaction
    async with db_engine.engine.connect() as connection:
        # Start a transaction for this test
        transaction = await connection.begin()

        # Create a session bound to this connection
        async with db_engine.session_factory(bind=connection) as session:
            yield session

        # Rollback the transaction after the test (with suppression for safety)
        with suppress(Exception):
            if transaction.is_active:
                await transaction.rollback()

        with suppress(Exception):
            await connection.close()


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
