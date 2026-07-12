from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.document import Document


class SqlAlchemyDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: str) -> list[Document]:
        statement = select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc())
        return list(self.db.execute(statement).scalars().all())

    def get_for_user(self, user_id: str, document_id: str) -> Document | None:
        statement = (
            select(Document)
            .where(Document.id == document_id, Document.user_id == user_id)
            .options(selectinload(Document.text_chunks), selectinload(Document.images))
        )
        return self.db.execute(statement).scalar_one_or_none()

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.commit()
