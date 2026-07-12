from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class UploadPolicy:
    max_bytes: int
    max_pages: int
    max_filename_length: int


class DocumentRepository(Protocol):
    def list_for_user(self, user_id: str) -> list[Any]: ...

    def get_for_user(self, user_id: str, document_id: str) -> Any | None: ...

    def delete(self, document: Any) -> None: ...


class DocumentIngestor(Protocol):
    def ingest(
        self,
        *,
        user: Any,
        upload: Any,
        equipment_name: str,
        document_type: str,
    ) -> Any: ...


class UploadValidator(Protocol):
    def __call__(
        self,
        upload: Any,
        *,
        max_bytes: int,
        max_pages: int,
        max_filename_length: int,
    ) -> Any: ...


class ArtifactCleaner(Protocol):
    def __call__(self, user_id: str, document_id: str) -> None: ...
