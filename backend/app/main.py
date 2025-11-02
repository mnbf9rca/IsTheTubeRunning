"""Main FastAPI application."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import script
from alembic.config import Config
from alembic.runtime import migration
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app import __version__
from app.api import auth, contacts
from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger(__name__)


def _check_alembic_migrations(sync_conn: Connection) -> str | None:
    """
    Validate that the database is at the expected Alembic revision.

    Args:
        sync_conn: Synchronous SQLAlchemy connection

    Returns:
        Current revision ID, or None if validation skipped

    Raises:
        RuntimeError: If database is not initialized or migrations are needed
    """

    # Get current database revision
    context = migration.MigrationContext.configure(sync_conn)
    current_rev = context.get_current_revision()

    # Check if alembic.ini exists at configured path
    alembic_ini_path = Path(settings.ALEMBIC_INI_PATH)
    if not alembic_ini_path.exists():
        logger.warning(f"alembic.ini not found at {settings.ALEMBIC_INI_PATH} - skipping migration validation")
        return current_rev

    # Get expected HEAD revision from migration files
    alembic_cfg = Config(str(alembic_ini_path))
    script_dir = script.ScriptDirectory.from_config(alembic_cfg)
    head_rev = script_dir.get_current_head()

    if current_rev is None:
        msg = "Database has not been initialized! Please run: alembic upgrade head"
        raise RuntimeError(msg)
    if current_rev != head_rev:
        msg = (
            f"Database migration required!\n"
            f"  Current revision: {current_rev}\n"
            f"  Expected revision: {head_rev}\n"
            f"Please run: alembic upgrade head"
        )
        raise RuntimeError(msg)

    return current_rev


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan - validate database migrations on startup."""
    # Skip all validation in DEBUG mode (tests use mock databases/contexts)
    if settings.DEBUG:
        logger.info("✓ DEBUG mode - skipping startup validation")
        yield
        logger.info("✓ Shutdown complete")
        return

    # Production mode: validate database connectivity and migrations
    logger.info("Starting up: Validating database...")

    try:
        async with engine.begin() as conn:
            # Check database connectivity
            await conn.execute(text("SELECT 1"))
            logger.info("✓ Database connection successful")

            # Check Alembic migration status
            current_rev = await conn.run_sync(_check_alembic_migrations)
            logger.info(f"✓ Database at correct revision: {current_rev}")

    except RuntimeError as e:
        logger.error(f"✗ Migration validation failed: {e}")
        raise
    except OSError as e:
        logger.error(f"✗ File system error during startup: {e}")
        raise
    except Exception as e:
        logger.error(f"✗ Database connection or startup failed: {e}")
        raise

    logger.info("✓ Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await engine.dispose()
    logger.info("✓ Shutdown complete")


app = FastAPI(
    title="IsTheTubeRunning API",
    description="TfL Disruption Alert System Backend",
    version=__version__,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(contacts.router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "IsTheTubeRunning API", "version": __version__}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check endpoint - verify dependencies."""
    # TODO: Add actual dependency checks (database, redis, etc.)
    return {"status": "ready"}
