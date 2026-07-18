from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.trace import Conversation


class SqlAlchemyConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, user_id: str, question: str, equipment_name: str | None) -> Conversation:
        conversation = Conversation(user_id=user_id, question=question, equipment_name=equipment_name)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        statement = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.agent_traces))
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_for_user(self, user_id: str, conversation_id: str) -> Conversation | None:
        statement = (
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .options(selectinload(Conversation.agent_traces))
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list_recent(self, limit: int = 50) -> list[Conversation]:
        statement = (
            select(Conversation)
            .options(selectinload(Conversation.agent_traces))
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(statement).scalars().all())

    def save(self, conversation: Conversation) -> None:
        self.db.add(conversation)
        self.db.commit()
