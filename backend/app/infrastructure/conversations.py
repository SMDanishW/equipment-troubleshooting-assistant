from sqlalchemy.orm import Session

from app.application.conversations.service import ConversationApplicationService
from app.infrastructure.repositories.conversations import SqlAlchemyConversationRepository


def build_conversation_service(db: Session) -> ConversationApplicationService:
    return ConversationApplicationService(SqlAlchemyConversationRepository(db))
