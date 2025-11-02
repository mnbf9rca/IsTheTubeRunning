"""Tests for main API endpoints."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
    """Test readiness check endpoint."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


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

        async with lifespan(mock_app):
            # In DEBUG mode, no database checks should happen
            pass


@pytest.mark.asyncio
async def test_lifespan_production_success() -> None:
    """Test lifespan successful startup and shutdown in production mode."""
    mock_app = Mock()
    mock_conn = AsyncMock()

    # Create a proper async context manager mock
    mock_engine = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_engine.begin = MagicMock(return_value=mock_cm)
    mock_engine.dispose = AsyncMock()

    with (
        patch("app.main.settings") as mock_settings,
        patch("app.main.engine", mock_engine),
        patch("app.main._check_alembic_migrations", return_value="test_revision"),
    ):
        mock_settings.DEBUG = False

        async with lifespan(mock_app):
            mock_conn.execute.assert_called_once()
            mock_conn.run_sync.assert_called_once()

        # Verify shutdown was called
        mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_production_runtime_error() -> None:
    """Test lifespan handles RuntimeError from migration check."""
    mock_app = Mock()
    mock_conn = AsyncMock()
    # Make run_sync raise RuntimeError
    mock_conn.run_sync.side_effect = RuntimeError("Migration failed")

    # Create a proper async context manager mock
    mock_engine = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_engine.begin = MagicMock(return_value=mock_cm)
    mock_engine.dispose = AsyncMock()

    with (
        patch("app.main.settings") as mock_settings,
        patch("app.main.engine", mock_engine),
    ):
        mock_settings.DEBUG = False

        with pytest.raises(RuntimeError, match="Migration failed"):
            async with lifespan(mock_app):
                pass


@pytest.mark.asyncio
async def test_lifespan_production_os_error() -> None:
    """Test lifespan handles OSError during startup."""
    mock_app = Mock()
    mock_conn = AsyncMock()
    # Make run_sync raise OSError
    mock_conn.run_sync.side_effect = OSError("File error")

    # Create a proper async context manager mock
    mock_engine = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_engine.begin = MagicMock(return_value=mock_cm)
    mock_engine.dispose = AsyncMock()

    with (
        patch("app.main.settings") as mock_settings,
        patch("app.main.engine", mock_engine),
    ):
        mock_settings.DEBUG = False

        with pytest.raises(OSError, match="File error"):
            async with lifespan(mock_app):
                pass


@pytest.mark.asyncio
async def test_lifespan_production_database_error() -> None:
    """Test lifespan handles database connection errors."""
    mock_app = Mock()
    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = Exception("Connection failed")

    # Create a proper async context manager mock
    mock_engine = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_engine.begin = MagicMock(return_value=mock_cm)

    with (
        patch("app.main.settings") as mock_settings,
        patch("app.main.engine", mock_engine),
    ):
        mock_settings.DEBUG = False

        with pytest.raises(Exception, match="Connection failed"):
            async with lifespan(mock_app):
                pass
