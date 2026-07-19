from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Tuple

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


Environment = Literal["development", "test", "production"]
AuthMode = Literal["development_headers", "disabled"]


class Settings(BaseSettings):
    """Typed control-plane settings.

    Header-based development identity is intentionally unavailable in production.
    A production deployment must use ``disabled`` until a verified authentication
    adapter is configured; protected routes then fail closed.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENCY_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Environment = "development"
    auth_mode: AuthMode = "development_headers"
    database_url: str = "sqlite+pysqlite:///./agency-control-plane.sqlite3"
    auto_create_schema: bool = True
    cors_origins: Tuple[str, ...] = ("http://localhost:5173",)
    log_level: str = "INFO"
    web_dist: Optional[Path] = None

    @model_validator(mode="after")
    def enforce_environment_boundaries(self) -> "Settings":
        if self.environment == "production":
            if self.auth_mode == "development_headers":
                raise ValueError("development_headers auth is forbidden in production")
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise ValueError("production requires a PostgreSQL database URL")
            if self.auto_create_schema:
                raise ValueError("production schema changes must use Alembic migrations")
        if not self.cors_origins:
            raise ValueError("cors_origins must contain at least one explicit origin")
        if "*" in self.cors_origins:
            raise ValueError("wildcard CORS origins are forbidden")
        return self
