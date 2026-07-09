import os

os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.database import Base
from app.main import app
from app.models.document import Document, DocumentImage, TextChunk  # noqa: F401
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


def setup_function():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


client = TestClient(app)


def test_register_login_and_me_flow():
    register_response = client.post(
        "/auth/register",
        json={"username": "operator", "email": "operator@example.com", "password": "strong-password"},
    )

    assert register_response.status_code == 201
    register_body = register_response.json()
    assert register_body["token_type"] == "bearer"
    assert register_body["access_token"]
    assert register_body["user"]["username"] == "operator"
    assert register_body["user"]["role"] == "user"

    login_response = client.post(
        "/auth/login",
        json={"identifier": "operator", "password": "strong-password"},
    )

    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "operator@example.com"


def test_register_rejects_duplicate_email_or_username():
    payload = {"username": "operator", "email": "operator@example.com", "password": "strong-password"}

    assert client.post("/auth/register", json=payload).status_code == 201
    duplicate_response = client.post("/auth/register", json=payload)

    assert duplicate_response.status_code == 409


def test_login_rejects_invalid_password():
    client.post(
        "/auth/register",
        json={"username": "operator", "email": "operator@example.com", "password": "strong-password"},
    )

    response = client.post("/auth/login", json={"identifier": "operator", "password": "wrong-password"})

    assert response.status_code == 401
