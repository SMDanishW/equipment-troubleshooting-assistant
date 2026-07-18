from io import BytesIO
from types import SimpleNamespace

import pytest

from app.agent.contracts import CrossCheckOutput, TroubleshootingOutput
from app.application.conversations.service import ConversationApplicationService
from app.application.ingestion.service import DocumentIngestionService
from app.infrastructure.storage.local import LocalArtifactStore


class FakeConversationRepository:
    def __init__(self) -> None:
        self.saved = []
        self.conversations = []

    def create(self, *, user_id, question, equipment_name):
        conversation = SimpleNamespace(
            id="conversation-1",
            user_id=user_id,
            question=question,
            equipment_name=equipment_name,
            status="running",
            final_answer=None,
            completed_at=None,
        )
        self.conversations.append(conversation)
        return conversation

    def save(self, conversation):
        self.saved.append(conversation)

    def get(self, conversation_id):
        return next((item for item in self.conversations if item.id == conversation_id), None)

    def get_for_user(self, user_id, conversation_id):
        return next(
            (item for item in self.conversations if item.id == conversation_id and item.user_id == user_id),
            None,
        )

    def list_recent(self, limit=50):
        return self.conversations[:limit]


class FakePipeline:
    def __init__(self) -> None:
        self.staged = []
        self.processed = []

    def stage(self, **kwargs):
        self.staged.append(kwargs)
        return SimpleNamespace(id="document-1")

    def process(self, document_id, *, final_failure_cleanup):
        self.processed.append((document_id, final_failure_cleanup))
        return SimpleNamespace(id=document_id, status="indexed")


def test_agent_contracts_reject_missing_grounding_fields():
    output = TroubleshootingOutput.model_validate(
        {"steps": [{"step": "Check cable", "evidence_ids": ["txt_1"], "risk_level": "low"}]}
    )
    assert output.steps[0].evidence_ids == ["txt_1"]
    with pytest.raises(ValueError):
        CrossCheckOutput.model_validate({"is_grounded": True})


def test_conversation_service_owns_lifecycle_and_visibility():
    repository = FakeConversationRepository()
    service = ConversationApplicationService(repository)
    conversation = service.start(user_id="user-1", question="Why?", equipment_name=None)

    service.complete(conversation, "Answer")

    assert conversation.status == "completed"
    assert conversation.final_answer == "Answer"
    assert service.get_visible(user_id="user-1", is_admin=False, conversation_id=conversation.id) is conversation
    assert service.get_visible(user_id="user-2", is_admin=False, conversation_id=conversation.id) is None
    with pytest.raises(PermissionError):
        service.list_for_admin(is_admin=False)


def test_ingestion_service_keeps_inline_and_worker_cleanup_policies_explicit():
    pipeline = FakePipeline()
    service = DocumentIngestionService(pipeline)

    result = service.ingest_inline(user=object(), upload=object(), equipment_name="Welder", document_type="manual")
    service.process_queued("document-2", final_attempt=False)

    assert result.id == "document-1"
    assert pipeline.processed == [("document-1", True), ("document-2", False)]


def test_local_artifact_store_saves_resolves_and_deletes_document(tmp_path):
    store = LocalArtifactStore(upload_root=tmp_path / "uploads", image_root=tmp_path / "images")
    upload = SimpleNamespace(filename="manual.pdf", file=BytesIO(b"pdf-data"))

    reference = store.save_upload(upload, user_id="user-1", document_id="document-1", max_bytes=100)
    image_dir = store.image_output_directory(user_id="user-1", document_id="document-1")
    image_dir.mkdir(parents=True)
    (image_dir / "figure.png").write_bytes(b"image")

    assert store.resolve(reference).read_bytes() == b"pdf-data"
    store.delete_document(user_id="user-1", document_id="document-1")
    assert not store.resolve(reference).exists()
    assert not image_dir.exists()
