"""
Central configuration via environment variables.

pydantic-settings reads from .env automatically.
All defaults work for local Docker Compose — no AWS account needed.

Production swap: change POSTGRES_HOST to RDS endpoint, REDIS_HOST to ElastiCache endpoint.
Zero code changes required.
"""

from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "Data Pipeline API Gateway"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # ── PostgreSQL (local Docker → AWS RDS in production) ────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "pipeline_db"
    postgres_user: str = "pipeline_user"
    postgres_password: str = "pipeline_pass"
    db_pool_size: int = 10
    db_pool_timeout: int = 30

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Redis (local Docker → AWS ElastiCache in production) ─────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    cache_ttl_seconds: int = 300
    cache_ttl_long_seconds: int = 3600

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # ── Pagination ───────────────────────────────────────────────────────────
    default_page_size: int = 50
    max_page_size: int = 1000

    # ── API ──────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
