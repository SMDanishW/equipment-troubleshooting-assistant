from datetime import datetime, timezone
from typing import Any

from app.domain.conversations.ports import ConversationRepository


class ConversationApplicationService:
    def __init__(self, repository: ConversationRepository) -> None:
        self.repository = repository

    def start(self, *, user_id: str, question: str, equipment_name: str | None) -> Any:
        return self.repository.create(user_id=user_id, question=question, equipment_name=equipment_name)

    def complete(self, conversation: Any, final_answer: str) -> None:
        conversation.final_answer = final_answer
        conversation.status = "completed"
        conversation.completed_at = datetime.now(timezone.utc)
        self.repository.save(conversation)

    def fail(self, conversation: Any) -> None:
        conversation.status = "failed"
        conversation.completed_at = datetime.now(timezone.utc)
        self.repository.save(conversation)

    def list_for_admin(self, *, is_admin: bool, limit: int = 50) -> list[Any]:
        if not is_admin:
            raise PermissionError("Admin role required.")
        return self.repository.list_recent(limit)

    def get_visible(self, *, user_id: str, is_admin: bool, conversation_id: str) -> Any | None:
        if is_admin:
            return self.repository.get(conversation_id)
        return self.repository.get_for_user(user_id, conversation_id)
