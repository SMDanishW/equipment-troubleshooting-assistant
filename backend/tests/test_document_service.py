from types import SimpleNamespace

import pytest

from app.application.documents.service import DocumentApplicationService
from app.domain.documents.errors import DocumentNotFoundError
from app.domain.documents.entities import DocumentStatus
from app.domain.documents.errors import DocumentProcessingError
from app.domain.documents.ports import UploadPolicy


class FakeRepository:
    def __init__(self, documents=None):
        self.documents = documents or []
        self.deleted = []

    def list_for_user(self, user_id):
        return [document for document in self.documents if document.user_id == user_id]

    def get_for_user(self, user_id, document_id):
        return next(
            (document for document in self.documents if document.user_id == user_id and document.id == document_id),
            None,
        )

    def delete(self, document):
        self.deleted.append(document)


class FakeIngestor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def ingest(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def make_service(repository=None, ingestor=None):
    validation_calls = []
    cleanup_calls = []

    def validator(upload, **limits):
        validation_calls.append((upload, limits))

    def cleaner(user_id, document_id):
        cleanup_calls.append((user_id, document_id))

    service = DocumentApplicationService(
        repository=repository or FakeRepository(),
        ingestor=ingestor or FakeIngestor(SimpleNamespace(id="created")),
        upload_validator=validator,
        artifact_cleaner=cleaner,
        upload_policy=UploadPolicy(max_bytes=100, max_pages=20, max_filename_length=80),
    )
    return service, validation_calls, cleanup_calls


def test_upload_applies_policy_before_delegating_to_ingestor():
    ingestor = FakeIngestor(SimpleNamespace(id="created"))
    service, validation_calls, _ = make_service(ingestor=ingestor)
    user = SimpleNamespace(id="user-1")
    upload = object()

    result = service.upload(
        user=user,
        upload=upload,
        equipment_name="Welder",
        document_type="manual",
    )

    assert result.id == "created"
    assert validation_calls == [
        (upload, {"max_bytes": 100, "max_pages": 20, "max_filename_length": 80})
    ]
    assert ingestor.calls[0]["user"] is user
    assert ingestor.calls[0]["equipment_name"] == "Welder"


def test_get_enforces_user_ownership_as_not_found():
    document = SimpleNamespace(id="document-1", user_id="user-1")
    service, _, _ = make_service(repository=FakeRepository([document]))

    assert service.get_for_user("user-1", "document-1") is document
    with pytest.raises(DocumentNotFoundError):
        service.get_for_user("user-2", "document-1")


def test_delete_cleans_artifacts_before_repository_delete():
    document = SimpleNamespace(id="document-1", user_id="user-1", status=DocumentStatus.INDEXED)
    repository = FakeRepository([document])
    service, _, cleanup_calls = make_service(repository=repository)

    service.delete_for_user("user-1", "document-1")

    assert cleanup_calls == [("user-1", "document-1")]
    assert repository.deleted == [document]


def test_delete_rejects_document_while_processing():
    document = SimpleNamespace(id="document-1", user_id="user-1", status=DocumentStatus.PROCESSING)
    repository = FakeRepository([document])
    service, _, cleanup_calls = make_service(repository=repository)

    with pytest.raises(DocumentProcessingError):
        service.delete_for_user("user-1", "document-1")

    assert cleanup_calls == []
    assert repository.deleted == []
