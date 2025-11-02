"""Pytest configuration and fixtures."""

import os

# Set DEBUG=true for all tests BEFORE any app imports
# This must be done before app.core.config loads settings
os.environ["DEBUG"] = "true"

import subprocess
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any, Protocol
from urllib.parse import quote_plus, urlunparse

import pytest
from app.core.auth import clear_jwks_cache, set_mock_jwks
from app.core.utils import convert_async_db_url_to_sync
from app.main import app
from app.models.user import User
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pytest_postgresql import factories
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.helpers.jwt_helpers import MockJWTGenerator


class PostgreSQLInfo(Protocol):
    """Protocol for PostgreSQL connection info from pytest-postgresql."""

    host: str
    port: int
    dbname: str


class PostgreSQLExecutor(Protocol):
    """Protocol for PostgreSQL executor from pytest-postgresql fixture."""

    info: PostgreSQLInfo


# Database connection configuration for tests
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "postgres"


# Configure pytest-postgresql to use our existing Docker PostgreSQL
postgresql_noproc = factories.postgresql_noproc(  # pyright: ignore[reportUnknownMemberType]
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
)

# Create a test database for each test
postgresql = factories.postgresql("postgresql_noproc", dbname="test_db")


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


@pytest.fixture
async def db_session(postgresql: PostgreSQLExecutor) -> AsyncGenerator[AsyncSession]:
    """
    Isolated PostgreSQL database session for each test.

    Creates a fresh test database, runs Alembic migrations to setup schema,
    provides an async SQLAlchemy session, and cleans up after the test.

    Args:
        postgresql: pytest-postgresql fixture providing database connection

    Yields:
        Async SQLAlchemy session with full migrated schema
    """
    # Build async connection URL using urllib for proper escaping
    # postgresql.info contains: host, port, user, password, dbname
    user_part = f"{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
    host_part = f"{quote_plus(postgresql.info.host)}:{postgresql.info.port}"
    netloc = f"{user_part}@{host_part}"
    db_url = urlunparse(("postgresql+asyncpg", netloc, f"/{quote_plus(postgresql.info.dbname)}", "", "", ""))

    # Run Alembic migrations (convert asyncpg to psycopg2 for sync migrations)
    env = os.environ.copy()
    env["DATABASE_URL"] = convert_async_db_url_to_sync(db_url)

    result = subprocess.run(  # noqa: ASYNC221
        ["uv", "run", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        msg = f"Migration failed: {result.stderr}\nstdout: {result.stdout}"
        raise RuntimeError(msg)

    # Create async engine and session
    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()
    # Database is automatically dropped by pytest-postgresql


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
