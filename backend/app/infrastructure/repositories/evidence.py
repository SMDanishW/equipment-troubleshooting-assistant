from sqlalchemy.orm import Session

from app.models.document import DocumentImage, TextChunk


class SqlAlchemyEvidenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_text_chunk(self, chunk_id: str) -> TextChunk | None:
        return self.db.get(TextChunk, chunk_id)

    def get_image(self, image_id: str) -> DocumentImage | None:
        return self.db.get(DocumentImage, image_id)
