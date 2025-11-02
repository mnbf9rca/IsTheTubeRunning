"""Application configuration."""

from dotenv_vault import load_dotenv

# Load environment variables FIRST - before any other imports or config
# Local: loads .env file
# CI/Production: loads from .env.vault using DOTENV_KEY environment variable
# override=False ensures existing environment variables take precedence (important for tests)
load_dotenv(override=False)

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
    def parse_cors(cls, v: str) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in v.split(",")] if isinstance(v, str) else v

    # Database Settings
    DATABASE_URL: str
    DATABASE_ECHO: bool = False

    # Redis Settings
    REDIS_URL: str

    # Auth0 Settings (for Phase 3)
    AUTH0_DOMAIN: str | None = None
    AUTH0_API_AUDIENCE: str | None = None
    AUTH0_ALGORITHMS: str = "RS256"

    @field_validator("AUTH0_ALGORITHMS", mode="after")
    @classmethod
    def parse_auth0_algorithms(cls, v: str) -> list[str]:
        """Parse comma-separated Auth0 algorithms."""
        return [algo.strip() for algo in v.split(",")] if isinstance(v, str) else v

    # TfL API Settings (for Phase 5)
    TFL_API_KEY: str | None = None

    # Email Settings (for Phase 4)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None

    # Celery Settings (for Phase 8)
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str


settings = Settings()
