from pathlib import Path
import re

from fastapi import UploadFile


def safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).name).strip("._")
    return cleaned or "manual.pdf"


class UploadSizeExceededError(ValueError):
    pass


def save_upload_file(
    upload: UploadFile,
    upload_dir: Path,
    user_id: str,
    document_id: str,
    max_bytes: int,
) -> Path:
    target_dir = upload_dir / user_id / document_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_filename(upload.filename or "manual.pdf")

    upload.file.seek(0)
    bytes_written = 0
    try:
        with target_path.open("wb") as destination:
            while chunk := upload.file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise UploadSizeExceededError(f"Upload exceeds the {max_bytes}-byte size limit.")
                destination.write(chunk)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise

    return target_path
