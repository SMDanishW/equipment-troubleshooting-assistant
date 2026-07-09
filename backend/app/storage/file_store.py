from pathlib import Path
import re
import shutil

from fastapi import UploadFile


def safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).name).strip("._")
    return cleaned or "manual.pdf"


def save_upload_file(upload: UploadFile, upload_dir: Path, user_id: str, document_id: str) -> Path:
    target_dir = upload_dir / user_id / document_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_filename(upload.filename or "manual.pdf")

    upload.file.seek(0)
    with target_path.open("wb") as destination:
        shutil.copyfileobj(upload.file, destination)

    return target_path

