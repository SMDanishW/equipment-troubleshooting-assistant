from collections.abc import Iterator
from datetime import datetime, timezone
from time import sleep
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import (
    cross_check_node,
    diagnosis_node,
    final_synthesis_node,
    guardrails_node,
    query_understanding_node,
    retrieval_node,
    troubleshooting_steps_node,
)
from app.models.trace import Conversation
from app.models.user import User
from app.schemas.chat import ChatResponse
from app.streaming.sse import chunk_text, sse_event
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
    final_answer: str
    citations: list[dict[str, Any]]
    images: list[dict[str, Any]]


AgentNode = Callable[[dict[str, Any]], dict[str, Any]]


STREAMING_STEPS: list[tuple[str, str, AgentNode]] = [
    ("query_understanding", "Query Understanding Agent", query_understanding_node),
    ("retrieval", "Retrieval Agent", retrieval_node),
    ("diagnosis", "Diagnosis Agent", diagnosis_node),
    ("troubleshooting_steps", "Troubleshooting Steps Agent", troubleshooting_steps_node),
    ("guardrails", "Guardrails Agent", guardrails_node),
    ("cross_check", "Cross-Check Agent", cross_check_node),
    ("final_synthesis", "Final Synthesis Agent", final_synthesis_node),
]


def build_troubleshooting_graph():
    graph = StateGraph(AgentState)
    graph.add_node("query_understanding", query_understanding_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("troubleshooting_steps", troubleshooting_steps_node)
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("cross_check", cross_check_node)
    graph.add_node("final_synthesis", final_synthesis_node)

    graph.add_edge(START, "query_understanding")
    graph.add_edge("query_understanding", "retrieval")
    graph.add_edge("retrieval", "diagnosis")
    graph.add_edge("diagnosis", "troubleshooting_steps")
    graph.add_edge("troubleshooting_steps", "guardrails")
    graph.add_edge("guardrails", "cross_check")
    graph.add_edge("cross_check", "final_synthesis")
    graph.add_edge("final_synthesis", END)
    return graph.compile()


def run_troubleshooting_graph(
    db: Session,
    user: User,
    question: str,
    equipment_name: str | None = None,
    document_ids: list[str] | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> ChatResponse:
    conversation = Conversation(user_id=user.id, question=question, equipment_name=equipment_name)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    trace_logger = TraceLogger(db=db, conversation_id=conversation.id)
    graph = build_troubleshooting_graph()
    state = graph.invoke(
        {
            "db": db,
            "user_id": user.id,
            "question": question,
            "equipment_name": equipment_name,
            "document_ids": document_ids,
            "chat_history": chat_history or [],
            "conversation_id": conversation.id,
            "trace_logger": trace_logger,
        }
    )

    _complete_conversation(db, conversation, state["final_answer"])
    db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        answer=state["final_answer"],
        citations=state.get("citations", []),
        images=state.get("images", []),
    )


def stream_troubleshooting_graph(
    db: Session,
    user: User,
    question: str,
    equipment_name: str | None = None,
    document_ids: list[str] | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> Iterator[str]:
    conversation = Conversation(user_id=user.id, question=question, equipment_name=equipment_name)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    state: dict[str, Any] = {
        "db": db,
        "user_id": user.id,
        "question": question,
        "equipment_name": equipment_name,
        "document_ids": document_ids,
        "chat_history": chat_history or [],
        "conversation_id": conversation.id,
        "trace_logger": TraceLogger(db=db, conversation_id=conversation.id),
    }

    try:
        for node_key, agent_name, node in STREAMING_STEPS:
            yield sse_event("agent_update", {"agent": node_key, "agent_name": agent_name, "status": "running"})
            update = node(state)
            state.update(update)
            if node_key == "retrieval":
                yield sse_event(
                    "retrieval_update",
                    {
                        "text_evidence_count": len(state["retrieval"]["text_evidence"]),
                        "image_evidence_count": len(state["retrieval"]["image_evidence"]),
                    },
                )
            yield sse_event("agent_update", {"agent": node_key, "agent_name": agent_name, "status": "completed"})

        final_answer = state["final_answer"]
        for token in chunk_text(final_answer, chunk_size=36):
            yield sse_event("token", {"content": token})
            sleep(0.015)
        yield sse_event("citation", {"citations": state.get("citations", [])})
        yield sse_event("image", {"images": state.get("images", [])})

        _complete_conversation(db, conversation, final_answer)
        db.commit()
        yield sse_event("done", {"conversation_id": conversation.id})
    except Exception as exc:
        conversation.status = "failed"
        db.commit()
        yield sse_event("error", {"message": str(exc), "conversation_id": conversation.id})


def _complete_conversation(db: Session, conversation: Conversation, final_answer: str) -> None:
    conversation.final_answer = final_answer
    conversation.status = "completed"
    conversation.completed_at = datetime.now(timezone.utc)
    db.add(conversation)
