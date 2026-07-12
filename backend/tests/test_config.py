import re

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_normalize_environment_provider_and_origins(monkeypatch):
    monkeypatch.setenv("APP_ENV", " LOCAL ")
    monkeypatch.setenv("EMBEDDING_PROVIDER", " SENTENCE_TRANSFORMERS ")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3100/, https://example.com/")

    configured = Settings(_env_file=None)

    assert configured.app_env == "local"
    assert configured.embedding_provider == "sentence_transformers"
    assert configured.cors_origins == ["http://localhost:3100", "https://example.com"]


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("APP_ENV", "preview", "APP_ENV must be one of"),
        ("EMBEDDING_PROVIDER", "unknown", "EMBEDDING_PROVIDER must be one of"),
        ("LOG_LEVEL", "verbose", "LOG_LEVEL must be one of"),
        ("LOG_FORMAT", "xml", "LOG_FORMAT must be one of"),
        ("FRONTEND_ORIGIN", "*", "explicit HTTP(S) origins"),
        ("APP_PORT", "70000", "less than or equal to 65535"),
        ("TOP_K_TEXT", "0", "greater than 0"),
        ("MAX_UPLOAD_SIZE_MB", "0", "greater than 0"),
        ("MAX_PDF_PAGES", "0", "greater than 0"),
        ("INGESTION_MODE", "unknown", "INGESTION_MODE must be one of"),
    ],
)
def test_settings_reject_invalid_values(monkeypatch, variable, value, message):
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError, match=re.escape(message)):
        Settings(_env_file=None)


def test_production_settings_reject_unsafe_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "change-me-in-production")
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3100")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-password")
    monkeypatch.setenv("LOG_FORMAT", "console")
    monkeypatch.setenv("DOCKER_LOGS_ENABLED", "true")
    monkeypatch.setenv("INGESTION_MODE", "inline")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    message = str(error.value)
    assert "SECRET_KEY must be at least 32 characters" in message
    assert "AUTO_CREATE_TABLES must be false" in message
    assert "DATABASE_URL cannot use SQLite" in message
    assert "FRONTEND_ORIGIN entries must use HTTPS" in message
    assert "ADMIN_PASSWORD must be at least 12 characters" in message
    assert "LOG_FORMAT must be json" in message
    assert "DOCKER_LOGS_ENABLED must be false" in message
    assert "INGESTION_MODE must be background" in message


def test_production_settings_accept_safe_configuration(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-production-secret-with-at-least-32-characters")
    monkeypatch.setenv("AUTO_CREATE_TABLES", "false")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://equipment_agent:password@postgres:5432/equipment_agent",
    )
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://equipment.example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("DOCKER_LOGS_ENABLED", "false")
    monkeypatch.setenv("INGESTION_MODE", "background")

    configured = Settings(_env_file=None)

    assert configured.app_env == "production"
    assert configured.auto_create_tables is False
