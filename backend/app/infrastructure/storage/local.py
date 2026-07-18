from pathlib import Path
from typing import Any

from app.storage.artifact_lifecycle import remove_document_file_trees
from app.storage.file_store import save_upload_file


class LocalArtifactStore:
    def __init__(self, *, upload_root: Path, image_root: Path) -> None:
        self.upload_root = upload_root
        self.image_root = image_root

    def save_upload(self, upload: Any, *, user_id: str, document_id: str, max_bytes: int) -> str:
        return str(save_upload_file(upload, self.upload_root, user_id, document_id, max_bytes))

    def image_output_directory(self, *, user_id: str, document_id: str) -> Path:
        return self.image_root / user_id / document_id

    def resolve(self, reference: str) -> Path:
        return Path(reference)

    def delete_document(
        self,
        *,
        user_id: str,
        document_id: str,
        remove_upload: bool = True,
        remove_images: bool = True,
    ) -> None:
        remove_document_file_trees(
            upload_root=self.upload_root,
            image_root=self.image_root,
            user_id=user_id,
            document_id=document_id,
            remove_upload=remove_upload,
            remove_images=remove_images,
        )
