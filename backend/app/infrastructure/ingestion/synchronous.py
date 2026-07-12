from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.pipeline import ingest_pdf_upload


class SynchronousDocumentIngestor:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ingest(
        self,
        *,
        user: Any,
        upload: Any,
        equipment_name: str,
        document_type: str,
    ) -> Any:
        return ingest_pdf_upload(
            db=self.db,
            user=user,
            upload=upload,
            equipment_name=equipment_name,
            document_type=document_type,
        )
