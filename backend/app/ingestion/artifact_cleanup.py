from app.infrastructure.retrieval import build_retrieval_service
from app.infrastructure.storage.factory import build_artifact_store


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
        build_retrieval_service().delete_document(user_id=user_id, document_id=document_id)
    except Exception as exc:
        if not continue_on_error:
            raise ArtifactCleanupError(f"Unable to clean vector artifacts for document {document_id}.") from exc
        errors.append(exc)

    try:
        build_artifact_store().delete_document(
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
