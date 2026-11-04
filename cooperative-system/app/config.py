from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (never hard-coded secrets)."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "postgresql+psycopg://cms:cms-local-dev-only@localhost:5432/cms"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
