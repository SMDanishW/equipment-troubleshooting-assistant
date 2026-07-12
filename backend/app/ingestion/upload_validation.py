from dataclasses import dataclass

from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.domain.errors import DomainError


class InvalidPdfUpload(DomainError):
    code = "invalid_pdf_upload"


class PdfUploadLimitExceeded(DomainError):
    code = "pdf_upload_limit_exceeded"


@dataclass(frozen=True)
class PdfUploadMetadata:
    size_bytes: int
    page_count: int


def validate_pdf_upload(
    upload: UploadFile,
    *,
    max_bytes: int,
    max_pages: int,
    max_filename_length: int,
) -> PdfUploadMetadata:
    filename = upload.filename or ""
    content_type = (upload.content_type or "").split(";", maxsplit=1)[0].strip().lower()

    if content_type not in {"application/pdf", "application/octet-stream"}:
        raise InvalidPdfUpload("Only PDF uploads are supported.")
    if not filename or not filename.lower().endswith(".pdf"):
        raise InvalidPdfUpload("Uploaded file must have a .pdf filename.")
    if len(filename) > max_filename_length:
        raise InvalidPdfUpload(f"Filename exceeds the {max_filename_length}-character limit.")

    try:
        upload.file.seek(0, 2)
        size_bytes = upload.file.tell()
        upload.file.seek(0)
        header = upload.file.read(min(size_bytes, 1024))
        upload.file.seek(0)
    except (OSError, ValueError) as exc:
        raise InvalidPdfUpload("Uploaded PDF could not be inspected.") from exc

    if size_bytes == 0:
        raise InvalidPdfUpload("Uploaded PDF is empty.")
    if size_bytes > max_bytes:
        raise PdfUploadLimitExceeded(f"PDF exceeds the {max_bytes // (1024 * 1024)} MB upload limit.")
    if b"%PDF-" not in header:
        raise InvalidPdfUpload("Uploaded file does not contain a valid PDF header.")

    try:
        reader = PdfReader(upload.file, strict=False)
        if reader.is_encrypted:
            raise InvalidPdfUpload("Encrypted or password-protected PDFs are not supported.")
        page_count = len(reader.pages)
    except InvalidPdfUpload:
        raise
    except (PdfReadError, OSError, ValueError, TypeError, KeyError) as exc:
        raise InvalidPdfUpload("Uploaded file is not a readable PDF.") from exc
    finally:
        upload.file.seek(0)

    if page_count == 0:
        raise InvalidPdfUpload("Uploaded PDF does not contain any pages.")
    if page_count > max_pages:
        raise PdfUploadLimitExceeded(f"PDF exceeds the {max_pages}-page processing limit.")

    return PdfUploadMetadata(size_bytes=size_bytes, page_count=page_count)
