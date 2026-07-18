from pathlib import Path

from app.config import settings
from app.domain.storage.ports import ArtifactStore
from app.infrastructure.storage.local import LocalArtifactStore


def build_artifact_store() -> ArtifactStore:
    return LocalArtifactStore(
        upload_root=Path(settings.upload_dir),
        image_root=Path(settings.image_dir),
    )
