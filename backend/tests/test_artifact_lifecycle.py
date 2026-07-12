from pathlib import Path

import pytest

from app.storage.artifact_lifecycle import remove_document_file_trees


def test_document_cleanup_removes_only_target_artifact_directories(tmp_path):
    upload_root = tmp_path / "uploads"
    image_root = tmp_path / "images"
    target_upload = upload_root / "user-1" / "document-1"
    target_images = image_root / "user-1" / "document-1"
    sibling = upload_root / "user-1" / "document-2"
    for directory in (target_upload, target_images, sibling):
        directory.mkdir(parents=True)
        (directory / "artifact.bin").write_bytes(b"data")

    remove_document_file_trees(
        upload_root=upload_root,
        image_root=image_root,
        user_id="user-1",
        document_id="document-1",
    )

    assert not target_upload.exists()
    assert not target_images.exists()
    assert sibling.exists()


@pytest.mark.parametrize("unsafe_segment", ["..", "../outside", "nested/path", ""])
def test_document_cleanup_rejects_unsafe_path_segments(tmp_path, unsafe_segment):
    with pytest.raises(ValueError, match="Invalid"):
        remove_document_file_trees(
            upload_root=Path(tmp_path / "uploads"),
            image_root=Path(tmp_path / "images"),
            user_id=unsafe_segment,
            document_id="document-1",
        )
