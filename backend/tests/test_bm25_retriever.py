import os

os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.domain.documents.entities import DocumentStatus
from app.infrastructure.bm25 import SqlAlchemyBm25Retriever, tokenize
from app.models.document import Document, TextChunk
from app.models.user import User


def test_tokenize_preserves_equipment_error_codes():
    assert tokenize("Fault E102 on AX-MIG controller") == [
        "fault",
        "e102",
        "on",
        "ax-mig",
        "controller",
    ]


def test_bm25_filters_tenant_and_document_before_ranking():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first_user = User(username="first", email="first@example.com", hashed_password="hash")
        second_user = User(username="second", email="second@example.com", hashed_password="hash")
        db.add_all([first_user, second_user])
        db.flush()
        own_document = Document(
            user_id=first_user.id,
            filename="own.pdf",
            equipment_name="Welder",
            document_type="manual",
            status=DocumentStatus.INDEXED,
        )
        other_document = Document(
            user_id=second_user.id,
            filename="other.pdf",
            equipment_name="Welder",
            document_type="manual",
            status=DocumentStatus.INDEXED,
        )
        db.add_all([own_document, other_document])
        db.flush()
        own_chunk = TextChunk(
            document_id=own_document.id,
            chunk_index=0,
            page_start=1,
            page_end=1,
            content="Error E102 indicates pressure sensor calibration failure.",
        )
        other_chunk = TextChunk(
            document_id=other_document.id,
            chunk_index=0,
            page_start=1,
            page_end=1,
            content="Error E102 belongs to another tenant.",
        )
        db.add_all([own_chunk, other_chunk])
        db.commit()

        hits = SqlAlchemyBm25Retriever(db, candidate_limit=100).search_texts(
            first_user.id,
            "E102 pressure sensor",
            top_k=5,
            document_ids=[own_document.id],
        )

        assert [hit.chunk_id for hit in hits] == [own_chunk.id]
