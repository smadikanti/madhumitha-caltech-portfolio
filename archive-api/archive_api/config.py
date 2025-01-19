"""Application configuration via environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings are overridable with ARCHIVE_ prefixed env vars."""

    model_config = {"env_prefix": "ARCHIVE_"}

    database_url: str = Field(
        default="postgresql+asyncpg://archive:archive@localhost:5432/exoplanets",
    )
    debug: bool = False
    log_level: str = "INFO"
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    app_name: str = "NASA Exoplanet Archive API"
    app_version: str = "1.0.0"


settings = Settings()
