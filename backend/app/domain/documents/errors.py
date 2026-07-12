from app.domain.errors import DomainError


class DocumentNotFoundError(DomainError):
    code = "document_not_found"

    def __init__(self, document_id: str) -> None:
        super().__init__("Document not found.")
        self.document_id = document_id


class DocumentProcessingError(DomainError):
    code = "document_processing"

    def __init__(self, document_id: str) -> None:
        super().__init__("Document cannot be deleted while indexing is in progress.")
        self.document_id = document_id
