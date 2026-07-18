from app.models.document import Document, DocumentImage, TextChunk
from app.infrastructure.retrieval import build_retrieval_service
from sqlalchemy.orm import object_session


def index_document_evidence(document: Document, chunks: list[TextChunk], images: list[DocumentImage]) -> None:
    db = object_session(document)
    if db is None:
        raise RuntimeError("Document must be attached to a database session before indexing.")
    build_retrieval_service(db).index_document(document, chunks, images)
