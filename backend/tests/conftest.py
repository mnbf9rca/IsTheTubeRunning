"""Pytest configuration and fixtures."""

import os
import subprocess
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from app.core.utils import convert_async_db_url_to_sync
from app.main import app
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pytest_postgresql import factories
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Configure pytest-postgresql to use our existing Docker PostgreSQL
postgresql_noproc = factories.postgresql_noproc(
    host="localhost",
    port=5432,
    user="postgres",
    password="postgres",
)

# Create a test database for each test
postgresql = factories.postgresql("postgresql_noproc", dbname="test_db")


@pytest.fixture
def client() -> Generator[TestClient]:
    """
    Synchronous test client fixture.

    Yields:
        TestClient: FastAPI test client
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient]:
    """
    Async test client fixture.

    Yields:
        AsyncClient: Async HTTP client
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def mock_settings() -> dict[str, Any]:
    """
    Mock settings for testing.

    Returns:
        dict: Mock settings
    """
    return {
        "DEBUG": True,
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379/15",
    }


@pytest.fixture
async def db_session(postgresql: Any) -> AsyncGenerator[AsyncSession]:  # noqa: ANN401
    """
    Database session fixture for tests.

    Creates a fresh PostgreSQL database for each test, runs migrations,
    and provides an async session.

    Args:
        postgresql: pytest-postgresql fixture providing database connection info

    Yields:
        AsyncSession: Async database session with migrated schema
    """
    # Build async connection string from postgresql info (with password)
    db_url = (
        f"postgresql+asyncpg://postgres:postgres@"
        f"{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )

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
        msg = f"Migration failed: {result.stderr}"
        raise RuntimeError(msg)

    # Create async engine and session
    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()
    # Database is automatically dropped by pytest-postgresql
