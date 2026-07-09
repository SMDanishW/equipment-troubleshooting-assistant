from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.trace import Conversation


def get_conversation_for_user(db: Session, user_id: str, conversation_id: str) -> Conversation | None:
    statement = (
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .options(selectinload(Conversation.agent_traces))
    )
    return db.execute(statement).scalar_one_or_none()


def get_conversation_by_id(db: Session, conversation_id: str) -> Conversation | None:
    statement = select(Conversation).where(Conversation.id == conversation_id).options(selectinload(Conversation.agent_traces))
    return db.execute(statement).scalar_one_or_none()


def list_conversations(db: Session, limit: int = 50) -> list[Conversation]:
    statement = (
        select(Conversation)
        .options(selectinload(Conversation.agent_traces))
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())
