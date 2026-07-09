import os
import json

os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.config import settings
from app.crud.users import create_user
from app.database import Base
from app.main import app
from app.models.document import Document, DocumentImage, TextChunk  # noqa: F401
from app.models.trace import AgentTrace, Conversation  # noqa: F401
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


def register_and_token(username: str = "operator", email: str = "operator@example.com") -> str:
    response = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": "strong-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_admin_token() -> str:
    db = TestingSessionLocal()
    try:
        create_user(db, "admin", "admin@example.com", "admin-password", role="admin")
    finally:
        db.close()

    response = client.post(
        "/auth/login",
        json={"identifier": "admin", "password": "admin-password"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    return response.json()["access_token"]


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


def upload_manual(
    token: str,
    filename: str = "manual.pdf",
    text: str = "Error E102 pressure sensor calibration failure. Check the sensor cable.",
) -> dict:
    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"equipment_name": "Kemppi AX MIG Welder", "document_type": "operating_manual"},
        files={
            "file": (
                filename,
                make_pdf_bytes(text),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 201
    return response.json()


def test_chat_test_runs_agent_workflow_and_stores_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    token = register_and_token()
    upload_manual(token)

    chat_response = client.post(
        "/chat/test",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What should I check for error E102?", "equipment_name": "Kemppi AX MIG Welder"},
    )

    assert chat_response.status_code == 200
    body = chat_response.json()
    assert body["conversation_id"]
    assert "## Answer" in body["answer"]
    assert "[[txt_" in body["answer"]
    assert body["citations"]

    trace_response = client.get(
        f"/traces/{body['conversation_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert trace["status"] == "completed"
    assert trace["final_answer"] == body["answer"]
    agent_names = [item["agent_name"] for item in trace["agent_traces"]]
    assert agent_names == [
        "Query Understanding Agent",
        "Retrieval Agent",
        "Diagnosis Agent",
        "Troubleshooting Steps Agent",
        "Guardrails Agent",
        "Cross-Check Agent",
        "Final Synthesis Agent",
    ]


def test_chat_can_scope_retrieval_to_selected_document(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    token = register_and_token()
    pressure_manual = upload_manual(
        token,
        filename="pressure-manual.pdf",
        text="Error E102 pressure sensor calibration failure. Check the sensor cable.",
    )
    robot_manual = upload_manual(
        token,
        filename="robot-manual.pdf",
        text="Robot Connectivity Module setup requires connecting the fieldbus cable and enabling robot mode.",
    )

    chat_response = client.post(
        "/chat/test",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "What should I check for error E102?",
            "equipment_name": "Kemppi AX MIG Welder",
            "document_ids": [robot_manual["id"]],
        },
    )

    assert chat_response.status_code == 200
    citations = chat_response.json()["citations"]
    assert citations
    assert {citation["document_id"] for citation in citations} == {robot_manual["id"]}
    assert pressure_manual["id"] not in {citation["document_id"] for citation in citations}


def test_trace_is_user_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    first_token = register_and_token("operator1", "operator1@example.com")
    second_token = register_and_token("operator2", "operator2@example.com")
    upload_manual(first_token)

    chat_response = client.post(
        "/chat/test",
        headers={"Authorization": f"Bearer {first_token}"},
        json={"question": "What should I check for error E102?"},
    )
    assert chat_response.status_code == 200

    trace_response = client.get(
        f"/traces/{chat_response.json()['conversation_id']}",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert trace_response.status_code == 404


def test_admin_can_list_and_read_any_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    user_token = register_and_token("operator1", "operator1@example.com")
    admin_token = create_admin_token()
    upload_manual(user_token)

    chat_response = client.post(
        "/chat/test",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"question": "What should I check for error E102?"},
    )
    assert chat_response.status_code == 200
    conversation_id = chat_response.json()["conversation_id"]

    list_response = client.get("/traces", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_response.status_code == 200
    assert any(trace["id"] == conversation_id for trace in list_response.json())

    trace_response = client.get(f"/traces/{conversation_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert trace_response.status_code == 200
    assert trace_response.json()["id"] == conversation_id


def test_non_admin_cannot_list_all_traces():
    token = register_and_token("operator3", "operator3@example.com")

    response = client.get("/traces", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_chat_stream_emits_sse_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "image_dir", str(tmp_path / "images"))
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path / "chroma"))
    get_chroma_store.cache_clear()
    token = register_and_token()
    upload_manual(token)

    with client.stream(
        "POST",
        "/chat/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What should I check for error E102?", "equipment_name": "Kemppi AX MIG Welder"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw_stream = "".join(response.iter_text())

    events = parse_sse(raw_stream)
    event_names = [event["event"] for event in events]

    assert "agent_update" in event_names
    assert "retrieval_update" in event_names
    assert "token" in event_names
    assert "citation" in event_names
    assert "image" in event_names
    assert event_names[-1] == "done"

    answer = "".join(event["data"]["content"] for event in events if event["event"] == "token")
    assert "## Answer" in answer
    assert "[[txt_" in answer
    assert events[-1]["data"]["conversation_id"]


def parse_sse(raw_stream: str) -> list[dict]:
    parsed = []
    for block in raw_stream.strip().split("\n\n"):
        event_name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            if line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if event_name and data is not None:
            parsed.append({"event": event_name, "data": data})
    return parsed
