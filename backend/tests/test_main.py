"""Tests for main API endpoints."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from app import __version__
from app.main import _check_alembic_migrations, lifespan
from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_root_endpoint(client: TestClient) -> None:
    """Test root endpoint returns correct response."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "IsTheTubeRunning API"
    assert data["version"] == __version__


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_readiness_check(client: TestClient) -> None:
    """Test readiness check endpoint - happy path."""
    with (
        patch("app.main.get_engine") as mock_get_engine,
        patch("app.main.redis.from_url") as mock_redis_from_url,
    ):
        # Mock database connection (async)
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        # Properly mock async context manager for begin()
        mock_begin_ctx = AsyncMock()
        mock_begin_ctx.__aenter__.return_value = mock_conn
        mock_begin_ctx.__aexit__.return_value = None

        mock_engine = Mock()
        mock_engine.begin.return_value = mock_begin_ctx
        mock_get_engine.return_value = mock_engine

        # Mock Redis connection (async)
        mock_redis_client = AsyncMock()
        mock_redis_client.ping = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_client

        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_readiness_check_database_failure(async_client: AsyncClient) -> None:
    """Test readiness check returns 503 when database is unavailable."""
    with patch("app.main.get_engine") as mock_get_engine:
        # Mock database connection failure
        mock_engine = Mock()
        mock_engine.begin.side_effect = Exception("Database connection failed")
        mock_get_engine.return_value = mock_engine

        response = await async_client.get("/ready")

        assert response.status_code == 503
        data = response.json()
        # Security: error details are logged but not exposed to clients
        assert data["detail"] == "Service unavailable"


@pytest.mark.asyncio
async def test_readiness_check_redis_failure(async_client: AsyncClient) -> None:
    """Test readiness check returns 503 when Redis is unavailable."""
    with (
        patch("app.main.get_engine") as mock_get_engine,
        patch("app.main.redis.from_url") as mock_redis_from_url,
    ):
        # Mock successful database connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine = Mock()
        mock_engine.begin.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        # Mock Redis connection failure
        mock_redis_client = AsyncMock()
        mock_redis_client.ping.side_effect = Exception("Redis connection failed")
        mock_redis_from_url.return_value = mock_redis_client

        response = await async_client.get("/ready")

        assert response.status_code == 503
        data = response.json()
        # Security: error details are logged but not exposed to clients
        assert data["detail"] == "Service unavailable"


@pytest.mark.asyncio
async def test_readiness_check_verifies_redis_connectivity(async_client: AsyncClient) -> None:
    """Test readiness check actually pings Redis."""
    with (
        patch("app.main.get_engine") as mock_get_engine,
        patch("app.main.redis.from_url") as mock_redis_from_url,
    ):
        # Mock database success
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine = Mock()
        mock_engine.begin.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        # Mock Redis client
        mock_redis_client = AsyncMock()
        mock_redis_ping = AsyncMock()
        mock_redis_client.ping = mock_redis_ping
        mock_redis_from_url.return_value = mock_redis_client

        response = await async_client.get("/ready")

        assert response.status_code == 200
        # Verify ping was called
        mock_redis_ping.assert_called_once()
        # Verify aclose was called in cleanup
        mock_redis_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_readiness_check_closes_redis_on_error(async_client: AsyncClient) -> None:
    """Test readiness check closes Redis client even when ping fails."""
    with (
        patch("app.main.get_engine") as mock_get_engine,
        patch("app.main.redis.from_url") as mock_redis_from_url,
    ):
        # Mock database success
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine = Mock()
        mock_engine.begin.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        # Mock Redis ping failure
        mock_redis_client = AsyncMock()
        mock_redis_client.ping.side_effect = Exception("Redis error")
        mock_redis_aclose = AsyncMock()
        mock_redis_client.aclose = mock_redis_aclose
        mock_redis_from_url.return_value = mock_redis_client

        response = await async_client.get("/ready")

        assert response.status_code == 503
        # Verify aclose was still called despite error
        mock_redis_aclose.assert_called_once()


@pytest.mark.asyncio
async def test_root_endpoint_async(async_client: AsyncClient) -> None:
    """Test root endpoint with async client."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "IsTheTubeRunning API"
    assert data["version"] == __version__


# Tests for _check_alembic_migrations


def test_check_alembic_migrations_no_ini_file() -> None:
    """Test migration check when alembic.ini doesn't exist."""
    mock_conn = Mock()
    mock_context = Mock()
    mock_context.get_current_revision.return_value = "abc123"

    with (
        patch("app.main.migration.MigrationContext.configure", return_value=mock_context),
        patch("app.main.Path") as mock_path,
        patch("app.main.settings") as mock_settings,
    ):
        mock_settings.ALEMBIC_INI_PATH = "alembic.ini"
        mock_path.return_value.exists.return_value = False

        result = _check_alembic_migrations(mock_conn)

        assert result == "abc123"
        mock_context.get_current_revision.assert_called_once()


