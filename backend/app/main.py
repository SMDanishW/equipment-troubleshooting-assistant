from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, citations, documents, health, metrics, retrieval, traces
from app.api.error_handlers import register_domain_error_handlers
from app.config import settings
from app.database import init_db
from app.observability.http import RequestContextMiddleware
from app.observability.logging import configure_logging
from app.observability.metrics import MetricsMiddleware


def create_app() -> FastAPI:
    configure_logging(level=settings.log_level, log_format=settings.log_format)
    app = FastAPI(title="Equipment Troubleshooting Agent API", version="0.1.0")
    register_domain_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    if settings.metrics_enabled:
        app.add_middleware(MetricsMiddleware)

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(citations.router)
    app.include_router(documents.router)
    app.include_router(retrieval.router)
    app.include_router(chat.router)
    app.include_router(traces.router)

    @app.on_event("startup")
    def on_startup() -> None:
        init_db(create_tables=settings.auto_create_tables)

    return app


app = create_app()
