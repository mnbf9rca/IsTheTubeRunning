"""Main FastAPI application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from alembic import script
from alembic.config import Config
from alembic.runtime import migration
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app import __version__
from app.api import admin, auth, contacts, notification_preferences, routes, tfl
from app.core.config import settings
from app.core.database import get_engine
from app.core.logging import configure_logging
from app.core.telemetry import get_tracer_provider, shutdown_tracer_provider
from app.middleware import AccessLoggingMiddleware

# Configure logging at module level so Uvicorn startup logs go through structlog pipeline
configure_logging(log_level=settings.LOG_LEVEL)

logger = structlog.get_logger(__name__)

# OpenTelemetry instrumentors will be initialized after app creation
# TracerProvider is set in lifespan (after fork) for fork-safety


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
        logger.warning("alembic_ini_not_found", path=settings.ALEMBIC_INI_PATH, action="skipping migration validation")
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
    """Application lifespan - initialize OTEL TracerProvider and validate database on startup."""
    # Initialize TracerProvider in lifespan (after fork) so each worker gets its own
    # BatchSpanProcessor with proper threading. Instrumentors were already called at module level.
    if settings.OTEL_ENABLED and (provider := get_tracer_provider()):
        trace.set_tracer_provider(provider)
        logger.info("otel_tracer_provider_initialized")

    # Skip database validation in DEBUG mode (tests use mock databases/contexts)
    if settings.DEBUG:
        logger.info("debug_mode_startup", message="skipping database validation")
        yield
        # Shutdown OTEL if enabled
        if settings.OTEL_ENABLED:
            shutdown_tracer_provider()
        logger.info("shutdown_complete")
        return

    # Production mode: Validate database
    logger.info("startup_initializing", message="validating database")

    try:
        async with get_engine().begin() as conn:
            # Check database connectivity
            await conn.execute(text("SELECT 1"))
            logger.info("database_connection_successful")

            # Check Alembic migration status
            current_rev = await conn.run_sync(_check_alembic_migrations)
            logger.info("database_migration_valid", revision=current_rev)

    except RuntimeError as e:
        logger.error("migration_validation_failed", error=str(e))
        raise
    except OSError as e:
        logger.error("startup_filesystem_error", error=str(e))
        raise
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

    logger.info("startup_complete")

    yield

    # Shutdown
    logger.info("shutdown_starting")
    if settings.OTEL_ENABLED:
        shutdown_tracer_provider()
    await get_engine().dispose()
    logger.info("shutdown_complete")


app = FastAPI(
    title="IsTheTubeRunning API",
    description="TfL Disruption Alert System Backend",
    version=__version__,
    lifespan=lifespan,
)

# Initialize OpenTelemetry FastAPI instrumentation (must be after app creation)
# Instrumentor wraps the ASGI application to create HTTP request spans
# TracerProvider is set later in lifespan (after fork) for fork-safety
if settings.OTEL_ENABLED:
    FastAPIInstrumentor().instrument_app(
        app,
        excluded_urls=",".join(settings.OTEL_EXCLUDED_URLS),
    )
    logger.info("otel_fastapi_instrumented", excluded_urls=settings.OTEL_EXCLUDED_URLS)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Access logging middleware (replaces uvicorn.access logs with structlog)
app.add_middleware(AccessLoggingMiddleware)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(contacts.router, prefix=settings.API_V1_PREFIX)
app.include_router(routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(notification_preferences.router, prefix=settings.API_V1_PREFIX)
app.include_router(tfl.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)


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
