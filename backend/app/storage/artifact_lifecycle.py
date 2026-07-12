from pathlib import Path
import shutil


def remove_document_file_trees(
    *,
    upload_root: Path,
    image_root: Path,
    user_id: str,
    document_id: str,
    remove_upload: bool = True,
    remove_images: bool = True,
) -> None:
    roots = []
    if remove_upload:
        roots.append(upload_root)
    if remove_images:
        roots.append(image_root)
    for root in roots:
        target = _document_directory(root, user_id, document_id)
        if target.exists():
            shutil.rmtree(target)


def _document_directory(root: Path, user_id: str, document_id: str) -> Path:
    _validate_path_segment(user_id, "user_id")
    _validate_path_segment(document_id, "document_id")

    resolved_root = root.resolve()
    target = (resolved_root / user_id / document_id).resolve()
    if not target.is_relative_to(resolved_root) or target == resolved_root:
        raise ValueError("Document artifact path escapes its configured root.")
    return target


def _validate_path_segment(value: str, field_name: str) -> None:
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError(f"Invalid {field_name} for artifact cleanup.")
