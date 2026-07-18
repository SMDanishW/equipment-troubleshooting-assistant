import logging
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.ingestion.chunker import chunk_pages
from app.ingestion.document_classifier import classify_document_type
from app.ingestion.artifact_cleanup import cleanup_document_artifacts
from app.ingestion.image_extractor import extract_pdf_images
from app.ingestion.pdf_loader import extract_pdf_pages
from app.models.document import Document, DocumentImage, DocumentStatus, TextChunk
from app.models.user import User
from app.rag.indexer import index_document_evidence
from app.infrastructure.storage.factory import build_artifact_store
from app.storage.file_store import safe_filename

logger = logging.getLogger("equipment_agent.ingestion")


def ingest_pdf_upload(
    db: Session,
    user: User,
    upload: UploadFile,
    equipment_name: str,
    document_type: str,
) -> Document:
    document = stage_pdf_upload(db, user, upload, equipment_name, document_type)
    return process_staged_document(db, document.id, final_failure_cleanup=True)


def stage_pdf_upload(
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

    upload_path = build_artifact_store().save_upload(
        upload,
        user_id=user.id,
        document_id=document.id,
        max_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
    document.storage_path = upload_path
    db.commit()
    db.refresh(document)
    return document


def process_staged_document(db: Session, document_id: str, *, final_failure_cleanup: bool) -> Document:
    document = db.get(Document, document_id)
    if document is None or not document.storage_path:
        raise LookupError(f"Staged document {document_id} was not found.")
    user = db.get(User, document.user_id)
    if user is None:
        raise LookupError(f"User for staged document {document_id} was not found.")
    artifact_store = build_artifact_store()
    upload_path = artifact_store.resolve(document.storage_path)
    document.status = DocumentStatus.PROCESSING
    document.error_message = None
    db.commit()

    try:
        page_count, pages = extract_pdf_pages(upload_path, max_pages=settings.max_pdf_pages)
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

        image_output_dir = artifact_store.image_output_directory(user_id=user.id, document_id=document.id)
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
        db.rollback()
        cleanup_succeeded = True
        try:
            cleanup_document_artifacts(
                user_id=user.id,
                document_id=document.id,
                continue_on_error=True,
                remove_upload=final_failure_cleanup,
                remove_images=True,
            )
        except Exception:
            cleanup_succeeded = False
            logger.exception(
                "failed_ingestion_cleanup_failed",
                extra={"user_id": user.id, "document_id": document.id},
            )

        failed_document = db.get(Document, document.id)
        if failed_document is None:
            raise
        failed_document.status = DocumentStatus.FAILED if final_failure_cleanup else DocumentStatus.PROCESSING
        failed_document.error_message = str(exc)[:4000]
        failed_document.page_count = 0
        failed_document.text_chunks_count = 0
        failed_document.images_extracted_count = 0
        if final_failure_cleanup and (
            cleanup_succeeded
            or (
                failed_document.storage_path
                and not build_artifact_store().resolve(failed_document.storage_path).exists()
            )
        ):
            failed_document.storage_path = None
        db.commit()
        db.refresh(failed_document)
        raise

    db.commit()
    db.refresh(document)
    return document


def _nearby_text_for_page(pages: list[tuple[int, str]], page_number: int) -> str | None:
    for page, text in pages:
        if page == page_number and text:
            return " ".join(text.split())[:1000]
    return None
