from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.ingestion.chunker import chunk_pages
from app.ingestion.document_classifier import classify_document_type
from app.ingestion.image_extractor import extract_pdf_images
from app.ingestion.pdf_loader import extract_pdf_pages
from app.models.document import Document, DocumentImage, DocumentStatus, TextChunk
from app.models.user import User
from app.rag.indexer import index_document_evidence
from app.storage.file_store import save_upload_file, safe_filename


def ingest_pdf_upload(
    db: Session,
    user: User,
    upload: UploadFile,
    equipment_name: str,
    document_type: str,
) -> Document:
    document = Document(
        user_id=user.id,
        filename=safe_filename(upload.filename or "manual.pdf"),
        equipment_name=equipment_name.strip(),
        document_type=document_type.strip(),
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    db.flush()

    upload_path = save_upload_file(upload, Path(settings.upload_dir), user.id, document.id)
    document.storage_path = str(upload_path)

    try:
        page_count, pages = extract_pdf_pages(upload_path)
        if document.document_type in {"", "auto", "unknown", "detect_automatically"}:
            document.document_type = classify_document_type(pages)

        chunks = chunk_pages(pages)
        document.page_count = page_count
        document.text_chunks_count = len(chunks)

        created_chunks: list[TextChunk] = []
        for chunk in chunks:
            text_chunk = TextChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                content=chunk.text,
            )
            db.add(text_chunk)
            created_chunks.append(text_chunk)

        image_output_dir = Path(settings.image_dir) / user.id / document.id
        images = extract_pdf_images(upload_path, image_output_dir, document.id)
        document.images_extracted_count = len(images)
        created_images: list[DocumentImage] = []
        for image in images:
            document_image = DocumentImage(
                document_id=document.id,
                page=image.page,
                filename=image.filename,
                image_path=image.path,
                content_hash=image.content_hash,
                nearby_text=_nearby_text_for_page(pages, image.page),
                width=image.width,
                height=image.height,
                bytes_size=image.bytes_size,
            )
            db.add(document_image)
            created_images.append(document_image)

        db.flush()
        index_document_evidence(document, created_chunks, created_images)

        document.status = DocumentStatus.INDEXED
        document.error_message = None
    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)
        db.commit()
        db.refresh(document)
        raise

    db.commit()
    db.refresh(document)
    return document


def _nearby_text_for_page(pages: list[tuple[int, str]], page_number: int) -> str | None:
    for page, text in pages:
        if page == page_number and text:
            return " ".join(text.split())[:1000]
    return None
