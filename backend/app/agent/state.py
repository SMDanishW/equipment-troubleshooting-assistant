from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.traces.trace_logger import TraceLogger


class AgentState(TypedDict, total=False):
    db: Session
    user_id: str
    question: str
    equipment_name: str | None
    document_ids: list[str] | None
    chat_history: list[dict[str, str]]
    conversation_id: str
    trace_logger: TraceLogger
    query_understanding: dict[str, Any]
    retrieval: dict[str, Any]
    diagnosis: dict[str, Any]
    troubleshooting_steps: dict[str, Any]
    guardrails: dict[str, Any]
    cross_check: dict[str, Any]
    revision_count: int
    final_answer: str
    citations: list[dict[str, Any]]
    images: list[dict[str, Any]]
