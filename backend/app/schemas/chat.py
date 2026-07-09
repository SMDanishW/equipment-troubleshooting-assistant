from typing import Any

from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    equipment_name: str | None = Field(default=None, max_length=255)
    document_ids: list[str] | None = Field(default=None, max_length=50)
    chat_history: list[ChatHistoryItem] = Field(default_factory=list, max_length=12)


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[dict[str, Any]]
    images: list[dict[str, Any]]
