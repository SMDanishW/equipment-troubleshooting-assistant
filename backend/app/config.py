from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    app_port: int = Field(default=8000, ge=1, le=65535, alias="APP_PORT")
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="console", alias="LOG_FORMAT")
    docker_logs_enabled: bool = Field(default=True, alias="DOCKER_LOGS_ENABLED")
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")

    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60 * 24, gt=0, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    database_url: str = Field(
        default="postgresql+psycopg://equipment_agent:equipment_agent@localhost:5432/equipment_agent",
        alias="DATABASE_URL",
    )
    auto_create_tables: bool = Field(default=True, alias="AUTO_CREATE_TABLES")

    upload_dir: str = Field(default="./data/uploads", alias="UPLOAD_DIR")
    max_upload_size_mb: int = Field(default=50, gt=0, le=1024, alias="MAX_UPLOAD_SIZE_MB")
    max_pdf_pages: int = Field(default=1000, gt=0, alias="MAX_PDF_PAGES")
    max_upload_filename_length: int = Field(default=255, ge=32, le=255, alias="MAX_UPLOAD_FILENAME_LENGTH")
    ingestion_mode: str = Field(default="inline", alias="INGESTION_MODE")
    ingestion_max_attempts: int = Field(default=3, ge=1, le=10, alias="INGESTION_MAX_ATTEMPTS")
    ingestion_poll_seconds: float = Field(default=2.0, ge=0.1, le=60, alias="INGESTION_POLL_SECONDS")
    ingestion_job_timeout_minutes: int = Field(default=30, ge=1, alias="INGESTION_JOB_TIMEOUT_MINUTES")
    image_dir: str = Field(default="./data/images", alias="IMAGE_DIR")
    trace_dir: str = Field(default="./data/traces", alias="TRACE_DIR")
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    embedding_provider: str = Field(default="hashing", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    hashing_embedding_dimensions: int = Field(default=256, gt=0, alias="HASHING_EMBEDDING_DIMENSIONS")
    top_k_text: int = Field(default=5, gt=0, alias="TOP_K_TEXT")
    top_k_images: int = Field(default=3, gt=0, alias="TOP_K_IMAGES")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="qwen/qwen3-32b", alias="GROQ_MODEL")

    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_email: str = Field(default="admin@example.com", alias="ADMIN_EMAIL")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")

    @field_validator("app_env", mode="before")
    @classmethod
    def validate_app_env(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        supported = {"local", "test", "staging", "production"}
        if normalized not in supported:
            raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(supported))}")
        return normalized

    @field_validator("embedding_provider", mode="before")
    @classmethod
    def validate_embedding_provider(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        supported = {"hashing", "sentence_transformers"}
        if normalized not in supported:
            raise ValueError(f"EMBEDDING_PROVIDER must be one of: {', '.join(sorted(supported))}")
        return normalized

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, value: object) -> str:
        normalized = str(value).strip().upper()
        supported = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in supported:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(sorted(supported))}")
        return normalized

    @field_validator("log_format", mode="before")
    @classmethod
    def validate_log_format(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        supported = {"console", "json"}
        if normalized not in supported:
            raise ValueError(f"LOG_FORMAT must be one of: {', '.join(sorted(supported))}")
        return normalized

    @field_validator("ingestion_mode", mode="before")
    @classmethod
    def validate_ingestion_mode(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        if normalized not in {"inline", "background"}:
            raise ValueError("INGESTION_MODE must be one of: background, inline")
        return normalized

    @field_validator("frontend_origin")
    @classmethod
    def validate_frontend_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("FRONTEND_ORIGIN must contain at least one origin")

        for origin in origins:
            parsed = urlparse(origin)
            if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("FRONTEND_ORIGIN entries must be explicit HTTP(S) origins")
            if parsed.path or parsed.params or parsed.query or parsed.fragment:
                raise ValueError("FRONTEND_ORIGIN entries cannot include paths, parameters, queries, or fragments")
        return ",".join(origins)

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.app_env not in {"staging", "production"}:
            return self

        errors: list[str] = []
        if self.secret_key == "change-me-in-production" or len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be at least 32 characters and cannot use the default")
        if self.auto_create_tables:
            errors.append("AUTO_CREATE_TABLES must be false; use database migrations")
        if self.database_url.lower().startswith("sqlite"):
            errors.append("DATABASE_URL cannot use SQLite")
        if any(not origin.startswith("https://") for origin in self.cors_origins):
            errors.append("FRONTEND_ORIGIN entries must use HTTPS")
        if self.admin_password and (self.admin_password == "admin-password" or len(self.admin_password) < 12):
            errors.append("ADMIN_PASSWORD must be at least 12 characters and cannot use the demo password")
        if self.log_format != "json":
            errors.append("LOG_FORMAT must be json")
        if self.docker_logs_enabled:
            errors.append("DOCKER_LOGS_ENABLED must be false")
        if self.ingestion_mode != "background":
            errors.append("INGESTION_MODE must be background")

        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
