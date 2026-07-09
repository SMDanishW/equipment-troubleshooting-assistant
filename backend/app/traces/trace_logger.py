from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trace import AgentTrace


class TraceLogger:
    def __init__(self, db: Session, conversation_id: str) -> None:
        self.db = db
        self.conversation_id = conversation_id

    def log_agent(self, agent_name: str, agent_input: dict[str, Any], agent_output: dict[str, Any]) -> AgentTrace:
        sequence = self._next_sequence()
        now = datetime.now(timezone.utc)
        trace = AgentTrace(
            conversation_id=self.conversation_id,
            sequence=sequence,
            agent_name=agent_name,
            status="completed",
            input=_json_safe(agent_input),
            output=_json_safe(agent_output),
            started_at=now,
            completed_at=now,
        )
        self.db.add(trace)
        self.db.commit()
        return trace

    def _next_sequence(self) -> int:
        statement = select(AgentTrace.sequence).where(AgentTrace.conversation_id == self.conversation_id)
        values = list(self.db.execute(statement).scalars().all())
        return (max(values) + 1) if values else 1


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    return str(value)

