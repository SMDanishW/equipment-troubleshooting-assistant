from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.documents.service import DocumentApplicationService
from app.config import settings
from app.database import get_db
from app.domain.documents.ports import UploadPolicy


def get_document_service(db: Session = Depends(get_db)) -> DocumentApplicationService:
    from app.infrastructure.ingestion.synchronous import SynchronousDocumentIngestor
    from app.infrastructure.ingestion.queued import QueuedDocumentIngestor
    from app.infrastructure.repositories.documents import SqlAlchemyDocumentRepository
    from app.ingestion.artifact_cleanup import cleanup_document_artifacts
    from app.ingestion.upload_validation import validate_pdf_upload

    return DocumentApplicationService(
        repository=SqlAlchemyDocumentRepository(db),
        ingestor=QueuedDocumentIngestor(db) if settings.ingestion_mode == "background" else SynchronousDocumentIngestor(db),
        upload_validator=validate_pdf_upload,
        artifact_cleaner=cleanup_document_artifacts,
        upload_policy=UploadPolicy(
            max_bytes=settings.max_upload_size_mb * 1024 * 1024,
            max_pages=settings.max_pdf_pages,
            max_filename_length=settings.max_upload_filename_length,
        ),
    )
