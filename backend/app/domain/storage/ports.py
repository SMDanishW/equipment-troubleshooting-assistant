from pathlib import Path
from typing import Any, Protocol


class ArtifactStore(Protocol):
    def save_upload(self, upload: Any, *, user_id: str, document_id: str, max_bytes: int) -> str: ...

    def image_output_directory(self, *, user_id: str, document_id: str) -> Path: ...

    def resolve(self, reference: str) -> Path: ...

    def delete_document(
        self,
        *,
        user_id: str,
        document_id: str,
        remove_upload: bool = True,
        remove_images: bool = True,
    ) -> None: ...
