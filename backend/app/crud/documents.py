from pathlib import Path
import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.document import Document
from app.rag.chroma_store import get_chroma_store


def list_documents_for_user(db: Session, user_id: str) -> list[Document]:
    statement = select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc())
    return list(db.execute(statement).scalars().all())


def get_document_for_user(db: Session, user_id: str, document_id: str) -> Document | None:
    statement = (
        select(Document)
        .where(Document.id == document_id, Document.user_id == user_id)
        .options(selectinload(Document.text_chunks), selectinload(Document.images))
    )
    return db.execute(statement).scalar_one_or_none()


def delete_document_for_user(db: Session, user_id: str, document_id: str) -> bool:
    document = get_document_for_user(db, user_id, document_id)
    if not document:
        return False

    storage_path = Path(document.storage_path) if document.storage_path else None
    image_paths = [Path(image.image_path) for image in document.images]
    get_chroma_store().delete_document(user_id=user_id, document_id=document.id)

    db.delete(document)
    db.commit()

    if storage_path and storage_path.exists():
        _remove_parent_directory(storage_path)
    for image_path in image_paths:
        if image_path.exists():
            _remove_parent_directory(image_path)
    return True


def _remove_parent_directory(path: Path) -> None:
    parent = path.parent
    if parent.exists():
        shutil.rmtree(parent, ignore_errors=True)
