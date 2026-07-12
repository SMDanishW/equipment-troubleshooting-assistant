from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.infrastructure.repositories.ingestion_jobs import SqlAlchemyIngestionJobRepository
from app.ingestion.artifact_cleanup import cleanup_document_artifacts
from app.ingestion.pipeline import stage_pdf_upload


class QueuedDocumentIngestor:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ingest(self, *, user: Any, upload: Any, equipment_name: str, document_type: str) -> Any:
        document = stage_pdf_upload(self.db, user, upload, equipment_name, document_type)
        try:
            SqlAlchemyIngestionJobRepository(self.db).enqueue(document.id, settings.ingestion_max_attempts)
        except Exception:
            self.db.rollback()
            cleanup_document_artifacts(user.id, document.id, continue_on_error=True)
            staged_document = self.db.get(type(document), document.id)
            if staged_document is not None:
                self.db.delete(staged_document)
                self.db.commit()
            raise
        return document
