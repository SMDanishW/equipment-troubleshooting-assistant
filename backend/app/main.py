from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, citations, documents, health, retrieval, traces
from app.config import settings
from app.database import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="Equipment Troubleshooting Agent API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(citations.router)
    app.include_router(documents.router)
    app.include_router(retrieval.router)
    app.include_router(chat.router)
    app.include_router(traces.router)

    @app.on_event("startup")
    def on_startup() -> None:
        if settings.auto_create_tables:
            init_db()

    return app


app = create_app()
