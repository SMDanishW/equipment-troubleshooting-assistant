import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="SQLAlchemy 2.0.36 model annotation parsing is incompatible with Python 3.14; the project runtime is Python 3.12.",
)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.infrastructure.repositories.documents import SqlAlchemyDocumentRepository
from app.infrastructure.repositories.ingestion_jobs import SqlAlchemyIngestionJobRepository
from app.domain.documents.entities import IngestionJobStatus
from app.models.document import Document, DocumentStatus, TextChunk
from app.models.user import User


def test_sqlalchemy_document_repository_enforces_tenant_scope_and_deletes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        first_user = User(
            username="operator-1",
            email="operator-1@example.com",
            hashed_password="hash",
        )
        second_user = User(
            username="operator-2",
            email="operator-2@example.com",
            hashed_password="hash",
        )
        db.add_all([first_user, second_user])
        db.flush()

        document = Document(
            user_id=first_user.id,
            filename="manual.pdf",
            equipment_name="Welder",
            document_type="manual",
            status=DocumentStatus.INDEXED,
        )
        db.add(document)
        db.flush()
        db.add(
            TextChunk(
                document_id=document.id,
                chunk_index=0,
                page_start=1,
                page_end=1,
                content="Pressure sensor calibration.",
            )
        )
        db.commit()

        repository = SqlAlchemyDocumentRepository(db)
        assert repository.list_for_user(first_user.id) == [document]
        assert repository.list_for_user(second_user.id) == []
        assert repository.get_for_user(second_user.id, document.id) is None

        loaded = repository.get_for_user(first_user.id, document.id)
        assert loaded is document
        assert loaded.text_chunks[0].content == "Pressure sensor calibration."

        repository.delete(loaded)
        assert repository.get_for_user(first_user.id, document.id) is None


def test_ingestion_job_repository_claims_retries_and_exhausts_jobs():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(username="operator", email="operator@example.com", hashed_password="hash")
        db.add(user)
        db.flush()
        document = Document(
            user_id=user.id,
            filename="manual.pdf",
            equipment_name="Welder",
            document_type="manual",
            status=DocumentStatus.PROCESSING,
        )
        db.add(document)
        db.commit()

        repository = SqlAlchemyIngestionJobRepository(db)
        queued = repository.enqueue(document.id, max_attempts=2)
        assert queued.status == IngestionJobStatus.QUEUED

        first_attempt = repository.claim_next()
        assert first_attempt.id == queued.id
        assert first_attempt.attempts == 1
        assert first_attempt.status == IngestionJobStatus.RUNNING
        assert repository.fail_or_requeue(first_attempt, RuntimeError("temporary")) is False
        assert first_attempt.status == IngestionJobStatus.QUEUED

        second_attempt = repository.claim_next()
        assert second_attempt.attempts == 2
        assert repository.fail_or_requeue(second_attempt, RuntimeError("permanent")) is True
        assert second_attempt.status == IngestionJobStatus.FAILED
        assert repository.claim_next() is None
