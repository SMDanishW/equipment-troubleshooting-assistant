from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.pipeline import process_staged_document, stage_pdf_upload


class SqlAlchemyIngestionPipeline:
    """Owns database transaction boundaries delegated to the legacy extraction pipeline."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def stage(self, *, user: Any, upload: Any, equipment_name: str, document_type: str) -> Any:
        return stage_pdf_upload(self.db, user, upload, equipment_name, document_type)

    def process(self, document_id: str, *, final_failure_cleanup: bool) -> Any:
        return process_staged_document(
            self.db,
            document_id,
            final_failure_cleanup=final_failure_cleanup,
        )
