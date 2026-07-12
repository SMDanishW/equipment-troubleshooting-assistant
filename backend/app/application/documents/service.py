from typing import Any

from app.domain.documents.entities import DocumentStatus
from app.domain.documents.errors import DocumentNotFoundError, DocumentProcessingError
from app.domain.documents.ports import (
    ArtifactCleaner,
    DocumentIngestor,
    DocumentRepository,
    UploadPolicy,
    UploadValidator,
)


class DocumentApplicationService:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        ingestor: DocumentIngestor,
        upload_validator: UploadValidator,
        artifact_cleaner: ArtifactCleaner,
        upload_policy: UploadPolicy,
    ) -> None:
        self.repository = repository
        self.ingestor = ingestor
        self.upload_validator = upload_validator
        self.artifact_cleaner = artifact_cleaner
        self.upload_policy = upload_policy

    def upload(
        self,
        *,
        user: Any,
        upload: Any,
        equipment_name: str,
        document_type: str,
    ) -> Any:
        self.upload_validator(
            upload,
            max_bytes=self.upload_policy.max_bytes,
            max_pages=self.upload_policy.max_pages,
            max_filename_length=self.upload_policy.max_filename_length,
        )
        return self.ingestor.ingest(
            user=user,
            upload=upload,
            equipment_name=equipment_name,
            document_type=document_type,
        )

    def list_for_user(self, user_id: str) -> list[Any]:
        return self.repository.list_for_user(user_id)

    def get_for_user(self, user_id: str, document_id: str) -> Any:
        document = self.repository.get_for_user(user_id, document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        return document

    def delete_for_user(self, user_id: str, document_id: str) -> None:
        document = self.get_for_user(user_id, document_id)
        if document.status == DocumentStatus.PROCESSING:
            raise DocumentProcessingError(document_id)
        self.artifact_cleaner(user_id, document.id)
        self.repository.delete(document)
