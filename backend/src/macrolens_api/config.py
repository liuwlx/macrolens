from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"  # noqa: S104 - the API binds inside its deployment boundary
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000/api/v1"
    data_mode: Literal["live", "demo"] = Field(
        default="live",
        validation_alias="MACROLENS_DATA_MODE",
    )

    database_url: str = "postgresql+asyncpg://macrolens:change-me@localhost:5432/macrolens"
    database_url_sync: str = "postgresql+psycopg://macrolens:change-me@localhost:5432/macrolens"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    jwt_secret: str = Field(default="replace-with-at-least-32-random-characters", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14
    cookie_secure: bool = False
    cookie_domain: str | None = None
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    allow_public_registration: bool = False
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "change-me-now"  # noqa: S105 - rejected in production

    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket: str = "macrolens"
    s3_region: str = "auto"
    s3_public_base_url: str | None = None

    fred_api_key: str | None = None
    bea_api_key: str | None = None
    bls_api_key: str | None = None
    eia_api_key: str | None = None
    census_api_key: str | None = None
    dol_claims_url: str | None = None
    federal_reserve_calendar_url: str = (
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    )
    bls_release_calendar_url: str = "https://www.bls.gov/schedule/news_release/bls.ics"

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_deep_research_model: str = "gpt-5.6"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_store: bool = False

    worker_id: str = "worker-local"
    worker_poll_seconds: float = 2.0
    worker_concurrency: int = 4
    worker_job_lock_seconds: int = 900

    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "MacroLens <noreply@example.com>"
    smtp_use_tls: bool = False

    sentry_dsn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @field_validator("web_origin")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_production_safety(self) -> Settings:
        if self.environment != "production":
            return self
        errors: list[str] = []
        if self.data_mode == "demo":
            errors.append("MACROLENS_DATA_MODE=demo is forbidden in production")
        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true")
        if not self.web_origin.startswith("https://"):
            errors.append("WEB_ORIGIN must use https")
        if (
            self.jwt_secret == "replace-with-at-least-32-random-characters"  # noqa: S105
            or len(self.jwt_secret) < 32
        ):
            errors.append("JWT_SECRET must be a unique secret of at least 32 characters")
        if (
            self.bootstrap_admin_password == "change-me-now"  # noqa: S105
            or len(self.bootstrap_admin_password) < 12
        ):
            errors.append(
                "BOOTSTRAP_ADMIN_PASSWORD must be changed and contain at least 12 characters"
            )
        if "change-me" in self.database_url or "change-me" in self.database_url_sync:
            errors.append("database credentials must not use the development defaults")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            errors.append("SameSite=None requires Secure cookies")
        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
