from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.base import Base


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(*, create_tables: bool = True) -> None:
    from app.bootstrap import run_startup_bootstrap
    from app.models import document  # noqa: F401
    from app.models import ingestion_job  # noqa: F401
    from app.models import trace  # noqa: F401
    from app.models import user  # noqa: F401

    if create_tables:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_startup_bootstrap(db)
    finally:
        db.close()
