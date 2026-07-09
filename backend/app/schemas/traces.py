from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    agent_name: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any]
    started_at: datetime
    completed_at: datetime


class ConversationTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    equipment_name: str | None = None
    final_answer: str | None = None
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    agent_traces: list[AgentTraceRead]

