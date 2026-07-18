from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.ingestion.service import build_ingestion_service


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
        return build_ingestion_service(self.db).ingest_inline(
            user=user,
            upload=upload,
            equipment_name=equipment_name,
            document_type=document_type,
        )
