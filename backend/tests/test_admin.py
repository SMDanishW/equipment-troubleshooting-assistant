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
from app.models.document import Document, DocumentImage, DocumentStatus, TextChunk  # noqa: F401
from app.models.trace import AgentTrace, Conversation
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


def create_user_token(username: str, email: str, role: str = "user") -> str:
    db = TestingSessionLocal()
    try:
        create_user(db, username=username, email=email, password="strong-password", role=role)
    finally:
        db.close()

    response = client.post("/auth/login", json={"identifier": username, "password": "strong-password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_docker_logs_require_admin_role():
    token = create_user_token("operator", "operator@example.com")

    response = client.get("/admin/docker/services", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_admin_can_read_mocked_docker_logs(monkeypatch):
    token = create_user_token("admin", "admin@example.com", role="admin")
    monkeypatch.setattr("app.api.admin.get_container_logs", lambda service, tail: f"{service}:{tail}:ok")

    response = client.get("/admin/docker/logs?service=backend&tail=20", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["logs"] == "backend:20:ok"


def test_admin_user_overview_lists_user_documents_and_chats():
    admin_token = create_user_token("admin", "admin@example.com", role="admin")
    create_user_token("operator", "operator@example.com")
    db = TestingSessionLocal()
    try:
        operator = db.query(User).filter(User.username == "operator").one()
        document = Document(
            user_id=operator.id,
            filename="manual.pdf",
            equipment_name="Kemppi Welder",
            document_type="operating_manual",
            page_count=10,
            text_chunks_count=4,
            images_extracted_count=2,
            status=DocumentStatus.INDEXED,
        )
        conversation = Conversation(
            user_id=operator.id,
            question="What should I check for E102?",
            equipment_name="Kemppi Welder",
            final_answer="Check the cited manual section.",
            status="completed",
        )
        db.add_all([document, conversation])
        db.commit()
    finally:
        db.close()

    response = client.get("/admin/users/overview", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200
    users = response.json()
    operator_overview = next(user for user in users if user["username"] == "operator")
    assert operator_overview["documents_count"] == 1
    assert operator_overview["conversations_count"] == 1
    assert operator_overview["documents"][0]["filename"] == "manual.pdf"
    assert operator_overview["conversations"][0]["question"] == "What should I check for E102?"


def test_user_overview_requires_admin_role():
    token = create_user_token("operator", "operator@example.com")

    response = client.get("/admin/users/overview", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
