from sqlalchemy.orm import Session

from app.application.ingestion.service import DocumentIngestionService
from app.infrastructure.ingestion.pipeline import SqlAlchemyIngestionPipeline


def build_ingestion_service(db: Session) -> DocumentIngestionService:
    return DocumentIngestionService(SqlAlchemyIngestionPipeline(db))