def test_check_alembic_migrations_db_not_initialized() -> None:
    """Test migration check when database hasn't been initialized."""
    mock_conn = Mock()
    mock_context = Mock()
    mock_context.get_current_revision.return_value = None

    with (
        patch("app.main.migration.MigrationContext.configure", return_value=mock_context),
        patch("app.main.Path") as mock_path,
        patch("app.main.Config"),
        patch("app.main.script.ScriptDirectory.from_config"),
        patch("app.main.settings") as mock_settings,
    ):
        mock_settings.ALEMBIC_INI_PATH = "alembic.ini"
        mock_path.return_value.exists.return_value = True

        with pytest.raises(RuntimeError, match="Database has not been initialized"):
            _check_alembic_migrations(mock_conn)


def test_check_alembic_migrations_needs_migration() -> None:
    """Test migration check when migrations are needed."""
    mock_conn = Mock()
    mock_context = Mock()
    mock_context.get_current_revision.return_value = "old_revision"

    mock_script_dir = Mock()
    mock_script_dir.get_current_head.return_value = "new_revision"

    with (
        patch("app.main.migration.MigrationContext.configure", return_value=mock_context),
        patch("app.main.Path") as mock_path,
        patch("app.main.Config"),
        patch("app.main.script.ScriptDirectory.from_config", return_value=mock_script_dir),
        patch("app.main.settings") as mock_settings,
    ):
        mock_settings.ALEMBIC_INI_PATH = "alembic.ini"
        mock_path.return_value.exists.return_value = True

        with pytest.raises(RuntimeError, match="Database migration required"):
            _check_alembic_migrations(mock_conn)


def test_check_alembic_migrations_up_to_date() -> None:
    """Test migration check when database is up-to-date."""
    mock_conn = Mock()
    mock_context = Mock()
    mock_context.get_current_revision.return_value = "current_revision"

    mock_script_dir = Mock()
    mock_script_dir.get_current_head.return_value = "current_revision"

    with (
        patch("app.main.migration.MigrationContext.configure", return_value=mock_context),
        patch("app.main.Path") as mock_path,
        patch("app.main.Config"),
        patch("app.main.script.ScriptDirectory.from_config", return_value=mock_script_dir),
        patch("app.main.settings") as mock_settings,
    ):
        mock_settings.ALEMBIC_INI_PATH = "alembic.ini"
        mock_path.return_value.exists.return_value = True

        result = _check_alembic_migrations(mock_conn)

        assert result == "current_revision"


# Tests for lifespan


@pytest.mark.asyncio
async def test_lifespan_debug_mode() -> None:
    """Test lifespan skips validation in DEBUG mode."""
    mock_app = Mock()

    with patch("app.main.settings") as mock_settings:
        mock_settings.DEBUG = True
        mock_settings.LOG_LEVEL = "INFO"

        async with lifespan(mock_app):
            # In DEBUG mode, no database checks should happen
            pass


@pytest.mark.asyncio
async def test_lifespan_production_success() -> None:
    """Test lifespan successful startup and shutdown in production mode."""
    mock_app = Mock()

    with (
        patch("app.main.settings") as mock_settings,
        patch("app.main._check_alembic_migrations", return_value="test_revision"),
        patch(
            "app.main.warm_up_metadata_cache",
            return_value={"severity_codes_count": 0, "disruption_categories_count": 0, "stop_types_count": 0},
        ),
    ):
        mock_settings.DEBUG = False
        mock_settings.LOG_LEVEL = "INFO"
        mock_settings.OTEL_ENABLED = False

        # Lifespan should complete without raising exceptions
        async with lifespan(mock_app):
            pass  # Lifespan startup successful


@pytest.mark.asyncio
async def test_lifespan_production_runtime_error() -> None:
    """Test lifespan handles RuntimeError from migration check."""
    mock_app = Mock()

    with (
        patch("app.main.settings") as mock_settings,
        patch("app.main._check_alembic_migrations", side_effect=RuntimeError("Migration failed")),
    ):
        mock_settings.DEBUG = False
        mock_settings.LOG_LEVEL = "INFO"
        mock_settings.OTEL_ENABLED = False

        with pytest.raises(RuntimeError, match="Migration failed"):
            async with lifespan(mock_app):
                pass


@pytest.mark.asyncio
async def test_lifespan_production_os_error() -> None:
    """Test lifespan handles OSError during startup."""
    mock_app = Mock()

    with (
        patch("app.main.settings") as mock_settings,
        patch("app.main._check_alembic_migrations", side_effect=OSError("File error")),
    ):
        mock_settings.DEBUG = False
        mock_settings.LOG_LEVEL = "INFO"
        mock_settings.OTEL_ENABLED = False

        with pytest.raises(OSError, match="File error"):
            async with lifespan(mock_app):
                pass
