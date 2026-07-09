from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.documents import DocumentRead


class AdminConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    equipment_name: str | None = None
    final_answer: str | None = None
    status: str
    created_at: datetime
    completed_at: datetime | None = None


class AdminUserOverviewRead(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    documents_count: int
    conversations_count: int
    documents: list[DocumentRead]
    conversations: list[AdminConversationRead]
