from io import BytesIO

import pytest
from fastapi import UploadFile
from pypdf import PdfWriter

from app.ingestion.upload_validation import InvalidPdfUpload, PdfUploadLimitExceeded, validate_pdf_upload
from app.storage.file_store import UploadSizeExceededError, save_upload_file


def make_pdf(page_count: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def make_upload(content: bytes, filename: str = "manual.pdf", content_type: str = "application/pdf") -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content), headers={"content-type": content_type})


def test_valid_pdf_returns_preflight_metadata_and_rewinds_stream():
    content = make_pdf(page_count=2)
    upload = make_upload(content)

    metadata = validate_pdf_upload(upload, max_bytes=1024 * 1024, max_pages=10, max_filename_length=255)

    assert metadata.size_bytes == len(content)
    assert metadata.page_count == 2
    assert upload.file.tell() == 0


@pytest.mark.parametrize(
    ("content", "filename", "content_type", "message"),
    [
        (b"", "manual.pdf", "application/pdf", "empty"),
        (b"not a pdf", "manual.pdf", "application/pdf", "valid PDF header"),
        (b"%PDF-1.4\nbroken", "manual.pdf", "application/pdf", "not a readable PDF"),
        (make_pdf(), "manual.txt", "application/pdf", ".pdf filename"),
        (make_pdf(), "manual.pdf", "text/plain", "Only PDF uploads"),
    ],
)
def test_invalid_pdf_uploads_are_rejected(content, filename, content_type, message):
    upload = make_upload(content, filename=filename, content_type=content_type)

    with pytest.raises(InvalidPdfUpload, match=message):
        validate_pdf_upload(upload, max_bytes=1024 * 1024, max_pages=10, max_filename_length=255)


def test_file_size_limit_is_enforced_before_pdf_parsing():
    upload = make_upload(make_pdf())

    with pytest.raises(PdfUploadLimitExceeded, match="upload limit"):
        validate_pdf_upload(upload, max_bytes=10, max_pages=10, max_filename_length=255)


def test_page_limit_is_enforced():
    upload = make_upload(make_pdf(page_count=2))

    with pytest.raises(PdfUploadLimitExceeded, match="page processing limit"):
        validate_pdf_upload(upload, max_bytes=1024 * 1024, max_pages=1, max_filename_length=255)


def test_bounded_file_copy_removes_partial_file(tmp_path):
    upload = make_upload(b"1234567890")

    with pytest.raises(UploadSizeExceededError):
        save_upload_file(upload, tmp_path, "user-1", "document-1", max_bytes=5)

    assert list(tmp_path.rglob("*.pdf")) == []
