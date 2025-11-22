"""Application configuration."""

from dotenv_vault import load_dotenv

# Load environment variables FIRST - before any other imports or config
# Local: loads .env file
# CI/Production: loads from .env.vault using DOTENV_KEY environment variable
# override=False ensures existing environment variables take precedence (important for tests)
load_dotenv(override=False)

import logging  # noqa: E402

from pydantic import field_validator  # noqa: E402
from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "IsTheTubeRunning"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str

    @field_validator("ALLOWED_ORIGINS", mode="after")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated CORS origins or pass through list."""
        return v if isinstance(v, list) else [origin.strip() for origin in v.split(",")]

    # Database Settings
    DATABASE_URL: str
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 5  # Connection pool size for worker engine
    DATABASE_MAX_OVERFLOW: int = 10  # Max overflow connections for worker engine

    # Redis Settings
    REDIS_URL: str

    # Auth0 Settings (for Phase 3)
    AUTH0_DOMAIN: str
    AUTH0_API_AUDIENCE: str
    AUTH0_ALGORITHMS: str

    @field_validator("AUTH0_ALGORITHMS", mode="after")
    @classmethod
    def parse_auth0_algorithms(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated Auth0 algorithms or pass through list."""
        return v if isinstance(v, list) else [algo.strip() for algo in v.split(",")]

    # TfL API Settings (for Phase 5)
    TFL_API_KEY: str | None = None

    # Email Settings (for Phase 4)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_TIMEOUT: int = 10  # Connection timeout in seconds (prevents indefinite hangs)
    SMTP_REQUIRE_TLS: bool = False  # If True, require STARTTLS upgrade on ports 25/587

    # SMS Settings (for Phase 4)
    SMS_LOG_DIR: str | None = None  # Directory for SMS stub logging (optional)

    # Celery Settings (for Phase 8)
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Notification Settings (for Phase 7)
    MAX_NOTIFICATION_PREFERENCES_PER_ROUTE: int = 5

    # Alembic Settings
    ALEMBIC_INI_PATH: str = "alembic.ini"

    # OpenTelemetry Settings (for observability)
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "isthetuberunning-backend"
    OTEL_ENVIRONMENT: str = "production"

    # OTLP Exporter Endpoints (separate for traces and logs)
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: str | None = None
    OTEL_EXPORTER_OTLP_LOGS_ENDPOINT: str | None = None
    OTEL_EXPORTER_OTLP_HEADERS: str | None = None
    OTEL_EXPORTER_OTLP_PROTOCOL: str = "http/protobuf"
    OTEL_TRACES_SAMPLER: str = "parentbased_always_on"
    OTEL_TRACES_SAMPLER_ARG: float = 1.0  # 100% sampling
    OTEL_EXCLUDED_URLS: str = "/health,/ready,/metrics"

    # Log level for OTLP log export (NOTSET exports all levels)
    # Valid values: NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL
    OTEL_LOG_LEVEL: str = "NOTSET"

    @field_validator("OTEL_EXCLUDED_URLS", mode="after")
    @classmethod
    def parse_otel_excluded_urls(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated excluded URLs or pass through list, filtering out empty strings."""
        if isinstance(v, list):
            return [url for url in v if url]
        return [url.strip() for url in v.split(",") if url.strip()]

    @field_validator("OTEL_LOG_LEVEL", mode="after")
    @classmethod
    def validate_otel_log_level(cls, v: str) -> str:
        """Validate and normalize OTEL log level."""
        normalized = v.upper()
        valid_levels = logging.getLevelNamesMapping()
        if normalized not in valid_levels:
            msg = f"Invalid OTEL_LOG_LEVEL '{v}'. Must be one of: {', '.join(sorted(valid_levels.keys()))}"
            raise ValueError(msg)
        return normalized

    # Logging Settings
    LOG_LEVEL: str = "INFO"

    @field_validator("LOG_LEVEL", mode="after")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate and normalize log level."""
        normalized = v.upper()
        valid_levels = logging.getLevelNamesMapping()
        if normalized not in valid_levels:
            msg = f"Invalid LOG_LEVEL '{v}'. Must be one of: {', '.join(sorted(valid_levels.keys()))}"
            raise ValueError(msg)
        return normalized


settings = Settings()


def require_config(*field_names: str) -> None:
    """
    Validate that required configuration fields are set.

    This utility should be called by modules on import to verify their
    required configuration is present.

    Args:
        *field_names: Names of required configuration fields

    Raises:
        ValueError: If any required field is missing or None

    Example:
        from app.core.config import require_config, settings
        require_config("AUTH0_DOMAIN", "AUTH0_API_AUDIENCE")
    """
    missing = []
    for field in field_names:
        value = getattr(settings, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)

    if missing:
        msg = f"Required configuration missing: {', '.join(missing)}"
        raise ValueError(msg)
