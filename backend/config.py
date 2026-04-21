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
    internal_api_token: str
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
    azure_openai_planner_deployment: Optional[str]
    azure_openai_reviewer_deployment: Optional[str]
    azure_openai_api_version: str
    llama_model_path: Optional[str]
    llama_resume_model_path: Optional[str]
    llama_job_model_path: Optional[str]
    llama_template_model_path: Optional[str]
    llama_n_ctx: int
    llama_temperature: float
    trusted_job_sources: List[str]
    request_timeout_seconds: float
    max_tokens: int
    diagnostics_interval_seconds: int
    # Ollama / local Llama
    ollama_base_url: str
    ollama_model: str
    ollama_models_dir: Optional[str]
    # Figma
    figma_access_token: Optional[str]
    figma_team_id: Optional[str]
    figma_file_key: Optional[str]
    # Job portal API credentials
    rapidapi_key: Optional[str]
    rapidapi_host: str
    linkedin_client_id: Optional[str]
    linkedin_client_secret: Optional[str]
    indeed_publisher_id: Optional[str]
    glassdoor_partner_id: Optional[str]
    glassdoor_api_key: Optional[str]
    adzuna_app_id: Optional[str]
    adzuna_api_key: Optional[str]
    # Social auth
    google_client_id: Optional[str]
    google_client_secret: Optional[str]
    # Google Gemini AI
    gemini_api_key: Optional[str]
    gemini_model: str
    # Model selection
    default_model_profile: Optional[str]

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
            internal_api_token=os.getenv("INTERNAL_API_TOKEN") or os.getenv("SECRET_KEY", "change-me-in-production"),
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
            azure_openai_planner_deployment=os.getenv("AZURE_OPENAI_PLANNER_DEPLOYMENT"),
            azure_openai_reviewer_deployment=os.getenv("AZURE_OPENAI_REVIEWER_DEPLOYMENT"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            llama_model_path=os.getenv("LLAMA_MODEL_PATH"),
            llama_resume_model_path=os.getenv("LLAMA_RESUME_MODEL_PATH"),
            llama_job_model_path=os.getenv("LLAMA_JOB_MODEL_PATH"),
            llama_template_model_path=os.getenv("LLAMA_TEMPLATE_MODEL_PATH"),
            llama_n_ctx=int(os.getenv("LLAMA_N_CTX", "4096")),
            llama_temperature=float(os.getenv("LLAMA_TEMPERATURE", "0.2")),
            trusted_job_sources=_split_csv(
                os.getenv(
                    "TRUSTED_JOB_SOURCES",
                    "linkedin,indeed,glassdoor,wellfound,naukri,foundit,careerbuilder,shine,dice,ziprecruiter",
                )
            ),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
            max_tokens=int(os.getenv("MAX_TOKENS", "2000")),
            diagnostics_interval_seconds=int(os.getenv("DIAGNOSTICS_INTERVAL_SECONDS", "1800")),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
            ollama_models_dir=os.getenv("OLLAMA_MODELS"),
            figma_access_token=os.getenv("FIGMA_ACCESS_TOKEN"),
            figma_team_id=os.getenv("FIGMA_TEAM_ID"),
            figma_file_key=os.getenv("FIGMA_FILE_KEY"),
            rapidapi_key=os.getenv("RAPIDAPI_KEY"),
            rapidapi_host=os.getenv("RAPIDAPI_HOST", "jsearch.p.rapidapi.com"),
            linkedin_client_id=os.getenv("LINKEDIN_CLIENT_ID"),
            linkedin_client_secret=os.getenv("LINKEDIN_CLIENT_SECRET"),
            indeed_publisher_id=os.getenv("INDEED_PUBLISHER_ID"),
            glassdoor_partner_id=os.getenv("GLASSDOOR_PARTNER_ID"),
            glassdoor_api_key=os.getenv("GLASSDOOR_API_KEY"),
            adzuna_app_id=os.getenv("ADZUNA_APP_ID"),
            adzuna_api_key=os.getenv("ADZUNA_API_KEY"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            default_model_profile=os.getenv("DEFAULT_MODEL_PROFILE"),
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
            internal_api_token="test-internal-token",
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
            azure_openai_planner_deployment=None,
            azure_openai_reviewer_deployment=None,
            azure_openai_api_version="2024-02-01",
            llama_model_path=None,
            llama_resume_model_path=None,
            llama_job_model_path=None,
            llama_template_model_path=None,
            llama_n_ctx=2048,
            llama_temperature=0.2,
            trusted_job_sources=["linkedin", "indeed", "glassdoor"],
            request_timeout_seconds=5.0,
            max_tokens=500,
            diagnostics_interval_seconds=1800,
            ollama_base_url="http://localhost:11434",
            ollama_model="llama3",
            ollama_models_dir=None,
            figma_access_token=None,
            figma_team_id=None,
            figma_file_key=None,
            rapidapi_key=None,
            rapidapi_host="jsearch.p.rapidapi.com",
            linkedin_client_id=None,
            linkedin_client_secret=None,
            indeed_publisher_id=None,
            glassdoor_partner_id=None,
            glassdoor_api_key=None,
            adzuna_app_id=None,
            adzuna_api_key=None,
            google_client_id=None,
            google_client_secret=None,
            gemini_api_key=None,
            gemini_model="gemini-2.0-flash",
            default_model_profile=None,
        )

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def azure_llm_enabled(self) -> bool:
        return bool(
            self.azure_openai_api_key
            and self.azure_openai_endpoint
            and self.azure_openai_deployment
        )

    @property
    def llm_enabled(self) -> bool:
        """True when any cloud LLM provider is configured."""
        return self.gemini_enabled or self.azure_llm_enabled

    @property
    def postgres_enabled(self) -> bool:
        return self.storage_backend == "postgres" or bool(self.postgres_dsn)

    @property
    def llama_enabled(self) -> bool:
        return bool(
            self.llama_model_path
            or self.llama_resume_model_path
            or self.llama_job_model_path
            or self.llama_template_model_path
        )

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
