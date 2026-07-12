import os
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.document_deps import get_document_service
from app.api.documents import router
from app.api.error_handlers import register_domain_error_handlers
from app.domain.documents.entities import DocumentStatus
from app.domain.documents.errors import DocumentNotFoundError
from app.ingestion.upload_validation import PdfUploadLimitExceeded


def document(document_id="document-1"):
    return SimpleNamespace(
        id=document_id,
        filename="manual.pdf",
        equipment_name="Welder",
        document_type="manual",
        page_count=1,
        text_chunks_count=1,
        images_extracted_count=0,
        status=DocumentStatus.INDEXED,
        error_message=None,
        created_at=datetime.now(timezone.utc),
        text_chunks=[],
        images=[],
    )


class FakeService:
    def __init__(self):
        self.documents = [document()]
        self.deleted = []
        self.upload_error = None

    def upload(self, **_kwargs):
        if self.upload_error:
            raise self.upload_error
        return self.documents[0]

    def list_for_user(self, _user_id):
        return self.documents

    def get_for_user(self, _user_id, document_id):
        if document_id != self.documents[0].id:
            raise DocumentNotFoundError(document_id)
        return self.documents[0]

    def delete_for_user(self, _user_id, document_id):
        self.get_for_user(_user_id, document_id)
        self.deleted.append(document_id)


def make_client(service):
    app = FastAPI()
    register_domain_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    app.dependency_overrides[get_document_service] = lambda: service
    return TestClient(app)


def test_document_routes_delegate_list_detail_and_delete_to_service():
    service = FakeService()
    client = make_client(service)

    assert client.get("/documents").status_code == 200
    assert client.get("/documents/document-1").status_code == 200
    assert client.delete("/documents/document-1").status_code == 204
    assert service.deleted == ["document-1"]


def test_document_routes_map_domain_not_found_to_404():
    response = make_client(FakeService()).get("/documents/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}
    assert response.headers["X-Error-Code"] == "document_not_found"


def test_upload_route_maps_policy_limit_to_413():
    service = FakeService()
    service.upload_error = PdfUploadLimitExceeded("PDF exceeds the upload limit.")

    response = make_client(service).post(
        "/documents/upload",
        data={"equipment_name": "Welder", "document_type": "manual"},
        files={"file": ("manual.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "PDF exceeds the upload limit."}
    assert response.headers["X-Error-Code"] == "pdf_upload_limit_exceeded"
