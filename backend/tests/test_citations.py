import os

os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.crud.users import create_user
from app.database import Base
from app.main import app
from app.models.document import Document, DocumentImage, TextChunk
from app.models.trace import AgentTrace, Conversation  # noqa: F401
from app.models.user import User  # noqa: F401


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
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_token(username: str, email: str) -> str:
    db = TestingSessionLocal()
    try:
        create_user(db, username=username, email=email, password="strong-password")
    finally:
        db.close()

    response = client.post("/auth/login", json={"identifier": username, "password": "strong-password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def create_document_fixture(username: str, email: str, image_path: str, pdf_path: str | None = None) -> tuple[str, str, str]:
    token = create_token(username, email)
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.username == username).one()
        document = Document(
            user_id=user.id,
            filename="manual.pdf",
            equipment_name="Kemppi Welder",
            document_type="operating_manual",
            storage_path=pdf_path,
            page_count=2,
            text_chunks_count=1,
            images_extracted_count=1,
        )
        db.add(document)
        db.flush()
        chunk = TextChunk(
            document_id=document.id,
            chunk_index=0,
            page_start=1,
            page_end=1,
            content="Error E102 indicates pressure sensor calibration failure.",
        )
        image = DocumentImage(
            document_id=document.id,
            page=2,
            filename="diagram.png",
            image_path=image_path,
            content_hash=f"hash-{username}",
            caption="Pressure sensor wiring diagram",
            nearby_text="Figure shows the pressure sensor wiring.",
            width=10,
            height=10,
            bytes_size=8,
        )
        db.add_all([chunk, image])
        db.commit()
        db.refresh(chunk)
        db.refresh(image)
        return token, f"txt_{chunk.id}", f"img_{image.id}"
    finally:
        db.close()


def make_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

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


def test_user_can_read_own_text_citation(tmp_path):
    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"fake-png")
    pdf_path = tmp_path / "manual.pdf"
    pdf_path.write_bytes(make_pdf_bytes("Error E102 indicates pressure sensor calibration failure."))
    token, text_citation_id, _ = create_document_fixture(
        "operator", "operator@example.com", str(image_path), str(pdf_path)
    )

    response = client.get(f"/citations/{text_citation_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == text_citation_id
    assert body["type"] == "text"
    assert body["source_file"] == "manual.pdf"
    assert body["page"] == 1
    assert body["pdf_url"].startswith("/files/pdfs/")
    assert body["highlighted_pdf_url"].endswith("/highlighted-pdf")
    assert "pressure sensor" in body["excerpt"]

    pdf_response = client.get(body["highlighted_pdf_url"], headers={"Authorization": f"Bearer {token}"})
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")


def test_user_can_read_own_image_citation_and_file(tmp_path):
    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"fake-png")
    token, _, image_citation_id = create_document_fixture("operator", "operator@example.com", str(image_path))

    citation_response = client.get(f"/citations/{image_citation_id}", headers={"Authorization": f"Bearer {token}"})

    assert citation_response.status_code == 200
    citation = citation_response.json()
    assert citation["type"] == "image"
    assert citation["image_url"].startswith("/files/images/")
    assert citation["caption"] == "Pressure sensor wiring diagram"

    file_response = client.get(citation["image_url"], headers={"Authorization": f"Bearer {token}"})
    assert file_response.status_code == 200
    assert file_response.content == b"fake-png"


def test_citations_are_user_scoped(tmp_path):
    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"fake-png")
    _, text_citation_id, image_citation_id = create_document_fixture("operator1", "operator1@example.com", str(image_path))
    second_token = create_token("operator2", "operator2@example.com")

    text_response = client.get(f"/citations/{text_citation_id}", headers={"Authorization": f"Bearer {second_token}"})
    image_response = client.get(f"/citations/{image_citation_id}", headers={"Authorization": f"Bearer {second_token}"})

    assert text_response.status_code == 404
    assert image_response.status_code == 404
