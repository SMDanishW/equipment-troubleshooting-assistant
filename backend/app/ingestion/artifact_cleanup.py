from pathlib import Path

from app.config import settings
from app.rag.chroma_store import get_chroma_store
from app.storage.artifact_lifecycle import remove_document_file_trees


class ArtifactCleanupError(RuntimeError):
    pass


def cleanup_document_artifacts(
    user_id: str,
    document_id: str,
    *,
    continue_on_error: bool = False,
    remove_upload: bool = True,
    remove_images: bool = True,
) -> None:
    errors: list[Exception] = []
    try:
        get_chroma_store().delete_document(user_id=user_id, document_id=document_id)
    except Exception as exc:
        if not continue_on_error:
            raise ArtifactCleanupError(f"Unable to clean vector artifacts for document {document_id}.") from exc
        errors.append(exc)

    try:
        remove_document_file_trees(
            upload_root=Path(settings.upload_dir),
            image_root=Path(settings.image_dir),
            user_id=user_id,
            document_id=document_id,
            remove_upload=remove_upload,
            remove_images=remove_images,
        )
    except Exception as exc:
        if not continue_on_error:
            raise ArtifactCleanupError(f"Unable to clean file artifacts for document {document_id}.") from exc
        errors.append(exc)

    if errors:
        raise ArtifactCleanupError(
            f"Unable to fully clean artifacts for document {document_id}: "
            + "; ".join(str(error) for error in errors)
        ) from errors[0]
