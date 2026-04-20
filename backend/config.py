from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)


def _split_csv(raw_value: str) -> List[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    debug: bool
    secret_key: str
    api_host: str
    api_port: int
    cors_origins: List[str]
    storage_backend: str
    storage_path: Path
    auth_enabled: bool
    default_admin_key: Optional[str]
    bootstrap_admin_token: Optional[str]
    postgres_dsn: Optional[str]
    postgres_host: str
    postgres_port: int
    postgres_database: str
    postgres_user: str
    postgres_password: str
    postgres_ssl_mode: Optional[str]
    postgres_pool_size: int
    postgres_max_overflow: int
    postgres_echo: bool
    azure_openai_api_key: Optional[str]
    azure_openai_endpoint: Optional[str]
    azure_openai_deployment: Optional[str]
    azure_openai_api_version: str
    request_timeout_seconds: float
    max_tokens: int

    @classmethod
    def from_env(cls) -> "Settings":
        storage_path = Path(
            os.getenv("APP_STORAGE_PATH", str(ROOT_DIR / "backend" / "data" / "executions.json"))
        ).expanduser()
        raw_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:4173",
        )
        return cls(
            app_name=os.getenv("APP_NAME", "Actypity Backend"),
            app_version=os.getenv("APP_VERSION", "2.0.0"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            secret_key=os.getenv("SECRET_KEY", "change-me-in-production"),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            cors_origins=_split_csv(raw_origins),
            storage_backend=os.getenv("APP_STORAGE_BACKEND", "postgres").lower(),
            storage_path=storage_path,
            auth_enabled=os.getenv("AUTH_ENABLED", "true").lower() == "true",
            default_admin_key=os.getenv("DEFAULT_ADMIN_KEY"),
            bootstrap_admin_token=os.getenv("BOOTSTRAP_ADMIN_TOKEN") or os.getenv("SECRET_KEY"),
            postgres_dsn=os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN"),
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_database=os.getenv("POSTGRES_DATABASE", "actypity"),
            postgres_user=os.getenv("POSTGRES_USER", "postgres"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            postgres_ssl_mode=os.getenv("POSTGRES_SSLMODE"),
            postgres_pool_size=int(os.getenv("POSTGRES_POOL_SIZE", "5")),
            postgres_max_overflow=int(os.getenv("POSTGRES_MAX_OVERFLOW", "10")),
            postgres_echo=os.getenv("POSTGRES_ECHO", "false").lower() == "true",
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
            max_tokens=int(os.getenv("MAX_TOKENS", "2000")),
        )

    @classmethod
    def for_testing(cls) -> "Settings":
        return cls(
            app_name="Actypity Test",
            app_version="0.0.1-test",
            debug=True,
            secret_key="test-secret-key",
            api_host="127.0.0.1",
            api_port=8000,
            cors_origins=["http://localhost:5173"],
            storage_backend="memory",
            storage_path=Path("/tmp/actypity-test.json"),
            auth_enabled=False,
            default_admin_key=None,
            bootstrap_admin_token="test-bootstrap-token",
            postgres_dsn=None,
            postgres_host="localhost",
            postgres_port=5432,
            postgres_database="actypity_test",
            postgres_user="postgres",
            postgres_password="postgres",
            postgres_ssl_mode=None,
            postgres_pool_size=2,
            postgres_max_overflow=2,
            postgres_echo=False,
            azure_openai_api_key=None,
            azure_openai_endpoint=None,
            azure_openai_deployment=None,
            azure_openai_api_version="2024-02-01",
            request_timeout_seconds=5.0,
            max_tokens=500,
        )

    @property
    def llm_enabled(self) -> bool:
        return bool(
            self.azure_openai_api_key
            and self.azure_openai_endpoint
            and self.azure_openai_deployment
        )

    @property
    def postgres_enabled(self) -> bool:
        return self.storage_backend == "postgres" or bool(self.postgres_dsn)

    @property
    def resolved_postgres_dsn(self) -> str:
        if self.postgres_dsn:
            return self.postgres_dsn

        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        query = f"?sslmode={self.postgres_ssl_mode}" if self.postgres_ssl_mode else ""
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}{query}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
