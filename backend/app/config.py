from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")

    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60 * 24, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    database_url: str = Field(
        default="postgresql+psycopg://equipment_agent:equipment_agent@localhost:5432/equipment_agent",
        alias="DATABASE_URL",
    )
    auto_create_tables: bool = Field(default=True, alias="AUTO_CREATE_TABLES")

    upload_dir: str = Field(default="./data/uploads", alias="UPLOAD_DIR")
    image_dir: str = Field(default="./data/images", alias="IMAGE_DIR")
    trace_dir: str = Field(default="./data/traces", alias="TRACE_DIR")
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    embedding_provider: str = Field(default="hashing", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    hashing_embedding_dimensions: int = Field(default=256, alias="HASHING_EMBEDDING_DIMENSIONS")
    top_k_text: int = Field(default=5, alias="TOP_K_TEXT")
    top_k_images: int = Field(default=3, alias="TOP_K_IMAGES")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="qwen/qwen3-32b", alias="GROQ_MODEL")

    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_email: str = Field(default="admin@example.com", alias="ADMIN_EMAIL")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
