import os
from io import BytesIO
from pathlib import Path

os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.config import settings
from app.database import Base
from app.ingestion.image_extractor import extract_pdf_images
from app.main import app
from app.models.document import Document, DocumentImage, TextChunk  # noqa: F401
from app.models.user import User  # noqa: F401
from app.rag.chroma_store import get_chroma_store


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    app.dependency_overrides[get_db] = override_get_db
    get_chroma_store.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def make_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 18 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def build_pdf(objects: list[bytes]) -> bytes:
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def make_pdf_with_image_bytes() -> bytes:
    from PIL import Image

    image_buffer = BytesIO()
    Image.new("RGB", (100, 100), color=(220, 20, 60)).save(image_buffer, format="JPEG")
    image_bytes = image_buffer.getvalue()
    image_stream = (
        b"<< /Type /XObject /Subtype /Image /Width 100 /Height 100 "
        b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length "
        + str(len(image_bytes)).encode("ascii")
        + b" >>\nstream\n"
        + image_bytes
        + b"\nendstream"
    )
    content = b"q 100 0 0 100 72 600 cm /Im1 Do Q"
    content_stream = b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream"

    return build_pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>",
            image_stream,
            content_stream,
        ]
    )


def register_and_token(username: str, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": "strong-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_upload_document_requires_auth():
    response = client.get("/documents")

    assert response.status_code == 401


def test_authenticated_user_can_upload_and_read_own_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    token = register_and_token("operator", "operator@example.com")

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"equipment_name": "Kemppi AX MIG Welder", "document_type": "operating_manual"},
        files={
            "file": (
                "manual.pdf",
                make_pdf_bytes("Error E102 pressure sensor calibration failure. Check the cable."),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "manual.pdf"
    assert body["equipment_name"] == "Kemppi AX MIG Welder"
    assert body["status"] == "indexed"
    assert body["page_count"] == 1
    assert body["text_chunks_count"] >= 1

    list_response = client.get("/documents", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/documents/{body['id']}", headers={"Authorization": f"Bearer {token}"})
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert "pressure sensor" in detail["text_chunks"][0]["content"]
    assert Path(settings.upload_dir).exists()


def test_upload_can_auto_detect_document_type(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    token = register_and_token("operator", "operator@example.com")

    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"equipment_name": "Kemppi Welder", "document_type": "auto"},
        files={
            "file": (
                "maintenance.pdf",
                make_pdf_bytes("Annual maintenance requires cleaning and checking service intervals."),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["document_type"] == "maintenance_guide"


def test_user_can_delete_uploaded_document(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    token = register_and_token("operator", "operator@example.com")

    upload_response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"equipment_name": "Kemppi Welder", "document_type": "operating_manual"},
        files={"file": ("manual.pdf", make_pdf_bytes("Operating manual for startup."), "application/pdf")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    delete_response = client.delete(f"/documents/{document_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_response.status_code == 204

    list_response = client.get("/documents", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert list_response.json() == []

    detail_response = client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail_response.status_code == 404


def test_users_cannot_read_each_others_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    first_token = register_and_token("operator1", "operator1@example.com")
    second_token = register_and_token("operator2", "operator2@example.com")

    upload_response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {first_token}"},
        data={"equipment_name": "Welder A", "document_type": "manual"},
        files={"file": ("manual.pdf", make_pdf_bytes("Private manual"), "application/pdf")},
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    forbidden_response = client.get(f"/documents/{document_id}", headers={"Authorization": f"Bearer {second_token}"})
    assert forbidden_response.status_code == 404

    second_list_response = client.get("/documents", headers={"Authorization": f"Bearer {second_token}"})
    assert second_list_response.status_code == 200
    assert second_list_response.json() == []


def test_retrieval_searches_across_current_users_uploaded_manuals(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    token = register_and_token("operator", "operator@example.com")

    first_upload = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"equipment_name": "Welder A", "document_type": "manual"},
        files={
            "file": (
                "welder-a.pdf",
                make_pdf_bytes("Error E102 pressure sensor calibration failure. Check sensor cable."),
                "application/pdf",
            )
        },
    )
    second_upload = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"equipment_name": "Welder B", "document_type": "maintenance"},
        files={
            "file": (
                "welder-b.pdf",
                make_pdf_bytes("Cooling unit maintenance requires checking coolant quality."),
                "application/pdf",
            )
        },
    )

    assert first_upload.status_code == 201
    assert second_upload.status_code == 201

    response = client.post(
        "/retrieval/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "pressure sensor calibration", "top_k_text": 2, "top_k_images": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "pressure sensor calibration"
    assert len(body["text_evidence"]) >= 1
    assert "pressure sensor" in body["text_evidence"][0]["text"]


def test_retrieval_does_not_cross_user_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    first_token = register_and_token("operator1", "operator1@example.com")
    second_token = register_and_token("operator2", "operator2@example.com")

    upload_response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {first_token}"},
        data={"equipment_name": "Private Welder", "document_type": "manual"},
        files={
            "file": (
                "private.pdf",
                make_pdf_bytes("Secret pressure sensor calibration note."),
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201

    response = client.post(
        "/retrieval/search",
        headers={"Authorization": f"Bearer {second_token}"},
        json={"query": "pressure sensor calibration", "top_k_text": 5, "top_k_images": 0},
    )

    assert response.status_code == 200
    assert response.json()["text_evidence"] == []


def test_pdf_image_extractor_saves_useful_unique_images(tmp_path):
    pdf_path = tmp_path / "image-manual.pdf"
    output_dir = tmp_path / "images"
    pdf_path.write_bytes(make_pdf_with_image_bytes())

    images = extract_pdf_images(pdf_path, output_dir, "doc_123", min_bytes=100)

    assert len(images) == 1
    assert images[0].page == 1
    assert images[0].width == 100
    assert images[0].height == 100
    assert Path(images[0].path).exists()
